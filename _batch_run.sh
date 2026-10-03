#!/bin/bash
# 国庆双更批量：串行生产 + 上传 + 定时。可断点续跑（已有成片则跳过生产）。
PY="D:/ProgramData/miniforge3/envs/bigmodel/python.exe"
CHROME="C:/Program Files (x86)/Google/Chrome/Application/chrome.exe"
cd "D:/Python/text_gen_agent" || exit 1
LOG="output/videos/_batch.log"

log(){ echo "[$(date '+%H:%M:%S')] $*" >> "$LOG"; }

ensure_chrome(){
  for i in 1 2 3 4; do
    if curl -s --max-time 3 http://127.0.0.1:9222/json/version >/dev/null 2>&1; then return 0; fi
    log "relaunch chrome"
    powershell -Command "Start-Process '$CHROME' -ArgumentList '--remote-debugging-port=9222','--remote-allow-origins=*','--user-data-dir=D:\\Python\\text_gen_agent\\.pw_chrome','--no-first-run','--no-default-browser-check','https://cp.kuaishou.com/article/publish/video'" >/dev/null 2>&1
    sleep 12
  done
  curl -s --max-time 3 http://127.0.0.1:9222/json/version >/dev/null 2>&1
}

run_one(){
  local script="$1"; local video="$2"; local when="$3"
  local desc="output/videos/_desc_$(basename "$script" .py).txt"
  log "START $script -> $when"
  if [ ! -f "$video" ]; then
    "$PY" -X utf8 "$script" >> "$LOG" 2>&1
  fi
  if [ ! -f "$video" ]; then log "PRODUCE_FAIL $video"; return 1; fi
  if ! ensure_chrome; then log "CHROME_FAIL, skip publish $video"; return 1; fi
  "$PY" -X utf8 _ks_desc.py "$script" "$desc" >> "$LOG" 2>&1
  for a in 1 2 3; do
    "$PY" -X utf8 _ks_publish_run.py "$video" "$desc" "$when" >> "$LOG" 2>&1 && break
    sleep 20
    ensure_chrome
  done
  log "DONE $script"
}

run_one _make_change_video.py   "output/videos/山海经嫦娥_AI漫剧版.mp4"    "2026-10-04 11:00:00"
run_one _make_gun_video.py      "output/videos/山海经鲧_AI漫剧版.mp4"      "2026-10-04 19:00:00"
run_one _make_nvwa_video.py     "output/videos/山海经女娲_AI漫剧版.mp4"    "2026-10-05 11:00:00"
run_one _make_xiangfei_video.py "output/videos/山海经娥皇女英_AI漫剧版.mp4" "2026-10-05 19:00:00"
run_one _make_xihe_video.py     "output/videos/山海经羲和_AI漫剧版.mp4"    "2026-10-06 11:00:00"
run_one _make_erfu_video.py     "output/videos/山海经贰负_AI漫剧版.mp4"    "2026-10-06 19:00:00"
run_one _make_wushan_video.py   "output/videos/山海经巫山神女_AI漫剧版.mp4" "2026-10-07 11:00:00"
run_one _make_xiwangmu_video.py "output/videos/山海经西王母_AI漫剧版.mp4"  "2026-10-07 19:00:00"
run_one _make_dijun_video.py    "output/videos/山海经帝俊_AI漫剧版.mp4"    "2026-10-08 19:00:00"

log "BATCH ALL DONE"
