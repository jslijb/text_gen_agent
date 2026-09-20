# -*- coding: utf-8 -*-
"""edge-tts 神经语音配音生成器（替代 SAPI 机械女声）
用法：改 LINES 与 VOICE_DIR 后直接运行。输出 44100Hz 单声道 wav。
关键坑：本机 aiodns(c-ares) 损坏，必须在创建连接前把
aiohttp.connector.DefaultResolver 换成 ThreadedResolver，否则 DNS 全挂。
角色台词区分：line 为 dict 时可带 rate/pitch（如旁白 rate=-4%，角色 rate=-12% pitch=-8Hz）。
"""
import asyncio
import os
import subprocess
import tempfile

import aiohttp.connector as _C
import aiohttp.resolver as _R
_C.DefaultResolver = _R.ThreadedResolver  # 绕过损坏的 aiodns

import edge_tts
import imageio_ffmpeg

VOICE_NAME = "zh-CN-YunxiNeural"   # 年轻男声，叙事自然；备选 zh-CN-YunjianNeural(更低沉)
VOICE_DIR = r"D:\Python\text_gen_agent\output\videos\baize\voice"
FFMPEG = imageio_ffmpeg.get_ffmpeg_exe()

# 白泽 8 句（与 _make_baize_smooth.py 的 LINES 一字不差）
LINES = [
    "传说黄帝在东海，见过一只神兽。",
    "它叫白泽，浑身雪白，额生独角。",
    "它能说人话，认得天下一万一千种精怪。",
    "妖影万千它全认得，你认识几个？",
    "黄帝请它讲天下鬼神，一万一千五百二十种。",
    "黄帝把《白泽图》传遍天下。",
    "古人把它画在门上，妖怪见了绕道走。",
    "点赞收藏保平安，明天讲九尾狐。",
]


def _wav_duration(p):
    r = subprocess.run([FFMPEG, "-i", p], capture_output=True, text=True,
                       encoding="utf-8", errors="ignore")
    import re
    m = re.search(r"Duration: (\d+):(\d+):([\d.]+)", r.stderr)
    return round(int(m.group(1)) * 60 + float(m.group(3)), 2) if m else 0.0


async def gen():
    bak = VOICE_DIR + "_sapi"
    os.makedirs(bak, exist_ok=True)
    os.makedirs(VOICE_DIR, exist_ok=True)
    for i, line in enumerate(LINES):
        dst = os.path.join(VOICE_DIR, "v%02d.wav" % i)
        if isinstance(line, dict):
            text, rate, pitch = line["t"], line.get("rate", "+0%"), line.get("pitch", "+0Hz")
        else:
            text, rate, pitch = line, "-5%", "+0Hz"
        # 旧 SAPI 配音挪走备份，不覆盖
        if os.path.exists(dst):
            os.replace(dst, os.path.join(bak, "v%02d.wav" % i))
        mp3 = tempfile.mktemp(suffix=".mp3")
        c = edge_tts.Communicate(text, VOICE_NAME, rate=rate, pitch=pitch)
        await c.save(mp3)
        subprocess.run([FFMPEG, "-y", "-i", mp3, "-ar", "44100", "-ac", "1",
                        "-c:a", "pcm_s16le", dst], capture_output=True, text=True,
                       encoding="utf-8", errors="ignore")
        os.remove(mp3)
        print("[%d] %.2fs  %s" % (i, _wav_duration(dst), text))


asyncio.run(gen())
print("VOICE_EDGE_OK")
