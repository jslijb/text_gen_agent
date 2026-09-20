# AI小说生成系统 - 项目文档

## 快速启动

```powershell
# 1. 确保Docker Desktop运行
# 2. 启动共享PG/Redis（如果未运行）
docker start ai_novel_postgres ai_novel_redis
# 3. 启动ai_novel服务
cd D:\Python\text_gen_agent
docker compose up -d
# 4. 访问
# 前端: http://localhost:3000
# 后端API: http://localhost:8000/docs
```

## 技术栈

- **后端**: FastAPI + Uvicorn (Python 3.11)
- **前端**: Next.js + Turbopack
- **数据库**: PostgreSQL 16 (共享容器 ai_novel_postgres)
- **缓存/队列**: Redis 7 (共享容器 ai_novel_redis)
- **异步任务**: Celery Worker
- **AI模型**: 阿里百炼平台 (DASHSCOPE_API_KEY1)
- **向量库**: ChromaDB (RAG知识库)
- **conda环境**: bigmodel

## 关键配置

- 模型配置: `config/models.yaml` (bind mount到容器，修改后自动检测重载)
- 后端环境变量: `backend/.env`
- Docker Compose: `docker-compose.yml`
- PostgreSQL数据卷: `ai_novel_pg_data`
- SDD文档: `.opencode/specs/ai_novel/`

## 平台化：多平台支持（2026-09-14 新增）

**思路**：平台的差异（频道、品类、书名规则、节奏要求）集中在一处配置，不再散落在 API / 模型 / 前端各写一份。

**权威配置**：`backend/app/config/platforms.py`
一个平台一条记录 —— `channels`（频道）、`genres`（品类）、`title_prompt`（书名 prompt）、
`title_len`（字数区间）、`title_prefix`（前缀）、`humanizer_profile`（人化节奏档位）、
`publish_host`（发布域名，None 表示自动发布未实现）。新增平台只登记一条，各层按表渲染。

| key | 平台 | 频道 | 品类数 | 书名规则 | 自动发布 |
|-----|------|------|--------|----------|----------|
| `baidu` | 百度作家平台 | 男性向 / 女性向 / 无性向 | 12 | `故事：` 前缀，17-30 字 | ✅ 已实现 |
| `fanqie` | 番茄小说 | 女频 / 男频 | 14 | 无前缀，5-20 字，大白话「设定+冲突」两段式 | ❌ 未实现 |

番茄品类取自官方短故事「IP金品共创计划」聚焦的 14 类（男频脑洞 / 女频脑洞 / 悬疑惊悚 /
玄幻仙侠 / 青春虐恋 / 古言虐恋 / 历史古代 / 都市日常 / 宫斗宅斗 / 现言甜宠 / 古言甜宠 /
民国旧影 / 年代 / 女性成长）。**悬疑惊悚是跨频道品类，男女频均开放。**

**落地位置**
- `projects.platform` 列，默认 `baidu`（存量数据不受影响）；迁移脚本 `backend/migrations/2026-09-14_platform.sql`
- `gender` 列沿用，平台化后承载"频道"；`ck_project_gender` 约束放宽为「百度频道 ∪ 番茄频道」
- 创建/编辑校验统一走 `_validate_taxonomy()`（`api/projects.py`），三处（platform/gender/genre）联动校验
- 新接口 `GET /api/v1/projects/platforms` —— 返回各平台频道/品类/书名规则
- 书名 prompt 从 `api/projects.py` 上移到 `platforms.py`（百度、番茄各一份，不再有硬编码副本）
- 去 AI 化全程带平台：`humanize_chapter(chapter_id, strategy, platform)`，
  未显式传时按章节所属项目自动取；`recursive` 策略也已接入平台节奏底线

**前端**：`page.tsx` 与 `project/[id]/page.tsx` 各内置一份 `PLATFORM_META`，
新建/编辑表单可选平台，切换平台自动重置频道与品类，项目卡片显示平台标签。

⚠️ **前后端各有一份分类表**（后端 `platforms.py` / 前端 `PLATFORM_META`）。改分类时两边都要动；
若嫌麻烦，后续可改成从 `GET /projects/platforms` 拉取，前端只留渲染逻辑。

