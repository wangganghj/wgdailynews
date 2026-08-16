# Daily News · 今日全球新闻聚合与 AI 速读

一个轻量、现代化、智能化的 Docker 新闻聚合与早报平台：
- **主流大报封面与头条**：WSJ、The Washington Post、The Economist、Financial Times、The New York Times、The Globe and Mail、The Vancouver Sun。
- **全球综合与财经资讯**：BBC、联合早报、Reuters（路透社）、Bloomberg（彭博社）、Nikkei Asia（日经亚洲）、TechCrunch 与 Hacker News。
- **AI 智能速读（Daily AI Briefing）**：基于 Gemini / OpenAI 大模型聚合全网 Top 5 核心热点快讯与宏观综述。
- **现代化 UI / UX**：支持深色/浅色双色温主题、全局即时搜索与高亮、分类标签筛选、稍后阅读收藏夹、字号调节与 Web Speech 语音朗读（TTS）。
- **自动化推送**：更新完成后支持一键推送每日早报到 Telegram 频道或 Webhook（飞书/企业微信/Discord）。

---

## 🚀 启动与部署

### 1. Docker Compose 极速启动

```bash
docker compose up -d --build
```

浏览器打开 <http://localhost:8000>。首次启动会自动在后台抓取新闻，页面右上角亦可点击「立即更新」。

---

### 2. VPS 生产部署

仓库的 GitHub Actions 会为 `main` 分支自动构建 `linux/amd64` 和 `linux/arm64` 镜像并发布至：

```text
ghcr.io/wangganghj/wgdailynews:latest
```

在 VPS 上只需准备 `compose.yaml` 和可选的 `.env`，然后执行：

```bash
docker compose pull
docker compose up -d
```

---

## ⚙️ 环境变量与个性化配置

复制环境变量示例文件进行配置：

```bash
cp .env.example .env
```

| 环境变量 | 默认值 | 说明 |
| :--- | :--- | :--- |
| `TIMEZONE` | `America/Vancouver` | IANA 时区（如 `Asia/Shanghai`） |
| `UPDATE_HOUR` | `8` | 每天定时更新小时（0–23） |
| `UPDATE_MINUTE` | `0` | 每天定时更新分钟（0–59） |
| `TRANSLATION_PROVIDER`| `google` | 翻译引擎：`google`（免 Key）、`gemini`、`openai`、`deepl` |
| `GEMINI_API_KEY` | - | Google Gemini API Key（推荐用于高品质翻译与 AI 早报） |
| `GEMINI_MODEL` | `gemini-2.5-flash` | Gemini 模型名称 |
| `OPENAI_API_KEY` | - | OpenAI API Key |
| `OPENAI_MODEL` | `gpt-4o-mini` | OpenAI 模型名称 |
| `DEEPL_API_KEY` | - | DeepL 翻译 API Key |
| `ENABLE_AI_BRIEFING` | `true` | 是否启用每日 AI 智能简报 |
| `TELEGRAM_BOT_TOKEN` | - | Telegram Bot Token（用于早报推送） |
| `TELEGRAM_CHAT_ID` | - | Telegram 目标 Chat/Channel ID |
| `WEBHOOK_URL` | - | 自定义 Webhook 推送地址（Discord/飞书/企业微信） |

---

## ✨ 核心功能与亮点

1. **AI 智能速读卡片**：顶部生成结构化每日热点，支持一键语音播报（听早报）、一键复制 Markdown 格式。
2. **即时全局搜索**：支持中英文关键词毫秒级过滤，高亮匹配内容。
3. **分类快速导航**：支持按「全部来源」、「全球时政」、「财经商业」、「科技前沿」、「亚太要闻」过滤。
4. **稍后阅读 / 收藏夹**：点击文章卡片右上角 ⭐ 即可加入收藏夹，支持导出链接与本地持久化。
5. **深色/浅色双色温主题**：支持夜间模式与白天模式无缝切换。
6. **Web Speech API 语音朗读**：支持在浏览器中一键朗读任意文章摘要或今日早报。

---

## 💻 本地开发与测试

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
DATABASE_PATH=/tmp/daily-news.db uvicorn app.main:app --reload
pytest
```

---

## 📡 API 接口

- `GET /`：新闻仪表盘首页
- `GET /api/status`：查看当前更新状态与实时进度
- `POST /api/update`：手动触发后台全量更新
- `GET /api/briefing`：获取最新一份 AI 每日早报数据
- `POST /api/briefing/generate`：手动重新生成 AI 早报
- `POST /api/notify`：手动触发 Telegram / Webhook 早报推送
- `GET /health`：健康检查接口

---

## ⚖️ 合规与免责提示

本项目仅供个人学习与日常阅读使用，严格遵守各媒体公开 robots 规则与服务条款，不绕过付费墙。所有内容版权归原出版商所有。
