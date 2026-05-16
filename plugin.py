# -*- coding: utf-8 -*-
from __future__ import absolute_import, print_function, unicode_literals
from Plugins.Plugin import PluginDescriptor
from Screens.Screen import Screen
from Components.ActionMap import ActionMap
from Components.Label import Label
from Components.ScrollLabel import ScrollLabel
from Components.config import config, ConfigSubsection, ConfigText, ConfigSelection
from Screens.MessageBox import MessageBox
import os
import re
import sys
import base64
import time
from enigma import gRGB, eTimer, ePoint
from twisted.web.client import getPage

# التحقق من إصدار بايثون في جهاز الاستقبال لضمان التوافق (Python 2 أو Python 3)
PY3 = sys.version_info.major >= 3

# الإصدار الحالي للبلجن على جهاز المستخدم
CURRENT_VERSION = "1.2"

# إعداد وتخزين متغيرات البلجن في نظام Enigma2
config.plugins.REALCAM = ConfigSubsection()
config.plugins.REALCAM.username = ConfigText(default="", fixed_size=False)
config.plugins.REALCAM.password = ConfigText(default="", fixed_size=False)
config.plugins.REALCAM.protocol = ConfigSelection(default="cccam", choices=[("cccam", "CCCam"), ("newcamd", "Newcamd")])
config.plugins.REALCAM.destination = ConfigSelection(default="oscam", choices=[("oscam", "OSCam"), ("ncam", "NCam")])

# مسارات ملفات المحاكيات (Softcams) المستهدفة في النظام
OSCAM_PATH = "/etc/tuxbox/config/oscam.server"
NCAM_PATH = "/etc/tuxbox/config/ncam.server"

# بيانات الاتصال الخاصة بسيرفرات البث والمنافذ
CC_HOST = "realcam.site"
CC_PORTS = ["11130", "11123"]

NC_HOST = "realcam.site"
NC_PORTS = ["11131", "11122"]
NC_DESKEY = "0102030405060708091011121314"

# الرابط الأساسي الموحد والمستقر للمستودع الخاص بك على GitHub
UPDATE_BASE = "https://raw.githubusercontent.com/sky-info1/realcam/main/"
NOTICE_URL = UPDATE_BASE + "notice.txt"
PACKAGES_URL = UPDATE_BASE + "packages.txt"

def set_timer_callback(timer, callback):
    try:
        return timer.timeout.connect(callback)
    except AttributeError:
        timer.callback.append(callback)
        return None

# --- شريط الأخبار المتحرك (Ticker) ---
current_ticker = None

class REALCAMTicker(Screen):
    skin = """
    <screen name="REALCAMTicker" position="0,1000" size="1920,80" flags="wfNoBorder" backgroundColor="#FF000000" zPosition="100">
        <eLabel position="0,0" size="1920,3" backgroundColor="#FF0000" zPosition="101" />
        <widget name="ticker_label" position="1920,20" size="20000,45" font="Regular;34" foregroundColor="#FFFFFF" backgroundColor="transparent" halign="left" noWrap="1" zPosition="102" />
        <eLabel position="1700,0" size="220,80" backgroundColor="#FF000000" zPosition="103" />
        <eLabel text="عاجل :" position="1720,18" size="180,45" font="Regular;36" foregroundColor="#FF0000" backgroundColor="transparent" zPosition="104" halign="center" />
        <eLabel text="[EXIT to close]" position="20,25" size="200,35" font="Regular;22" foregroundColor="#888888" backgroundColor="transparent" zPosition="105" />
    </screen>"""

    def __init__(self, session, text):
        Screen.__init__(self, session)
        separator = " " * 35
        full_text = separator.join([text] * 30)
        
        self["ticker_label"] = Label(full_text)
        self["actions"] = ActionMap(["OkCancelActions"], {"cancel": self.closeTicker}, -1)
        
        self.x_pos = 1920
        self.move_timer = eTimer()
        set_timer_callback(self.move_timer, self.updatePosition)
        self.move_timer.start(50, False)

    def updatePosition(self):
        self.x_pos -= 6 
        if self.x_pos < -15000:
            self.x_pos = 1920
        if self["ticker_label"].instance:
            self["ticker_label"].instance.move(ePoint(self.x_pos, 20))

    def closeTicker(self):
        global current_ticker
        current_ticker = None
        if self.move_timer:
            self.move_timer.stop()
        self.close()

