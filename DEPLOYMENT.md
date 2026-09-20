# AI漫剧/视频生成功能部署指南

## 部署前检查清单

### 1. 环境配置

#### 1.1 Python环境
```powershell
# 激活conda环境
conda activate bigmodel

# 检查Python版本
python --version  # 需要Python 3.11+
```

#### 1.2 依赖包
```powershell
# 检查依赖包
pip list | findstr httpx
pip list | findstr sqlalchemy
pip list | findstr fastapi

# 如果需要安装
pip install httpx sqlalchemy fastapi uvicorn celery redis psycopg2-binary
```

#### 1.3 环境变量
确保`.env`文件中配置了以下API Key:
```bash
# 阿里百炼标准API (主用)
DASHSCOPE_API_KEY1=your_api_key

# 阿里百炼Token Plan (备选)
DASHSCOPE_TOKEN_KEY=your_token_plan_key

# Agnes API (首选)
AGNES_KEY=your_agnes_key
```

### 2. 数据库迁移

#### 2.1 创建新表
```sql
-- 视频项目表
CREATE TABLE IF NOT EXISTS video_projects (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    title VARCHAR(255) NOT NULL,
    topic TEXT,
    style VARCHAR(50) DEFAULT 'comic',
    target_duration INTEGER DEFAULT 30,
    status VARCHAR(20) DEFAULT 'draft',
    config JSONB,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW(),
    completed_at TIMESTAMP
);

-- 分镜表
CREATE TABLE IF NOT EXISTS video_shots (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    project_id UUID REFERENCES video_projects(id) ON DELETE CASCADE,
    sequence INTEGER NOT NULL,
    description TEXT,
    narration TEXT,
    duration INTEGER DEFAULT 5,
    image_prompt TEXT,
    video_prompt TEXT,
    image_url VARCHAR(500),
    video_url VARCHAR(500),
    audio_url VARCHAR(500),
    status VARCHAR(20) DEFAULT 'pending',
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

-- 素材表
CREATE TABLE IF NOT EXISTS video_assets (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    type VARCHAR(20) NOT NULL,
    name VARCHAR(255),
    description TEXT,
    image_url VARCHAR(500),
    metadata JSONB,
    used_count INTEGER DEFAULT 0,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

-- 素材-分镜关联表
CREATE TABLE IF NOT EXISTS video_asset_shots (
    asset_id UUID REFERENCES video_assets(id) ON DELETE CASCADE,
    shot_id UUID REFERENCES video_shots(id) ON DELETE CASCADE,
    role VARCHAR(50),
    PRIMARY KEY (asset_id, shot_id)
);

-- 创建索引
CREATE INDEX IF NOT EXISTS idx_video_shots_project ON video_shots(project_id);
CREATE INDEX IF NOT EXISTS idx_video_assets_type ON video_assets(type);
```

### 3. 配置文件更新

#### 3.1 更新models.yaml
确保`config/models.yaml`中包含视频生成模型配置:
```yaml
# 视频生成相关模型
topic_generator:
  provider: dashscope
  model_id: qwen3.7-max
  priority: 100
  
script_writer:
  provider: dashscope
  model_id: qwen3.7-max
  priority: 101
  
shot_splitter:
  provider: dashscope
  model_id: qwen3.7-max
  priority: 102
  
image_generator:
  provider: dashscope
  model_id: qwen-image-3.0-pro
  priority: 110

# 视频生成模型
video_agnes:
  provider: agnes
  model_id: agnes-2.5-flash
  priority: 1
  
video_wan27_t2v:
  provider: dashscope
  model_id: wan2.7-t2v-2026-06-12
  priority: 2
  # ... 其他模型
```

#### 3.2 更新Prompt配置
确保`backend/app/config/prompts/video.yaml`存在

### 4. 代码部署

#### 4.1 同步代码到容器
```powershell
# 如果使用Docker部署
docker cp backend/app/services/ ai_novel_backend:/app/app/services/
docker cp backend/app/models/ ai_novel_backend:/app/app/models/
docker cp backend/app/schemas/ ai_novel_backend:/app/app/schemas/
docker cp backend/app/api/v1/video/ ai_novel_backend:/app/app/api/v1/
docker cp backend/app/config/prompts/ ai_novel_backend:/app/app/config/prompts/
docker cp backend/tests/test_integration.py ai_novel_backend:/app/app/tests/

# 同步到Worker
docker cp backend/app/services/ ai_novel_worker:/app/app/services/
docker cp backend/app/models/ ai_novel_worker:/app/app/models/
docker cp backend/app/schemas/ ai_novel_worker:/app/app/schemas/
docker cp backend/app/config/prompts/ ai_novel_worker:/app/app/config/prompts/
```

#### 4.2 重启服务
```powershell
# 重启后端和Worker
docker restart ai_novel_backend ai_novel_worker

# 检查服务状态
docker ps | findstr ai_novel
```

### 5. 健康检查

#### 5.1 API健康检查
```powershell
# 检查API服务
curl http://localhost:8000/health

# 预期响应
# {"status": "ok", "version": "..."}
```

#### 5.2 视频API测试
```powershell
# 测试创建视频项目
curl -X POST http://localhost:8000/api/v1/video/projects \
  -H "Content-Type: application/json" \
  -d '{"title": "测试项目", "style": "comic", "target_duration": 30}'

# 预期响应: 201 Created
```

### 6. 功能验证

#### 6.1 单元测试
```powershell
# 运行单元测试
cd backend
pytest tests/test_ai_video.py -v
pytest tests/test_topic_generator.py -v
pytest tests/test_script_writer.py -v
pytest tests/test_shot_splitter.py -v
pytest tests/test_asset_generator.py -v
pytest tests/test_video_generator.py -v
```

#### 6.2 集成测试
```powershell
# 运行集成测试(需要真实API)
pytest tests/test_integration.py -v -m integration
```

#### 6.3 冒烟测试
```powershell
# 运行冒烟测试
pytest tests/test_integration.py -v -m smoke
```

### 7. 监控和告警

#### 7.1 配置监控
- 监控API响应时间
- 监控视频生成成功率
- 监控API额度使用情况

#### 7.2 告警设置
- 403错误率超过阈值
- API响应时间超过5秒
- 视频生成失败率超过10%

### 8. 回滚计划

如果部署失败,执行以下回滚:

```powershell
# 回滚代码
docker exec ai_novel_backend git checkout HEAD~1
docker exec ai_novel_worker git checkout HEAD~1

# 重启服务
docker restart ai_novel_backend ai_novel_worker
```

### 9. 常见问题

#### Q1: 403 Forbidden错误
**原因**: API额度用完
**解决**: 自动切换到下一个模型,403模型加入黑名单

#### Q2: 视频生成超时
**原因**: API响应慢或网络问题
**解决**: 增加超时时间,检查网络连接

#### Q3: 数据库连接失败
**原因**: 数据库配置错误
**解决**: 检查DATABASE_URL配置

#### Q4: Celery任务失败
**原因**: Redis连接问题
**解决**: 检查Redis配置,确保Redis运行正常

### 10. 联系信息

- **技术支持**: [待填写]
- **项目负责人**: [待填写]
- **紧急联系**: [待填写]

---

**部署日期**: 2026-08-16
**版本**: v1.0.0
**部署人**: [待填写]