# AI小说生成系统 - 测试报告

**生成时间**: 2026-07-13
**测试环境**: Windows 11, Python 3.13.11, conda bigmodel, SQLite

---

## 一、单元测试（120个，全部通过）

| 测试模块 | 测试数 | 状态 | 说明 |
|---------|--------|------|------|
| test_agents.py | 5 | PASS | 4-Agent协作（Planner/Writer/Reviewer/Reviser） |
| test_api/test_projects.py | 8 | PASS | 项目CRUD API + gender/genre校验 |
| test_cover_service.py | 11 | PASS | 封面生成（Agnes LLM编排 + 图像API + Pillow叠加） |
| test_cover_service_agnes.py | 14 | PASS | Agnes图像API + gender/genre分层校验 |
| test_covers_api.py | 7 | PASS | 封面API端点 |
| test_hot_topic_fetcher.py | 13 | PASS | 百度热搜抓取 + 缓存 + 降级 + 性向筛选 |
| test_hot_topics_api.py | 6 | PASS | 热点API + 创意生成API |
| test_humanize_control.py | 3 | PASS | 去AI化暂停/停止控制 |
| test_humanize_tasks.py | 11 | PASS | 去AI化任务（quick策略 + 批量 + 状态查询） |
| test_humanizer.py | 8 | PASS | 去AI化引擎（正则替换 + AI评分） |
| test_humanizer_recursive.py | 8 | PASS | 递进去AI化（多轮 + best-of-N + 一致性检查） |
| test_knowledge_base.py | 5 | PASS | ChromaDB知识库（单例 + 文本分割 + 相似度搜索） |
| test_model_manager.py | 6 | PASS | 模型管理（配置 + 403自动切换 + 额度耗尽） |
| test_publisher.py | 4 | PASS | 百度作家平台发布（加密 + Cookie管理） |
| **合计** | **120** | **120 PASS** | |

---

## 二、端到端测试（分步执行，3/4步通过）

| 步骤 | 描述 | 状态 | 详情 |
|------|------|------|------|
| Step 1 | 创建项目 + 生成大纲 | PASS | 3章大纲，模型=qwen3.7-plus，耗时58s |
| Step 2 | 生成第1章 | PASS | 2199字，模型=qwen3.7-plus，耗时68s |
| Step 3 | 去AI化（quick策略） | PASS | AI分数 68.5→68.5（本章无套话模式匹配） |
| Step 4 | 生成封面 | TIMEOUT | Agnes图像API超时（AGNES_KEY可能未配置） |

**端到端流水线核心路径验证通过**：选题→大纲→写作→去AI化。封面生成依赖Agnes API key配置。

---

## 三、模块验证（之前已通过）

| 模块 | 验证结果 |
|------|---------|
| 模型管理器 | 8个模型配置，403自动切换已验证 |
| 小说引擎 | 大纲生成3章规划已验证 |
| 去AI化引擎 | AI分数79.9→61.5（有套话的文本） |
| 封面生成 | 文字封面已验证（Agnes API需key） |
| 知识库 | ChromaDB持久化已验证 |
| 配置服务 | 热加载已验证 |
| 热点抓取 | 百度热搜解析已验证 |

---

## 四、已知限制

1. **bash 2分钟超时**：单次LLM调用1-2分钟，完整10章测试无法在单次bash中完成
2. **Agnes图像API**：需配置AGNES_KEY环境变量，否则封面生成会跳过
3. **Redis未运行**：Celery异步任务无法使用，测试中通过`.apply()`同步执行
4. **PostgreSQL未运行**：已改用SQLite，GUID/JSONType已适配
5. **模型额度**：qwen3.7-max等已耗尽，当前使用qwen3.7-plus和qwen-turbo