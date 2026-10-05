#!/bin/bash
# 待发布作品逐条「删除 -> 带 AI 作者声明重发 -> 按原时间定时」。
# 巫山神女已单独完成，这里跑剩下 5 条。任一条 DECLARE_AI 不为 True 即停止。
cd "D:/Python/text_gen_agent" || exit 1
PY="D:/ProgramData/miniforge3/envs/bigmodel/python.exe"
export KS_CDP="http://127.0.0.1:9223"
LOG="output/videos/_republish.log"

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
  echo "[$(date '+%m-%d %H:%M:%S')] PASS $kw" >> "$LOG"
  return 0
}

V=output/videos
item 贰负     "$V/山海经贰负_AI漫剧版.mp4"     "$V/_desc__make_erfu_video.txt"     "2026-10-06 19:00:00" || exit 1
item 羲和     "$V/山海经羲和_AI漫剧版.mp4"     "$V/_desc__make_xihe_video.txt"     "2026-10-06 11:00:00" || exit 1
item 娥皇女英 "$V/山海经娥皇女英_AI漫剧版.mp4" "$V/_desc__make_xiangfei_video.txt" "2026-10-05 19:00:00" || exit 1
item 女娲     "$V/山海经女娲_AI漫剧版.mp4"     "$V/_desc__make_nvwa_video.txt"     "2026-10-05 11:00:00" || exit 1
# 鲧（今晚 19:00）留到最后单独盯，避免临近时点重排失败丢档
echo "[$(date '+%m-%d %H:%M:%S')] BATCH4 DONE" >> "$LOG"
