package main

// k11c-cloud: answer JetKVM-cloud WebRTC sessions from this board.
//
// Flow (mirrors JetKVM device side):
//   dial wss://api.jetkvm.com/ with the long-lived secretToken
//   cloud pushes {"type":"offer","data":{sd(base64 of {type,sdp}), ip, iceServers, OidcGoogle}}
//   we answer with an H.265 track fed by fakevo's RTP, then send
//   {"type":"answer","data": base64(JSON{type:"answer",sdp})}
//
// Notes:
//   * iceServers from the cloud only contains STUN. We also append the public IP the
//     cloud observed as an srflx candidate (SetICEAddressRewriteRules), same trick as
//     JetKVM's webrtc.go so no STUN query is needed when the NAT keeps ports.
//   * fakevo hardcodes RTP to 127.0.0.1:5004 pt=96, so this binary must own that port;
//     stop k11c-gw while testing.

import (
	"context"
	"encoding/base64"
	"encoding/binary"
	"encoding/json"
	"flag"
	"fmt"
	"io"
	"log"
	"net"
	"net/http"
	"os"
	"regexp"
	"strconv"
	"strings"
	"sync/atomic"
	"time"

	"github.com/coder/websocket"
	"github.com/pion/rtp"
	"github.com/pion/webrtc/v4"
)

type state struct {
	DeviceID string `json:"deviceId"`
	SKU      string `json:"sku"`
	Secret   string `json:"secretToken"`
}

type sigMsg struct {
	Type string          `json:"type"`
	Data json.RawMessage `json:"data"`
}

type offerData struct {
	SD         string   `json:"sd"`
	IP         string   `json:"ip"`
	ICEServers []string `json:"iceServers"`
	OidcGoogle string   `json:"OidcGoogle"`
}

type sdpMsg struct {
	Type string `json:"type"`
	SDP  string `json:"sdp"`
}

var (
	statePath = flag.String("state", "/tmp/k11c-cloud.json", "token state file")
	rtpAddr   = flag.String("rtp", "127.0.0.1:5004", "fakevo RTP input")
	curTrack  atomic.Pointer[webrtc.TrackLocalStaticRTP]
	curPC     atomic.Pointer[webrtc.PeerConnection]
	curPT     atomic.Int32
	rpcDC     atomic.Pointer[webrtc.DataChannel]
	hidDC     atomic.Pointer[webrtc.DataChannel]
)

const localRPC = "http://127.0.0.1:8000/rpc"

var httpClient = &http.Client{Timeout: 3 * time.Second}

// postLocal forwards one JSON-RPC call to kvm_server.py (same target our gateway uses),
// so the cloud path reuses the single HID implementation.
func postLocal(body string) {
	resp, err := httpClient.Post(localRPC, "application/json", strings.NewReader(body))
	if err != nil {
		log.Printf("local rpc: %v", err)
		return
	}
	_, _ = io.Copy(io.Discard, resp.Body)
	_ = resp.Body.Close()
}

// handleHID maps JetKVM's hidrpc binary framing to the JSON-RPC calls kvm_server.py serves.
// Layout matches board/gw/hid.go: [type][payload...].
func handleHID(data []byte) {
	if len(data) < 1 {
		return
	}
	switch data[0] {
	case 0x03: // PointerReport: x int32 BE, y int32 BE, buttons u8
		if len(data) != 10 {
			log.Printf("hid pointer bad length %d", len(data))
			return
		}
		x := int32(binary.BigEndian.Uint32(data[1:5]))
		y := int32(binary.BigEndian.Uint32(data[5:9]))
		postLocal(fmt.Sprintf(`{"id":0,"method":"absMouseReport","params":{"x":%d,"y":%d,"buttons":%d}}`,
			x, y, data[9]))
	case 0x02: // KeyboardReport: modifiers u8, keys...
		if len(data) < 3 {
			return
		}
		keys := make([]string, 0, len(data)-2)
		for _, k := range data[2:] {
			keys = append(keys, strconv.Itoa(int(k)))
		}
		postLocal(fmt.Sprintf(`{"id":0,"method":"keyboardReport","params":{"modifiers":%d,"keys":[%s]}}`,
			data[1], strings.Join(keys, ",")))
	case 0x05: // KeypressReport: key u8, pressed u8
		if len(data) < 3 {
			return
		}
		postLocal(fmt.Sprintf(`{"id":0,"method":"keypressReport","params":{"keyCode":%d,"pressed":%t,"modifiers":0}}`,
			data[1], data[2] == 1))
	default:
		log.Printf("hid type 0x%02x not handled (%d bytes)", data[0], len(data))
	}
}

