"""
数据库迁移脚本 - 修复版

执行迁移:
1. 创建视频项目表 (video_projects)
2. 创建分镜表 (video_shots)
3. 创建素材表 (video_assets)
4. 创建素材-分镜关联表 (video_asset_shots)
5. 创建索引和约束
"""

import asyncio
import logging
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# 异步数据库URL
ASYNC_DATABASE_URL = "postgresql+asyncpg://postgres:postgres@localhost:5432/ai_novel"


async def execute_sql(conn, sql: str, description: str):
    """执行单条SQL语句"""
    try:
        await conn.execute(text(sql))
        logger.info(f"✓ {description}")
    except Exception as e:
        logger.error(f"✗ {description} 失败: {e}")
        raise


async def create_tables():
    """创建表"""
    engine = create_async_engine(ASYNC_DATABASE_URL, echo=False)
    
    async with engine.begin() as conn:
        # 1. 创建视频项目表
        await execute_sql(conn, """
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
        """, "创建视频项目表")
        
        # 2. 创建分镜表
        await execute_sql(conn, """
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
        """, "创建分镜表")
        
        # 3. 创建素材表
        await execute_sql(conn, """
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
        """, "创建素材表")
        
        # 4. 创建素材-分镜关联表
        await execute_sql(conn, """
            CREATE TABLE IF NOT EXISTS video_asset_shots (
                asset_id UUID REFERENCES video_assets(id) ON DELETE CASCADE,
                shot_id UUID REFERENCES video_shots(id) ON DELETE CASCADE,
                role VARCHAR(50),
                PRIMARY KEY (asset_id, shot_id)
            );
        """, "创建素材-分镜关联表")
        
        # 5. 创建索引
        await execute_sql(conn, """
            CREATE INDEX IF NOT EXISTS idx_video_shots_project ON video_shots(project_id);
        """, "创建索引 idx_video_shots_project")
        
        await execute_sql(conn, """
            CREATE INDEX IF NOT EXISTS idx_video_assets_type ON video_assets(type);
        """, "创建索引 idx_video_assets_type")
        
        # 6. 添加约束
        await execute_sql(conn, """
            ALTER TABLE video_projects 
            ADD CONSTRAINT ck_video_project_duration 
            CHECK (target_duration BETWEEN 15 AND 300);
        """, "添加约束 ck_video_project_duration")
        
        await execute_sql(conn, """
            ALTER TABLE video_projects 
            ADD CONSTRAINT ck_video_project_status 
            CHECK (status IN ('draft','generating','completed','failed'));
        """, "添加约束 ck_video_project_status")
        
        await execute_sql(conn, """
            ALTER TABLE video_shots 
            ADD CONSTRAINT ck_video_shot_duration 
            CHECK (duration BETWEEN 2 AND 10);
        """, "添加约束 ck_video_shot_duration")
        
        await execute_sql(conn, """
            ALTER TABLE video_shots 
            ADD CONSTRAINT ck_video_shot_status 
            CHECK (status IN ('pending','generating','completed','failed'));
        """, "添加约束 ck_video_shot_status")
        
        # 7. 添加注释
        await execute_sql(conn, """
            COMMENT ON TABLE video_projects IS '视频项目表';
        """, "添加注释 video_projects")
        
        await execute_sql(conn, """
            COMMENT ON TABLE video_shots IS '分镜表';
        """, "添加注释 video_shots")
        
        await execute_sql(conn, """
            COMMENT ON TABLE video_assets IS '素材表';
        """, "添加注释 video_assets")
        
        await execute_sql(conn, """
            COMMENT ON TABLE video_asset_shots IS '素材-分镜关联表';
        """, "添加注释 video_asset_shots")
    
    await engine.dispose()
    logger.info("\n✅ 数据库迁移完成!")


async def check_tables():
    """检查表是否创建成功"""
    engine = create_async_engine(ASYNC_DATABASE_URL, echo=False)
    
    async with engine.begin() as conn:
        # 检查表是否存在
        tables = ['video_projects', 'video_shots', 'video_assets', 'video_asset_shots']
        
        for table in tables:
            result = await conn.execute(text(f"""
                SELECT EXISTS (
                    SELECT FROM information_schema.tables 
                    WHERE table_name = '{table}'
                );
            """))
            exists = result.scalar()
            
            if exists:
                logger.info(f"✓ 表 {table} 存在")
            else:
                logger.error(f"✗ 表 {table} 不存在")
    
    await engine.dispose()


if __name__ == "__main__":
    import sys
    
    if len(sys.argv) > 1 and sys.argv[1] == "check":
        # 只检查表
        asyncio.run(check_tables())
    else:
        # 创建表
        asyncio.run(create_tables())
        print("\n运行 'python migrate.py check' 检查表状态")
