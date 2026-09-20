-- AI漫剧/视频生成功能数据库迁移脚本
-- 执行日期: 2026-08-16
-- 说明: 创建视频项目、分镜、素材相关表

-- 1. 视频项目表
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

-- 2. 分镜表
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

-- 3. 素材表
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

-- 4. 素材-分镜关联表
CREATE TABLE IF NOT EXISTS video_asset_shots (
    asset_id UUID REFERENCES video_assets(id) ON DELETE CASCADE,
    shot_id UUID REFERENCES video_shots(id) ON DELETE CASCADE,
    role VARCHAR(50),
    PRIMARY KEY (asset_id, shot_id)
);

-- 5. 创建索引
CREATE INDEX IF NOT EXISTS idx_video_shots_project ON video_shots(project_id);
CREATE INDEX IF NOT EXISTS idx_video_assets_type ON video_assets(type);

-- 6. 添加约束
ALTER TABLE video_projects 
ADD CONSTRAINT ck_video_project_duration 
CHECK (target_duration BETWEEN 15 AND 300);

ALTER TABLE video_projects 
ADD CONSTRAINT ck_video_project_status 
CHECK (status IN ('draft','generating','completed','failed'));

ALTER TABLE video_shots 
ADD CONSTRAINT ck_video_shot_duration 
CHECK (duration BETWEEN 2 AND 10);

ALTER TABLE video_shots 
ADD CONSTRAINT ck_video_shot_status 
CHECK (status IN ('pending','generating','completed','failed'));

-- 7. 添加注释
COMMENT ON TABLE video_projects IS '视频项目表';
COMMENT ON TABLE video_shots IS '分镜表';
COMMENT ON TABLE video_assets IS '素材表';
COMMENT ON TABLE video_asset_shots IS '素材-分镜关联表';

COMMENT ON COLUMN video_projects.status IS '状态: draft-草稿, generating-生成中, completed-已完成, failed-失败';
COMMENT ON COLUMN video_shots.status IS '状态: pending-待生成, generating-生成中, completed-已完成, failed-失败';
COMMENT ON COLUMN video_assets.type IS '类型: character-角色, scene-场景, audio-音频, prop-道具';