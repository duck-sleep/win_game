// T14：板内 WebRTC 网关（JetKVM 的路 —— 用 pion 自带 ICE/DTLS/SRTP，不依赖 libnice 插件）。
//
// 数据流：fakevo --enc 的 rtph265pay 把 H.265 打成 RTP 丢到 127.0.0.1:5004，
// 这里收下来原样写进 pion 的一条 track。pion 会自己改 SSRC 和 PayloadType
// （见 track_local_static.go: packet.Header.SSRC = uint32(b.ssrc)），所以不用重打包。
//
// 信令沿用 webrtc_gw.py 那套，前端 webrtc.html 一个字都不用改：
//
//	GET  /offer   -> 本地 SDP 文本（非 trickle，等 ICE 收集完才返回）
//	POST /answer  <- 远端 SDP 文本
//	POST /stats   <- 浏览器 getStats 的一行，带时间戳落到 --stats 文件
//	GET  /state   -> 计数器
//
// 只服务一个观看端：新来 /offer 就把上一个连接拆掉。局域网，不用 STUN/TURN。
package main

import (
	"bytes"
	"encoding/json"
	"errors"
	"flag"
	"io"
	"log"
	"math"
	"net"
	"net/http"
	"os"
	"strconv"
	"sync"
	"sync/atomic"
	"time"

	"github.com/pion/rtp"
	"github.com/pion/webrtc/v4"
)

// session 是一条观看端连接。live 只有在 DTLS/SRTP 真的打通后才置位，
// rtp_sent 因此是"确实发出去了"，不是"往空管子里灌了多少"。
//
// 三条 datachannel 的划分和报文格式见 hid.go。
type session struct {
	pc    *webrtc.PeerConnection
	track *webrtc.TrackLocalStaticRTP
	live  atomic.Bool

	hid     *webrtc.DataChannel // 可靠：键盘 + 鼠标按键
	hidFast *webrtc.DataChannel // 保序不重传：鼠标移动
	rpc     *webrtc.DataChannel // JSON-RPC：滚轮 / 打字 / 查询
	hidOpen atomic.Bool
	rpcOpen atomic.Bool
	queue   chan []byte
	closed  sync.Once

	// latest 是"只保留最新一条"的移动槽位，doorbell 用来叫醒 worker。
	// 按键/键盘/文字都走 queue（要保序、不许被覆盖），只有纯移动走 latest。
	latest   atomic.Pointer[[]byte]
	doorbell chan struct{}
}

var (
	mu  sync.Mutex
	cur *session

	udpConn   *net.UDPConn
	statsFile string
	startAt   = time.Now()
	rpcURL    = "http://127.0.0.1:8000/rpc"
	rpcClient = &http.Client{Timeout: 2 * time.Second}

	rtpIn     uint64
	rtpSent   uint64
	rtpErr    uint64
	rtpNoPeer uint64
	bytesIn   uint64
	offers    uint64
)

// swap 装上这条新连接，并把旧的关掉。
func swap(s *session) {
	mu.Lock()
	old := cur
	cur = s
	mu.Unlock()
	if old != nil && old != s {
		_ = old.pc.Close()
		old.shutdown() // 被新观看端顶掉时不会走 retire，队列得在这儿关，否则 worker 泄漏
	}
}

// retire 只在"回调来自当前这条连接"时把它摘掉。
// 少了这个判断，newOffer 关旧连接时旧连接的 closed 回调会把刚装上的新连接清空，
// 浏览器的 /answer 就会撞上"没有活动连接"。
func retire(s *session) {
	mu.Lock()
	keep := cur != s
	if !keep {
		cur = nil
	}
	mu.Unlock()
	if !keep {
		s.shutdown()
	}
}