## 可用模型 (2026-09-14 全量更新)

### Agnes（`AGNES_KEY`，文本/图像/视频第一优先级，免费无配额）

> ⚠️ **Agnes 有两套互不通用的端点 + key 空间，`base_url` 必须与 key 配对，
> 不存在"绝对正确的那个域名"。**（2026-09-15 实测修正，此前此处说法是反的）
>
> | key | `https://api.agnes-ai.cn/v1` | `https://apihub.agnes-ai.com/v1` |
> |---|---|---|
> | `sk-CioO…4aZa`（`backend/.env` 当前值） | **200** | 401 `Invalid token` |
> | `sk-jY3Q…w6Hv` | 401「无效的令牌」 | **200** |
>
> **401 的正确读法是「这把 key 不属于这个域名」，不是 key 坏、也不是域名错。**
> 报错语言可作判断依据：`.cn` 回中文「无效的令牌」，`apihub` 回英文 `Invalid token`。
> 两套空间的**产物地址域名也不同**，且**跨空间查不到对方的任务**。
> 当前 `.env` 用的是 `.cn` 那把，故 `base_url = https://api.agnes-ai.cn/v1`。

> 📹 **视频链路补充（2026-09-15 实测）**：`agnes-video-2.5-flash` 可用且产物可下载，
> 建议用 `AGNES_BASE_URL` / `AGNES_VIDEO_MODEL` 环境变量覆盖。
> `agnes-video-v2.0` 的产物取件是坏的（返回 22 字节 `Not Found`），不要再用。
> 注意 Agnes 免费档**有 API 限流**（短时间连发 3 个请求即 429），需退避。
> 完整实测参数见 `.workbuddy/Agnes视频API实测手册.md`。

| 模型 | 角色 |
|------|------|
| agnes-3.0-flash | planner, writer, reviewer, reviser, humanizer, cover_planner, topic_generator, script_writer, shot_splitter |
| agnes-image-2.5-flash / agnes-image-2.1-flash / agnes-image-2.0-flash | image_generator |
| agnes-video-v2.0 / agnes-video-2.5 / agnes-video-2.5-flash | video_generator |

账号可用模型全量（`GET /v1/models` 实测 12 个）：
agnes-3.0-flash、agnes-2.5-pro、agnes-2.5-pro-alpha、agnes-2.5-pro-beta、agnes-2.5-flash、
agnes-2.0-flash、agnes-image-2.5-flash、agnes-image-2.1-flash、agnes-image-2.0-flash、
agnes-video-2.5、agnes-video-2.5-flash、agnes-video-v2.0

### 百炼（`DASHSCOPE_API_KEY1`，兜底）

> **glm-5.2 额度即将过期 —— 已放在各角色兜底序列的第一位（priority 2），优先消耗。**

| 模型 | 挂载角色 |
|------|------|
| glm-5.2 | 全部文本角色的兜底第 1 位 |
| qwen3.8-max-0902 | planner, writer, topic_generator, script_writer |
| qwen3.8-2.4t-a95b | planner |
| deepseek-v4-pro-0813 | planner, writer |
| deepseek-v4.1-flash | reviser, humanizer |
| deepseek-v4-flash-0731 | reviewer |
| kimi-k3 | writer |
| qwen3.8-flash | reviewer, reviser, cover_planner, shot_splitter |
| qwen3.7-flash-2026-07-15 | reviewer |
| qwen3.8-27b | reviser, humanizer |

**已删除的模型 id（2026-09-14 清理）**：
qwen3.7-max-2026-06-08、glm5.2（旧写法）、kimi-k2.7-code、qwen-image-3.0-pro、
wan2.7-t2v-2026-06-12、wan2.7-r2v-2026-06-12、wan3.0-video、happyhorse-1.1-t2v/i2v/r2v。

**`DASHSCOPE_TOKEN_KEY` 整组剔除**（Token Plan 已无额度，401/无配额）——
图像与视频生成现在**全部走 Agnes**。该 key 仍留在 `.env` 里但已无任何模型引用。

## 阿里百炼Token Plan（已于 2026-09-14 停用）

