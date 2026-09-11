# SNM970 项目记忆（工作目录：D:\win_game_project\12_win_上机跑）

> 建立：2026-09-07。当前主战场：**安卓雷云（HapticX）**。

## 项目与角色
- SNM970/OK700 安卓复古游戏掌机 BSP（Qualcomm QCS8550/代号 kalama，Android 15，内核 6.1 GKI）
- 安卓雷云 = 掌机游戏音频 → FFT 低频分析 → 驱动外接手柄马达震动（对标雷云 Synapse）；分工：Windows 调参、安卓执行，同一份 config.json 两端生效（DSP 对拍已过 ~5e-13）
- 完整方案文档：`12_win_上机跑\11_安卓雷云技术.md`（结论以「🎊 2026-09-07 深夜大捷」及「🎯 2026-09-08：FF 方案重构」章节为准；原 13 文档已合并入其「📌 终审档案」）
- 知识库（快速恢复手册）：`D:\win_game_project\03_ai的记忆_和skill\02_知识库_整理版.md`；新会话先读这两份
- 记忆同步约定（用户要求，必须执行）：存新记忆后镜像到 `03_ai的记忆_和skill\01_记忆原档\` 对应位置

## 环境拓扑
- Windows 主机 ←SSH免密→ Ubuntu 22.04 VM `laide@192.168.64.130`，代码 `~/Desktop/10_code/`（LA.VENDOR.15.4.3-irix / LA.QSSI.15.0-irix / modem 三仓库；不带 -irix 的是符号链接）
- git 走 Gitea `http://106.52.24.80:3005`（账号 981637988 密码 LTWLTW200057）；**不要 git pull origin**（指向不可达群晖）
- adb 完整路径 `C:\platform-tools\adb.exe`（不在 PATH）
- 设备 WiFi：SSID「今天鸭鸭还好困」密码 00000000；WiFi adb 流程：插线→`adb tcpip 5555`→确认 WiFi→拔线→`adb connect IP:5555`
- 蓝牙音箱 SRS-XB10（板子无喇叭，音频验证的出口设备）

