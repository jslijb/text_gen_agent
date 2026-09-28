# AI小说生成系统 - Agent 约束手册

> 本文件只保留对 Agent 的**约束与纪律**：部署/改动纪律、快手物料规则。
> 启动方法、技术栈、关键配置等**项目事实**在 `README.md`；
> 架构细节、模型清单、踩坑因果在 `docs/`（完整索引见 README「文档索引」）。

## 部署与改动纪律（改完代码照着做，因果见 `docs/pitfalls.md`）

**1. 改后端代码 = build 三个镜像 + 强制重建**（backend/worker/beat 是三个独立镜像标签）：

```bash
docker compose build backend worker beat
docker compose up -d --force-recreate backend worker beat
# 逐容器核对新符号，别只看镜像时间戳
docker exec ai_novel_worker grep -c "_current_task_id" /app/app/tasks/novel_tasks.py
```

**2. 改 `backend/.env` = 重建容器**（env_file 只在容器创建时注入，不热重载）：

```bash
docker compose up -d --force-recreate backend worker beat
# 自检（脱敏比对首尾字符）
docker exec ai_novel_backend printenv AGNES_KEY
```

**3. 别在有长任务在跑时重建 worker**：`task_acks_late=True` 下被 SIGKILL 的任务要等
`visibility_timeout`（默认 3600s）才重投——任务会"消失"最多 1 小时，项目一直挂在 `generating`。

**4. 快速生效替代方案（docker cp）——知道风险时可用，常规路径仍是纪律 1**：

```powershell
docker cp backend/app/services/novel_engine.py ai_novel_backend:/app/app/services/novel_engine.py
docker cp backend/app/services/novel_engine.py ai_novel_worker:/app/app/services/novel_engine.py
docker restart ai_novel_backend ai_novel_worker
```

`config/` 目录是 bind mount，本地修改实时同步，无需 docker cp。

**5. 改动可见性自检**：动手前先确认"我改的东西容器到底看不看得见"——
bind mount（改了立即生效）／ volume（数据）／ 镜像层（必须 rebuild），三种路径别混。

**6. 每次修改完成 = 提交并推送**：任务完成后把**本任务相关文件** `git add` → `git commit`（message 说明意图）→ `git push` 远程。铁律：
- 只 add 本任务改动的文件，**禁止 `git add -A` / `git add .`**（工作区常有 sieve/其他会话的并行改动，不可误收）
- 提交前 `git status` + `git diff` 过一眼 staged 内容，发现非本任务文件要 unstage
- 未经用户明确要求不 force push、不 rebase 已推历史

## 快手发布物料规则（2026-09-24 起，长期生效）

**每生成一条新视频后，必须在项目根目录 `发布指南.md` 中写入该视频的：**
1. **「作品描述」**——发布标题 + 描述文案 + 话题标签（描述必须含原文出处 + 开放式提问，禁止「扣1/扣2」类引导话术，账号有处罚前科）
2. **「评论」**——置顶自评 + 按类型的评论区回复预案
3. **后续所有发布的视频**都在 `发布指南.md` 持续更新：生成后新增条目 → 发布后回填发布时间与状态。

- `发布指南.md` 是发布物料的**唯一权威台账**：聊天里给过物料不算交付，落盘才算。
- 数据复盘不写在这里，台账见 `快手作品数据.xlsx`；生产规格见 `快手视频生产经验清单.md`。
- 流水线脚本（如 `_make_nuba_video.py`）里的 `PUBLISH` 字段是物料的生成源；脚本更新物料后，须同步更新 `发布指南.md`。
- **每条视频生产之前**，先按 `快手视频生产经验清单.md` §四纪律 8 采集快手后台数据并修订经验清单，再开产。

## 文档速查（指针，不是约束）

- 启动方法 / 技术栈 / 关键配置 / 目录结构 → `README.md`
- 模型清单与密钥规则 → `docs/models.md`；踩坑因果全文 → `docs/pitfalls.md`；
  其余专题（platforms / novel-pipeline / humanizer / sieve / works-log / 调研报告）→ `docs/`，完整索引见 README「文档索引」
- 快手连载三件套：`快手视频生产经验清单.md`（生产规格+数据纪律）/ `发布指南.md`（物料台账）/ `快手作品数据.xlsx`（数据台账）