- **API Key**: `DASHSCOPE_TOKEN_KEY` — **已无额度，所有引用该 key 的模型条目已从 models.yaml 移除**
- 曾用模型：happyhorse-1.1-t2v/i2v/r2v（视频）、wan2.7-image（图像）
- 相关历史说明保留在 `DASHSCOPE_TOKEN_KEY_使用指南.md`，仅作存档，不再适用于当前配置

## 小说生成模式（v2.1 连载链路，2026-09-15 修复）

- **首批生成**：生成覆盖 total_chapters 的完整大纲 + 写 initial_chapters 章
- **手动续写**：项目详情页「连载进度」卡片 →「续写下一批」→ `POST /projects/{id}/generate/daily?chapters=N`
- **自动日更**：`ai_novel_beat` 容器按 `daily_publish_time` 触发续写（每 10 分钟检查一次；到点即触发、当日只跑一次）
- **目标总章数**：total_chapters，写满后按钮变「已完结」，续写自动停止
- **字数规范按平台走**（见 `app/config/platforms.py` 的 `chapter_words`）：
  - 百度 `(2000, 3000)`；番茄 `(1800, 2200)`
  - 番茄官方口径：单章最低 1000 字、黄金区间 2000-2200 字，低于 1800 易被判"水文"降权
  - 番茄短故事分档：超短篇 8k-2.49w 字，中短篇 2.5w-8w 字

### 连载修复记录（2026-09-15）

修复前连载**完全走不动**：三重锁死叠加 5 处硬伤。

| # | 问题 | 修复 |
|---|---|---|
| 1 | `docker-compose.yml` 只有 backend/worker/frontend，**没有 beat 服务**，worker 命令也没 `-B` → `beat_schedule` 里的日更调度在 Docker 下从未执行 | 新增 `beat` 服务；`-s /app/data/celerybeat-schedule` 把调度状态落到挂载目录，容器重建不失忆 |
| 2 | 判定用「HH:MM 精确相等」，而 `schedule: 3600` 的相位由 beat 启动时刻决定（历史日志实测相位 21:55 / 22:54）→ **永不命中**；且容器时区是 UTC，`datetime.now()` 与北京时间差 8 小时 | 改为「**到点或已过点 + Redis 当日去重**」；时间显式用北京时间；beat 改 `crontab(minute="*/10")` 把相位钉在整十分 |
| 3 | 前端**全站零调用** `generate/daily`，界面上没有续写入口，用户只能干等定时任务 | 详情页新增「连载进度」卡片：进度条 + 续写按钮（可选 1/2/3/5 章） |
| 4 | 续写只把「最近 3 章的**标题**」当上下文，而首批用的是大纲章节**摘要** → 上下文断层，续写必然脱节重复 | 抽出 `build_continuation_context()`：统一取最近 8 章的大纲摘要 + **上一章正文尾部 900 字** |
| 5 | 首批去AI化用 `recursive`、续写用 `adversarial` 且未传 platform → 同书章节风格与分数漂移 | 统一为 `DEFAULT_HUMANIZE_STRATEGY = "recursive"`，两处都显式传平台 |
| 6 | `generate_novel` 开头就 `delete()` 项目下**全部**章节 → 连载中误点「生成」= 已更章节全没 | 默认改为「**补齐首批**」不清空；真要从头重写须显式 `force=true` |
| 7 | 续写无并发保护；章号用「总数+1」推算，章节号一旦有空洞就撞唯一约束 | Redis 互斥锁 `novel:continue_lock:{pid}`；章号改取 `max(chapter_number)+1` |
| 8 | `writer.py` 硬编码「每章2000-3000字」，与平台无关 | 字数与写作规范全部搬进 `platforms.py`，writer/planner 按平台渲染 |

**关键代码位置**：
- `app/config/platforms.py` — `chapter_words` / `writer_rules` / `planner_rules`，及 `chapter_words_of` / `writer_rules_of` / `planner_rules_of`
- `app/agents/writer.py` — `build_writer_system_prompt(platform)`；`write_chapter(..., previous_tail, platform)`
- `app/agents/planner.py` — `plan(..., platform)` 注入番茄「黄金三章 / 情绪闭环 ≤3 章」
- `app/services/novel_engine.py` — `build_continuation_context()`、`write_chapter_with_review()`（首批与续写共用同一实现）
- `app/tasks/novel_tasks.py` — `generate_novel(force)`、`generate_daily_chapters(target_upto, batch_size)`、续写锁
- `app/tasks/publish_tasks.py` — `check_and_publish_scheduled` 的到点判定 + 当日去重
- 独立验证脚本：`backend/tests/test_platform_adaptation.py`（平台适配）、`.workbuddy/_ctx_test.py`（续写上下文 8 例）

