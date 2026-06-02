import os
from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.utils.keyboard import InlineKeyboardBuilder
from sqlalchemy.orm import Session
from sqlalchemy import func
from backend.db import get_db
import backend.models as models

admin_router = Router()

ADMIN_IDS_RAW = os.getenv("ADMIN", "")
ADMIN_IDS = [int(x.strip()) for x in ADMIN_IDS_RAW.split(",") if x.strip().isdigit()]


def get_admin_kb():
    builder = InlineKeyboardBuilder()
    builder.button(text="📊 Статистика", callback_data="admin_stats")
    builder.button(text="📦 Последние 5 заказов", callback_data="admin_orders")
    builder.button(text="❌ Закрыть меню", callback_data="admin_close")
    builder.adjust(1)
    return builder.as_markup()


def get_back_kb():
    builder = InlineKeyboardBuilder()
    builder.button(text="⬅️ Назад в меню", callback_data="admin_main")
    return builder.as_markup()


@admin_router.message(F.text == "/admin")
async def admin_menu(message: Message):
    if message.from_user.id not in ADMIN_IDS:
        await message.answer("⛔ **Доступ деактивирован.** У вас нет прав администратора.")
        return

    await message.answer("⚙️ **Панель администратора MPFood:**", reply_markup=get_admin_kb(), parse_mode="Markdown")


@admin_router.callback_query(F.data == "admin_main")
async def admin_main_callback(call: CallbackQuery):
    if call.from_user.id not in ADMIN_IDS:
        await call.answer("🔒 Доступ ограничен!", show_alert=True)
        return
    await call.message.edit_text("⚙️ **Панель администратора MPFood:**", reply_markup=get_admin_kb(),
                                 parse_mode="Markdown")


@admin_router.callback_query(F.data == "admin_stats")
async def admin_stats_callback(call: CallbackQuery):
    if call.from_user.id not in ADMIN_IDS:
        await call.answer("🔒 Доступ ограничен!", show_alert=True)
        return

    db: Session = next(get_db())
    try:
        total_orders = db.query(Order).count()
        total_sum = db.query(func.sum(Order.total_price)).scalar() or 0

        text = (
            "📊 **Статистика магазина:**\n\n"
            f" Всего заказов в базе: `{total_orders}`\n"
            f" Выручка общая: ⭐ `{int(total_sum)} Stars`"
        )
        await call.message.edit_text(text, reply_markup=get_back_kb(), parse_mode="Markdown")
    except Exception as e:
        await call.message.edit_text(f"❌ Ошибка БД: {e}", reply_markup=get_back_kb())
    finally:
        db.close()


@admin_router.callback_query(F.data == "admin_orders")
async def admin_orders_callback(call: CallbackQuery):
    if call.from_user.id not in ADMIN_IDS:
        await call.answer("🔒 Доступ ограничен!", show_alert=True)
        return

    db: Session = next(get_db())
    try:
        orders = db.query(Order).order_by(Order.id.desc()).limit(5).all()
        if not orders:
            await call.message.edit_text("📦 Заказов в базе пока нет.", reply_markup=get_back_kb())
            return

        text = "📦 **Последние 5 заказов в системе:**\n\n"
        for o in orders:
            text += f"🔹 **Заказ №{o.id}**\n"
            text += f"   ├ ID пользователя: `{o.user_id}`\n"
            text += f"   └ Сумма: ⭐ `{getattr(o, 'total_price', '0')} Stars`\n\n"

        await call.message.edit_text(text, reply_markup=get_back_kb(), parse_mode="Markdown")
    except Exception as e:
        await call.message.edit_text(f"❌ Ошибка БД: {e}", reply_markup=get_back_kb())
    finally:
        db.close()


@admin_router.callback_query(F.data == "admin_close")
async def admin_close_callback(call: CallbackQuery):
    if call.from_user.id not in ADMIN_IDS:
        await call.answer("🔒 Доступ ограничен!", show_alert=True)
        return
    await call.message.delete()