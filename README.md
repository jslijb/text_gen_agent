# text_gen_agent

AI 小说生成 + AI 竖屏短视频生产的全栈工作台。

一条链路打通「**多智能体写小说 → 去 AI 化 → 爆款知识库检索 → 分章自动发布 → 成片级 AI 视频**」，人在环里只做创意和终审。

## 能力

| 模块 | 说明 |
|---|---|
| **多智能体写作** | `planner / writer / reviewer / reviser` 四个 Agent 协作产出章节，含自我修正 |
| **去 AI 化** | `services/humanizer.py`：多轮 Best-of-N 候选 + reviewer 评分择优 |
| **多模型额度自动切换** | `config/models.yaml` 声明模型与角色，单模型额度耗尽（403）自动切下一个，热加载不重启 |
| **爆款知识库（RAG）** | Chroma + `bge-large-zh` 向量检索；内置 Playwright 抓取平台爆款小说、支持人工维护与过期内容清理 |
| **分章自动日更** | Celery beat 定时任务：首次可批量产章，之后每天增量 2-3 章，配置热生效 |
| **封面生成** | Pillow 中文叠字 + 图像模型出图（中文文字交给 Pillow 保证可靠） |
| **AI 漫剧视频流水线** | 独立模块见 [`kuaishou-ai-comic-pipeline/`](kuaishou-ai-comic-pipeline/)：分镜表驱动，首帧图 → 视频段 → TTS 配音 → ffmpeg 合成 |
| **外部抓取（sieve）** | `app/services/sieve_client.py` + `/api/v1/sieve/*`：自然语言指令抓公开页面， Celery 异步轮询，产物落 `data/sieve/`。未配置 `SIEVE_API_KEY` 时整体关闭，不影响其它功能 |

## 架构

```
Next.js (3000)  ──HTTP──▶  FastAPI (8000)
                              │
                              ├─ PostgreSQL    业务数据
                              ├─ Redis         Celery broker / 结果
                              ├─ Celery worker 生成任务
                              ├─ Celery beat   日更调度
                              └─ Chroma + bge-large-zh   爆款知识库检索
```

四个容器：`ai_novel_backend` / `ai_novel_worker` / `ai_novel_beat` / `ai_novel_frontend`。

## 技术栈

- **后端**: FastAPI + Uvicorn (Python 3.11)
- **前端**: Next.js + Turbopack
- **数据库**: PostgreSQL 16（共享容器 ai_novel_postgres）
- **缓存/队列**: Redis 7（共享容器 ai_novel_redis）
- **异步任务**: Celery Worker + Beat
- **AI模型**: Agnes 第一优先级（文本/图像/视频，免费无配额），百炼兜底 —— 清单见 `docs/models.md`
- **向量库**: ChromaDB（RAG 知识库）
- **Python 环境**: 宿主机统一用 conda `bigmodel`（Python 3.11，本机运行任何 python/pytest/脚本前先 `conda activate bigmodel`，Windows 下建议加 `-X utf8`）；容器内 Python 由镜像自带，不依赖 conda

## 目录结构

```
backend/                 FastAPI 服务
  app/agents/            多智能体（planner / writer / reviewer / reviser）
  app/api/               接口层（章节、封面、发布、知识库、视频）
  app/services/          业务服务（humanizer、封面、视频生成等）
  app/tasks/             Celery 任务
  app/config/            配置与提示词
  alembic/               数据库迁移
  tests/                 端到端测试与报告
config/models.yaml       模型与角色配置（多模型额度切换）
frontend/                Next.js 前端
kuaishou-ai-comic-pipeline/  AI 漫剧视频流水线（可独立运行）
docs/                    项目文档（见文末「文档索引」）
```

## 关键配置