## 雷云当前状态（09-07 深夜大捷，通道已打通）
- **修复两步（生效中）**：
  ① `setprop persist.bluetooth.a2dp_offload.disabled true`（BT 栈改起软编码 session 1，AAC 软编码）
  ② A2DP 端口从 primary 移到 **bluetooth_qti 模块**：改两份配置 `apc_btq.xml`（主配置，注释 primary 的 A2DP）+ `ha_btq.xml`（hearing aid 配置，bluetooth_qti 加 A2DP 端口）；生成脚本 `make_apc_btq.py` 一键再生（本地 `D:\win_game_project\.workbuddy\tmp_apmcheck\`）
- **根因终审**：同进程三张互不相通的蓝牙 session 表——AOSP `audio.bluetooth.default.so` 查孤儿空表（必失败 -22）；QTI provider 工厂写 `libbluetooth_audio_session_aidl_qti.so`；QTI `audio.bluetooth_qti.default.so` 与工厂同表 → 必须用 bluetooth_qti
- **验证全过**：A2DP 设备注册（SRS-XB10）、PCM 出声无死锁（AudioOut_A5，44100Hz/PCM16，writes=174 干净进 standby）、**auto_test PASS**（blocks=708 nonZero=512 peak=0.3662 maxMotor=0.235，音频成功驱动马达）
- 一键自测：`adb shell am start -n com.meig.hapticx/.MainActivity --ez auto_test true`（18s 出 AUTOTEST SUMMARY/RESULT）；免弹窗授权 `appops set com.meig.hapticx PROJECT_MEDIA allow`
- 蓝牙天线必须插（硬前提）；**恢复出厂/重刷后配置+persist 属性全丢**，用 make_apc_btq.py + setprop 重做
- PAL offload 路（session 2）已废弃，音乐统一 PCM 软编码走 bluetooth_qti——所有声音都在可镜像的 PCM 路上，对捕获有利

## 待办（按优先级）
1. **FF 震动主战场（09-07 全天实录 + 深夜有线直连增补见 11 文档新章）**：三步走了两步半——① 心跳假说**证伪**（ffpulse 50ms/10ms 高频重发均不震）② usbmon 铁证（URB 全成功、包格式与 xpad.c 一致、IN 对 rumble 零响应）③ GIP 会话半逆向（sendgip 工具）：设备一直发 announce 要求 ack，BSP xpad 从不回；正确 ack = 0x01 ACKNOWLEDGE 13 字节（`01 20 <对方seq> 09 {00,cmd,20,len:LE16,pad2,rem:LE16}`，0x02 是 ANNOUNCE 别用）；正确 ack 后 chunk 流停但 rumble 仍不震。**深夜新增：USB-C 有线直联手柄本体也不震**（同 PID 0a3f 双形态：dongle=ep_05/84 无序列号，有线本体=ep_01/81 有序列号、devnum 稳定）——排除无线/dongle 因素，雷蛇全系固件拒收 BSP xpad rumble。**下一步四路（11 文档深夜增补章）**：① 其他 Xbox 手柄对照实验（零成本，判"雷蛇特有 vs BSP FF 路径坏"）② sendgip 有线探测 announce（endpoint 改 0x01）③ Windows USBPcap 抓包（对象改有线手柄，三场景：插入握手 30s/test-vib 震动/静默，pcap 存 captures\）④ diff mainline 6.4+ xpad.c vs BSP。板上工具：/data/local/tmp/{ffpulse,sendgip,gip_exp.sh}（源码 25_xbox_control\hapticx\fftest\，VM 编译脚本 /tmp/build_sendgip.sh）
2. 任务3决策：AF per-track hook 还做不做——官方捕获 API 已复活，建议先用官方 API 跑通产品流程（游戏实测+FF 联调），遇"游戏禁止捕获"或"系统音污染"再上 hook；**待与同事复核**
3. 真实游戏实测：auto_test 只验证了本 app 测试音，需用真实验证游戏捕获（重点：游戏是否 opt-out allowPlaybackCapture=false；系统音污染低频分析）
4. 方案固化进出包：apc_btq.xml/ha_btq.xml + persist 属性 + HapticX priv-app 预装集成进固件出包（重刷不丢）——"上机跑"的落点
5. Windows 侧 HapticX：模式切换时频段增益加载/保存接通（pipeline/app/config_store 三处，config.json 增 mode_band_gains 字段）

## 关键坑（勿重复踩）
- 改 kernel_platform 下**任何**文件（DT/.ko/defconfig/fragment）→ 编译前必须 `rm -f device/qcom/kalama-kernel/Image`（否则增量编译出旧内核，白刷）
- 编译：`cd ~/Desktop/10_code/LA.VENDOR.15.4.3 && ./SNM970_A15_build.sh userdebug kalama 01`，全程 6-8h；**长编译用户自己跑**（tmux build 会话），AI 只改代码+发指令
- toybox 体检：`kernel_platform/prebuilts/build-tools/linux-x86/bin/toybox` 必须 290344 字节，坏了 `git checkout --` 恢复
- 绝不 `git add -A`（30+ 编译副产物）；提交格式 `[SNM970_A15][TaskID]编号 [Description]... [Solution]... [Owner]...`；APM 增量编译走 VM `~/build_apm.sh`
- adb push 到只读 /system 假成功：先 `adb root && adb remount`，push 完 md5sum 核对；验包特征串用 ALOGD 格式串（内联函数名 grep 不到）
- 刷机后必做 provision：`settings put global device_provisioned 1 && settings put secure user_setup_complete 1`
- 板子无喇叭：SPEAKER HAL write 永久阻塞（固件 bug，Total writes=4 冻结）；3.5mm 物理不通（硬件断路）——都别试
- PAL PCM→A2DP 死锁会连锁拖垮 audioserver（TimeCheck 10s SIGABRT），已用 bluetooth_qti 绕开；PCM→A2DP 必挂是 F4 级事实
- 重复 start 捕获前必须 `am force-stop com.meig.hapticx` 清旧投影（否则 createRecord -22）
- 板子无 `media` 命令，调音量用 `cmd audio set-volume 3 <index>`（STREAM_MUSIC 默认 0，测前拉满）
- 中文 WiFi SSID 连 adb 用 `connect-network -x` + UTF-8 hex
- 动 USB 角色前先开 WiFi adb（echo host 会断 adb 通道）；雷云 2.4G 收发器（1532:0a3f）必须手柄开机才握手
- **切 host 实测有效版（09-07）**：`adb root` 后 `echo host > /sys/bus/platform/devices/a600000.ssusb/mode`（强制，绕 CC/UCSI）；typec data_role 写入被静默忽略（充电栈残缺）→ 别用。验证：`ls /sys/bus/usb/devices/` 见 usb1/usb2/1-1.x；收发器=xpad 绑 "Generic X-Box pad"；恢复 `echo device > .../mode`。详见 01_工程说明.md 第7节
- **板子 WiFi**：路由器已从中文名「今天鸭鸭还好困/今天鸭鸭还好困_5G」改成**纯英文「Duck/Duck_5G」**（中文 SSID 导致板子收不到 beacon、wlan0 永卡 NO-CARRIER，改成英文立刻能连，IP 动态 09-07 实测 192.168.31.195）。网络已存 2.4G 和 5G 两条。连接命令 `cmd wifi add-network Duck wpa2 00000000`（已保存，重连用 `cmd wifi connect-network Duck wpa2 00000000`）；SSID UTF-8 hex 旧记忆已过时，勿再用
- 无 root 时读 /sys/class/typec/ 会 Permission denied，先 `adb root`
- logcat 测前 `logcat -G 64M; logcat -c`（camera provider 每 5s 崩溃刷屏）；板上包版本看特征字符串（ro.build.date 停在 8-23 不刷新）
- 手写 PNG chunk 长度/CRC 必须大端 `>I`（曾有坏图导致整会话 11135 报错报废）
- **usbfs 收包必须用 USBDEVFS_REAPURBNDELAY+等待循环**（REAPURB 设备沉默时永久阻塞；卡死进程持有 interface claim，xpad rebind 会失败，须 kill -9 后再 bind）
- dongle 每次重枚举 devnum+1，usbfs 路径用 `cat /sys/bus/usb/devices/1-1.1/devnum` 现查；`authorized 0/1` 写入强制设备重置（GIP 状态机归零，可复现 announce）
- event 节点会漂移（xpad 重绑后变 event5），跑工具前 `getevent -pl` 确认"Generic X-Box pad"

## 用户约定
- 中文沟通；VM 配置修改用户自己动手；长编译用户自己跑；刷机/adb 验证用户在 Windows 端做
- 技术文档要白话+类比，与参考产品差异放显眼位置；UI 用直观百分比不用抽象倍率
- Git commit 编辑用 Vim

## 09-07 深夜增补2（WorkBuddy 接力，FF 排查）
- 主线 commit e2b0ae5 把 Wolverine V3 Pro（0x0a57 有线 / 0x0a59 dongle）标为 XTYPE_XBOX360，但板上 0x0a3f 不在主线表且接口 subclass=0x47（GIP 签名非 0x5D）——0x0a3f 是不同形态；Xbox/PC 模式切换不改 USB 身份
- 有线本体 endpoint 01/81 也跑 GIP 会话：announce `03 20 xx 04 80`，chunk 完结通知 `03 a0 xx 00 04 00` 连环发，13 字节 ack 止不住（dongle 侧能止住，行为有差异）
- Xbox360 协议 12 字节 rumble 直发、四马达变体（扳机7F/仅扳机/mask03）全部不震；用户确认 Xbox 模式也不震——Linux 侧便宜招数全部穷尽，剩唯一变量=Windows 初始化/会话命令，必须 USBPcap 抓包
- USBPcap 1.5.4 已装（GitHub 走 FlClash 7890 代理；winget 不通 0x80072efd；desowin.org 不通）；驱动注册 OK 但热重绑控制器后 USBPcapN 设备不出现，Disable-PnpDevice 报 0x8004100c——**必须重启电脑**激活；重启后流程见 11 文档「09-07 深夜增补2」：跑 pcap_setup.ps1 → 场景1/2/3（pcap_run.ps1 N，脚本在 D:\win_game_project\13_win_cap\captures\ 纯 ASCII 路径；场景2 AI 轮询 go2.flag 后自动跑 test-vib）
- 坑：PowerShell 5.1 把 UTF-8 无 BOM 的 ps1 中文路径读成乱码（涓婃満璺），ps1 一律纯英文路径+纯 ASCII 内容
- sendgip.c 已升级：-o/-i 参数指定 OUT/IN endpoint（默认 05/84 dongle，有线用 -o 01 -i 81），源码 25_xbox_control\hapticx\fftest\，VM 编译脚本 /tmp/build_sendgip.sh
- 板上 WiFi adb=192.168.31.70:5555（09-07 实测）；手柄有线本体 Windows 枚举=XboxComposite USB\VID_1532&PID_0A3F\00004AF69A7327BF- 09-07深夜增补3（USBPcap攻坚实录）：重启后\.\USBPcap1曾存在且-open成功（probe.pcap注入描述符1605B含设备描述符32 15 3f 0a=VID1532/PID0a3f），但实时流量零录制（鼠标动+拔插手柄都不进包）；hcmon(VMware)事件日志刷"Detected unrecognized USB driver (\Driver\USBPcap)"证明过滤器当时已挂栈；停VMUSBArbService+pnputil重绑控制器后USBPcap1彻底消失（CreateFile失败），**判定：USBPcap控制设备只在开机挂栈时创建，热重绑会销毁且无法重建——重试必须再重启且重绑动作绝对禁止**；USBPcapCMD交互菜单经管道调用不输出（_getch控制台读取），要看得在管理员窗口人眼看；winget网络不通、desowin.org不通，GitHub走FlClash 7890代理OK
- 09-07深夜增补4（新假说，未测）：**360协议包只测过Xbox模式，PC模式从未测过**——板上subclass 0x47(GIP)全是Xbox模式读的；主线commit说V3 Pro家族360协议=subclass 0x5D/protocol 1，Xbox/PC拨动开关很可能就是切USB描述符：Xbox模式=GIP接口(0x47，固件GIP门禁挡住所有rumble)，PC模式=可能0x5D(360协议，12字节包直发ep_01即可震)。之前PC模式fftest失败是因为BSP xpad通配XTYPE_XBOXONE发GIP包，非360包本身不行。下一步：手柄切PC模式→插板→读subclass确认→unbind→sendgip -o 01 -i 81发360 12字节包→若震则xpad加0a3f=XTYPE_XBOX360条目即修复（无需抓包）
