# 踩坑记录

> 本文档从 CLAUDE.md 迁出（2026-09-27）：Docker/LLM/API/视频合成等 15 条踩坑全记录。
> 改动基础设施、部署、模型链路、视频合成前，先对照本文避坑。
> 与部署强相关的 14.1/15 条，CLAUDE.md 操作纪律里有速查版；这里存完整因果。

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
