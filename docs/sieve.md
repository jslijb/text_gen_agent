# sieve 抓取 API 集成（2026-09-25）

> 本文档从 CLAUDE.md 迁出（2026-09-27）：sieve 外部抓取的集成设计、硬规则与排障记录。

外部抓取（`https://scrape.usesieve.com`）接进来，用来抓公开页面的数据（对标账号、作品数据等）。
**未配置 `SIEVE_API_KEY` 时整套功能关闭**（接口 503、任务不启动），其余功能完全不受影响。

## 密钥

- 存放位置：`backend/.env` 的 `SIEVE_API_KEY`（项目唯一的密钥载体，随 compose 的 `env_file`
  注入 backend / worker / beat 三容器；`backend/.env.example` 里有占位）。
- 获取方式：`python backend/scripts/sieve_device_login.py` —— 走设备登录（device code）流程，
  脚本把链接和 user_code 给你，**由你自己在浏览器里核对并点 Approve**，脚本只负责轮询和写盘，
  密钥不会出现在任何输出里。已有 key 想换要加 `--force`。
- ⚠️ **2026-09-25 实测：设备登录这条路暂时走不通。** `POST /api/auth/device/code` 稳定返回
  401 `{"error":"unauthorized"}`（换 Origin/Referer/UA、换路径写法、换 host 都一样）；
  `/api/*` 下只有 `/api/auth/session` 在鉴权门之外，其余（含不存在的路径）一律先 401。
  服务端问题，客户端绕不过也不应该绕。
  **替代路径：网页版 Settings → API keys 建一把 key，然后**
  `python backend/scripts/sieve_device_login.py --set-key`（隐藏输入粘贴，不走 argv/历史记录）。
  脚本已支持这种混用：key 从哪里来对代码没影响。
- ⚠️ key 有整账号权限且无 scope：**只在服务端用**，不要进浏览器/移动端包、日志、错误上报或 git。
  改完 `.env` 必须 `docker compose up -d --force-recreate backend worker beat`（env_file 不热重载）。

## 代码位置

| 层 | 文件 | 职责 |
|---|---|---|
| HTTP 客户端 | `app/services/sieve_client.py` | 请求构建、状态码→异常映射、轮询退避、取件 |
| 台账 | `app/models/sieve.py`（表 `sieve_runs`） | run 的本地记录（session_id 先落库） |
| 异步任务 | `app/tasks/sieve_tasks.py` | 创建+轮询、追问、beat 补轮询 |
| 接口 | `app/api/sieve.py` + `app/schemas/sieve.py` | `/api/v1/sieve/*` |

## 三条硬规则（都别拆）

1. **创建 run 超时绝不自动重试。** `POST /api/scrapes` 没有幂等键，被接受就扣费；
   超时/网络错误只能记 `ambiguous` 交给人判断。只有 429 与 5xx 会重试（这两种确定没创建 run）。
2. **session_id 先落库再干活。** 202 一回来就单独 commit 到 `sieve_runs`，然后才轮询/下载；
   进程崩了由 `resume_pending_sieve_runs`（beat，每 5 分钟）照 session_id 接着跑，而不是重开一次。
3. **追问必须等 turns 推进。** `status` 变 `done` 但 `turns` 没动，读到的是上一轮的答案；
   基线存 `sieve_runs.baseline_turns`（不能存 `turns`，轮询会覆盖它）。409 = 有 turn 在飞。

## 结果怎么读

- `status`：`running` 继续轮询；`done` 读结果；`refused` 是终态（`refusal.code` 说明原因，
  `quota` = 额度类拒绝）；其它值一律当错误（`SieveUnknownStatus`）。
- `schema_conformance.status`：`fail` 的产物**不能当干净数据交付** ——
  `describe_conformance()` 会给出 `conformance_ok=False` + 警告文案，接口原样透出给前端。
- 交付文件 `files[].url` 是相对地址，取件要拼 base URL + Bearer 头，落到 `data/sieve/<session_id>/`。
- 额度：`GET /api/v1/sieve/credits`（plan / limit / used / remaining）。

## 验证

```bash
conda activate bigmodel
cd backend
python -m pytest tests/test_sieve_client.py tests/test_sieve_api.py tests/test_sieve_tasks.py tests/test_sieve_secret_store.py -q
```

录制响应只用 `httpx.MockTransport` 打在 HTTP 边界，状态机与落库都是真实代码。

**未做**：monitors（定时监控）与 webhook 回执没接——本项目用不到；需要时按官方文档在
`sieve_tasks.py` 里加，webhook 侧要自己实现常量时间比对密钥路径、10s 内返回 2xx、按
(monitor_id, run_id) 去重，并定时用 `GET /api/monitors/<id>/runs` 对账（漏发的不会重发）。
