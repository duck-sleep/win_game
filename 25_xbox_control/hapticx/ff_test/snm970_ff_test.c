/*
 * snm970_ff_test.c — uinput force-feedback end-to-end self test
 * 1) create a virtual uinput device with FF_RUMBLE capability
 * 2) open its evdev node, upload a rumble effect via EVIOCSFF
 * 3) play it for 1s, verify ioctls succeed
 * exit 0 = kernel FF chain OK
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

static int find_event_node(const char *name)
{
    DIR *d = opendir("/sys/class/input");
    struct dirent *e;
    char path[512], buf[256];
    int found = -1;
    if (!d) return -1;
    while ((e = readdir(d)) != NULL) {
        if (strncmp(e->d_name, "event", 5) != 0) continue;
        snprintf(path, sizeof(path), "/sys/class/input/%s/device/name", e->d_name);
        int f = open(path, O_RDONLY);
        if (f < 0) continue;
        ssize_t n = read(f, buf, sizeof(buf) - 1);
        close(f);
        if (n <= 0) continue;
        buf[n] = 0;
        if (strstr(buf, name)) { found = 1; printf("found: /dev/input/%s (%s)\n", e->d_name, buf); break; }
    }
    closedir(d);
    return found;
}

int main(void)
{
    int uifd, evfd, ret;
    struct uinput_user_setup uiset;
    struct ff_effect eff;
    struct input_event ev;
    char evpath[64];
    const char *devname = "SNM970_FF_TEST";

    /* --- 1. create uinput FF device --- */
    uifd = open("/dev/uinput", O_WRONLY | O_NONBLOCK);
    if (uifd < 0) { perror("open /dev/uinput"); return 1; }

    ioctl(uifd, UI_SET_EVBIT, EV_FF);
    ioctl(uifd, UI_SET_FFBIT, FF_RUMBLE);
    ioctl(uifd, UI_SET_FFBIT, FF_GAIN);

    memset(&uiset, 0, sizeof(uiset));
    snprintf(uiset.name, UINPUT_MAX_NAME_SIZE, "%s", devname);
    uiset.id.bustype = BUS_VIRTUAL;
    uiset.id.vendor  = 0x1234;
    uiset.id.product = 0x5678;
    uiset.id.version = 1;
    uiset.ff_effects_max = 4;
    if (write(uifd, &uiset, sizeof(uiset)) < 0) { perror("write uinput setup"); return 1; }
    if (ioctl(uifd, UI_DEV_CREATE) < 0) { perror("UI_DEV_CREATE"); return 1; }
    printf("[1] uinput FF device created (ff_effects_max=%d)\n", uiset.ff_effects_max);
    usleep(200000);

    /* --- 2. locate evdev node --- */
    if (find_event_node(devname) < 0) { fprintf(stderr, "evdev node not found\n"); return 1; }
    snprintf(evpath, sizeof(evpath), "/dev/input/event");
    /* rescan: get exact name via same helper — simplest: iterate again storing path */
    {
        DIR *d = opendir("/sys/class/input");
        struct dirent *e;
        char path[512], buf[256];
        int hit = 0;
        while (d && (e = readdir(d)) != NULL) {
            if (strncmp(e->d_name, "event", 5) != 0) continue;
            snprintf(path, sizeof(path), "/sys/class/input/%s/device/name", e->d_name);
            int f = open(path, O_RDONLY);
            if (f < 0) continue;
            ssize_t n = read(f, buf, sizeof(buf) - 1);
            close(f);
            if (n > 0) { buf[n] = 0; if (strstr(buf, devname)) { snprintf(evpath, sizeof(evpath), "/dev/input/%s", e->d_name); hit = 1; break; } }
        }
        if (d) closedir(d);
        if (!hit) { fprintf(stderr, "evdev path not resolved\n"); return 1; }
    }
    evfd = open(evpath, O_RDWR);
    if (evfd < 0) { perror("open evdev"); return 1; }

    /* check FF caps reported by kernel */
    unsigned char ffbits[(FF_MAX + 7) / 8];
    memset(ffbits, 0, sizeof(ffbits));
    ret = ioctl(evfd, EVIOCGBIT(EV_FF, sizeof(ffbits)), ffbits);
    if (ret < 0) { perror("EVIOCGBIT(EV_FF)"); return 1; }
    int rumble_supported = ffbits[FF_RUMBLE / 8] & (1 << (FF_RUMBLE % 8));
    printf("[2] evdev opened %s, FF bits queried (%d bytes), FF_RUMBLE=%s\n",
           evpath, ret, rumble_supported ? "SUPPORTED" : "MISSING");
    if (!rumble_supported) { fprintf(stderr, "kernel did not report FF_RUMBLE\n"); return 1; }

    /* --- 3. upload effect --- */
    memset(&eff, 0, sizeof(eff));
    eff.type = FF_RUMBLE;
    eff.id = -1;
    eff.u.rumble.strong_magnitude = 0xC000;
    eff.u.rumble.weak_magnitude   = 0x4000;
    eff.replay.length = 1000;   /* ms */
    ret = ioctl(evfd, EVIOCSFF, &eff);
    if (ret < 0) { perror("EVIOCSFF upload"); return 1; }
    printf("[3] effect uploaded OK (kernel assigned id=%d)\n", eff.id);

    /* --- 4. play 1s --- */
    memset(&ev, 0, sizeof(ev));
    ev.type = EV_FF;
    ev.code = eff.id;
    ev.value = 1;
    if (write(evfd, &ev, sizeof(ev)) < 0) { perror("play effect"); return 1; }
    printf("[4] PLAY sent, sleeping 1s...\n");
    sleep(1);

    ev.value = 0;
    if (write(evfd, &ev, sizeof(ev)) < 0) { perror("stop effect"); return 1; }
    printf("[5] STOP sent\n");

    ioctl(evfd, EVIOCRMFF, eff.id);
    close(evfd);
    ioctl(uifd, UI_DEV_DESTROY);
    close(uifd);
    printf("\nPASS: kernel FF chain (uinput -> input core -> FF core) fully functional\n");
    return 0;
}
