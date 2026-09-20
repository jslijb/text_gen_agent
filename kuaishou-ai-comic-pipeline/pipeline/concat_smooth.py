# -*- coding: utf-8 -*-
"""白泽流畅版合成 v2 —— 修复段间卡顿
不调任何模型（raw/voice 全用缓存），只重做合成：
  1) 每段时长 = 配音时长 + 0.6s（消灭段尾死寂）
  2) 视频 setpts 慢放补齐（5s 原素材拉伸到段长，消灭循环跳变）
  3) 段间 xfade 0.5s 交叉溶解 + acrossfade 音频交叉淡化（消灭硬切）
成片: 山海经白泽_流畅版.mp4
"""
import io
import os
import re
import subprocess

import imageio_ffmpeg

WORK = r"D:\Python\text_gen_agent\output\videos\baize"
RAW = os.path.join(WORK, "raw")
VOICE = os.path.join(WORK, "voice")
CLIPS2 = os.path.join(WORK, "clips_v2")
FINAL = r"D:\Python\text_gen_agent\output\videos\山海经白泽_流畅版.mp4"
FFMPEG = imageio_ffmpeg.get_ffmpeg_exe()
FONT_DIR = "C:/Windows/Fonts"
FONT_BOLD = "C:/Windows/Fonts/msyhbd.ttc"
W, H, FPS = 720, 1280, 30
XF = 0.5          # 段间交叉溶解时长
LEAD = 0.5        # 人声前静音垫：段间音频交叉淡化只落在静音上，不吞字头
PAD = 0.6         # 每段配音后余量

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


LOGF = os.path.join(WORK, "smooth_log.txt")


def P(s=""):
    try:
        with io.open(LOGF, "a", encoding="utf-8") as f:
            f.write(str(s) + "\n")
    except Exception:
        pass
    try:
        print(s)
    except Exception:
        print(str(s).encode("ascii", "replace").decode("ascii"))


def media_duration(path):
    r = subprocess.run([FFMPEG, "-i", path], capture_output=True, text=True,
                       encoding="utf-8", errors="ignore")
    m = re.search(r"Duration: (\d+):(\d+):([\d.]+)", r.stderr)
    if m:
        return int(m.group(1)) * 3600 + int(m.group(2)) * 60 + float(m.group(3))
    return 0.0


def esc(p):
    return p.replace("\\", "/").replace(":", "\\:")


os.makedirs(CLIPS2, exist_ok=True)
targets = []
for i in range(8):
    raw = os.path.join(RAW, "r%02d.mp4" % i)
    voice = os.path.join(VOICE, "v%02d.wav" % i)
    vdur = media_duration(voice)
    target = round(vdur + PAD + LEAD, 2)
    targets.append(target)
    out = os.path.join(CLIPS2, "c%02d.mp4" % i)
    if os.path.exists(out) and abs(media_duration(out) - target) < 0.2:
        P("[%d] 复用 %.2fs" % (i, target))
        continue
    rdur = media_duration(raw)
    speed = target / rdur if rdur > 0 else 1.0
    srt = os.path.join(CLIPS2, "s%02d.srt" % i)
    end = int(target * 1000)
    ts = "00:00:00,000 --> 00:%02d:%02d,%03d" % (end // 60000, (end // 1000) % 60, end % 1000)
    with io.open(srt, "w", encoding="utf-8") as f:
        f.write("1\n%s\n%s\n" % (ts, LINES[i]))
    style = ("FontName=Microsoft YaHei,FontSize=17,PrimaryColour=&H00FFFFFF,"
             "OutlineColour=&H00000000,BorderStyle=1,Outline=2,Shadow=0,"
             "Alignment=2,MarginV=90")
    vf = ("[0:v]setpts=%.4f*PTS,fps=%d,scale=%d:%d:force_original_aspect_ratio=increase,"
          "crop=%d:%d,setsar=1,"
          "subtitles='%s':fontsdir='%s':force_style='%s',"
          "drawtext=fontfile='%s':text='AI生成':x=w-tw-24:y=28:fontsize=30:"
          "fontcolor=white@0.92:box=1:boxcolor=black@0.5:boxborderw=10,"
          "format=yuv420p[v];"
          "[1:a]aresample=44100,aformat=sample_fmts=fltp:channel_layouts=stereo,"
          "adelay=%d|%d,apad=whole_dur=%.2f[a]"
          % (speed, FPS, W, H, W, H, esc(srt), esc(FONT_DIR), style,
             esc(FONT_BOLD), int(LEAD * 1000), int(LEAD * 1000), target))
    cmd = [FFMPEG, "-y", "-i", raw, "-i", voice,
           "-filter_complex", vf, "-map", "[v]", "-map", "[a]",
           "-t", "%.2f" % target,
           "-c:v", "libx264", "-preset", "medium", "-crf", "20",
           "-c:a", "aac", "-b:a", "128k", "-ar", "44100", "-ac", "2",
           out]
    r = subprocess.run(cmd, capture_output=True, text=True,
                       encoding="utf-8", errors="ignore")
    if r.returncode != 0:
        P("[%d] 合成失败: %s" % (i, r.stderr[-400:]))
        raise SystemExit(1)
    P("[%d] %.2fs (配音%.2fs 慢放x%.2f)" % (i, target, vdur, speed))

# ---- xfade 链 ----
P("\n交叉溶解拼接...")
inputs = []
for i in range(8):
    inputs += ["-i", os.path.join(CLIPS2, "c%02d.mp4" % i)]
fc = []
offset = 0.0
total = targets[0]
for i in range(8):
    fc.append("[%d:v]setsar=1[v%d]" % (i, i))
for i in range(7):
    offset = round(total - XF, 3)
    src0 = "v%d" % i if i == 0 else "vx%d" % (i - 1)
    fc.append("[%s][v%d]xfade=transition=fade:duration=%.2f:offset=%.3f[vx%d]"
              % (src0, i + 1, XF, offset, i))
    total = round(offset + targets[i + 1], 3)
for i in range(8):
    fc.append("[%d:a]acrossfade" % i if False else "[%d:a]anull[a%d]" % (i, i))
prev = "a0"
for i in range(7):
    out_a = "ax%d" % i
    fc.append("[%s][a%d]acrossfade=d=%.2f:c1=tri:c2=tri[%s]" % (prev, i + 1, XF, out_a))
    prev = out_a
fc.append("[%s]anull[aout]" % prev)
filter_complex = ";".join(fc)
total_out = round(sum(targets) - XF * 7, 2)
cmd = ([FFMPEG, "-y"] + inputs +
       ["-filter_complex", filter_complex,
        "-map", "[vx6]", "-map", "[aout]",
        "-t", "%.2f" % total_out,
        "-c:v", "libx264", "-preset", "medium", "-crf", "20", "-pix_fmt", "yuv420p",
        "-r", str(FPS), "-c:a", "aac", "-b:a", "128k", "-ar", "44100", "-ac", "2",
        "-movflags", "+faststart", FINAL])
r = subprocess.run(cmd, capture_output=True, text=True,
                   encoding="utf-8", errors="ignore")
if r.returncode != 0:
    P("拼接失败: " + r.stderr[-800:])
    raise SystemExit(1)

P("\n成片: %s" % FINAL)
P("时长 %.1fs | %.2f MB | 段间交叉 %.1fs" %
  (media_duration(FINAL), os.path.getsize(FINAL) / 1048576, XF))
P("DONE")
