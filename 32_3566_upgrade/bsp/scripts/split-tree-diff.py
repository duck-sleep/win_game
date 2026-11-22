#!/usr/bin/env python3
"""把一个组件「基线 -> 目标树」的差异拆成符合 BSP 任务规则的提交序列。

用法（在组件临时仓库里，工作区已铺好目标内容）：
  python3 split-tree-diff.py --baseline <commit> --component kernel-6.1 \
      --origin "Origin: rockchip sdk import 1f9d3a8 vs <url>@<commit>, path kernel-6.1" \
      --blobs-list ../blobs-kernel-6.1.txt --report ../split-kernel-6.1.json

规则（BSP_patch拆分任务.md 第 2 条）：
  - 一个 patch 一个主题；按目录从顶往下分组，超过 1MB 或 100 个文件就展开子目录；
    叶子仍超限就按文件名排序切段，标题带 (part i/n)。
  - 单个 >1MB 的源文件可以独占一个 patch，记入 report 的 exceptions。
  - 二进制不进 patch：从暂存区剔除，写入 blobs 清单（apply.sh 负责拷回/删除）。

脚本结束后 HEAD 是一串按组排好的提交，再跑
  git format-patch -o <输出目录> <baseline>..HEAD
即得 patch 序列。
"""
import argparse
import hashlib
import json
import os
import re
import subprocess
import sys
from collections import defaultdict