# --- محرك ذكي مدمج في الخلفية (إشعار الأخبار + فحص التحديث الصامت المؤمن) ---
global_session = None
background_timer = None
last_notice_content = ""

def check_background_notice():
    global global_session
    if global_session:
        cache_buster = "?t=" + str(time.time())
        url = (NOTICE_URL + cache_buster).encode("utf-8") if PY3 else NOTICE_URL + cache_buster
        getPage(url, timeout=8).addCallback(process_remote_data).addErrback(lambda _: None)

def process_remote_data(data):
    global global_session, last_notice_content, current_ticker
    if data:
        text = data.decode("utf-8", errors="ignore").strip() if PY3 else data.strip()
        if not text:
            return
            
        lines = text.split('\n', 1)
        remote_version = lines[0].strip()
        ticker_text = lines[1].strip() if len(lines) > 1 else ""

        if ticker_text and ticker_text != last_notice_content and global_session:
            last_notice_content = ticker_text
            if current_ticker:
                try:
                    current_ticker.closeTicker()
                except:
                    pass
            current_ticker = global_session.open(REALCAMTicker, ticker_text)
        elif not ticker_text:
            last_notice_content = ""
            if current_ticker:
                try:
                    current_ticker.closeTicker()
                except:
                    pass
                    
        # مقارنة رقم إصدار السيرفر بالإصدار المحلي الحالي لتفعيل التحديث التلقائي
        if remote_version > CURRENT_VERSION:
            do_silent_update()

def do_silent_update():
    # استخدام الطابع الزمني الفعلي كـ Cache Buster لكسر كاش خوادم GitHub تماماً
    cache_buster = "?t=" + str(int(time.time()))
    plugin_dir = "/usr/lib/enigma2/python/Plugins/Extensions/REALCAM/"
    
    # بناء الأمر البرمجي المتسلسل: التحميل، مسح الكاش المترجم القديم لضمان القراءة الحية، ثم sync
    cmd = (
        "wget -q --no-check-certificate -O {0}plugin.py \"{1}plugin.py{2}\" && "
        "wget -q --no-check-certificate -O {0}plugin.png \"{1}plugin.png{2}\" && "
        "wget -q --no-check-certificate -O {0}setup.xml \"{1}setup.xml{2}\" && "
        "wget -q --no-check-certificate -O {0}__init__.py \"{1}__init__.py{2}\" && "
        "rm -f {0}*.pyc && "
        "sync"
    ).format(plugin_dir, UPDATE_BASE, cache_buster)
    
    # تنفيذ السكربت صامتاً 100% في خلفية نظام التشغيل بدون أي إشعار مزعج للمستخدم
    os.system("sh -c '" + cmd + "'")

def autostart(reason, **kwargs):
    global global_session, background_timer
    if reason == 0 and "session" in kwargs:
        global_session = kwargs["session"]
        if background_timer is None:
            background_timer = eTimer()
            set_timer_callback(background_timer, check_background_notice)
            background_timer.start(180000, False)
            eTimer.singleShot(15000, check_background_notice)

