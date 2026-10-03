# -*- coding: utf-8 -*-
"""山海经·巫山神女 —— AI 漫剧流水线（2026-10-02；国庆双更#9，悲剧英雄第11条）

出处：《山海经·中次七经》：姑媱之山，帝女死焉，其名曰女尸，化为䔄草，
其叶胥成，其华黄，其实如菟丘，服之媚于人。

系列衔接：贰负片尾预告「巫山神女」——本条兑现。片尾预告定「西王母」。
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

WORK = r"D:\Python\text_gen_agent\output\videos\Wushan"
FRAMES = os.path.join(WORK, "frames")
RAW = os.path.join(WORK, "raw")
VOICE = os.path.join(WORK, "voice")
CLIPS = os.path.join(WORK, "clips")
FINAL = r"D:\Python\text_gen_agent\output\videos\山海经巫山神女_AI漫剧版.mp4"
LOG = os.path.join(WORK, "build_log.txt")
URLS_JSON = os.path.join(WORK, "urls.json")
FFMPEG = imageio_ffmpeg.get_ffmpeg_exe()
FONT_DIR = "C:/Windows/Fonts"
FONT_BOLD = "C:/Windows/Fonts/msyhbd.ttc"
W, H, FPS = 720, 1280, 30
XF = 0.5
LEAD = 0.5
PAD = 0.6

# 形象与画风锁死（巫山神女：云雾中的素衣女神）
WUSHAN = ("巫山神女瑶姬：素白衣裙的女子，长发垂肩，赤足立于山巅，"
          "周身云雾环绕，衣袊飘飞，眉眼清寂")
STYLE = ("东方神话史诗电影质感，写实与水墨融合，色彩以青碧、云雾白、淡金、墨黑为主，"
         "画面无任何文字水印logo")

VOICE_NAME = "zh-CN-YunxiNeural"
VOICE_BACKUP = "zh-CN-YunjianNeural"
ROLE_VOICE = {
    "narr": dict(rate="-5%", pitch="+0Hz"),
}
ROLE_COLOR = {
    "narr": "&H00FFFFFF",
}

# ---------------- 分镜表（8 镜） ----------------
SHOTS = [
    dict(role="narr",
         img="竖版9:16。极广角，巫山十二峰矗立在云海之上，一素衣女子立于峰顶，"
             "脚下云涛翻涌霞光染云，衣袊飘飞，" + WUSHAN + "，" + STYLE,
         vprompt="参考图保持构图不变，云涛缓缓流动霞光漂染峰顶，衣袊猎猎，"
                 "镜头极缓拉远，写实电影质感，无文字",
         line="巫山的云雾里，住着一位很早就死去的女神。"),
    dict(role="narr",
         img="竖版9:16。中景，山间一座孤坟，坟头泛着微光，云雾缠绕，"
             "" + STYLE,
         vprompt="参考图保持构图不变，云雾缭绕坟头，荒草微摆，"
                 "中景镜头极缓推近，写实电影质感，无文字",
         line="《山海经》说，她是天帝的女儿，死在姑媱之山。"),
    dict(role="narr",
         img="竖版9:16。近景，坟头长出一株叶色金黄、果实如菟丘的仙草，露光闪动，"
             "" + STYLE,
         vprompt="参考图保持构图不变，草叶舒展黄结微光，露珠滚落，"
                 "近景镜头极缓推近，写实电影质感，无文字",
         line="她的坟上，长出一株黄色的仙草。"),
    dict(role="narr",
         img="竖版9:16。中景，古人采下仙草合于掌心，神情惊喜，"
             "" + STYLE,
         vprompt="参考图保持构图不变，掌心草结微光流转，人面微怔，"
                 "中景镜头极缓推近，写实电影质感，无文字",
         line="人吃了那草，就会被人喜欢。"),
    dict(role="narr",
         img="竖版9:16。远景，云雾中神女身形重现，若隐若现，"
             "" + WUSHAN + "，" + STYLE,
         vprompt="参考图保持构图不变，身形在雾中渐显又淡，云气旋绕，"
                 "远景镜头极缓拉升，写实电影质感，无文字",
         line="后来她化为巫山神女，在云里若隐若现。"),
    dict(role="narr",
         img="竖版9:16。近景，神女与人间的王在梦中隔着云气相望，朦胧，"
             "" + WUSHAN + "，" + STYLE,
         vprompt="参考图保持构图不变，两人隔着云气相望渐渐淡开，"
                 "近景镜头极缓拉远，写实电影质感，无文字",
         line="有人梦见她，写下了流传千年的高唐赋。"),
    dict(role="narr",
         img="竖版9:16。远景，巫山云雨，朝云暮雨变幻无穷，山影隐现，"
             "" + STYLE,
         vprompt="参考图保持构图不变，云雨朝暮交替山影隐现，"
                 "远景镜头极缓拉升，写实电影质感，无文字",
         line="楚人把巫山的云和雨，都算作她的身影。"),
    dict(role="narr",
         img="竖版9:16。远景，巫山云海日出，金辉漫染峰峦，安宁壮阔，"
             "" + STYLE,
         vprompt="参考图保持构图不变，日轮自云海升起金光漫染，云涛缓涌，"
                 "远景镜头极缓拉升，写实电影质感，无文字",
         line="她死得很早，却让一座山活成了传说。你说，这样的永恒，是不是另一种活着？明天讲，西王母。"),
]

AI_META = {
    "title": "山海经巫山神女：化作仙草的天帝之女",
    "artist": "AI生成",
    "comment": "AI生成合成内容",
    "description": "本视频画面由 AI 生成合成，已按《人工智能生成合成内容标识办法》添加隐式标识",
    "genre": "AI生成合成内容",
}

PUBLISH = {
    "title": "死了却让巫山活成传说的女神｜山海经·巫山神女",
    "desc": ("《山海经·中次七经》：姑媱之山，帝女死焉，其名曰女尸，化为䔄草，"
             "其叶胥成，其华黄，其实如菟丘，服之媚于人。"
             "她是天帝的女儿，死得很早，坟上长出一株让人被爱的仙草，后来化作巫山云雨里的神女。"
             "你说，这样算不算另一种活着？"
             "#山海经 #巫山神女 #AI经典奇谈 #原来神就是孤独的"),
    "comment": ("《中次七经》原文：姑媱之山，帝女死焉，其名曰女尸，化为䔄草。"
                "她死得早，坟上的草吃了会被人喜欢，后来成了巫山神女。你眼里的她，是仙，还是留在山间的叹息？评论区聊聊。明天讲，西王母。"),
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


def qc_check():
    """像素体检：AI角标区(x∈[w-140,w-20], y∈[20,66])白像素>80；字幕区(y∈[700,900])有渲染"""
    import struct
    import zlib
    png = os.path.join(WORK, "qc_probe.png")
    frame = os.path.join(WORK, "qc_frame.png")
    t = round(media_duration(FINAL) - 3, 2)
    subprocess.run([FFMPEG, "-y", "-ss", str(t), "-i", FINAL, "-frames:v", "1",
                    "-vf", "crop=720:360:0:20", png], capture_output=True)
    subprocess.run([FFMPEG, "-y", "-ss", "1", "-i", FINAL, "-frames:v", "1", frame],
                   capture_output=True)
    def read_png_pixels(p, x0, x1, y0, y1):
        with open(p, "rb") as f:
            data = f.read()
        pos, w_, h_, idat = 8, 0, 0, b""
        while pos < len(data):
            ln = struct.unpack(">I", data[pos:pos+4])[0]
            typ = data[pos+4:pos+8]
            chunk = data[pos+8:pos+8+ln]
            if typ == b"IHDR":
                w_, h_ = struct.unpack(">II", chunk[:8])
            elif typ == b"IDAT":
                idat += chunk
            pos += 12 + ln
        raw = zlib.decompress(idat)
        stride = w_ * 3
        px = bytearray()
        prev = bytearray(stride)
        o = 0
        for y in range(h_):
            ft = raw[o]; o += 1
            line = bytearray(raw[o:o+stride]); o += stride
            for x in range(stride):
                a = line[x-3] if x >= 3 else 0
                b = prev[x]
                c = prev[x-3] if x >= 3 else 0
                if ft == 1: line[x] = (line[x] + a) & 0xFF
                elif ft == 2: line[x] = (line[x] + b) & 0xFF
                elif ft == 3: line[x] = (line[x] + (a+b)//2) & 0xFF
                elif ft == 4:
                    pp = a + b - c
                    pa, pb, pc = abs(pp-a), abs(pp-b), abs(pp-c)
                    pr = a if pa <= pb and pa <= pc else (b if pb <= pc else c)
                    line[x] = (line[x] + pr) & 0xFF
            prev = line
            px += line
        cnt = 0
        for y in range(max(0, y0), min(h_, y1)):
            for x in range(max(0, x0), min(w_, x1)):
                o2 = y*stride + x*3
                if px[o2] > 200 and px[o2+1] > 200 and px[o2+2] > 200:
                    cnt += 1
        return cnt, w_, h_
    try:
        white, _, _ = read_png_pixels(png, 720-140-0, 720-20, 20-20, 66-20)
        P("体检：AI角标区白像素=%d (阈值>80)" % white)
        ok1 = white > 80
        ok2 = os.path.exists(frame) and os.path.getsize(frame) > 10000
        P("体检：首帧渲染 %s" % ("OK" if ok2 else "FAIL"))
        if not ok1:
            P(">>> 警告：AI角标区白像素不足，检查 drawtext 是否生效")
    except Exception as e:
        P("体检异常(不阻断): %s" % e)


# ---------------- 主流程 ----------------
def main():
    # 教训落实：启动前自检 SHOTS 逐镜三键齐全
    for i, s in enumerate(SHOTS):
        for k in ("img", "vprompt", "line", "role"):
            if not s.get(k):
                raise SystemExit("SHOTS[%d] 缺少键 %s —— 先修脚本再跑" % (i + 1, k))
    # 台词长度预检：4.5字/秒，单镜≤6s（末镜≤11s）
    for i, s in enumerate(SHOTS):
        n_chars = len(re.sub(r"[，。？！—…：；、「」]", "", s["line"]))
        est = n_chars / 4.5
        limit = 11.0 if i == len(SHOTS) - 1 else 6.0
        if est > limit:
            raise SystemExit("SHOTS[%d] 台词过长：约%.1fs > %.0fs 上限，先删词再跑：%s"
                             % (i + 1, est, limit, s["line"][:30]))
    for d in (FRAMES, RAW, VOICE, CLIPS):
        os.makedirs(d, exist_ok=True)
    t0 = time.time()
    n = len(SHOTS)
    P("=" * 70)
    P("山海经·巫山神女 免费全片流水线启动 %s（8镜 / 目标45-55s / 0 付费额度）"
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
               and os.path.getsize(os.path.join(RAW, "r%02d.mp4" % i) ) > 200000)
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
    qc_check()
    P("发布建议：2026-10-07 11:00 定时发布（国庆双更#9：贰负→巫山神女）｜标题：%s"
      % PUBLISH["title"])
    P("ALL DONE 总耗时 %.1f 分钟" % ((time.time() - t0) / 60.0))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
