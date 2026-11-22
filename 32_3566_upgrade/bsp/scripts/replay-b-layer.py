#!/usr/bin/env python3
"""B 层生成器：把 KickPI 的提交按组件重放进临时仓库，产出可 git am 的纯文本提交序列。

规则（BSP_patch拆分任务.md 第 5 步）：
  - 一个原提交 = 一个 patch，保留原标题/作者/日期，提交信息加 Origin: kickpi <原hash>。
  - 空提交跳过。二进制不进 patch（剔除，最终状态由 blobs 提供）。
  - 超过 1MB 或 100 文件的提交：reset 后按目录/文件名拆段，标题带 (part i/n)。

前置：--work-repo 已初始化并提交好基线状态（HEAD = 基线）。
结束后 HEAD 即 B 层序列，跑 git format-patch <基线>..HEAD 导出。
"""
import argparse
import json
import os
import re
import shutil
import subprocess
import sys
from collections import defaultdict

MAX_BYTES = 1000000
MAX_FILES = 100
IDENT = {"GIT_AUTHOR_NAME": "bsp-split", "GIT_AUTHOR_EMAIL": "bsp-split@local",
         "GIT_COMMITTER_NAME": "bsp-split", "GIT_COMMITTER_EMAIL": "bsp-split@local"}


