#!/bin/sh

# مسار مجلد البلجن في جهاز الاستقبال
PLUGIN_PATH="/usr/lib/enigma2/python/Plugins/Extensions/REALCAM"
BASE_URL="https://raw.githubusercontent.com/sky-info1/realcam/main"

echo "[1/3] Cleaning old files and creating folder..."
rm -rf $PLUGIN_PATH
mkdir -p $PLUGIN_PATH

echo "[2/3] Downloading plugin files directly..."
wget -q --no-check-certificate "$BASE_URL/plugin.py" -O $PLUGIN_PATH/plugin.py
wget -q --no-check-certificate "$BASE_URL/plugin.png" -O $PLUGIN_PATH/plugin.png
wget -q --no-check-certificate "$BASE_URL/setup.xml" -O $PLUGIN_PATH/setup.xml
wget -q --no-check-certificate "$BASE_URL/__init__.py" -O $PLUGIN_PATH/__init__.py

echo "[3/3] Saving changes..."
sync

# طباعة الجدول النهائي مضافاً إليه سطر الاشتراك الترويجي الموزون برمجياً
echo ""
echo "┌────────────────────────────────────────────────────────┐"
echo "│          ✅ REALCAM Installed Successfully!            │"
echo "├────────────────────────────────────────────────────────┤"
echo "│  🎉 Welcome to REALCAM Extension                       │"
echo "│  📞 Telegram Support: @skyinfotv                       │"
echo "│  📢 Available all IPTV subscription contact us         │"
echo "│     via Telegram @skyinfotv                            │"
echo "├────────────────────────────────────────────────────────┤"
echo "│  🔄 Please restart your receiver (Restart GUI).        │"
echo "└────────────────────────────────────────────────────────┘"
echo ""
