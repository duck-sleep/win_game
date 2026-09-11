# USB 问题排查文档 — MTP（文件传输）用不了的排查与修复

> 症状：刷完自己编的固件，USB 插电脑只充电 / 只有 ADB，**MTP 文件传输不出现**。
> 本文基于本机源码实测（2026-08-23 排查），链路和文件路径都是真实的，不是泛泛攻略。

---

## 〇、结论先行

**最可能的原因：Android 的 USB 默认模式是"仅充电"，MTP 从来就不是自动开的**——原生安卓插电脑后要手动在下拉通知或"设置→连接设备→USB"里选"文件传输"。

而我们是掌机：HOME 是游戏前端 `ok-frontend.apk`，用户很可能**根本没有入口去做这个手动切换**。源码里也验证了：`persist.sys.usb.config`（USB 功能的持久默认值）**在整个 device 树里没有设置过**，所以烧出来就是"无功能"状态。

不是内核没编 MTP，不是 HAL 缺失——是**默认值 + UI 入口**问题，修复见第三节。

---

## 一、原理：MTP 生成的完整链路（分段排障用）

```
用户选"文件传输"（或默认属性生效）
      ↓
框架 UsbDeviceManager（frameworks/base/services/usb/）
  setprop persist.sys.usb.config=mtp[,adb]     ← 持久化
  setprop sys.usb.config=mtp                   ← 触发
      ↓ init 监听属性变化（property trigger）
LA.QSSI.15.0/system/core/rootdir/init.usb.configfs.rc
  on property:sys.usb.config=mtp && property:sys.usb.configfs=1
      → mkdir/symlink /config/usb_gadget/g1/functions/mtp.gs0
      → setprop sys.usb.state mtp              ← 链路完成的标志
      ↓ 内核 USB gadget（configfs）拉起 MTP function
MediaProvider 的 MtpServer 起服务，电脑枚举出 MTP 设备
```

**QCOM 厂商层**叠在上面（都在 `LA.VENDOR.15.4.3/vendor/qcom/opensource/usb/`）：
- `hal/android.hardware.usb@1.2-service-qti` —— USB 状态 HAL
- `hal/android.hardware.usb.gadget@1.1-service-qti` —— gadget 控制 HAL
- `etc/init.qcom.usb.rc` —— 把 `persist.vendor.usb.config` 映射到 `persist.sys.usb.config`；把控制器切到 device 模式（role-switch）
- `hal/usb_compositions.conf` —— QCOM 组合表（含 `mtp,diag` / `mtp,diag,adb` 两种产品组合）

**分层排障口诀**：`persist` 默认值 → `sys` 触发 → configfs 落地 → MtpServer 服务，四层各自有检查命令（下一节）。

---

## 二、5 分钟快速诊断（按顺序做，在哪步断了一目了然）

前置：设备插电脑，确保 `adb devices` 能看到（adb 都不通先走第四节的"线/驱动"分支）。

```bash
# ① 当前 USB 状态——看链路走到了哪
adb shell getprop sys.usb.config      # 框架想切到什么功能
adb shell getprop sys.usb.state       # 实际生效了吗（应等于 config）
adb shell getprop persist.sys.usb.config   # 持久默认值（多半是 none 或空）

# ② 手动强制切 MTP——本机 svc 命令已确认存在
adb shell svc usb setFunctions mtp
# 电脑立刻弹出 MTP 设备 → 链路完全正常，纯粹是"没默认开"
#       → 直接跳第三节方案 B（改默认值）收工

# ③ 切了还是不行，看 configfs 有没有 mtp function
adb shell ls /config/usb_gadget/g1/functions/
#   应看到 mtp.gs0。没有 → 内核 gadget 问题（第四节深挖）

# ④ 看日志定位
adb logcat -s UsbDeviceManager:V UsbService:V MtpService:V
adb shell dmesg | grep -iE "dwc3|gadget|mtp"

# ⑤ 全景快照（dumpsys 里有当前 functions/HAL 状态）
adb shell dumpsys usb
```

诊断结论对照：

| 现象 | 结论 |
|------|------|
| `persist.sys.usb.config` 为空/none | **默认值问题**（最常见）→ 方案 B |
| ②能弹出 MTP | 链路好，改默认 + 前端加入口即可 |
| ③无 mtp.gs0 | 内核 configfs/组合配置问题 → 第四节 |
| 日志有 `avc: denied` | SEPolicy 拦了 → 第四节 |
| adb 都不通 | 线/驱动/角色问题 → 第四节 |

---

## 三、修复方案

### 方案 A：临时验证（不重新编译，重启失效）

```bash
adb shell svc usb setFunctions mtp              # 立即生效
adb shell setprop persist.sys.usb.config mtp,adb # 重启也保持（本次 data 未清）
```

适合先证明"改默认值就能解决"，再落代码。

### 方案 B：改出厂默认（推荐，一行搞定）

**位置**：`LA.VENDOR.15.4.3/device/qcom/kalama/kalama.mk` 末尾追加：

```make
# USB: default to MTP + ADB for factory/eng use
PRODUCT_PROPERTY_OVERRIDES += \
    persist.sys.usb.config=mtp,adb
```

