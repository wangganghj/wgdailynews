# Daily News

一个轻量的 Docker 新闻聚合网页：聚合 WSJ、The Washington Post、The Economist、Financial Times、The New York Times、BBC 和联合早报。

## 启动

```bash
docker compose up -d --build
```

浏览器打开 <http://localhost:8000>。首次启动会在后台抓取新闻；页面右上角可以手动更新。

## VPS 部署

仓库的 GitHub Actions 会为 `main` 分支自动构建 `linux/amd64` 和 `linux/arm64` 镜像并发布至：

```text
ghcr.io/wangganghj/wgdailynews:latest
```

在 VPS 上只需复制 `compose.yaml` 和可选的 `.env`，然后执行：

```bash
docker compose pull
docker compose up -d
```

更新到最新版本：

```bash
docker compose pull && docker compose up -d
```

如果 GHCR package 不是公开状态，需要先执行 `docker login ghcr.io`，或在仓库 Package settings 中将其改为 Public。`compose.yaml` 也允许用 `NEWS_IMAGE` 覆盖镜像地址。

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

- WSJ、Washington Post、Economist、FT 和纽约时报使用 Chromium 生成首页截图，并在截图右侧列出新闻标题。
- BBC 使用 RSS，联合早报直接读取首页；这两个来源保留图片卡片模式并显示在页面最下方。
- 每条新闻显示原标题、原摘要及对应的简体中文翻译；手动更新会显示抓取、图片补全、翻译和缓存阶段。
- 默认使用 Google 翻译。设置 `TRANSLATION_PROVIDER=openai` 和 `OPENAI_API_KEY` 可使用 OpenAI 获得更好的新闻语境翻译。
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
