from sqlalchemy import create_engine, text

# 测试同步连接
engine = create_engine('postgresql://postgres:postgres@localhost:5432/ai_novel')
with engine.connect() as conn:
    result = conn.execute(text('SELECT 1'))
    print('✓ 同步连接正常')
    
    # 检查表是否存在
    result = conn.execute(text("""
        SELECT table_name FROM information_schema.tables 
        WHERE table_name IN ('video_projects', 'video_shots', 'video_assets', 'video_asset_shots')
    """))
    tables = [row[0] for row in result]
    print(f'✓ 找到表: {tables}')
    
    # 检查每个表的数据量
    for table in tables:
        result = conn.execute(text(f'SELECT COUNT(*) FROM {table}'))
        count = result.scalar()
        print(f'  - {table}: {count} 条记录')