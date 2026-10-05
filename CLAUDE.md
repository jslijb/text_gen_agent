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

## 自动发布与首评铁律（2026-10-04 起，长期生效）

**1. 自动发布必须声明「作品由 AI 生成」**——发布流程里 作者声明 一律勾 `内容为AI生成`，不可省略。
- 该声明**只在首次上传的发布页可勾**；`编辑作品` 页（含待发布与已发布）都没有这个控件，事后补不了。
- 想补声明只能「删除待发布项 → 重新上传 → 重新定时」，代价是重传与排期风险，所以**首发就要勾对**。
- 视频文件本身也要齐：右上角「AI生成」角标 + mp4 元数据隐式标识（`_ks_ai_check.py` 可批量核验）。
  平台另有自动检测，未勾声明的作品公开页只显示「疑似含AI生成内容」而非作者自主声明。

**2. 首发评论（含置顶）必须先确认"视频真的发出去了、而且是这一条"**：
- 定位依据用**作品链接/workId**，不用标题文本——同系列标题高度相似，纯文本匹配会搞错对象。
- 三重校验：① 作品在「已发布」列表且发布时间与排期一致；② 公开页 `www.kuaishou.com/short-video/<workId>` 可访问、标题与预期一致；③ 该作品评论区还没有自己的首评（幂等去重）。
- 任一项不通过 → **不发评论**，写失败状态并告警；宁可漏评，不可错评。


**3. 尾部引流预告必须按真实排期措辞，不能一律写「明天讲」**（10-04 起双更：每天 11:00 + 19:00）：
- 上一条的口播尾镜 + 首发评论里的预告对象，必须是**时间轴上真正紧接着发的那一条**；
- 19:00 场 → 下一条是次日 11:00，写「明天十一点讲，X」；11:00 场 → 下一条是**当晚 19:00**，写「今晚七点讲，X」；
- 改排期/插播/跳票时，预告文案要同步改；已出厂成片改不了，就在首发评论里纠偏并记进《发布指南》。
- 已知欠账：口播尾镜出厂全是「明天讲，X」，11:00 场（嫦娥/女娲/羲和/巫山神女）措辞与当晚更新不符，首发评论已改为「今晚七点讲」。

**4. 首评自动补发链路（10-05 起上线，改任何一环都要同步）**：
- 正文唯一来源 = `发布指南.md` 每条的「**首发评论**」引用块；`_ks_comment_run.py` 每次运行先 `sync_from_guide()` 刷进 `data/ks_comment_queue.json`（文档缺条目只告警，**绝不自己编文案**）；
- 排期与状态在队列 JSON 里（`publish_at` / `status` / `work_id`），新增一条视频 = 队列加一条 + 文档写正文，两处都要动；
- 触发：计划任务 `KS_Comment_Post`（每天 11:05）、`KS_Comment_Evening`（每天 19:05）+ 开机自启 `Startup\KS首评补发.lnk`，三者都调 `_ks_comment_task.bat`；错过时点靠**登录后自启补发**（已验证：10-05 11:05 任务失败，16:14 开机补发成功）；
- 排障看两个日志：`logs/ks_comment.log`（业务事件，含 START/END/CRASH）与 `logs/ks_comment_task.log`（bat 原始输出）；
- 网页版**没有置顶入口**，脚本只发首评并记 `PIN_MANUAL_ON_APP`，置顶由人工在手机 APP 完成。

## 文档速查（指针，不是约束）

- 启动方法 / 技术栈 / 关键配置 / 目录结构 → `README.md`
- 模型清单与密钥规则 → `docs/models.md`；踩坑因果全文 → `docs/pitfalls.md`；
  其余专题（platforms / novel-pipeline / humanizer / sieve / works-log / 调研报告）→ `docs/`，完整索引见 README「文档索引」
- 快手连载三件套：`快手视频生产经验清单.md`（生产规格+数据纪律）/ `发布指南.md`（物料台账）/ `快手作品数据.xlsx`（数据台账）
