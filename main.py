import logging
import os
from dotenv import load_dotenv
from telegram import (
    Update,
    ReplyKeyboardMarkup,
    KeyboardButton,
    ReplyKeyboardRemove,
)
from telegram.ext import (
    Application,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    filters,
    ConversationHandler,
)
from db import (
    init_db, add_user, get_user, reset_user, add_pushups,
    get_pushups_today, next_day, fail_day, get_fails, get_day
)

# States
CHOOSING_NAME, CHOOSING_START_TIME, CHOOSING_END_TIME, CHOOSING_REMINDERS = range(4)

DEVIL = "😈"
CLOVER = "🍀"
HEART_RED = "❤️"
HEART_BLACK = "🖤"
STRONG = "💪"
REMIND = "🔔"
NOTE = "📝"
CLOCK = "🕒"
TROPHY = "🏆"
CHILL = "🧘"
SKULL = "💀"
ROAD = "🛣️"

load_dotenv()
TOKEN = os.getenv("TELEGRAM_TOKEN")

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

init_db()

def progress_bar(val, total, length, char="▇", empty="—"):
    filled = int(round(length * val / float(total)))
    return char * filled + empty * (length - filled)

def emoji_number(num):
    # Только для 1–9, иначе просто цифры
    emoji_digits = {
        '0': '0️⃣', '1': '1️⃣', '2': '2️⃣', '3': '3️⃣', '4': '4️⃣',
        '5': '5️⃣', '6': '6️⃣', '7': '7️⃣', '8': '8️⃣', '9': '9️⃣'
    }
    return ''.join(emoji_digits.get(d, d) for d in str(num))

def hearts(fails):
    return (HEART_RED * (3 - fails)) + (HEART_BLACK * fails)

async def status(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    u = get_user(user.id)
    if not u:
        await update.message.reply_text("Сначала зарегистрируйся через /start")
        return
    day = u["day"]
    fails = u["fails"]
    pushups = u["pushups_today"]
    # Бары
    bar_days = progress_bar(day, 90, 3)
    bar_pushups = progress_bar(pushups, 100, 5)
    msg = (
        f"DAY: {emoji_number(day)}/90 {bar_days}\n"
        f"PROGRESS: {emoji_number(pushups)}/100 {bar_pushups}\n"
        f"HEALTH: {hearts(fails)}\n"
    )
    keyboard = [
        [KeyboardButton("/add10"), KeyboardButton("/add15")],
        [KeyboardButton("/add20"), KeyboardButton("/add25")],
        [KeyboardButton("/add")],
    ]
    reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
    await update.message.reply_text(msg, reply_markup=reply_markup)

async def check_end_of_day(user_id, update):
    u = get_user(user_id)
    if u and u["pushups_today"] < 100:
        fails = fail_day(user_id)
        if fails < 3:
            await update.message.reply_text(
                f"Па-па-па… Сегодня ты не осилил сотку. К сожалению это минус жизнь. У тебя осталось всего: {hearts(fails)}"
            )
        else:
            await update.message.reply_text(
                f"К сожалению ты зафейлил третий раз! {SKULL}\nДля тебя Devil's 100 challenge закончен… в этот раз!\nПоэтому, написав /reset ты можешь начать всё сначала! {ROAD}",
                reply_markup=ReplyKeyboardRemove()
            )

async def addday(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    u = get_user(user.id)
    if not u:
        await update.message.reply_text("Сначала зарегистрируйся через /start")
        return
    if u["pushups_today"] < 100:
        await check_end_of_day(user.id, update)
    else:
        next_day(user.id)
        await update.message.reply_text(
            f"Поздравляю, ты молодец! Сегодняшняя сотка сделана, увидимся завтра! {STRONG}"
        )
    await status(update, context)

# Остальной код (start, reset, add10/15/20/25, add и т.д.) остаётся как был выше

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    # ... (Оставьте код как был выше)
    user = update.effective_user
    user_db = get_user(user.id)
    if user_db:
        await update.message.reply_text(
            f"Ты уже зарегистрирован! Напиши /reset, чтобы начать заново.", reply_markup=ReplyKeyboardRemove()
        )
        return ConversationHandler.END
    keyboard = [[KeyboardButton("🚀 Начать челлендж")]]
    reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
    await update.message.reply_text(
        f"Добро пожаловать в Devil's 100!\nНажмите кнопку ниже, чтобы начать регистрацию.",
        reply_markup=reply_markup,
    )
    return CHOOSING_NAME

# ... (Оставьте остальные функции регистрации и добавления отжиманий как выше)

def main():
    application = Application.builder().token(TOKEN).build()

    conv_handler = ConversationHandler(
        entry_points=[
            CommandHandler("start", start),
            MessageHandler(filters.Regex("🚀 Начать челлендж"), choose_name),
        ],
        states={
            CHOOSING_NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, save_name)],
            CHOOSING_START_TIME: [MessageHandler(filters.TEXT & ~filters.COMMAND, save_start_time)],
            CHOOSING_END_TIME: [MessageHandler(filters.TEXT & ~filters.COMMAND, save_end_time)],
            CHOOSING_REMINDERS: [MessageHandler(filters.TEXT & ~filters.COMMAND, save_reminders)],
        },
        fallbacks=[CommandHandler("start", start)],
    )

    application.add_handler(conv_handler)
    application.add_handler(CommandHandler("reset", reset))
    application.add_handler(CommandHandler("status", status))
    application.add_handler(CommandHandler("addday", addday))
    application.add_handler(CommandHandler("add10", add10))
    application.add_handler(CommandHandler("add15", add15))
    application.add_handler(CommandHandler("add20", add20))
    application.add_handler(CommandHandler("add25", add25))
    application.add_handler(CommandHandler("add", add_custom))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_custom_pushups))

    logger.info("Bot started!")
    application.run_polling()

if __name__ == "__main__":
    main()
