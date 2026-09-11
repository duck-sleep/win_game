---
name: api-endpoint-slow-diagnosis
description: 诊断某个 API/AI 服务端点"变慢、超时、连接被重置"（如 10054 / 500 / 429）到底是本机网络、代理劫持还是服务端问题。当用户报"回答慢""接口超时""WebSocket error""ConnectionReset"并给出域名或 URL 时使用。
agent_created: true
---

# API 端点慢 / 断连 诊断五步法

目标：**先定性（谁的锅），再给建议**。不要一上来就说"重启试试"。

## 第 0 步：最后一公里（无线侧）—— 最常被漏掉的真凶

> 真实案例：用户报"手机热点快、家里 WiFi 慢"，前五步全查完都正常，
> 最后发现是电脑连在 **2.4GHz 信道 1（802.11n）** 上，而网卡本身支持 Wi-Fi 6 / 5GHz。
> 2.4G 干扰 → 延迟抖动 + 重传 → 长连接流式传输最受伤。**先查这一步能省半小时。**

```bash
netsh wlan show interfaces 2>&1 | iconv -f GBK -t UTF-8 | grep -aE "SSID|信号|信道|无线电|速率"
netsh wlan show drivers 2>&1 | iconv -f GBK -t UTF-8 | grep -aE "驱动程序|支持的无线电"
netsh wlan show networks mode=bssid 2>&1 | iconv -f GBK -t UTF-8 | grep -aE "SSID|信道|信号"
```

判据（**信号满格 ≠ 链路健康**）：

| 观察项 | 健康 | 有问题 |
|---|---|---|
| 无线电类型 | 802.11ac / ax | **802.11n / b / g**（说明在 2.4G） |
| 信道 | 36/44/149...（5G）或 2.4G 的 6/11 | **信道 1**（2.4G 默认最挤） |
| 信号 vs 速率 | 信号高 + 速率高 | **信号 98% 但速率仅几十 Mbps** → 干扰严重 |
| 网关 ping | 平均 <5ms | 平均 >20ms 或有丢包 → 无线侧抖动 |

配套验证：`ping -n 30 <网关IP>`，丢包 0% 但平均延迟 >20ms 就是无线侧抖动。

**修法优先级**：① 连 5GHz SSID（路由器后台确认 5G 是否开启/被隐藏）
② 路由器改 2.4G 信道到 6 或 11 ③ 网线直连 ④ 换支持 5G 的网卡。

## 第 1 步：DNS 定性 —— 先搞清楚它落在哪

```bash
nslookup <域名>
```

看 CNAME 和 IP，判断机房位置：
- 国内（阿里云/腾讯云/华为云 IP）→ 本该直连，若绕境外就是代理规则错了
- 境外 → 慢是常态，重点查代理节点质量

判据：**DNS 解析不出来** = 本机 DNS 或代理 DNS 有问题；**能解析** = 继续第 2 步。

## 第 2 步：分层计时 —— 定位卡在哪一跳

```bash
curl --noproxy '*' -s -o /dev/null \
  -w "connect=%{time_connect}s tls=%{time_appconnect}s total=%{time_total}s http=%{http_code}\n" \
  --max-time 25 -X POST <url> -H "Content-Type: application/json" -d '{}'
```

- `time_connect` 大 → 网络/路由问题
- `time_appconnect` 大 → TLS 握手慢（中间设备多或被劫持）
- 两个都小而 `time_total` 大 → **服务端处理慢**（对方锅）

## 第 3 步：逐个后端 IP 测 —— 揪出挂掉的那台

ALB/CDN 常有多个后端 IP，一个挂了就表现为"时好时坏"：

```bash
for ip in <IP1> <IP2>; do
  for i in 1 2 3; do
    curl --noproxy '*' --resolve "<域名>:443:$ip" -s -o /dev/null \
      -w "  $ip 第${i}次: %{time_total}s http=%{http_code}\n" --max-time 30 \
      -X POST https://<域名>/<path> -H "Content-Type: application/json" -d '{}'
  done
done
```

