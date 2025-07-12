@echo off
echo 启动哔哩哔哩动态自动缓存GUI...
echo.

REM 激活虚拟环境并启动程序
call .venv\Scripts\activate.bat
python bilibili_gui.py

pause 