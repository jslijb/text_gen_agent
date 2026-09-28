# -*- coding: utf-8 -*-
"""山海经·梼杌 —— AI 漫剧流水线（免费全片版，2026-09-28；四凶收官）

出处：《神异经·西荒经》：西方荒中有兽焉，其状如虎而犬毛，长二尺，人面虎足，
猪牙，尾长一丈八尺，恃己强横，力能斗虎。名曰梼杌，一名傲狠，一名难训。
《左传·文公十八年》：颛顼有不才子，不可教训，不知话言，告之则顽，舍之则嚚，
傲狠明德，以乱天常，天下之民谓之梼杌。
《史记·五帝本纪》（背景）：舜请四凶族投诸四裔，以御螭魅。

系列衔接：女魃9/24 → 相柳9/25 → 应龙9/26 → 饕餮9/27 → 穷奇9/28 → 混沌9/29（待定）
→ 梼杌（9/30，本条）。混沌片尾已预告「明天讲，梼杌」——本条兑现预告链，
结尾预告新系列开篇：夸父逐日（大众认知度最高，按「选题救流量」标准选题）。

教训落实（9/28 经验清单裁决版）：
① 首镜「动作进行时」怼脸构图（4样本验证：2s跳出<15%起飞/24-27%扑）——
   首帧直接上梼杌人面怼脸+獠牙啃咬进行中，禁止远景定场/静态亮相；
② 中段每镜结尾半句钩子必须是「未完成动作」而非「氛围渲染」；
③ 镜7 原文卡加「分享诱因」改法（验证分享破零）；
④ SHOTS 逐镜三键齐全（img/vprompt/line，启动自检）；台词先控长再落盘；
   单镜配音 ≤6s（末镜 ≤11s）。
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

WORK = r"D:\Python\text_gen_agent\output\videos\Taowu"
FRAMES = os.path.join(WORK, "frames")
RAW = os.path.join(WORK, "raw")
VOICE = os.path.join(WORK, "voice")
CLIPS = os.path.join(WORK, "clips")
FINAL = r"D:\Python\text_gen_agent\output\videos\山海经梼杌_AI漫剧版.mp4"
LOG = os.path.join(WORK, "build_log.txt")
URLS_JSON = os.path.join(WORK, "urls.json")
FFMPEG = imageio_ffmpeg.get_ffmpeg_exe()
FONT_DIR = "C:/Windows/Fonts"
FONT_BOLD = "C:/Windows/Fonts/msyhbd.ttc"
W, H, FPS = 720, 1280, 30
XF = 0.5
LEAD = 0.5
PAD = 0.6

# 形象与画风锁死（梼杌：人面虎足猪牙犬毛长尾，傲狠难训）
TAOWU = ("上古凶兽梼杌：虎身覆着粗硬灰黑犬毛，人脸生在虎颈上，神情桀骜凶顽，"
         "嘴生外露野猪獠牙，人形双足兽爪，身后一条一丈八尺长尾如战旗横扫，"
         "周身灰黑煞气翻涌")
STYLE = ("东方神话史诗电影质感，写实与水墨融合，色彩以灰黑、暗金、铁锈红为主，"
         "画面无任何文字水印logo")

VOICE_NAME = "zh-CN-YunxiNeural"
VOICE_BACKUP = "zh-CN-YunjianNeural"
ROLE_VOICE = {
    "narr": dict(rate="-5%", pitch="+0Hz"),
}
ROLE_COLOR = {
    "narr": "&H00FFFFFF",
}

# ---------------- 分镜表（8 镜；逐镜三键：img/vprompt/line；全 narr） ----------------
# 教训①：镜1 动作进行时怼脸（獠牙啃咬中）；教训②：镜3-6结尾未完成动作钩子
SHOTS = [
    dict(role="narr",
         img="竖版9:16。极近怼脸特写，一张人脸与虎口合生的巨脸占满画面，野猪獠牙正"
             "死死咬进一杆铜戈，戈身弯折崩裂，火星飞溅，灰黑煞气扑面，压迫感极强，"
             "克制无血腥，" + TAOWU + "，" + STYLE,
         vprompt="参考图保持构图不变，獠牙咬碎铜戈火星四溅，铜戈崩断弯折，"
                 "煞气翻涌扑向镜头，怼脸特写镜头极缓推近，写实电影质感，无文字",
         line="四凶里最横的一只，连兵器都敢咬碎当饭吃。"),
    dict(role="narr",
         img="竖版9:16。中近景，灰黑虎身人面凶兽立于西荒戈壁，人面怒目圆睁，"
             "长尾如战旗横扫黄沙，天色铁灰，" + TAOWU + "，" + STYLE,
         vprompt="参考图保持构图不变，长尾横扫卷起黄沙，犬毛随风翻卷，"
                 "怒目直视镜头，中近景镜头极缓环绕，写实电影质感，无文字",
         line="《神异经》的西荒，有一头恃己强横、力能斗虎的凶兽。"),
    dict(role="narr",
         img="竖版9:16。中景，灰黑凶兽一爪把一头猛虎按倒在地，虎口微张无力反抗，"
             "黄沙飞扬，" + TAOWU + "，" + STYLE,
         vprompt="参考图保持构图不变，兽爪按虎缓缓发力下压，猛虎挣扎扬起黄沙，"
                 "长尾甩动，中景镜头极缓推近，写实电影质感，无文字",
         line="老虎在它面前就是猎物——可它最可怕的不是力气。"),
    dict(role="narr",
         img="竖版9:16。近景，颛顼宫中一名老臣对着稚童伸出手，稚童背身别过脸去，"
             "殿内烛火摇曳，气氛压抑，人物古风写实，" + STYLE,
         vprompt="参考图保持构图不变，老臣伸出的手缓缓收回，稚童背身别过脸，"
                 "烛火摇曳明灭，近景镜头极缓推近，写实电影质感，无文字",
         line="它是颛顼的不才子：教它规矩，它听不进。"),
    dict(role="narr",
         img="竖版9:16。中景，灰黑凶兽在荒村外横冲直撞，掀翻农舍土墙，尘土冲天，"
             "村民四散奔逃，克制无血腥，" + TAOWU + "，" + STYLE,
         vprompt="参考图保持构图不变，凶兽撞塌土墙尘土冲天，村民奔逃，"
                 "长尾扫飞杂物，中景镜头横向缓移，写实电影质感，无文字",
         line="教不会、听人劝——天下人叫它：滚刀肉。"),
    dict(role="narr",
         img="竖版9:16。远景俯瞰，舜立于高台之上，四位凶兽化作流光被投向四方边荒，"
             "天穹四色，" + STYLE,
         vprompt="参考图保持构图不变，四道流光飞向天穹四角，高台衣袂飘扬，"
                 "云层翻涌，远景镜头极缓拉升，写实电影质感，无文字",
         line="舜把四凶流放四荒——梼杌还有第四个用处。"),
    dict(role="narr",
         img="竖版9:16。近景，一卷展开的古简特写，简上墨迹如刀刻般狰狞，"
             "旁侧青铜灯盏火光跳动，" + STYLE,
         vprompt="参考图保持构图不变，灯焰跳动映亮简上墨迹，墨迹纹理缓缓渗出微光，"
                 "近景镜头极缓推近，写实电影质感，无文字",
         line="古人把每年开篇的史册，就叫梼杌。"),
    dict(role="narr",
         img="竖版9:16。中景，黄昏旷野上一名巨人夸父正追逐天边落日，身形渺小而"
             "意志如山，地平线拉出长长的影子，壮烈感，克制无血腥，" + STYLE,
         vprompt="参考图保持构图不变，巨人朝着落日狂奔，影子在旷野拉长，"
                 "落日余晖渐渐炽烈，中景镜头极缓拉远，写实电影质感，无文字",
         line="顽固不化到底是恶，还是不肯低头？而明天要讲的这位，追着太阳跑到了死——明天讲，夸父。"),
]

AI_META = {
    "title": "山海经梼杌：四凶里最横的滚刀肉",
    "artist": "AI生成",
    "comment": "AI生成合成内容",
    "description": "本视频画面由 AI 生成合成，已按《人工智能生成合成内容标识办法》添加隐式标识",
    "genre": "AI生成合成内容",
}

PUBLISH = {
    "title": "最横的凶兽：老虎是它的猎物，史册跟它重名｜山海经·梼杌",
    "desc": ("《神异经·西荒经》：西方荒中有兽焉，其状如虎而犬毛，人面虎足，猪牙，"
             "尾长一丈八尺，恃己强横，力能斗虎。名曰梼杌。《左传》：颛顼有不才子，"
             "不可教训，告之则顽，舍之则嚚，天下之民谓之梼杌。"
             "四凶收官：顽固不化到底是恶，还是不肯低头？你说呢？明天讲，夸父。"
             "#山海经 #梼杌 #AI经典奇谈 #神话"),
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
    # 教训落实：启动前自检 SHOTS 逐镜三键齐全
    for i, s in enumerate(SHOTS):
        for k in ("img", "vprompt", "line", "role"):
            if not s.get(k):
                raise SystemExit("SHOTS[%d] 缺少键 %s —— 先修脚本再跑" % (i + 1, k))
    for d in (FRAMES, RAW, VOICE, CLIPS):
        os.makedirs(d, exist_ok=True)
    t0 = time.time()
    n = len(SHOTS)
    P("=" * 70)
    P("山海经·梼杌 免费全片流水线启动 %s（8镜 / 目标45-55s / 0 付费额度）"
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
    P("发布建议：9/30 19:00-19:30 定时发布（穷奇9/28 → 混沌9/29 → 梼杌9/30，四凶收官）｜标题：%s"
      % PUBLISH["title"])
    P("ALL DONE 总耗时 %.1f 分钟" % ((time.time() - t0) / 60.0))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
