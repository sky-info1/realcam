#!/bin/sh

clear
echo ""
echo "┌────────────────────────────────────────────────────┐"
echo "│         ⚙ TVSATMAROC Plugin Installer ⚙            │"
echo "├────────────────────────────────────────────────────┤"
echo "│ This script will install the REALCAM plugin        │"
echo "│ on your Enigma2-based receiver.                    │"
echo "│                                                    │"
echo "│ Version   : 1.2                                    │"
echo "│ Developer : SKYINFO                                │"
echo "└────────────────────────────────────────────────────┘"
echo ""

# 1. التحميل
echo "[1/3] 🔽 Downloading REALCAM plugin..."
wget --no-check-certificate "https://raw.githubusercontent.com/sky-info1/realcam/main/REALCAM.tar.gz" -O /tmp/REALCAM.tar.gz >/dev/null 2>&1

# 2. فك الضغط والتثبيت المباشر
echo "[2/3] 📦 Installing plugin directly..."
# فك الضغط مباشرة في مسار البلاجن
tar -xzf /tmp/REALCAM.tar.gz -C /usr/lib/enigma2/python/Plugins/Extensions/ >/dev/null 2>&1

# 3. التنظيف
echo "[3/3] 🧹 Cleaning up..."
rm -f /tmp/REALCAM.tar.gz

# 4. رسالة النجاح ومعلومات الاشتراك
echo ""
echo "✅ Installation complete!"
echo "🎉 The plugin \"REALCAM\" (v1.2) has been installed successfully."
echo ""
echo "📞 للإشتراك، المرجو التواصل معنا عبر تيليجرام:"
echo "📞 For subscription, please contact us via Telegram:"
echo "    👉 Telegram: @skyinfotv"
echo ""

# 5. إعادة تشغيل الجهاز
echo "🔄 Rebooting the receiver in 3 seconds..."
sleep 3
reboot

exit 0
