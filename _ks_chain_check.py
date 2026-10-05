# -*- coding: utf-8 -*-
"""连载预告链校验：排期顺序 + 下一篇对象 + 今晚/明天措辞，三项一起核。

数据源：
  data/ks_comment_queue.json  —— 排期与首发评论
  _make_<key>_video.py        —— 成片里烧进口播的最后一镜台词
用法: _ks_chain_check.py
退出码非 0 = 有错配，禁止发布。
"""
import datetime as dt
import io
import json
import os
import re
import sys

ROOT = os.path.dirname(os.path.abspath(__file__))
QUEUE_F = os.path.join(ROOT, "data", "ks_comment_queue.json")
PAT = re.compile(r"(今晚七点|今晚|明天十一点|明天|后天)\s*讲\s*[，,]\s*([^。，,；;]+)")


def who(title):
    m = re.search(r"｜山海经·(.+)$", title.strip())
    return m.group(1).strip() if m else title.strip()[-6:]


def spoken_line(key):
    f = os.path.join(ROOT, "_make_%s_video.py" % key)
    if not os.path.exists(f):
        return ""
    txt = io.open(f, encoding="utf-8").read()
    blocks = re.findall(r'line\s*=\s*((?:"(?:[^"\\]|\\.)*"\s*)+)', txt)
    lines = ["".join(re.findall(r'"((?:[^"\\]|\\.)*)"', b)) for b in blocks]
    return lines[-1] if lines else ""


def main():
    tasks = json.load(io.open(QUEUE_F, encoding="utf-8"))
    tasks.sort(key=lambda t: dt.datetime.strptime(t["publish_at"], "%Y-%m-%d %H:%M:%S"))
    bad = 0
    print("%-19s %-10s %-14s %-14s %s" % ("排期", "本篇", "口播预告", "首评预告", "实际下一篇"))
    print("-" * 88)
    for i, t in enumerate(tasks):
        nxt = who(tasks[i + 1]["title"]) if i + 1 < len(tasks) else None
        when = dt.datetime.strptime(t["publish_at"], "%Y-%m-%d %H:%M:%S")
        sp = PAT.search(spoken_line(t["key"]) or "")
        cm = PAT.search(t.get("comment", "") or "")
        errs = []
        for tag, m in (("口播", sp), ("首评", cm)):
            if not m:
                errs.append("%s无预告" % tag)
                continue
            who_said, word = m.group(2).strip(), m.group(1)
            if nxt and who_said != nxt:
                errs.append("%s预告对象错:%s≠%s" % (tag, who_said, nxt))
            if nxt:
                gap = (dt.datetime.strptime(tasks[i + 1]["publish_at"], "%Y-%m-%d %H:%M:%S")
                       - when).total_seconds()
                same_day = tasks[i + 1]["publish_at"][:10] == t["publish_at"][:10]
                need = "今晚" if (same_day and gap <= 12 * 3600) else "明天"
                if not word.startswith(need):
                    errs.append("%s措辞应为%s（实际:%s）" % (tag, need, word))
        if nxt is None:
            print("  %-19s %-10s 收官条，无下一篇" % (t["publish_at"], who(t["title"])))
            continue
        print("%-19s %-10s %-14s %-14s %s%s" % (
            t["publish_at"], who(t["title"]),
            (sp.group(0)[:12] if sp else "-"),
            (cm.group(0)[:12] if cm else "-"),
            "%s(%s)" % (nxt, tasks[i + 1]["publish_at"][5:16]),
            "" if not errs else "   <<< " + "；".join(errs)))
        bad += len(errs)
    print("-" * 88)
    print("错配 %d 处" % bad)
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