func newOffer() (string, error) {
	me := &webrtc.MediaEngine{}
	// 只注册 H.265：协商不上就直接失败，好过悄悄退回 H.264 让我们以为走通了
	h265cap := webrtc.RTPCodecCapability{MimeType: webrtc.MimeTypeH265, ClockRate: 90000}
	if err := me.RegisterCodec(webrtc.RTPCodecParameters{
		RTPCodecCapability: h265cap,
		PayloadType:        96,
	}, webrtc.RTPCodecTypeVideo); err != nil {
		return "", err
	}

	api := webrtc.NewAPI(webrtc.WithMediaEngine(me))
	pc, err := api.NewPeerConnection(webrtc.Configuration{})
	if err != nil {
		return "", err
	}
	tr, err := webrtc.NewTrackLocalStaticRTP(h265cap, "kvm-h265", "kvm-stream")
	if err != nil {
		return "", err
	}
	if _, err = pc.AddTrack(tr); err != nil {
		return "", err
	}

	gathered := make(chan struct{})
	var gatherOnce sync.Once
	s := &session{pc: pc, track: tr, queue: make(chan []byte, dcQueueLen), doorbell: make(chan struct{}, 1)}

	// 通道由板子这边先建、写进 offer，浏览器用 ondatachannel 接。
	// （JetKVM 是反过来的：浏览器建、设备 OnDataChannel 收 —— 那要配 perfect negotiation
	//   二次协商。我们的信令只有一次 offer/answer，所以换了方向建，报文格式完全照他。）
	ordered := true
	fast, err := pc.CreateDataChannel(dcLabelHIDFast, &webrtc.DataChannelInit{
		Ordered:        &ordered,      // 必须保序：乱序到达 = 光标一会儿新位置一会儿旧位置，来回跳
		MaxRetransmits: uint16Ptr(0), // 但一次都不重传：旧位置没有价值，宁可丢
	})
	if err != nil {
		return "", err
	}
	hid, err := pc.CreateDataChannel(dcLabelHID, &webrtc.DataChannelInit{Ordered: &ordered})
	if err != nil {
		return "", err
	}
	rpcdc, err := pc.CreateDataChannel(dcLabelRPC, &webrtc.DataChannelInit{Ordered: &ordered})
	if err != nil {
		return "", err
	}
	s.hid, s.hidFast, s.rpc = hid, fast, rpcdc

	onHID := func(ch *webrtc.DataChannel, m webrtc.DataChannelMessage) {
		if m.IsString || len(m.Data) == 0 {
			atomic.AddUint64(&dcBad, 1)
			return
		}
		body, reply, isMove := handleHIDMessage(s, m.Data)
		if len(reply) > 0 {
			if err := ch.Send(reply); err != nil {
				log.Printf("握手回包失败: %v", err)
			}
			return
		}
		if body == "" {
			return // 不支持的类型，handleHIDMessage 已经计过数
		}
		if isMove {
			// 覆盖式：新位置直接把还没转发的旧位置顶掉，绝不排队
			b := []byte(body)
			if s.latest.Swap(&b) != nil {
				atomic.AddUint64(&dcCoalesced, 1)
			}
			select {
			case s.doorbell <- struct{}{}:
			default: // worker 已经被叫过了，它会取到最新那条
			}
			return
		}
		// 按键/键盘/文字：进队列，保序、不许被覆盖
		select {
		case s.queue <- []byte(body):
		default:
			atomic.AddUint64(&dcDrop, 1) // 队列满：丢，不阻塞
		}
	}
	hid.OnMessage(func(m webrtc.DataChannelMessage) { onHID(hid, m) })
	fast.OnMessage(func(m webrtc.DataChannelMessage) { onHID(fast, m) })
	rpcdc.OnMessage(func(m webrtc.DataChannelMessage) {
		if len(m.Data) == 0 {
			return
		}
		atomic.AddUint64(&rpcIn, 1)
		// JetKVM 也是每条一个 goroutine：RPC 要保序的场景（打字）由服务端串行写 HID 保证
		go func(body []byte) {
			resp, err := postRPCBody(body)
			if err != nil {
				atomic.AddUint64(&rpcHTTPerr, 1)
				return
			}
			// 发**文本帧**（JetKVM 也是 SendText）：二进制帧会让对端 JSON.parse 拿到 ArrayBuffer
			if err := rpcdc.SendText(string(resp)); err != nil {
				atomic.AddUint64(&rpcWriteErr, 1)
			}
		}(append([]byte(nil), m.Data...))
	})

	hid.OnOpen(func() { s.hidOpen.Store(true); log.Printf("hid 通道打开") })
	hid.OnClose(func() { s.hidOpen.Store(false) })
	fast.OnOpen(func() { log.Printf("hid-unreliable 通道打开") })
	rpcdc.OnOpen(func() { s.rpcOpen.Store(true); log.Printf("jsonrpc 通道打开") })
	rpcdc.OnClose(func() { s.rpcOpen.Store(false) })
	go s.runHID()
	pc.OnICEGatheringStateChange(func(st webrtc.ICEGatheringState) {
		if st == webrtc.ICEGatheringStateComplete {
			gatherOnce.Do(func() { close(gathered) })
		}
	})
	pc.OnConnectionStateChange(func(st webrtc.PeerConnectionState) {
		switch st {
		case webrtc.PeerConnectionStateConnected:
			s.live.Store(true)
		case webrtc.PeerConnectionStateFailed, webrtc.PeerConnectionStateClosed:
			s.live.Store(false)
			retire(s)
		}
		log.Printf("连接状态: %s", st)
	})

	offer, err := pc.CreateOffer(nil)
	if err != nil {
		return "", err
	}
	if err = pc.SetLocalDescription(offer); err != nil {
		return "", err
	}
	select {
	case <-gathered:
	case <-time.After(5 * time.Second):
		log.Printf("警告: ICE 收集 5 秒没完成，先返回 offer")
	}

	// 必须回 LocalDescription：gather 是把 candidate 追加进 local description 的，
	// 直接用 CreateOffer 那份字符串会一个 candidate 都没有，ICE 永远连不上。
	ld := pc.LocalDescription()
	if ld == nil || !hasCandidate(ld.SDP) {
		_ = pc.Close()
		return "", errNoCandidate
	}

	swap(s)
	atomic.AddUint64(&offers, 1)
	return ld.SDP, nil
}

