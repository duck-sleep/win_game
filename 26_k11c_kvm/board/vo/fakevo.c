/* T12：fakevo —— 板子 HDMI OUT 直出（只管显示，不编码）。
 *
 * 目标：电视上每秒 60 张**不同**画面、不丢不重、延时 1-2 帧，当后面所有对比的基准。
 * 做法：彩条底图只读一次铺进 5 块 NV12 dumb buffer，每帧只重写码表那 800x80 的 Y，
 *       然后 atomic 非阻塞翻 NV12 平面的 FB，靠 page-flip 事件自限速（一个 vblank 一帧）。
 *
 * 编译：gcc -O2 -Wall -Wextra -o fakevo fakevo.c $(pkg-config --cflags --libs libdrm)
 * 用法：fakevo [--seconds N]      N=0 表示一直跑（默认 0）
 * 素材：从当前目录读 bars_nv12.yuv(3110400) 和 glyphs.gray(41600)，见 mkassets.sh
 */

#define _GNU_SOURCE
#include <drm/drm.h>
#include <drm/drm_fourcc.h>
#include <drm/drm_mode.h>
#include <errno.h>
#include <fcntl.h>
#include <signal.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/mman.h>
#include <sys/poll.h>
#include <sys/stat.h>
#include <time.h>
#include <unistd.h>
#include <xf86drm.h>
#include <xf86drmMode.h>

#include <gst/app/gstappsrc.h>
#include <gst/allocators/gstdmabuf.h>
#include <gst/gst.h>
#include <gst/video/video.h>

#define W 1920
#define H 1080
#define YLINES 1088                 /* NV12 的 Y 平面按 16 对齐；UV 偏移 = pitch*1088 */
#define NBUF 5
#define BARS_BYTES ((long)W * H * 3 / 2)
#define GLYPH_BYTES 41600L
#define GLYPH_W 40
#define GLYPH_H 80
#define TXT_CHARS 20
#define TXT_X0 ((W - TXT_CHARS * GLYPH_W) / 2)   /* 560 */
#define TXT_Y0 (H - GLYPH_H - 40)                /* 960 */
#define GLYPHS "0123456789:.#"

enum { S_FREE = 0, S_PENDING = 1, S_ON = 2 };

struct slot {
    uint32_t handle, fb, pitch;
    uint64_t size;
    uint8_t *map;
    int prime_fd;
    int state;
    volatile int enc_refs;        /* 编码器还在读这块的份数；挑 FREE 时要为 0 */
    GstMemory *mem;               /* 包着 prime_fd 的 DMA-buf，只包一次，退出才释放 */
};

static volatile sig_atomic_t g_quit;
static int g_fd;
static uint32_t g_plane_nv12, g_prop_fb;
static struct slot *g_on;                 /* 当前在屏的那块 */
static unsigned int g_last_seq;
static int g_have_seq;
static long g_miss, g_noslot, g_flips_sec;
static double g_last_stamp, g_dt_sum, g_dt_max;

/* ---- T13：硬编那一路。电视那一路永远不等它。 ---- */
static gboolean g_enc;
static GstElement *g_pipe;
static GstElement *g_appsrc;
static GstAllocator *g_dmalloc;
static GstBus *g_bus;
static volatile long g_enc_frames;      /* mpph265enc 出了多少帧 */
static volatile long g_enc_skip;        /* 因为编码器手上活太多而没送进去 */
static long g_enc_last;

static void on_signal(int sig)
{
    (void)sig;
    g_quit = 1;
}

static void die(const char *step)
{
    fprintf(stderr, "FAIL %s: %s\n", step, strerror(errno));
    exit(1);
}

static void die_ret(const char *step, int v)
{
    fprintf(stderr, "FAIL %s: ret=%d (%s)\n", step, v, strerror(v < 0 ? -v : v));
    exit(1);
}

static double now_s(void)
{
    struct timespec ts;
    clock_gettime(CLOCK_MONOTONIC_RAW, &ts);
    return (double)ts.tv_sec + ts.tv_nsec / 1e9;
}

static uint8_t *read_file(const char *path, long want)
{
    struct stat st;
    if (stat(path, &st) != 0)
        die(path);
    if (st.st_size != want) {
        fprintf(stderr, "FAIL %s size=%lld want=%ld\n", path, (long long)st.st_size, want);
        exit(1);
    }
    int fd = open(path, O_RDONLY | O_CLOEXEC);
    if (fd < 0)
        die(path);
    uint8_t *buf = malloc((size_t)want);
    if (buf == NULL)
        die("malloc asset");
    long got = 0;
    while (got < want) {
        ssize_t n = read(fd, buf + got, (size_t)(want - got));
        if (n <= 0)
            die(path);
        got += n;
    }
    close(fd);
    return buf;
}

/* 按名字取属性 ID；取不到返回 0 */
static uint32_t prop_id(uint32_t obj, uint32_t type, const char *name)
{
    drmModeObjectPropertiesPtr p = drmModeObjectGetProperties(g_fd, obj, type);
    uint32_t out = 0;

    if (p == NULL)
        return 0;
    for (uint32_t i = 0; i < p->count_props && out == 0; i++) {
        drmModePropertyPtr pp = drmModeGetProperty(g_fd, p->props[i]);
        if (pp == NULL)
            continue;
        if (strcmp(pp->name, name) == 0)
            out = pp->prop_id;
        drmModeFreeProperty(pp);
    }
    drmModeFreeObjectProperties(p);
    return out;
}

