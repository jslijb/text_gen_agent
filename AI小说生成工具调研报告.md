# AI小说/短篇故事自动生成开源项目调研报告

> 调研时间：2026-06-20

---

## 一、核心项目详细分析

### 1. InkOS — 故事创作AI Agent系统 ⭐⭐⭐⭐⭐

| 项目 | 详情 |
|------|------|
| **GitHub URL** | https://github.com/Narcooo/inkos |
| **Stars** | 7,425 |
| **Forks** | 1,400 |
| **最后更新** | 2026-06-17（3天前） |
| **许可证** | AGPL-3.0 |
| **语言** | TypeScript |
| **创建时间** | 2026-03-12 |

**核心功能：**
- 面向长短篇小说、剧本剧作、互动游戏与IP内容的创作智能体系统
- **InkOS Play**：开放世界与分支互动，支持自由动作、角色Agent、物品/证据/关系状态
- **长篇小说**：从创作简报建书，生成世界观、角色、卷纲、章节意图，按"写作→审稿→修订→状态结算"推进
- **InkOS Short**：独立短篇生成，含正文、大纲、审稿记录、简介卖点、封面提示词
- **Studio Chat**：统一交互入口，聊天、建书、短篇、封面、互动世界共享action surface
- **记忆与上下文**：SQLite记忆、Markdown投影、会话摘要、protected/compressible语义压缩
- 支持Studio（Web UI）、TUI、CLI三种交互形式
- 已发布为OpenClaw Skill，可被Claude Code等Agent调用

**技术栈：**
- TypeScript + Node.js
- npm包：`@actalk/inkos`
- SQLite（记忆存储）
- 支持多模型服务商：Google Gemini、Moonshot、MiniMax、智谱、百炼、OpenRouter、自定义OpenAI-compatible端点

**是否支持自定义LLM：** ✅ 是
- Studio内置多服务配置、模型路由
- 支持百炼（DashScope）作为服务商
- 支持自定义OpenAI-compatible服务
- 规划/正文/审阅可按路由拆开配不同模型

**是否可以本地运行：** ✅ 是
- `npm i -g @actalk/inkos` 安装
- `inkos init my-novel` 初始化
- 完全本地运行，数据存储在本地

**成熟度评估：** ⭐⭐⭐⭐⭐（5/5）
- Stars最高（7.4k），社区活跃
- 已入选KIMI开源合作伙伴
- v1.5.0版本，功能完整
- 持续更新（3天前）
- 有完善的文档和微信交流群

**生成质量评估：** ⭐⭐⭐⭐（4/5）
- 多Agent协作架构，写作→审稿→修订闭环
- 语义压缩记忆系统解决长篇上下文问题
- 伏笔管理和状态追踪
- 但AI写作质量仍受限于底层模型能力

---

### 2. AI_NovelGenerator — AI长篇小说生成工具 ⭐⭐⭐⭐

| 项目 | 详情 |
|------|------|
| **GitHub URL** | https://github.com/YILING0013/AI_NovelGenerator |
| **Stars** | 5,344 |
| **Forks** | — |
| **最后更新** | 2026-06-20（今天） |
| **许可证** | — |
| **语言** | Python |
| **创建时间** | — |

**核心功能：**
- 使用AI生成多章节的长篇小说，自动衔接上下文、伏笔
- 小说设定工坊：世界观/角色设计/剧情蓝图
- 智能章节生成：多阶段生成确保剧情连贯
- 状态追踪系统：角色发展轨迹/伏笔管理
- 语义搜索引擎：基于向量的长期上下文一致性
- 知识库集成：支持本地文档引用
- 自动校对：检测剧情矛盾和逻辑冲突
- 可视化工作台：全流程GUI

**技术栈：**
- Python 3.9+（推荐3.10-3.12）
- 向量数据库（可选）
- OpenAI兼容接口（支持OpenAI/DeepSeek/Ollama等）

**是否支持自定义LLM：** ✅ 是
- 支持OpenAI兼容接口
- 支持Ollama本地模型
- 可配置base_url、model_name、api_key
- 支持embedding接口配置

**是否可以本地运行：** ✅ 是
- `pip install -r requirements.txt`
- `python main.py` 启动GUI
- 支持本地Ollama模型

**成熟度评估：** ⭐⭐⭐⭐（4/5）
- Stars第二高（5.3k）
- 作者表示精力有限，正在重构
- 重构版本在dev分支
- GUI界面完善

