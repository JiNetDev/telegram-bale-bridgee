import sqlite3
import secrets
import time
import threading
import requests
import os

TG_TOKEN = "8596191469:AAEMKEUpKQBxTYU-tbzALUzJkWDOGKyk8_s"
BALE_TOKEN = "1819784904:V3xHKd-N2Upe6iDqvzBKFtv-aycts0KH5jM"

TG_API = f"https://api.telegram.org/bot{TG_TOKEN}"
BALE_API = f"https://tapi.bale.ai/bot{BALE_TOKEN}"

DB_PATH = '/tmp/bridge.db'


def db_query(query, params=(), fetch=False):
    conn = sqlite3.connect(DB_PATH, timeout=10)
    c = conn.cursor()
    c.execute(query, params)
    if fetch:
        result = c.fetchone()
        conn.commit()
        conn.close()
        return result[0] if result else None
    conn.commit()
    conn.close()


def init_db():
    conn = sqlite3.connect(DB_PATH, timeout=10)
    c = conn.cursor()
    c.execute('CREATE TABLE IF NOT EXISTS users (tg TEXT PRIMARY KEY, bale TEXT)')
    c.execute('CREATE TABLE IF NOT EXISTS codes (code TEXT PRIMARY KEY, platform TEXT, uid TEXT)')
    c.execute('CREATE TABLE IF NOT EXISTS ids (platform TEXT PRIMARY KEY, lid INTEGER)')
    conn.commit()
    conn.close()


def send_tg(chat_id, text):
    try:
        requests.post(f"{TG_API}/sendMessage", json={"chat_id": chat_id, "text": text}, timeout=10)
    except:
        pass


def send_bale(uid, text):
    try:
        requests.post(f"{BALE_API}/sendMessage", json={"chat_id": uid, "text": text}, timeout=10)
    except:
        pass


def handle_tg(msg):
    try:
        if 'message' not in msg: return
        m = msg['message']
        chat = str(m['chat']['id'])
        text = m.get('text', '')

        if text == '/start':
            bale = db_query("SELECT bale FROM users WHERE tg=?", (chat,), True)
            if bale:
                send_tg(chat, "✅ شما متصل هستید")
            else:
                code = secrets.token_hex(4)
                conn = sqlite3.connect(DB_PATH)
                conn.execute("INSERT OR REPLACE INTO codes VALUES (?,?,?)", (code, 'tg', chat))
                conn.commit()
                conn.close()
                send_tg(chat, f"🔗 کد: {code}\nاین کد رو به بله بفرست")
            return

        bale = db_query("SELECT bale FROM users WHERE tg=?", (chat,), True)
        if bale:
            send_bale(bale, f"📱 از تلگرام:\n{text}")
            send_tg(chat, "✅ ارسال شد")
        else:
            send_tg(chat, "⚠️ /start رو بزن")
    except:
        pass


def handle_bale(msg):
    try:
        if 'message' not in msg: return
        m = msg['message']
        uid = str(m['from']['id'])
        text = m.get('text', '')

        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        c.execute("SELECT platform, uid FROM codes WHERE code=?", (text,))
        row = c.fetchone()

        if row and row[0] == 'tg':
            c.execute("INSERT OR REPLACE INTO users VALUES (?,?)", (row[1], uid))
            c.execute("DELETE FROM codes WHERE code=?", (text,))
            conn.commit()
            conn.close()
            send_tg(row[1], "✅ اتصال برقرار شد!")
            send_bale(uid, "✅ متصل شدی!")
            return
        conn.close()

        tg = db_query("SELECT tg FROM users WHERE bale=?", (uid,), True)
        if tg:
            send_tg(tg, f"📱 از بله:\n{text}")
            send_bale(uid, "✅ ارسال شد")
        else:
            code = secrets.token_hex(4)
            conn = sqlite3.connect(DB_PATH)
            conn.execute("INSERT OR REPLACE INTO codes VALUES (?,?,?)", (code, 'bale', uid))
            conn.commit()
            conn.close()
            send_bale(uid, f"🔗 کد: {code}\nاین کد رو به تلگرام بفرست @ghostShadowwbot")
    except:
        pass


def poll_tg():
    last = db_query("SELECT lid FROM ids WHERE platform='tg'", (), True) or 0
    while True:
        try:
            r = requests.get(f"{TG_API}/getUpdates", params={"offset": last + 1, "timeout": 20}, timeout=25)
            if r.status_code == 200:
                for u in r.json().get('result', []):
                    handle_tg(u)
                    last = u.get('update_id', last)
                    conn = sqlite3.connect(DB_PATH)
                    conn.execute("INSERT OR REPLACE INTO ids VALUES ('tg', ?)", (last,))
                    conn.commit()
                    conn.close()
        except:
            time.sleep(5)


def poll_bale():
    last = db_query("SELECT lid FROM ids WHERE platform='bale'", (), True) or 0
    while True:
        try:
            r = requests.get(f"{BALE_API}/getUpdates", params={"offset": last + 1, "timeout": 20}, timeout=25)
            if r.status_code == 200:
                for u in r.json().get('result', []):
                    handle_bale(u)
                    last = u.get('update_id', last)
                    conn = sqlite3.connect(DB_PATH)
                    conn.execute("INSERT OR REPLACE INTO ids VALUES ('bale', ?)", (last,))
                    conn.commit()
                    conn.close()
        except:
            time.sleep(5)


init_db()
threading.Thread(target=poll_tg, daemon=True).start()
threading.Thread(target=poll_bale, daemon=True).start()

while True:
    time.sleep(60)
