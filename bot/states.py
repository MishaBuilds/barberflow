"""Состояние выбора пользователя (in-memory, для MVP).

Хранит текущий прогресс сценария записи для каждого telegram_id:
service_id -> master_id -> date -> slot_id.

Этого достаточно для портфолийного MVP: состояние простое, прозрачное,
не требует Redis. При перезапуске бота незавершённые выборы сбрасываются,
а созданные записи лежат в SQLite и никуда не пропадают.
"""
from __future__ import annotations

_states: dict[int, dict] = {}


def get_state(telegram_id: int) -> dict:
    return _states.setdefault(int(telegram_id), {})


def set_value(telegram_id: int, key: str, value) -> None:
    get_state(telegram_id)[key] = value


def clear_state(telegram_id: int) -> None:
    _states.pop(int(telegram_id), None)


def reset_booking_progress(telegram_id: int) -> None:
    """Начать сценарий записи заново, сохранив сам факт состояния."""
    _states[int(telegram_id)] = {}