**生成质量评估：** ⭐⭐⭐（3/5）
- 多阶段生成确保连贯性
- 伏笔和状态追踪
- 但作者自己承认需要改进重复措辞和章节衔接

---

### 3. AI-Novel-Writing-Assistant — AI小说创作工作台 ⭐⭐⭐⭐

| 项目 | 详情 |
|------|------|
| **GitHub URL** | https://github.com/ExplosiveCoderflome/AI-Novel-Writing-Assistant |
| **Stars** | 1,701 |
| **Forks** | — |
| **最后更新** | 2026-06-20（今天） |
| **许可证** | — |
| **语言** | TypeScript |
| **创建时间** | — |

**核心功能：**
- 面向长篇小说的AI生产系统，"AI导演式"而非聊天壳子
- **自动导演开书**：从一句灵感直接进入，自动生成整本方向和标题组
- **Creative Hub**：统一创作中枢，对话/规划/工具调用/执行状态
- **整本生产主链**：从结构化规划到章节执行到整本批量pipeline
- **写法引擎**：写法可保存、编辑、绑定、试写和复用，可从现有文本提取写法特征
- **本书世界**：世界观→世界骨架→世界手册→规则→势力→地点→关系
- **RAG知识库**：Qdrant向量数据库，拆书结果回灌
- Windows桌面版（Setup.exe/portable）

**技术栈：**
- Monorepo：pnpm workspace
- 前端：React + Vite
- 后端：Express + Prisma
- AI：LangChain + LangGraph
- 编辑器：Plate
- 数据库：SQLite + Prisma
- 向量数据库：Qdrant（RAG）

**是否支持自定义LLM：** ✅ 是
- 支持OpenAI、DeepSeek、SiliconFlow、xAI等多提供商
- 模型路由：规划/正文/审阅可配不同模型
- 可扩展

**是否可以本地运行：** ✅ 是
- SQLite默认即可运行
- Qdrant按需接入
- Windows桌面版
- 前后端Monorepo拆分

**成熟度评估：** ⭐⭐⭐⭐（4/5）
- 功能最全面的项目之一
- 持续更新（今天）
- 桌面版v0.3.20
- LangGraph编排工作流

**生成质量评估：** ⭐⭐⭐⭐（4/5）
- 写法引擎控制风格一致性
- RAG知识库增强上下文
- 自动导演+整本生产主链
- 质量修复链路（局部→整章升级）

---

### 4. terminal-velocity — 10个AI Agent协作写小说 ⭐⭐⭐

| 项目 | 详情 |
|------|------|
| **GitHub URL** | https://github.com/mind-protocol/terminal-velocity |
| **Stars** | 1,106 |
| **最后更新** | 2026-06-20 |
| **语言** | Python |

**核心功能：**
- 10个AI Agent协作自主创作小说
- 完整的Agent团队分工

**成熟度评估：** ⭐⭐⭐（3/5）— 更偏实验性项目

---

### 5. NovelClaw — 结构化长篇小说工作台 ⭐⭐⭐

| 项目 | 详情 |
|------|------|
| **GitHub URL** | https://github.com/iLearn-Lab/NovelClaw |
| **Stars** | 326 |
| **最后更新** | 2026-06-19 |
| **许可证** | MIT |
| **语言** | Python |

**核心功能：**
- 动态记忆优先的协作AI框架
- 长篇故事生成、章节规划、连贯叙事写作
- 可检查的运行会话、故事板、稿件表面
- 角色和世界视图、可编辑记忆库
- 人在回路的工作流

**技术栈：**
- Python 3.10+
- FastAPI
- 在线试用：colong-idea-studio.cloud

**是否支持自定义LLM：** ✅ 部分
- 支持在线和本地运行
- 具体LLM配置需查看代码

**是否可以本地运行：** ✅ 是（`START_LOCAL.bat`）

**成熟度评估：** ⭐⭐⭐（3/5）

---

### 6. show-me-the-story — 自托管AI小说生成器 ⭐⭐⭐⭐

| 项目 | 详情 |
|------|------|
| **GitHub URL** | https://github.com/Nigh/show-me-the-story |
| **Stars** | 182 |
| **最后更新** | 2026-06-20（今天） |
| **许可证** | — |
| **语言** | Go |

