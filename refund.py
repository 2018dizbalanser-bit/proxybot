import asyncio
import logging
from datetime import datetime, timedelta
from aiogram import Bot, Dispatcher, F, types
from aiogram.filters import Command
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.exceptions import TelegramAPIError

# Ваш токен
BOT_TOKEN = "7421702384:AAHgUpDlvEkp7JBhbrYc6qVIm4huWZvAD-E"

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()


@dp.message(Command("start"))
async def cmd_start(message: types.Message):
    await message.answer(
        "⭐️ Бот для управления возвратами Telegram Stars.\n"
        "Используйте /refund для просмотра ваших платежей."
    )


@dp.message(Command("refund"))
async def cmd_refund(message: types.Message):
    sent_msg = await message.answer("🔍 Поиск ваших транзакций в блокчейне Telegram...")

    try:
        # Получаем транзакции (последние 100)
        # В актуальном API 2026 года возвращается объект StarTransactions
        history = await bot.get_star_transactions(limit=100)
        transactions = history.transactions
    except Exception as e:
        await sent_msg.edit_text(f"❌ Ошибка API: {e}")
        return

    user_id = message.from_user.id
    keyboard_buttons = []

    # Текущее время для проверки срока (21 день)
    now = datetime.now()

    for tx in transactions:
        # 1. Проверяем, что это ВХОДЯЩАЯ транзакция от пользователя (source не None)
        if not tx.source or tx.source.type != "user":
            continue

        # 2. Проверяем ID пользователя (он внутри объекта user)
        if tx.source.user.id != user_id:
            continue

        # 3. Проверка на "возвратность" (Telegram позволяет refund в течение ~21 дня)
        # tx.date — это int (timestamp)
        tx_date = datetime.fromtimestamp(tx.date)
        is_expired = (now - tx_date).days > 21

        status_icon = "⚠️" if is_expired else "✅"
        date_str = tx_date.strftime('%d.%m.%Y %H:%M')

        # В callback_data передаем ID транзакции
        btn_text = f"{status_icon} {tx.amount} ⭐️ | {date_str}"

        # Если срок истек, кнопка будет просто уведомлением (или можно не добавлять)
        cb_data = f"refund_exec:{tx.id}" if not is_expired else "refund_expired"

        keyboard_buttons.append([InlineKeyboardButton(text=btn_text, callback_data=cb_data)])

    if not keyboard_buttons:
        await sent_msg.edit_text(
            "Ничего не найдено. Возможные причины:\n"
            "1. Вы еще не платили этому боту звездами.\n"
            "2. Платеж был совершен более 21 дня назад.\n"
            "3. Вы платили через другой аккаунт."
        )
        return

    await sent_msg.edit_text(
        "Выберите транзакцию для возврата.\n"
        "✅ — доступно для возврата\n"
        "⚠️ — срок (21 день) истек",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=keyboard_buttons)
    )


@dp.callback_query(F.data == "refund_expired")
async def process_expired(callback: types.CallbackQuery):
    await callback.answer("Срок возврата этой транзакции (21 день) истек.", show_alert=True)


@dp.callback_query(F.data.startswith("refund_exec:"))
async def process_refund(callback: types.CallbackQuery):
    # Извлекаем transaction_id
    tx_id = callback.data.split(":")[1]

    try:
        # Выполняем возврат
        # user_id обязателен для верификации
        await bot.refund_star_payment(
            user_id=callback.from_user.id,
            telegram_payment_charge_id=tx_id
        )

        await callback.message.edit_text(
            f"✅ Успешно! Транзакция `{tx_id}` отозвана. "
            "Звезды вернутся на баланс пользователя в течение нескольких минут."
        )
    except TelegramAPIError as e:
        # Если Telegram вернул ошибку (например, уже был сделан возврат)
        error_msg = str(e)
        if "CHARGE_ALREADY_REFUNDED" in error_msg:
            await callback.answer("Эти звезды уже были возвращены!", show_alert=True)
        else:
            await callback.answer(f"Ошибка: {error_msg}", show_alert=True)

    await callback.answer()


async def main():
    await bot.delete_webhook(drop_pending_updates=True)
    logging.basicConfig(level=logging.INFO)
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())