#!/bin/bash
# 尾镜口播回炉：只删第8镜配音，复用首帧/视频段，重跑合成。
cd "D:/Python/text_gen_agent" || exit 1
PY="D:/ProgramData/miniforge3/envs/bigmodel/python.exe"
LOG="output/videos/_tail_rerun.log"
for k in nvwa xihe wushan; do
  case $k in
    nvwa) d=Nvwa;   v="output/videos/山海经女娲_AI漫剧版.mp4";;
    xihe) d=Xihe;   v="output/videos/山海经羲和_AI漫剧版.mp4";;
    wushan) d=Wushan; v="output/videos/山海经巫山神女_AI漫剧版.mp4";;
  esac
  old=$(stat -c %Y "$v" 2>/dev/null || echo 0)
  echo "[$(date '+%m-%d %H:%M:%S')] START $k (final mtime $old)" >> "$LOG"
  rm -f "output/videos/$d/voice/v07.wav"
  "$PY" -X utf8 "_make_${k}_video.py" >> "$LOG" 2>&1
  new=$(stat -c %Y "$v" 2>/dev/null || echo 0)
  if [ "$new" = "$old" ]; then
    echo "[$(date '+%m-%d %H:%M:%S')] FAIL $k 成片未更新" >> "$LOG"; exit 1
  fi
  echo "[$(date '+%m-%d %H:%M:%S')] DONE $k" >> "$LOG"
done
echo "[$(date '+%m-%d %H:%M:%S')] TAIL RERUN ALL DONE" >> "$LOG"