func applyAnswer(sdp string) error {
	mu.Lock()
	s := cur
	mu.Unlock()
	if s == nil {
		return errNoSession
	}
	return s.pc.SetRemoteDescription(webrtc.SessionDescription{
		Type: webrtc.SDPTypeAnswer,
		SDP:  sdp,
	})
}

// runHID 把 datachannel 队列里的报文翻译成 kvm_server 的 JSON-RPC 发给本机。
// 只用一条 worker 串行处理，保证鼠标"按下/松开"不会乱序。
func (s *session) runHID() {
	for {
		select {
		case body, ok := <-s.queue:
			if !ok {
				return // 队列被关 = 这条连接结束了
			}
			s.post(body)
		case <-s.doorbell:
			// 只发最新那一条移动，中间被顶掉的位置直接作废
			if p := s.latest.Swap(nil); p != nil {
				s.post(*p)
			}
		}
	}
}

func (s *session) post(body []byte) {
	if _, err := postRPCBody(body); err != nil {
		atomic.AddUint64(&dcHTTPerr, 1)
	}
}

// shutdown 关掉队列，让 worker 退出。retire 和 dc.OnClose 都可能先到，所以只关一次。
func (s *session) shutdown() {
	s.closed.Do(func() { close(s.queue) })
}

// postRPC 转给 kvm_server。HID 那套逻辑只有 Python 一份实现，网关不复制第二份。
// 必须把响应体读干净，否则 keep-alive 连接不会被复用（每次新建连接会多几毫秒）。
func postRPCBody(body []byte) ([]byte, error) {
	resp, err := rpcClient.Post(rpcURL, "application/json", bytes.NewReader(body))
	if err != nil {
		return nil, err
	}
	defer resp.Body.Close()
	out, err := io.ReadAll(io.LimitReader(resp.Body, rpcForwardLimit))
	if err != nil {
		return nil, err
	}
	if resp.StatusCode != http.StatusOK {
		return out, errors.New("rpc HTTP " + strconv.Itoa(resp.StatusCode))
	}
	return out, nil
}

// pump 把 UDP 上的 RTP 原样写给当前 track。
func pump() {
	buf := make([]byte, 2048)
	pkt := &rtp.Packet{}
	for {
		n, err := udpConn.Read(buf)
		if err != nil {
			log.Printf("udp 读错: %v", err)
			time.Sleep(50 * time.Millisecond)
			continue
		}
		atomic.AddUint64(&rtpIn, 1)
		atomic.AddUint64(&bytesIn, uint64(n))
		if err = pkt.Unmarshal(buf[:n]); err != nil {
			continue
		}
		mu.Lock()
		s := cur
		mu.Unlock()
		if s == nil || !s.live.Load() {
			atomic.AddUint64(&rtpNoPeer, 1)
			continue // 没打通，丢掉
		}
		if err = s.track.WriteRTP(pkt); err != nil {
			atomic.AddUint64(&rtpErr, 1)
			continue
		}
		atomic.AddUint64(&rtpSent, 1)
	}
}

