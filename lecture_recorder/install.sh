#!/usr/bin/env bash
# تثبيت المتطلبات - Install dependencies

echo "==> Installing system dependencies (Ubuntu/Debian)..."
sudo apt-get update -q
sudo apt-get install -y portaudio19-dev python3-pyaudio python3-tk

echo "==> Installing Python packages..."
pip3 install -r requirements.txt

echo ""
echo "✅ تم التثبيت بنجاح / Installation complete!"
echo "   لتشغيل التطبيق / To run: python3 main.py"
