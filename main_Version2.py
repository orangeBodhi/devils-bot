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
from db import init_db, add_user, get_user, reset_user, add_pushups, get_pushups_today, next_day

# States
CHOOSING_NAME, CHOOSING_START_TIME, CHOOSING_END_TIME, CHOOSING_REMINDERS = range(4)

# Emojis
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

load_dotenv()
TOKEN = os.getenv("TELEGRAM_TOKEN")

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

init_db()

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
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

async def choose_name(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    await update.message.reply_text(f"Как к тебе обращаться? {NOTE}")
    return CHOOSING_START_TIME

async def save_name(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    context.user_data["name"] = update.message.text
    await update.message.reply_text(
        f"Укажи время в формате ЧАСЫ:МИНУТЫ (например, 07:00), когда бот начинает работать {CLOCK}"
    )
    return CHOOSING_END_TIME

async def save_start_time(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    context.user_data["start_time"] = update.message.text
    await update.message.reply_text(
        f"Укажи время в формате ЧАСЫ:МИНУТЫ (например, 22:00), когда бот завершает работу {CLOCK}"
    )
    return CHOOSING_REMINDERS

async def save_end_time(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    context.user_data["end_time"] = update.message.text
    await update.message.reply_text(
        f"Сколько раз в день тебе напоминать про отжимания? Минимум 2, максимум 10 {REMIND}"
    )
    return CHOOSING_REMINDERS

async def save_reminders(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    try:
        reminders = int(update.message.text)
    except ValueError:
        await update.message.reply_text("Пожалуйста, введи число (от 2 до 10)")
        return CHOOSING_REMINDERS
    if reminders < 2 or reminders > 10:
        await update.message.reply_text("Число должно быть от 2 до 10")
        return CHOOSING_REMINDERS
    context.user_data["reminders"] = reminders
    user = update.effective_user
    add_user(
        user.id,
        context.user_data["name"],
        context.user_data["start_time"],
        context.user_data["end_time"],
        context.user_data["reminders"]
    )
    await update.message.reply_text(
        f"{DEVIL} Приветствую в Devil's 100 challenge! Сегодня первый день челленджа, а значит ты должен сделать первые 100 отжиманий! Удачи! {CLOVER}",
        reply_markup=ReplyKeyboardRemove()
    )
    return ConversationHandler.END

async def reset(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    if get_user(user.id):
        reset_user(user.id)
        await update.message.reply_text("Все данные сброшены! Можешь пройти регистрацию заново через /start.")
    else:
        await update.message.reply_text("Ты ещё не зарегистрирован!")

async def add10(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await add_pushups_generic(update, context, 10)

async def add15(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await add_pushups_generic(update, context, 15)

async def add20(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await add_pushups_generic(update, context, 20)

async def add25(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await add_pushups_generic(update, context, 25)

async def add_pushups_generic(update, context, count):
    user = update.effective_user
    if not get_user(user.id):
        await update.message.reply_text("Сначала зарегистрируйся через /start")
        return
    cur = get_pushups_today(user.id)
    if cur >= 100:
        await update.message.reply_text(f"Ты уже сделал сегодняшнюю сотку, отдохни! {CHILL}")
        return
    ok = add_pushups(user.id, count)
    if not ok:
        await update.message.reply_text("Нельзя добавить больше 100 отжиманий за день!")
        return
    new_count = get_pushups_today(user.id)
    await update.message.reply_text(f"Отлично! {count} отжиманий добавлено к сегодняшнему прогрессу! {TROPHY}\nТекущий прогресс: {new_count}/100")
    if new_count == 100:
        await update.message.reply_text(f"Юху! сегодняшняя сотка сделана! {STRONG} 💯")

async def add_custom(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Введите количество сделанных отжиманий (например, 13):")
    context.user_data["awaiting_custom"] = True

async def handle_custom_pushups(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if context.user_data.get("awaiting_custom"):
        try:
            count = int(update.message.text)
        except ValueError:
            await update.message.reply_text("Пожалуйста, введите число.")
            return
        await add_pushups_generic(update, context, count)
        context.user_data["awaiting_custom"] = False

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