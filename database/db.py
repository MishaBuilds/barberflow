"""SQLite-слой BarberFlow.

Таблицы (строго по ТЗ):
  users:    id, telegram_id (UNIQUE), name
  services: id, name, price
  masters:  id, name
  slots:    id, master_id (FK), date (TEXT YYYY-MM-DD), time (TEXT HH:MM), is_available (1/0)
  bookings: id, user_id (FK), service_id (FK), master_id (FK),
            slot_id (FK UNIQUE), created_at, status

Ключевая идея против двойного бронирования: создание записи выполняется
в одной транзакции BEGIN IMMEDIATE: проверяем is_available=1, вставляем
бронирование и гасим слот. Два параллельных вызова не смогут занять
один и тот же slot_id.
"""
from __future__ import annotations

import sqlite3
from datetime import datetime

from config import DB_PATH

SCHEMA = """
PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    telegram_id INTEGER UNIQUE NOT NULL,
    name TEXT NOT NULL DEFAULT ''
);

CREATE TABLE IF NOT EXISTS services (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    price INTEGER NOT NULL
);

CREATE TABLE IF NOT EXISTS masters (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS slots (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    master_id INTEGER NOT NULL REFERENCES masters(id),
    date TEXT NOT NULL,
    time TEXT NOT NULL,
    is_available INTEGER NOT NULL DEFAULT 1,
    UNIQUE (master_id, date, time)
);

CREATE TABLE IF NOT EXISTS bookings (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL REFERENCES users(id),
    service_id INTEGER NOT NULL REFERENCES services(id),
    master_id INTEGER NOT NULL REFERENCES masters(id),
    slot_id INTEGER NOT NULL UNIQUE REFERENCES slots(id),
    created_at TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'active'
);
"""


def get_connection() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH, timeout=10)
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_db() -> None:
    conn = get_connection()
    try:
        conn.executescript(SCHEMA)
        conn.commit()
    finally:
        conn.close()


# --- users ---

def get_or_create_user(telegram_id: int, name: str = "") -> int:
    """Возвращает внутренний id пользователя, создаёт при отсутствии."""
    conn = get_connection()
    try:
        conn.execute(
            "INSERT OR IGNORE INTO users (telegram_id, name) VALUES (?, ?)",
            (telegram_id, name or ""),
        )
        conn.commit()
        row = conn.execute(
            "SELECT id FROM users WHERE telegram_id = ?", (telegram_id,)
        ).fetchone()
        return int(row[0])
    finally:
        conn.close()


# --- catalogs ---

def get_services() -> list[tuple[int, str, int]]:
    conn = get_connection()
    try:
        return [
            (r[0], r[1], r[2])
            for r in conn.execute(
                "SELECT id, name, price FROM services ORDER BY id"
            ).fetchall()
        ]
    finally:
        conn.close()


def get_service(service_id: int) -> tuple[int, str, int] | None:
    conn = get_connection()
    try:
        row = conn.execute(
            "SELECT id, name, price FROM services WHERE id = ?", (service_id,)
        ).fetchone()
        return (row[0], row[1], row[2]) if row else None
    finally:
        conn.close()


def get_masters() -> list[tuple[int, str]]:
    conn = get_connection()
    try:
        return [
            (r[0], r[1])
            for r in conn.execute("SELECT id, name FROM masters ORDER BY id").fetchall()
        ]
    finally:
        conn.close()


def get_master(master_id: int) -> tuple[int, str] | None:
    conn = get_connection()
    try:
        row = conn.execute(
            "SELECT id, name FROM masters WHERE id = ?", (master_id,)
        ).fetchone()
        return (row[0], row[1]) if row else None
    finally:
        conn.close()


# --- slots ---

def get_dates_with_counts(master_id: int) -> list[tuple[str, int]]:
    """Даты мастера + количество свободных слотов. Только даты, где есть слоты."""
    conn = get_connection()
    try:
        rows = conn.execute(
            """
            SELECT date, SUM(CASE WHEN is_available = 1 THEN 1 ELSE 0 END) AS free_cnt
            FROM slots
            WHERE master_id = ?
            GROUP BY date
            ORDER BY date
            """,
            (master_id,),
        ).fetchall()
        return [(r[0], int(r[1] or 0)) for r in rows]
    finally:
        conn.close()


def get_slots_for_date(master_id: int, date: str) -> list[tuple[int, str, int]]:
    """Слоты мастера на дату: (id, time, is_available). Отсортированы по времени."""
    conn = get_connection()
    try:
        rows = conn.execute(
            """
            SELECT id, time, is_available FROM slots
            WHERE master_id = ? AND date = ?
            ORDER BY time
            """,
            (master_id, date),
        ).fetchall()
        return [(int(r[0]), r[1], int(r[2])) for r in rows]
    finally:
        conn.close()