// handleRPC answers the JSON-RPC calls the cloud UI makes on the "rpc" channel.
// Response shapes were read from the open-source UI (kvm/ui/src/hooks/stores.ts).
// Unknown methods get -32601 so the UI takes its documented fallback path.
func handleRPC(dc *webrtc.DataChannel, data []byte) {
	var req struct {
		ID     json.RawMessage `json:"id"`
		Method string          `json:"method"`
	}
	if err := json.Unmarshal(data, &req); err != nil {
		log.Printf("dc[rpc] bad json: %v", err)
		return
	}
	var result any
	switch req.Method {
	case "getVideoState":
		result = map[string]any{"ready": true}
	case "getNetworkSettings":
		result = map[string]any{"hostname": "k11c"}
	case "getKeyboardLedState":
		result = map[string]any{"num_lock": false, "caps_lock": false, "scroll_lock": false,
			"compose": false, "kana": false, "shift": false}
	case "getKeyDownState":
		result = map[string]any{"modifier": 0, "keys": []int{}}
	case "getKeyboardMacros":
		result = []any{}
	case "getLocalVersion":
		result = map[string]any{"current": "6.1.0-k11c", "build": "k11c-cloud"}
	case "ping":
		result = "pong"
	default:
		b, _ := json.Marshal(map[string]any{"jsonrpc": "2.0", "id": req.ID,
			"error": map[string]any{"code": -32601, "message": "method not found: " + req.Method}})
		_ = dc.SendText(string(b))
		log.Printf("dc[rpc] %s -> method not found", req.Method)
		return
	}
	b, _ := json.Marshal(map[string]any{"jsonrpc": "2.0", "id": req.ID, "result": result})
	_ = dc.SendText(string(b))
	log.Printf("dc[rpc] %s -> ok", req.Method)
}

var reH265 = regexp.MustCompile(`a=rtpmap:(\d+) H265/90000`)

func loadState() (*state, error) {
	b, err := os.ReadFile(*statePath)
	if err != nil {
		return nil, err
	}
	var s state
	if err := json.Unmarshal(b, &s); err != nil {
		return nil, err
	}
	if s.DeviceID == "" || s.Secret == "" {
		return nil, fmt.Errorf("state file missing deviceId/secretToken")
	}
	return &s, nil
}

func main() {
	flag.Parse()
	st, err := loadState()
	if err != nil {
		log.Fatalf("state: %v", err)
	}
	go feedRTP()

	hdr := http.Header{}
	hdr.Set("Authorization", "Bearer "+st.Secret)
	hdr.Set("X-Device-ID", st.DeviceID)
	hdr.Set("X-App-Version", "0.5.0-k11c")
	hdr.Set("X-Device-SKU", st.SKU)

	ctx := context.Background()
	for {
		log.Printf("dialing wss://api.jetkvm.com/ as %s sku=%s", st.DeviceID, st.SKU)
		c, _, err := websocket.Dial(ctx, "wss://api.jetkvm.com/", &websocket.DialOptions{
			HTTPHeader: hdr,
			// the cloud pings every 10s and drops us if we look dead
		})
		if err != nil {
			log.Printf("dial failed: %v (retry in 5s)", err)
			time.Sleep(5 * time.Second)
			continue
		}
		log.Printf("connected")
		readLoop(ctx, c)
		_ = c.CloseNow()
		log.Printf("ws closed, retry in 3s")
		time.Sleep(3 * time.Second)
	}
}

