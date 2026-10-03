# -*- coding: utf-8 -*-
"""从各 episode 脚本生成国庆双更物料，追加到 发布指南.md。"""
import importlib.util
import io
import os

MAP = [
    ("_make_gonggong_video.py", "10-03 11:00", "已定时"),
    ("_make_houyi_video.py", "10-03 19:00", "已定时"),
    ("_make_change_video.py", "10-04 11:00", "排队生产"),
    ("_make_gun_video.py", "10-04 19:00", "排队生产"),
    ("_make_nvwa_video.py", "10-05 11:00", "排队生产"),
    ("_make_xiangfei_video.py", "10-05 19:00", "排队生产"),
    ("_make_xihe_video.py", "10-06 11:00", "排队生产"),
    ("_make_erfu_video.py", "10-06 19:00", "排队生产"),
    ("_make_wushan_video.py", "10-07 11:00", "排队生产"),
    ("_make_xiwangmu_video.py", "10-07 19:00", "排队生产"),
    ("_make_dijun_video.py", "10-08 19:00", "排队生产"),
]

lines = ["", "---", "", "## 国庆双更批次（10-03~10-08；悲剧英雄 2~13，季终）", "",
         "> 10-02 起衔接：蚩尤(10-02 19:00) → 本批次。10-03~10-07 每天 11:00+19:00，10-08 回归 19:00。",
         "> 物料由脚本 PUBLISH 字段生成，逐条与《发布指南》同步。", ""]
for script, when, status in MAP:
    spec = importlib.util.spec_from_file_location("ep", script)
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    pub = m.PUBLISH
    fin = os.path.basename(m.FINAL)
    lines.append("### %s（%s｜%s）" % (pub["title"].split("｜")[0][:14], when, status))
    lines.append("")
    lines.append("- **脚本**：`%s`｜**视频**：`output\\videos\\%s`" % (script, fin))
    lines.append("- **标题+作品描述**：")
    lines.append("")
    lines.append("```")
    lines.append(pub["title"])
    lines.append(pub["desc"])
    lines.append("```")
    lines.append("")
    lines.append("- **首发评论**：")
    lines.append("")
    lines.append("> " + pub["comment"])
    lines.append("")

with io.open("发布指南.md", "a", encoding="utf-8") as f:
    f.write("\n".join(lines))
print("appended %d episodes" % len(MAP))
