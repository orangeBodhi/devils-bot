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
    init_db,
    add_user,
    get_user,
    reset_user,
    add_pushups,
    get_pushups_today,
    next_day,
    fail_day,
    get_fails,
    get_day,
)

# Состояния для ConversationHandler
ASK_NAME, ASK_START_TIME, ASK_END_TIME, ASK_REMINDERS = range(4)

# Эмодзи
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
    emoji_digits = {
        '0': '0️⃣', '1': '1️⃣', '2': '2️⃣', '3': '3️⃣', '4': '4️⃣',
        '5': '5️⃣', '6': '6️⃣', '7': '7️⃣', '8': '8️⃣', '9': '9️⃣'
    }
    return ''.join(emoji_digits.get(d, d) for d in str(num))

def hearts(fails):
    return (HEART_RED * (3 - fails)) + (HEART_BLACK * fails)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    user = update.effective_user
    user_db = get_user(user.id)
    if user_db:
        await update.message.reply_text(
            f"Ты уже зарегистрирован! Напиши /reset, чтобы начать заново.", reply_markup=ReplyKeyboardRemove()
        )
        return ConversationHandler.END
    await update.message.reply_text(
        "Как к тебе обращаться? 📝"
    )
    return ASK_NAME

async def ask_start_time(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    context.user_data["name"] = update.message.text
    await update.message.reply_text(
        "Укажи время в формате ЧАСЫ:МИНУТЫ (например, 07:00), когда бот начинает работать (начало дня) и ты сможешь записывать свои отжимания🕒"
    )
    return ASK_END_TIME

async def ask_end_time(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    context.user_data["start_time"] = update.message.text
    await update.message.reply_text(
        "Укажи время в формате ЧАСЫ:МИНУТЫ (например, 22:00), когда бот завершает работу (конец дня) 🕒 и ты больше не сможешь добавлять отжимания в этот день"
    )
    return ASK_REMINDERS

async def ask_reminders(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    context.user_data["end_time"] = update.message.text
    await update.message.reply_text(
        "Сколько раз в день тебе напоминать про отжимания? Минимум 2, максимум 10 🔔"
    )
    return ASK_REMINDERS

async def save_reminders(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    try:
        reminders = int(update.message.text)
    except ValueError:
        await update.message.reply_text("Пожалуйста, введи число (от 2 до 10)")
        return ASK_REMINDERS
    if reminders < 2 or reminders > 10:
        await update.message.reply_text("Число должно быть от 2 до 10")
        return ASK_REMINDERS
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
    # Всегда делаем сброс, даже если пользователь не найден
    reset_user(user.id)
    await update.message.reply_text("Все данные сброшены! Можешь пройти регистрацию заново через /start.")

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

async def add10(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await add_pushups_generic(update, context, 10)

async def add15(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await add_pushups_generic(update, context, 15)

async def add20(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await add_pushups_generic(update, context, 20)

async def add25(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await add_pushups_generic(update, context, 25)

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

async def status(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    u = get_user(user.id)
    if not u:
        await update.message.reply_text("Сначала зарегистрируйся через /start")
        return
    day = u["day"]
    fails = u["fails"]
    pushups = u["pushups_today"]
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
                f"К сожалению ты зафейлил третий раз! {SKULL}\nДля тебя Devil's 100 challenge закончен… в этот раз!\nДля перезапуска напиши /reset",
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

def main():
    application = Application.builder().token(TOKEN).build()

    conv_handler = ConversationHandler(
        entry_points=[CommandHandler("start", start)],
        states={
            ASK_NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, ask_start_time)],
            ASK_START_TIME: [MessageHandler(filters.TEXT & ~filters.COMMAND, ask_end_time)],
            ASK_END_TIME: [MessageHandler(filters.TEXT & ~filters.COMMAND, ask_reminders)],
            ASK_REMINDERS: [MessageHandler(filters.TEXT & ~filters.COMMAND, save_reminders)],
        },
        fallbacks=[CommandHandler("start", start), CommandHandler("reset", reset)],
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
