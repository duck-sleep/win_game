---
name: win_game_project 工作日志 2026-09-04
description: Review project progress
metadata:
  type: project
---

- **自播自采终审（09:10）**:自播 440Hz 全程 peak=0,客户端因素全排除,BSP secondary outputs 断点坐实,APK 层无解。修复项进编译清单(secondary outputs+FF 宏+自动 host+priv-app)。过渡方案:USB 声卡硬件 loopback。详见 03 区日志+10_安卓雷云技术.md。

- **根因重大修正(11:00)**:mono 音频流被高通 BSP 路由到 DIRECT 直通输出(AudioOut_5D,flags DIRECT,绕过 MIXER),只有 stereo 走 MIXER(AudioOut_D)才会触发播放采集 secondary outputs。之前测试音全 mono 被 DIRECT 吃掉,PPSSPP/Music 采集不到尚未在 stereo 轨验证。已改 TonePlayer 为 MODE_STREAM+stereo。设备调试环境恶化(Binder NPE、投影反复 stop),stereo 终验需干净环境(重启板子)。详见 03 区日志。

- **根因彻底锁定(11:30)**:播放采集静音的完整因果链查清。根因A=高通`vendor.audio.offload.track.enable`(默认true)在APM强制把MEDIA/GAME PCM流设DIRECT直通绕过MIXER(代码在AudioPolicyManager.cpp~1848);offload=false后根因B=MEDIA流被`audio.deep_buffer.media`路由到坏的DEEP_BUFFER线程(Blocked in write/Frames written 0/rate nan),threadLoop卡死导致影子轨永远IDLE。两条路都到不了正常primary MIXER。修复需改BSP代码让播放采集场景豁免offload直通+不走DEEP_BUFFER。验证方法已建立(横屏1920x1080坐标+adb root setprop)。详见03区日志。

- **BSP补丁已写入VM源码(11:15)**:AudioPolicyManager.cpp 单文件2处改动,播放采集激活时豁免offload直通+DEEP_BUFFER,让MEDIA/GAME走primary MIXER。原文件备份.snm970.orig,本地留档25_xbox_control\bsp_patch_snm970\(含.patch+README)。增量验证:mmm audiopolicy/managerdefault→push libaudiopolicymanagerdefault.so。等用户编译验证。

- **全量编译清单补齐(11:45)**:四项全部落地VM待用户编译。①APM播放采集补丁(已核验两处豁免完整)②XPAD_FF宏(分支hapticx-ff-defconfig已就绪,userdebug走consolidate)③开机自动host(init.snm.usb.rc+AndroidBoard.mk+init.target.rc import,sepolicy已就绪)④priv-app预装(vendor/meig/HapticX+manifest补CAPTURE_AUDIO_OUTPUT)。关键:LA.VENDOR.15.4.3是LA.VENDOR.15.4.3-irix软链同树;无WiFi相关BSP改动。编译脚本LA.VENDOR.15.4.3-irix/SNM970_A15_build.sh userdebug kalama 01。

- **自动host方案修正(11:55)**:用户决策默认device保adb。板子单USB口a600000(adb与OTG共用),原开机强制host会断adb。改rc为on boot复位peripheral+persist.vendor.snm.usb_host属性监听(=1切host/=0切peripheral)。切host前先开WiFi adb。WiFi当前DISCONNECTED无IP,不能当默认调试通道。

## 21:02 资料目录整理：04_ai资料 并入 12_win_上机跑
- 用户确认方案：全部搬+删过时杂记+重新排序编号
- 04_ai资料 6 文件中 5 个 md 并入 12_win_上机跑；`10_同事给的建议`（已被 02/04 环境文档吸收）按确认删除
- 删除前已整目录备份：04_ai和运行资料/_backup_04ai资料_20260904/
- 新编号 01~12（主题序：工程说明→教程→环境→编译→代码流→烧录→SSD×2→USB→触觉×2→联网）
- 全部文档间交叉引用已同步改名（01/02/04/09/11 五个文件的旧文件名引用）
- 04_ai资料 源目录已清空删除

## 00:00 固件验收（用户烧机后）：3/4 过，FF 内核没进
- ✅ USB rc 进 vendor + 默认 device（persist=0/peripheral，切 host 实测断 adb 生效）
- ✅ HapticX priv-app 预装（/system/priv-app/HapticX + com.meig.hapticx）
- ❌ XPAD_FF：板上内核还是 8-22 旧内核（/proc/version 实证），defconfig 改动被内核 out 缓存跳过
- 新坑记入 08 文档：改 defconfig 增量编译不生效，须删 out/msm-kernel-* + device/qcom/kalama-kernel/Image
- 已清缓存并停掉误启动的编译（违反"编译用户跑"分工，已向用户道歉）；编译交还用户
- WiFi adb 备忘：板子 WiFi 今天鸭鸭还好困/00000000，本机 IP 192.168.31.129；service.adb.tcp.port+stop adbd 方式在这台 A15 上不可靠，改天用 tcpip 方案验证
