package main

// 照 jetkvm/kvm 的通道划分（读 main 分支 webrtc.go / hidrpc.go / internal/hidrpc/*.go 得到）：
//
//	hid            可靠有序   —— 键盘报文、按键按下/松开、鼠标按键
//	hid-unreliable 不可靠      —— 鼠标移动。丢了就丢了，新的位置马上覆盖旧的，
//	                              重传只会让"最新位置"更晚到，反而更卡
//	jsonrpc        可靠有序   —— 其余 JSON-RPC（滚轮、打字、能力查询）
//
// 报文格式 [1 字节类型][载荷]，和 JetKVM 逐字节一致：
//
//	0x01 Handshake    [ver]              设备原样回一条，表示这条通道能用
//	0x02 KeyboardRep  [modifiers][keys…]
//	0x03 PointerRep   [x int32 BE][y int32 BE][buttons u8]
//	0x05 KeypressRep  [key u8][press u8]
//
// 0x04 WheelReport 在 JetKVM 设备侧**根本没有 case**（滚轮走 JSON-RPC），我们照此不实现；
// 0x06 MouseReport 是相对鼠标，本固件没挂 hidg2，收到只计数。

import (
	"encoding/binary"
	"strconv"
	"sync/atomic"
)

const (
	msgHandshake    = 0x01
	msgKeyboard     = 0x02
	msgPointer      = 0x03
	msgKeypress     = 0x05
	hidVersion      = 0x01
	pointerMsgLen   = 10
	keyboardMsgMin  = 2
	keypressMsgLen  = 3
	dcLabelHID      = "hid"
	dcLabelHIDFast  = "hid-unreliable"
	dcLabelRPC      = "jsonrpc"
	dcQueueLen      = 64
	rpcForwardLimit = 1 << 16
)

var (
	dcIn         uint64
	dcBad        uint64
	dcDrop       uint64
	dcHTTPerr    uint64
	dcUnsupport  uint64
	rpcIn        uint64
	rpcHTTPerr   uint64
	rpcWriteErr  uint64
)

// handleHIDMessage 解析一条二进制报文，返回要发给 kvm_server 的 JSON-RPC 请求体。
// 返回空串表示这条不需要转发（握手已在通道里回掉了 / 不支持的类型）。
func handleHIDMessage(s *session, data []byte) (string, []byte, bool) {
	if len(data) < 1 {
		atomic.AddUint64(&dcBad, 1)
		return "", nil, false
	}
	atomic.AddUint64(&dcIn, 1)
	switch data[0] {
	case msgHandshake:
		// 照 JetKVM：原样回一条握手，对端收到才认为 hidrpc 可用
		return "", []byte{msgHandshake, hidVersion}, true
	case msgPointer:
		if len(data) != pointerMsgLen {
			atomic.AddUint64(&dcBad, 1)
			return "", nil, false
		}
		x := int32(binary.BigEndian.Uint32(data[1:5]))
		y := int32(binary.BigEndian.Uint32(data[5:9]))
		return `{"id":0,"method":"absMouseReport","params":{"x":` +
			strconv.FormatInt(int64(x), 10) + `,"y":` +
			strconv.FormatInt(int64(y), 10) + `,"buttons":` +
			strconv.Itoa(int(data[9])) + `}}`, nil, false
	case msgKeyboard:
		if len(data) < keyboardMsgMin {
			atomic.AddUint64(&dcBad, 1)
			return "", nil, false
		}
		mods := int(data[1])
		keys := make([]string, 0, len(data)-2)
		for _, k := range data[2:] {
			keys = append(keys, strconv.Itoa(int(k)))
		}
		return `{"id":0,"method":"keyboardReport","params":{"modifiers":` +
			strconv.Itoa(mods) + `,"keys":[` + joinComma(keys) + `]}}`, nil, false
	case msgKeypress:
		if len(data) != keypressMsgLen {
			atomic.AddUint64(&dcBad, 1)
			return "", nil, false
		}
		return `{"id":0,"method":"keypressReport","params":{"keyCode":` +
			strconv.Itoa(int(data[1])) + `,"pressed":` +
			strconv.FormatBool(data[2] == 1) + `,"modifiers":0}}`, nil, false
	default:
		// 0x04 滚轮 / 0x06 相对鼠标 / 0x07 宏：不假装处理，计数并说明原因
		atomic.AddUint64(&dcUnsupport, 1)
		return "", nil, false
	}
}
