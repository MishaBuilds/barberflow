"""Конфигурация BarberFlow. Токен и путь к БД берутся из .env."""
import os
from pathlib import Path

from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent

load_dotenv(BASE_DIR / ".env")

BOT_TOKEN: str = os.getenv("BOT_TOKEN", "").strip()

_db_path_raw: str = (os.getenv("DB_PATH", "") or "").strip() or "barberflow.db"
_db_path = Path(_db_path_raw)
if not _db_path.is_absolute():
    _db_path = BASE_DIR / _db_path
DB_PATH: str = str(_db_path)