| 配置 | 位置 | 说明 |
|---|---|---|
| 模型配置 | `config/models.yaml` | bind mount 到容器，修改后自动检测重载 |
| 后端环境变量 | `backend/.env` | **唯一密钥载体**，不进 git/日志；`.env.example` 有占位；**改后需重建容器**（见 CLAUDE.md 纪律 2） |
| Docker Compose | `docker-compose.yml` | 四容器编排 |
| PostgreSQL 数据卷 | `ai_novel_pg_data` | 共享数据卷 |
| SDD 文档 | `.opencode/specs/ai_novel/` | 规格驱动开发文档 |
| 文档目录 | `docs/` | 架构细节与踩坑记录 |

## 快速开始

```bash
# 1. 准备凭据（文件不入库）
cp backend/.env.example backend/.env   # 无示例文件时手动新建
# 需填写：DATABASE_URL / REDIS_URL / CELERY_* / COOKIE_ENCRYPTION_KEY
#         DASHSCOPE_API_KEY1（阿里云百炼）/ AGNES_KEY（图像与免费视频兜底）
#         SIEVE_API_KEY（外部抓取，可选：python backend/scripts/sieve_device_login.py 获取）

# 2. 确保 Docker Desktop 运行；启动共享 PG/Redis（如果未运行）
docker start ai_novel_postgres ai_novel_redis

# 3. 起服务
cd D:\Python\text_gen_agent
docker compose up -d

# 4. 访问
#    前端 http://localhost:3000
#    接口文档 http://localhost:8000/docs
```

> 本机跑流水线脚本（如 `_make_hundun_video.py`）或 pytest：先 `conda activate bigmodel`，用 `python -X utf8` 运行；ffmpeg 无需单独安装，脚本内通过 `imageio_ffmpeg.get_ffmpeg_exe()` 取用。
> Agent 的部署/改动纪律（改后端必 rebuild、改 .env 必重建容器等）见 [`CLAUDE.md`](CLAUDE.md)。

## 文档索引

| 文档 | 内容 |
|---|---|
| [`CLAUDE.md`](CLAUDE.md) | **Agent 约束手册**：部署/改动纪律 + 快手物料规则（只放约束，不放事实） |
| [`DEPLOYMENT.md`](DEPLOYMENT.md) | 部署说明 |
| `docs/models.md` | 模型清单与角色挂载、Agnes 双端点×key 配对、百炼/Token Plan 状态、密钥使用规则 |
| `docs/platforms.md` | 多平台架构（百度/番茄：频道、品类、书名规则）、百度分发标题 |
| `docs/novel-pipeline.md` | 连载链路机制 + v2.1/v2.2 两轮 18 条修复记录、关键代码位置 |
| `docs/humanizer.md` | 去 AI 味 v2.3：禁用正则、10 维评分、平台节奏、实测效果 |
| `docs/pitfalls.md` | 踩坑记录 15 条全文（Docker/LLM/API/ffmpeg 合成/Agnes） |
| `docs/works-log.md` | 小说项目状态、《无字碑》、历史视频生成记录 |
| `docs/sieve.md` | sieve 抓取集成：密钥获取、三条硬规则、结果解读、排障 |
| `docs/AI漫剧视频调研报告.md` / `docs/去AI味技术原理.md` | 专题调研 |
| `快手视频生产经验清单.md` | 快手连载：生产规格 + 生产前数据采集纪律（§四纪律 8）+ 假设裁决 |
| `发布指南.md` | 快手连载：发布物料唯一台账 |
| `快手作品数据.xlsx` | 快手连载：五维数据台账（明细/画像/快照） |
| `快手AI漫剧生成方法总结.md` | 视频流水线方法论 |
| `快手AI漫剧短剧对标账号调研报告.md` | 赛道与对标分析 |
| `AI小说生成工具调研报告.md` | 写作工具选型 |
| `research_report_ai_dedetection.md` | AI 文本检测与去 AI 化调研 |

## 合规

AI 生成的视频与图文内容均按《人工智能生成合成内容标识办法》添加标识（画面显式角标 + 文件元数据隐式标识 + 发布平台声明）。模型 API 凭据仅通过环境变量注入，不落盘、不入库。