### ⚠️ 改后端代码后的固定动作（2026-09-15 血泪）

compose 里 backend / worker / beat 是**三个独立镜像标签**（`text_gen_agent-backend|worker|beat`）。
`docker compose build backend` **不会**重建 worker 的镜像 —— worker 容器会继续跑旧代码，
于是"明明改完了却不生效"，而且很容易误判成逻辑没写对。

```bash
docker compose build backend worker beat
docker compose up -d --force-recreate backend worker beat
# 逐容器核对新符号，别只看镜像时间戳
docker exec ai_novel_worker grep -c "_current_task_id" /app/app/tasks/novel_tasks.py
```

补充三点：
- `docker compose build` **不重启容器**；镜像 ID 未变时 `up -d` 也不重建 → 必须 `--force-recreate`
- 前端是 dev 模式挂源码（`npm run dev`），改了 `page.tsx` 无需重建
- `task_acks_late=True` 下，被 SIGKILL 的在跑任务要靠 Redis broker 的 `visibility_timeout`
  （默认 **3600s**）才会重投，不是立刻 —— 所以**别在有长任务在跑时重建 worker**，
  否则任务会"消失"最多 1 小时后才重跑，项目期间一直挂在 `generating`

### v2.2 二次修复（2026-09-15）

| # | 问题 | 修复 |
|---|---|---|
| 9 | 锁 value 是常量 `"1"`，无法识别持锁者。task 被重投时 **task_id 不变**，却被上一轮已死任务残留的锁挡死 → 3 个项目同时卡在 `generating` | 锁 value 改存 **Celery task_id**；持锁者==自己→认锁续期接管；加 `takeover_ok`（项目状态已非 `generating` 即允许接管）；接管用 **Lua CAS** 防两个任务互相挤掉 |
| 10 | 首批生成不持锁 → beat 日更可能在首批还在写时读到旧章节数，章号撞车 | `generate_novel` 并入同一把锁。**锁必须在"补齐首批"分支之后才抢**（该分支把活转派给 `generate_daily_chapters`，提前持锁会让被转派的任务把自己挡在门外） |
| 11 | 字数只卡上限，且留 10% 容差（判到 2420 才算超）→ 番茄黄金区间是 1800-2200，放容差等于把不合规稿当合格交付 | 上限按平台真实上限判定；**新增下限兜底** `ReviserAgent.expand_to_length()`（只做场景内加厚，严禁新增情节） |
| 12 | 只收紧上限后正文普遍偏短（实测 1651 / 1764 字，番茄判"水文"） | writer prompt 目标改「区间中值」并写明字数口径；补写提示词**把差额算给模型看**并把上一轮实际字数回喂（`last_attempt_len`）—— 只说"补到 1800-2200"模型会从 1651 补到 1764 就收手 |
| 13 | 去AI化会重写全文但**不校验字数**，能把刚校准好的合规稿改坏 | `humanize_chapter` 落库前校验平台区间，跌出区间直接回滚原文 |
| 14 | 日更调度不看平台，番茄项目出现 `approved+unpublished` 章节就被丢给**百度**发布器，必然失败并刷重试与 `PublishQueue` 失败记录 | `platforms.supports_auto_publish()` 前置拦截；`publish_chapter_task` 内再兜一道（须放在"置 publishing"**之前**，否则 `publish_status` 会永久留在 publishing） |
| 15 | `humanize_recursive` 调 LLM **没传 `max_tokens`**，落到默认 4096。本策略要求输出完整改写全文，输出长度≈输入长度 → 结尾被硬切 → 一致性检查每轮都判"结尾截断/关键剧情缺失" → **候选全被跳过、文本一轮都没改成** | 补 `max_tokens=8192`（与同文件 `humanize_default`/`humanize_adversarial` 对齐）；另加长度地板：短于原文 80% 的候选直接丢弃 |
| 16 | 一致性裁判只拿到双方**各前 1500 字**（`original[:1500]`）。单章 2000-3000 字 → 裁判看到的"原文"是从中间断开的，于是每次都判"原文结尾缺失/改写新增结尾"——**这些 issues 是取样截断的产物，不是稿子的问题**。这才是"处理前后计数不变"的根因 | 新增 `_sample_for_review()`：不超 6000 字送全文，超长送"头 4000 + 尾 2000"并标注"此处省略中间 N 字"；prompt 里写明省略标注≠剧情缺失 |
| 17 | 人化可能**把结尾切掉十几个字**，而字数闸（1826 仍在 1800-2200）和长度地板（83.7% > 80%）**双双放行** → 成品文件末尾断在"那里，还" | 加三道**结尾句读**检查（比例法判不了完整性）：① `humanize_recursive` 候选级 ② `humanize_chapter` 落库前最终闸门（`rollback_reason="truncated_tail"`）③ `_export.py` 导出自检。⚠️ 句读正则必须含全角引号 `”` `’`，否则"……微笑。”会被误判 |
| 18 | 补写环节的"无增即停"会把**劣化结果**收下（模型"补"出更短的文本 1747→1700）| 候选不比当前长就地丢弃并继续催，`max_attempts` 用尽才按现状交付 |

