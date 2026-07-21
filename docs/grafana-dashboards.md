# Grafana 仪表盘 & LogQL 速查

## 一键导入仪表盘

把下面 JSON 粘贴到 Grafana → Dashboards → Import：

```json
{
  "title": "Suwayomi Upscaler",
  "tags": ["suwayomi", "upscaler"],
  "refresh": "30s",
  "panels": [
    {
      "title": "超分速率 (页/分钟)",
      "type": "timeseries",
      "targets": [{
        "expr": "rate({filename=~\".*app.jsonl\"} | json | status=\"ok\" [5m]) * 60"
      }]
    },
    {
      "title": "失败率",
      "type": "stat",
      "targets": [{
        "expr": "sum(rate({filename=~\".*app.jsonl\"} | json | status=\"fail\" [1h])) / sum(rate({filename=~\".*app.jsonl\"} | json [1h])) * 100"
      }],
      "fieldConfig": { "defaults": { "unit": "percent", "decimals": 1 } }
    },
    {
      "title": "耗时分布 (P50/P95/P99)",
      "type": "timeseries",
      "targets": [
        { "expr": "quantile_over_time(0.50, {filename=~\".*app.jsonl\"} | json | unwrap elapsed [$__interval])", "legend": "P50" },
        { "expr": "quantile_over_time(0.95, {filename=~\".*app.jsonl\"} | json | unwrap elapsed [$__interval])", "legend": "P95" },
        { "expr": "quantile_over_time(0.99, {filename=~\".*app.jsonl\"} | json | unwrap elapsed [$__interval])", "legend": "P99" }
      ],
      "fieldConfig": { "defaults": { "unit": "s" } }
    },
    {
      "title": "平均耗时 (按输出尺寸)",
      "type": "timeseries",
      "targets": [
        { "expr": "avg_over_time({filename=~\".*app.jsonl\"} | json | size_out_mb < 2 | unwrap elapsed [$__interval])", "legend": "输出 < 2MB" },
        { "expr": "avg_over_time({filename=~\".*app.jsonl\"} | json | size_out_mb >= 2 | size_out_mb < 5 | unwrap elapsed [$__interval])", "legend": "输出 2-5MB" },
        { "expr": "avg_over_time({filename=~\".*app.jsonl\"} | json | size_out_mb >= 5 | unwrap elapsed [$__interval])", "legend": "输出 ≥ 5MB" }
      ],
      "fieldConfig": { "defaults": { "unit": "s" } }
    },
    {
      "title": "原图 vs 超分尺寸分布",
      "type": "bargauge",
      "targets": [
        { "expr": "avg_over_time({filename=~\".*app.jsonl\"} | json | unwrap size_in_mb [$__interval])", "legend": "原图 MB" },
        { "expr": "avg_over_time({filename=~\".*app.jsonl\"} | json | unwrap size_out_mb [$__interval])", "legend": "超分 MB" },
        { "expr": "avg_over_time({filename=~\".*app.jsonl\"} | json | unwrap ratio [$__interval])", "legend": "放大倍数" }
      ]
    },
    {
      "title": "今日超分总计",
      "type": "stat",
      "targets": [{
        "expr": "count_over_time({filename=~\".*app.jsonl\"} | json | status=\"ok\" [24h])"
      }]
    },
    {
      "title": "实时日志流 (最后 20 条)",
      "type": "logs",
      "targets": [{
        "expr": "{filename=~\".*app.jsonl\"} | json | line_format \"{{.msg}}  {{.in_w}}x{{.in_h}}→{{.out_w}}x{{.out_h}}  {{.size_in_mb}}→{{.size_out_mb}}MB  {{.elapsed}}s\""
      }],
      "options": { "showTime": true, "sortOrder": "Descending" }
    },
    {
      "title": "nginx 状态码 (5 分钟)",
      "type": "piechart",
      "targets": [{
        "expr": "sum by(status) (count_over_time({app=\"nginx\"} | pattern `<remote> - <user> [<ts>] \"<method> <path> <_>\" <status> <size> <_> <_>` [5m]))"
      }],
      "description": "Suwayomi 访问状态码分布"
    }
  ]
}
```

## 独立 LogQL 查询

### 性能分析

```logql
# Top 10 最慢超分
{filename=~".*app.jsonl"} | json | status="ok"
| line_format "{{.in_w}}x{{.in_h}} → {{.out_w}}x{{.out_h}}  {{.size_in_mb}}→{{.size_out_mb}}MB  {{.elapsed}}s  {{.url}}"
| unwrap elapsed | sort by _value desc
| limit 10

# 超出 30s 的异常超分
{filename=~".*app.jsonl"} | json | elapsed > 30

# 每小时超分吞吐量
sum(count_over_time({filename=~".*app.jsonl"} | json | status="ok" [1h]))

# 按引擎分组统计
sum by(engine) (count_over_time({filename=~".*app.jsonl"} | json [24h]))

# 平均放大倍数
avg_over_time({filename=~".*app.jsonl"} | json | unwrap ratio [24h])
```

### 故障排查

```logql
# 所有失败
{filename=~".*app.jsonl"} | json | status="fail"

# nginx 5xx (含超时)
{app="nginx"} |= "status" | pattern `<_> <_> [<_>] \"<_> <_> <_>\" <status> <_>` | status >= 500

# 某 Manga 全链路追踪
{app=~"nginx|upscaler"} |~ "manga/7777/chapter/4"
```

### 今日摘要

```logql
# 成功数 / 失败数
count_over_time({filename=~".*app.jsonl"} | json | status="ok" [24h])

count_over_time({filename=~".*app.jsonl"} | json | status="fail" [24h])

# 平均耗时
avg_over_time({filename=~".*app.jsonl"} | json | unwrap elapsed [24h])

# 最大输出文件
{filename=~".*app.jsonl"} | json | status="ok"
| line_format "{{.size_out_mb}}MB  {{.out_w}}x{{.out_h}}"
| unwrap size_out_mb | sort by _value desc
| limit 5
```
