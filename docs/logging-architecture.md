# Suwayomi Upscaler — 日志架构与部署指南

> 2026-07-21 | commit `095e39c`

## 架构

```
 Mac (upscaler)                       Debian (nginx + Suwayomi)
 ┌──────────────────────┐             ┌─────────────────────────────┐
 │                      │             │                             │
 │  Brother             │             │  Docker: nginx:443          │
 │  → 192.68.1.90:8765  │             │    → /api/v1/manga/*        │
 │                      │             │      ┌─ primary: Mac:8765   │
 │  logs/access.log     │             │      └─ backup: Suwayomi    │
 │  logs/error.log      │             │                             │
 │  logs/app.jsonl  ◄───┼─ Promtail ──┤  Suwayomi:4567             │
 │  cache/audit.jsonl  ◄┼─ Promtail ──┤    → /app/suwayomi/...     │
 │                      │             │                             │
 └──────────────────────┘             │  /var/log/nginx-suwayomi/   │
                                       │    suwayomi_access.log      │
                                       │    error.log                │
                                       └──────────┬──────────────────┘
                                                  │
                  ┌───────────────────────────────┘
                  │    Promtail (debian) :9080
                  │
                  ▼
           ┌────────────┐
           │    Loki    │  Debian Docker
           │    :3100   │
           └─────┬──────┘
                 │
                 ▼
           ┌────────────┐
           │  Grafana   │  你已有的服务器
           │   :3000    │
           └────────────┘
```

## 日志文件

### upscaler (Mac)

| 文件 | 格式 | 内容 |
|------|------|------|
| `logs/access.log` | 标准 combined | gunicorn HTTP 请求 |
| `logs/error.log` | gunicorn 时间戳 | 启动/关闭/worker 状态 |
| `logs/app.jsonl` | JSON 一行一个 | 超分操作的结构化日志 |
| `cache/audit.jsonl` | JSON 一行一个 | 每次超分的审计记录 |

### app.jsonl 字段

```json
{
  "ts": "2026-07-21T14:28:40.595928+00:00",
  "level": "INFO",
  "app": "upscaler",
  "msg": "🎨 Upscaling",
  "status": "upscale_start",
  "url": "download:xxx.png",
  "engine": "realcugan",
  "in_w": 600,
  "in_h": 900,
  "size_in_mb": 0.01
}
```

超分完成时额外字段：

```json
{
  "msg": "✅ Upscale complete",
  "status": "ok",
  "out_w": 1200,
  "out_h": 1800,
  "size_out_mb": 1.96,
  "ratio": 370.1,
  "elapsed": 1.38
}
```

### access.log（gunicorn JSON 格式）

```json
{"ts":"[21/Jul/2026:22:28:41 +0800]","app":"upscaler","stream":"access","method":"POST","path":"/convert","query":"","status":"200","size":2055687,"referer":"-","ua":"curl/8.7.1","remote":"127.0.0.1","duration_us":1234567}
```

## 部署步骤

### 1. Loki（Debian Docker）

```bash
docker run -d \
  --name loki \
  --restart unless-stopped \
  -p 3100:3100 \
  grafana/loki:latest
```

### 2. Mac Promtail

```bash
brew install promtail
# 或下载二进制: https://github.com/grafana/loki/releases

# 编辑 config/promtail-mac.yml，把 <LOKI_HOST> 替换为 Loki 的地址
# 然后启动:
promtail --config.file ~/tools/suwayomi-upscaler/config/promtail-mac.yml

# 作为 LaunchAgent 开机启动:
cat > ~/Library/LaunchAgents/com.suwayomi.promtail.plist << 'PLIST'
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>com.suwayomi.promtail</string>
    <key>ProgramArguments</key>
    <array>
        <string>/opt/homebrew/bin/promtail</string>
        <string>--config.file</string>
        <string>/Users/sasoribi/tools/suwayomi-upscaler/config/promtail-mac.yml</string>
    </array>
    <key>RunAtLoad</key>
    <true/>
    <key>KeepAlive</key>
    <true/>
    <key>StandardOutPath</key>
    <string>/Users/sasoribi/tools/suwayomi-upscaler/logs/promtail.log</string>
    <key>StandardErrorPath</key>
    <string>/Users/sasoribi/tools/suwayomi-upscaler/logs/promtail.log</string>
</dict>
</plist>
PLIST
launchctl load ~/Library/LaunchAgents/com.suwayomi.promtail.plist
```

