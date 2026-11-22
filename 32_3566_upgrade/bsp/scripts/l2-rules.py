#!/usr/bin/env python3
# l2-rules.py — L2 窄规则判定（compare-build.sh 调用）。不按文件名单豁免。
# 每个有差异的文件必须套进一条写死的规则，否则计入「无法解释」。
import os, re, sys, struct, gzip, crypt

DATE = rb"20\d\d-\d\d-\d\d"
TIME = rb"\d\d:\d\d:\d\d"
FULLTS = rb"[A-Z][a-z]{2} [A-Z][a-z]{2} +\d+ \d\d:\d\d:\d\d [A-Z]+ 20\d\d"
# OpenSSL "built on: Thu Nov 19 16:00:38 2026 UTC"（年在时区前）
OSSLTS = rb"[A-Z][a-z]{2} [A-Z][a-z]{2} +\d+ \d\d:\d\d:\d\d 20\d\d [A-Z]+"
ATTS = rb"[A-Z][a-z]{2} +\d+ 20\d\d at \d\d:\d\d:\d\d"
BDATE = rb"[A-Z][a-z]{2} +\d+ 20\d\d"
GIT = rb"-g[0-9a-f]{7,40}"
PATS = [FULLTS, OSSLTS, ATTS, DATE, TIME, BDATE, GIT]

def norm_ts(b):
    for p in PATS:
        b = re.sub(p, b"<TS>", b)
    return b

def diff_positions(rb, nb):
    return [i for i, (a, b) in enumerate(zip(rb, nb)) if a != b]

def regions(pos, gap=32):
    out = []
    for p in pos:
        if out and p - out[-1][1] <= gap:
            out[-1][1] = p
        else:
            out.append([p, p])
    return out

def miniloader(r, n):
    rb, nb = open(r, "rb").read(), open(n, "rb").read()
    if len(rb) != len(nb):
        print("[L2] FAIL MiniLoaderAll 大小不同"); return 1
    if rb[:4] != b"LDR " or nb[:4] != b"LDR ":
        print("[L2] FAIL MiniLoaderAll magic"); return 1
    sz = len(rb)
    allowed = set(range(14, 21)) | set(range(sz - 4, sz))
    pos = diff_positions(rb, nb)
    bad = [p for p in pos if p not in allowed]
    if bad:
        print("[L2] FAIL MiniLoaderAll 差异越界(前10):", bad[:10]); return 1
    def dec(b):
        return "%04d-%02d-%02d %02d:%02d:%02d" % (
            int.from_bytes(b[14:16], "little"), b[16], b[17], b[18], b[19], b[20])
    print("[L2] OK MiniLoaderAll 仅时间字段+校验和 (%d 字节差异)" % len(pos))
    print("     0x0E-0x14 打包时间: ref=%s new=%s" % (dec(rb), dec(nb)))
    print("     末尾4字节校验和: ref=%s new=%s" % (rb[-4:].hex(), nb[-4:].hex()))
    return 0

def brconfig(r, n):
    rl = open(r, "rb").read().split(b"\n")
    nl = open(n, "rb").read().split(b"\n")
    if len(rl) != len(nl):
        print("[L2] FAIL buildroot .config 行数不同"); return 1
    pat = re.compile(rb"^# Buildroot -g[0-9a-f]+ Configuration$")
    bad = 0
    for i, (a, b) in enumerate(zip(rl, nl)):
        if a == b:
            continue
        if pat.match(a) and pat.match(b):
            print("[L2] buildroot .config 哈希注释行: %s -> %s" % (a.decode(), b.decode()))
        else:
            print("[L2] FAIL buildroot .config 第%d行非哈希注释差异: %r vs %r" % (i + 1, a[:80], b[:80]))
            bad = 1
    if bad:
        return 1
    print("[L2] OK buildroot .config 仅哈希注释行")
    return 0

def rule_pyc(rb, nb):
    if len(rb) != len(nb) or len(rb) < 16:
        return False
    return rb[:8] == nb[:8] and rb[12:16] == nb[12:16] and rb[16:] == nb[16:] and rb[8:12] != nb[8:12]

def rule_gz(rb, nb):
    if len(rb) != len(nb) or len(rb) < 8:
        return False
    if rb[:4] != nb[:4] or rb[8:] != nb[8:] or rb[4:8] == nb[4:8]:
        return False
    try:
        return gzip.decompress(rb) == gzip.decompress(nb)
    except Exception:
        return False