**新增验证脚本**（`backend/tests/` 归档目标，当前在 `.workbuddy/`）：
- `_test_lock.py` — 续写锁 11 例（含"同 task_id 重投可接管"="卡死事故复现场景"）
- `_test_expand.py` — 字数兜底定向验证（对偏短章节跑补写，不重新生成整章）
- `_watch_words.py` / `_watch_beat.py` — 观察首批生成字数 / beat 自动日更链路


## 去 AI 味 v2.3（2026-09-14 升级）

调研来源：Wikipedia "Signs of AI writing" 指南、blader/humanizer 与 Show-Chan97/Humanizer-zh（29 种 AI 写作模式）、
2026 番茄短篇爆款方法论、hardikpandya/stop-slop。

**改动集中在 `backend/app/services/humanizer.py`：**

1. **禁用正则从 48 条扩到 88 条**，新增五类：
   - 说明文连词（然而/因此/于是/随后/紧接着/与此同时/除此之外/此外）——AI 写小说时残留的议论文骨架
   - 程度副词堆砌（非常/极其/十分/格外/无比/异常/极度）——AI 靠副词加力，人靠动词和细节
   - 翻译腔名词化（对……进行……／在……的过程中／作出决定）
   - 全知视角机械腔（只见/只听得/不由得）
   - 情绪平滑的万能过渡（不知过了多久/时间一分一秒地过去）
2. **评分从 7 维加到 10 维**，新增：感官失衡（0-10，AI 只调视觉+听觉，缺气味/温度/触感/身体反应）、
   赘余副词残留（0-8）、口语毛边缺失（0-5）。原始满分 100 + 新增 23 分，末尾统一归一化回 0-100，保持旧阈值可用。
3. **新增 `_build_humanize_prompt(platform)`** 统一人化提示词：12 条硬指标（砍长句/补非视觉感官/删连词/
   对话要接不住/允许毛边/情绪不要平滑/抽象换具体/结尾别收口）+「番茄平台的节奏底线」5 条。
4. **`humanize()` 系列新增 `platform` 参数，默认 `fanqie`**，老调用方无需改动。

**⚠️ 踩坑：检测正则的负向断言必须加。** `(r"十分", "")` 会把「二十分钟」改成「二十钟」——
程度副词类正则一律加 `(?![钟点])` 之类的否定断言。已有回归用例覆盖。

**实测效果**（用同一段典型 AI 味文本）：AI 分 52.0 → 25.2（quick 策略）；
成品短篇《无字碑》AI 分 **6.9**，句长 CV 0.867，感官覆盖 3/4 类，禁用词残留 0。

## 百度分发标题

- API: `POST /api/v1/projects/{id}/generate-titles`
- 规则：标题以"故事："开头，17-30字，符合百度作家平台规范
- 自动过滤字数不合格的标题

