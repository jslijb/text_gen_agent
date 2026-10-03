# -*- coding: utf-8 -*-
"""山海经·应龙 —— AI 漫剧流水线（免费全片版，2026-09-24）

出处：《山海经·大荒东经》：应龙处南极，杀蚩尤与夸父，不得复上，故下数旱。
旱而为应龙之状，乃得大雨。
系列衔接：女魃（9/24 发）→ 相柳（9/25 发）→ 应龙（9/26 19:00-19:30 计划）。
女魃讲"雨止杀蚩尤"，本条回扣：真正动手的龙，杀完蚩尤与夸父后回不了天上。

规格：8 镜 / 目标 45-55 秒 / 金色羽翼神龙+战场剧情线 / 结尾开放式提问 + 预告饕餮。
额度纪律：0 付费额度——Agnes 免费首帧 + 免费 keyframe + edge-tts。
改进（源自相柳经验）：gen_voices 三层兜底（重试×3 → 备用音色 YunjianNeural → 静音垫 4.5s）。
"""
import asyncio
import io
import json
import os
import re
import subprocess
import time
import urllib.error
import urllib.parse
import urllib.request

import aiohttp.connector as _C
import aiohttp.resolver as _R
_C.DefaultResolver = _R.ThreadedResolver  # 本机 aiodns(c-ares) 损坏，必须绕过

import edge_tts
import imageio_ffmpeg