def rule_osrelease(rb, nb):
    rl, nl = rb.split(b"\n"), nb.split(b"\n")
    if len(rl) != len(nl):
        return False
    vpat = re.compile(rb"^VERSION=-g[0-9a-f]+$")
    for a, b in zip(rl, nl):
        if a == b:
            continue
        if vpat.match(a) and vpat.match(b):
            continue
        if a.startswith(b"RK_BUILD_INFO=") and b.startswith(b"RK_BUILD_INFO=") and norm_ts(a) == norm_ts(b):
            continue
        return False
    return True

def rule_shadow(rb, nb, password):
    rl, nl = rb.split(b"\n"), nb.split(b"\n")
    if len(rl) != len(nl):
        return False
    hpat = re.compile(r"^\$5\$[A-Za-z0-9./]+\$[A-Za-z0-9./]+$")
    for a, b in zip(rl, nl):
        if a == b:
            continue
        fa, fb = a.split(b":"), b.split(b":")
        if len(fa) != len(fb) or fa[0] != fb[0] or fa[2:] != fb[2:]:
            return False
        ha, hb = fa[1].decode(), fb[1].decode()
        if not (hpat.match(ha) and hpat.match(hb)):
            return False
        sa, sb = ha.split("$")[2], hb.split("$")[2]
        if crypt.crypt(password, "$5$" + sa) != ha or crypt.crypt(password, "$5$" + sb) != hb:
            return False
    return True

def elf_sections(b):
    if b[:4] != b"\x7fELF" or b[4] != 2:
        return None
    shoff = struct.unpack_from("<Q", b, 0x28)[0]
    shentsize, shnum, shstrndx = struct.unpack_from("<HHH", b, 0x3A)
    secs = []
    for i in range(shnum):
        o = shoff + i * shentsize
        name, typ, flags, addr, off, size = struct.unpack_from("<IIQQQQ", b, o)
        secs.append([name, typ, off, size])
    strtab = secs[shstrndx]
    for s in secs:
        base = strtab[2] + s[0]
        end = b.find(b"\x00", base)
        s.append(b[base:end].decode("latin1"))
    return secs

def rule_elf(rb, nb):
    if len(rb) != len(nb):
        return False, "大小不同(%d vs %d)" % (len(rb), len(nb))
    sa, sb = elf_sections(rb), elf_sections(nb)
    if sa is None or sb is None:
        return False, "非ELF64"
    if len(sa) != len(sb):
        return False, "段数不同"
    for x, y in zip(sa, sb):
        if x[3] != y[3]:
            return False, "段大小不同: %s %d vs %d" % (x[4], x[3], y[3])
        if x[4] != y[4] or x[1] != y[1]:
            return False, "段名/类型不同: %s" % x[4]
    ta = [s for s in sa if s[4] == ".text"]
    tb = [s for s in sb if s[4] == ".text"]
    if ta and tb:
        if rb[ta[0][2]:ta[0][2] + ta[0][3]] != nb[tb[0][2]:tb[0][2] + tb[0][3]]:
            return False, ".text 不同"
    # .note.gnu.build-id（SHT_NOTE=7）：只放行 desc 的 20 字节（段偏移 16..35）；
    # 段头 16 字节、desc 之后到段尾都必须相同。其余差异字节继续套现有日期/时间/git 串规则。
    bid = []
    for x, y in zip(sa, sb):
        if x[4] == ".note.gnu.build-id":
            if x[1] != 7 or y[1] != 7 or x[3] < 36 or y[3] < 36:
                return False, "build-id 段异常"
            bid.append((x[2], y[2], x[3], y[3]))
    pos = diff_positions(rb, nb)
    if not pos:
        return True, ""
    used_bid = False
    if bid:
        if len(bid) > 1:
            return False, "多个 build-id 段"
        ao, bo, asz, bsz = bid[0]
        if rb[ao:ao + 16] != nb[bo:bo + 16]:
            return False, "build-id 段头不同"
        if rb[ao + 36:ao + asz] != nb[bo + 36:bo + bsz]:
            return False, "build-id 段 desc 之后有差异"
        span_a = range(ao + 16, ao + 36)
        span_b = range(bo + 16, bo + 36)
        used_bid = any(rb[d] != nb[d] for d in pos if d in span_a or d in span_b)
        pos = [d for d in pos if not (d in span_a or d in span_b)]
        if not pos:
            return True, ("build-id" if used_bid else "")
    spans_a, spans_b = [], []
    for p in PATS:
        spans_a += [(m.start(), m.end()) for m in re.finditer(p, rb)]
        spans_b += [(m.start(), m.end()) for m in re.finditer(p, nb)]
    def covered(spans, i):
        return any(s <= i < e for s, e in spans)
    # 按差异字节所属的 C 串分组（相邻两串各自判定，串间 \0 填充不算串内容）
    groups = {}
    for d in pos:
        lo = rb.rfind(b"\x00", max(0, d - 4096), d) + 1
        hi = rb.find(b"\x00", d)
        lo2 = nb.rfind(b"\x00", max(0, d - 4096), d) + 1
        hi2 = nb.find(b"\x00", d)
        if hi < 0 or hi2 < 0 or lo != lo2 or hi != hi2:
            return False, "差异不在同一C串内 @%d" % d
        groups.setdefault((lo, hi), []).append(d)
    for (lo, hi), ds in groups.items():
        sr, sn = rb[lo:hi], nb[lo:hi]
        def printable(x):
            return all(c in (9, 10, 13) or 32 <= c < 127 for c in x)
        if not printable(sr) or not printable(sn):
            return False, "差异串含非打印字节 @%d" % lo
        if norm_ts(sr) != norm_ts(sn):
            return False, "串归一化后不同 @%d: %r" % (lo, sr[:80])
        for d in ds:
            if not (covered(spans_a, d) and covered(spans_b, d)):
                return False, "差异字节不在日期/时间/git串内 @%d" % d
    return True, ("build-id" if used_bid else "")

