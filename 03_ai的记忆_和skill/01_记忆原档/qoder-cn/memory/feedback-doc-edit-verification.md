---
name: feedback-doc-edit-verification
description: 改 markdown 文档的结构（插/删节、替换标题附近内容）之后，必须回跑一次标题与代码围栏检查再说"改好了"
metadata:
  type: feedback
---

**规则：任何动过文档结构的编辑（新增节、重排编号、替换标题上下方的内容），落地后必须跑这两条再回复用户：**

```bash
grep -n '^## \|^### ' <文件>      # 编号连续、没有标题被吃掉
grep -c '^```' <文件>             # 偶数（代码围栏成对）
```

**Why:** 在 `12_win_上机跑/15_KVM公网连接方案.md` 上我**连着三次**犯同一个错：
用 Edit 替换的 `old_string` 里带着下一节的标题（`---\n\n## 2. …`、`## 9. 附录`），
`new_string` 里忘了把它写回去 ⇒ 整节标题凭空消失，正文变成"孤儿"。
前两次都是事后自己 grep 才发现，第三次（2026-11-01）同样是 grep 出来才补回。
这类错误**看 diff 不容易发现**（少了的那行在 old_string 里，看起来像"我只是替换了内容"），
但对读者就是"目录里少了整整一节"。

**How to apply:**
- 优先让 `old_string` **不含标题行**（只替换标题之间的内容），从根上避免吃掉标题；
- 万不得已要连标题一起替换，就把标题原样写进 `new_string`，并立刻 grep 复核；
- 重排章节编号时，顺带 grep 交叉引用（`§9`、`第 9 节`、`见 §x.y`）和代码围栏配对；
- 报告"改好了"之前，这几条是**前置条件**，不是可选检查。

相关：[[feedback-instrument-and-explain-metrics]]（先有证据再下结论）、[[feedback-memory-mirrored-into-repo]]
