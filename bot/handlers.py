"""Обработчики BarberFlow: /start и навигация по inline-кнопкам.

Принцип: не отправляем новое сообщение на каждый шаг, а редактируем
текущее через query.edit_message_text. Новые сообщения — только /start
и ответы на уже завершённые действия там, где редактировать нечего.

Сценарий: услуги -> мастер -> дата -> время -> подтверждение -> БД -> успех.
"""
from __future__ import annotations

from telegram import Update
from telegram.error import BadRequest
from telegram.ext import ContextTypes

from bot import keyboards as kb
from bot import states
from bot import texts
from database import db


async def _safe_edit(query, text: str, reply_markup=None) -> None:
    """Редактировать сообщение, игнорируя 'Message is not modified'."""
    try:
        await query.edit_message_text(
            text, reply_markup=reply_markup, parse_mode="HTML"
        )
    except BadRequest as e:
        if "not modified" not in str(e).lower():
            raise


def _user_name(update: Update) -> str:
    user = update.effective_user
    if not user:
        return ""
    return user.full_name or user.first_name or ""


# --- /start и главное меню ---

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user = update.effective_user
    assert user is not None
    db.get_or_create_user(user.id, _user_name(update))
    states.clear_state(user.id)
    if update.message:
        await update.message.reply_html(texts.MAIN_MENU, reply_markup=kb.main_menu_kb())


async def show_main(query, telegram_id: int) -> None:
    states.clear_state(telegram_id)
    await _safe_edit(query, texts.MAIN_MENU, kb.main_menu_kb())


# --- шаги сценария ---

async def show_services(query) -> None:
    services = db.get_services()
    await _safe_edit(query, texts.CHOOSE_SERVICE, kb.services_kb(services))


async def show_masters(query) -> None:
    masters = db.get_masters()
    await _safe_edit(query, texts.CHOOSE_MASTER, kb.masters_kb(masters))


async def show_dates(query, master_id: int) -> None:
    dates = db.get_dates_with_counts(master_id)
    if not dates:
        await _safe_edit(
            query,
            "На этого мастера пока нет слотов. Выберите другого.",
            kb.masters_kb(db.get_masters()),
        )
        return
    await _safe_edit(query, texts.CHOOSE_DATE, kb.dates_kb(dates))


async def show_slots(query, master_id: int, date_iso: str) -> None:
    slots = db.get_slots_for_date(master_id, date_iso)
    if not slots:
        await _safe_edit(query, texts.CHOOSE_DATE, kb.dates_kb([]))
        return
    await _safe_edit(query, texts.CHOOSE_TIME, kb.slots_kb(slots))


async def show_confirm(query, telegram_id: int) -> None:
    st = states.get_state(telegram_id)
    service = db.get_service(int(st["service_id"]))
    master = db.get_master(int(st["master_id"]))
    slot = db.get_slot(int(st["slot_id"]))
    if not service or not master or not slot:
        await show_main(query, telegram_id)
        return
    text = texts.CONFIRM_TEMPLATE.format(
        service=service[1],
        price=service[2],
        master=master[1],
        date=texts.format_date(slot[2]),
        time=slot[3],
    )
    await _safe_edit(query, text, kb.confirm_kb())


async def show_my_booking(query) -> None:
    user = query.from_user
    booking = db.get_active_booking(user.id)
    if not booking:
        await _safe_edit(
            query,
            texts.NO_BOOKING,
            kb.main_menu_kb(),
        )
        return
    text = texts.BOOKING_TEMPLATE.format(
        service=booking["service_name"],
        price=booking["price"],
        master=booking["master_name"],
        date=texts.format_date(booking["date"]),
        time=booking["time"],
    )
    await _safe_edit(query, text, kb.booking_kb())


# --- роутер callback-кнопок ---

