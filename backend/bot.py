import os
import logging
import asyncio
from dotenv import load_dotenv
from aiogram import Bot, Dispatcher, F, types, Router
from aiogram.filters import CommandStart, Command, CommandObject
from aiogram.types import WebAppInfo, InlineKeyboardMarkup, InlineKeyboardButton, PreCheckoutQuery, Message, CallbackQuery, LabeledPrice
from backend.db import SessionLocal
import backend.models as models
import json
import redis.asyncio as aioredis
from backend.db import SessionLocal, Order

logging.basicConfig(level=logging.INFO)


load_dotenv()
BOT_TOKEN = os.getenv("BOT_TOKEN")
WEB_APP_URL = os.getenv("WEB_APP_URL", "https://t.me/mpfoodorderbot/app")
redis_client = aioredis.from_url("redis://localhost:6379", decode_responses=True)

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()
from backend.adminka import admin_router
dp.include_router(admin_router)
router = Router()


@dp.message(CommandStart())
async def start_handler(message: Message, command: CommandObject):
    args = command.args

    from backend.db import SessionLocal, Order

    if args and args.startswith("order_"):
        try:
            order_id = int(args.split("_")[1])

            from backend.app import SessionLocal, Order
            db = SessionLocal()

            order = db.query(models.Order).filter(models.Order.id == order_id).first()

            if not order:
                await message.answer("❌ Заказ не найден в базе данных.")
                db.close()
                return

            if order.status == "paid":
                await message.answer("❌ Этот заказ уже успешно оплачен! Повторный вызов счета невозможен.")
                db.close()
                return

            total_price = int(order.price)

            await message.answer(f"⏳ Заказ №{order_id} ожидает оплаты. Ссылка на оплату сформирована.")

            await message.bot.send_invoice(
                chat_id=message.chat.id,
                title=f"Оплата заказа #{order_id}",
                description="Оплата выбранных товаров в магазине MPFood",
                payload=str(order_id),
                provider_token="",
                currency="XTR",
                prices=[
                    LabeledPrice(label="Сумма заказа", amount=total_price)
                ]
            )

            db.close()

        except Exception as e:
            print(f"Критическая ошибка в start_handler: {e}")
            await message.answer("❌ Произошла ошибка при обработке ссылки.")
    else:
        await message.answer("👋 Привет! Добро пожаловать в MPFood. Перейдите в наше приложение, чтобы сделать заказ.")

@dp.message(Command("stats"))
async def admin_stats(message: Message):
    db = SessionLocal()
    user = db.query(models.User).filter(models.User.tg_id == str(message.from_id)).first()



    if not user or not user.is_admin:
        await message.answer("У вас нет прав для просмотра статистики.")
        db.close()
        return

    users_count = db.query(models.User).count()
    orders_count = db.query(models.Order).filter(models.Order.status == "paid").count()
    revenue = db.query(models.Order.total_amount).filter(models.Order.status == "paid").all()
    total_revenue = sum([r[0] for r in revenue]) if revenue else 0

    await message.answer(
        "📊 <b>Статистика магазина MPFood:</b>\n\n"
        f"👥 Всего клиентов: {users_count}\n"
        f"📦 Успешных заказов: {orders_count}\n"
        f"⭐️ Заработано Звезд: {total_revenue} XTR",
        parse_mode="HTML"
    )
    db.close()


@dp.pre_checkout_query()
async def pre_checkout_handler(pre_checkout_query: PreCheckoutQuery):
    order_id = int(pre_checkout_query.invoice_payload)

    from backend.app import SessionLocal, Order
    db = SessionLocal()
    order = db.query(models.Order).filter(models.Order.id == order_id).first()
    db.close()

    if order and order.status == "paid":
        await pre_checkout_query.answer(ok=False, error_message="Этот заказ уже был оплачен ранее!")
    else:
        await pre_checkout_query.answer(ok=True)


@dp.message(F.successful_payment)
async def successful_payment_handler(message: Message):
    payment_info = message.successful_payment
    order_id = int(payment_info.invoice_payload)
    total_amount = payment_info.total_amount / 100

    from backend.app import SessionLocal, Order

    db = SessionLocal()
    try:
        order = db.query(models.Order).filter(models.Order.id == order_id).first()

        if order:
            order.status = "paid"
            db.commit()

            await message.answer(
                f"🎉 Спасибо! Ваш заказ №{order_id} успешно оплачен и передан на кухню."
            )

            ADMIN_ID = 6263303676

            admin_text = (
                f"🔔 **Новый оплаченный заказ!**\n\n"
                f"📦 **Заказ №:** {order_id}\n"
                f"💰 **Сумма:** {total_amount} {payment_info.currency}\n"
                f"👤 **Покупатель:** ID {message.from_user.id} (@{message.from_user.username or 'нет юзернейма'})"
            )

            await message.bot.send_message(chat_id=ADMIN_ID, text=admin_text, parse_mode="Markdown")
        else:
            print(f"Критическая ошибка: Деньги списаны, но заказ №{order_id} отсутствует в БД!")

    except Exception as e:
        db.rollback()
        print(f"Ошибка при сохранении платежа в БД: {e}")
    finally:
        db.close()

    ADMIN_ID = 6263303676

    stars_amount = message.successful_payment.total_amount
    await message.bot.send_message(
        chat_id=ADMIN_ID,
        text=(
            f"🔔 <b>Новый оплаченный заказ #{order_id}!</b>\n\n"
            f"👤 Покупатель: @{message.from_user.username or 'без юзернейма'}\n"
            f"💰 Сумма: <b>{stars_amount} Stars</b>\n"
            f"✅ Статус в БД обновлен на: <b>paid</b>"
        ),
        parse_mode="HTML"
    )

    await message.answer(
        f"🎉 <b>Спасибо за оплату заказа #{order_id}!</b>\n"
        f"Ваш заказ успешно принят и отправлен на кухню. Ожидайте уведомления.",
        parse_mode="HTML"
    )


@dp.callback_query(F.data.startswith("pay:"))
async def process_pay_button(callback: CallbackQuery):

    _, order_id, total_price = callback.data.split(":")

    await callback.message.answer_invoice(
        title=f"Оплата заказа #{order_id}",
        description="Оплата выбранных товаров в магазине MPFood",
        payload=f"order_pay_{order_id}",
        provider_token="",
        currency="XTR",
        prices=[
            LabeledPrice(label="Сумма заказа", amount=int(total_price))
        ]
    )
    await callback.answer()


@dp.callback_query(F.data.startswith("cancel:"))
async def process_cancel_button(callback: CallbackQuery):
    _, order_id = callback.data.split(":")

    await callback.message.edit_text(
        text=f"❌ <b>Процесс оплаты заказа #{order_id} отменен.</b>\n\nВы можете открыть Mini App и собрать корзину заново.",
        parse_mode="HTML"
    )
    await callback.answer("Оплата отменена")


async def main():
    print("запущен")
    await bot.delete_webhook(drop_pending_updates=True)
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
