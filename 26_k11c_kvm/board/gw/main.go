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
	"encoding/json"
	"flag"
	"log"
	"math"
	"net"
	"net/http"
	"os"
	"sync"
	"sync/atomic"
	"time"

	"github.com/pion/rtp"
	"github.com/pion/webrtc/v4"
)

// session 是一条观看端连接。live 只有在 DTLS/SRTP 真的打通后才置位，
// rtp_sent 因此是"确实发出去了"，不是"往空管子里灌了多少"。
type session struct {
	pc    *webrtc.PeerConnection
	track *webrtc.TrackLocalStaticRTP
	live  atomic.Bool
}

var (
	mu  sync.Mutex
	cur *session

	udpConn   *net.UDPConn
	statsFile string
	startAt   = time.Now()

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
	}
}

// retire 只在"回调来自当前这条连接"时把它摘掉。
// 少了这个判断，newOffer 关旧连接时旧连接的 closed 回调会把刚装上的新连接清空，
// 浏览器的 /answer 就会撞上"没有活动连接"。
func retire(s *session) {
	mu.Lock()
	if cur == s {
		cur = nil
	}
	mu.Unlock()
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
	s := &session{pc: pc, track: tr}
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
			}
			if s != nil {
				st.PeerLive = s.live.Load()
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
	)
	flag.Parse()
	statsFile = *stats

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