static uint64_t prop_value(uint32_t obj, uint32_t type, const char *name)
{
    drmModeObjectPropertiesPtr p = drmModeObjectGetProperties(g_fd, obj, type);
    uint64_t out = 0;

    if (p == NULL)
        return 0;
    for (uint32_t i = 0; i < p->count_props; i++) {
        drmModePropertyPtr pp = drmModeGetProperty(g_fd, p->props[i]);
        if (pp == NULL)
            continue;
        int hit = (strcmp(pp->name, name) == 0);
        if (hit)
            out = p->prop_values[i];
        drmModeFreeProperty(pp);
        if (hit)
            break;
    }
    drmModeFreeObjectProperties(p);
    return out;
}

static void *map_dumb(uint32_t handle, uint64_t size)
{
    struct drm_mode_map_dumb m;
    memset(&m, 0, sizeof(m));
    m.handle = handle;
    if (drmIoctl(g_fd, DRM_IOCTL_MODE_MAP_DUMB, &m) != 0)
        die("DRM_IOCTL_MODE_MAP_DUMB");
    void *p = mmap(NULL, (size_t)size, PROT_READ | PROT_WRITE, MAP_SHARED, g_fd, m.offset);
    if (p == MAP_FAILED)
        die("mmap dumb");
    return p;
}

static void *create_dumb(uint32_t width, uint32_t height, uint32_t bpp,
                         uint32_t *handle, uint32_t *pitch, uint64_t *size)
{
    struct drm_mode_create_dumb c;
    memset(&c, 0, sizeof(c));
    c.width = width;
    c.height = height;
    c.bpp = bpp;
    if (drmIoctl(g_fd, DRM_IOCTL_MODE_CREATE_DUMB, &c) != 0)
        die("DRM_IOCTL_MODE_CREATE_DUMB");
    *handle = c.handle;
    *pitch = c.pitch;
    *size = c.size;
    return map_dumb(c.handle, c.size);
}

/* 翻页完成：上一块回 FREE，这一块上屏，顺手统计帧率/丢帧/帧间隔。
   libdrm 的 page_flip_handler2 签名是 (fd, sequence, tv_sec, tv_usec, plane_id, user) */
static void flip_cb(int fd, unsigned int seq, unsigned int tv_sec, unsigned int tv_usec,
                    unsigned int plane_id, void *data)
{
    struct slot *s = data;
    (void)fd;
    (void)tv_sec;
    (void)tv_usec;
    (void)plane_id;

    if (g_on != NULL && g_on != s)
        g_on->state = S_FREE;
    s->state = S_ON;
    g_on = s;

    double t = now_s();
    g_flips_sec++;
    if (g_last_stamp > 0) {
        double dt = (t - g_last_stamp) * 1000.0;
        g_dt_sum += dt;
        if (dt > g_dt_max)
            g_dt_max = dt;
    }
    g_last_stamp = t;

    if (g_have_seq && seq > g_last_seq + 1)
        g_miss += (long)(seq - g_last_seq - 1);
    g_last_seq = seq;
    g_have_seq = 1;
}

/* 把 HH:MM:SS.mmm #NNNNNN 用字形表贴进这块缓冲的 Y 平面 */
static void draw_table(const struct slot *s, uint32_t pitch, const uint8_t *glyphs, long frame)
{
    char txt[TXT_CHARS + 8];
    struct timespec ts;

    clock_gettime(CLOCK_MONOTONIC_RAW, &ts);
    long ms = (long)ts.tv_sec * 1000 + ts.tv_nsec / 1000000;
    snprintf(txt, sizeof(txt), "%02ld:%02ld:%02ld.%03ld #%06ld",
             ((ms / 3600000) % 100), (ms / 60000) % 60, (ms / 1000) % 60, ms % 1000,
             (frame >= 0 ? frame : 0) % 1000000);

    for (int i = 0; i < TXT_CHARS; i++) {
        int gx = TXT_X0 + i * GLYPH_W;
        const char *at = strchr(GLYPHS, txt[i]);

        if (txt[i] == ' ' || at == NULL) {
            for (int r = 0; r < GLYPH_H; r++)
                memset(s->map + (size_t)(TXT_Y0 + r) * pitch + gx, 16, GLYPH_W);
            continue;
        }
        const uint8_t *src = glyphs + (long)(at - GLYPHS) * GLYPH_W * GLYPH_H;
        for (int r = 0; r < GLYPH_H; r++) {
            uint8_t *dst = s->map + (size_t)(TXT_Y0 + r) * pitch + gx;
            const uint8_t *gp = src + (long)r * GLYPH_W;
            for (int k = 0; k < GLYPH_W; k++)
                dst[k] = (uint8_t)(16 + gp[k] * 219 / 255);   /* 灰度 → limited-range Y */
        }
    }
}

