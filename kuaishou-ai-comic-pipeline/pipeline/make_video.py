# -*- coding: utf-8 -*-
"""糖画匠 —— 多模型分镜流水线（2026-09-15 晚）

8 分镜 = qwen-image-3.0 首帧（统一人物+画风锁死）+ 视频模型各一段 5s 真运动
  分镜1/4/7  happyhorse-1.1-r2v      （仅5s，9:16，720P，无水印）
  分镜2/5/8  wan2.7-r2v-2026-06-12   （额度45，省着用，只用3次）
  分镜3/6    wan3.0-video-prime      （额度25，只用2次）
硬规矩：百炼每段只调用一次，提交失败/额度不足/任务失败 → 该分镜直接落
        Agnes 2.5-flash 免费 keyframe 兜底，不重试百炼、不等下一轮。
后期：SAPI 配音 → 全部统一 TARGET 秒 → 字幕+AI角标 → 拼接 → 隐式元数据标识。
断点续跑：urls.json（首帧直链）+ tasks.json（已提交任务）+ raw/（已成片段）。
"""
import io
import json
import os
import re
import subprocess
import time
import urllib.error
import urllib.parse
import urllib.request

import imageio_ffmpeg

# ---------------- 常量 ----------------
DASH = os.environ.get("DASHSCOPE_API_KEY", "")  # key1 只从环境变量读，不打印
AGNES = os.environ.get("AGNES_API_KEY", "")
MULTI = "https://dashscope.aliyuncs.com/api/v1/services/aigc/multimodal-generation/generation"
SYN = "https://dashscope.aliyuncs.com/api/v1/services/aigc/video-generation/video-synthesis"
GEN = "https://dashscope.aliyuncs.com/api/v1/services/aigc/video-generation/generation"
TASK = "https://dashscope.aliyuncs.com/api/v1/tasks/"
AGBASE = "https://api.agnes-ai.cn"
VIDEO_MODEL = "agnes-video-2.5-flash"      # 兜底
IMAGE_MODEL = "agnes-image-2.1-flash"      # 兜底

WORK = r"D:\Python\text_gen_agent\output\videos\zhulong"
FRAMES = os.path.join(WORK, "frames")
RAW = os.path.join(WORK, "raw")
VOICE = os.path.join(WORK, "voice")
CLIPS = os.path.join(WORK, "clips")
FINAL = r"D:\Python\text_gen_agent\output\videos\山海经烛龙_AI纪录片版.mp4"
LOG = os.path.join(WORK, "build_log.txt")
URLS_JSON = os.path.join(WORK, "urls.json")
TASKS_JSON = os.path.join(WORK, "tasks.json")
FFMPEG = imageio_ffmpeg.get_ffmpeg_exe()
FONT_DIR = "C:/Windows/Fonts"
FONT_BOLD = "C:/Windows/Fonts/msyhbd.ttc"
W, H, FPS = 720, 1280, 30

# 人物与画风锁死（所有首帧共用，保证 8 段一致）
CHAR = ("八十四岁中国老人，满头银发，灰白山羊胡，脸上皱纹深刻，"
        "穿深蓝色旧棉袄，袖口磨损")
STYLE = ("写实电影质感，自然光，暖色调，浅景深，胶片颗粒感，"
         "画面无任何文字水印logo")

# ---------------- 分镜表 ----------------
DRAGON = ("一条赤红色巨龙，人面蛇身：面部是威严的人脸轮廓，巨躯如蛇覆盖朱砂红鳞片，"
          "鳞片边缘泛熔金微光")
STYLE = ("东方神话史诗电影质感，写实与水墨融合，色彩以赤红、墨黑、熔金为主，"
         "画面无任何文字水印logo")
