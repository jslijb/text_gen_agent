#!/bin/bash
# 尾镜回炉后的 3 条：删除旧待发布 -> 上传新成片 -> 勾 AI 声明 -> 按原时间定时。
# 最后新增发布 西王母（10-07 19:00）。任一步不达标即停止，绝不带错排期。
cd "D:/Python/text_gen_agent" || exit 1
PY="D:/ProgramData/miniforge3/envs/bigmodel/python.exe"
export KS_CDP="http://127.0.0.1:9223"
LOG="output/videos/_republish_tail.log"
V=output/videos

item(){
  local kw="$1" vid="$2" desc="$3" when="$4"
  echo "[$(date '+%m-%d %H:%M:%S')] === $kw -> $when" >> "$LOG"
  "$PY" -X utf8 _ks_del_pending.py "$kw" >> "$LOG" 2>&1
  if ! grep -q "REMAIN matched: 0" <(tail -3 "$LOG"); then
    echo "[$(date '+%m-%d %H:%M:%S')] DELETE_FAIL $kw, STOP" >> "$LOG"; return 1
  fi
  "$PY" -X utf8 _ks_publish_run.py "$vid" "$desc" "$when" >> "$LOG" 2>&1
  if ! grep -q "DECLARE_AI: True" <(tail -15 "$LOG"); then
    echo "[$(date '+%m-%d %H:%M:%S')] DECLARE_FAIL $kw, STOP" >> "$LOG"; return 1
  fi
  if ! grep -q "SCHEDULED: $when" <(tail -15 "$LOG"); then
    echo "[$(date '+%m-%d %H:%M:%S')] TIME_FAIL $kw, STOP" >> "$LOG"; return 1
  fi
  echo "[$(date '+%m-%d %H:%M:%S')] PASS $kw" >> "$LOG"
  return 0
}

new(){
  local kw="$1" vid="$2" desc="$3" when="$4"
  echo "[$(date '+%m-%d %H:%M:%S')] === NEW $kw -> $when" >> "$LOG"
  "$PY" -X utf8 _ks_publish_run.py "$vid" "$desc" "$when" >> "$LOG" 2>&1
  if ! grep -q "DECLARE_AI: True" <(tail -15 "$LOG"); then
    echo "[$(date '+%m-%d %H:%M:%S')] DECLARE_FAIL $kw, STOP" >> "$LOG"; return 1
  fi
  if ! grep -q "SCHEDULED: $when" <(tail -15 "$LOG"); then
    echo "[$(date '+%m-%d %H:%M:%S')] TIME_FAIL $kw, STOP" >> "$LOG"; return 1
  fi
  echo "[$(date '+%m-%d %H:%M:%S')] PASS NEW $kw" >> "$LOG"
  return 0
}

item 女娲     "$V/山海经女娲_AI漫剧版.mp4"     "$V/_desc__make_nvwa_video.txt"     "2026-10-05 11:00:00" || exit 1
item 羲和     "$V/山海经羲和_AI漫剧版.mp4"     "$V/_desc__make_xihe_video.txt"     "2026-10-06 11:00:00" || exit 1
item 巫山神女 "$V/山海经巫山神女_AI漫剧版.mp4" "$V/_desc__make_wushan_video.txt"   "2026-10-07 11:00:00" || exit 1
new  西王母   "$V/山海经西王母_AI漫剧版.mp4"   "$V/_desc__make_xiwangmu_video.txt" "2026-10-07 19:00:00" || exit 1
echo "[$(date '+%m-%d %H:%M:%S')] BATCH5 ALL DONE" >> "$LOG"