**核心功能：**
- **单文件运行**：一个二进制文件+浏览器，零依赖
- 两阶段创作：先生成大纲→逐章写作
- 逐章审核+自动确认模式
- 结构化设定：角色/世界观/组织/人物关系
- **关系图谱**：可视化展示关系网络
- **伏笔系统**：规划→埋设→推进→回收，超期告警
- **事实核查**：每章自动一致性检查，不通过自动重写
- **去AI味**：23条禁止模式+高频套话替换+口语化规则
- **全书优化**：完稿后一键诊断→一致性核查→优化工单→逐章修订
- **AI助理**：对话式操作项目设定/大纲/章节
- 续写已有作品、技能系统、断点续作、多语言

**技术栈：**
- 后端：Go 1.25+，仅标准库，零第三方依赖
- 前端：Vite 5 + Svelte 4 + Tailwind CSS 4 + DaisyUI 5
- 通信：REST API + SSE实时事件流
- 前端构建产物通过embed.FS内嵌进二进制

**是否支持自定义LLM：** ✅ 是
- 任意OpenAI兼容API（OpenAI、DeepSeek、Ollama/LM Studio等）
- API地址+模型名称+API Key配置
- 全局共享，所有项目通用

**是否可以本地运行：** ✅ 是（核心优势）
- 单个Go二进制文件，开箱即用
- 所有数据本地纯文本/JSON文件
- 无需数据库

**成熟度评估：** ⭐⭐⭐⭐（4/5）
- 功能非常完善
- 持续活跃更新
- 架构设计优秀（零依赖Go后端）
- 但Stars相对较少

**生成质量评估：** ⭐⭐⭐⭐（4/5）
- 伏笔系统+事实核查+去AI味
- 全书优化流程
- 人工审核+AI修订结合

---

### 7. kimi-writer — Kimi写作Agent ⭐⭐⭐

| 项目 | 详情 |
|------|------|
| **GitHub URL** | https://github.com/Doriandarko/kimi-writer |
| **Stars** | 572 |
| **最后更新** | 2026-06-17 |
| **语言** | Python |

**核心功能：**
- 基于kimi-k2-thinking模型的自主写作Agent
- 自动规划和执行创意写作任务
- 实时流式输出（推理+内容）
- 智能上下文管理（200K token限制，自动压缩）
- 恢复模式（从保存的上下文摘要恢复）
- 工具使用：创建项目、写文件、管理工作区

**技术栈：**
- Python
- Moonshot API（kimi-k2-thinking）
- 最大300次迭代

**是否支持自定义LLM：** ❌ 否（仅支持Kimi/Moonshot）

**是否可以本地运行：** ✅ 是

**成熟度评估：** ⭐⭐⭐（3/5）— 轻量级，单Agent

---

### 8. AIStoryWriter — AI故事生成器 ⭐⭐⭐

| 项目 | 详情 |
|------|------|
| **GitHub URL** | https://github.com/datacrystals/AIStoryWriter |
| **Stars** | 253 |
| **最后更新** | 2026-06-16 |
| **语言** | Python |

**核心功能：**
- 基于用户Prompt生成中到长篇小说
- 支持本地模型（Ollama）和云服务（Google）
- 自动模型下载
- 可自定义Prompt和模型
- 多语言翻译

**技术栈：**
- Python
- Ollama（本地模型）
- Google Gemini（云服务）
- OpenRouter

**是否支持自定义LLM：** ✅ 是（Ollama/Google/OpenRouter）

**是否可以本地运行：** ✅ 是

**成熟度评估：** ⭐⭐⭐（3/5）

---

### 9. storycraftr — AI书籍创作助手 ⭐⭐⭐

| 项目 | 详情 |
|------|------|
| **GitHub URL** | https://github.com/raestrada/storycraftr |
| **Stars** | 145 |
| **最后更新** | 2026-06-12 |
| **语言** | Python |

**核心功能：**
- CLI驱动的AI书籍创作工具
- 世界观构建、书籍结构、章节生成
- 聊天模式
- 多语言支持

**技术栈：**
- Python + LangChain
- 支持 OpenAI / OpenRouter / Ollama
- 本地Embedding（BAAI/bge-large-en-v1.5）

**是否支持自定义LLM：** ✅ 是

**是否可以本地运行：** ✅ 是

**成熟度评估：** ⭐⭐⭐（3/5）— Beta阶段

---

### 10. 其他值得关注的项目

