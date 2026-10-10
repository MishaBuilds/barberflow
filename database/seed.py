"""Тестовые данные BarberFlow. Только выдуманные данные для демо.

Услуги, мастера, даты и слоты генерируются локально. Часть слотов
помечается занятыми (is_available=0), чтобы проверить логику
недоступного времени. Реальных данных нет.
"""
from __future__ import annotations

from datetime import date, timedelta

from database.db import get_connection

SERVICES: list[tuple[str, int]] = [
    ("Мужская стрижка", 1200),
    ("Стрижка + борода", 1700),
    ("Оформление бороды", 700),
]

MASTERS: list[str] = ["Алексей", "Максим", "Кирилл"]

DAYS_AHEAD = 5
TIMES = ["10:00", "11:30", "13:00", "14:30", "16:00", "17:30"]


def seed() -> dict:
    """Заполнить справочники и слоты, если БД пустая. Идемпотентно."""
    conn = get_connection()
    try:
        svc_count = conn.execute("SELECT COUNT(*) FROM services").fetchone()[0]
        if svc_count == 0:
            conn.executemany(
                "INSERT INTO services (name, price) VALUES (?, ?)", SERVICES
            )

        mst_count = conn.execute("SELECT COUNT(*) FROM masters").fetchone()[0]
        if mst_count == 0:
            conn.executemany(
                "INSERT INTO masters (name) VALUES (?)", [(m,) for m in MASTERS]
            )
        conn.commit()

        masters = conn.execute("SELECT id FROM masters ORDER BY id").fetchall()
        master_ids = [int(r[0]) for r in masters]

        slot_count = conn.execute("SELECT COUNT(*) FROM slots").fetchone()[0]
        created = 0
        busy = 0
        if slot_count == 0:
            today = date.today()
            for mi, master_id in enumerate(master_ids):
                for di in range(DAYS_AHEAD):
                    day = (today + timedelta(days=di + 1)).isoformat()  # со завтра
                    for ti, t in enumerate(TIMES):
                        # Детерминированное правило: ~1/3 слотов заняты,
                        # у каждого мастера/даты есть и свободные, и занятые.
                        is_available = 0 if (mi + di + ti) % 3 == 0 else 1
                        conn.execute(
                            """
                            INSERT OR IGNORE INTO slots
                                (master_id, date, time, is_available)
                            VALUES (?, ?, ?, ?)
                            """,
                            (master_id, day, t, is_available),
                        )
                        created += 1
                        busy += 1 if is_available == 0 else 0
            conn.commit()

        return {
            "services": conn.execute("SELECT COUNT(*) FROM services").fetchone()[0],
            "masters": conn.execute("SELECT COUNT(*) FROM masters").fetchone()[0],
            "slots": conn.execute("SELECT COUNT(*) FROM slots").fetchone()[0],
            "slots_created_now": created,
            "slots_busy_now": busy,
        }
    finally:
        conn.close()