SHOTS = [
    dict(model="wan3.0-video",
         img="竖版9:16。极特写，一条巨龙的金色竖瞳正在缓缓睁开，瞳孔中迸出熔金色的光，"
             "周围是赤红鳞片与黑暗，" + DRAGON + "，" + STYLE,
         vprompt="画面中的巨龙竖瞳缓缓睁开，金色瞳孔光芒逐渐增强并照亮周围赤红鳞片，"
                 "瞳孔微缩，光线从瞳孔中迸射，极特写镜头极缓推近，写实电影质感，无文字",
         line="它睁开眼，人间就是白天。"),
    dict(model="wan2.7-r2v-2026-06-12",
         img="竖版9:16。极特写，巨龙的金色竖瞳半闭，眼睑低垂，周围光线暗淡，黑暗笼罩，"
             "仅鳞片边缘有一点余光，" + DRAGON + "，" + STYLE,
         vprompt="参考图中的巨龙眼睑缓缓闭合，金色瞳孔光芒渐渐熄灭，画面整体转暗，"
                 "只余鳞片边缘微光，极特写镜头极缓推近，写实电影质感，无文字",
         line="它闭上眼，大地就沉入黑夜。"),
    dict(model="wan2.7-r2v-2026-06-12",
         img="竖版9:16。大远景，一条赤红色巨龙盘绕在漆黑的钟山山巅，身躯绵延缠绕大半座山，"
             "云海在山腰翻涌，冷月光，" + DRAGON + "，" + STYLE,
         vprompt="参考图中的赤色巨龙保持外形不变，巨大蛇形身躯在山巅与云海间缓缓游动，"
                 "鳞片反光流动，云海缓慢翻涌，大远景镜头极缓推进，写实电影质感，无文字",
         line="《山海经》记载：钟山之神，名曰烛阴。"),
    dict(model="wan3.0-video-prime",
         img="竖版9:16。近景特写，巨龙的人脸面部：威严的人脸轮廓与蛇形巨躯相连，"
             "面部覆有细密赤红鳞片，双目微阖，神态古老而庄严，" + DRAGON + "，" + STYLE,
         vprompt="画面中的巨龙面部保持不变，人脸面部微微抬起，双目缓缓半睁透出金光，"
                 "面部细鳞随肌肉轻微起伏，近景镜头极缓推近，写实电影质感，无文字",
         line="人面蛇身，通体赤红，身长千里。"),
    dict(model="wan3.0-video",
         img="竖版9:16。中景，赤红色巨龙盘绕在风雪中的黑色山巅，一动不动，"
             "风雪横扫过鳞片，龙身覆盖薄雪，冷蓝色调，" + DRAGON + "，" + STYLE,
         vprompt="画面中的巨龙保持盘绕姿态纹丝不动，风雪持续横扫过赤红鳞片，"
                 "雪花在龙身边堆积，中景镜头极缓环绕，写实电影质感，无文字",
         line="它不吃、不喝、不睡、不动。"),
    dict(model="wan2.7-r2v-2026-06-12",
         img="竖版9:16。近景，巨龙张开口呼出一道浓烈的白色寒雾，寒雾如洪流般喷涌而出，"
             "鳞片间透出暗红光，" + DRAGON + "，" + STYLE,
         vprompt="参考图中的巨龙保持外形不变，龙口持续呼出浓烈白色寒雾，寒雾喷涌扩散"
                 "形成局部暴风雪，龙身鳞片微光流动，近景镜头轻微横移，写实电影质感，无文字",
         line="一次呼吸，就是人间的一季寒冬。"),
    dict(model="wan3.0-video-prime",
         img="竖版9:16。大远景，赤红色巨龙盘绕钟山山巅，画面一侧是白昼一侧是黑夜，"
             "昼夜分界线横贯天空，云海与星河同现，" + DRAGON + "，" + STYLE,
         vprompt="画面中的巨龙与钟山保持不变，昼夜分界线缓慢移动，白昼一侧渐渐扩张，"
                 "星河隐去太阳升起，云海缓缓流动，大远景固定镜头，写实电影质感，无文字",
         line="睁眼闭眼之间，是人间一昼夜。"),
    dict(model="wan3.0-video",
         img="竖版9:16。夜空下的雪原远景，黑暗中只剩一点巨龙的金色眼瞳余光，"
             "雪原寂静，星空清冷，极简构图，" + DRAGON + "，" + STYLE,
         vprompt="画面保持雪原夜景不变，黑暗中那一点金色眼瞳余光缓缓变暗直至熄灭，"
                 "星空缓慢旋转，雪面微光流动，远景镜头极缓拉远，写实电影质感，无文字",
         line="你觉得，古人真的见过它吗？"),
]

