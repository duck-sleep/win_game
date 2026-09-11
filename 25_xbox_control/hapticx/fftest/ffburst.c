/*
 * ffburst.c — 高频 rumble 重发测试(验证雷蛇 dongle 是否需要 keep-alive 心跳)
 *
 * 背景:fftest 是"on 1s / off 50ms"稀疏模式,每次 EV_FF start 只触发
 *      xpad_play_effect 发一个 13 字节 GIP rumble 包,然后 1 秒静默。
 *      若 dongle 的 rumble 状态有超时(keep-alive),稀疏单发天然不匹配。
 *      本工具改为每 interval_ms 重新 EVIOCSFF 上传同一效果,
 *      每次上传都会调用 xpad_play_effect → 发一个 rumble 包 → 高频心跳。
 *
 * 用法: ffburst /dev/input/eventX [strong] [weak] [interval_ms] [duration_s]
 *        strong/weak 0-65535,默认 40000;interval 默认 20ms;duration 默认 6s
 * 编译(VM 静态交叉编译,同 fftest):
 *   aarch64-linux-gnu-gcc -static -O2 -o ffburst ffburst.c
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
            "用法: %s /dev/input/eventX [strong 0-65535] [weak 0-65535]"
            " [interval_ms] [duration_s]\n", argv[0]);
        return 1;
    }

    unsigned int strong = argc > 2 ? atoi(argv[2]) : 40000;
    unsigned int weak   = argc > 3 ? atoi(argv[3]) : 40000;
    int interval_ms     = argc > 4 ? atoi(argv[4]) : 20;
    int duration_s      = argc > 5 ? atoi(argv[5]) : 6;

    int fd = open(argv[1], O_RDWR);
    if (fd < 0) { perror("open"); return 1; }

    struct ff_effect eff;
    memset(&eff, 0, sizeof(eff));
    eff.type = FF_RUMBLE;
    eff.id   = -1;
    eff.u.rumble.strong_magnitude = strong;
    eff.u.rumble.weak_magnitude   = weak;
    if (ioctl(fd, EVIOCSFF, &eff) < 0) { perror("EVIOCSFF first"); close(fd); return 1; }
    int eid = eff.id;

    printf("effect id=%d, 每 %dms 重发 strong=%u weak=%u, 持续 %ds\n",
           eid, interval_ms, strong, weak, duration_s);
    fflush(stdout);

    int loops = (duration_s * 1000) / interval_ms;
    for (int i = 0; i < loops; i++) {
        eff.id = eid;   /* 更新同一效果 → 内核调 xpad_play_effect → 发包 */
        if (ioctl(fd, EVIOCSFF, &eff) < 0) { perror("EVIOCSFF repeat"); break; }
        usleep(interval_ms * 1000);
    }

    /* 停止:上传零强度 */
    eff.id = eid;
    eff.u.rumble.strong_magnitude = 0;
    eff.u.rumble.weak_magnitude   = 0;
    ioctl(fd, EVIOCSFF, &eff);
    close(fd);
    printf("done\n");
    return 0;
}
