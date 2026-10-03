# -*- coding: utf-8 -*-
"""TTS 实测：给定候选台词，用流水线同款音色生成并测时长。"""
import asyncio
import io
import os
import re
import subprocess
import aiohttp.connector as _C
import aiohttp.resolver as _R
_C.DefaultResolver = _R.ThreadedResolver  # 本机 aiodns(c-ares) 损坏，必须绕过

import edge_tts
import imageio_ffmpeg

FFMPEG = imageio_ffmpeg.get_ffmpeg_exe()
VOICE = "zh-CN-YunxiNeural"
RATE, PITCH = "-5%", "+0Hz"
TMP = r"D:\Python\text_gen_agent\output\videos\_ttsprobe"
os.makedirs(TMP, exist_ok=True)


def dur(p):
    r = subprocess.run([FFMPEG, "-i", p], capture_output=True, text=True,
                       encoding="utf-8", errors="ignore")
    m = re.search(r"Duration: (\d+):(\d+):([\d.]+)", r.stderr)
    return round(int(m.group(1)) * 3600 + int(m.group(2)) * 60 + float(m.group(3)), 2) if m else 0.0


async def one(i, line):
    mp3 = os.path.join(TMP, "t%d.mp3" % i)
    wav = os.path.join(TMP, "t%d.wav" % i)
    await edge_tts.Communicate(line, VOICE, rate=RATE, pitch=PITCH).save(mp3)
    subprocess.run([FFMPEG, "-y", "-i", mp3, "-ar", "44100", "-ac", "1",
                    "-c:a", "pcm_s16le", wav], capture_output=True)
    d = dur(wav)
    flag = "OK" if d <= 6.0 else "XX"
    print("%s %5.2fs | %s" % (flag, d, line))


async def main():
    cands = [
        # 镜2 候选
        "《大荒北经》说：蚩尤作兵——兵器，是他先造的。",
        "古书说：蚩尤作兵——第一件兵器，是他造的。",
        "《大荒北经》说：蚩尤作兵伐黄帝，兵器是他造的。",
        "史书只记一句：蚩尤作兵，兵器是他先造的。",
        "第一件兵器，就是蚩尤造的。",
        # 镜6 候选
        "《大荒北经》：应龙攻之，遂杀蚩尤。兵器之王，败了。",
        "应龙攻之，遂杀蚩尤——兵器之王，败了。",
        "巨龙俯冲而下——兵器之王，败了。",
        "应龙自天而降——兵器之王，第一次败了。",
        "应龙攻之，遂杀蚩尤。",
    ]
    for i, c in enumerate(cands):
        try:
            await one(i, c)
        except Exception as e:
            print("ERR", c, str(e)[:60])
        await asyncio.sleep(1)


if __name__ == "__main__":
    asyncio.run(main())
