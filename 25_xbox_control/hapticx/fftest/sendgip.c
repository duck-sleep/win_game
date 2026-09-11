/*
 * sendgip.c — usbfs user-space GIP packet tool (SNM970 FF debugging)
 *
 * Prereq: echo 1-1.1:1.0 > /sys/bus/usb/drivers/xpad/unbind
 * Usage:  sendgip [-a] [-o OUTEP] [-i INEP] <usbfd> <hex1> [hex2 ...]
 *         usbfd = /dev/bus/usb/001/<devnum> (Razer dongle)
 *         hex   = full packet bytes, e.g. 09000109000f00007f7fff00ff
 *         -a    = auto mode: send power-mode init, wait for announce
 *                 (0x03 flags=0x20), ack it (02 00 <seq> 01 <devseq>),
 *                 then send user packets. Mirrors what a GIP host does.
 *         -o/-i = override OUT/IN endpoint hex (default 05/84 for dongle;
 *                 wired controller body uses 01/81)
 * Default endpoints are OUT 0x05 / IN 0x84 (Razer dongle).
 *
 * Xbox 360 protocol rumble example (wired, XTYPE_XBOX360 12-byte packet):
 *   sendgip -o 01 -i 81 /dev/bus/usb/001/003 00010f00000000ffff000000
 */
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <unistd.h>
#include <fcntl.h>
#include <errno.h>
#include <sys/ioctl.h>
#include <linux/usbdevice_fs.h>

static int hexval(char c)
{
    if (c >= '0' && c <= '9') return c - '0';
    if (c >= 'a' && c <= 'f') return c - 'a' + 10;
    if (c >= 'A' && c <= 'F') return c - 'A' + 10;
    return -1;
}

static int parse_hex(const char *s, unsigned char *out, int maxlen)
{
    int n = 0, hi = -1;
    for (; *s; s++) {
        int v = hexval(*s);
        if (v < 0) continue;
        if (hi < 0) { hi = v; continue; }
        if (n >= maxlen) return -1;
        out[n++] = (hi << 4) | v;
        hi = -1;
    }
    return (hi >= 0) ? -1 : n;
}

static unsigned char g_out_ep = 0x05;
static unsigned char g_in_ep  = 0x84;

static void dump(const char *tag, unsigned char *buf, int len)
{
    printf("%s [%d] ", tag, len);
    for (int i = 0; i < len; i++) printf("%02x ", buf[i]);
    printf("\n");
    fflush(stdout);
}

static int send_pkt(int fd, unsigned char *pkt, int len, int wait_ms)
{
    struct usbdevfs_urb out_urb;
    memset(&out_urb, 0, sizeof(out_urb));
    out_urb.type = USBDEVFS_URB_TYPE_INTERRUPT;
    out_urb.endpoint = g_out_ep;
    out_urb.buffer = pkt;
    out_urb.buffer_length = len;
    if (ioctl(fd, USBDEVFS_SUBMITURB, &out_urb) < 0) {
        perror("submit OUT"); return -1;
    }
    struct usbdevfs_urb *done = NULL;
    int ok = -1;
    for (int t = 0; t < 300; t++) {          /* wait up to 300ms */
        if (ioctl(fd, USBDEVFS_REAPURBNDELAY, &done) == 0) { ok = 0; break; }
        usleep(1000);
    }
    if (ok < 0) { fprintf(stderr, "reap OUT timeout\n"); return -1; }
    dump("OUT>>", pkt, len);
    if (wait_ms) usleep(wait_ms * 1000);
    return 0;
}

static int resubmit_in(int fd, struct usbdevfs_urb *in_urb, unsigned char *buf, int len)
{
    memset(in_urb, 0, sizeof(*in_urb));
    in_urb->type = USBDEVFS_URB_TYPE_INTERRUPT;
    in_urb->endpoint = g_in_ep;
    in_urb->buffer = buf;
    in_urb->buffer_length = len;
    return ioctl(fd, USBDEVFS_SUBMITURB, in_urb);
}

