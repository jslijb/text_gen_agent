# -*- coding: utf-8 -*-
"""从 episode 脚本提取 PUBLISH 描述块 -> 写文件。用法: _ks_desc.py <script> <out_txt>"""
import importlib.util
import io
import sys

spec = importlib.util.spec_from_file_location("ep", sys.argv[1])
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)
txt = m.PUBLISH["title"] + "\n" + m.PUBLISH["desc"]
with io.open(sys.argv[2], "w", encoding="utf-8") as f:
    f.write(txt)
print("wrote %s (%d chars)" % (sys.argv[2], len(txt)))