| 项目 | Stars | 语言 | 特点 |
|------|-------|------|------|
| [neuro-book](https://github.com/notnotype/neuro-book) | 103 | TypeScript | 本地AI工作台，Markdown Studio，多Agent写作 |
| [novel_agent](https://github.com/blackzhanzhan/novel_agent) | 79 | Python | Git原生+Dify Agent |
| [Morpheus](https://github.com/papysans/Morpheus) | 33 | TypeScript | 多智能体+三层记忆+实时流式 |
| [ai-novel-generator](https://github.com/yangqi1309134997-coder/ai-novel-generator) | 234 | Python | AI自动生成长篇小说和故事 |

---

## 二、关于指定项目的说明

### NovelScribe
在GitHub上**未找到**名为"NovelScribe"的AI小说生成项目。搜索"NovelScribe AI novel"返回0个结果。该项目可能：
- 不存在或已更名
- 是私有仓库
- 是你计划创建的项目

### zqy-novel
在GitHub上**未找到**名为"zqy-novel"的项目。搜索返回0个结果。该项目可能：
- 不存在或已删除
- 是私有仓库

---

## 三、阿里百炼平台（DashScope）API能力

### 支持的模型

#### 千问系列（自研）
| 模型 | 类型 | 说明 |
|------|------|------|
| qwen3.7-max | 文本生成 | 最强千问模型 |
| qwen3.7-plus | 文本生成 | 高性价比 |
| qwen3.6-flash | 文本生成 | 快速推理 |
| qwen3.5-omni-plus | 全模态 | 文本+图像+音频+视频 |
| text-embedding-v4 | 向量化 | 文本向量化 |
| qwen3-rerank | 重排序 | 检索增强 |

#### 第三方模型
| 模型 | 说明 |
|------|------|
| deepseek-v4-pro | DeepSeek最新 |
| deepseek-v4-flash | DeepSeek快速版 |
| kimi-k2.7-code | Kimi代码模型 |
| glm-5.2 | 智谱GLM |
| MiniMax-M2.7 | MiniMax |
| mimo-v2.5-pro | 小米 |

#### 其他模态
- 图像生成：wan2.7-image-pro、qwen-image-2.0-pro
- 语音合成：cosyvoice-v3.5-plus
- 语音识别：fun-asr
- 3D模型：Tripo

### API调用方式

百炼提供**4种接口**：

1. **OpenAI兼容 Chat Completions**（推荐）
   - 与OpenAI客户端库直接兼容
   - 迁移成本最低
   - `base_url`: `https://dashscope.aliyuncs.com/compatible-mode/v1`

2. **OpenAI兼容 Responses**
   - 内置联网搜索、代码解释器、网页内容提取
   - 自动管理对话历史

3. **Anthropic兼容 Messages**
   - 兼容Anthropic Messages API
   - 支持思考和工具调用

4. **DashScope原生接口**
   - 百炼原生接口
   - 最完整的功能集和参数支持

### 是否支持长文本生成

✅ **是**
- 千问系列模型支持长上下文（最高128K+ tokens）
- 支持流式输出
- 支持多轮对话
- 可通过OpenAI兼容接口直接调用

### 是否支持Agent模式

✅ **是**
- 百炼提供**智能体（Agent）应用构建**能力
- 支持工具调用（Function Calling）
- OpenAI兼容Responses接口内置联网搜索、代码解释器
- 支持RAG（检索增强生成）
- 支持多Agent编排

### 百炼与开源项目的对接

| 项目 | 对接百炼的可行性 | 方式 |
|------|-------------------|------|
| InkOS | ✅ 原生支持 | Studio内置百炼服务商配置 |
| AI_NovelGenerator | ✅ 可行 | 配置base_url为百炼OpenAI兼容端点 |
| AI-Novel-Writing-Assistant | ✅ 可行 | 自定义OpenAI-compatible端点 |
| show-me-the-story | ✅ 可行 | 任意OpenAI兼容API |
| 其他OpenAI兼容项目 | ✅ 可行 | 统一通过OpenAI兼容接口 |

---

## 四、对比总结

| 项目 | Stars | 语言 | 多Agent | 伏笔系统 | 去AI味 | RAG | GUI | 本地运行 | 百炼兼容 | 成熟度 |
|------|-------|------|---------|----------|--------|-----|-----|----------|----------|--------|
| **InkOS** | 7.4k | TS | ✅ | ✅ | ❌ | ✅ | ✅Studio | ✅ | ✅原生 | ⭐⭐⭐⭐⭐ |
| **AI_NovelGenerator** | 5.3k | Py | ❌ | ✅ | ❌ | ✅ | ✅ | ✅ | ✅ | ⭐⭐⭐⭐ |
| **AI-Novel-Writing-Assistant** | 1.7k | TS | ✅ | ❌ | ❌ | ✅Qdrant | ✅ | ✅ | ✅ | ⭐⭐⭐⭐ |
| **show-me-the-story** | 182 | Go | ✅ | ✅ | ✅ | ❌ | ✅Web | ✅ | ✅ | ⭐⭐⭐⭐ |
| **NovelClaw** | 326 | Py | ✅ | ❌ | ❌ | ❌ | ✅ | ✅ | 部分 | ⭐⭐⭐ |
| **kimi-writer** | 572 | Py | ❌ | ❌ | ❌ | ❌ | ❌CLI | ✅ | ❌ | ⭐⭐⭐ |
| **AIStoryWriter** | 253 | Py | ❌ | ❌ | ❌ | ❌ | ❌CLI | ✅ | ✅ | ⭐⭐⭐ |
| **storycraftr** | 145 | Py | ❌ | ❌ | ❌ | ✅ | ❌CLI | ✅ | ✅ | ⭐⭐⭐ |

---

## 五、推荐方案

### 🏆 最佳综合推荐：InkOS

**理由：**
1. 社区最活跃（7.4k Stars，1.4k Forks）
2. 功能最全面：长篇/短篇/剧本/互动游戏/开放世界
3. **原生支持百炼**作为模型服务商
4. 多Agent协作+记忆系统+审稿修订闭环
5. 持续更新（3天前），已入选KIMI开源合作伙伴
6. 三种交互形式（Studio/TUI/CLI）
7. npm一键安装，开箱即用

### 🥈 最佳轻量级推荐：show-me-the-story

**理由：**
1. **单文件运行**，零依赖（Go编译）
2. 功能意外地完善：伏笔系统+事实核查+去AI味+全书优化
3. 任意OpenAI兼容API（含百炼）
4. 所有数据本地纯文本，易备份迁移
5. 适合快速上手和个人使用

### 🥉 最佳Python方案：AI_NovelGenerator

**理由：**
1. Python生态，易于二次开发
2. 5.3k Stars，社区认可
3. GUI界面完善
4. 向量语义搜索+知识库
5. 但作者精力有限，重构中

### 🎯 如果要自研项目的推荐架构

基于调研结果，推荐的自研架构：

```
技术栈：Python + FastAPI + LangChain/LangGraph
LLM后端：阿里百炼（DashScope）OpenAI兼容接口
模型：qwen3.7-max（规划）+ qwen3.6-flash（正文）+ deepseek-v4-flash（审阅）
向量数据库：Qdrant / text-embedding-v4
Agent框架：LangGraph多Agent编排
存储：SQLite + 本地文件
前端：React + Vite（参考AI-Novel-Writing-Assistant）
```

**核心功能模块（参考各项目最佳实践）：**
1. **自动导演开书**（参考AI-Novel-Writing-Assistant）
2. **多Agent协作**（参考InkOS：规划Agent+写作Agent+审稿Agent+修订Agent）
3. **记忆与上下文管理**（参考InkOS：protected/compressible分层）
4. **伏笔系统**（参考show-me-the-story：埋设→推进→回收→告警）
5. **事实核查**（参考show-me-the-story：每章自动一致性检查）
6. **去AI味**（参考show-me-the-story：23条禁止模式+口语化规则）
7. **写法引擎**（参考AI-Novel-Writing-Assistant：风格提取+绑定+试写）
8. **RAG知识库**（参考AI-Novel-Writing-Assistant：Qdrant+拆书回灌）
9. **全书优化**（参考show-me-the-story：诊断→核查→工单→修订）

---

## 六、关键词搜索结果汇总

| 关键词 | 结果数 | 主要发现 |
|--------|--------|----------|
| "ai novel generator" | 195 | AI_NovelGenerator(5.3k)、show-me-the-story(182) |
| "ai story writer" | 302 | kimi-writer(572)、NovelClaw(326)、AIStoryWriter(253) |
| "novel writing ai agent" | 93 | AI-Novel-Writing-Assistant(1.7k)、terminal-velocity(1.1k) |
| "fiction generator" | — | 搜索超时，部分结果与上述重叠 |