/* 编码器 buffer 用完（被下游 unref 到 0）时回调，只许做原子减，不许碰 DRM。
   GstMiniObjectNotify 的参数顺序是 (user_data, object)，别写反。 */
static void on_enc_done(gpointer u, GstMiniObject *mini)
{
    struct slot *s = u;
    (void)mini;
    __atomic_sub_fetch(&s->enc_refs, 1, __ATOMIC_SEQ_CST);
}

/* 挂在 mpph265enc 的 src pad 上数编出来的帧 */
static GstPadProbeReturn enc_count_cb(GstPad *pad, GstPadProbeInfo *info, gpointer u)
{
    (void)pad;
    (void)info;
    (void)u;
    __atomic_add_fetch(&g_enc_frames, 1, __ATOMIC_SEQ_CST);
    return GST_PAD_PROBE_OK;
}

static gboolean enc_setup(void)
{
    /* 两个 sink：5004 给本地网关（局域网页面），5005 给云客户端（k11c-cloud）。
       两条路互不影响，也不再抢端口。 */
    static const char *desc =
        "appsrc name=src is-live=true format=time do-timestamp=true "
        "max-buffers=2 leaky-type=downstream "
        "caps=video/x-raw,format=NV12,width=1920,height=1080,framerate=60/1 "
        "! mpph265enc name=enc bps=6000000 gop=60 "
        "! h265parse config-interval=-1 "
        "! rtph265pay config-interval=-1 pt=96 mtu=1200 "
        "! tee name=t "
        "t. ! queue ! udpsink host=127.0.0.1 port=5004 sync=false async=false "
        "t. ! queue ! udpsink host=127.0.0.1 port=5005 sync=false async=false";
    GError *err = NULL;

    g_pipe = gst_parse_launch(desc, &err);
    if (g_pipe == NULL || err != NULL) {
        fprintf(stderr, "FAIL gst_parse_launch: %s\n", err != NULL ? err->message : "返回空");
        if (err != NULL)
            g_clear_error(&err);
        return FALSE;
    }
    g_appsrc = gst_bin_get_by_name(GST_BIN(g_pipe), "src");
    if (g_appsrc == NULL) {
        fprintf(stderr, "FAIL appsrc not found\n");
        return FALSE;
    }
    g_bus = gst_element_get_bus(g_pipe);

    GstPad *sp = NULL;
    GstElement *venc = gst_bin_get_by_name(GST_BIN(g_pipe), "enc");
    if (venc != NULL) {
        sp = gst_element_get_static_pad(venc, "src");
        g_object_unref(venc);
    }
    if (sp != NULL) {
        gst_pad_add_probe(sp, GST_PAD_PROBE_TYPE_BUFFER, enc_count_cb, NULL, NULL);
        gst_object_unref(sp);
    } else {
        fprintf(stderr, "WARN 没挂上编码帧计数器（找不到 enc 的 src pad）\n");
    }

    if (gst_element_set_state(g_pipe, GST_STATE_PLAYING) == GST_STATE_CHANGE_FAILURE) {
        fprintf(stderr, "FAIL 编码管道进不了 PLAYING\n");
        return FALSE;
    }
    return TRUE;
}

/* 把一帧（零拷贝，只递 DMA-buf fd）推给编码器 */
static void enc_push(struct slot *s)
{
    GstBuffer *b = gst_buffer_new();
    /* add_video_meta_full 的 offset/stride 固定按 GST_VIDEO_MAX_PLANES=4 个元素读 */
    gsize off[4] = { 0, (gsize)s->pitch * YLINES, 0, 0 };
    gint st[4] = { (gint)s->pitch, (gint)s->pitch, 0, 0 };

    gst_buffer_append_memory(b, gst_memory_ref(s->mem));
    gst_buffer_add_video_meta_full(b, GST_VIDEO_FRAME_FLAG_NONE, GST_VIDEO_FORMAT_NV12,
                                   W, H, 2, off, st);
    __atomic_add_fetch(&s->enc_refs, 1, __ATOMIC_SEQ_CST);
    gst_mini_object_weak_ref(GST_MINI_OBJECT(b), on_enc_done, s);
    if (gst_app_src_push_buffer(GST_APP_SRC(g_appsrc), b) != GST_FLOW_OK)
        __atomic_sub_fetch(&s->enc_refs, 1, __ATOMIC_SEQ_CST);
}

/* 没有 HDMI 也要出画面：不开扫描输出，同一套 NV12 画进 dumb buffer，按 60fps 直接送编码。
   远程 KVM 的场景就是"被控机在机房、没接显示器"，这条路必须有。 */
