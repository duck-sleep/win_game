---
name: usb-gadget-hid-bringup
description: 把 Linux 板子（RK3566/DWC3 这类）点亮成 USB 键盘+鼠标，以及"设备侧全对但主机不认"的排查顺序。触发词：configfs、usb_gadget、hidg、HID gadget、板子插电脑没反应、复合设备不枚举、adb 和 hid 抢 UDC。
---

# USB HID gadget 点亮与排障（板子 → 电脑）

2026-10-17 在 K11C(RK3566) 上做 IP-KVM 时总结。四条都能白耗半天，所以写死成清单。

## 装配顺序（错一步就静默失败）

```
1) 解绑：对 /sys/kernel/config/usb_gadget/* 里每个已绑的 gadget 执行  echo "" > $g/UDC
2) 建 gadget 本体：idVendor/idProduct/bcdUSB/bDeviceClass... + strings/0x409 + configs/b.1
3) 建 function：functions/hid.usbN/{protocol,subclass,report_length,no_out_endpoint,report_desc}
4) 链进 config：ln -s functions/hid.usbN configs/b.1/hid.usbN      ← 必须在解绑状态下做
5) 绑定：echo <udc> > $G/UDC
```

- 🔴 **第 4 步在已绑定时返回 EBUSY**。脚本里**千万别给 `ln -s` 加 `|| true`** —— 我这么干过一次，
  结果"function 全建好了、config 里只有原来那一个"，看起来像内核不支持 HID，实际是链没上。
- 判据：`ls $G/configs/b.1/` 必须能看到每个 function 的软链；`ls /dev/hidg*` 有节点才算绑上。

## 主机不认的第一嫌疑：VID/PID 撞了已装过的驱动

沿用板子出厂的 `VID_2207&PID_0006`（Rockchip adb）时，Windows 上装过的 Android 驱动会
**按硬件 ID 把复合设备的父节点整台认领**，`MI_xx` 子设备根本不生成 —— 现象是"加了 HID 接口但电脑毫无反应"。

```powershell
Get-PnpDevice -PresentOnly | Where-Object { $_.InstanceId -match '1D6B' }
```
- 只看到 `AndroidUsbDeviceClass`、**没有任何 `MI_` 子节点** ⇒ 就是这个坑。
- 解法：**换自己的 VID/PID**（验证过 `1d6b:0104` 可用）+ 明确声明复合：
  `bDeviceClass=0xEF`、`bDeviceSubClass=0x02`、`bDeviceProtocol=0x01`。
- 另一种"读描述符就失败"会长成 `USB\VID_0000&PID_0000`，查的时候别只 grep 自己的 VID。

## 属性可用性要逐个试，别照抄别的内核

`wakeup_on_write` 是 JetKVM 那颗 5.10 的厂改属性，**RK3566 SDK 的 6.1 没有**，写它 `Permission denied`。
先看有什么：`ls -l /sys/kernel/config/usb_gadget/<g>/functions/hid.usb0/`。
（顺带：`systemctl is-masked` 在部分 systemd 版本不存在，会报 `Unknown command verb`，用 `ls -l` 看软链更可靠。）

## 换 gadget 会踢掉你自己的通道

把 adb 换掉的那一瞬间 **adbd 死，它派生的脚本也跟着被带走**（`setsid nohup` 也没扛住）。

- 要跑完整个"解绑→改→重绑"，用 **`systemd-run --collect --unit=x /bin/sh /path/x.sh`**（交给 PID1）。
- 或者提前把日志重定向到文件，事后用**不受影响的通道**去读（调试串口 / ACM 的 `/dev/ttyGS0`→主机 COM 口）。
- ACM 控制台值得常挂：它是"网络挂了、WiFi 配错了"之后唯一的自救入口。

## 无人验证法（别靠人眼看屏幕）

"字有没有真的打进主机"——用**剪贴板回读**闭环：

1. 主机开记事本/Notepad++ 并置为前台（PowerShell `SetForegroundWindow`，用 `.ps1` 文件跑，
   别在 bash 里内嵌 `$_`/`$()`，会被 bash 吃掉）
2. 板子：发文本 → `Ctrl+A` → `Ctrl+C`
3. 主机：`Get-Clipboard` 比对

鼠标用坐标闭环：发 `(0.5,0.5)`，读 `[System.Windows.Forms.Cursor]::Position`，
1920×1080 上应落在 ≈`960,540`。

⚠️ **中文输入法会把字母吃进候选框**，不进文档 —— 表现极像"键盘坏了"，但 CapsLock 照样生效（IME 不拦它）。
测之前先让板子发 `Ctrl+Space` 切英文。

## 两端状态怎么对上（判断卡在哪一层）

| 板子 `cat /sys/class/udc/*/state` | 主机侧 | 含义 |
|---|---|---|
| `not_attached` | 无设备 | 线/供电问题，主机电都没到 |
| `addressed` | 无设备节点 | 主机会话没建立：要么线不在这台机器上，要么描述符阶段就失败 |
| `addressed` | 只有父节点、无 `MI_` | **VID/PID 撞驱动认领**（上面那节） |
| `configured` | 有 `MI_` 但功能不对 | report descriptor / 报文格式问题，回到 `lsusb -v` 与主机 HID 描述符比对 |
| `configured` | 键鼠都正常 | 通了，去做上层 |

## 相关文件（本项目）

- 方案与实测记录：`12_win_上机跑\14_K11C做JetKVM式IP-KVM_方案.md`（§2-Q18 移植清单、§5.4 实测记录）
- 可跑脚本：`26_k11c_kvm\gadget\k11c-gadget.sh`（开机自启版）、`k11c_hid.py`（发报文）、`port\k11cd.py`（RPC）
