"""Inline-клавиатуры BarberFlow. Только inline-кнопки по ТЗ."""
from __future__ import annotations

from telegram import InlineKeyboardButton, InlineKeyboardMarkup

from bot.texts import format_date


def main_menu_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [
            [InlineKeyboardButton("✂️ Записаться", callback_data="book_services")],
            [InlineKeyboardButton("📋 Моя запись", callback_data="my_booking")],
        ]
    )


def services_kb(services: list[tuple[int, str, int]]) -> InlineKeyboardMarkup:
    rows = [
        [
            InlineKeyboardButton(
                f"{name} — {price} ₽", callback_data=f"service_{sid}"
            )
        ]
        for sid, name, price in services
    ]
    rows.append([InlineKeyboardButton("⬅️ В главное меню", callback_data="menu_main")])
    return InlineKeyboardMarkup(rows)


def masters_kb(masters: list[tuple[int, str]]) -> InlineKeyboardMarkup:
    rows = [
        [InlineKeyboardButton(name, callback_data=f"master_{mid}")]
        for mid, name in masters
    ]
    rows.append(
        [InlineKeyboardButton("⬅️ Назад к услугам", callback_data="book_services")]
    )
    rows.append([InlineKeyboardButton("🏠 В главное меню", callback_data="menu_main")])
    return InlineKeyboardMarkup(rows)


def dates_kb(dates: list[tuple[str, int]]) -> InlineKeyboardMarkup:
    rows = []
    for date_iso, free_cnt in dates:
        label = format_date(date_iso)
        if free_cnt > 0:
            label += f" (свободно: {free_cnt})"
            cb = f"date_{date_iso}"
        else:
            label += " — занято"
            cb = "date_busy"
        rows.append([InlineKeyboardButton(label, callback_data=cb)])
    rows.append(
        [InlineKeyboardButton("⬅️ Назад к мастерам", callback_data="back_masters")]
    )
    rows.append([InlineKeyboardButton("🏠 В главное меню", callback_data="menu_main")])
    return InlineKeyboardMarkup(rows)


def slots_kb(slots: list[tuple[int, str, int]]) -> InlineKeyboardMarkup:
    """Свободные — кликабельны, занятые — кнопка с алертом (не выбираются)."""
    rows: list[list[InlineKeyboardButton]] = []
    row: list[InlineKeyboardButton] = []
    for slot_id, time, is_available in slots:
        if is_available == 1:
            row.append(
                InlineKeyboardButton(f"✅ {time}", callback_data=f"slot_{slot_id}")
            )
        else:
            row.append(InlineKeyboardButton(f"❌ {time}", callback_data="slot_busy"))
        if len(row) == 2:
            rows.append(row)
            row = []
    if row:
        rows.append(row)
    rows.append(
        [InlineKeyboardButton("⬅️ Назад к датам", callback_data="back_dates")]
    )
    rows.append([InlineKeyboardButton("🏠 В главное меню", callback_data="menu_main")])
    return InlineKeyboardMarkup(rows)


def confirm_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [
            [InlineKeyboardButton("✅ Подтвердить", callback_data="confirm_yes")],
            [InlineKeyboardButton("⬅️ Выбрать другое время", callback_data="back_slots")],
            [InlineKeyboardButton("🏠 В главное меню", callback_data="menu_main")],
        ]
    )


def after_booking_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [
            [InlineKeyboardButton("📋 Моя запись", callback_data="my_booking")],
            [InlineKeyboardButton("🏠 В главное меню", callback_data="menu_main")],
        ]
    )


def booking_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [
            [InlineKeyboardButton("❌ Отменить запись", callback_data="cancel_booking")],
            [InlineKeyboardButton("🏠 В главное меню", callback_data="menu_main")],
        ]
    )


def ask_cancel_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton("Да, отменить", callback_data="cancel_yes"),
                InlineKeyboardButton("Нет", callback_data="cancel_no"),
            ]
        ]
    )
