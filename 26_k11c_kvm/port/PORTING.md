# 移植 JetKVM 的契约与取舍（P4 开工前必读）

来源：`jetkvm/kvm`（**GPL-2.0**）。本目录里凡是照它抄的协议/代码，出处都标在下面。
自用不分发没有公开义务；**一旦公开或分发，衍生部分必须同样按 GPL-2.0 开源**。

## 1. 它的接口面有多大（实测，不是估的）

`jsonrpc.go` 的方法注册表里共 **118 个方法**。前端 `ui/src` 有 **160 个 .ts/.tsx**。
视频被 **WebRTC 硬绑**：`ui/src/components/WebRTCVideo.tsx` 805 行、
`ui/src/webrtc/signaling/useWebSocketSignaling.ts` 527 行。

⇒ **整个 ui/ 搬过来不划算**：里面大半是云接入、虚拟媒体、扩展、MQTT、TLS、序列控制台，我们都不做；
而要在板子上跑 WebRTC，等于再引一整套 pion/信令栈。

## 2. 我们要实现的子集（方法名与它**逐字相同**）

| 方法 | 参数 | 我们做什么 |
|---|---|---|
| `ping` | — | 返回 pong，前端探活 |
| `getDeviceCapabilities` | — | 返回**我们真有的**能力（见下） |
| `getLocalVersion` | — | 返回固件版本串（板子上用 `uname -v`） |
| `keyboardReport` | `{modifiers, keys1..keys6}` | 写 `/dev/hidg0`，8 字节 `[mod,0,k1..k6]` |
| `keypressReport` | `{keyCode, pressed}` | 单键按下/松开（它前端用的快捷路径） |
| `absMouseReport` | `{x, y, buttons}` | 写 `/dev/hidg1`，6 字节 `[1,buttons,x_lo,x_hi,y_lo,y_hi]`，x/y 0–32767 |
| `relMouseReport` | `{buttons, dx, dy, wheel, wheelX}` | 写 `/dev/hidg2`，5 字节 |
| `wheelReport` | `{y, x}` | 写 `/dev/hidg1`，4 字节 `[2, wheelY, wheelX, 0]` |

**能力表只报真有的**：它的 `getDeviceCapabilities` 返回
`shell, extensions, usb_serial, custom_edid, upload_channel, video_during_update, http_proxy, domain, mdns, ipv6, tls, local_loopback, log_level, tailscale`。
我们一个都还没做 ⇒ 先只报 `usb_serial`（ACM 控制台，**这个是真好用的**），其余不报，
前端的对应菜单会自动隐藏 —— 这正是它 `capabilities` 门控机制的用处，**别为了界面好看去谎报能力**。

## 3. 输入层直接搬这三个文件（它们不依赖视频）

| 文件 | 行数 | 为什么值得搬 |
|---|---|---|
| `ui/src/hooks/useMouse.ts` | 166 | 绝对坐标换算已经替我们想清楚了：从视频元素的渲染盒算 `relativeX`，再 `Math.round(rel*32767)`；还处理了滚轮加速度（`|delta|>=100` 才除以 100） |
| `ui/src/hooks/useKeyboard.ts` | 521 | 键码/修饰键/布局切换/粘贴，**这块自己从零写最容易出错** |
| `ui/src/keyboardLayouts/*` | 多语言 | `en_US` 等一张"字符→HID usage + 是否 shift"的表，直接可用 |

搬的时候保留来源注释（GPL 要求保留版权声明）。

## 4. 视频这一路怎么接（待 P3 之后定，先记候选）

| 方案 | 说明 | 代价 |
|---|---|---|
| A. 自己写一个 60 行的页面：`<img src="/stream.mjpg">` + 上面那三个 hook | 最省事，且**输入层仍然是它的** | 界面简陋 |
| B. 搬它的 ui/，把 `WebRTCVideo.tsx` 换成 MJPEG 组件 | 界面完整 | 要动它的 805 行组件 + 一堆我们不需要的方法得打桩 |
| C. 板子上真做 WebRTC（pion 或 aiortc） | 最接近它的形态 | 明显超出现在的范围 |

**当前建议：A**。等 ①② 两个验收问题过了，再决定要不要升级到 B。

## 5. 设备端实现

`k11cd.py`（本目录）= 上面第 2 节那个子集，**只用 Python 标准库**（板子上现在没网、装不了 pip 包）。
HID 设备路径可注入，所以能在任何机器上离线跑测试（`--hid-keyboard /tmp/fake0`）。

## 6. "别人有的我们就不用自己写" —— 这条只对一半

判据只有一条：**它那个东西依不依赖我们没有的硬件 / 不做的选择。**
不依赖 = 白拿；依赖 = 搬不动，硬搬还要倒贴"假实现"。

| JetKVM 有的 | 能不能白拿 | 为什么 |
|---|---|---|
| HID 报文格式、report descriptor、configfs 装配顺序 | ✅ **白拿**（已拿，见 §2） | 纯字节，跟硬件无关 |
| 重绑容错（`hidWriteTimeout=100ms`、ENXIO 后重开、`soft_connect`） | ✅ 白拿 | 是踩坑经验，不是代码依赖 |
| `useMouse.ts` / `useKeyboard.ts` / `keyboardLayouts/*` | ✅ 白拿 | 只依赖"有 HID"，不依赖视频怎么来的 |
| JSON-RPC 的方法名与参数形状 | ✅ 白拿 | 协议形状，实现是我们自己的 |
| **视频采集**（`rv1106-system`、MIPI + MPP 硬编管线） | ❌ **搬不动** | 绑死 RV1106 那颗芯片；**我们根本没有 HDMI 输入**，这块**没有对应物**，不是"抄不抄"的问题 |
| **网络层** `pkg/nmlite`（自写的 NetworkManager 客户端 + DHCP） | ❌ 搬不动 | 它原版**纯有线 `eth0`**；我们走 WiFi ⇒ 用 Ubuntu 自带 NetworkManager |
| WebRTC 出流（`webrtc.go` + 前端 1332 行） | ⚠️ 能搬但要命 | 要在板子上跑 pion/信令栈；我们用 MJPEG 就够 |
| 虚拟媒体 `mass_storage` + TF 卡 + HTTP/iscsi mount | ❌ 不做 | 我们不需要给被控机装系统 |
| 音频 `uac1`、ATX/DC 扩展、云接入、MQTT、TLS/OIDC、序列控制台扩展 | ❌ 不做 | 都是"它有场景、我们没场景" |

⚠️ **"全搬 ui/" 的反噬**：它 160 个前端文件里每个页面都假设那 118 个方法在、且视频来自 WebRTC。
要"全搬界面"，就得**把 110 个我们不用的方法逐个打桩返回假数据**，否则设置页一进去就报错。
⇒ 那种情况下"用别人的"反而比"自己写 60 行"**更贵**。这就是为什么第 4 节建议方案 A。