int main(int argc, char **argv)
{
    int auto_ack = 0, argi = 1;
    while (argc > argi && argv[argi][0] == '-') {
        if (!strcmp(argv[argi], "-a")) { auto_ack = 1; argi++; }
        else if (!strcmp(argv[argi], "-o") && argc > argi + 1) { g_out_ep = strtol(argv[argi+1], NULL, 16); argi += 2; }
        else if (!strcmp(argv[argi], "-i") && argc > argi + 1) { g_in_ep = strtol(argv[argi+1], NULL, 16); argi += 2; }
        else break;
    }

    if (argc < argi + 2) {
        fprintf(stderr,
            "usage: %s [-a] [-o OUTEP] [-i INEP] <usbfd> <hex1> [hex2 ...]\n"
            "  -a: power-mode init + auto-ack announce, then send packets\n"
            "  -o/-i: OUT/IN endpoint hex (default 05/84 dongle, 01/81 wired)\n"
            "  e.g. %s -a /dev/bus/usb/001/010 09000109000f00007f7fff00ff\n"
            "       %s -o 01 -i 81 /dev/bus/usb/001/003 00010f00000000ffff000000\n",
            argv[0], argv[0], argv[0]);
        return 1;
    }

    int fd = open(argv[argi], O_RDWR);
    if (fd < 0) { perror("open"); return 1; }

    int ifnum = 0;
    if (ioctl(fd, USBDEVFS_CLAIMINTERFACE, &ifnum) < 0) {
        perror("CLAIMINTERFACE"); close(fd); return 1;
    }
    printf("claimed if0\n"); fflush(stdout);

    struct usbdevfs_urb in_urb;
    unsigned char in_buf[64];
    if (resubmit_in(fd, &in_urb, in_buf, sizeof(in_buf)) < 0)
        perror("submit IN (continue)");

    unsigned char host_seq = 1;

    if (auto_ack) {
        /* power mode init, same packet xpad sends on bind */
        unsigned char pwr[5] = { 0x05, 0x20, 0x00, 0x01, 0x00 };
        pwr[2] = host_seq++;
        send_pkt(fd, pwr, 5, 300);

        /* ack engine (xone gip_acknowledge_pkt style):
           ack packet = 01 20 <orig seq> 08 {00,cmd,20,len:LE16,pad2,rem:LE16}
           len = chunk_offset + payload_len (bytes acked so far)
           user packets sent at t=2s, 3.5s, 5s... regardless of traffic */
        int sent_user = 0, n_user = argc - (argi + 1);
        int chunk_total = -1;
        for (int t = 0; t < 120; t++) {          /* total 12s */
            if (n_user > 0 && sent_user < n_user && t >= 20 && (t - 20) % 15 == 0) {
                unsigned char pkt[64];
                int len = parse_hex(argv[argi + 1 + sent_user], pkt, sizeof(pkt));
                if (len > 0 && send_pkt(fd, pkt, len, 0) == 0) sent_user++;
            }
            struct usbdevfs_urb *done = NULL;
            if (ioctl(fd, USBDEVFS_REAPURBNDELAY, &done) == 0 && done == &in_urb) {
                int n = in_urb.actual_length;
                dump("IN <<", in_buf, n);
                if (n >= 4) {
                    /* parse GIP header: 3 fixed + length varint [+ chunk varint] */
                    int i = 3, v = 0, sh = 0, plen = 0, coff = 0;
                    while (i < n) {
                        v |= (in_buf[i] & 0x7f) << sh;
                        if (!(in_buf[i] & 0x80)) { i++; break; }
                        sh += 7; i++;
                    }
                    plen = v;
                    if ((in_buf[1] & 0x80) && i < n) {   /* GIP_OPT_CHUNK */
                        v = 0; sh = 0;
                        while (i < n) {
                            v |= (in_buf[i] & 0x7f) << sh;
                            if (!(in_buf[i] & 0x80)) { i++; break; }
                            sh += 7; i++;
                        }
                        coff = v;
                    }
                    if (in_buf[1] & 0x40) chunk_total = coff;  /* CHUNK_START: offset = total */
                    int acked = coff + plen;
                    int remaining = (chunk_total > acked) ? (chunk_total - acked) : 0;

                    unsigned char ack[13];
                    memset(ack, 0, sizeof(ack));
                    ack[0] = 0x01;            /* GIP_CMD_ACKNOWLEDGE */
                    ack[1] = 0x20;            /* INTERNAL */
                    ack[2] = in_buf[2];       /* echo original seq */
                    ack[3] = 9;               /* payload len */
                    ack[4] = 0x00;            /* unknown */
                    ack[5] = in_buf[0];       /* command being acked */
                    ack[6] = 0x20;            /* options */
                    ack[7] = acked & 0xff;    /* length LE16 */
                    ack[8] = (acked >> 8) & 0xff;
                    ack[9] = 0; ack[10] = 0;  /* padding */
                    ack[11] = remaining & 0xff;         /* remaining LE16 */
                    ack[12] = (remaining >> 8) & 0xff;
                    send_pkt(fd, ack, sizeof(ack), 0);
                }
                if (resubmit_in(fd, &in_urb, in_buf, sizeof(in_buf)) < 0) break;
            } else {
                usleep(100000);
            }
            if (sent_user >= n_user && t > 60) break;
        }
        printf("ack engine done: %d/%d user packets sent\n", sent_user, n_user);
        fflush(stdout);
    } else {
        for (int i = argi + 1; i < argc; i++) {
            unsigned char pkt[64];
            int len = parse_hex(argv[i], pkt, sizeof(pkt));
            if (len <= 0) { fprintf(stderr, "hex %d parse failed\n", i - argi); continue; }
            if (send_pkt(fd, pkt, len, 200) < 0) continue;
        }

        /* listen for IN responses: poll 10s */
        for (int t = 0; t < 100; t++) {
            struct usbdevfs_urb *done = NULL;
            if (ioctl(fd, USBDEVFS_REAPURBNDELAY, &done) == 0 && done == &in_urb) {
                dump("IN <<", in_buf, in_urb.actual_length);
                if (in_urb.status != 0)
                    printf("  IN status=%d\n", in_urb.status);
                if (resubmit_in(fd, &in_urb, in_buf, sizeof(in_buf)) < 0) break;
            } else {
                usleep(100000);
            }
        }
    }

    ioctl(fd, USBDEVFS_DISCARDURB, &in_urb);
    {
        struct usbdevfs_urb *d = NULL;
        int t = 0;
        while (ioctl(fd, USBDEVFS_REAPURBNDELAY, &d) == 0 && t++ < 4) d = NULL;
    }
    ioctl(fd, USBDEVFS_RELEASEINTERFACE, &ifnum);
    close(fd);
    printf("done\n");
    return 0;
}
