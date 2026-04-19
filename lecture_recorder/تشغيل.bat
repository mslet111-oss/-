@echo off
chcp 65001 >nul
title مسجل المحاضرات - Lecture Recorder

echo.
echo ========================================
echo    مسجل المحاضرات - Lecture Recorder
echo ========================================
echo.

:: Check Python
python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo [!] Python غير مثبت على جهازك
    echo.
    echo افتح هذا الرابط وحمل Python:
    echo https://www.python.org/downloads/
    echo.
    echo بعد التحميل، شغل هذا الملف مجدداً
    echo.
    pause
    exit
)

echo [1] جاري تثبيت المكتبات...
pip install pyaudio SpeechRecognition pywhatkit >nul 2>&1

echo [2] جاري تشغيل التطبيق...
echo.
python main.py

if %errorlevel% neq 0 (
    echo.
    echo [!] حدث خطأ، جرب هذا الامر:
    echo pip install pipwin
    echo pipwin install pyaudio
    pause
)