def get_slot(slot_id: int) -> tuple[int, int, str, str, int] | None:
    conn = get_connection()
    try:
        row = conn.execute(
            "SELECT id, master_id, date, time, is_available FROM slots WHERE id = ?",
            (slot_id,),
        ).fetchone()
        if not row:
            return None
        return (int(row[0]), int(row[1]), row[2], row[3], int(row[4]))
    finally:
        conn.close()


# --- bookings ---

def get_active_booking(telegram_id: int) -> dict | None:
    """Текущая (active) запись пользователя или None."""
    conn = get_connection()
    try:
        row = conn.execute(
            """
            SELECT b.id, s.name, s.price, m.name, sl.date, sl.time, b.created_at
            FROM bookings b
            JOIN users u ON u.id = b.user_id
            JOIN services s ON s.id = b.service_id
            JOIN masters m ON m.id = b.master_id
            JOIN slots sl ON sl.id = b.slot_id
            WHERE u.telegram_id = ? AND b.status = 'active'
            ORDER BY b.id DESC
            LIMIT 1
            """,
            (telegram_id,),
        ).fetchone()
        if not row:
            return None
        return {
            "id": int(row[0]),
            "service_name": row[1],
            "price": int(row[2]),
            "master_name": row[3],
            "date": row[4],
            "time": row[5],
            "created_at": row[6],
        }
    finally:
        conn.close()


def create_booking(
    telegram_id: int, service_id: int, master_id: int, slot_id: int
) -> tuple[bool, str]:
    """Атомарно создать запись.

    Возвращает (True, 'ok') либо (False, причина):
      'has_active' — у пользователя уже есть активная запись;
      'occupied'   — слот уже занят;
      'bad_slot'   — слот не принадлежит выбранному мастеру/не найден.
    """
    conn = get_connection()
    try:
        conn.execute("BEGIN IMMEDIATE")

        user_row = conn.execute(
            "SELECT id FROM users WHERE telegram_id = ?", (telegram_id,)
        ).fetchone()
        if not user_row:
            conn.execute("ROLLBACK")
            return False, "no_user"
        user_id = int(user_row[0])

        active = conn.execute(
            "SELECT id FROM bookings WHERE user_id = ? AND status = 'active' LIMIT 1",
            (user_id,),
        ).fetchone()
        if active:
            conn.execute("ROLLBACK")
            return False, "has_active"

        slot = conn.execute(
            "SELECT master_id, is_available FROM slots WHERE id = ?", (slot_id,)
        ).fetchone()
        if not slot:
            conn.execute("ROLLBACK")
            return False, "bad_slot"
        if int(slot[0]) != int(master_id):
            conn.execute("ROLLBACK")
            return False, "bad_slot"
        if int(slot[1]) != 1:
            conn.execute("ROLLBACK")
            return False, "occupied"

        try:
            conn.execute(
                """
                INSERT INTO bookings
                    (user_id, service_id, master_id, slot_id, created_at, status)
                VALUES (?, ?, ?, ?, ?, 'active')
                """,
                (
                    user_id,
                    service_id,
                    master_id,
                    slot_id,
                    datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                ),
            )
        except sqlite3.IntegrityError:
            conn.execute("ROLLBACK")
            return False, "occupied"

        conn.execute("UPDATE slots SET is_available = 0 WHERE id = ?", (slot_id,))
        conn.execute("COMMIT")
        return True, "ok"
    except sqlite3.Error:
        try:
            conn.execute("ROLLBACK")
        except sqlite3.Error:
            pass
        return False, "error"
    finally:
        conn.close()


def cancel_active_booking(telegram_id: int) -> bool:
    """Отменить активную запись и освободить слот. Возвращает True, если было что отменять."""
    conn = get_connection()
    try:
        conn.execute("BEGIN IMMEDIATE")
        row = conn.execute(
            """
            SELECT b.id, b.slot_id FROM bookings b
            JOIN users u ON u.id = b.user_id
            WHERE u.telegram_id = ? AND b.status = 'active'
            ORDER BY b.id DESC LIMIT 1
            """,
            (telegram_id,),
        ).fetchone()
        if not row:
            conn.execute("ROLLBACK")
            return False
        booking_id, slot_id = int(row[0]), int(row[1])
        conn.execute(
            "UPDATE bookings SET status = 'cancelled' WHERE id = ?", (booking_id,)
        )
        conn.execute("UPDATE slots SET is_available = 1 WHERE id = ?", (slot_id,))
        conn.execute("COMMIT")
        return True
    except sqlite3.Error:
        try:
            conn.execute("ROLLBACK")
        except sqlite3.Error:
            pass
        return False
    finally:
        conn.close()