## 第 4 步：抽样统计 —— 看错误码分布（最关键）

```bash
for i in $(seq 1 10); do
  curl --noproxy '*' -s -o /dev/null -w "  %2d: http=%{http_code} %{time_total}s\n" $i \
    --max-time 30 -X POST <url> -H "Content-Type: application/json" -d '{}'
done
```

⚠️ **自限流警告**：连续打 10~20 次可能把自己打成 429，测完立刻停手，不要为了"再确认一次"反复压。

### 错误码判读表

| 现象 | 谁的问题 | 说明 |
|---|---|---|
| 401 / 403 | 都不是 | 链路完全正常，只是没带凭证 —— 说明网络没问题 |
| **429** | 服务端容量 | 限流，请求在排队 → 表现为"慢"；推重试会让限流窗口更长 |
| **500 + 连接重置** | 服务端过载 | 网关扛不住时直接掐连接，Windows 上报 10054 |
| connect 超时 / 无响应 | 本机或中间件 | 回第 2 步看是哪一跳 |
| 全部超时但 DNS 正常 | 代理劫持 | 查第 5 步 |

### 两个已验证的"假象"，别当真

1. **云厂商对 ICMP 限速**：阿里云 ALB/云盾常限制 ping，表现为目标 IP "丢包 10~15%"，
   但 TCP 连接耗时稳定在几十毫秒、首字节正常 → **TCP 层并没有丢**。
   判据：ping 丢包但 `time_connect` 不抖动 = 假丢包。**以 TCP 分层计时为准，不要以 ping 为准。**
2. **Python `ssl` 握手假慢**：Python 默认证书验证可能耗时 2.3s（稳定不抖动），
   而 curl 实测同一目标只要 150ms。测 TLS 耗时优先用 curl 的 `time_appconnect`，
   或用 `netcheck.py` 这类脚本时标明是含证书验证的总耗时。

### 长连接空闲存活测试（判断 NAT / 服务端谁掐连接）

10054 "远程主机强迫关闭" 常发生在 AI 流式回答的思考静默期。直接复现：

```python
# 见 23_网络诊断/idle_conn_test.py：建连 -> 空闲 N 秒 -> 再发请求看是否还活着
python idle_conn_test.py 30 --host www.baidu.com   # 对照组
```

**必须有对照**：目标死了但百度活着 → 目标服务端/链路问题；
两者都死 → 本地 NAT 会话回收（查路由器是否双层 NAT：`tracert` 第二跳仍是 192.168.x.x）。

## 第 5 步：排查代理劫持（这台机器的特色坑）

```bash
env | grep -i proxy                 # 看代理变量
tasklist | grep -iE "clash|mihomo|verge|tun"
ipconfig | grep -iE "TUN|TAP|clash|mihomo"   # TUN 虚拟网卡在不在
netstat -ano | grep ":<代理端口>"    # 再用 tasklist /FI "PID eq <pid>" 查是谁
```

- 代理端口若是 **sandbox-cli.exe** → 是 WorkBuddy 自带沙箱代理，不是 Clash，别误伤
- **开了 TUN/全局代理 + 目标域名是国内 IP** → 流量绕境外再回来，必慢易断，给该域名加直连规则
- 用户在深圳/香港两地跑：香港出口走国际线路访问国内端点会明显更差

## 输出要求

给结论时讲清三件事：
1. **谁的锅**（本机网络 / 代理规则 / 服务端），附证据（哪个命令、什么数字）
2. **为什么会"慢"**（排队限流 / 绕路 / 后端挂）
3. **用户能做什么**（等限流窗口 / 加直连规则 / 避开高峰 / 反馈官方），做不到的也要说明（如端点由服务端下发、本地改不了）

## 诚实原则

如果探测本身可能干扰了结果（比如连续压测打出 429），**必须主动说明**，不要把锅全推给服务端。
