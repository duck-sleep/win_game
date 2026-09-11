/*
 * ffpulse.c — 心跳假说验证工具(SNM970 FF 排查第二步)
 *
 * 背景:ff-memless 对 length=0 的 rumble 只发一个孤包(ml_schedule_timer
 *      直接删 timer),dongle 若有 rumble 状态超时则忽略孤包。
 *      Windows XInput 驱动语义是持续重发。本工具模拟 Windows 行为。
 *
 * 用法:  ffpulse /dev/input/eventX [strong] [weak] [interval_ms] [duration_s]
 *         strong/weak = 0-65535,默认 40000
 *         interval_ms = 重发间隔,默认 50
 *         duration_s  = 总时长,默认 10
 * 每次写 EV_FF(value=1) 都触发一次 xpad URB(ff-memless 源码证实)。
 */
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <unistd.h>
#include <fcntl.h>
#include <errno.h>
#include <time.h>
#include <sys/ioctl.h>
#include <linux/input.h>

static double now_ms(void)
{
    struct timespec ts;
    clock_gettime(CLOCK_MONOTONIC, &ts);
    return ts.tv_sec * 1000.0 + ts.tv_nsec / 1000000.0;
}

int main(int argc, char **argv)
{
    if (argc < 2) {
        fprintf(stderr,
            "用法: %s /dev/input/eventX [strong] [weak] [interval_ms] [duration_s]\n"
            "  心跳重发实验:固定强度,按 interval_ms 高频重写 EV_FF\n", argv[0]);
        return 1;
    }

    unsigned int strong     = argc > 2 ? atoi(argv[2]) : 40000;
    unsigned int weak       = argc > 3 ? atoi(argv[3]) : 40000;
    unsigned int interval_ms= argc > 4 ? atoi(argv[4]) : 50;
    unsigned int duration_s = argc > 5 ? atoi(argv[5]) : 10;

    int fd = open(argv[1], O_RDWR);
    if (fd < 0) { perror("open"); return 1; }

    unsigned char ff_bits[(FF_MAX + 7) / 8];
    memset(ff_bits, 0, sizeof(ff_bits));
    if (ioctl(fd, EVIOCGBIT(EV_FF, sizeof(ff_bits)), ff_bits) < 0) {
        perror("EVIOCGBIT(EV_FF)"); close(fd); return 1;
    }
    if (!(ff_bits[FF_RUMBLE / 8] & (1 << (FF_RUMBLE % 8)))) {
        fprintf(stderr, "该设备不支持 FF_RUMBLE\n");
        close(fd); return 1;
    }
    printf("心跳重发实验: strong=%u weak=%u interval=%ums duration=%us\n",
           strong, weak, interval_ms, duration_s);

    struct ff_effect eff;
    memset(&eff, 0, sizeof(eff));
    eff.type = FF_RUMBLE;
    eff.id   = -1;
    eff.u.rumble.strong_magnitude = strong;
    eff.u.rumble.weak_magnitude   = weak;
    if (ioctl(fd, EVIOCSFF, &eff) < 0) { perror("EVIOCSFF"); close(fd); return 1; }
    printf("效果已上传 id=%d\n", eff.id);

    struct input_event play_on, play_off;
    memset(&play_on, 0, sizeof(play_on));
    play_on.type  = EV_FF;
    play_on.code  = eff.id;
    play_on.value = 1;
    play_off = play_on;
    play_off.value = 0;

    unsigned long sent = 0, failed = 0;
    double t0 = now_ms();
    double deadline = t0 + duration_s * 1000.0;
    double next_send = t0;

    while (now_ms() < deadline) {
        double wait = next_send - now_ms();
        if (wait > 0) {
            usleep((useconds_t)(wait * 1000));
            continue;
        }
        if (write(fd, &play_on, sizeof(play_on)) < 0) {
            if (errno != EAGAIN) { perror("write EV_FF"); failed++; }
        } else {
            sent++;
        }
        next_send += interval_ms;
        if (next_send < now_ms() - 1000)  /* 进度追不上了就重对齐 */
            next_send = now_ms();
    }

    write(fd, &play_off, sizeof(play_off));
    printf("完成: %lums 内发送 %lu 次 EV_FF(每次触发一个 rumble URB),失败 %lu\n",
           (unsigned long)(now_ms() - t0), sent, failed);

    close(fd);
    return (sent > 0 && failed == 0) ? 0 : 1;
}
