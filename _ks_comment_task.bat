@echo off
rem 快手首评+置顶补发（计划任务 KS_Comment_Post 11:05 / KS_Comment_Evening 19:05 + 开机自启）
setlocal
cd /d D:\Python\text_gen_agent
if not exist logs mkdir logs
echo [%date% %time%] BAT START >> logs\ks_comment_task.log
rem 开机自启时网络/Chrome 可能还没就绪，先等一下再跑
timeout /t 45 /nobreak >nul
"D:\ProgramData\miniforge3\envs\bigmodel\python.exe" -X utf8 _ks_comment_run.py run >> logs\ks_comment_task.log 2>&1
echo [%date% %time%] BAT END exit=%errorlevel% >> logs\ks_comment_task.log
endlocal
