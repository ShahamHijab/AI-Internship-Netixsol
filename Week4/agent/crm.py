import datetime, sqlite3
from .config import DB_PATH

# 4.4 CRM tables: calls, client profiles, appointments, follow-ups
def init_crm_db():
    conn = sqlite3.connect(DB_PATH)
    conn.execute('''CREATE TABLE IF NOT EXISTS calls (
        call_id TEXT PRIMARY KEY, started_at TEXT, transcript TEXT)''')
    conn.execute('''CREATE TABLE IF NOT EXISTS client_profiles (
        call_id TEXT, budget_pkr REAL, currency TEXT, country TEXT, purpose TEXT,
        preferred_city TEXT, bedrooms INTEGER)''')
    conn.execute('''CREATE TABLE IF NOT EXISTS appointments (
        call_id TEXT, event_id TEXT, property_id TEXT, start_iso TEXT, timezone TEXT, status TEXT)''')
    conn.execute('''CREATE TABLE IF NOT EXISTS follow_ups (
        call_id TEXT, due_date TEXT, reason TEXT, done INTEGER DEFAULT 0)''')
    conn.commit()
    conn.close()

init_crm_db()

def log_call(call_id, transcript):
    conn = sqlite3.connect(DB_PATH)
    conn.execute("INSERT OR REPLACE INTO calls VALUES (?, ?, ?)",
                 (call_id, datetime.datetime.now().isoformat(), transcript))
    conn.commit(); conn.close()

def log_client_profile(call_id, profile: dict):
    conn = sqlite3.connect(DB_PATH)
    conn.execute("INSERT INTO client_profiles VALUES (?, ?, ?, ?, ?, ?, ?)",
                 (call_id, profile.get("budget_pkr"), profile.get("currency"), profile.get("country"),
                  profile.get("purpose"), profile.get("preferred_city"), profile.get("bedrooms")))
    conn.commit(); conn.close()

def log_appointment(call_id, event_id, property_id, start_iso, timezone, status):
    conn = sqlite3.connect(DB_PATH)
    conn.execute("INSERT INTO appointments VALUES (?, ?, ?, ?, ?, ?)",
                 (call_id, event_id, property_id, start_iso, timezone, status))
    conn.commit(); conn.close()

def add_follow_up(call_id, due_date, reason):
    conn = sqlite3.connect(DB_PATH)
    conn.execute("INSERT INTO follow_ups (call_id, due_date, reason) VALUES (?, ?, ?)",
                 (call_id, due_date, reason))
    conn.commit(); conn.close()

