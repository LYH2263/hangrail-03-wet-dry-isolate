# HangRail

干洗挂衣杆：按衣长一维 First-Fit 上杆，取件释放，逾期扫描。

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
3. **干湿同杆隔离**：每根杆只允许一种干湿属性；已挂相反属性时即使空隙足够也拒绝上杆（HTTP 409 `isolation_conflict`），自动改扫其它杆。未标注属性的历史工单按干衣兼容。
4. 工单页可维护干湿（干衣/湿衣）；占位图展示每杆当前干湿集合（干衣杆/湿衣杆徽标与分段配色）；取件释放；逾期页扫描清退。

## 开发与测试

```bash
docker compose exec api pytest -q
```
