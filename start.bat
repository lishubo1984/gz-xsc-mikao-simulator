@echo off
REM 广州小升初密考模拟系统 —— 一键启动脚本
REM 用法：双击本文件即可。会自动切到脚本所在目录、启动服务并打开浏览器。
chcp 65001 >nul 2>&1

title 广州小升初密考模拟系统
cd /d "%~dp0"

set "PY=C:\Users\li.shubo\.workbuddy\binaries\python\envs\default\Scripts\python.exe"
set "HOST=127.0.0.1"
set "PORT=8765"

REM 端口占用检查：若已在运行，直接打开浏览器，避免重复启动
netstat -ano 2>nul | findstr /r ":%PORT% .*LISTENING" >nul 2>&1
if %errorlevel%==0 (
  echo [提示] 端口 %PORT% 已被占用，服务可能已在运行，直接打开浏览器。
  start http://%HOST%:%PORT%
  goto :eof
)

echo =====================================================
echo   广州小升初密考模拟系统 正在启动...
echo   本机访问: http://%HOST%:%PORT%
echo   启动完成后会自动打开浏览器。
echo   停止服务：关闭本窗口（Ctrl+C）即可。
echo =====================================================

REM 后台延迟 4 秒打开浏览器（此时服务已就绪）
start "" cmd /c "timeout /t 4 /nobreak >nul && start http://%HOST%:%PORT%"

REM 前台启动 uvicorn（窗口显示日志，Ctrl+C 停止）
"%PY%" -m uvicorn app.main:app --host %HOST% --port %PORT%