**原理**：编进 vendor 分区 build.prop，开机时 `init.qcom.usb.rc` 把它设为 USB 默认功能；`init.usb.configfs.rc` 里 `on property:sys.usb.config=mtp,adb` 的分支本机已确认存在，直接吃这个值。

**注意**：
- userdebug 编译本来就会自动补 adb（框架 UsbDeviceManager 里有逻辑），写 `mtp,adb` 最稳
- 用户之后在系统里选了别的模式，persist 属性会被覆盖，这是正常优先级
- 想只给开发版开、正式版不开，可用 `ifeq ($(TARGET_BUILD_VARIANT),userdebug)` 包住

### 方案 C：游戏前端加"USB 文件传输"开关（产品级正解）

掌机用户不进系统设置，前端（`LA.QSSI.15.0/vendor/meig/OnionKnight/`）加个开关最顺手：

```java
UsbManager usb = getSystemService(UsbManager.class);
usb.setCurrentFunctions(UsbManager.FUNCTION_MTP);   // 开
usb.setCurrentFunctions(UsbManager.FUNCTION_NONE);  // 关
```

需要 `android.permission.MANAGE_USB`（系统 App 权限，预装到 system 分区的 App 可用）。

**建议 B + C 组合**：B 保证插线即传（出厂体验），C 给用户自由开关。

---

## 四、深挖：链路断了去哪查

### 4.1 adb 都不通（连诊断都做不了）

| 检查 | 命令/方法 |
|------|----------|
| 换**数据线** | 最常见坑：充电线无数据芯。换根确认的 |
| 换电脑/换 Linux PC | 排除 Windows MTP 驱动 |
| USB 角色被切到 host | `adb shell cat /sys/class/usb_role/a600000.ssusb-role-switch/role`，应为 `device`。`init.qti.usb.qmaa.rc` 会写它，掌机若被别的脚本切成 host（插外设逻辑），插电脑就枚举不了 |
| Windows 设备管理器 | 有叹号的 MTP 设备 → 装/更新驱动 |

### 4.2 configfs 没有 mtp.gs0（③失败）

```bash
adb shell ls /config/usb_gadget/g1/       # gadget 是否挂载、配置是否存在
adb shell getprop sys.usb.configfs        # 应为 1
adb shell getprop vendor.usb.use_gadget_hal  # 1=走 QCOM gadget HAL 路径
adb shell ps -A | grep -i "hardware.*usb" # usb HAL 服务在不在跑
```

对应源码位置：
- 框架层组合定义：`LA.QSSI.15.0/system/core/rootdir/init.usb.configfs.rc`
- QCOM HAL 服务：`LA.VENDOR.15.4.3/vendor/qcom/opensource/usb/hal/`
- QCOM 组合表（想让出厂组合带 diag 就改这）：`.../hal/usb_compositions.conf`

### 4.3 SELinux 拒绝

```bash
adb shell dmesg | grep "avc.*denied" | grep -iE "mtp|usb|media"
```

有输出 → 把日志拿去 `device/qcom/sepolicy_vndr/` 对应 `.te` 补规则（方法见 `02_安卓工程教程.md` 第八节）。自己编译的 userdebug 也可先 `adb shell setenforce 0` 验证是不是 SELinux 问题（验证完记得 setenforce 1）。

### 4.4 MTP 出来了但看不到文件 / 显示空

- **FBE 加密**：设备重启后未解锁前 MTP 就是空的（标准行为），解锁屏幕后再刷新
- MediaProvider 扫描问题：`adb shell cmd media scan` 或看 `logcat -s MediaProvider:V`

---

## 五、本工程 USB 相关文件索引

| 文件 | 角色 |
|------|------|
| `LA.QSSI.15.0/system/core/rootdir/init.usb.rc` + `init.usb.configfs.rc` | 框架层：属性→configfs 的全部规则（mtp/mtp,adb 分支确认存在） |
| `LA.QSSI.15.0/frameworks/base/services/usb/`（UsbDeviceManager.java 等） | 框架 USB 管家：默认值、切换逻辑 |
| `LA.VENDOR.15.4.3/vendor/qcom/opensource/usb/etc/init.qcom.usb.rc` | QCOM：role 切换、persist 映射、组合切换 |
| `LA.VENDOR.15.4.3/vendor/qcom/opensource/usb/hal/` | QTI USB/gadget HAL 服务 + `usb_compositions.conf` 组合表 |
| `LA.VENDOR.15.4.3/device/qcom/kalama/init.qti.usb.qmaa.rc` | QMAA 模式把控制器切 device 角色 |
| `LA.VENDOR.15.4.3/device/qcom/kalama/kalama.mk` | **方案 B 改默认值的位置** |
| `LA.QSSI.15.0/frameworks/base/cmds/svc/` | `svc usb setFunctions` 命令实现 |

---

## 附：验证清单（改完方案 B 重刷后）

```bash
adb shell getprop persist.sys.usb.config   # 期望: mtp,adb
adb shell getprop sys.usb.state            # 插线后期望: mtp,adb
# 电脑弹出文件传输窗口 → 通过
```
