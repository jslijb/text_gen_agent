# DASHSCOPE_TOKEN_KEY 使用指南

## 1. 什么是DASHSCOPE_TOKEN_KEY?

**DASHSCOPE_TOKEN_KEY** 是阿里百炼Token Plan的API密钥,用于调用阿里百炼的视频生成模型。

### 与DASHSCOPE_API_KEY1的区别

| 密钥 | 用途 | 模型类型 | 计费方式 |
|------|------|----------|----------|
| **DASHSCOPE_API_KEY1** | 标准API | 文本生成、图像生成 | 按量计费 |
| **DASHSCOPE_TOKEN_KEY** | Token Plan | 视频生成(T2V/I2V/R2V) | Token套餐 |

**注意**: 两个密钥不同,不要混淆使用!

---

## 2. 如何获取DASHSCOPE_TOKEN_KEY?

### 步骤1: 登录阿里百炼控制台

1. 访问 [阿里百炼控制台](https://bailian.console.aliyun.com/)
2. 使用阿里云账号登录

### 步骤2: 开通Token Plan服务

1. 在控制台左侧菜单选择"Token Plan"
2. 点击"立即开通"
3. 选择适合的套餐(Lite/Pro/Ultra)

### 步骤3: 获取API Key

1. 在Token Plan控制台,选择"API Key管理"
2. 点击"创建API Key"
3. 复制生成的密钥

### 步骤4: 配置到环境变量

编辑 `backend/.env` 文件:

```bash
# 阿里百炼Token Plan
DASHSCOPE_TOKEN_KEY=your_token_plan_key_here
```

**注意**: 将 `your_token_plan_key_here` 替换为真实的密钥

---

## 3. 支持的视频模型

使用DASHSCOPE_TOKEN_KEY可以调用以下视频生成模型:

### 3.1 文生视频(T2V)

| 模型ID | 说明 | 时长 | 分辨率 |
|--------|------|------|--------|
| `happyhorse-1.1-t2v` | 文生视频 | 2-15秒 | 720P/1080P |
| `wan2.7-t2v-2026-06-12` | 万相文生视频 | 2-15秒 | 720P/1080P |

### 3.2 图生视频(I2V)

| 模型ID | 说明 | 时长 | 分辨率 |
|--------|------|------|--------|
| `happyhorse-1.1-i2v` | 图生视频 | 2-15秒 | 720P/1080P |
| `wan2.7-r2v-2026-06-12` | 万相参考生视频 | 2-10秒 | 720P/1080P |

### 3.3 参考生视频(R2V)

| 模型ID | 说明 | 时长 | 分辨率 |
|--------|------|------|--------|
| `happyhorse-1.1-r2v` | 参考生视频 | 2-10秒 | 720P/1080P |

---

## 4. 使用示例

### 4.1 使用curl测试

```bash
# 文生视频测试
curl -X POST https://token-plan.cn-beijing.maas.aliyuncs.com/apps/anthropic/v1/messages \
  -H "Authorization: Bearer $DASHSCOPE_TOKEN_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "model": "happyhorse-1.1-t2v",
    "prompt": "一只猫在阳光下打盹"
  }'
```

### 4.2 使用Python测试

```python
import os
import httpx

# 获取API Key
api_key = os.getenv("DASHSCOPE_TOKEN_KEY")

# 调用视频生成API
response = httpx.post(
    "https://token-plan.cn-beijing.maas.aliyuncs.com/apps/anthropic/v1/messages",
    headers={
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json"
    },
    json={
        "model": "happyhorse-1.1-t2v",
        "prompt": "一只猫在阳光下打盹"
    },
    timeout=60
)

print(response.json())
```

---

## 5. 在项目中使用

### 5.1 配置优先级

我们的视频生成模块按以下优先级选择模型:

1. **Agnes API** (首选,免费) - 使用 `AGNES_KEY`
2. **DASHSCOPE_API_KEY1** (标准API) - 10个模型
3. **DASHSCOPE_TOKEN_KEY** (Token Plan) - 3个模型

### 5.2 自动切换机制

当某个模型返回403错误(额度用完),系统会自动:
1. 切换到下一个可用模型
2. 将403模型加入黑名单
3. 继续生成视频

### 5.3 代码示例

```python
from app.services.video_generator import VideoGenerator

generator = VideoGenerator()

# 生成视频
video_url = await generator.generate(
    project_id="your-project-id",
    shots=[...],
    assets=[...]
)

# 查看当前使用的模型
current_model = generator.get_current_model()
print(f"当前模型: {current_model}")
```

---

## 6. 常见问题

### Q1: 403 Forbidden错误

**原因**: Token Plan额度用完

**解决方案**:
1. 登录阿里百炼控制台查看额度
2. 购买更多Token套餐
3. 系统会自动切换到备用模型

### Q2: API Key无效

**原因**: API Key配置错误或已过期

**解决方案**:
1. 检查 `.env` 文件中的 `DASHSCOPE_TOKEN_KEY`
2. 确认API Key是否正确
3. 在阿里百炼控制台重新生成API Key

### Q3: 视频生成超时

**原因**: 视频生成时间过长或网络问题

**解决方案**:
1. 增加超时时间
2. 检查网络连接
3. 减少视频时长

### Q4: 模型不支持

**原因**: 使用的模型ID不正确

**解决方案**:
1. 参考第3节的模型ID列表
2. 使用正确的模型ID

---

## 7. 费用说明

### 7.1 Token Plan套餐

| 套餐 | Token数量 | 价格 | 说明 |
|------|-----------|------|------|
| Lite | 100万 | ¥99 | 适合小规模使用 |
| Pro | 500万 | ¥399 | 适合中等规模 |
| Ultra | 2000万 | ¥1299 | 适合大规模 |

### 7.2 视频生成消耗

| 模型 | 消耗Token/秒 | 5秒视频消耗 |
|------|-------------|-------------|
| happyhorse-1.1-t2v | 100 | 500 |
| happyhorse-1.1-i2v | 120 | 600 |
| happyhorse-1.1-r2v | 150 | 750 |

---

## 8. 最佳实践

### 8.1 成本控制

1. **优先使用免费模型**: Agnes API
2. **批量生成**: 批量处理,减少API调用次数
3. **优化时长**: 控制视频时长在5秒以内
4. **监控使用量**: 定期查看Token消耗

### 8.2 错误处理

1. **实现重试机制**: 失败时自动重试
2. **记录日志**: 记录所有API调用
3. **设置告警**: 额度接近上限时告警

### 8.3 安全建议

1. **不要硬编码**: API Key放在环境变量中
2. **定期更换**: 定期更换API Key
3. **最小权限**: 只授予必要的权限

---

## 9. 技术支持

如果遇到问题:

1. 查看阿里百炼文档: https://help.aliyun.com/zh/model-studio/
2. 提交工单: 阿里云控制台
3. 联系技术支持: [待填写]

---

**文档版本**: v1.0  
**更新日期**: 2026-08-16  
**维护者**: [待填写]