"""Проверка SQLite-слоя BarberFlow на временной копии БД (боевую не трогаем)."""
import os
import sqlite3
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import config  # noqa: E402

tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
tmp.close()
config.DB_PATH = tmp.name

from database import db  # noqa: E402
from database.seed import seed  # noqa: E402

db.init_db()
s1 = seed()
s2 = seed()  # идемпотентность
assert s1["services"] == 3 and s2["services"] == 3, (s1, s2)
assert s1["slots"] == 90 and s2["slots"] == 90, (s1, s2)

services = db.get_services()
assert len(services) == 3, services
masters = db.get_masters()
assert [m[1] for m in masters] == ["Алексей", "Максим", "Кирилл"], masters

# свободный слот первого мастера
mid = masters[0][0]
dates = db.get_dates_with_counts(mid)
assert len(dates) == 5, dates
free = [d for d in dates if d[1] > 0]
assert free, "у мастера должны быть свободные даты"
slots = db.get_slots_for_date(mid, free[0][0])
slot_id = next(s[0] for s in slots if s[2] == 1)

uid = db.get_or_create_user(777001, "Тест")
uid2 = db.get_or_create_user(777002, "Тест2")
assert db.get_or_create_user(777001) == uid  # идемпотентность юзера

ok, reason = db.create_booking(777001, services[0][0], mid, slot_id)
assert ok, reason
# повторная запись того же пользователя блокируется
ok, reason = db.create_booking(777001, services[0][0], mid, slot_id)
assert not ok and reason == "has_active", reason
# второй пользователь не может занять тот же слот
ok, reason = db.create_booking(777002, services[0][0], mid, slot_id)
assert not ok and reason == "occupied", reason
# чужой master_id отклоняется
other_mid = masters[1][0]
other_slots = db.get_slots_for_date(other_mid, free[0][0])
other_free = next(s[0] for s in other_slots if s[2] == 1)
ok, reason = db.create_booking(777002, services[0][0], mid, other_free)
assert not ok and reason == "bad_slot", reason

b = db.get_active_booking(777001)
assert b and b["service_name"] == services[0][1], b
assert db.cancel_active_booking(777001) is True
assert db.get_active_booking(777001) is None
assert db.cancel_active_booking(777001) is False
# слот снова свободен
assert db.get_slot(slot_id)[4] == 1

conn = sqlite3.connect(tmp.name)
leak = conn.execute(
    "SELECT COUNT(*) FROM bookings b "
    "LEFT JOIN users u ON u.id=b.user_id "
    "LEFT JOIN slots s ON s.id=b.slot_id WHERE u.id IS NULL OR s.id IS NULL"
).fetchone()[0]
conn.close()
assert leak == 0

os.unlink(tmp.name)
print("DB-CHECKS-OK: seed idempotent, booking/cancel/double-book guards pass")
