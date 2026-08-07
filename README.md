# Daily News

一个轻量的 Docker 新闻聚合网页：从 WSJ、华尔街日报中文网、The Washington Post、BBC、The Economist、联合早报和 Financial Times 获取每家最多 10 条新闻，展示标题、图片、公开摘要和原文链接。

## 启动

```bash
docker compose up -d --build
```

浏览器打开 <http://localhost:8000>。首次启动会在后台抓取新闻；页面右上角可以手动更新。

## 定时更新

默认每天 `08:00`（`America/Vancouver`）更新。复制环境变量示例后可调整：

```bash
cp .env.example .env
```

- `TIMEZONE`: IANA 时区，例如 `Asia/Shanghai`
- `UPDATE_HOUR`: 0–23
- `UPDATE_MINUTE`: 0–59

数据保存在 Docker volume `news-data` 中，容器重启后不会丢失。

## 实现说明

- 优先读取出版商的 RSS/公开 feed，不足 10 条时回退到首页公开链接。
- 不绕过登录或付费墙。若来源限制访问，页面会显示错误提示，已缓存内容仍可保留。
- 摘要来自 feed 的公开 description/content，进行纯文本清理和截断；不是全文转载，也不使用外部 AI API。
- 为避免重复的定时任务和 SQLite 写入冲突，容器固定使用一个 Uvicorn worker。

## 本地开发与测试

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
DATABASE_PATH=/tmp/daily-news.db uvicorn app.main:app --reload
pytest
```

## API

- `POST /api/update`：开始后台更新
- `GET /api/status`：查看更新状态
- `GET /health`：容器健康检查

## 合规提示

请仅用于个人阅读，并遵守各媒体的服务条款、robots 规则和版权要求。内容版权归原出版商所有。