## 踩坑记录

### 1. Docker网络问题：PG/Redis是共享容器
**问题**: docker-compose.yml定义了postgres/redis服务，但它们与其他项目共享，不在同一Docker网络中，导致`could not translate host name "postgres"`错误。
**解决**: docker-compose.yml不再管理PG/Redis，改用`host.docker.internal:5432`和`host.docker.internal:6379`连接宿主机上的共享容器。添加`extra_hosts: host.docker.internal:host-gateway`。
**教训**: **永远不要删除共享容器！** 用IP/host.docker.internal访问外部服务。

### 2. ModelManager单例缓存导致配置不生效
**问题**: 修改models.yaml后，即使容器重启，ModelManager单例不重新加载配置。
**解决**: 在`_check_config_changed()`中检测文件mtime变更，`get_model_for_role()`和`call_llm()`调用前自动检测。也可手动调API: `POST /api/v1/config/models/reload`。
**教训**: 单例模式需要文件变更自动检测机制。

### 3. LLM返回非法JSON导致生成失败
**问题**: LLM返回的JSON含控制字符、未转义换行、中文引号等，导致json.loads失败。
**解决**: `_robust_json_parse()`4级容错：(1)清理控制字符+尾逗号 (2)修复中文引号+换行 (3)逐字符修复字符串内非法字符 (4)正则提取关键字段。
**教训**: 永远不要信任LLM返回的JSON格式，必须多层容错。

### 4. Celery任务超时
**问题**: 10章小说生成需10+分钟，但容器内celery配置是600s（旧镜像），导致硬超时kill。
**解决**: celery_config.py已设为1800s(30min)，需确保容器内配置同步。
**教训**: docker cp部署代码后，配置文件也要同步。

### 5. PostgreSQL数据卷挂载
**问题**: docker compose down后重建postgres容器，数据卷名不匹配导致数据丢失。
**解决**: 正确的数据卷是`ai_novel_pg_data`，不是`pg_data`或`text_gen_agent_pg_data`。
**教训**: 记住数据卷名，重建容器时用`-v ai_novel_pg_data:/var/lib/postgresql/data`。

### 6. docker cp无法覆盖bind mount
**问题**: `docker cp`到bind mount目录报"mounted volume is marked read-only"。
**解决**: bind mount的文件直接在宿主机修改即可，容器内实时可见。docker cp只适用于非挂载路径。
**教训**: 理解bind mount vs volume vs 镜像层文件的区别。

### 7. SQLAlchemy保留字`metadata`（v2.2端到端测试）
**问题**: `VideoAsset`模型使用`metadata`字段名，SQLAlchemy报错`Attribute name 'metadata' is reserved`。
**解决**: 改为`meta: Mapped[dict] = mapped_column("metadata", JSONType(), nullable=True)`，保持列名不变。
**教训**: SQLAlchemy保留字不能用作ORM属性名，用`mapped_column("原列名", ...)`保持DB兼容。

### 8. 百炼视频生成API端点错误（v2.2端到端测试）
**问题**: 用`/api/v1/services/video/video-synthesis`返回400 "task can not be null"。
**解决**: 正确端点是`/api/v1/services/aigc/video-generation/video-synthesis`，且必须加请求头`X-DashScope-Async: enable`。
**教训**: 百炼视频生成是异步API，必须查官方文档确认端点和请求头。

### 9. Token Plan需要专属base URL（v2.2端到端测试）
**问题**: Token Plan key用在百炼标准端点`dashscope.aliyuncs.com`返回401。
**解决**: Token Plan专属base URL：`https://token-plan.cn-beijing.maas.aliyuncs.com`（OpenAI兼容:`/compatible-mode/v1`，Anthropic兼容:`/apps/anthropic`）。
**教训**: Token Plan的API Key与百炼标准API Key不同，必须用对应的base URL。

### 10. Agnes API 503服务繁忙（v2.2端到端测试）
**问题**: Agnes API返回503 "Service busy: inference..."。
**解决**: 这是服务端问题，非配置错误。Key配置正确（能到达服务端），稍后重试即可。
**教训**: 503是服务端繁忙，不是配置问题；测试报告需区分配置错误和服务端错误。

