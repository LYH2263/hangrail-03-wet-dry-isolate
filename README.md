# HangRail

干洗挂衣杆：按衣长一维 First-Fit 上杆，取件释放，逾期扫描。

## 干湿隔离

- 工单带干湿属性（干衣 `dry` / 湿衣 `wet`），工单页可维护；已上杆工单锁定不可改。
- 已挂某杆的衣物若存在相反干湿属性，该杆不得再挂另一属性的新衣——即使衣长空隙足够；自动上杆会改扫其它杆，指定杆时明确拒绝并提示"干湿隔离冲突"。
- 同属性衣物仍按 First-Fit 填补空隙。
- 未标注属性的历史工单按干衣兼容。
- 占位图每杆标注当前干湿集合（干衣/湿衣/空杆），分段按干湿着色。

## 启动

```bash
docker compose up --build
```

| 服务 | 地址 |
| --- | --- |
| 前端 | http://localhost:4400 |
| API | http://localhost:9400 |
| API 文档 | http://localhost:9400/docs |
| Postgres | localhost:5445 |

健康检查：`GET http://localhost:9400/api/health`

## 页面

- `/stores` — 门店
- `/rails` — 挂杆
- `/orders` — 工单
- `/occupancy` — 占位图
- `/pickup` — 取件
- `/overdue` — 逾期

## 使用说明

1. 查看门店挂杆长度。
2. 工单上杆按衣长 First-Fit 占位。
3. 占位图为横向尺线；取件释放；逾期页扫描清退。

## 开发与测试

```bash
docker compose exec api pytest -q
```
