# 弱网下推送仓库到 GitHub（FlClash / 代理环境）

适用：本机开着 FlClash（TUN + fake-ip）时，`git push` 到 GitHub 反复报
`send-pack: unexpected disconnect while reading sideband packet` /
`Connection to ssh.github.com closed by remote host`。

## 核心结论（先看这条）

**不是宽带问题，也不是 key 问题——是包太大 + 代理节点太慢，长传输被掐断。**

实测（09-11，深圳电信 + FlClash TUN）：

| 路径 | 到 GitHub 的下载实速 | TLS 握手 |
|---|---|---|
| FlClash TUN（fake-ip `198.18.0.24`） | **236 KB/s** | 3.0 s |
| WorkBuddy 沙箱代理 `127.0.0.1:5047` | **82 KB/s** | 2.7 s |
| 真实 IP 直连（`--resolve`） | 0.8~1.0 s | — |

同一份仓库：
- 9.43 MB 包 → 连续两次失败（19s 断 / 6m14s 断）
- **4.12 MB 包 → 1m51s 成功**

## 三步处置（按顺序做）

### 第 1 步：先把包瘦下来（收益最大）

算清各目录体积，把**可再生的产物**踢出索引：

```bash
# 各目录体积
du -sh */ | sort -rh
# 已跟踪文件里最大的 20 个
git ls-files -z | xargs -0 -I{} sh -c 'test -f "{}" && echo "$(stat -c%s "{}") {}"' | sort -rn | head -20
# 打包后真实体积（这才是要上传的量）
git pack-objects --all --revs --stdout --thin < /dev/null | wc -c
```

**优先排除**（都能重新生成，别进仓）：
- `*.bmp` 截图原图（同目录通常已有压缩后的 `.png`）
- `*.wav` 测试音频
- 编译好的测试二进制（**同目录保留 `.c` 源码**）
- `build/`、`.gradle/`、`__pycache__/`、`*.pyc`、`*.log`
- 安装包目录（如 `01_软件/`）、烧录包、游戏镜像

从索引移除但保留工作区文件：
```bash
git rm --cached <路径...>
git add -A .gitignore
git commit --amend          # 首次提交还没推上去时用 amend；已推过则另起提交
```

### 第 2 步：加 SSH 保活（防中途被静默掐断）

```bash
export GIT_SSH_COMMAND="ssh -o ServerAliveInterval=15 -o ServerAliveCountMax=8 -o TCPKeepAlive=yes -o ConnectTimeout=20"
git -c pack.threads=1 push -u origin main
```

- `ServerAliveInterval/CountMax`：定期发心跳，让 NAT/代理别回收连接
- `pack.threads=1`：少开并发，降低被中间设备干扰的概率
- 走后台跑，1~2 分钟是正常的

### 第 3 步：仍失败才动线上设置

**先问用户**，不要自己改他们的网络。可选项：
- FlClash 换节点 / 给 `github.com`、`github.io`、`*.githubusercontent.com` 加**直连规则**
- 临时关掉 FlClash TUN
- 或改用 Gitee 镜像（同环境下 Gitee TLS 只要 0.13s，快一个数量级）

## 首次建仓的前置检查（本机已验证可用）

```bash
# 1) 22 端口常被 FlClash fake-ip 拦，固定走 443 —— 写进 ~/.ssh/config
Host github.com
  HostName ssh.github.com
  Port 443
  User git
  IdentityFile ~/.ssh/id_ed25519
  ServerAliveInterval 15
  ServerAliveCountMax 8

# 2) 验证认证（应回 Hi <用户名>!）
ssh -T git@github.com

# 3) 补 git 身份（否则 commit 报错）
git config --global user.name  "duck-sleep"
git config --global user.email "ltw18505222732@gmail.com"

# 4) 探测远端仓库是否存在、是否为空
git ls-remote --heads origin      # 退出码 0 且无输出 = 仓库存在但为空
```

## 错误速查

| 报错 | 含义 | 处置 |
|---|---|---|
| `unexpected disconnect while reading sideband packet` | 长传输被中间设备/代理掐断 | 瘦包 + 保活重试；改直连规则 |
| `Connection to ssh.github.com closed by remote host` | 同上，代理节点主动断 | 同上 |
| `port 22: Connection timed out` + 解析到 `198.18.x.x` | FlClash fake-ip 拦了 22 端口 | ssh config 改走 `ssh.github.com:443` |
| `remote: Repository not found` | 仓库不存在 或 key 没登记成功 | 先在网页建仓；`ssh -T` 确认认证 |
| `Please tell me who you are` | 缺 git 身份 | 配 `user.name` / `user.email` |
| `file is 26.03 MB; this exceeds GitHub's file size limit` | 单文件 > 100MB | 移出索引或上 LFS |

## 事后核对

```bash
git rev-parse HEAD
git rev-parse origin/main      # 两者应相同
git status -sb                 # ## main...origin/main，无 ahead/behind
git ls-remote --heads origin
```
