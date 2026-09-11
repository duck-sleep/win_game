---
name: snm970-aarch64-static-bin
description: 在 VM 上用 AOSP 自带 clang（无需 NDK）交叉编译 aarch64 Android 静态 C 工具，以及 snm970_jt 虚拟耳机插孔/FF 测试的用法
agent_created: true
---

# SNM970 aarch64 静态二进制交叉编译（无 NDK 方案）

适用：VM laide@192.168.64.130，源码树在 `~/Desktop/10_code/`。NDK 没装也能编，全用 AOSP 预编译工具链。

## 编译配方（已验证可用，2026-09-05）

```bash
CC=/home/laide/Desktop/10_code/LA.QSSI.15.0-irix/prebuilts/clang/host/linux-x86/clang-r510928/bin/clang
B=/home/laide/Desktop/10_code/LA.VENDOR.15.4.3/bionic
RT=/home/laide/Desktop/10_code/LA.QSSI.15.0-irix/prebuilts/clang/host/linux-x86/clang-r510928/lib/clang/18/lib/linux/libclang_rt.builtins-aarch64-android.a
O=/home/laide/Desktop/10_code/LA.VENDOR.15.4.3/out/soong/.intermediates/bionic/libc
CRTB=$O/crtbegin_static/android_ramdisk_arm64_armv8-a-branchprot_kryo300/crtbegin_static.o
LIBCA=$O/libc/android_ramdisk_arm64_armv8-a-branchprot_kryo300_static/libc.a

# 1. crtend 从 bionic 源码现编（out 里没有现成静态版）
$CC --target=aarch64-linux-android30 -I $B/libc -c $B/libc/arch-common/bionic/crtend.S -o /tmp/crtend.o

# 2. 编译 .o（头文件路径是关键，全手工指定）
$CC --target=aarch64-linux-android30 -O2 \
  -I $B/libc/include -I $B/libc/arch-arm64/include \
  -I $B/libc/kernel/uapi -I $B/libc/kernel/uapi/asm-arm64 \
  -I $B/libc/kernel/android/uapi -I $B/libm/include \
  -c foo.c -o foo.o

# 3. 静态链接（builtins 库必须带，否则 LSE outline atomics 报 undefined）
$CC --target=aarch64-linux-android30 -nostdlib -static -fuse-ld=lld \
  -o foo $CRTB foo.o /tmp/crtend.o $LIBCA $RT
```

## 踩坑记录（按遇到顺序）

1. **不能 `-lm`**：out 里没有静态 libm.a，纯 C 工具不需要数学库就去掉
2. **头文件架构目录**：必须 `asm-arm64`，用 `asm-arm`（32位）会撞 signal 宏冲突（sa_handler 重定义）
3. **crtend**：out 里只有 `crtend_so.o`（so 用），静态 exe 要从 `bionic/libc/arch-common/bionic/crtend.S` 现编，编译需 `-I $B/libc`（找 private/bionic_asm_arm64.h）
4. **undefined `__aarch64_swp1_acq_rel` 等**：libc 静态库用了 LSE outline atomics，链接必须带 clang builtins 库（$RT）
5. **compiler_types.h 找不到**：加 `-I $B/libc/kernel/android/uapi`

## snm970_jt 用法（虚拟耳机插孔 + FF 自测）

```bash
adb push snm970_jt /data/local/tmp/ && adb shell chmod 755 /data/local/tmp/snm970_jt
adb shell /data/local/tmp/snm970_jt jack      # 虚拟耳机插入（SW_HEADPHONE_INSERT=1）
adb shell /data/local/tmp/snm970_jt jackout   # 虚拟拔出
adb shell /data/local/tmp/snm970_jt ff        # uinput FF 链路自测
```

⚠️ **5.15 内核 uinput 坑**：write() 走 legacy 路径（要求 1492B 的 struct uinput_user_dev），
发新 struct uinput_setup(92B) 报 EINVAL。设备 setup 必须用 `UI_DEV_SETUP` ioctl。
（snm970_jack_ff_test.c 已修复，勿回退到 write 方式）

验证成功标志（logcat）：
- `WiredAccessoryManager: headset: h2w connected`
- `AudioFlinger: openOutput ... AUDIO_DEVICE_OUT_WIRED_HEADPHONE`

## 板上无 UI 播放测试音（SnapdragonMusic，需先修权限）

```bash
pm grant com.android.music android.permission.READ_PHONE_STATE   # 不给会崩
# 前提：gamenative 已 disable（见下），否则它抢前台
monkey -p com.android.music -c android.intent.category.LAUNCHER 1
# 界面导航（1080x1920 竖屏）：艺人(700,360) → 专辑(700,540) → 歌曲(700,1404)
cmd media_session dispatch previous   # 歌播完停在末尾时先回曲首
cmd media_session dispatch play
# 验证：logcat grep 'PAL: Device: open' → PAL_DEVICE_OUT_WIRED_HEADPHONE exit status 0
```

## 板上环境修复速查

```bash
# Settings/解锁全废（重启后常见）：provision 标志丢失
settings put global device_provisioned 1
settings put secure user_setup_complete 1

# IRIX 桌面(gamenative)弹窗抢前台、force-stop 会复活
pm disable-user --user 0 app.gamenative   # 禁用（露出 launcher3）
pm enable app.gamenative                   # 恢复

# 息屏太快
svc power stayon true
settings put system screen_off_timeout 600000
```