func cors(w http.ResponseWriter) {
	w.Header().Set("Access-Control-Allow-Origin", "*")
	w.Header().Set("Access-Control-Allow-Headers", "Content-Type")
	w.Header().Set("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
}

type stateMsg struct {
	UptimeS   float64 `json:"uptime_s"`
	RtpIn     uint64  `json:"rtp_in"`
	RtpSent   uint64  `json:"rtp_sent"`
	RtpErr    uint64  `json:"rtp_err"`
	RtpNoPeer uint64  `json:"rtp_nopeer"`
	BytesIn   uint64  `json:"bytes_in"`
	KbpsIn    float64 `json:"kbps_in"`
	Offers    uint64  `json:"offers"`
	PeerLive  bool    `json:"peer_live"`
	DcOpen    bool   `json:"dc_open"`
	RpcOpen   bool   `json:"rpc_open"`
	DcIn      uint64 `json:"dc_in"`
	DcBad     uint64 `json:"dc_bad"`
	DcDrop    uint64 `json:"dc_drop"`
	DcHTTPerr uint64 `json:"dc_http_err"`
	DcUnsup   uint64 `json:"dc_unsupported"`
	DcCoalesc uint64 `json:"dc_coalesced"`
	RPCIn     uint64 `json:"rpc_in"`
	RPCHTTPer uint64 `json:"rpc_http_err"`
	RPCWriteE uint64 `json:"rpc_write_err"`
}

func handler() http.Handler {
	mux := http.NewServeMux()
	mux.HandleFunc("/", func(w http.ResponseWriter, r *http.Request) {
		cors(w)
		if r.Method == http.MethodOptions {
			w.WriteHeader(http.StatusNoContent)
			return
		}
		switch r.URL.Path {
		case "/offer":
			sdp, err := newOffer()
			if err != nil {
				log.Printf("offer 失败: %v", err)
				w.WriteHeader(500)
				_, _ = w.Write([]byte("offer failed: " + err.Error() + "\n"))
				return
			}
			w.Header().Set("Content-Type", "text/plain")
			_, _ = w.Write([]byte(sdp))
		case "/answer":
			body, _ := readAll(r)
			if err := applyAnswer(body); err != nil {
				log.Printf("answer 失败: %v", err)
				w.WriteHeader(500)
				_, _ = w.Write([]byte(err.Error() + "\n"))
				return
			}
			w.Header().Set("Content-Type", "text/plain")
			_, _ = w.Write([]byte("ok\n"))
		case "/stats":
			body, _ := readAll(r)
			f, err := os.OpenFile(statsFile, os.O_APPEND|os.O_CREATE|os.O_WRONLY, 0o644)
			if err != nil {
				w.WriteHeader(500)
				_, _ = w.Write([]byte(err.Error() + "\n"))
				return
			}
			defer f.Close()
			_, _ = f.WriteString(time.Now().Format("15:04:05 ") + oneLine(body) + "\n")
			w.Header().Set("Content-Type", "text/plain")
			_, _ = w.Write([]byte("ok\n"))
		case "/state":
			mu.Lock()
			s := cur
			mu.Unlock()
			up := time.Since(startAt).Seconds()
			st := stateMsg{
				UptimeS:   math.Round(up*10) / 10,
				RtpIn:     atomic.LoadUint64(&rtpIn),
				RtpSent:   atomic.LoadUint64(&rtpSent),
				RtpErr:    atomic.LoadUint64(&rtpErr),
				RtpNoPeer: atomic.LoadUint64(&rtpNoPeer),
				BytesIn:   atomic.LoadUint64(&bytesIn),
				Offers:    atomic.LoadUint64(&offers),
				DcIn:      atomic.LoadUint64(&dcIn),
				DcBad:     atomic.LoadUint64(&dcBad),
				DcDrop:    atomic.LoadUint64(&dcDrop),
				DcHTTPerr: atomic.LoadUint64(&dcHTTPerr),
				DcUnsup:   atomic.LoadUint64(&dcUnsupport),
				DcCoalesc: atomic.LoadUint64(&dcCoalesced),
				RPCIn:     atomic.LoadUint64(&rpcIn),
				RPCHTTPer: atomic.LoadUint64(&rpcHTTPerr),
				RPCWriteE: atomic.LoadUint64(&rpcWriteErr),
			}
			if s != nil {
				st.PeerLive = s.live.Load()
				st.DcOpen = s.hidOpen.Load()
				st.RpcOpen = s.rpcOpen.Load()
			}
			if up > 0 {
				st.KbpsIn = float64(st.BytesIn) * 8 / 1000 / up
			}
			w.Header().Set("Content-Type", "application/json")
			_ = json.NewEncoder(w).Encode(st)
		default:
			http.NotFound(w, r)
		}
	})
	return mux
}

func main() {
	var (
		port    = flag.Int("port", 8001, "HTTP 信令端口")
		rtpPort = flag.Int("rtp-port", 5004, "板内 RTP 收流端口")
		stats   = flag.String("stats", "/tmp/webrtc_stats.log", "浏览器统计落盘路径")
		rpc     = flag.String("rpc", "http://127.0.0.1:8000/rpc", "板内 JSON-RPC 地址（datachannel 的鼠标报文转发到这里）")
	)
	flag.Parse()
	statsFile = *stats
	rpcURL = *rpc

	var err error
	udpConn, err = net.ListenUDP("udp", &net.UDPAddr{IP: net.IPv4(127, 0, 0, 1), Port: *rtpPort})
	if err != nil {
		log.Fatalf("监听 127.0.0.1:%d 失败: %v", *rtpPort, err)
	}
	go pump()

	log.Printf("WebRTC 网关(pion) :%d  RTP <- 127.0.0.1:%d  统计 -> %s",
		*port, *rtpPort, *stats)
	srv := &http.Server{
		Addr:              net.JoinHostPort("0.0.0.0", itoa(*port)),
		Handler:           handler(),
		ReadHeaderTimeout: 5 * time.Second,
	}
	log.Fatal(srv.ListenAndServe())
}
