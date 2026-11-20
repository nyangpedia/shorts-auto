@echo off
chcp 65001 >nul
cd /d "%~dp0"
where node >nul 2>nul || (echo Node.js가 설치되어 있지 않습니다. & pause & exit /b 1)
if not exist logs mkdir logs
rem 창 없이 켭니다. 로그는 logs\server.log, 끄려면 PC를 재시작하거나 작업 관리자에서 node.exe를 종료하세요.
powershell -NoProfile -WindowStyle Hidden -Command "Start-Process node -ArgumentList 'tools\dev\start-dev.mjs','--open' -WindowStyle Hidden -RedirectStandardOutput logs\server.log -RedirectStandardError logs\server.err.log"
