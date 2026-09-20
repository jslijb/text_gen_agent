"""
端到端测试脚本：自动选题 → 生成梗概 → 生成标题 → 创建项目 → 触发生成 → 监控 → 验证
用法：python e2e_test.py
"""
import json
import time
import sys
import requests

BASE = "http://localhost:8000/api/v1"

# 题材 → 性向映射（与前端 genresByGender 对齐）
GENRE_TO_GENDER = {
    "都市情感": "男性向", "历史故事": "男性向",
    "现代言情": "女性向", "古代言情": "女性向", "青春校园": "女性向", "婚姻家庭": "女性向",
    "恐怖推理": "无性向", "乡村故事": "无性向", "真实故事": "无性向",
    "见闻杂谈": "无性向", "复仇爽文": "无性向", "特殊职业": "无性向",
}

CHAPTERS = 3  # 端到端测试用 3 章


def step(msg):
    print(f"\n{'='*60}\n>>> {msg}\n{'='*60}")


def wait_docker_ready():
    """等待 Docker 容器就绪"""
    step("检查 Docker 容器状态")
    import subprocess
    for i in range(30):
        try:
            r = subprocess.run(["docker", "ps", "--format", "{{.Names}}\t{{.Status}}"],
                               capture_output=True, text=True, timeout=10)
            if r.returncode == 0 and "ai_novel_backend" in r.stdout:
                print("Docker 容器就绪")
                print(r.stdout)
                return True
        except Exception:
            pass
        time.sleep(5)
    print("Docker 容器未就绪，请手动启动 Docker Desktop 并运行 docker compose up -d")
    return False


def auto_select_topic():
    """自动选题：从热搜取第一个，生成梗概和标题"""
    step("1. 自动选题：从百度热搜获取题材")

    # 取热搜 top 5
    r = requests.get(f"{BASE}/hot-topics/novel", params={"top_n": 5}, timeout=30)
    r.raise_for_status()
    hot = r.json()
    print(f"热搜来源: {hot['source']}, 降级: {hot['degraded']}")
    print(f"Top 5 热搜:")
    for t in hot["topics"][:5]:
        print(f"  {t['rank']}. {t['title']} | {t['genre']} | {t['gender']} | hot={t['hot_index']}")

    # 选第一个热搜的题材，映射到我们的二级类型
    top1 = hot["topics"][0]
    baidu_genre = top1["genre"]
    print(f"\n自动选择 Top 1: {top1['title']} (百度类型={baidu_genre})")

    # 百度 genre → 我们的二级类型映射（简化版）
    BAIDU_TO_OUR = {
        "玄幻": "都市情感", "都市": "都市情感", "历史": "历史故事",
        "奇幻": "都市情感", "武侠": "历史故事", "仙侠": "历史故事",
        "科幻": "都市情感", "游戏": "都市情感", "体育": "都市情感",
        "军事": "历史故事",
        "言情": "现代言情", "古代言情": "古代言情", "现代言情": "现代言情",
        "青春校园": "青春校园", "婚姻": "婚姻家庭",
        "悬疑": "恐怖推理", "灵异": "恐怖推理", "推理": "恐怖推理",
    }
    our_genre = BAIDU_TO_OUR.get(baidu_genre, "都市情感")
    gender = GENRE_TO_GENDER.get(our_genre, "无性向")
    print(f"映射到二级类型: {our_genre} (性向: {gender})")

    # 用 Top 3 书名作为参考生成梗概
    ref_topics = [t["title"] for t in hot["topics"][:3]]
    print(f"参考书名: {ref_topics}")

    # 生成梗概
    print("\n生成梗概中（LLM 调用，约 30-60 秒）...")
    r = requests.post(f"{BASE}/hot-topics/generate-synopsis",
                      json={"genre": our_genre, "reference_topics": ref_topics, "count": 3},
                      timeout=300)
    r.raise_for_status()
    synopses = r.json()["synopses"]
    print(f"生成 {len(synopses)} 个候选梗概:")
    for i, s in enumerate(synopses):
        print(f"\n--- 梗概 {i+1} ---")
        print(s[:200] + "..." if len(s) > 200 else s)

    # 选第一个梗概
    synopsis = synopses[0]
    print(f"\n自动选择梗概 1")

    # 生成标题
    print("\n生成标题中（LLM 调用，约 30 秒）...")
    r = requests.post(f"{BASE}/hot-topics/generate-title",
                      json={"synopsis": synopsis, "genre": our_genre, "count": 5},
                      timeout=300)
    r.raise_for_status()
    titles = r.json()["titles"]
    print(f"生成 {len(titles)} 个候选标题:")
    for i, t in enumerate(titles):
        print(f"  {i+1}. {t}")

    # 选第一个标题
    title = titles[0]
    print(f"\n自动选择标题: {title}")

    return {
        "title": title,
        "synopsis": synopsis,
        "genre": our_genre,
        "gender": gender,
    }


