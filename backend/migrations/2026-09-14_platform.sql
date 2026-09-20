-- 2026-09-14 平台化迁移：projects 增加 platform 列，并扩展分类取值域
-- 幂等：可重复执行
BEGIN;

-- 1) 新增 platform 列（存量数据默认为百度平台）
ALTER TABLE projects
    ADD COLUMN IF NOT EXISTS platform VARCHAR(20) NOT NULL DEFAULT 'baidu';

-- 2) 放宽 gender 约束：百度频道 ∪ 番茄频道
ALTER TABLE projects DROP CONSTRAINT IF EXISTS ck_project_gender;
ALTER TABLE projects
    ADD CONSTRAINT ck_project_gender
    CHECK (gender IN ('男性向','女性向','无性向','女频','男频'));

-- 3) platform 取值约束
ALTER TABLE projects DROP CONSTRAINT IF EXISTS ck_project_platform;
ALTER TABLE projects
    ADD CONSTRAINT ck_project_platform
    CHECK (platform IN ('baidu','fanqie'));

COMMIT;

-- 验证
SELECT platform, gender, genre, count(*) AS n
FROM projects
GROUP BY platform, gender, genre
ORDER BY platform, gender;

SELECT column_name, data_type, is_nullable, column_default
FROM information_schema.columns
WHERE table_name = 'projects' AND column_name = 'platform';
