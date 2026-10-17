#!/bin/sh
# 端到端演示：起 HID gadget，然后让板子真的往这台笔记本上打字
#   Win+R  ->  输入 notepad  ->  回车
# 判据：Windows 侧 notepad 进程出现（不需要人眼看屏幕）
ACM="${1:-withacm}"
systemctl stop usb-gadget 2>/dev/null || true
sleep 1
sh /root/k11c/k11c_min.sh "$ACM"
echo "等主机枚举..."
sleep 12
python3 -c '
import sys, time
sys.path.insert(0, "/root/k11c")
import k11c_hid as h

def tap(mod, code):
    h.write(h.KB, [mod, 0, code, 0, 0, 0, 0, 0])
    h.write(h.KB, [0, 0, 0, 0, 0, 0, 0, 0])

tap(0x08, 0x15)          # GUI + R  -> 运行对话框
time.sleep(2.0)
h.type_text("notepad")   # 打字
time.sleep(0.6)
tap(0, 0x28)             # Enter
print("KEYS_SENT")
'
echo DEMO_DONE
