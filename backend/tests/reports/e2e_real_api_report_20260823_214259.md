# 真实API端到端测试报告

**测试时间**: 2026-08-23 21:38:44
**耗时**: 255.1秒
**测试总数**: 3
**成功**: 2
**失败**: 1
**成功率**: 66.7%

## 测试结果汇总

| 序号 | 提供商 | 模型 | Key | 状态 | 耗时 | 视频URL | 合规分 | 爆款分 |
|------|--------|------|-----|------|------|---------|--------|--------|
| 1 | Agnes | agnes-video-v2.0 | AGNES_KEY | ❌ 失败 | 10.6s | - | - | 100.0 |
| 2 | DashScope | wan2.7-t2v-2026-06-12 | DASHSCOPE_API_KEY1 | ✅ 成功 | 152.5s | https://dashscope-a717.oss-accelerate.aliyuncs.com... | 66.7 | 100.0 |
| 3 | TokenPlan | happyhorse-1.1-t2v | DASHSCOPE_TOKEN_KEY | ✅ 成功 | 91.7s | https://dashscope-7c2c.oss-accelerate.aliyuncs.com... | 66.7 | 100.0 |

## 详细测试结果

### 1. Agnes - agnes-video-v2.0

- **API Key**: `AGNES_KEY`
- **状态**: ❌ 失败
- **耗时**: 10.6秒
- **错误信息**: HTTP 503: {"code":"fail_to_fetch_task","message":"{\"error\":{\"message\":\"litellm.ServiceUnavailableError: ServiceUnavailableError: OpenAIException - {\\\"error\\\":{\\\"message\\\":\\\"Service busy: inferenc
- **爆款特征检查** (得分: 100.0):
  - ✅ 标题长度合规: 21字
  - ✅ 标题包含悬念词
  - ✅ 标题包含情绪词
  - ✅ 开头3秒有钩子
  - ✅ 结尾有悬念引导追更
  - ✅ 总时长合规: 20秒

### 2. DashScope - wan2.7-t2v-2026-06-12

- **API Key**: `DASHSCOPE_API_KEY1`
- **状态**: ✅ 成功
- **耗时**: 152.5秒
- **视频URL**: https://dashscope-a717.oss-accelerate.aliyuncs.com/1d/13/20260823/b4f00fdb/50142469-metadata_user_e8eb6ae2ad198c37.mp4?Expires=1787578874&OSSAccessKeyId=LTAI***MASKED***&Signature=***MASKED***
- **视频时长**: 5秒
- **快手合规检查** (得分: 66.7):
  - ✅ 视频URL有效
  - ✅ 视频格式为MP4
  - ❌ 视频时长不合规: 5秒(建议15-180秒)
- **爆款特征检查** (得分: 100.0):
  - ✅ 标题长度合规: 21字
  - ✅ 标题包含悬念词
  - ✅ 标题包含情绪词
  - ✅ 开头3秒有钩子
  - ✅ 结尾有悬念引导追更
  - ✅ 总时长合规: 20秒

### 3. TokenPlan - happyhorse-1.1-t2v

- **API Key**: `DASHSCOPE_TOKEN_KEY`
- **状态**: ✅ 成功
- **耗时**: 91.7秒
- **视频URL**: https://dashscope-7c2c.oss-accelerate.aliyuncs.com/1d/eb/20260823/e750bce7/18014717-metadata_video_720p_4b50b586-2aa1-4ded-95db-7b44dac555bb_refiner.mp4?Expires=1787578968&OSSAccessKeyId=LTAI***MASKED***&Signature=***MASKED***
- **视频时长**: 5秒
- **快手合规检查** (得分: 66.7):
  - ✅ 视频URL有效
  - ✅ 视频格式为MP4
  - ❌ 视频时长不合规: 5秒(建议15-180秒)
- **爆款特征检查** (得分: 100.0):
  - ✅ 标题长度合规: 21字
  - ✅ 标题包含悬念词
  - ✅ 标题包含情绪词
  - ✅ 开头3秒有钩子
  - ✅ 结尾有悬念引导追更
  - ✅ 总时长合规: 20秒

## 踩坑记录

- **agnes-video-v2.0**: HTTP 503: {"code":"fail_to_fetch_task","message":"{\"error\":{\"message\":\"litellm.ServiceUnavailableError: ServiceUnavailableError: OpenAIException - {\\\"error\\\":{\\\"message\\\":\\\"Service busy: inferenc

---
*报告生成时间: 2026-08-23 21:42:59*