### 11. ffmpeg xfade offset=0导致视频重叠（v2.2多段合成）
**问题**: `xfade=transition=fade:duration=0.5:offset=0`中offset=0导致第二段视频从0秒开始播放，与第一段重叠，最终视频只有最后一段的时长（5秒）。
**解决**: offset应为`第一段视频时长 - 转场时长`，例如`offset=4.54`。需先用ffmpeg获取第一段时长。
**教训**: ffmpeg xfade的offset是转场开始时间点，不是转场时长；必须获取前段视频时长来计算offset。

### 12. Token Plan配额按周限制（v2.2多段合成）
**问题**: Token Plan返回429 `Throttling.AllocationQuota`，"Your token-plan 1-week quota has been exhausted. The quota will reset at 08-30 13:37:00 UTC."
**解决**: Token Plan是按周配额（7天重置），不是按次。配额用完后需等重置。改用Agnes API（免费无配额限制）。
**教训**: Token Plan Lite套餐7万额度按周限制，不适合批量生成；Agnes API免费且无配额限制，适合批量生成。

### 13. Agnes CDN下载不稳定（v2.2多段合成）
**问题**: Agnes视频生成成功但下载失败，CDN（cos-platform-outputs.agnes-ai.cn）间歇性断开连接。
**解决**: 添加5次重试逻辑，每次间隔10秒。改为逐个下载（非并行）避免CDN并发限制。
**教训**: 免费CDN不稳定，必须加重试逻辑；并行下载可能触发CDN限流，逐个下载更可靠。

### 14. Agnes 401 的真因：**两套互不通用的端点 + key 空间**（2026-09-14，三次判断后定稿）
**问题**: models.yaml 把 agnes-3.0-flash 配成文本链路第一优先级后，实测 401
`{'message': '无效的令牌', 'type': 'AgnesAI_error'}`。

**三次判断过程（前两次都错，务必看完）**:
- **误判一**: "key 轮换失效、要换新 key" → 错，白让用户去找 key。
- **误判二**: "域名写错了，`.cn` 是假域名" → 错。`.cn` 和 `apihub` **都是真实在线的 Agnes 端点**，
  都返回 `AgnesAI_error` 格式 + request id。
- **真因**: Agnes 有**两套互不通用的端点与 key 空间**，**key 必须和域名配对**。
  报错语言都不一样，是判断依据：
  - `https://api.agnes-ai.cn/v1` → 中文 `无效的令牌`
  - `https://apihub.agnes-ai.com/v1` → 英文 `Invalid token`

**对照实测（2026-09-14 23:36，两把 key 各打两个域名）**:

| key | `api.agnes-ai.cn/v1` | `apihub.agnes-ai.com/v1` |
|---|---|---|
| `sk-CioO…4aZa`（现 `backend/.env`） | **200**（11 模型，对话正常） | 401 Invalid token |
| `sk-jY3Q…w6Hv`（旧） | 401 无效的令牌 | **200**（12 模型） |

**结论**: 401 的正确读法是「**这把 key 不属于这个域名**」——
**不是 key 坏、也不是域名错**。当前项目用 `.cn` 空间那把，故
`base_url: https://api.agnes-ai.cn/v1`。

**排查手法（可复用，按顺序做）**:
1. 先穷举鉴权头：`Authorization: Bearer` / 裸 / `x-api-key` / `api-key`。
   回「无效的令牌」或 `Invalid token` = 鉴权通道对、token 被服务端评估后拒绝；
   回「未提供令牌」= header 名不对。**这一步把"请求格式问题"彻底排掉。**
2. 两个候选端点用**同一把 key** 各打一次 `/models`，看是否"一边 200 一边 401"。
3. 反向交叉验证：**换另一把已知可用的 key 再打一次**。若结果对调，就直接证明是
   "key ↔ 域名 配对"问题（本次就是这样定案的）。
4. 比对报错语言/文案差异 —— 不同后端常有不同本地化，是分空间的旁证。

**教训**: 401 有四个变量（key 值 / 端点 / 鉴权头 / 配对关系），
**每换一个变量就要重新观测一次，不要只查一个变量就宣布根因**。
两次误判都是"单变量归因"。