async def on_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    assert query is not None
    await query.answer()
    telegram_id = query.from_user.id
    db.get_or_create_user(telegram_id, query.from_user.full_name or "")
    data = query.data or ""
    st = states.get_state(telegram_id)

    # Главное меню
    if data == "menu_main":
        await show_main(query, telegram_id)
        return

    # Шаг 1: услуги
    if data == "book_services":
        states.reset_booking_progress(telegram_id)
        # Блокируем новую запись, если уже есть активная.
        if db.get_active_booking(telegram_id):
            await _safe_edit(query, texts.HAS_ACTIVE, kb.main_menu_kb())
            return
        await show_services(query)
        return

    # Шаг 2: мастер
    if data.startswith("service_"):
        try:
            service_id = int(data.split("_", 1)[1])
        except ValueError:
            await show_services(query)
            return
        if not db.get_service(service_id):
            await show_services(query)
            return
        states.set_value(telegram_id, "service_id", service_id)
        await show_masters(query)
        return

    # Назад к мастерам (из дат): service_id уже в состоянии
    if data == "back_masters":
        await show_masters(query)
        return

    # Шаг 3: дата
    if data.startswith("master_"):
        if "service_id" not in st:
            await show_services(query)
            return
        try:
            master_id = int(data.split("_", 1)[1])
        except ValueError:
            await show_masters(query)
            return
        if not db.get_master(master_id):
            await show_masters(query)
            return
        states.set_value(telegram_id, "master_id", master_id)
        await show_dates(query, master_id)
        return

    if data == "date_busy":
        await query.answer("Эта дата полностью занята. Выберите другую.", show_alert=True)
        return

    # Назад к датам (из времени)
    if data == "back_dates":
        if "master_id" not in st:
            await show_masters(query)
            return
        await show_dates(query, int(st["master_id"]))
        return

    # Шаг 4: время
    if data.startswith("date_"):
        if "master_id" not in st:
            await show_masters(query)
            return
        date_iso = data[len("date_"):]
        states.set_value(telegram_id, "date", date_iso)
        await show_slots(query, int(st["master_id"]), date_iso)
        return

    if data == "slot_busy":
        await query.answer(texts.SLOT_BUSY_ALERT, show_alert=True)
        return

    # Назад к времени (из подтверждения)
    if data == "back_slots":
        if "master_id" not in st or "date" not in st:
            await show_main(query, telegram_id)
            return
        await show_slots(query, int(st["master_id"]), str(st["date"]))
        return

    # Шаг 5: подтверждение
    if data.startswith("slot_"):
        if "master_id" not in st or "date" not in st:
            await show_main(query, telegram_id)
            return
        try:
            slot_id = int(data.split("_", 1)[1])
        except ValueError:
            await show_slots(query, int(st["master_id"]), str(st["date"]))
            return
        slot = db.get_slot(slot_id)
        # Сверяем слот с выбранными мастером/датой и доступностью.
        if (
            not slot
            or slot[1] != int(st["master_id"])
            or slot[2] != str(st["date"])
        ):
            await show_slots(query, int(st["master_id"]), str(st["date"]))
            return
        if slot[4] != 1:
            await query.answer(texts.SLOT_BUSY_ALERT, show_alert=True)
            await show_slots(query, int(st["master_id"]), str(st["date"]))
            return
        states.set_value(telegram_id, "slot_id", slot_id)
        await show_confirm(query, telegram_id)
        return

    if data == "confirm_yes":
        if "service_id" not in st or "master_id" not in st or "slot_id" not in st:
            await show_main(query, telegram_id)
            return
        ok, reason = db.create_booking(
            telegram_id,
            int(st["service_id"]),
            int(st["master_id"]),
            int(st["slot_id"]),
        )
        if ok:
            service = db.get_service(int(st["service_id"]))
            master = db.get_master(int(st["master_id"]))
            slot = db.get_slot(int(st["slot_id"]))
            assert service and master and slot
            details = texts.BOOKING_TEMPLATE.format(
                service=service[1],
                price=service[2],
                master=master[1],
                date=texts.format_date(slot[2]),
                time=slot[3],
            )
            states.clear_state(telegram_id)
            await _safe_edit(
                query, texts.SUCCESS.format(details=details), kb.after_booking_kb()
            )
            return
        if reason == "has_active":
            await _safe_edit(query, texts.HAS_ACTIVE, kb.main_menu_kb())
            return
        # Слот заняли между выбором и подтверждением: предлагаем выбрать заново.
        await _safe_edit(query, texts.OCCUPIED, kb.main_menu_kb())
        states.clear_state(telegram_id)
        return

    # Моя запись
    if data == "my_booking":
        await show_my_booking(query)
        return

    if data == "cancel_booking":
        booking = db.get_active_booking(telegram_id)
        if not booking:
            await _safe_edit(query, texts.NO_BOOKING, kb.main_menu_kb())
            return
        await _safe_edit(query, texts.ASK_CANCEL, kb.ask_cancel_kb())
        return

    if data == "cancel_yes":
        db.cancel_active_booking(telegram_id)
        await _safe_edit(query, texts.CANCELLED, kb.main_menu_kb())
        return

    if data == "cancel_no":
        await show_my_booking(query)
        return

    # Неизвестный callback — мягко вернуть в меню.
    await show_main(query, telegram_id)