# --- شاشة البلجن الرئيسية (REALCAM Screen Interface) ---
class REALCAMScreen(Screen):
    skin = """
    <screen name="REALCAMScreen" position="center,center" size="1150,850" title="REALCAM Config" backgroundColor="#1A1A1A">
        <eLabel position="20,20" size="1110,810" backgroundColor="#2C2C2C" zPosition="-1" />
        
        <widget name="title_info_label" position="30,30" size="1090,90" font="Regular;28" halign="center" valign="center" foregroundColor="#FFFFFF" backgroundColor="#3A3A3A" transparent="0" />
        
        <widget name="plugin_header_name" position="40,50" size="400,50" font="Regular;32" halign="left" valign="center" foregroundColor="#FFD700" transparent="1" backgroundColor="#3A3A3A" />
        <widget name="date_label" position="720,40" size="380,30" font="Regular;24" halign="right" valign="center" foregroundColor="#FFFFFF" transparent="1" backgroundColor="#3A3A3A" />
        <eLabel position="800,75" size="300,2" backgroundColor="#FFD700" zPosition="2" />
        <widget name="time_label" position="720,82" size="380,30" font="Regular;24" halign="right" valign="center" foregroundColor="#FFD700" transparent="1" backgroundColor="#3A3A3A" />
        
        <eLabel position="20,130" size="1110,2" backgroundColor="#FFD700" />
        <eLabel position="20,700" size="1110,2" backgroundColor="#FFD700" /> 
        
        <widget name="username_label" position="60,160" size="220,50" font="Regular;28" halign="left" valign="center" foregroundColor="#FFD700" transparent="1" />
        <widget name="username_value" position="300,160" size="350,50" font="Regular;28" halign="left" valign="center" transparent="1" backgroundColor="#3A3A3A" />
        <widget name="password_label" position="60,230" size="220,50" font="Regular;28" halign="left" valign="center" foregroundColor="#FFD700" transparent="1" />
        <widget name="password_value" position="300,230" size="350,50" font="Regular;28" halign="left" valign="center" transparent="1" backgroundColor="#3A3A3A" />
        <widget name="protocol_label" position="60,300" size="220,50" font="Regular;28" halign="left" valign="center" foregroundColor="#FFD700" transparent="1" />
        <widget name="protocol_value" position="300,300" size="350,50" font="Regular;28" halign="left" valign="center" transparent="1" backgroundColor="#3A3A3A" />
        <widget name="destination_label" position="60,370" size="220,50" font="Regular;28" halign="left" valign="center" foregroundColor="#FFD700" transparent="1" />
        <widget name="destination_value" position="300,370" size="350,50" font="Regular;28" halign="left" valign="center" transparent="1" backgroundColor="#3A3A3A" />
        <widget name="server_state_label" position="60,440" size="220,50" font="Regular;28" halign="left" valign="center" foregroundColor="#FFD700" transparent="1" />
        <widget name="status_led" position="300,440" size="40,50" font="Regular;35" halign="center" valign="center" transparent="1" />
        <widget name="server_state_value" position="350,440" size="300,50" font="Regular;28" halign="left" valign="center" transparent="1" backgroundColor="#3A3A3A" />
        
        <eLabel position="680,150" size="2,480" backgroundColor="#444444" />
        
        <widget name="packages_title" position="700,160" size="400,50" font="Regular;26" halign="center" valign="center" foregroundColor="#FFD700" backgroundColor="#3A3A3A" transparent="0" />
        <widget name="packages_text" position="700,220" size="400,460" font="Regular;22" halign="left" valign="top" foregroundColor="#FFFFFF" transparent="1" />
        <widget name="version_label" position="60,640" size="500,40" font="Regular;24" halign="left" valign="center" foregroundColor="#CCCCCC" transparent="1" />
        
        <widget name="key_yellow" position="150,730" size="200,60" font="Regular;30" halign="center" valign="center" backgroundColor="#A08500" transparent="0" foregroundColor="#FFFFFF" text="Restart" />
        <widget name="key_blue" position="380,730" size="200,60" font="Regular;30" halign="center" valign="center" backgroundColor="#000080" transparent="0" foregroundColor="#FFFFFF" text="Clear" />
        <widget name="key_red" position="610,730" size="200,60" font="Regular;30" halign="center" valign="center" backgroundColor="#9F1313" transparent="0" foregroundColor="#FFFFFF" text="Delete" />
        <widget name="key_green" position="840,730" size="200,60" font="Regular;30" halign="center" valign="center" backgroundColor="#1F771F" transparent="0" foregroundColor="#FFFFFF" text="Save" />
    </screen>"""

    def __init__(self, session):
        Screen.__init__(self, session)
        self.session = session
        self.temp_username = config.plugins.REALCAM.username.value
        self.temp_password = config.plugins.REALCAM.password.value
        self.active_panel = "left"
        self["key_red"] = Label("Delete")
        self["key_green"] = Label("Save")
        self["key_yellow"] = Label("Restart")
        self["key_blue"] = Label("Clear")
        
        self["title_info_label"] = Label("")
        self["plugin_header_name"] = Label("REALCAM v" + CURRENT_VERSION)
        self["date_label"] = Label("")
        self["time_label"] = Label("")
        
        self.clockTimer = eTimer()
        set_timer_callback(self.clockTimer, self.updateClock)
        self.clockTimer.start(1000, False)
        self.updateClock()
        
        self["username_label"] = Label("Username:")
        self["password_label"] = Label("Password:")
        self["protocol_label"] = Label("Protocol:")
        self["destination_label"] = Label("Destination:")
        self["server_state_label"] = Label("Server Status:")
        self["username_value"] = Label(self.temp_username)
        self["password_value"] = Label(self.temp_password)
        self["protocol_value"] = Label(config.plugins.REALCAM.protocol.value)
        self["destination_value"] = Label(config.plugins.REALCAM.destination.value)
        self["status_led"] = Label("●")
        self["server_state_value"] = Label("Checking...")
        self["packages_title"] = Label("📦 Available Packages")
        self["packages_text"] = ScrollLabel("Loading packages...")
        self["version_label"] = Label("Version: %s" % CURRENT_VERSION)

        self["actions"] = ActionMap(["OkCancelActions", "ColorActions", "DirectionActions", "NumberActions"], {
            "ok": self.keyOk,
            "cancel": self.close,
            "green": self.saveConfig,
            "red": self.keyRed,
            "yellow": self.restartSoftcam,
            "blue": self.clearSelectedField,
            "up": self.keyUp,
            "down": self.keyDown,
            "left": self.keyLeft,
            "right": self.keyRight,
            "pageUp": self.pageUp,
            "pageDown": self.pageDown,
            "0": lambda: self.keyNumber("0"), "1": lambda: self.keyNumber("1"), "2": lambda: self.keyNumber("2"),
            "3": lambda: self.keyNumber("3"), "4": lambda: self.keyNumber("4"), "5": lambda: self.keyNumber("5"),
            "6": lambda: self.keyNumber("6"), "7": lambda: self.keyNumber("7"), "8": lambda: self.keyNumber("8"),
            "9": lambda: self.keyNumber("9"),
        }, -1)
        
        self.config_items = ["username", "password", "protocol", "destination"]
        self.current_focus_index = 0

        self.flickerTimer = eTimer()
        set_timer_callback(self.flickerTimer, self.flickerEffect)
        self.flicker_on = False

        self.checkServerTimer = eTimer()
        set_timer_callback(self.checkServerTimer, self.check_oscam_status)
        self.onLayoutFinish.append(self.startTimers)
        
        # استدعاء دالة جلب حزمة الباقات الحية من السيرفر عند فتح الشاشة
        self.onLayoutFinish.append(self.load_packages)

    def load_packages(self):
        cache_buster = "?t=" + str(time.time())
        url = (PACKAGES_URL + cache_buster).encode("utf-8") if PY3 else PACKAGES_URL + cache_buster
        getPage(url, timeout=5).addCallback(self.packages_loaded).addErrback(self.packages_error)

    def packages_loaded(self, data):
        if data:
            text = data.decode("utf-8", errors="ignore").strip() if PY3 else data.strip()
            self["packages_text"].setText(text)
        else:
            self["packages_text"].setText("No packages available.")

    def packages_error(self, error):
        self["packages_text"].setText("Failed to load packages from server.\nPlease check your internet connection.")

    def updateClock(self):
        day_en = time.strftime("%A")
        date_str = time.strftime("%Y-%m-%d")
        full_date = "{0}   {1}".format(day_en, date_str)
        self["date_label"].setText(full_date)
        
        time_str = time.strftime("%H:%M:%S")
        self["time_label"].setText(time_str)

    def startTimers(self):
        self.updateFocus()
        self.checkServerTimer.start(2000, True)

    def check_oscam_status(self):
        dest = config.plugins.REALCAM.destination.value
        path = OSCAM_PATH.replace(".server", ".conf") if dest == "oscam" else NCAM_PATH.replace(".server", ".conf")
        port = "8888"
        user = ""
        pwd = ""
        try:
            if os.path.exists(path):
                with open(path, 'r') as f:
                    content = f.read()
                    webif = re.search(r'\[webif\](.*?)(\[|$)', content, re.DOTALL | re.IGNORECASE)
                    if webif:
                        b = webif.group(1)
                        p = re.search(r'httpport\s*=\s*\+?([0-9]+)', b, re.IGNORECASE)
                        if p: port = p.group(1)
                        u = re.search(r'httpuser\s*=\s*([^\s]+)', b, re.IGNORECASE)
                        if u: user = u.group(1)
                        pw = re.search(r'httppwd\s*=\s*([^\s]+)', b, re.IGNORECASE)
                        if pw: pwd = pw.group(1)
        except:
            pass

        url_str = "http://127.0.0.1:{0}/status.html".format(port)
        url_bytes = url_str.encode("utf-8") if PY3 else url_str
        headers = {}
        if user and pwd:
            auth_string = "{0}:{1}".format(user, pwd)
            base64_str = base64.b64encode(auth_string.encode("utf-8")).decode("utf-8")
            if PY3:
                headers[b"Authorization"] = [b"Basic " + base64_str.encode("utf-8")]
            else:
                headers["Authorization"] = ["Basic " + base64_str]

        d = getPage(url_bytes, headers=headers, timeout=3)
        d.addCallback(self.parse_oscam_xml).addErrback(self.oscam_error)

    def parse_oscam_xml(self, data):
        if data:
            data_str = data.decode("utf-8", errors="ignore").upper() if PY3 else data.upper()
            protocol = config.plugins.REALCAM.protocol.value
            
            t1 = "REALCAM_@SKYINFOTV_C" if protocol == "cccam" else "REALCAM_@SKYINFOTV_N"
            found = False
            
            rows = re.split(r'(?i)<tr', data_str)
            for row in rows:
                if t1 in row:
                    found = True
                    if "CONNECTED" in row or "CARDOK" in row or "ACTIVE" in row or "IDLE" in row:
                        self.set_status_display("Online", 0x00FF00)
                    else:
                        self.set_status_display("Offline", 0xFF0000)
                    break
            if not found:
                self.set_status_display("Offline", 0xFF0000)
        self.checkServerTimer.start(5000, True)

    def oscam_error(self, error):
        self.set_status_display("WebIF Off", 0xFF0000)
        self.checkServerTimer.start(5000, True)

    def set_status_display(self, text, color):
        self["server_state_value"].setText(text)
        if self["status_led"].instance:
            self["status_led"].instance.removeForegroundColor()
            self["status_led"].instance.setForegroundColor(gRGB(color))
        if self["server_state_value"].instance:
            self["server_state_value"].instance.removeForegroundColor()
            self["server_state_value"].instance.setForegroundColor(gRGB(color))

    def updateFocus(self):
        gold = gRGB(0xFFD700)
        yellow = gRGB(0xFFFFFF00)
        self.flickerTimer.stop()
        
        for i in self.config_items:
            l = self.get(i + "_label")
            v = self.get(i + "_value")
            if l and l.instance: l.instance.setForegroundColor(gold)
            if v and v.instance: v.instance.setForegroundColor(gold)
            
        if self["packages_title"].instance:
            self["packages_title"].instance.setForegroundColor(gold)
            
        if self.active_panel == "left":
            curr = self.config_items[self.current_focus_index]
            l = self.get(curr + "_label")
            v = self.get(curr + "_value")
            if l and l.instance: l.instance.setForegroundColor(yellow)
            if v and v.instance: v.instance.setForegroundColor(yellow)
        else:
            if self["packages_title"].instance:
                self["packages_title"].instance.setForegroundColor(yellow)
                
        self.flickerTimer.start(250, True)

    def flickerEffect(self):
        gold = gRGB(0xFFD700)
        yellow = gRGB(0xFFFFFF00)
        self.flicker_on = not self.flicker_on
        color = gold if self.flicker_on else yellow
        
        if self.active_panel == "left":
            curr = self.config_items[self.current_focus_index]
            l = self.get(curr + "_label")
            v = self.get(curr + "_value")
            if l and l.instance: l.instance.setForegroundColor(color)
            if v and v.instance: v.instance.setForegroundColor(color)
        else:
            if self["packages_title"].instance:
                self["packages_title"].instance.setForegroundColor(color)
                
        self.flickerTimer.start(250, True)

    def pageUp(self):
        self["packages_text"].pageUp()

    def pageDown(self):
        self["packages_text"].pageDown()

    def keyUp(self):
        if self.active_panel == "right":
            self.pageUp()
        elif self.current_focus_index > 0:
            self.current_focus_index -= 1
            self.updateFocus()

    def keyDown(self):
        if self.active_panel == "right":
            self.pageDown()
        elif self.current_focus_index < len(self.config_items) - 1:
            self.current_focus_index += 1
            self.updateFocus()

    def keyLeft(self):
        if self.active_panel == "right":
            self.active_panel = "left"
            self.updateFocus()
        else:
            curr = self.config_items[self.current_focus_index]
            if curr in ["protocol", "destination"]:
                getattr(config.plugins.REALCAM, curr).handleKey(0, 5)
                self[curr + "_value"].setText(getattr(config.plugins.REALCAM, curr).value)

    def keyRight(self):
        if self.active_panel == "left":
            curr = self.config_items[self.current_focus_index]
            if curr in ["protocol", "destination"]:
                getattr(config.plugins.REALCAM, curr).handleKey(0, 6)
                self[curr + "_value"].setText(getattr(config.plugins.REALCAM, curr).value)
            else:
                self.active_panel = "right"
                self.updateFocus()

    def keyNumber(self, number):
        if self.active_panel == "left":
            curr = self.config_items[self.current_focus_index]
            if curr == "username":
                self.temp_username += number
                self["username_value"].setText(self.temp_username)
            elif curr == "password":
                self.temp_password += number
                self["password_value"].setText(self.temp_password)

    def keyRed(self):
        self.keyBackspace()

    def keyBackspace(self):
        if self.active_panel == "left":
            curr = self.config_items[self.current_focus_index]
            if curr == "username" and len(self.temp_username) > 0:
                self.temp_username = self.temp_username[:-1]
                self["username_value"].setText(self.temp_username)
            elif curr == "password" and len(self.temp_password) > 0:
                self.temp_password = self.temp_password[:-1]
                self["password_value"].setText(self.temp_password)

    def keyOk(self):
        if self.active_panel == "left":
            curr = self.config_items[self.current_focus_index]
            if curr in ["protocol", "destination"]:
                self.keyRight()

    def restartSoftcam(self):
        os.system("/etc/init.d/softcam restart")
        self.session.open(MessageBox, "Softcam Restarted Successfully!", MessageBox.TYPE_INFO, timeout=4)
        self.checkServerTimer.start(4000, True)

    def saveConfig(self):
        config.plugins.REALCAM.username.value = self.temp_username
        config.plugins.REALCAM.password.value = self.temp_password
        for i in self.config_items:
            getattr(config.plugins.REALCAM, i).save()
        
        p = config.plugins.REALCAM.protocol.value
        d = config.plugins.REALCAM.destination.value
        f_p = OSCAM_PATH if d == "oscam" else NCAM_PATH
        
        if not self.temp_username or not self.temp_password:
            self.session.open(MessageBox, "User or Pass is empty!", MessageBox.TYPE_INFO)
            return
            
        if p == "cccam":
            r = self.gen_cccam(self.temp_username, self.temp_password, 1, 1)
        else:
            r = self.gen_newcamd(self.temp_username, self.temp_password, 1, 1)
            
        self.add_rep(f_p, r, p)
        self.session.open(MessageBox, "Configuration saved successfully!", MessageBox.TYPE_INFO, timeout=5)

    def clearSelectedField(self):
        if self.active_panel == "left":
            curr = self.config_items[self.current_focus_index]
            if curr == "username":
                self.temp_username = ""
                self["username_value"].setText("")
            elif curr == "password":
                self.temp_password = ""
                self["password_value"].setText("")

    def close(self):
        self.clockTimer.stop()
        self.flickerTimer.stop()
        if self.temp_username != config.plugins.REALCAM.username.value or self.temp_password != config.plugins.REALCAM.password.value:
            self.session.openWithCallback(self.exit_confirm, MessageBox, "Changes not saved. Exit?", MessageBox.TYPE_YESNO)
        else:
            Screen.close(self)

    def exit_confirm(self, result):
        if result:
            Screen.close(self)

    def add_rep(self, p, r, proto):
        try:
            with open(p, 'r') as f:
                c = f.read()
        except:
            c = ""
            
        c = re.sub(r'\[reader\]\s*label\s*=\s*REALCAM_@skyinfotv_.*?(?=\[reader\]|\Z)', '', c, flags=re.DOTALL | re.IGNORECASE)
        c = re.sub(r'\[reader\]\s*label\s*=\s*REALCAM_[CN].*?(?=\[reader\]|\Z)', '', c, flags=re.DOTALL | re.IGNORECASE)
        
        c = c.strip() + "\n" + r.strip() + "\n"
            
        with open(p, 'w') as f:
            f.write(c)

    def gen_cccam(self, u, p, start_n, g):
        result = ""
        for index, port in enumerate(CC_PORTS):
            current_n = start_n + index 
            result += """
[reader]
label = REALCAM_@skyinfotv_C{0}
description = REALCAM SERVER CONTACT US VIA TELEGRAM @skyinfotv
enable = 1
protocol = cccam
device = {1},{2}
user = {3}
password = {4}
inactivitytimeout = 30
cccversion = 2.3.2
disablecrccws = 1
disableserverfilter = 1
keepalive = 1
cacheex = 1
cacheex_allow_request = 1
cacheex_drop_csp = 1
cacheex_allow_filter = 0
group = {5}
uniq = 1
dropbadcws = 1
connectoninit = 1
reconnecttimeout = 2
""".format(current_n, CC_HOST, port, u, p, g)
        return result

    def gen_newcamd(self, u, p, start_n, g):
        result = ""
        for index, port in enumerate(NC_PORTS):
            current_n = start_n + index
            result += """
[reader]
label = REALCAM_@skyinfotv_N{0}
description = REALCAM SERVER CONTACT US VIA TELEGRAM @skyinfotv
enable = 1
protocol = newcamd
device = {1},{2}
user = {3}
password = {4}
deskey = {5}
inactivitytimeout = 30
disablecrccws = 1
disableserverfilter = 1
cacheex = 1
cacheex_allow_request = 1
cacheex_drop_csp = 1
cacheex_allow_filter = 0
group = {6}
uniq = 1
dropbadcws = 1
connectoninit = 1
reconnecttimeout = 2
""".format(current_n, NC_HOST, port, u, p, NC_DESKEY, g)
        return result

def main(session, **kwargs):
    session.open(REALCAMScreen)

def Plugins(**kwargs):
    return [
        PluginDescriptor(where=PluginDescriptor.WHERE_SESSIONSTART, fnc=autostart),
        PluginDescriptor(name="REALCAM", description="REALCAM Config", where=PluginDescriptor.WHERE_PLUGINMENU, fnc=main, icon="plugin.png")
    ]