static int run_headless(const char *barsfile, const char *glyphfile, int seconds)
{
    double start = now_s();
    uint8_t *bars = read_file(barsfile, BARS_BYTES);
    uint8_t *glyphs = read_file(glyphfile, GLYPH_BYTES);

    static struct slot slots[NBUF];
    memset(slots, 0, sizeof(slots));
    for (int i = 0; i < NBUF; i++) {
        struct slot *s = &slots[i];
        s->map = create_dumb(W, YLINES * 3 / 2, 8, &s->handle, &s->pitch, &s->size);
        s->fb = 0;                                  /* 不扫描，就不建 framebuffer */
        if (drmPrimeHandleToFD(g_fd, s->handle, DRM_CLOEXEC | DRM_RDWR, &s->prime_fd) != 0)
            die("drmPrimeHandleToFD");
        for (int r = 0; r < H; r++)
            memcpy(s->map + (size_t)r * s->pitch, bars + (size_t)r * W, W);
        for (int r = 0; r < H / 2; r++)
            memcpy(s->map + (size_t)s->pitch * YLINES + (size_t)r * s->pitch,
                   bars + (size_t)W * H + (size_t)r * W, W);
        for (int r = 0; r < GLYPH_H; r++)
            memset(s->map + (size_t)(TXT_Y0 + r) * s->pitch + TXT_X0, 16, TXT_CHARS * GLYPH_W);
        for (int r = 0; r < GLYPH_H / 2; r++)
            memset(s->map + (size_t)s->pitch * YLINES +
                   (size_t)(TXT_Y0 / 2 + r) * s->pitch + TXT_X0, 128, TXT_CHARS * GLYPH_W);
        s->state = S_FREE;
    }

    if (g_enc) {
        gst_init(NULL, NULL);
        g_dmalloc = gst_dmabuf_allocator_new();
        for (int i = 0; i < NBUF; i++)
            slots[i].mem = gst_dmabuf_allocator_alloc_with_flags(
                g_dmalloc, slots[i].prime_fd, (gsize)slots[i].size,
                GST_FD_MEMORY_FLAG_DONT_CLOSE);
        if (!enc_setup())
            return 1;
        printf("enc(headless): mpph265enc bps=6000000 gop=60 -> rtp 127.0.0.1:5004+5005 pt=96\n");
        fflush(stdout);
    }

    long frame = 1;
    double next_report = now_s() + 1.0;
    struct timespec tick;
    clock_gettime(CLOCK_MONOTONIC, &tick);

    while (!g_quit) {
        if (seconds > 0 && (now_s() - start) >= seconds)
            break;

        struct slot *cur = NULL;
        for (int i = 0; i < NBUF; i++) {
            if (slots[i].state != S_FREE)
                continue;
            if (__atomic_load_n(&slots[i].enc_refs, __ATOMIC_SEQ_CST) > 0)
                continue;
            cur = &slots[i];
            break;
        }
        if (cur == NULL) {
            g_noslot++;
        } else {
            draw_table(cur, cur->pitch, glyphs, frame);
            frame++;
            g_flips_sec++;
            if (g_enc) {
                long inuse = 0;
                for (int i = 0; i < NBUF; i++)
                    if (__atomic_load_n(&slots[i].enc_refs, __ATOMIC_SEQ_CST) > 0)
                        inuse++;
                if (inuse < 2)
                    enc_push(cur);
                else
                    __atomic_add_fetch(&g_enc_skip, 1, __ATOMIC_SEQ_CST);
            }
        }

        /* 60fps 节拍（没有 page flip 事件可用，就用绝对时间睡到下一个格点） */
        tick.tv_nsec += 16666667L;
        if (tick.tv_nsec >= 1000000000L) {
            tick.tv_sec++;
            tick.tv_nsec -= 1000000000L;
        }
        clock_nanosleep(CLOCK_MONOTONIC, TIMER_ABSTIME, &tick, NULL);

        double t = now_s();
        if (t >= next_report) {
            long enc_now = __atomic_load_n(&g_enc_frames, __ATOMIC_SEQ_CST);
            fprintf(stderr, "headless flips=%ld dt=%.2f noslot=%ld enc=%ld enc_skip=%ld\n",
                    g_flips_sec, g_flips_sec ? 1000.0 / g_flips_sec : 0.0, g_noslot,
                    enc_now - g_enc_last, __atomic_load_n(&g_enc_skip, __ATOMIC_SEQ_CST));
            fflush(stderr);
            g_enc_last = enc_now;
            g_flips_sec = 0;
            next_report += 1.0;
            if (g_enc) {
                GstMessage *m = gst_bus_pop_filtered(g_bus, GST_MESSAGE_ERROR | GST_MESSAGE_WARNING);
                if (m != NULL) {
                    GError *ge = NULL;
                    gst_message_parse_error(m, &ge, NULL);
                    fprintf(stderr, "BUS %s: %s\n", GST_MESSAGE_TYPE_NAME(m),
                            ge != NULL ? ge->message : "-");
                    if (ge != NULL)
                        g_error_free(ge);
                    gst_message_unref(m);
                }
            }
        }
    }

    fprintf(stderr, "TOTAL headless flips=%ld noslot=%ld enc=%ld\n",
            frame - 1, g_noslot, __atomic_load_n(&g_enc_frames, __ATOMIC_SEQ_CST));
    fflush(stderr);
    if (g_enc) {
        gst_element_set_state(g_pipe, GST_STATE_NULL);
        for (int i = 0; i < NBUF; i++)
            if (slots[i].mem != NULL)
                gst_memory_unref(slots[i].mem);
        gst_object_unref(g_bus);
        gst_object_unref(g_appsrc);
        gst_object_unref(g_dmalloc);
        gst_object_unref(g_pipe);
        gst_deinit();
    }
    return 0;
}

