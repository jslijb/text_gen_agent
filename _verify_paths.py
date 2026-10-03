# -*- coding: utf-8 -*-
import io
import re
import os

batch = io.open("_batch_run.sh", encoding="utf-8").read()
for s in ["change", "gun", "nvwa", "xiangfei", "xihe", "erfu", "wushan", "xiwangmu", "dijun"]:
    src = io.open("_make_%s_video.py" % s, encoding="utf-8").read()
    m = re.search(r'FINAL = r"(.+?)"', src)
    fin = m.group(1) if m else "??"
    base = os.path.basename(fin)
    base2 = base.replace("\\", "/").split("/")[-1]
    hit = base2 in batch
    print("OK  " if hit else "MISS", s, "->", base2)
