---
name: hapticx-png-guard
description: AI 会话报"图片格式不支持"(11135) 或读项目图片就挂时的诊断与修复流程。校验工作区 PNG 块结构/CRC、定位坏图、从 BMP 原地重生成、修复手写 PNG 编码的字节序 bug。
agent_created: true
---

# hapticx-png-guard — 会话 11135 坏图诊断

## 什么时候用

- 会话报 Error 11135"图片格式不支持，请更换图片后重试"，且重开上下文后一读某个项目目录就再挂
- 怀疑工作区里有坏图片污染会话上下文

## 诊断流程

1. **先扫全工作区图片**（找坏图在哪）：
   ```bash
   find /d/win_game_project -type f \( -iname "*.png" -o -iname "*.bmp" -o -iname "*.jpg" \) -printf "%s\t%p\n" | sort -rn
   ```
2. **逐张做 PNG 块结构 + CRC 校验**（纯 Python，无需 PIL）：
   ```python
   import struct, zlib, glob
   def check_png(path):
       data = open(path,'rb').read()
       if data[:8] != b'\x89PNG\r\n\x1a\n': return 'BAD: signature'
       pos = 8
       while pos + 8 <= len(data):
           ln, ctype = struct.unpack('>I4s', data[pos:pos+8])
           end = pos + 12 + ln
           if end > len(data): return f'BAD: {ctype} length overrun'
           crc = struct.unpack('>I', data[pos+8+ln:pos+12+ln])[0]
           if zlib.crc32(data[pos+4:pos+8+ln]) & 0xffffffff != crc: return f'BAD: {ctype} CRC'
           pos = end
           if ctype == b'IEND':
               return 'OK' if pos == len(data) else 'WARN: trailing bytes'
       return 'BAD: no IEND'
   for p in glob.glob(r'D:\win_game_project\**\*.png', recursive=True):
       print(f'{check_png(p):20s} {p}')
   ```
   （跑图用受管 Python：`C:\Users\123456\.workbuddy\binaries\python\versions\3.13.12\python.exe`，无 PIL 也能跑）

## 修复方式

- **能从 BMP 重生成**（本项目截图流程都是 BMP→PNG）：用 `hapticx\profiles_shot.py` 里的 `bmp2png()`（已修正为 `>I`）把同内容 BMP 原地转成好 PNG，不丢数据、不用重启 App。
- **无 BMP 来源**：把坏图移出工作区（或删掉，需用户确认），让会话不再读到它。

## 历史根因（2026-09-03 已修复）

`profiles_shot.py` 的 `chunk()` 曾用 `struct.pack("<I", ...)`（小端）写 PNG chunk 长度和 CRC，PNG 规范要求**大端 `>I`**，导致产出的 PNG 全是坏图。已改 `>I`。

## 预防

- 任何 AI 手写 PNG 编码，chunk 长度/CRC 必须大端
- 手写编码产出后，先用上面 check_png 校验一遍再交差
- 注意：PIL 不在任何 Python 环境里，别依赖 PIL