int main(int argc, char **argv)
{
    int seconds = 0;
    int force_headless = 0;
    for (int i = 1; i < argc; i++) {
        if (strcmp(argv[i], "--seconds") == 0 && i + 1 < argc) {
            seconds = atoi(argv[++i]);
        } else if (strcmp(argv[i], "--enc") == 0) {
            g_enc = TRUE;
        } else if (strcmp(argv[i], "--headless") == 0) {
            force_headless = 1;
        } else {
            fprintf(stderr, "usage: %s [--enc] [--headless] [--seconds N]\n", argv[0]);
            return 2;
        }
    }
    signal(SIGINT, on_signal);
    signal(SIGTERM, on_signal);

    g_fd = open("/dev/dri/card0", O_RDWR | O_CLOEXEC);
    if (g_fd < 0)
        die("open /dev/dri/card0");
    if (drmSetClientCap(g_fd, DRM_CLIENT_CAP_UNIVERSAL_PLANES, 1) != 0)
        die("cap UNIVERSAL_PLANES");
    if (drmSetClientCap(g_fd, DRM_CLIENT_CAP_ATOMIC, 1) != 0)
        die("cap ATOMIC");

    /* ---------- 按名字找连接器 / CRTC / 模式 ---------- */
    drmModeResPtr res = drmModeGetResources(g_fd);
    if (res == NULL)
        die("drmModeGetResources");

    drmModeConnectorPtr conn = NULL;
    for (int i = 0; i < res->count_connectors && conn == NULL; i++) {
        drmModeConnectorPtr c = drmModeGetConnector(g_fd, res->connectors[i]);
        if (c == NULL)
            continue;
        if (c->connector_type == DRM_MODE_CONNECTOR_HDMIA && c->connection == DRM_MODE_CONNECTED)
            conn = c;
        else
            drmModeFreeConnector(c);
    }
    if (conn == NULL || force_headless) {
        if (conn == NULL)
            fprintf(stderr, "WARN no connected HDMI-A-* connector -> headless encode mode\n");
        return run_headless("bars_nv12.yuv", "glyphs.gray", seconds);
    }

    uint32_t crtc_id = 0;
    const char *crtc_how = "encoder";
    if (conn->encoder_id != 0) {
        drmModeEncoderPtr enc = drmModeGetEncoder(g_fd, conn->encoder_id);
        if (enc != NULL) {
            crtc_id = enc->crtc_id;
            drmModeFreeEncoder(enc);
        }
    }
    int crtc_idx = -1;
    if (crtc_id == 0 && res->count_crtcs > 0) {
        crtc_id = res->crtcs[0];
        crtc_how = "first-crtc";
    }
    for (int i = 0; i < res->count_crtcs; i++)
        if (res->crtcs[i] == crtc_id)
            crtc_idx = i;
    if (crtc_id == 0 || crtc_idx < 0)
        die_ret("no CRTC for this connector", -ENODEV);

    drmModeModeInfoPtr mode = NULL;
    for (int i = 0; i < conn->count_modes; i++) {
        if (conn->modes[i].hdisplay == W && conn->modes[i].vdisplay == H &&
            conn->modes[i].vrefresh == 60) {
            mode = &conn->modes[i];
            break;
        }
    }
    if (mode == NULL)
        die_ret("no 1920x1080@60 mode in connector mode list", -ENODEV);

    /* ---------- 找主平面和能收 NV12 的 overlay 平面 ---------- */
    drmModePlaneResPtr pres = drmModeGetPlaneResources(g_fd);
    if (pres == NULL)
        die("drmModeGetPlaneResources");

    uint32_t primary_id = 0, nv12_id = 0;
    for (uint32_t i = 0; i < pres->count_planes; i++) {
        uint32_t pid = pres->planes[i];
        drmModePlanePtr pl = drmModeGetPlane(g_fd, pid);
        if (pl == NULL)
            continue;
        if ((pl->possible_crtcs & (1u << crtc_idx)) == 0) {
            drmModeFreePlane(pl);
            continue;
        }
        uint64_t ptype = prop_value(pid, DRM_MODE_OBJECT_PLANE, "type");
        if (ptype == DRM_PLANE_TYPE_PRIMARY && primary_id == 0) {
            primary_id = pid;
        } else if (ptype == DRM_PLANE_TYPE_OVERLAY && nv12_id == 0) {
            for (uint32_t f = 0; f < pl->count_formats; f++) {
                if (pl->formats[f] == DRM_FORMAT_NV12) {
                    nv12_id = pid;
                    break;
                }
            }
        }
        drmModeFreePlane(pl);
    }
    drmModeFreePlaneResources(pres);
    if (primary_id == 0)
        die_ret("no primary plane on this crtc", -ENODEV);
    if (nv12_id == 0)
        die_ret("no overlay plane accepting NV12", -ENODEV);

    printf("conn=%u crtc=%u primary=%u nv12plane=%u mode=%dx%d@%d pitch_hint (%s)\n",
           conn->connector_id, crtc_id, primary_id, nv12_id,
           mode->hdisplay, mode->vdisplay, mode->vrefresh, crtc_how);
    fflush(stdout);

    /* ---------- 属性 ID ---------- */
    uint32_t pc_conn = prop_id(conn->connector_id, DRM_MODE_OBJECT_CONNECTOR, "CRTC_ID");
    uint32_t pc_mode = prop_id(crtc_id, DRM_MODE_OBJECT_CRTC, "MODE_ID");
    uint32_t pc_act = prop_id(crtc_id, DRM_MODE_OBJECT_CRTC, "ACTIVE");
    uint32_t pp_fb = prop_id(primary_id, DRM_MODE_OBJECT_PLANE, "FB_ID");
    uint32_t pp_crtc = prop_id(primary_id, DRM_MODE_OBJECT_PLANE, "CRTC_ID");
    uint32_t pp_sx = prop_id(primary_id, DRM_MODE_OBJECT_PLANE, "SRC_X");
    uint32_t pp_sy = prop_id(primary_id, DRM_MODE_OBJECT_PLANE, "SRC_Y");
    uint32_t pp_sw = prop_id(primary_id, DRM_MODE_OBJECT_PLANE, "SRC_W");
    uint32_t pp_sh = prop_id(primary_id, DRM_MODE_OBJECT_PLANE, "SRC_H");
    uint32_t pp_cx = prop_id(primary_id, DRM_MODE_OBJECT_PLANE, "CRTC_X");
    uint32_t pp_cy = prop_id(primary_id, DRM_MODE_OBJECT_PLANE, "CRTC_Y");
    uint32_t pp_cw = prop_id(primary_id, DRM_MODE_OBJECT_PLANE, "CRTC_W");
    uint32_t pp_ch = prop_id(primary_id, DRM_MODE_OBJECT_PLANE, "CRTC_H");
    uint32_t np_crtc = prop_id(nv12_id, DRM_MODE_OBJECT_PLANE, "CRTC_ID");
    uint32_t np_sx = prop_id(nv12_id, DRM_MODE_OBJECT_PLANE, "SRC_X");
    uint32_t np_sy = prop_id(nv12_id, DRM_MODE_OBJECT_PLANE, "SRC_Y");
    uint32_t np_sw = prop_id(nv12_id, DRM_MODE_OBJECT_PLANE, "SRC_W");
    uint32_t np_sh = prop_id(nv12_id, DRM_MODE_OBJECT_PLANE, "SRC_H");
    uint32_t np_cx = prop_id(nv12_id, DRM_MODE_OBJECT_PLANE, "CRTC_X");
    uint32_t np_cy = prop_id(nv12_id, DRM_MODE_OBJECT_PLANE, "CRTC_Y");
    uint32_t np_cw = prop_id(nv12_id, DRM_MODE_OBJECT_PLANE, "CRTC_W");
    uint32_t np_ch = prop_id(nv12_id, DRM_MODE_OBJECT_PLANE, "CRTC_H");
    g_prop_fb = prop_id(nv12_id, DRM_MODE_OBJECT_PLANE, "FB_ID");
    g_plane_nv12 = nv12_id;
    if (!(pc_conn && pc_mode && pc_act && pp_fb && pp_crtc && pp_sx && pp_sy && pp_sw && pp_sh &&
          pp_cx && pp_cy && pp_cw && pp_ch && g_prop_fb && np_crtc && np_sx && np_sy && np_sw &&
          np_sh && np_cx && np_cy && np_cw && np_ch))
        die_ret("missing atomic property", -ENOENT);

    /* ---------- 黑底（主平面只收 RGB） ---------- */
    uint32_t bh, bp;
    uint64_t bs;
    void *black = create_dumb(W, H, 32, &bh, &bp, &bs);
    memset(black, 0, (size_t)bs);
    uint32_t black_fb = 0;
    uint32_t bhandles[4] = { bh, 0, 0, 0 };      /* AddFB2 固定按 4 元素平面数组读 */
    uint32_t bpitches[4] = { bp, 0, 0, 0 };
    uint32_t boffsets[4] = { 0, 0, 0, 0 };
    if (drmModeAddFB2(g_fd, W, H, DRM_FORMAT_XRGB8888, bhandles, bpitches, boffsets,
                      &black_fb, 0) != 0)
        die("AddFB2 XRGB8888");

    /* ---------- 素材 + 5 块 NV12 ---------- */
    uint8_t *bars = read_file("bars_nv12.yuv", BARS_BYTES);
    uint8_t *glyphs = read_file("glyphs.gray", GLYPH_BYTES);

    struct slot slots[NBUF];
    memset(slots, 0, sizeof(slots));
    for (int i = 0; i < NBUF; i++) {
        struct slot *s = &slots[i];
        s->map = create_dumb(W, YLINES * 3 / 2, 8, &s->handle, &s->pitch, &s->size);
        uint32_t handles[4] = { s->handle, s->handle, 0, 0 };
        uint32_t pitches[4] = { s->pitch, s->pitch, 0, 0 };
        uint32_t offs[4] = { 0, s->pitch * YLINES, 0, 0 };
        if (drmModeAddFB2(g_fd, W, H, DRM_FORMAT_NV12, handles, pitches, offs, &s->fb, 0) != 0)
            die("AddFB2 NV12");
        if (drmPrimeHandleToFD(g_fd, s->handle, DRM_CLOEXEC | DRM_RDWR, &s->prime_fd) != 0)
            die("drmPrimeHandleToFD");

        for (int r = 0; r < H; r++)                       /* Y：文件紧排 → 目标按 pitch */
            memcpy(s->map + (size_t)r * s->pitch, bars + (size_t)r * W, W);
        for (int r = 0; r < H / 2; r++)                   /* UV */
            memcpy(s->map + (size_t)s->pitch * YLINES + (size_t)r * s->pitch,
                   bars + (size_t)W * H + (size_t)r * W, W);
        for (int r = 0; r < GLYPH_H; r++)                 /* 码表区擦成黑 */
            memset(s->map + (size_t)(TXT_Y0 + r) * s->pitch + TXT_X0, 16, TXT_CHARS * GLYPH_W);
        for (int r = 0; r < GLYPH_H / 2; r++)             /* 对应 UV 擦成中性灰 */
            memset(s->map + (size_t)s->pitch * YLINES +
                   (size_t)(TXT_Y0 / 2 + r) * s->pitch + TXT_X0, 128, TXT_CHARS * GLYPH_W);
        s->state = S_FREE;
    }

    /* ---------- T13：把每块的 prime_fd 包成 GstMemory（一次性的，退出才释放） ---- */
    if (g_enc) {
        gst_init(NULL, NULL);
        g_dmalloc = gst_dmabuf_allocator_new();
        for (int i = 0; i < NBUF; i++)
            slots[i].mem = gst_dmabuf_allocator_alloc_with_flags(
                g_dmalloc, slots[i].prime_fd, (gsize)slots[i].size,
                GST_FD_MEMORY_FLAG_DONT_CLOSE);
        if (!enc_setup())
            return 1;
        printf("enc: mpph265enc bps=6000000 gop=60 -> rtp 127.0.0.1:5004 pt=96\n");
        fflush(stdout);
    }

    /* ---------- 第一次提交：带 MODESET，阻塞 ---------- */
    uint32_t blob = 0;
    if (drmModeCreatePropertyBlob(g_fd, mode, sizeof(*mode), &blob) != 0)
        die("CreatePropertyBlob");

    drmModeAtomicReqPtr req = drmModeAtomicAlloc();
    if (req == NULL)
        die("AtomicAlloc");

    int rc = 0;
    rc |= drmModeAtomicAddProperty(req, conn->connector_id, pc_conn, crtc_id);
    rc |= drmModeAtomicAddProperty(req, crtc_id, pc_mode, blob);
    rc |= drmModeAtomicAddProperty(req, crtc_id, pc_act, 1);
    rc |= drmModeAtomicAddProperty(req, primary_id, pp_fb, black_fb);
    rc |= drmModeAtomicAddProperty(req, primary_id, pp_crtc, crtc_id);
    rc |= drmModeAtomicAddProperty(req, primary_id, pp_sx, 0);
    rc |= drmModeAtomicAddProperty(req, primary_id, pp_sy, 0);
    rc |= drmModeAtomicAddProperty(req, primary_id, pp_sw, (uint64_t)W << 16);
    rc |= drmModeAtomicAddProperty(req, primary_id, pp_sh, (uint64_t)H << 16);
    rc |= drmModeAtomicAddProperty(req, primary_id, pp_cx, 0);
    rc |= drmModeAtomicAddProperty(req, primary_id, pp_cy, 0);
    rc |= drmModeAtomicAddProperty(req, primary_id, pp_cw, W);
    rc |= drmModeAtomicAddProperty(req, primary_id, pp_ch, H);
    rc |= drmModeAtomicAddProperty(req, nv12_id, g_prop_fb, slots[0].fb);
    rc |= drmModeAtomicAddProperty(req, nv12_id, np_crtc, crtc_id);
    rc |= drmModeAtomicAddProperty(req, nv12_id, np_sx, 0);
    rc |= drmModeAtomicAddProperty(req, nv12_id, np_sy, 0);
    rc |= drmModeAtomicAddProperty(req, nv12_id, np_sw, (uint64_t)W << 16);
    rc |= drmModeAtomicAddProperty(req, nv12_id, np_sh, (uint64_t)H << 16);
    rc |= drmModeAtomicAddProperty(req, nv12_id, np_cx, 0);
    rc |= drmModeAtomicAddProperty(req, nv12_id, np_cy, 0);
    rc |= drmModeAtomicAddProperty(req, nv12_id, np_cw, W);
    rc |= drmModeAtomicAddProperty(req, nv12_id, np_ch, H);
    if (rc < 0)
        die_ret("AtomicAddProperty(first)", rc);

    slots[0].state = S_ON;
    g_on = &slots[0];
    rc = drmModeAtomicCommit(g_fd, req, DRM_MODE_ATOMIC_ALLOW_MODESET, NULL);
    if (rc != 0)
        die_ret("first AtomicCommit", rc);

    /* ---------- 主循环：一个 vblank 一帧 ---------- */
    drmEventContext ev;
    memset(&ev, 0, sizeof(ev));
    ev.version = 3;
    ev.page_flip_handler2 = flip_cb;

    double start = now_s();
    double next_report = start + 1.0;
    long frame = 1;

    while (!g_quit) {
        if (seconds > 0 && (now_s() - start) >= seconds)
            break;

        struct slot *cur = NULL;
        for (int i = 0; i < NBUF; i++) {
            if (slots[i].state != S_FREE)
                continue;
            if (__atomic_load_n(&slots[i].enc_refs, __ATOMIC_SEQ_CST) > 0)
                continue;                       /* 编码器还在读这块 */
            cur = &slots[i];
            break;
        }
        if (cur == NULL) {
            g_noslot++;
            fprintf(stderr, "no free slot\n");
            struct pollfd pfd = { .fd = g_fd, .events = POLLIN, .revents = 0 };
            if (poll(&pfd, 1, 50) > 0)
                drmHandleEvent(g_fd, &ev);
            continue;
        }

        draw_table(cur, cur->pitch, glyphs, frame);

        drmModeAtomicSetCursor(req, 0);
        rc = (int)drmModeAtomicAddProperty(req, nv12_id, g_prop_fb, cur->fb);
        if (rc < 0)
            die_ret("AtomicAddProperty(loop)", rc);
        cur->state = S_PENDING;
        rc = drmModeAtomicCommit(g_fd, req,
                                 DRM_MODE_PAGE_FLIP_EVENT | DRM_MODE_ATOMIC_NONBLOCK, cur);
        if (rc != 0)
            die_ret("AtomicCommit(loop)", rc);
        frame++;

        /* 电视已经提交完了才想到编码器：它忙就跳过这帧，绝不回头等它 */
        if (g_enc) {
            long inuse = 0;
            for (int i = 0; i < NBUF; i++)
                if (__atomic_load_n(&slots[i].enc_refs, __ATOMIC_SEQ_CST) > 0)
                    inuse++;
            if (inuse < 2) {
                enc_push(cur);
            } else {
                __atomic_add_fetch(&g_enc_skip, 1, __ATOMIC_SEQ_CST);
            }
        }

        struct pollfd pfd = { .fd = g_fd, .events = POLLIN, .revents = 0 };
        if (poll(&pfd, 1, 100) > 0)
            drmHandleEvent(g_fd, &ev);

        double t = now_s();
        if (t >= next_report) {
            long enc_now = __atomic_load_n(&g_enc_frames, __ATOMIC_SEQ_CST);
            if (g_enc) {
                fprintf(stderr,
                        "flips=%ld miss=%ld dt_avg=%.2f dt_max=%.2f noslot=%ld enc=%ld enc_skip=%ld\n",
                        g_flips_sec, g_miss,
                        g_flips_sec ? g_dt_sum / g_flips_sec : 0.0, g_dt_max, g_noslot,
                        enc_now - g_enc_last, __atomic_load_n(&g_enc_skip, __ATOMIC_SEQ_CST));
                g_enc_last = enc_now;
                GstMessage *m = gst_bus_pop_filtered(g_bus, GST_MESSAGE_ERROR | GST_MESSAGE_WARNING);
                if (m != NULL) {
                    GError *ge = NULL;
                    gst_message_parse_error(m, &ge, NULL);
                    fprintf(stderr, "BUS %s: %s\n",
                            GST_MESSAGE_TYPE_NAME(m), ge != NULL ? ge->message : "-");
                    if (ge != NULL)
                        g_error_free(ge);
                    gst_message_unref(m);
                }
            } else {
                fprintf(stderr, "flips=%ld miss=%ld dt_avg=%.2f dt_max=%.2f noslot=%ld\n",
                        g_flips_sec, g_miss,
                        g_flips_sec ? g_dt_sum / g_flips_sec : 0.0, g_dt_max, g_noslot);
            }
            fflush(stderr);
            g_flips_sec = 0;
            g_dt_sum = 0;
            g_dt_max = 0;
            next_report += 1.0;
        }
    }

    fprintf(stderr, "TOTAL flips=%ld miss=%ld noslot=%ld enc=%ld enc_skip=%ld\n",
            frame - 1, g_miss, g_noslot,
            __atomic_load_n(&g_enc_frames, __ATOMIC_SEQ_CST),
            __atomic_load_n(&g_enc_skip, __ATOMIC_SEQ_CST));
    fflush(stderr);

    if (g_enc) {
        gst_element_set_state(g_pipe, GST_STATE_NULL);
        for (int i = 0; i < NBUF; i++)
            if (slots[i].mem != NULL)
                gst_memory_unref(slots[i].mem);
        gst_object_unref(g_bus);
        gst_object_unref(g_appsrc);
        gst_object_unref(g_dmalloc);
        gst_object_unref(g_pipe);
        gst_deinit();
    }

    drmModeDestroyPropertyBlob(g_fd, blob);
    drmModeAtomicFree(req);
    drmModeFreeConnector(conn);
    drmModeFreeResources(res);
    close(g_fd);
    return 0;
}
