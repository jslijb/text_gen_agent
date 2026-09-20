"""下载百炼和Token Plan生成的视频到本地"""
import httpx
from pathlib import Path
from datetime import datetime

videos_dir = Path(__file__).parent.parent / "app" / "static" / "videos"
videos_dir.mkdir(parents=True, exist_ok=True)

timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

videos = [
    {
        "url": "https://dashscope-a717.oss-accelerate.aliyuncs.com/1d/13/20260823/b4f00fdb/50142469-metadata_user_e8eb6ae2ad198c37.mp4?Expires=1787578874&OSSAccessKeyId=LTAI***MASKED***&Signature=***MASKED***",
        "filename": f"dashscope_wan2.7-t2v_{timestamp}.mp4",
        "key": "DASHSCOPE_API_KEY1",
        "model": "wan2.7-t2v-2026-06-12",
    },
    {
        "url": "https://dashscope-7c2c.oss-accelerate.aliyuncs.com/1d/eb/20260823/e750bce7/18014717-metadata_video_720p_4b50b586-2aa1-4ded-95db-7b44dac555bb_refiner.mp4?Expires=1787578968&OSSAccessKeyId=LTAI***MASKED***&Signature=***MASKED***",
        "filename": f"tokenplan_happyhorse-1.1-t2v_{timestamp}.mp4",
        "key": "DASHSCOPE_TOKEN_KEY",
        "model": "happyhorse-1.1-t2v",
    },
]

for v in videos:
    filepath = videos_dir / v["filename"]
    print(f"下载中: {v['key']} ({v['model']}) -> {v['filename']}")
    try:
        with httpx.Client(timeout=120, follow_redirects=True) as client:
            resp = client.get(v["url"])
            if resp.status_code == 200:
                filepath.write_bytes(resp.content)
                size_mb = len(resp.content) / 1024 / 1024
                print(f"  ✅ 成功: {filepath} ({size_mb:.2f} MB)")
            else:
                print(f"  ❌ 失败: HTTP {resp.status_code} - {resp.text[:100]}")
    except Exception as e:
        print(f"  ❌ 异常: {e}")

print(f"\n视频目录: {videos_dir}")
for f in sorted(videos_dir.glob("*.mp4")):
    size_mb = f.stat().st_size / 1024 / 1024
    print(f"  {f.name}: {size_mb:.2f} MB")