### 14.1 `env_file` 只在容器创建时注入，改 `.env` 后必须重建容器
改 `backend/.env`（如换 `AGNES_KEY`）后，**运行中的容器拿的还是旧值**——
`docker-compose.yml` 用 `env_file: ./backend/.env`，值是创建时写进容器环境的，
**不是 bind mount，不会热重载**。
```bash
docker compose up -d backend worker     # 重建容器才会读到新 .env
```
自检：`docker exec ai_novel_backend printenv AGNES_KEY`（脱敏比对首尾字符）。

### 15. 后端代码改动必须 rebuild 镜像（2026-09-14）
**问题**: 改完 `backend/app/**` 的代码后重启容器，行为没变化。
**原因**: `docker-compose.yml` 里 backend/worker 只挂了 `config/ data/ logs/ static/ models/`，
**代码目录不在挂载列表里**；`backend/Dockerfile` 用 `COPY . .` 把代码打进镜像层。
所以宿主机改的 .py 文件容器根本看不见。
**解决**:
```bash
docker compose build backend worker
docker compose up -d backend worker
```
依赖层（torch/pip）有缓存，重建只需重跑 `COPY . .` 之后的层。
**对比**: `config/models.yaml`（挂载 + 热重载）改了立即生效；
前端 `frontend/src`（挂载）改了热重载生效。**只有后端代码需要 rebuild。**
**教训**: 分清三种路径 —— bind mount（改了立即生效）、volume（数据）、镜像层（必须 rebuild）。
验证前先确认"我改的东西容器到底看不看得见"。

## 部署方式

当前用**docker cp + 重启**方式部署代码更新（避免重建镜像的长时间等待）：
```powershell
# 同步Python文件到容器
docker cp backend/app/services/novel_engine.py ai_novel_backend:/app/app/services/novel_engine.py
docker cp backend/app/services/novel_engine.py ai_novel_worker:/app/app/services/novel_engine.py
# 重启生效
docker restart ai_novel_backend ai_novel_worker
```

注意：`config/`目录是bind mount，本地修改实时同步，无需docker cp。

## 项目数据

| 项目名 | 状态 | 章节数 |
|--------|------|--------|
| 和离后她入医谷惊艳天下，高傲将军卑微追妻 | reviewed | 8章(已去AI化，已发布百度) |
| 那些匿名树洞里的文字，全是对方不敢说的爱 | reviewed | 10章(已去AI化，total=30，待日更续写) |
| 我替人扫墓，守着一块无字碑（番茄短篇） | 完稿 | 6章/7833字，AI分6.9，待发布番茄 |

## 番茄短篇《无字碑》（2026-09-14）

- 文件：`无字碑_番茄小说版.txt`（工作区根目录）
- 题材：代客祭扫（殡葬新职业）+ 空碑悬念 + 情感反转，女频情感悬疑
- 结构：6 章，第1章前 300 字内出事，每章末留钩
- 硬指标：平均句长 13.5 字／短句(≤8字)占 30.2%／长句(≥30字)占 4.4%／对话占比 28.3%
- 时间线锚点：周砚失踪=3年前8月初 → 报案=3年前8月11日 → 周姨认尸撒谎=3年前8月29日 → 沈知夏接单=前年腊月 → 正文当下
- 待办：如果要做番茄自动发布，需新增 `services/publisher.py` 的番茄适配 + cookie 登录（现仅支持百度作家平台）

## AI漫剧视频生成结果（v2.2）

| 日期 | 模型 | 镜头数 | 时长 | 文件大小 | 说明 |
|------|------|--------|------|----------|------|
| 2026-08-24 | agnes-video-v2.0 | 10/10 | 46秒 | 12.31MB | 完整AI漫剧，重生题材，带转场+字幕 |
| 2026-08-24 | wan2.7-t2v-2026-06-12 | 6/10 | 30秒 | 1.05MB | DASHSCOPE_API_KEY1额度耗尽(403) |
| 2026-08-23 | wan2.7-t2v / happyhorse-1.1-t2v | 1/1 each | 5秒 each | 4.26MB/3.06MB | 端到端测试 |