def run(cmd, cwd=None, env=None, input=None):
    r = subprocess.run(cmd, cwd=cwd, env=env, input=input,
                       stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    if r.returncode != 0:
        sys.exit("命令失败 %s\n%s" % (cmd, r.stderr.decode("utf-8", "replace")))
    return r.stdout


def git(repo, *args, input=None, env=None):
    e = dict(os.environ)
    e.update(IDENT)
    if env:
        e.update(env)
    return run(["git", "-C", repo] + list(args), env=e, input=input)


def split_diff_chunks(diff):
    chunks = re.split(rb"(?m)^(?=diff --git )", diff)
    return [c for c in chunks if c.startswith(b"diff --git ")]


def group_paths(names, size, max_bytes, max_files):
    groups, exceptions = [], []

    def gsize(ps):
        return sum(size[p] for p in ps)

    def chunk_files(paths, label):
        cur, cur_bytes, segs = [], 0, []
        for p in sorted(paths):
            s = size[p]
            if s > max_bytes:
                if cur:
                    segs.append(cur)
                    cur, cur_bytes = [], 0
                segs.append([p])
                exceptions.append({"path": p, "diff_bytes": s})
                continue
            if cur and (cur_bytes + s > max_bytes or len(cur) >= max_files):
                segs.append(cur)
                cur, cur_bytes = [], 0
            cur.append(p)
            cur_bytes += s
        if cur:
            segs.append(cur)
        n = len(segs)
        for i, seg in enumerate(segs, 1):
            groups.append((label if n == 1 else "%s (part %d/%d)" % (label, i, n), seg))

    def split(paths, label, depth):
        if len(paths) <= max_files and gsize(paths) <= max_bytes:
            groups.append((label, sorted(paths)))
            return
        children, here = defaultdict(list), []
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
            chunk_files(here, (label + "/(files)") if label else "(files)")
        for name in sorted(children):
            split(children[name], (label + "/" + name) if label else name, depth + 1)

    top, rootfiles = defaultdict(list), []
    for p in names:
        if "/" in p:
            top[p.split("/")[0]].append(p)
        else:
            rootfiles.append(p)
    if rootfiles:
        split(rootfiles, "(root)", 0)
    for name in sorted(top):
        split(top[name], name, 1)
    return groups, exceptions


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--sdk-repo", required=True)
    ap.add_argument("--work-repo", required=True)
    ap.add_argument("--component", required=True)
    ap.add_argument("--paths", required=True, help="逗号分隔的 SDK 内路径")
    ap.add_argument("--base", required=True)
    ap.add_argument("--head", required=True)
    ap.add_argument("--report", required=True)
    ap.add_argument("--max-bytes", type=int, default=MAX_BYTES)
    ap.add_argument("--max-files", type=int, default=MAX_FILES)
    args = ap.parse_args()
    sdk, work = os.path.abspath(args.sdk_repo), os.path.abspath(args.work_repo)
    paths = args.paths.split(",")
    base, head = args.base, args.head

    commits = git(sdk, "rev-list", "--reverse", "%s..%s" % (base, head),
                  "--", *paths).decode().split()
    made, skipped, parts_total, exceptions = [], 0, 0, []
    binaries_seen = set()
    prev = base

    for c in commits:
        meta = git(sdk, "show", "-s", "--format=%an%x00%ae%x00%aI%x00%B", c).decode("utf-8")
        an, ae, ad, body = meta.split("\0", 3)
        body = body.rstrip("\n")
        origin = "Origin: kickpi %s" % c

        delta = git(sdk, "diff", "--no-renames", "--binary", prev, c, "--", *paths)
        prev = c
        if not delta.strip():
            skipped += 1
            continue
        r = subprocess.run(["git", "-C", work, "apply", "--whitespace=nowarn"],
                           input=delta, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        if r.returncode != 0:
            sys.exit("git apply 失败于提交 %s:\n%s" % (c, r.stderr.decode("utf-8", "replace")))
        git(work, "add", "-A")

        ns = git(work, "diff", "--cached", "--no-renames", "--numstat", "-z", "HEAD")
        nf = ns.split(b"\0")
        binaries = set()
        j = 0
        while j < len(nf) - 1:
            if not nf[j]:
                j += 1
                continue
            parts = nf[j].split(b"\t")
            if len(parts) >= 3 and parts[0] == b"-" and parts[1] == b"-":
                binaries.add(parts[2].decode("utf-8"))
            j += 1
        if binaries:
            git(work, "reset", "-q", "HEAD", "--", *sorted(binaries))
            binaries_seen |= binaries

        names = git(work, "diff", "--cached", "--no-renames", "--name-only", "-z",
                    "HEAD").decode("utf-8").split("\0")
        names = [n for n in names if n]
        if not names:
            skipped += 1
            continue

        size = {n: len(git(work, "diff", "--cached", "--no-renames", "HEAD", "--", n)) for n in names}
        total = sum(size.values())

        author = "%s <%s>" % (an, ae)
        if total <= args.max_bytes and len(names) <= args.max_files:
            git(work, "commit", "-q", "--author", author, "--date", ad,
                "-m", body + "\n\n" + origin + "\n")
            made.append({"orig": c, "parts": 1, "files": len(names), "bytes": total})
            continue

        git(work, "reset", "-q")
        groups, exc = group_paths(names, size, args.max_bytes, args.max_files)
        exceptions += exc
        n = len(groups)
        for i, (label, ps) in enumerate(groups, 1):
            git(work, "add", "--", *ps)
            first, _, rest = body.partition("\n")
            title = first if n == 1 else "%s (part %d/%d)" % (first, i, n)
            msg = title + ("\n" + rest if rest else "") + "\n\n" + origin + "\n"
            git(work, "commit", "-q", "--author", author, "--date", ad, "-m", msg)
        made.append({"orig": c, "parts": n, "files": len(names), "bytes": total})
        parts_total += n

    # 校验：工作区（含未跟踪二进制）应与 SDK head 的对应路径完全一致
    import tempfile
    tmp = tempfile.mkdtemp(prefix="bverify-")
    arch = git(sdk, "archive", head, "--", *paths)
    run(["tar", "-x", "-C", tmp], input=arch)
    bad = []
    for p in paths:
        a, b = os.path.join(work, p), os.path.join(tmp, p)
        r = subprocess.run(["diff", "-r", "--no-dereference", "-q", a, b],
                           stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        for line in r.stdout.decode("utf-8", "replace").splitlines():
            bad.append(line)
    shutil.rmtree(tmp)
    total_commits = len(made) + sum(m["parts"] - 1 for m in made)
    report = {"component": args.component, "orig_commits": len(commits),
              "patches": total_commits,
              "skipped_empty": skipped, "split_commits": made,
              "binaries_seen": sorted(binaries_seen), "exceptions": exceptions,
              "tree_mismatch": bad}
    with open(args.report, "w") as f:
        json.dump(report, f, indent=1, ensure_ascii=False)
    print("%s: 原提交 %d，跳过空 %d，生成提交 %d，二进制 %d 种，树差异 %d"
          % (args.component, len(commits), skipped, total_commits,
             len(binaries_seen), len(bad)))
    if bad:
        print("🔴 工作区与 SDK head 不一致：")
        for line in bad[:20]:
            print(" ", line)
        sys.exit(1)


if __name__ == "__main__":
    main()