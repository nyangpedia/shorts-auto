@echo off
chcp 65001 >nul
title 쇼츠공방 (이 창을 닫으면 꺼집니다)
cd /d "%~dp0"
where ffmpeg >nul 2>nul || echo [경고] ffmpeg를 찾지 못했습니다. 영상 만들기가 안 될 수 있어요.
where node >nul 2>nul || (echo Node.js가 설치되어 있지 않습니다. & pause & exit /b 1)
node tools\dev\start-dev.mjs --open
pause