# ---------------- 常量 ----------------
def _load_agnes_key():
    env_path = r"D:\Python\text_gen_agent\backend\.env"
    with io.open(env_path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line.startswith("AGNES_KEY=") and not line.startswith("#"):
                return line.split("=", 1)[1].strip().strip('"').strip("'")
    return os.environ.get("AGNES_API_KEY", "")

AGNES = _load_agnes_key()
AGBASE = "https://api.agnes-ai.cn"
IMAGE_MODEL = "agnes-image-2.1-flash"
VIDEO_MODEL = "agnes-video-2.5-flash"

WORK = r"D:\Python\text_gen_agent\output\videos\Yinglong"
FRAMES = os.path.join(WORK, "frames")
RAW = os.path.join(WORK, "raw")
VOICE = os.path.join(WORK, "voice")
CLIPS = os.path.join(WORK, "clips")
FINAL = r"D:\Python\text_gen_agent\output\videos\山海经应龙_AI漫剧版.mp4"
LOG = os.path.join(WORK, "build_log.txt")
URLS_JSON = os.path.join(WORK, "urls.json")
FFMPEG = imageio_ffmpeg.get_ffmpeg_exe()
FONT_DIR = "C:/Windows/Fonts"
FONT_BOLD = "C:/Windows/Fonts/msyhbd.ttc"
W, H, FPS = 720, 1280, 30
XF = 0.5
LEAD = 0.5
PAD = 0.6

# 形象与画风锁死
DRAGON = ("上古神龙应龙：金色鳞甲，一对巨大的羽翼，鹿角鹰爪，龙须飘扬，"
          "身形修长矫健，神情威严疲惫")
STYLE = ("东方神话史诗电影质感，写实与水墨融合，色彩以青灰、赤金、墨黑为主，"
         "画面无任何文字水印logo")

VOICE_NAME = "zh-CN-YunxiNeural"
VOICE_BACKUP = "zh-CN-YunjianNeural"
ROLE_VOICE = {
    "narr": dict(rate="-5%", pitch="+0Hz"),
    "long": dict(rate="-10%", pitch="-14Hz"),  # 应龙：低沉男声变体（单语音包方案）
}
ROLE_COLOR = {
    "narr": "&H00FFFFFF",
    "long": "&H0046D2F0",   # 应龙 金色字幕（ASS 为 BBGGRR，#F0D246 → 46 D2 F0）
}

# ---------------- 分镜表（8 镜） ----------------
SHOTS = [
    dict(role="narr",
         img="竖版9:16。仰拍，暴雨云层中一条金色鳞甲巨龙展开双翼俯冲而下，"
             "羽翼遮天，闪电撕裂云层，水汽翻涌，" + DRAGON + "，" + STYLE,
         vprompt="参考图保持构图不变，巨龙双翼展开缓缓俯冲，闪电在云层间闪动，"
                 "雨丝斜飞，翼尖气流扰动云雾，仰拍镜头极缓拉远，写实电影质感，无文字",
         line="中国上古神话里，唯一一条长着翅膀的龙。"),
    dict(role="narr",
         img="竖版9:16。中景，冀州旷野战场，乌云压顶大雨倾盆，远处蚩尤军阵旌旗猎猎，"
             "一条金色巨龙盘旋于乌云之间若隐若现，" + STYLE,
         vprompt="参考图保持构图不变，龙影在乌云间缓缓盘旋上升，大雨倾泻，"
                 "旌旗在风中剧烈摆动，中景镜头极缓推进，写实电影质感，无文字",
         line="黄帝与蚩尤决战冀州，蚩尤请来风伯雨师，纵起漫天大风雨。"),
    dict(role="narr",
         img="竖版9:16。远景，战场之上金色巨龙张口引出巨大水柱，与暴风雨对抗，"
             "水汽与乌云缠绕成柱，天地间水光接天，克制无血腥，" + STYLE,
         vprompt="参考图保持构图不变，水柱缓缓旋转上升，乌云被搅动翻涌，"
                 "水汽弥漫流动，远景固定镜头极缓推近，写实电影质感，无文字",
         line="应龙畜水迎战，硬扛风伯雨师。"),
    dict(role="long",
         img="竖版9:16。近景，金色巨龙头部特写，金色竖瞳锐利，龙须飘扬，"
             "张口露齿低吼，雨水顺鳞片滑落，" + DRAGON + "，" + STYLE,
         vprompt="参考图中的巨龙保持外形不变，龙须飘动，雨水顺鳞片流淌，"
                 "龙口微张低吼，热气从龙口散出，近景镜头极缓推近，写实电影质感，无文字",
         line="蚩尤、夸父，一个都走不了。"),
    dict(role="narr",
         img="竖版9:16。远景，战场上两个巨人身影相继倒下扬起漫天尘土，"
             "金色巨龙在半空盘旋俯瞰，天色赤金转昏黄，克制无血腥，" + STYLE,
         vprompt="参考图保持构图不变，尘土缓缓扬起扩散，巨龙在空中缓慢盘旋，"
                 "残旌随风摆动，远景固定镜头，写实电影质感，无文字",
         line="《大荒东经》：应龙杀蚩尤与夸父。"),
    dict(role="long",
         img="竖版9:16。仰拍，暮色中云层深处一道天门光缝渐渐闭合熄灭，"
             "金色巨龙悬停半空仰望，双翼仍展开着，" + DRAGON + "，" + STYLE,
         vprompt="参考图中的巨龙保持外形不变，天门光缝缓缓收窄熄灭，"
                 "巨龙双翼微颤悬停不动，仰拍固定镜头极缓拉远，写实电影质感，无文字",
         line="仗打完了。翅膀还在，天，回不去了。"),
    dict(role="narr",
         img="竖版9:16。远景，南方水乡烟雨迷蒙，金色巨龙盘卧于云雾缭绕的山脊上，"
             "山下江河纵横村落安详，" + DRAGON + "，" + STYLE,
         vprompt="参考图保持构图不变，云雾在山间缓缓流动，细雨落江面泛起涟漪，"
                 "巨龙鳞光随呼吸明灭，远景镜头极缓横移，写实电影质感，无文字",
         line="它留在南方不再离去，从此南方多雨，北方常旱。"),
    dict(role="narr",
         img="竖版9:16。中景，干旱龟裂的大地上村民举着草扎的龙形图腾起舞求雨，"
             "尘土飞扬，远处天边乌云初聚透出一丝金光，克制无暴力，" + STYLE,
         vprompt="参考图保持构图不变，尘土随舞步扬起，草龙图腾轻轻晃动，"
                 "天边乌云缓缓聚拢金光渐亮，中景镜头极缓拉远，写实电影质感，无文字",
         line="大旱的年头，人们扮成它的样子求雨。你觉得应龙是英雄，还是一把用完就收的刀？明天讲，饕餮。"),
]

AI_META = {
    "title": "山海经应龙：杀蚩尤的龙，回不了天上",
    "artist": "AI生成",
    "comment": "AI生成合成内容",
    "description": "本视频画面由 AI 生成合成，已按《人工智能生成合成内容标识办法》添加隐式标识",
    "genre": "AI生成合成内容",
}

PUBLISH = {
    "title": "杀掉蚩尤的龙，再也回不了天上｜山海经·应龙",
    "desc": ("《山海经·大荒东经》：应龙处南极，杀蚩尤与夸父，不得复上，故下数旱。"
             "旱而为应龙之状，乃得大雨。帮黄帝打赢决战的有翼神龙，为何回不了天上？"
             "你觉得应龙是英雄，还是一把用完就收的刀？明天讲，饕餮。"
             "#山海经 #应龙 #AI经典奇谈 #神话"),
}


# ---------------- 基础 ----------------
def P(s=""):
    try:
        with io.open(LOG, "a", encoding="utf-8") as f:
            f.write(str(s) + "\n")
    except Exception:
        pass
    try:
        print(s)
    except Exception:
        print(str(s).encode("ascii", "replace").decode("ascii"))


def http(url, body=None, method="GET", key=None, timeout=120):
    h = {"Content-Type": "application/json", "User-Agent": "Mozilla/5.0"}
    if key:
        h["Authorization"] = "Bearer " + key
    data = json.dumps(body).encode("utf-8") if body is not None else None
    r = urllib.request.Request(url, data=data, headers=h, method=method)
    try:
        with urllib.request.urlopen(r, timeout=timeout) as resp:
            return resp.status, resp.read().decode("utf-8", "ignore")
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode("utf-8", "ignore")
    except Exception as e:
        return -1, "%s: %s" % (type(e).__name__, e)


def download(url, path, min_size=50000):
    for a in range(3):
        try:
            d = urllib.request.urlopen(
                urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"}),
                timeout=300).read()
            if len(d) < min_size:
                raise RuntimeError("内容过小 %d" % len(d))
            with open(path, "wb") as f:
                f.write(d)
            return True
        except Exception as e:
            P("    下载失败#%d %s: %s" % (a, type(e).__name__, str(e)[:120]))
            time.sleep(6)
    return False


def load_json(path, default):
    if os.path.exists(path):
        try:
            with io.open(path, encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return default


def save_json(path, obj):
    with io.open(path, "w", encoding="utf-8") as f:
        json.dump(obj, f, ensure_ascii=False, indent=1)


# ---------------- 阶段1：edge-tts 配音（三层兜底） ----------------
def wav_duration(p):
    r = subprocess.run([FFMPEG, "-i", p], capture_output=True, text=True,
                       encoding="utf-8", errors="ignore")
    m = re.search(r"Duration: (\d+):(\d+):([\d.]+)", r.stderr)
    return round(int(m.group(1)) * 3600 + int(m.group(2)) * 60 + float(m.group(3)), 2) if m else 0.0


async def tts_one(line, v, mp3):
    c = edge_tts.Communicate(line, v["name"], rate=v["rate"], pitch=v["pitch"])
    await c.save(mp3)


async def gen_voices():
    os.makedirs(VOICE, exist_ok=True)
    for i, s in enumerate(SHOTS):
        dst = os.path.join(VOICE, "v%02d.wav" % i)
        if os.path.exists(dst) and os.path.getsize(dst) > 5000:
            P("  [%d] 配音复用 %.2fs %s" % (i + 1, wav_duration(dst), s["line"]))
            continue
        v = ROLE_VOICE[s["role"]]
        mp3 = os.path.join(WORK, "voice_tmp_%d.mp3" % i)
        ok = False
        # 三层兜底：主音色重试×3 → 备用音色×2 → 静音垫 4.5s
        for attempt in range(3):
            try:
                await tts_one(s["line"], dict(v, name=VOICE_NAME), mp3)
                if os.path.exists(mp3) and os.path.getsize(mp3) > 3000:
                    ok = True
                    break
            except Exception as e:
                P("    [%d] tts重试%d %s: %s" % (i + 1, attempt + 1, type(e).__name__, str(e)[:80]))
                await asyncio.sleep(3 * (attempt + 1))
        if not ok:
            for attempt in range(2):
                try:
                    await tts_one(s["line"], dict(v, name=VOICE_BACKUP), mp3)
                    if os.path.exists(mp3) and os.path.getsize(mp3) > 3000:
                        P("    [%d] 备用音色救回" % (i + 1))
                        ok = True
                        break
                except Exception as e:
                    P("    [%d] 备用音色重试%d: %s" % (i + 1, attempt + 1, str(e)[:80]))
                    await asyncio.sleep(3)
        subprocess.run([FFMPEG, "-y", "-i", mp3, "-ar", "44100", "-ac", "1",
                        "-c:a", "pcm_s16le", dst], capture_output=True, text=True,
                       encoding="utf-8", errors="ignore")
        if os.path.exists(mp3):
            os.remove(mp3)
        if not ok or not os.path.exists(dst) or os.path.getsize(dst) < 5000:
            P("    [%d] >>> 配音全失败，静音垫 4.5s 兜底" % (i + 1))
            subprocess.run([FFMPEG, "-y", "-f", "lavfi", "-i", "anullsrc=r=44100:cl=mono",
                            "-t", "4.5", "-c:a", "pcm_s16le", dst],
                           capture_output=True, text=True, encoding="utf-8", errors="ignore")
        P("  [%d] 配音 %.2fs (%s) %s" % (i + 1, wav_duration(dst), s["role"], s["line"]))


# ---------------- 阶段2：Agnes 免费首帧 ----------------
def agnes_image(prompt, path):
    for a in range(4):
        st, txt = http(AGBASE + "/v1/images/generations",
                       {"model": IMAGE_MODEL, "prompt": prompt, "size": "720x1280"},
                       method="POST", key=AGNES, timeout=300)
        if st != 200:
            P("    agnes图 HTTP %s %s" % (st, txt[:140]))
            time.sleep(45 if st == 429 else 12)
            continue
        try:
            url = json.loads(txt)["data"][0]["url"]
        except Exception:
            continue
        if download(url, path):
            P("    首帧图 OK %d KB" % (os.path.getsize(path) // 1024))
            return url
    return None


# ---------------- 阶段3：Agnes 免费视频段 ----------------
def agnes_video(img_url, prompt, out):
    for rnd in range(6):
        st, txt = http(AGBASE + "/v1/videos",
                       {"model": VIDEO_MODEL, "prompt": prompt, "seconds": "5",
                        "mode": "keyframe", "size": "720P", "aspect_ratio": "9:16",
                        "first_frame": img_url},
                       method="POST", key=AGNES, timeout=120)
        if st != 200:
            P("      agnes提交 HTTP %s: %s" % (st, txt.replace("\n", " ")[:180]))
            time.sleep(60 if st in (429, 503) else 20)
            continue
        vid = None
        try:
            j = json.loads(txt)
            vid = j.get("video_id") or j.get("id") or j.get("task_id")
        except Exception:
            pass
        if not vid:
            time.sleep(15)
            continue
        P("      agnes video_id=%s" % vid)
        url, delay, t0 = None, 8, time.time()
        while time.time() - t0 < 1500:
            qs = urllib.parse.urlencode({"video_id": vid, "model_name": VIDEO_MODEL})
            st2, txt2 = http(AGBASE + "/agnesapi?" + qs, key=AGNES, timeout=60)
            if st2 == 429:
                delay = min(delay * 2, 60)
                time.sleep(delay)
                continue
            s = "?"
            try:
                j2 = json.loads(txt2)
                s = j2.get("status", "?")
                if s == "completed":
                    url = j2.get("url") or (j2.get("metadata") or {}).get("url")
            except Exception:
                pass
            if s == "completed":
                break
            if s == "failed":
                P("      agnes任务失败: %s" % txt2[:160])
                break
            time.sleep(delay)
        if url and download(url, out, min_size=200000):
            P("      ✓ 出片 %d KB" % (os.path.getsize(out) // 1024))
            return True
        time.sleep(30)
    return False


# ---------------- 阶段4：流畅合成 ----------------
def esc(p):
    return p.replace("\\", "/").replace(":", "\\:")


def media_duration(path):
    r = subprocess.run([FFMPEG, "-i", path], capture_output=True, text=True,
                       encoding="utf-8", errors="ignore")
    m = re.search(r"Duration: (\d+):(\d+):([\d.]+)", r.stderr)
    return int(m.group(1)) * 3600 + int(m.group(2)) * 60 + float(m.group(3)) if m else 0.0


def build_clips(targets):
    os.makedirs(CLIPS, exist_ok=True)
    for i, s in enumerate(SHOTS):
        out = os.path.join(CLIPS, "c%02d.mp4" % i)
        target = targets[i]
        if os.path.exists(out) and abs(media_duration(out) - target) < 0.2:
            P("  [%d] 复用 %.2fs" % (i + 1, target))
            continue
        raw = os.path.join(RAW, "r%02d.mp4" % i)
        voice = os.path.join(VOICE, "v%02d.wav" % i)
        rdur = media_duration(raw)
        speed = target / rdur if rdur > 0 else 1.0
        srt = os.path.join(CLIPS, "s%02d.srt" % i)
        end = int(target * 1000)
        ts = "00:00:00,000 --> 00:%02d:%02d,%03d" % (end // 60000, (end // 1000) % 60, end % 1000)
        with io.open(srt, "w", encoding="utf-8") as f:
            f.write("1\n%s\n%s\n" % (ts, s["line"]))
        style = ("FontName=Microsoft YaHei,FontSize=17,PrimaryColour=%s,"
                 "OutlineColour=&H00000000,BorderStyle=1,Outline=2,Shadow=0,"
                 "Alignment=2,MarginV=90" % ROLE_COLOR[s["role"]])
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
            P("  [%d] 合成失败: %s" % (i + 1, r.stderr[-400:]))
            raise SystemExit(1)
        P("  [%d] %.2fs (配音%.2fs 慢放x%.2f)" % (i + 1, target, media_duration(voice), speed))


def concat_final(n, targets):
    inputs = []
    for i in range(n):
        inputs += ["-i", os.path.join(CLIPS, "c%02d.mp4" % i)]
    fc = []
    for i in range(n):
        fc.append("[%d:v]setsar=1[v%d]" % (i, i))
    offset, total = 0.0, targets[0]
    for i in range(n - 1):
        offset = round(total - XF, 3)
        src0 = "v%d" % i if i == 0 else "vx%d" % (i - 1)
        fc.append("[%s][v%d]xfade=transition=fade:duration=%.2f:offset=%.3f[vx%d]"
                  % (src0, i + 1, XF, offset, i))
        total = round(offset + targets[i + 1], 3)
    for i in range(n):
        fc.append("[%d:a]anull[a%d]" % (i, i))
    prev = "a0"
    for i in range(n - 1):
        out_a = "ax%d" % i
        fc.append("[%s][a%d]acrossfade=d=%.2f:c1=tri:c2=tri[%s]" % (prev, i + 1, XF, out_a))
        prev = out_a
    fc.append("[%s]anull[aout]" % prev)
    total_out = round(sum(targets) - XF * (n - 1), 2)
    cmd = ([FFMPEG, "-y"] + inputs +
           ["-filter_complex", ";".join(fc),
            "-map", "[vx%d]" % (n - 2), "-map", "[aout]",
            "-t", "%.2f" % total_out,
            "-c:v", "libx264", "-preset", "medium", "-crf", "20", "-pix_fmt", "yuv420p",
            "-r", str(FPS), "-c:a", "aac", "-b:a", "128k", "-ar", "44100", "-ac", "2",
            "-movflags", "+faststart", FINAL])
    r = subprocess.run(cmd, capture_output=True, text=True,
                       encoding="utf-8", errors="ignore")
    if r.returncode != 0:
        P("拼接失败: " + r.stderr[-800:])
        raise SystemExit(1)


def tag_ai_metadata(path):
    tmp = path + ".tagged.mp4"
    cmd = [FFMPEG, "-y", "-i", path, "-c", "copy"]
    for k, v in AI_META.items():
        cmd += ["-metadata", "%s=%s" % (k, v)]
    cmd += ["-movflags", "+faststart", tmp]
    r = subprocess.run(cmd, capture_output=True, text=True,
                       encoding="utf-8", errors="ignore")
    if r.returncode == 0 and os.path.exists(tmp) and os.path.getsize(tmp) > 100000:
        os.replace(tmp, path)
        P("AI 隐式标识已写入元数据")


# ---------------- 主流程 ----------------
def main():
    for d in (FRAMES, RAW, VOICE, CLIPS):
        os.makedirs(d, exist_ok=True)
    t0 = time.time()
    n = len(SHOTS)
    P("=" * 70)
    P("山海经·应龙 免费全片流水线启动 %s（8镜 / 目标45-55s / 0 付费额度）"
      % time.strftime("%H:%M:%S"))
    P("=" * 70)

    P("\n阶段 1/4 配音 (edge-tts)")
    asyncio.run(gen_voices())

    P("\n阶段 2/4 首帧图 (Agnes 免费)")
    urls = load_json(URLS_JSON, {})
    for i, s in enumerate(SHOTS):
        ip = os.path.join(FRAMES, "f%02d.png" % i)
        if urls.get(str(i)) and os.path.exists(ip) and os.path.getsize(ip) > 50000:
            s["img_url"] = urls[str(i)]
            P("  [%d] 复用已有首帧" % (i + 1))
            continue
        url = agnes_image(s["img"], ip)
        s["img_url"] = url
        if url:
            urls[str(i)] = url
            save_json(URLS_JSON, urls)
        else:
            P("  [%d] >>> 首帧失败，留待重跑" % (i + 1))
        time.sleep(8)

    P("\n阶段 3/4 视频段 (Agnes 免费 keyframe)")
    for i, s in enumerate(SHOTS):
        out = os.path.join(RAW, "r%02d.mp4" % i)
        if os.path.exists(out) and os.path.getsize(out) > 200000:
            P("  [%d] 已有片段，跳过" % (i + 1))
            continue
        if not s.get("img_url"):
            P("  [%d] 无首帧直链，跳过（重跑补）" % (i + 1))
            continue
        P("  [%d] %s" % (i + 1, s["line"]))
        if not agnes_video(s["img_url"], s["vprompt"], out):
            P("  [%d] >>> 该镜未出片，留待重跑" % (i + 1))
        time.sleep(15)

    done = sum(1 for i in range(n)
               if os.path.exists(os.path.join(RAW, "r%02d.mp4" % i))
               and os.path.getsize(os.path.join(RAW, "r%02d.mp4" % i)) > 200000)
    P("\n阶段 3 结束：%d/%d 段成功" % (done, n))

    ok = [i for i in range(n)
          if os.path.exists(os.path.join(RAW, "r%02d.mp4" % i))
          and os.path.getsize(os.path.join(RAW, "r%02d.mp4" % i)) > 200000
          and os.path.exists(os.path.join(VOICE, "v%02d.wav" % i))]
    if len(ok) < n:
        P(">>> 仅 %d/%d 镜可用；重跑本脚本续补缺失镜" % (len(ok), n))
        return 1

    P("\n阶段 4/4 流畅合成（段长跟配音 + 慢放 + 交叉溶解）")
    targets = []
    for i in range(n):
        vdur = media_duration(os.path.join(VOICE, "v%02d.wav" % i))
        targets.append(round(vdur + PAD + LEAD, 2))
    build_clips(targets)
    concat_final(n, targets)
    P("\n成片: %s" % FINAL)
    P("时长 %.1fs | %.2f MB" % (media_duration(FINAL), os.path.getsize(FINAL) / 1048576))
    tag_ai_metadata(FINAL)
    P("发布建议：9/26 19:00-19:30 定时发布（女魃9/24 → 相柳9/25 → 应龙9/26）｜标题：%s"
      % PUBLISH["title"])
    P("ALL DONE 总耗时 %.1f 分钟" % ((time.time() - t0) / 60.0))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
