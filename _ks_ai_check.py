# -*- coding: utf-8 -*-
"""批量核验本地视频是否带 AI 标识：文件元数据（隐式）+ 右上角「AI生成」角标像素（显式）。

用法: _ks_ai_check.py [video ...]   不带参数则核验 QUEUE 列表
"""
import os
import re
import subprocess
import sys

import imageio_ffmpeg
from PIL import Image

FF = imageio_ffmpeg.get_ffmpeg_exe()
V = "output/videos"
QUEUE = [
    "%s/山海经鲧_AI漫剧版.mp4" % V,
    "%s/山海经女娲_AI漫剧版.mp4" % V,
    "%s/山海经娥皇女英_AI漫剧版.mp4" % V,
    "%s/山海经羲和_AI漫剧版.mp4" % V,
    "%s/山海经贰负_AI漫剧版.mp4" % V,
    "%s/山海经巫山神女_AI漫剧版.mp4" % V,
]
OUT = "output/videos/_ai_badge_crops"


def probe(path):
    r = subprocess.run([FF, "-hide_banner", "-i", path],
                       capture_output=True, text=True, encoding="utf-8", errors="ignore")
    err = r.stderr or ""
    m = re.search(r"Duration: (\d+):(\d+):([\d.]+)", err)
    dur = int(m.group(1)) * 3600 + int(m.group(2)) * 60 + float(m.group(3)) if m else 0
    meta = {}
    for k, v in re.findall(r"^\s{4}(\w+)\s*:\s*(.+?)\s*$", err, re.M):
        meta.setdefault(k, v)
    return dur, meta


def badge(path, dur, out):
    subprocess.run([FF, "-y", "-ss", "%.2f" % max(0.5, dur - 3), "-i", path,
                    "-frames:v", "1", "-vf", "crop=170:60:550:15", out],
                   capture_output=True)
    im = Image.open(out).convert("RGB")
    px = list(im.getdata())
    return sum(1 for p in px if min(p) > 200)


def main():
    files = [a for a in sys.argv[1:] if not a.startswith("-")] or QUEUE
    os.makedirs(OUT, exist_ok=True)
    print("%-34s %-8s %-10s %s" % ("file", "dur", "badge_px", "meta(AI?)"))
    for f in files:
        if not os.path.exists(f):
            print("%-34s MISSING" % os.path.basename(f))
            continue
        dur, meta = probe(f)
        crop = os.path.join(OUT, os.path.basename(f).replace(".mp4", "_badge.png"))
        n = badge(f, dur, crop)
        joined = " | ".join("%s=%s" % (k, v) for k, v in meta.items())
        ai = [k for k, v in meta.items() if "AI" in v or "AI" in k]
        print("%-34s %6.1fs %10d %s%s" % (
            os.path.basename(f), dur, n,
            "OK" if ai else "NO-AI-META",
            "  <- " + joined[:150] if "-v" in sys.argv else ""))
    print("crops ->", OUT)


if __name__ == "__main__":
    main()
