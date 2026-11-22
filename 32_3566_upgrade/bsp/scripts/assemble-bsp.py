#!/usr/bin/env python3
"""assemble-bsp.py — 把 A/B/C 三层 patch 与 blobs 组装成最终 bsp/ 交付布局。
用法: python3 assemble-bsp.py <bsp-work目录> <输出bsp目录>
输入（bsp-work 下）: components.tsv, patches-a/<comp>, patches-b-final/<comp>,
  patches-c/<comp>, blobs-a/<comp>.txt, reports-b/<comp>.json, split-a/<comp>(基线仓库),
  ref-clean/(k11c-target 工作树)
输出: patches/<comp>/NNNN-<a|b|c>-<主题>.patch + series, blobs/<comp>/manifest.tsv + 文件,
  blobs/SHA256SUMS, assemble-report.json
"""
import json, os, re, shutil, stat, subprocess, sys, hashlib

W, OUT = sys.argv[1], sys.argv[2]

def g(repo, *a):
    return subprocess.run(["git", "-C", repo] + list(a), capture_output=True, text=True).stdout.strip()

def sha256(p):
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()

def topic(fname):
    # 0001-<subject>.patch -> subject 清洗成文件名
    s = re.sub(r"^\d+-", "", fname)
    s = re.sub(r"\.patch$", "", s)
    s = re.sub(r"[^A-Za-z0-9._-]+", "-", s).strip("-")
    return s[:80] or "patch"

comps = []
for line in open(os.path.join(W, "components.tsv")):
    if line.startswith("#") or not line.strip():
        continue
    comps.append(line.rstrip("\n").split("\t"))

os.makedirs(OUT, exist_ok=True)
report = {"components": {}, "exceptions": []}
blob_sums = []

for comp, path, kind, subset in comps:
    pdir = os.path.join(OUT, "patches", comp)
    os.makedirs(pdir, exist_ok=True)
    series = []
    n = 0
    counts = {}
    for layer, src in (("a", "patches-a"), ("b", "patches-b-final"), ("c", "patches-c")):
        d = os.path.join(W, src, comp)
        files = sorted(f for f in os.listdir(d) if f.endswith(".patch")) if os.path.isdir(d) else []
        counts[layer] = len(files)
        for f in files:
            n += 1
            name = f"{n:04d}-{layer}-{topic(f)}.patch"
            shutil.copyfile(os.path.join(d, f), os.path.join(pdir, name))
            series.append(name)
    with open(os.path.join(pdir, "series"), "w") as fh:
        fh.write("\n".join(series) + ("\n" if series else ""))

    # blobs: A 清单 ∪ B binaries_seen，最终内容取自 ref-clean（k11c-target）
    paths = set()
    al = os.path.join(W, "blobs-a", comp + ".txt")
    if os.path.isfile(al):
        for line in open(al):
            if line.strip() and not line.startswith("#"):
                paths.add(line.split("\t")[1])
    rb = os.path.join(W, "reports-b", comp + ".json")
    if os.path.isfile(rb):
        paths.update(json.load(open(rb)).get("binaries_seen", []))
    # A 层例外（单文件>1MB）也记入报告
    ra = os.path.join(W, "reports-a", comp + ".json")
    if os.path.isfile(ra):
        report["exceptions"] += json.load(open(ra)).get("exceptions", [])
    if os.path.isfile(rb):
        report["exceptions"] += json.load(open(rb)).get("exceptions", [])

    bdir = os.path.join(OUT, "blobs", comp)
    manifest = []
    arepo = os.path.join(W, "split-a", comp)
    base = g(arepo, "rev-list", "--max-parents=0", "HEAD") if os.path.isdir(arepo) else ""
    for sp in sorted(paths):
        rel = sp[len(path) + 1:] if path != "." else sp
        final = os.path.join(W, "ref-clean", sp)
        in_base = subprocess.run(["git", "-C", arepo, "cat-file", "-e", f"{base}:{sp}"],
                                 capture_output=True).returncode == 0 if base else False
        if not os.path.isfile(final):
            manifest.append(f"D\t{sp}\t-\t-")
            continue
        st = "M" if in_base else "A"
        mode = oct(stat.S_IMODE(os.stat(final).st_mode))[2:]
        os.makedirs(os.path.dirname(os.path.join(bdir, rel)), exist_ok=True)
        shutil.copyfile(final, os.path.join(bdir, rel))
        os.chmod(os.path.join(bdir, rel), int(mode, 8))
        h = sha256(final)
        manifest.append(f"{st}\t{sp}\t{h}\t{mode}")
        blob_sums.append(f"{h}  {comp}/{rel}")
    if manifest:
        os.makedirs(bdir, exist_ok=True)
        with open(os.path.join(bdir, "manifest.tsv"), "w") as fh:
            fh.write("\n".join(manifest) + "\n")
    report["components"][comp] = {"patches": counts, "blobs": len(manifest)}

with open(os.path.join(OUT, "blobs", "SHA256SUMS"), "w") as fh:
    fh.write("\n".join(blob_sums) + ("\n" if blob_sums else ""))
json.dump(report, open(os.path.join(OUT, "assemble-report.json"), "w"), indent=1, ensure_ascii=False)
total = sum(os.path.getsize(os.path.join(r, f)) for r, _, fs in os.walk(OUT) for f in fs)
print(f"ASSEMBLE_OK total={total/1e6:.1f}MB")
for c, v in report["components"].items():
    print(c, v)