def target(reftgt, newtgt, manifest, password):
    counts = {"same": 0, "symlink": 0, "pyc-mtime": 0, "gz-mtime": 0,
              "os-release-meta": 0, "shadow-salt": 0, "elf-timestamp": 0,
              "elf-build-id": 0}
    unexplained = []
    missing = []
    for line in open(manifest):
        f = line.strip()
        if not f:
            continue
        r, n = os.path.join(reftgt, f), os.path.join(newtgt, f)
        if os.path.islink(r) or os.path.islink(n):
            if os.path.islink(r) and os.path.islink(n) and os.readlink(r) == os.readlink(n):
                counts["symlink"] += 1
            else:
                unexplained.append((f, "软链不一致"))
            continue
        if not os.path.isfile(n):
            missing.append(f); continue
        if not os.path.isfile(r):
            unexplained.append((f, "参考侧缺失")); continue
        rb, nb = open(r, "rb").read(), open(n, "rb").read()
        if rb == nb:
            counts["same"] += 1; continue
        base = os.path.basename(f)
        if f.endswith(".pyc") and rule_pyc(rb, nb):
            counts["pyc-mtime"] += 1; continue
        if f.endswith(".gz") and rule_gz(rb, nb):
            counts["gz-mtime"] += 1; continue
        if base == "os-release" and rule_osrelease(rb, nb):
            counts["os-release-meta"] += 1; continue
        if base == "shadow" and rule_shadow(rb, nb, password):
            counts["shadow-salt"] += 1; continue
        if rb[:4] == b"\x7fELF":
            ok, why = rule_elf(rb, nb)
            if ok:
                counts["elf-build-id" if why == "build-id" else "elf-timestamp"] += 1
                continue
            unexplained.append((f, "ELF: " + why)); continue
        unexplained.append((f, "无匹配规则"))
    print("[L2] target 逐字节相同: %d, 软链相同: %d" % (counts["same"], counts["symlink"]))
    print("[L2] target 规则命中: pyc-mtime=%d gz-mtime=%d os-release-meta=%d shadow-salt=%d elf-timestamp=%d elf-build-id=%d" % (
        counts["pyc-mtime"], counts["gz-mtime"], counts["os-release-meta"],
        counts["shadow-salt"], counts["elf-timestamp"], counts["elf-build-id"]))
    if missing:
        print("[L2] FAIL 缺失文件 %d 个:" % len(missing))
        for f in missing[:20]:
            print("   ", f)
    for f, why in unexplained:
        print("[L2] 无法解释: %s (%s)" % (f, why))
    print("[L2] 无法解释: %d" % (len(unexplained) + len(missing)))
    return 1 if (unexplained or missing) else 0

if __name__ == "__main__":
    cmd = sys.argv[1]
    if cmd == "miniloader":
        sys.exit(miniloader(sys.argv[2], sys.argv[3]))
    elif cmd == "brconfig":
        sys.exit(brconfig(sys.argv[2], sys.argv[3]))
    elif cmd == "target":
        sys.exit(target(sys.argv[2], sys.argv[3], sys.argv[4], sys.argv[5]))
    sys.exit(2)