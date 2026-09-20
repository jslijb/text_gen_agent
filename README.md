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
docs/                    项目文档
```

## 快速开始

```bash
# 1. 准备凭据（文件不入库）
cp backend/.env.example backend/.env   # 无示例文件时手动新建
# 需填写：DATABASE_URL / REDIS_URL / CELERY_* / COOKIE_ENCRYPTION_KEY
#         DASHSCOPE_API_KEY1（阿里云百炼）/ AGNES_KEY（图像与免费视频兜底）

# 2. 起服务（PostgreSQL 与 Redis 用外部共享容器）
docker compose up -d

# 3. 访问
#    前端 http://localhost:3000
#    接口文档 http://localhost:8000/docs
```

## 相关文档

- [`CLAUDE.md`](CLAUDE.md) — 项目开发约定
- [`DEPLOYMENT.md`](DEPLOYMENT.md) — 部署说明
- [`快手AI漫剧生成方法总结.md`](快手AI漫剧生成方法总结.md) — 视频流水线方法论
- [`快手AI漫剧短剧对标账号调研报告.md`](快手AI漫剧短剧对标账号调研报告.md) — 赛道与对标分析
- [`AI小说生成工具调研报告.md`](AI小说生成工具调研报告.md) — 写作工具选型
- [`research_report_ai_dedetection.md`](research_report_ai_dedetection.md) — AI 文本检测与去 AI 化调研

## 合规

AI 生成的视频与图文内容均按《人工智能生成合成内容标识办法》添加标识（画面显式角标 + 文件元数据隐式标识 + 发布平台声明）。模型 API 凭据仅通过环境变量注入，不落盘、不入库。