def create_project(info):
    """创建项目"""
    step("2. 创建项目（含封面自动生成）")
    payload = {
        "name": info["title"],
        "synopsis": info["synopsis"],
        "gender": info["gender"],
        "genre": info["genre"],
        "target_chapters": CHAPTERS,
        "words_per_chapter": 2500,
    }
    print(f"创建项目: {payload['name']}")
    print(f"  性向: {payload['gender']}")
    print(f"  二级类型: {payload['genre']}")
    print(f"  章节数: {payload['target_chapters']}")
    print(f"  每章字数: {payload['words_per_chapter']}")

    r = requests.post(f"{BASE}/projects", json=payload, timeout=60)
    r.raise_for_status()
    proj = r.json()
    pid = proj["id"]
    print(f"\n项目创建成功！")
    print(f"  ID: {pid}")
    print(f"  状态: {proj['status']}")
    print(f"  封面: {proj.get('cover_url', '（生成中...）')}")
    return pid


def trigger_generation(pid):
    """触发生成"""
    step("3. 触发小说生成（大纲 + 章节 + 去AI化）")
    r = requests.post(f"{BASE}/projects/{pid}/generate", timeout=30)
    if r.status_code != 200:
        print(f"触发生成失败: {r.status_code} {r.text}")
        return False
    print(f"生成任务已提交: {r.json()}")
    return True


def monitor_generation(pid):
    """监控生成进度"""
    step("4. 监控生成进度")
    last_status = None
    wait_seconds = 0
    max_wait = 600  # 10 分钟
    while wait_seconds < max_wait:
        r = requests.get(f"{BASE}/projects/{pid}", timeout=10)
        r.raise_for_status()
        proj = r.json()
        status = proj["status"]
        outline = proj.get("outline")
        cover = proj.get("cover_url")

        if status != last_status:
            print(f"[{wait_seconds}s] 状态: {status} | 大纲: {'有' if outline else '无'} | 封面: {cover or '无'}")
            last_status = status

        # 生成完成进入待审核
        if status == "pending_review":
            print(f"\n生成完成！进入待审核状态")
            return True

        # 生成中出错
        if status == "draft" and wait_seconds > 30:
            print(f"\n警告：状态回退到 draft，可能生成失败")
            return False

        time.sleep(15)
        wait_seconds += 15

    print(f"\n超时（{max_wait}s），未完成")
    return False


def verify_result(pid):
    """验证最终结果"""
    step("5. 验证端到端结果")
    r = requests.get(f"{BASE}/projects/{pid}", timeout=10)
    r.raise_for_status()
    proj = r.json()
    print(f"项目名称: {proj['name']}")
    print(f"状态: {proj['status']}")
    print(f"性向（一级类型）: {proj.get('gender')}")
    print(f"题材（二级类型）: {proj.get('genre')}")
    print(f"简介: {(proj.get('synopsis') or '')[:100]}...")
    print(f"封面: {proj.get('cover_url')}")
    print(f"大纲: {'已生成' if proj.get('outline') else '空'}")

    # 章节
    r = requests.get(f"{BASE}/projects/{pid}/chapters", timeout=10)
    r.raise_for_status()
    chs_resp = r.json()
    chs = chs_resp.get("items", chs_resp) if isinstance(chs_resp, dict) else chs_resp
    print(f"\n章节数: {len(chs)}")
    total_words = 0
    for ch in chs:
        content = ch.get("content", "") or ""
        orig = ch.get("original_content", "") or ""
        words = len(content)
        total_words += words
        print(f"  第{ch['chapter_number']}章: {ch['title']}")
        print(f"    字数: {words} (原始: {len(orig)})")
        print(f"    AI分数: {ch.get('ai_score_before')} → {ch.get('ai_score_after')}")
        print(f"    内容前80字: {content[:80]}...")

    print(f"\n总字数: {total_words}")

    # 验证结论
    print(f"\n{'='*60}")
    print("端到端验证结论:")
    print(f"{'='*60}")
    ok = True
    checks = [
        ("项目状态 pending_review", proj["status"] == "pending_review"),
        ("一级类型（性向）已设置", bool(proj.get("gender"))),
        ("二级类型（题材）已设置", bool(proj.get("genre"))),
        ("简介非空", bool(proj.get("synopsis"))),
        ("封面已生成", bool(proj.get("cover_url"))),
        ("大纲已生成", bool(proj.get("outline"))),
        (f"章节数 = {CHAPTERS}", len(chs) == CHAPTERS),
        ("所有章节内容非空", all(ch.get("content") for ch in chs)),
    ]
    for label, passed in checks:
        print(f"  {'✅' if passed else '❌'} {label}")
        if not passed:
            ok = False

    print(f"\n总结: {'全部通过 ✅' if ok else '存在问题 ❌'}")
    print(f"\n项目 ID: {pid}")
    print(f"前端审核地址: http://localhost:3000/")
    print(f"可在前端审核章节内容，审核通过后手动发布到百度作家平台")

    return ok


def main():
    print("="*60)
    print("端到端测试：自动选题 → 生成小说 → 去AI化 → 生成封面")
    print("="*60)

    if not wait_docker_ready():
        sys.exit(1)

    try:
        # 1. 自动选题
        info = auto_select_topic()

        # 2. 创建项目
        pid = create_project(info)

        # 3. 触发生成
        if not trigger_generation(pid):
            sys.exit(1)

        # 4. 监控
        if not monitor_generation(pid):
            print("生成未完成，检查 worker 日志: docker logs ai_novel_worker --tail 50")
            sys.exit(1)

        # 5. 验证
        ok = verify_result(pid)
        sys.exit(0 if ok else 1)

    except Exception as e:
        print(f"\n错误: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