MAX_BYTES = 1000000   # 给 format-patch 的头部留余量（规则上限 1MB）
MAX_FILES = 100


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--repo", default=".")
    ap.add_argument("--baseline", required=True)
    ap.add_argument("--component", required=True)
    ap.add_argument("--origin", required=True, help="完整 Origin: 行，逐字进每个提交信息")
    ap.add_argument("--blobs-list", required=True)
    ap.add_argument("--report", required=True)
    ap.add_argument("--max-bytes", type=int, default=MAX_BYTES)
    ap.add_argument("--max-files", type=int, default=MAX_FILES)
    ap.add_argument("--author-name", default="bsp-split")
    ap.add_argument("--author-email", default="bsp-split@local")
    args = ap.parse_args()
    repo = os.path.abspath(args.repo)
    base = args.baseline

    env = dict(os.environ,
               GIT_AUTHOR_NAME=args.author_name, GIT_AUTHOR_EMAIL=args.author_email,
               GIT_COMMITTER_NAME=args.author_name, GIT_COMMITTER_EMAIL=args.author_email)

    def g(*a, input=None):
        r = subprocess.run(["git", "-C", repo] + list(a), input=input,
                           stdout=subprocess.PIPE, stderr=subprocess.PIPE, env=env)
        if r.returncode != 0:
            sys.exit("git %s 失败: %s" % (" ".join(a), r.stderr.decode("utf-8", "replace")))
        return r.stdout

    # 1. 全部暂存，拿变更清单
    g("add", "-A", "-f")
    raw = g("diff", "--cached", "--no-renames", "--name-status", "-z", base)
    fields = raw.split(b"\0")
    changes = []  # (status, path)
    i = 0
    while i < len(fields) - 1:
        st = fields[i].decode()
        if not st:
            i += 1
            continue
        changes.append((st[0], fields[i + 1].decode("utf-8")))
        i += 2
    if not changes:
        print("没有差异，无需拆分")
        json.dump({"component": args.component, "groups": [], "binaries": [], "exceptions": []},
                  open(args.report, "w"), indent=1)
        return

    # 2. 二进制识别（numstat 里是 - -）
    numstat = g("diff", "--cached", "--no-renames", "--numstat", "-z", base)
    nf = numstat.split(b"\0")
    binary = set()
    j = 0
    while j < len(nf) - 1:
        if not nf[j]:
            j += 1
            continue
        parts = nf[j].split(b"\t")
        if len(parts) >= 3 and parts[0] == b"-" and parts[1] == b"-":
            binary.add(parts[2].decode("utf-8"))
        j += 1

    binaries = []
    for st, p in changes:
        if p in binary:
            full = os.path.join(repo, p)
            if st == "D":
                binaries.append({"path": p, "status": "D", "sha256": "", "mode": ""})
            else:
                h = hashlib.sha256(open(full, "rb").read()).hexdigest()
                m = oct(os.stat(full).st_mode & 0o777)[2:]
                binaries.append({"path": p, "status": st, "sha256": h, "mode": m})
    if binaries:
        g("reset", "-q", base, "--", *[b["path"] for b in binaries])
    with open(args.blobs_list, "w") as f:
        for b in sorted(binaries, key=lambda x: x["path"]):
            f.write("%s\t%s\t%s\t%s\n" % (b["status"], b["path"], b["sha256"], b["mode"]))

    text = [(st, p) for st, p in changes if p not in binary]
    if not text:
        print("只有二进制差异，见 blobs 清单")
        json.dump({"component": args.component, "groups": [], "binaries": binaries,
                   "exceptions": []}, open(args.report, "w"), indent=1)
        return

    # 3. 一次性生成全量 diff，按文件切块记大小
    names = [p for _, p in text]
    size = {p: len(g("diff", "--cached", "--no-renames", base, "--", p)) for p in names}

    def gsize(paths):
        return sum(size[p] for p in paths)

    groups = []      # (label, [paths])
    exceptions = []

    def chunk_files(paths, label):
        paths = sorted(paths)
        cur, cur_bytes = [], 0
        segs = []
        for p in paths:
            s = size[p]
            if s > args.max_bytes:
                if cur:
                    segs.append(cur)
                    cur, cur_bytes = [], 0
                segs.append([p])
                exceptions.append({"path": p, "diff_bytes": s,
                                   "note": "单个源文件 diff 超过 1MB，独占一个 patch"})
                continue
            if cur and (cur_bytes + s > args.max_bytes or len(cur) >= args.max_files):
                segs.append(cur)
                cur, cur_bytes = [], 0
            cur.append(p)
            cur_bytes += s
        if cur:
            segs.append(cur)
        n = len(segs)
        for i, seg in enumerate(segs, 1):
            lab = label if n == 1 else "%s (part %d/%d)" % (label, i, n)
            groups.append((lab, seg))

    def split(paths, label, depth):
        if len(paths) <= args.max_files and gsize(paths) <= args.max_bytes:
            groups.append((label, sorted(paths)))
            return
        # 尝试按第 depth 层目录展开
        children = defaultdict(list)
        here = []
        for p in paths:
            parts = p.split("/")
            if len(parts) > depth + 1:
                children[parts[depth]].append(p)
            else:
                here.append(p)
        if not children:
            chunk_files(paths, label)
            return
        if here:
            chunk_files(here, label + "/(files)" if label else "(files)")
        for name in sorted(children):
            sub = children[name]
            sublabel = name if not label else label + "/" + name
            split(sub, sublabel, depth + 1)

    top = defaultdict(list)
    rootfiles = []
    for _, p in text:
        if "/" in p:
            top[p.split("/")[0]].append(p)
        else:
            rootfiles.append(p)
    if rootfiles:
        split(rootfiles, "(root)", 0)
    for name in sorted(top):
        split(top[name], name, 1)

    # 4. 逐组建提交（先全部取消暂存，再按组 add）
    g("reset", "-q")
    for label, paths in groups:
        g("add", "--", *paths) if len(paths) <= 500 else \
            g("add", "--pathspec-from-file=-", "--pathspec-file-nul",
              input=b"\0".join(p.encode() for p in paths))
        msg = "%s: %s\n\n%s\n" % (args.component, label, args.origin)
        g("commit", "-q", "-m", msg)

    report = {
        "component": args.component,
        "baseline": base,
        "groups": [{"title": lab, "files": len(ps), "diff_bytes": gsize(ps)}
                   for lab, ps in groups],
        "binaries": binaries,
        "exceptions": exceptions,
    }
    with open(args.report, "w") as f:
        json.dump(report, f, indent=1, ensure_ascii=False)
    print("组件 %s：%d 个文本组提交，%d 个二进制进 blobs，%d 个超限例外"
          % (args.component, len(groups), len(binaries), len(exceptions)))


if __name__ == "__main__":
    main()