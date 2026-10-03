# 小说连载链路（v2.1 / v2.2 修复记录）

> 本文档从 CLAUDE.md 迁出（2026-09-27）：连载生成的运行机制与两轮修复的完整记录。
> 改相关代码前先读这里的「关键代码位置」与踩坑，避免复踩。

## 小说生成模式（v2.1 连载链路，2026-09-15 修复）

- **首批生成**：生成覆盖 total_chapters 的完整大纲 + 写 initial_chapters 章
- **手动续写**：项目详情页「连载进度」卡片 →「续写下一批」→ `POST /projects/{id}/generate/daily?chapters=N`
- **自动日更**：`ai_novel_beat` 容器按 `daily_publish_time` 触发续写（每 10 分钟检查一次；到点即触发、当日只跑一次）
- **目标总章数**：total_chapters，写满后按钮变「已完结」，续写自动停止
- **字数规范按平台走**（见 `app/config/platforms.py` 的 `chapter_words`）：
  - 百度 `(2000, 3000)`；番茄 `(1800, 2200)`
  - 番茄官方口径：单章最低 1000 字、黄金区间 2000-2200 字，低于 1800 易被判"水文"降权
  - 番茄短故事分档：超短篇 8k-2.49w 字，中短篇 2.5w-8w 字

## 连载修复记录（2026-09-15）

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

## v2.2 二次修复（2026-09-15）

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
