# 推送文件到 SNM970 掌机 SSD

适用：把 PC 上的 ROM/ISO/大文件传到掌机（SNM970 / kalama）的 SSD 或内部存储。

## 核心结论（先看这条）

**大文件一律走 USB。** 实测对比（6.4GB 文件，09-11）：

| 通道 | 速度 | 6.4GB 耗时 |
|---|---|---|
| **USB**（设备号 `12344321`） | **33.5 MB/s** | 3m17s |
| WiFi 2.4G（`192.168.31.70:5555`） | 3.2 MB/s | ~35 min |

USB 快约 10 倍。只有在实在拔不了线时才用 WiFi。

---

## 步骤 0：连上设备

```bash
A="C:/platform-tools/adb.exe"     # adb 不在 PATH
MSYS_NO_PATHCONV=1 "$A" devices   # ★ MSYS_NO_PATHCONV=1 必须加，否则路径被 Git Bash 改写
```

WiFi 通道（备用）：

```bash
adb tcpip 5555                    # USB 还插着时执行，让板子开 TCP 监听
adb shell ip addr show wlan0      # 查 IP（DHCP 会变，历史上出现过 .13 / .70）
adb connect <IP>:5555             # ★ 这步不能漏，tcpip 只是让板子监听
adb devices                       # 看到 <IP>:5555  device 才算通
```

## 步骤 1：切 USB 为设备模式（走 USB 时必做）

板子 USB 控制器平时为了接手柄/hub 处于 `host` 模式，电脑认不到，必须切：

```bash
# ❌ 写 device 无效，mode 会读回 none
echo device > /sys/bus/platform/devices/a600000.ssusb/mode

# ✅ 正确值是小写 peripheral
echo peripheral > /sys/bus/platform/devices/a600000.ssusb/mode
```

**成功三判据**（缺一不可）：
1. `cat /sys/bus/platform/devices/a600000.ssusb/mode` → `peripheral`
2. `cat /sys/class/udc/a600000.dwc3/state` → `configured`（切换前是 `not attached`）
3. `adb devices` 出现 `12344321  device`

> ⚠️ **用完记得切回去**：`echo host > .../mode`，否则接手柄/hub 不工作。

### 切不过去时的排查
- `power_supply/usb/voltage_now` 有 5V 但 UDC `not attached` → 线是**充电线**（无数据线芯），换根数据线
- `ls /config/usb_gadget/` 里有 `g1`/`g2` 说明 gadget 正常，问题在物理链路

## 步骤 2：找挂载点

```bash
adb shell "ls /mnt/media_rw/"          # SSD 卷号，如 7FEE-F970（会变，别写死）
adb shell "df -h /mnt/media_rw/<卷号>" # 确认剩余空间
adb shell "ls -la /mnt/media_rw/<卷号>/GAMES/"   # 游戏目录约定名
```

> adb shell 里 `/storage/<卷号>` 用户视图可能不可见，但 app 有存储权限走自己的视图，不影响 PPSSPP/AetherSX2 加载。

## 步骤 3：推送

```bash
adb -s <设备> push "<本地文件>" "/mnt/media_rw/<卷号>/GAMES/<完整文件名>"
```

**★ 目标必须写完整文件路径，不能带尾斜杠。** 写成 `GAMES/` 会报 `remote couldn't create file: Is a directory`，而且 adb **表面显示"1 file pushed + 速度"却是假成功**，实际一个字节没写（09-05 踩过）。

大文件挂后台跑，然后从设备端采样算速度：

```bash
adb shell "ls -la '/mnt/media_rw/<卷号>/GAMES/<文件>'"   # 隔 10~20 秒采两次，差值即速度
```

## 步骤 4：核对（不可省）

```bash
md5sum "<本地文件>"                                                    # 本地
adb shell "md5sum '/mnt/media_rw/<卷号>/GAMES/<文件>'"                  # 设备
```

两端 md5 + 字节数都一致才算成功。**别信 "1 file pushed" 的字面输出。**

---

## 常见错误速查

| 现象 | 原因 | 解法 |
|---|---|---|
| `device not found`（用了 `-s`） | 漏了 `adb connect` | 先 connect 再 devices |
| USB 设备不出现、UDC `not attached` | 写了 `device` 而非 `peripheral`；或线是充电线 | 改 `peripheral`；换数据线 |
| `Is a directory` 且假成功 | push 目标带尾斜杠 | 写完整文件路径 |
| `Failed to install` APK | 文件后缀不是 `.apk`（如 `.apk.1`） | 复制改名成 `.apk` |
| USB 和 WiFi 同时在线 | 两个设备 | `-s` 必须带；只留 WiFi 时可省 |
| 传完游戏跑不动 | 大小对但内容坏 | md5 校验；重新推 |

## 附：APK 安装

```bash
adb -s <设备> install -r "xxx.apk"     # 后缀必须是 .apk
pm list packages | grep -i <包名>       # 验证
monkey -p <包名> -c android.intent.category.LAUNCHER 1   # 启动
```
