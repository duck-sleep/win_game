/*
 * snm970_jack_ff_test.c
 * mode "jack": uinput virtual switch device emitting SW_HEADPHONE_INSERT
 *              (WiredAccessoryManager picks it up -> policy routes to WIRED_HEADPHONE)
 * mode "jackout": emit insert=0 (unplug)
 * mode "ff": create uinput FF device, upload+play rumble (kernel FF chain test)
 */
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <unistd.h>
#include <fcntl.h>
#include <dirent.h>
#include <errno.h>
#include <sys/ioctl.h>
#include <linux/uinput.h>
#include <linux/input.h>

/* struct missing in old bionic/kernel headers (from kernel 4.19+ uinput.h) */
#ifndef UINPUT_MAX_NAME_SIZE
#define UINPUT_MAX_NAME_SIZE 80
#endif
struct uinput_user_setup_ {
    struct input_id id;
    char name[UINPUT_MAX_NAME_SIZE];
    unsigned int ff_effects_max;
};

#ifndef UI_DEV_SETUP
#define UI_DEV_SETUP _IOW('U', 3, struct uinput_user_setup_)
#endif

static int do_dev_setup(int fd, struct uinput_user_setup_ *us)
{
    /* 5.15 uinput: write() uses legacy struct uinput_user_dev (abs arrays),
     * so device setup must go through the UI_DEV_SETUP ioctl instead. */
    if (ioctl(fd, UI_DEV_SETUP, us) < 0) { perror("UI_DEV_SETUP"); return -1; }
    return 0;
}

static int emit_switch(int fd, int value)
{
    struct input_event ev;
    memset(&ev, 0, sizeof(ev));
    ev.type = EV_SW;
    ev.code = SW_HEADPHONE_INSERT;
    ev.value = value;
    if (write(fd, &ev, sizeof(ev)) < 0) { perror("write SW"); return -1; }
    memset(&ev, 0, sizeof(ev));
    ev.type = EV_SYN;
    ev.code = SYN_REPORT;
    ev.value = 0;
    if (write(fd, &ev, sizeof(ev)) < 0) { perror("write SYN"); return -1; }
    return 0;
}

static int do_jack(int value)
{
    int fd;
    struct uinput_user_setup_ us;

    fd = open("/dev/uinput", O_WRONLY | O_NONBLOCK);
    if (fd < 0) { perror("open /dev/uinput"); return 1; }
    ioctl(fd, UI_SET_EVBIT, EV_SW);
    ioctl(fd, UI_SET_SWBIT, SW_HEADPHONE_INSERT);

    memset(&us, 0, sizeof(us));
    us.id.bustype = BUS_VIRTUAL;
    us.id.vendor  = 0x1234;
    us.id.product = 0x9999;
    us.id.version = 1;
    snprintf(us.name, UINPUT_MAX_NAME_SIZE, "SNM970_JACK_SIM");
    if (do_dev_setup(fd, &us) < 0) return 1;
    if (ioctl(fd, UI_DEV_CREATE) < 0) { perror("UI_DEV_CREATE"); return 1; }
    usleep(300000);
    printf("virtual jack device created, sending SW_HEADPHONE_INSERT=%d\n", value);
    if (emit_switch(fd, value) < 0) return 1;
    printf("event sent. keeping device alive 5s...\n");
    sleep(5);
    ioctl(fd, UI_DEV_DESTROY);
    close(fd);
    printf("done (device removed; switch state may persist in framework)\n");
    return 0;
}

static int do_ff(void)
{
    int fd, evfd = -1, ret;
    struct uinput_user_setup_ us;
    struct ff_effect eff;
    struct input_event ev;
    char evpath[128] = "";

    fd = open("/dev/uinput", O_WRONLY | O_NONBLOCK);
    if (fd < 0) { perror("open /dev/uinput"); return 1; }
    ioctl(fd, UI_SET_EVBIT, EV_FF);
    ioctl(fd, UI_SET_FFBIT, FF_RUMBLE);

    memset(&us, 0, sizeof(us));
    us.id.bustype = BUS_VIRTUAL;
    us.id.vendor  = 0x1234;
    us.id.product = 0x5678;
    us.id.version = 1;
    us.ff_effects_max = 4;
    snprintf(us.name, UINPUT_MAX_NAME_SIZE, "SNM970_FF_TEST");
    if (do_dev_setup(fd, &us) < 0) return 1;
    if (ioctl(fd, UI_DEV_CREATE) < 0) { perror("UI_DEV_CREATE"); return 1; }
    printf("[1] uinput FF device created\n");
    usleep(300000);

    /* find evdev node */
    DIR *d = opendir("/sys/class/input");
    struct dirent *e;
    while (d && (e = readdir(d)) != NULL) {
        char path[512], buf[256];
        if (strncmp(e->d_name, "event", 5) != 0) continue;
        snprintf(path, sizeof(path), "/sys/class/input/%s/device/name", e->d_name);
        int f = open(path, O_RDONLY);
        if (f < 0) continue;
        ssize_t n = read(f, buf, sizeof(buf) - 1);
        close(f);
        if (n > 0) { buf[n] = 0; if (strstr(buf, "SNM970_FF_TEST")) { snprintf(evpath, sizeof(evpath), "/dev/input/%s", e->d_name); break; } }
    }
    if (d) closedir(d);
    if (!evpath[0]) { fprintf(stderr, "evdev node not found\n"); return 1; }

    evfd = open(evpath, O_RDWR);
    if (evfd < 0) { perror("open evdev"); return 1; }
    printf("[2] opened %s\n", evpath);

    memset(&eff, 0, sizeof(eff));
    eff.type = FF_RUMBLE;
    eff.id = -1;
    eff.u.rumble.strong_magnitude = 0xC000;
    eff.u.rumble.weak_magnitude   = 0x4000;
    eff.replay.length = 1000;
    ret = ioctl(evfd, EVIOCSFF, &eff);
    if (ret < 0) { perror("EVIOCSFF"); return 1; }
    printf("[3] effect uploaded, id=%d\n", eff.id);

    memset(&ev, 0, sizeof(ev));
    ev.type = EV_FF; ev.code = eff.id; ev.value = 1;
    if (write(evfd, &ev, sizeof(ev)) < 0) { perror("play"); return 1; }
    printf("[4] PLAY sent, 1s...\n");
    sleep(1);
    ev.value = 0;
    write(evfd, &ev, sizeof(ev));
    ioctl(evfd, EVIOCRMFF, eff.id);
    close(evfd);
    ioctl(fd, UI_DEV_DESTROY);
    close(fd);
    printf("PASS: kernel FF chain OK\n");
    return 0;
}

int main(int argc, char **argv)
{
    if (argc < 2) { fprintf(stderr, "usage: %s jack|jackout|ff\n", argv[0]); return 1; }
    if (!strcmp(argv[1], "jack"))    return do_jack(1);
    if (!strcmp(argv[1], "jackout")) return do_jack(0);
    if (!strcmp(argv[1], "ff"))      return do_ff();
    fprintf(stderr, "unknown mode\n");
    return 1;
}
