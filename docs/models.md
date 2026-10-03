# 模型配置与密钥状态

> 本文档从 CLAUDE.md 迁出（2026-09-27）：模型清单、端点配对、密钥使用状态的**唯一详细参考**。
> 密钥本身的唯一载体是 `backend/.env`（不入 git、不进日志）；本文只记录掩码与状态。
> 改动 `backend/.env` 后必须重建容器（见 CLAUDE.md 踩坑 14.1）。

## 可用模型 (2026-09-14 全量更新)

### Agnes（`AGNES_KEY`，文本/图像/视频第一优先级，免费无配额）

> ⚠️ **Agnes 有两套互不通用的端点 + key 空间，`base_url` 必须与 key 配对，
> 不存在"绝对正确的那个域名"。**（2026-09-15 实测修正，此前说法是反的）
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
