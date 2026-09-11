/*
 * fftest.c — Xbox 手柄 FF 震动验证小工具(SNM970/安卓 阶段0 验收)
 *
 * 用法:  fftest /dev/input/eventX [strong] [weak]
 *         strong/weak = 0-65535,默认 30000
 * 示例:  adb push fftest /data/local/tmp/
 *         adb shell /data/local/tmp/fftest /dev/input/event6
 *         (先 adb shell getevent -l 找 Xbox 手柄对应的 eventX)
 *
 * 编译(VM 上静态交叉编译):
 *   aarch64-linux-gnu-gcc -static -O2 -o fftest fftest.c
 *
 * 逻辑等价于 Windows XInputSetState(leftMotor, rightMotor):
 *   EVIOCSFF 上传 rumble 效果 → 写 EV_FF 事件播放(1s 强/1s 弱循环)
 */
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <unistd.h>
#include <fcntl.h>
#include <errno.h>
#include <sys/ioctl.h>
#include <linux/input.h>

int main(int argc, char **argv)
{
    if (argc < 2) {
        fprintf(stderr,
            "用法: %s /dev/input/eventX [strong 0-65535] [weak 0-65535]\n"
            "  先用 getevent -l 确认手柄 event 节点\n", argv[0]);
        return 1;
    }

    unsigned int strong = argc > 2 ? atoi(argv[2]) : 30000;
    unsigned int weak   = argc > 3 ? atoi(argv[3]) : 30000;

    int fd = open(argv[1], O_RDWR);
    if (fd < 0) { perror("open"); return 1; }

    /* 确认设备支持 FF */
    unsigned char ff_bits[(FF_MAX + 7) / 8];
    memset(ff_bits, 0, sizeof(ff_bits));
    if (ioctl(fd, EVIOCGBIT(EV_FF, sizeof(ff_bits)), ff_bits) < 0) {
        perror("EVIOCGBIT(EV_FF)"); close(fd); return 1;
    }
    if (!(ff_bits[FF_RUMBLE / 8] & (1 << (FF_RUMBLE % 8)))) {
        fprintf(stderr, "该设备不支持 FF_RUMBLE(检查 CONFIG_JOYSTICK_XPAD_FF 是否已编入内核)\n");
        close(fd); return 1;
    }
    printf("设备 %s 支持 FF_RUMBLE,开始测试: 强马达1s -> 弱马达1s 循环,Ctrl+C 退出\n",
           argv[1]);

    /* 上传 rumble 效果 */
    struct ff_effect eff;
    memset(&eff, 0, sizeof(eff));
    eff.type = FF_RUMBLE;
    eff.id   = -1;                      /* 让内核分配 id */
    eff.u.rumble.strong_magnitude = strong;
    eff.u.rumble.weak_magnitude   = weak;
    if (ioctl(fd, EVIOCSFF, &eff) < 0) { perror("EVIOCSFF"); close(fd); return 1; }
    printf("效果已上传 id=%d strong=%u weak=%u\n", eff.id, strong, weak);

    /* 循环播放/停止 */
    struct input_event play_on, play_off;
    memset(&play_on, 0, sizeof(play_on));
    play_on.type  = EV_FF;
    play_on.code  = eff.id;
    play_on.value = 1;
    play_off = play_on;
    play_off.value = 0;

    for (;;) {
        if (write(fd, &play_on, sizeof(play_on)) < 0) { perror("write on"); break; }
        printf("strong %u...\n", strong);
        sleep(1);
        if (write(fd, &play_off, sizeof(play_off)) < 0) { perror("write off"); break; }
        usleep(50000);

        play_on.code = play_off.code = eff.id;
        /* 交换强弱:把 effect 的强弱对调后重新上传 */
        eff.u.rumble.strong_magnitude = weak;
        eff.u.rumble.weak_magnitude   = strong;
        if (ioctl(fd, EVIOCSFF, &eff) < 0) { perror("EVIOCSFF swap"); break; }
        if (write(fd, &play_on, sizeof(play_on)) < 0) break;
        printf("weak %u...\n", weak);
        sleep(1);
        if (write(fd, &play_off, sizeof(play_off)) < 0) break;
        usleep(50000);
        eff.u.rumble.strong_magnitude = strong;
        eff.u.rumble.weak_magnitude   = weak;
        if (ioctl(fd, EVIOCSFF, &eff) < 0) break;
    }

    close(fd);
    return 1;
}