func readLoop(ctx context.Context, c *websocket.Conn) {
	for {
		typ, data, err := c.Read(ctx)
		if err != nil {
			log.Printf("ws read: %v", err)
			return
		}
		if typ != websocket.MessageText {
			continue
		}
		var m sigMsg
		if err := json.Unmarshal(data, &m); err != nil {
			log.Printf("bad ws json: %v", err)
			continue
		}
		switch m.Type {
		case "offer":
			log.Printf("offer received (%d bytes)", len(m.Data))
			go func(raw json.RawMessage) {
				if err := handleOffer(ctx, c, raw); err != nil {
					log.Printf("offer: %v", err)
				}
			}(m.Data)
		case "new-ice-candidate":
			var cand webrtc.ICECandidateInit
			if err := json.Unmarshal(m.Data, &cand); err != nil {
				log.Printf("bad candidate: %v", err)
				continue
			}
			if pc := curPC.Load(); pc != nil && cand.Candidate != "" {
				if err := pc.AddICECandidate(cand); err != nil {
					log.Printf("add candidate: %v", err)
				}
			}
		default:
			log.Printf("ws msg type=%s (%d bytes)", m.Type, len(m.Data))
		}
	}
}

func handleOffer(ctx context.Context, c *websocket.Conn, raw json.RawMessage) error {
	var od offerData
	if err := json.Unmarshal(raw, &od); err != nil {
		return fmt.Errorf("parse offer data: %w", err)
	}
	sdRaw, err := base64.StdEncoding.DecodeString(od.SD)
	if err != nil {
		return fmt.Errorf("base64 sd: %w", err)
	}
	var sd sdpMsg
	if err := json.Unmarshal(sdRaw, &sd); err != nil {
		return fmt.Errorf("parse sd: %w", err)
	}

	pt := uint8(96)
	if m := reH265.FindStringSubmatch(sd.SDP); m != nil {
		v, _ := strconv.Atoi(m[1])
		pt = uint8(v)
	}
	curPT.Store(int32(pt))
	log.Printf("offer sdp=%d bytes, H265 pt=%d, ip=%s, ice=%v", len(sd.SDP), pt, od.IP, od.ICEServers)

	me := &webrtc.MediaEngine{}
	if err := me.RegisterCodec(webrtc.RTPCodecParameters{
		RTPCodecCapability: webrtc.RTPCodecCapability{
			MimeType:  webrtc.MimeTypeH265,
			ClockRate: 90000,
			SDPFmtpLine: "profile-id=1",
		},
		PayloadType: webrtc.PayloadType(pt),
	}, webrtc.RTPCodecTypeVideo); err != nil {
		return fmt.Errorf("register H265: %w", err)
	}

	se := webrtc.SettingEngine{}
	if ip := net.ParseIP(od.IP); ip != nil {
		if err := se.SetICEAddressRewriteRules(webrtc.ICEAddressRewriteRule{
			CIDR:            "0.0.0.0/0",
			External:        []string{od.IP},
			Mode:            webrtc.ICEAddressRewriteAppend,
			AsCandidateType: webrtc.ICECandidateTypeSrflx,
		}); err != nil {
			log.Printf("address rewrite: %v", err)
		}
	}

	api := webrtc.NewAPI(webrtc.WithMediaEngine(me), webrtc.WithSettingEngine(se))
	var iceServers []webrtc.ICEServer
	for _, u := range od.ICEServers {
		iceServers = append(iceServers, webrtc.ICEServer{URLs: []string{u}})
	}
	pc, err := api.NewPeerConnection(webrtc.Configuration{ICEServers: iceServers})
	if err != nil {
		return fmt.Errorf("new pc: %w", err)
	}

	track, err := webrtc.NewTrackLocalStaticRTP(webrtc.RTPCodecCapability{
		MimeType: webrtc.MimeTypeH265, ClockRate: 90000,
	}, "video", "k11c-h265")
	if err != nil {
		return fmt.Errorf("track: %w", err)
	}
	if _, err := pc.AddTrack(track); err != nil {
		return fmt.Errorf("add track: %w", err)
	}

	pc.OnDataChannel(func(dc *webrtc.DataChannel) {
		log.Printf("datachannel opened label=%q id=%d", dc.Label(), dc.ID())
		switch dc.Label() {
		case "rpc":
			rpcDC.Store(dc)
		case "hidrpc":
			hidDC.Store(dc)
		}
		dc.OnMessage(func(m webrtc.DataChannelMessage) {
			if !m.IsString {
				// hidrpc handshake: peer sends 0x01 and waits for an echo before it
				// considers the channel usable (same rule as our gateway)
				if len(m.Data) > 0 && m.Data[0] == 0x01 {
					_ = dc.Send([]byte{0x01, 0x01})
					log.Printf("dc[%s] handshake echoed", dc.Label())
					return
				}
				if strings.HasPrefix(dc.Label(), "hidrpc") {
					handleHID(m.Data)
					return
				}
				log.Printf("dc[%s] <- binary %d bytes: %x", dc.Label(), len(m.Data), m.Data[:min(len(m.Data), 16)])
				return
			}
			handleRPC(dc, m.Data)
		})
	})
	pc.OnICEConnectionStateChange(func(s webrtc.ICEConnectionState) {
		log.Printf("ice state: %s", s)
	})
	pc.OnConnectionStateChange(func(s webrtc.PeerConnectionState) {
		log.Printf("pc state: %s", s)
	})

	if err := pc.SetRemoteDescription(webrtc.SessionDescription{Type: webrtc.SDPTypeOffer, SDP: sd.SDP}); err != nil {
		return fmt.Errorf("set remote: %w", err)
	}
	ans, err := pc.CreateAnswer(nil)
	if err != nil {
		return fmt.Errorf("create answer: %w", err)
	}
	gatherDone := webrtc.GatheringCompletePromise(pc)
	if err := pc.SetLocalDescription(ans); err != nil {
		return fmt.Errorf("set local: %w", err)
	}
	select {
	case <-gatherDone:
	case <-time.After(6 * time.Second):
		log.Printf("ice gathering did not finish in 6s, sending what we have")
	}
	local := pc.LocalDescription()
	if local == nil {
		return fmt.Errorf("no local description")
	}

	payload, _ := json.Marshal(sdpMsg{Type: "answer", SDP: local.SDP})
	out, _ := json.Marshal(map[string]string{"type": "answer", "data": base64.StdEncoding.EncodeToString(payload)})
	if err := c.Write(ctx, websocket.MessageText, out); err != nil {
		return fmt.Errorf("send answer: %w", err)
	}
	log.Printf("answer sent (%d bytes sdp)", len(local.SDP))

	curPC.Store(pc)
	curTrack.Store(track)
	return nil
}

// feedRTP reads fakevo's RTP and forwards it to the latest track.
func feedRTP() {
	addr, err := net.ResolveUDPAddr("udp", *rtpAddr)
	if err != nil {
		log.Fatalf("rtp addr: %v", err)
	}
	conn, err := net.ListenUDP("udp", addr)
	if err != nil {
		log.Fatalf("rtp listen %s: %v (is k11c-gw still running?)", *rtpAddr, err)
	}
	log.Printf("rtp listening on %s", *rtpAddr)
	buf := make([]byte, 2048)
	var n int
	for {
		sz, _, err := conn.ReadFromUDP(buf)
		if err != nil {
			log.Printf("rtp read: %v", err)
			return
		}
		tr := curTrack.Load()
		if tr == nil {
			continue
		}
		var pkt rtp.Packet
		if err := pkt.Unmarshal(buf[:sz]); err != nil {
			continue
		}
		pkt.PayloadType = uint8(curPT.Load())
		if n%300 == 0 {
			log.Printf("rtp #%d seq=%d ts=%d pt=%d", n, pkt.SequenceNumber, pkt.Timestamp, pkt.PayloadType)
		}
		n++
		_ = tr.WriteRTP(&pkt)
	}
}