AI_META = {
    "title": "山海经烛龙：它睁眼是白天，闭眼是黑夜",
    "artist": "AI生成",
    "comment": "AI生成合成内容",
    "description": "本视频画面由 AI 生成合成，已按《人工智能生成合成内容标识办法》添加隐式标识",
    "genre": "AI生成合成内容",
}


# ---------------- 基础 ----------------
def P(s=""):
    s = str(s)
    try:
        with io.open(LOG, "a", encoding="utf-8") as f:
            f.write(s + "\n")
    except Exception:
        pass
    try:
        print(s)
    except Exception:
        try:
            print(s.encode("ascii", "replace").decode("ascii"))
        except Exception:
            pass


def http(url, body=None, method="GET", key=None, async_hdr=False, timeout=120):
    h = {"Content-Type": "application/json", "User-Agent": "Mozilla/5.0"}
    if key:
        h["Authorization"] = "Bearer " + key
    if method == "POST" and async_hdr:
        h["X-DashScope-Async"] = "enable"
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


# ---------------- 首帧图 ----------------
def qwen_image(prompt, path):
    """qwen-image-3.0 同步出图，返回 (本地ok, 公开URL)。"""
    body = {"model": "qwen-image-2.0-pro-2026-06-22",
            "input": {"messages": [{"role": "user", "content": [{"text": prompt}]}]},
            "parameters": {"size": "928*1664"}}
    st, txt = http(MULTI, body, method="POST", key=DASH, timeout=240)
    P("    qwen-image HTTP %s" % st)
    url = None
    try:
        j = json.loads(txt)
        for item in j["output"]["choices"][0]["message"]["content"]:
            if "image" in item:
                url = item["image"]
                break
    except Exception:
        pass
    if not url:
        P("    qwen-image 无URL: %s" % txt.replace("\n", " ")[:200])
        return False, None
    if download(url, path):
        P("    首帧图 OK %d KB" % (os.path.getsize(path) // 1024))
        return True, url
    return False, None


def agnes_image(prompt, path):
    """Agnes 免费图像兜底，返回 (本地ok, 公开COS直链)。"""
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
            P("    首帧图(agnes兜底) OK %d KB" % (os.path.getsize(path) // 1024))
            return True, url
    return False, None


# ---------------- 视频提交/轮询 ----------------
def submit_bailian(shot, img_url):
    """提交百炼视频任务。成功返回 task_id，失败返回 None（不重试烧额度）。"""
    m = shot["model"]
    params = {"resolution": "720P", "ratio": "9:16", "duration": 5}
    if m.startswith("happyhorse"):
        params["watermark"] = False

    def _post(endpoint, inp):
        st, txt = http(endpoint, {"model": m, "input": inp, "parameters": params},
                       method="POST", key=DASH, async_hdr=True, timeout=120)
        P("    [%s] HTTP %s: %s" % (m, st, txt.replace("\n", " ")[:220]))
        if st != 200:
            return None
        try:
            return json.loads(txt)["output"]["task_id"]
        except Exception:
            return None

    if m.startswith("wan3.0-video"):
        # 先试带参考图；4xx 再试纯文生（4xx 不耗额度）
        tid = _post(SYN, {"prompt": shot["vprompt"],
                          "media": [{"type": "reference_image", "url": img_url}]})
        if tid:
            return tid
        tid = _post(SYN, {"prompt": shot["vprompt"]})
        return tid
    # r2v 双雄：参考图 + 提示词
    tid = _post(SYN, {"prompt": shot["vprompt"],
                      "media": [{"type": "reference_image", "url": img_url}]})
    if tid is None and m.startswith("happyhorse"):
        tid = _post(GEN, {"prompt": shot["vprompt"],
                          "media": [{"type": "reference_image", "url": img_url}]})
    return tid


def poll_bailian(tid, max_min=30):
    t0 = time.time()
    last = ""
    while time.time() - t0 < max_min * 60:
        st, txt = http(TASK + tid, key=DASH, timeout=60)
        try:
            o = json.loads(txt).get("output", {})
            s = o.get("task_status", "?")
        except Exception:
            s = "?"
        if s != last:
            P("      [%4.0fs] %s" % (time.time() - t0, s))
            last = s
        if s == "SUCCEEDED":
            try:
                return json.loads(txt)["output"]["video_url"]
            except Exception:
                return None
        if s in ("FAILED", "CANCELED", "UNKNOWN"):
            P("      任务失败: %s" % txt.replace("\n", " ")[:260])
            return None
        time.sleep(15)
    P("      轮询超时")
    return None


def agnes_video(img_url, prompt, out):
    """Agnes 免费 keyframe 兜底：出片返回 True。"""
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
        # 轮询
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
        if url and download(url, out):
            P("      ✓ agnes兜底出片 %d KB" % (os.path.getsize(out) // 1024))
            return True
        time.sleep(30)
    return False


# ---------------- 配音 ----------------
def make_voice(text, path):
    if os.path.exists(path) and os.path.getsize(path) > 5000:
        return True
    try:
        import win32com.client
        sp = win32com.client.Dispatch("SAPI.SpVoice")
        for v in sp.GetVoices():
            desc = v.GetDescription()
            if "Chinese" in desc and ("Kangkang" in desc or "Male" in desc or "男" in desc):
                sp.Voice = v
                break
        else:
            for v in sp.GetVoices():
                desc = v.GetDescription()
                if "Chinese" in desc or "Huihui" in desc:
                    sp.Voice = v
                    break
        sp.Rate = -2
        sp.Volume = 100
        fs = win32com.client.Dispatch("SAPI.SpFileStream")
        fs.Open(path, 3, False)
        sp.AudioOutputStream = fs
        sp.Speak(text)
        fs.Close()
        return os.path.exists(path) and os.path.getsize(path) > 5000
    except Exception as e:
        P("    SAPI ERR %s: %s" % (type(e).__name__, e))
        return False


def media_duration(path):
    r = subprocess.run([FFMPEG, "-i", path], capture_output=True, text=True,
                       encoding="utf-8", errors="ignore")
    m = re.search(r"Duration: (\d+):(\d+):([\d.]+)", r.stderr)
    if m:
        return int(m.group(1)) * 3600 + int(m.group(2)) * 60 + float(m.group(3))
    return 0.0


# ---------------- 合成 ----------------
def esc(p):
    return p.replace("\\", "/").replace(":", "\\:")


def build_clip(i, raw, voice, target, text, out):
    srt = os.path.join(WORK, "sub_%02d.srt" % i)
    end = int(target * 1000)
    ts = "00:00:00,000 --> 00:%02d:%02d,%03d" % (end // 60000, (end // 1000) % 60, end % 1000)
    with io.open(srt, "w", encoding="utf-8") as f:
        f.write("1\n%s\n%s\n" % (ts, text))
    style = ("FontName=Microsoft YaHei,FontSize=17,PrimaryColour=&H00FFFFFF,"
             "OutlineColour=&H00000000,BorderStyle=1,Outline=2,Shadow=0,"
             "Alignment=2,MarginV=90")
    vf = ("[0:v]scale=%d:%d:force_original_aspect_ratio=increase,crop=%d:%d,setsar=1,"
          "subtitles='%s':fontsdir='%s':force_style='%s',"
          "drawtext=fontfile='%s':text='AI生成':x=w-tw-24:y=28:fontsize=30:"
          "fontcolor=white@0.92:box=1:boxcolor=black@0.5:boxborderw=10[v];"
          "[1:a]apad,aresample=44100,aformat=sample_fmts=fltp:channel_layouts=stereo[a]"
          % (W, H, W, H, esc(srt), esc(FONT_DIR), style, esc(FONT_BOLD)))
    cmd = [FFMPEG, "-y", "-stream_loop", "-1", "-i", raw, "-i", voice,
           "-filter_complex", vf, "-map", "[v]", "-map", "[a]",
           "-t", "%.2f" % target,
           "-c:v", "libx264", "-preset", "medium", "-crf", "21", "-pix_fmt", "yuv420p",
           "-r", str(FPS), "-c:a", "aac", "-b:a", "128k", "-ar", "44100", "-ac", "2",
           out]
    r = subprocess.run(cmd, cwd=WORK, capture_output=True, text=True,
                       encoding="utf-8", errors="ignore")
    if r.returncode != 0:
        P("    片段合成失败: " + r.stderr[-500:])
        return False
    return os.path.exists(out)


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
        P("  [元数据] AI 隐式标识已写入")
    else:
        P("  [元数据] 打标失败: " + r.stderr[-300:])


# ---------------- 主流程 ----------------
def main():
    for d in (FRAMES, RAW, VOICE, CLIPS):
        os.makedirs(d, exist_ok=True)
    t0 = time.time()
    P("=" * 70)
    P("多模型分镜流水线启动 %s  (8分镜, 百炼单次调用+Agnes兜底)" % time.strftime("%H:%M:%S"))
    P("=" * 70)

    # --- 1/5 配音（先做，用来定统一时长 TARGET） ---
    P("\n阶段 1/5 配音(SAPI)")
    for i, s in enumerate(SHOTS):
        vp = os.path.join(VOICE, "v%02d.wav" % i)
        ok = make_voice(s["line"], vp)
        d = media_duration(vp) if ok else 0.0
        P("  [%d] %.2fs  %s" % (i + 1, d, s["line"]))
        s["voice"] = vp if ok else None
        s["vdur"] = d
    TARGET = max([5.0] + [s["vdur"] + 0.7 for s in SHOTS if s["vdur"] > 0])
    P("  >>> 统一目标时长 TARGET=%.2fs" % TARGET)

    # --- 2/5 首帧图（统一 qwen-image-3.0，失败落 Agnes） ---
    P("\n阶段 2/5 首帧图")
    urls = load_json(URLS_JSON, {})
    for i, s in enumerate(SHOTS):
        ip = os.path.join(FRAMES, "f%02d.png" % i)
        if urls.get(str(i)) and os.path.exists(ip) and os.path.getsize(ip) > 50000:
            s["img_url"] = urls[str(i)]
            P("  [%d] 复用已有首帧直链" % (i + 1))
            continue
        ok, url = qwen_image(s["img"], ip)
        if not ok or not url:
            P("  [%d] qwen-image 失败 -> Agnes 兜底" % (i + 1))
            ok, url = agnes_image(s["img"], ip)
        s["img_url"] = url if ok else None
        if ok and url:
            urls[str(i)] = url
            save_json(URLS_JSON, urls)
        if not ok:
            P("  [%d] >>> 首帧图失败，该分镜将无法出片" % (i + 1))
        time.sleep(5)

    # --- 3/5 视频段（百炼一次机会，失败落 Agnes） ---
    P("\n阶段 3/5 视频段")
    tasks = load_json(TASKS_JSON, {})
    for i, s in enumerate(SHOTS):
        out = os.path.join(RAW, "r%02d.mp4" % i)
        if os.path.exists(out) and os.path.getsize(out) > 200000:
            s["raw"] = out
            P("  [%d] 已有片段，跳过" % (i + 1))
            continue
        if not s.get("img_url"):
            P("  [%d] 无首帧直链，只能等首帧阶段重跑" % (i + 1))
            continue
        P("\n  [%d] %s  (%s)" % (i + 1, s["line"], s["model"]))
        url = None
        rec = tasks.get(str(i)) or {}
        if rec.get("task_id"):
            P("    续跑：轮询已提交任务 %s" % rec["task_id"])
            url = poll_bailian(rec["task_id"])
        else:
            tid = submit_bailian(s, s["img_url"])
            if tid:
                tasks[str(i)] = {"model": s["model"], "task_id": tid}
                save_json(TASKS_JSON, tasks)
                url = poll_bailian(tid)
        if url and download(url, out, min_size=200000):
            s["raw"] = out
            P("    ✓ 百炼出片 %d KB" % (os.path.getsize(out) // 1024))
            continue
        P("    -> Agnes 免费 keyframe 兜底")
        if agnes_video(s["img_url"], s["vprompt"], out):
            s["raw"] = out
        else:
            P("    >>> [%d] 兜底也未出片，留待补跑" % (i + 1))
        time.sleep(10)

    done = sum(1 for s in SHOTS if s.get("raw"))
    P("\n阶段 3 结束：%d/8 段成功" % done)
    if done == 0:
        P("无任何片段，终止")
        return 1

    # --- 4/5 单段合成（统一 TARGET 秒） ---
    P("\n阶段 4/5 单段合成(字幕+AI角标+配音)")
    clips = []
    for i, s in enumerate(SHOTS):
        if not s.get("raw"):
            P("  [%d] 缺片段，跳过" % (i + 1))
            continue
        if not s.get("voice"):
            P("  [%d] 缺配音，跳过" % (i + 1))
            continue
        out = os.path.join(CLIPS, "c%02d.mp4" % i)
        if os.path.exists(out) and os.path.getsize(out) > 100000:
            clips.append(out)
            continue
        P("  [%d] target=%.2fs  %s" % (i + 1, TARGET, s["line"]))
        if build_clip(i, s["raw"], s["voice"], TARGET, s["line"], out):
            clips.append(out)
        else:
            P("      合成失败")

    if not clips:
        P("没有可用片段，终止")
        return 1

    # --- 5/5 拼接成片 ---
    P("\n阶段 5/5 拼接成片")
    lst = os.path.join(WORK, "concat.txt")
    with io.open(lst, "w", encoding="utf-8") as f:
        f.write("\n".join("file '%s'" % c.replace("\\", "/") for c in clips))
    r = subprocess.run(
        [FFMPEG, "-y", "-f", "concat", "-safe", "0", "-i", lst,
         "-c:v", "libx264", "-preset", "medium", "-crf", "21", "-pix_fmt", "yuv420p",
         "-c:a", "aac", "-b:a", "128k", "-ar", "44100", "-ac", "2",
         "-movflags", "+faststart", FINAL],
        cwd=WORK, capture_output=True, text=True, encoding="utf-8", errors="ignore")
    if r.returncode != 0:
        P("拼接失败: " + r.stderr[-800:])
        return 1

    total = media_duration(FINAL)
    P("")
    P("=" * 70)
    P("成片: %s" % FINAL)
    P("时长 %.1fs | %.2f MB | %dx%d | 片段 %d | 总耗时 %.1f 分钟"
      % (total, os.path.getsize(FINAL) / 1048576, W, H, len(clips),
         (time.time() - t0) / 60.0))
    for i, s in enumerate(SHOTS):
        P("  分镜%d [%s] %s" % (i + 1,
                                "百炼:" + s["model"] if os.path.exists(
                                    os.path.join(RAW, "r%02d.mp4" % i))
                                and s.get("raw") == os.path.join(RAW, "r%02d.mp4" % i)
                                else "Agnes兜底/缺",
                                "OK" if s.get("raw") else "MISS"))
    P("=" * 70)
    tag_ai_metadata(FINAL)
    P("ALL DONE")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
