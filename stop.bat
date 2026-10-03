@echo off
REM 广州小升初密考模拟系统 —— 停止脚本
REM 用法：双击本文件，会按端口 8765 精确结束正在运行的服务进程。
chcp 65001 >nul 2>&1
setlocal enabledelayedexpansion

title 停止广州小升初密考模拟系统
set "PORT=8765"

echo 正在查找监听端口 %PORT% 的服务进程...
set "found=0"
for /f "tokens=5" %%a in ('netstat -ano 2^>nul ^| findstr /r ":%PORT% .*LISTENING"') do (
  set "found=1"
  echo   找到 PID=%%a，正在结束...
  taskkill /PID %%a /F >nul 2>&1
  echo   PID=%%a 已发送结束信号。
)

if !found! == 0 (
  echo [提示] 端口 %PORT% 没有监听中的服务，可能未启动或已停止。
) else (
  echo.
  echo 服务已停止。如仍残留启动窗口，可手动关闭该窗口。
)
echo.
echo 按任意键退出...
pause >nul
