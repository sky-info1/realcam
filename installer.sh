#!/bin/sh

echo "┌────────────────────────────────────────────────────┐"
echo "│         ⚙ REALCAM v 1.2 Plugin Installer ⚙         │"
echo "├────────────────────────────────────────────────────┤"
echo "│ This script will install the REALCAM plugin        │"
echo "│ on your Enigma2-based receiver.                    │"
echo "│                                                    │"
echo "│ Version   : 1.2                                    │"
echo "│ Developer : SKYINFO                                │"
echo "└────────────────────────────────────────────────────┘"

echo ""
echo "[1/3] 🔽 Downloading REALCAM plugin..."
rm -f /tmp/REALCAM.tar.gz

# تحميل الملف مع التأكد من الشهادات
wget --no-check-certificate "https://raw.githubusercontent.com/sky-info1/realcam/main/REALCAM.tar.gz" -O /tmp/REALCAM.tar.gz

# التحقق من أن التحميل نجح والملف موجود
if [ ! -f /tmp/REALCAM.tar.gz ]; then
    echo "❌ Error: Download failed! Please check your internet or GitHub link."
    exit 1
fi

echo "[2/3] 📦 Installing plugin directly..."
PLUGIN_PATH="/usr/lib/enigma2/python/Plugins/Extensions/REALCAM"

# مسح النسخة القديمة إن وجدت وإنشاء المجلد الجديد
rm -rf $PLUGIN_PATH
mkdir -p $PLUGIN_PATH

# فك الضغط داخل مسار البلجن
tar -xzf /tmp/REALCAM.tar.gz -C $PLUGIN_PATH

# حيلة برمجية: إذا كان الملف المضغوط يحتوي على مجلد REALCAM بداخله، سيتم نقل الملفات لتصحيح المسار
if [ -d "$PLUGIN_PATH/REALCAM" ]; then
    mv $PLUGIN_PATH/REALCAM/* $PLUGIN_PATH/
    rm -rf $PLUGIN_PATH/REALCAM
fi

echo "[3/3] 🧹 Cleaning up..."
rm -f /tmp/REALCAM.tar.gz

echo ""
echo "✅ Installation complete!"
echo "🎉 The plugin REALCAM (v 1.2) has been installed successfully."
echo ""
echo "📞 للإشتراك، المرجو التواصل معنا عبر تيليجرام:"
echo "📞 For subscription, please contact us via Telegram:"
echo "    👉 Telegram: @skyinfotv"
echo ""
echo "🔄 Restarting the interface in 3 seconds..."
sleep 3
killall -9 enigma2
