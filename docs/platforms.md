# 平台化：多平台支持

> 本文档从 CLAUDE.md 迁出（2026-09-27）：小说项目的多平台架构（频道/品类/书名规则/字数规范）。
> 权威配置在 `backend/app/config/platforms.py`，本文记录设计与落地位置。

## 设计思路（2026-09-14 新增）

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

## 落地位置

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

## 百度分发标题

- API: `POST /api/v1/projects/{id}/generate-titles`
- 规则：标题以"故事："开头，17-30字，符合百度作家平台规范
- 自动过滤字数不合格的标题