### 3. Debian Promtail

```bash
# 下载 Promtail 二进制
cd /usr/local/bin
curl -LO https://github.com/grafana/loki/releases/download/v3.x.x/promtail-linux-amd64.zip
unzip promtail-linux-amd64.zip && chmod +x promtail-linux-amd64
mv promtail-linux-amd64 promtail

# 配置已放在 /home/sasoribi/docker/promtail-config.yml
# 编辑其中的 <LOKI_HOST> 为 Loki 地址

# systemd 服务
cat > /etc/systemd/system/promtail.service << 'UNIT'
[Unit]
Description=Promtail log collector
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
User=sasoribi
ExecStart=/usr/local/bin/promtail --config.file /home/sasoribi/docker/promtail-config.yml
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
UNIT

systemctl daemon-reload
systemctl enable --now promtail
```

### 4. Nginx 日志挂载（Debian，需重建容器）

```bash
# 创建宿主机日志目录
mkdir -p /home/sasoribi/docker/nginx-proxy/logs

# 重建 nginx 容器，添加 -v 挂载:
docker run -d \
  --name nginx-proxy \
  -v /home/sasoribi/docker/nginx-proxy/nginx.conf:/etc/nginx/nginx.conf:ro \
  -v /home/sasoribi/docker/nginx-proxy/cert:/etc/nginx/cert:ro \
  -v /home/sasoribi/docker/nginx-proxy/logs:/var/log/nginx \
  -p 80:80 -p 443:443 -p 8080:8080 \
  nginx:alpine
```

### 5. Suwayomi 日志落地

修改启动脚本，把 stdout/stderr 重定向到文件：

```bash
# suwayomi-server.sh 末尾改为:
exec ./jre/bin/java -jar ./bin/Suwayomi-Server.jar \
  >> /var/log/suwayomi/server.log 2>&1
```

### 6. Grafana 数据源

1. `Configuration → Data Sources → Add → Loki`
2. URL: `http://<DEBIAN_IP>:3100`
3. `Save & Test`

## 常用查询（LogQL）

### 超分操作

```logql
# 所有超分完成
{stream="app"} | json | status = "ok"

# 超分失败
{stream="app"} | json | status = "fail"

# 耗时超过 5 秒
{stream="app"} | json | status = "ok" | elapsed > 5

# 今日超分次数
count_over_time({stream="app"} | json | status = "ok" [24h])

# 平均耗时（今日）
avg_over_time({stream="app"} | json | status = "ok" | unwrap elapsed [24h])

# 输出超过 5MB 的大文件
{stream="app"} | json | size_out_mb > 5
```

### nginx

```logql
# 5xx 错误
{app="nginx"} |~ " [5][0-9][0-9] "

# 慢请求（> 10s）
{stream="access"} |~ "duration_us.*[0-9]{8}"

# 某个 Manga 的访问量
sum(count_over_time({app="nginx"} |~ "/manga/631/" [1h]))
```

### 跨应用追踪

```logql
# 某 Manga 某章节的所有日志（按时间排序）
{app=~"nginx|upscaler"} |~ "manga/631/chapter/11" |= "" 
```

### 仪表盘建议

| 面板 | 查询 |
|------|------|
| 超分速率 | `rate({stream="app"} | json | status = "ok" [5m])` |
| 失败率 | `rate({stream="app"} | json | status = "fail" [5m]) / rate({stream="app"} | json [5m])` |
| P50/P95/P99 耗时 | `quantile_over_time(0.5, {stream="app"} | json | unwrap elapsed [1h])` |
| 缓存命中率 | `rate({stream="app"} |~ "Cache hit" [5m])` |
| nginx 5xx | `rate({app="nginx"} \|~ " [5][0-9][0-9] " [5m])` |

## 配置文件

| 文件 | 位置 |
|------|------|
| promtail-mac.yml | `~/tools/suwayomi-upscaler/config/` |
| promtail-debian.yml | `/home/sasoribi/docker/promtail-config.yml` |

所有配置文件中的 `<LOKI_HOST>` 需要替换为你实际 Loki 服务的 IP 地址。
