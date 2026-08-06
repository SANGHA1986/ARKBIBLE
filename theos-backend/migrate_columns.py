from sqlalchemy import text
from database import engine

alters = [
    "ALTER TABLE users ADD COLUMN membership_status VARCHAR(30) DEFAULT 'Free_Trial'",
    "ALTER TABLE users ADD COLUMN trial_started_at DATETIME",
    "ALTER TABLE users ADD COLUMN limited_started_at DATETIME",
    "ALTER TABLE users ADD COLUMN subscribed_until DATETIME",
    "ALTER TABLE users ADD COLUMN daily_view_limit INTEGER DEFAULT 20",
    "ALTER TABLE language_data ADD COLUMN strong_number VARCHAR(16)",
]

with engine.begin() as conn:
    for sql in alters:
        try:
            conn.execute(text(sql))
            print("ok", sql[:50])
        except Exception as e:
            print("skip", str(e)[:80])
