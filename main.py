import logging
import os
import re
import asyncio
from datetime import datetime, timedelta, time as dt_time
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
    get_all_user_ids,  # не забудь обязательно про этот импорт!
)

ASK_NAME, ASK_START_TIME, ASK_END_TIME, ASK_REMINDERS = range(4)

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
UP = "📈"

load_dotenv()
TOKEN = os.getenv("TELEGRAM_TOKEN")

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

init_db()

# Для хранения задач напоминаний по user_id
reminder_tasks = {}

def get_main_keyboard():
    keyboard = [
        [KeyboardButton("🎯 +10 отжиманий"), KeyboardButton("🎯 +15 отжиманий")],
        [KeyboardButton("🎯 +20 отжиманий"), KeyboardButton("🎯 +25 отжиманий")],
        [KeyboardButton("🎲 Другое число"), KeyboardButton("🏅 Мой статус")]
    ]
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True)

def progress_bar(val, total, length=5, char_full="🟩", char_empty="⬜️"):
    val = max(0, min(val, total))
    filled = int(round(length * val / float(total)))
    empty = length - filled
    percent = int(round(100 * val / float(total)))
    bar = (char_full * filled) + (char_empty * empty)
    return f"{bar} {percent}%"

def days_bar(day, total_days=90, length=5, char_full="🟪", char_empty="⬜️"):
    day = max(0, min(day, total_days))
    filled = int(round(length * day / float(total_days)))
    empty = length - filled
    percent = int(round(100 * day / float(total_days)))
    bar = (char_full * filled) + (char_empty * empty)
    return f"{bar} {percent}%"

def emoji_number(num):
    emoji_digits = {
        '0': '0️⃣', '1': '1️⃣', '2': '2️⃣', '3': '3️⃣', '4': '4️⃣',
        '5': '5️⃣', '6': '6️⃣', '7': '7️⃣', '8': '8️⃣', '9': '9️⃣'
    }
    return ''.join(emoji_digits.get(d, d) for d in str(num))

def hearts(fails):
    return (HEART_RED * (3 - fails)) + (HEART_BLACK * fails)

def is_valid_time(timestr):
    if not re.match(r"^\d{2}:\d{2}$", timestr):
        return False
    try:
        datetime.strptime(timestr, "%H:%M")
        return True
    except ValueError:
        return False

def time_to_minutes(timestr):
    h, m = map(int, timestr.split(":"))
    return h * 60 + m

def minutes_to_time(mins):
    h = mins // 60
    m = mins % 60
    return dt_time(hour=h, minute=m)

def get_reminder_times(start_time_str, end_time_str, reminders_count):
    """Вернёт список времени напоминаний в формате [datetime.time, ...] равномерно между стартом и концом."""
    start_dt = datetime.strptime(start_time_str, "%H:%M")
    end_dt = datetime.strptime(end_time_str, "%H:%M")
    total_minutes = int((end_dt - start_dt).total_seconds() // 60)
    if reminders_count < 2:
        return [start_dt.time()]
    interval = total_minutes / (reminders_count - 1)
    times = []
    for i in range(reminders_count):
        mins = int(round(i * interval))
        t = (start_dt + timedelta(minutes=mins)).time()
        times.append(t)
    return times

async def send_reminders_loop(application, user_id, chat_id):
    """Фоновая задача на каждый день: отправлять напоминания по расписанию, если челлендж не завершён."""
    while True:
        u = get_user(user_id)
        if not u:
            return
        # Получаем расписание
        start_time = u["start_time"]
        end_time = u["end_time"]
        reminders_count = u["reminders"]
        times = get_reminder_times(start_time, end_time, reminders_count)

        now = datetime.now()
        today = now.date()
        # Считаем datetime для всех напоминаний на сегодня
        reminder_datetimes = []
        for t in times:
            reminder_dt = datetime.combine(today, t)
            if reminder_dt > now:
                reminder_datetimes.append(reminder_dt)
        # Запускаем отправку напоминаний на сегодня
        for reminder_dt in reminder_datetimes:
            seconds = (reminder_dt - datetime.now()).total_seconds()
            if seconds > 0:
                await asyncio.sleep(seconds)
            # Проверяем, нужно ли отправлять (100 сделано - не отправляем)
            pushups = get_pushups_today(user_id)
            if pushups >= 100:
                continue
            # Отправляем напоминание
            await application.bot.send_message(
                chat_id=chat_id,
                text="Эй! Ты не забыл про челлендж? Отожмись! 💪",
                reply_markup=get_main_keyboard()
            )
        # Спим до полуночи
        tomorrow = datetime.combine(now.date() + timedelta(days=1), dt_time(0,0))
        await asyncio.sleep((tomorrow - datetime.now()).total_seconds())

def start_reminders(application, user_id, chat_id):
    """Запустить фоновую задачу напоминаний для пользователя."""
    # Если уже есть задача для этого пользователя — отменяем
    old_task = reminder_tasks.get(user_id)
    if old_task:
        old_task.cancel()
    task = asyncio.create_task(send_reminders_loop(application, user_id, chat_id))
    reminder_tasks[user_id] = task

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    user = update.effective_user
    user_db = get_user(user.id)
    if user_db:
        await update.message.reply_text(
            "Ты уже зарегистрирован! Напиши /reset, чтобы начать заново.",
            reply_markup=get_main_keyboard()
        )
        return ConversationHandler.END
    await update.message.reply_text("Как к тебе обращаться? 📝")
    return ASK_NAME

async def ask_start_time(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    context.user_data["name"] = update.message.text
    await update.message.reply_text(
        "Укажи время в формате ЧАСЫ:МИНУТЫ (например, 07:00), когда бот начинает работать (начало дня) и ты сможешь записывать свои отжимания🕒"
    )
    return ASK_START_TIME

async def ask_end_time(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    time_text = update.message.text.strip()
    if not is_valid_time(time_text):
        await update.message.reply_text(
            "Пожалуйста, укажи время в формате ЧЧ:ММ (например, 07:00)"
        )
        return ASK_START_TIME
    context.user_data["start_time"] = time_text
    await update.message.reply_text(
        "Укажи время в формате ЧАСЫ:МИНУТЫ (например, 22:00), когда бот завершает работу (конец дня) 🕒 и ты больше не сможешь добавлять отжимания в этот день"
    )
    return ASK_END_TIME

async def ask_reminders(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    time_text = update.message.text.strip()
    if not is_valid_time(time_text):
        await update.message.reply_text(
            "Пожалуйста, укажи время в формате ЧЧ:ММ (например, 22:00)"
        )
        return ASK_END_TIME

    start_time = context.user_data.get("start_time")
    end_time = time_text

    if time_to_minutes(end_time) <= time_to_minutes(start_time):
        await update.message.reply_text(
            "Время конца дня должно быть позже времени начала дня!\n"
            "Пожалуйста, укажи время в формате ЧЧ:ММ (например, 22:00), когда бот завершает работу (конец дня)"
        )
        return ASK_END_TIME

    context.user_data["end_time"] = end_time
    await update.message.reply_text(
        "Сколько раз в день тебе напоминать про отжимания? Минимум 2, максимум 10 🔔"
    )
    return ASK_REMINDERS

async def save_reminders(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    try:
        reminders = int(update.message.text)
    except ValueError:
        await update.message.reply_text(
            "Пожалуйста, введи число (от 2 до 10)\nСколько раз в день тебе напоминать про отжимания? Минимум 2, максимум 10 🔔"
        )
        return ASK_REMINDERS
    if reminders < 2 or reminders > 10:
        await update.message.reply_text(
            "Число должно быть от 2 до 10\nСколько раз в день тебе напоминать про отжимания? Минимум 2, максимум 10 🔔"
        )
        return ASK_REMINDERS
    context.user_data["reminders"] = reminders
    user = update.effective_user
    user_name = context.user_data.get("name", "друг")

    add_user(
        user.id,
        context.user_data["name"],
        context.user_data["start_time"],
        context.user_data["end_time"],
        context.user_data["reminders"]
    )

    await update.message.reply_text(
        f"{DEVIL} Приветствую в Devil's 100 challenge, *{user_name}*! Сегодня первый день челленджа, а значит ты должен сделать первые 100 отжиманий! Удачи! {CLOVER}",
        reply_markup=get_main_keyboard(),
        parse_mode="Markdown"
    )
    # Запустить напоминалки!
    start_reminders(context.application, user.id, update.effective_chat.id)
    await status(update, context)
    return ConversationHandler.END

async def reset(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    reset_user(user.id)
    # Остановить напоминалки
    old_task = reminder_tasks.get(user.id)
    if old_task:
        old_task.cancel()
        reminder_tasks.pop(user.id)
    await update.message.reply_text(
        "Все данные сброшены! Можешь пройти регистрацию заново через /start.",
        reply_markup=ReplyKeyboardRemove()
    )

def parse_pushup_command(text):
    mapping = {
        "🎯 +10 отжиманий": 10,
        "🎯 +15 отжиманий": 15,
        "🎯 +20 отжиманий": 20,
        "🎯 +25 отжиманий": 25
    }
    return mapping.get(text.strip(), None)

async def add_pushups_generic(update, context, count):
    user = update.effective_user
    user_db = get_user(user.id)
    if not user_db:
        await update.message.reply_text("Сначала зарегистрируйся через /start", reply_markup=get_main_keyboard())
        return

    user_name = user_db["username"] or user_db["name"] or "друг"
    cur = user_db["pushups_today"]

    if cur >= 100:
        await update.message.reply_text(
            "Нельзя добавить больше 100 отжиманий за день!",
            reply_markup=get_main_keyboard()
        )
        return

    ok = add_pushups(user.id, count)
    new_count = get_pushups_today(user.id)

    await update.message.reply_text(
        f"Отлично! {emoji_number(count)} отжиманий добавлено к сегодняшнему прогрессу {UP}",
        parse_mode="Markdown",
        reply_markup=get_main_keyboard()
    )
    await update.message.reply_text(
        f"Текущий прогресс: {emoji_number(new_count)}",
        reply_markup=get_main_keyboard()
    )
    if new_count >= 100 and cur < 100:
        await update.message.reply_text(
            f"Юху! *{user_name}*, сегодняшняя сотка сделана! Поздравляю! {STRONG} 💯",
            parse_mode="Markdown",
            reply_markup=get_main_keyboard()
        )

async def add_custom(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["awaiting_custom"] = True
    await update.message.reply_text("Введи количество сделанных отжиманий (например, 13):", reply_markup=get_main_keyboard())

async def handle_custom_pushups(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip()
    count = parse_pushup_command(text)
    if count is not None:
        await add_pushups_generic(update, context, count)
        return
    if text == "🎲 Другое число":
        await add_custom(update, context)
        return
    if text == "🏅 Мой статус":
        await status(update, context)
        return
    if context.user_data.get("awaiting_custom"):
        try:
            count = int(text)
        except ValueError:
            await update.message.reply_text("Пожалуйста, введи число.", reply_markup=get_main_keyboard())
            return
        await add_pushups_generic(update, context, count)
        context.user_data["awaiting_custom"] = False

async def status(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    u = get_user(user.id)
    if not u:
        await update.message.reply_text("Сначала зарегистрируйся через /start", reply_markup=get_main_keyboard())
        return
    day = u["day"]
    fails = u["fails"]
    pushups = u["pushups_today"]

    bar_days = days_bar(day, 90, 5, "🟪", "⬜️")
    bar_pushups = progress_bar(pushups, 100, 5, "🟩", "⬜️")
    msg = (
        f"DAY: {emoji_number(day)} {bar_days}\n\n"
        f"PROGRESS: {emoji_number(pushups)} {bar_pushups}\n\n"
        f"HEALTH: {hearts(fails)}"
    )
    await update.message.reply_text(msg, reply_markup=get_main_keyboard())

async def check_end_of_day(user_id, update):
    u = get_user(user_id)
    user_name = u["username"] or u["name"] or "друг"
    if u and u["pushups_today"] < 100:
        fails = fail_day(user_id)
        if fails < 3:
            await update.message.reply_text(
                f"Па-па-па… *{user_name}*, сегодня ты не осилил сотку. К сожалению это минус жизнь. У тебя осталось всего: {hearts(fails)}",
                parse_mode="Markdown",
                reply_markup=get_main_keyboard()
            )
        else:
            await update.message.reply_text(
                f"К сожалению ты зафейлил третий раз! {SKULL}\nДля тебя, *{user_name}*, Devil's 100 challenge закончен… в этот раз!\nДля перезапуска напиши /reset",
                reply_markup=ReplyKeyboardRemove(),
                parse_mode="Markdown"
            )

async def addday(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    u = get_user(user.id)
    user_name = u["username"] or u["name"] or "друг"
    if not u:
        await update.message.reply_text("Сначала зарегистрируйся через /start", reply_markup=get_main_keyboard())
        return
    if u["pushups_today"] < 100:
        await check_end_of_day(user.id, update)
    else:
        next_day(user.id)
        await update.message.reply_text(
            f"Поздравляю, *{user_name}*, ты молодец! Сегодняшняя сотка сделана, увидимся завтра! {STRONG}",
            parse_mode="Markdown",
            reply_markup=get_main_keyboard()
        )
    await status(update, context)

async def on_startup(application: Application):
    """Запустить напоминалки для всех пользователей при запуске бота."""
    for user_id in get_all_user_ids():
        user = get_user(user_id)
        if user:
            chat_id = user_id  # предполагаем, что юзер всегда в личке с ботом
            start_reminders(application, user_id, chat_id)

# === Добавляем функции для /add10 и т.д. ===
async def add10(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await add_pushups_generic(update, context, 10)

async def add15(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await add_pushups_generic(update, context, 15)

async def add20(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await add_pushups_generic(update, context, 20)

async def add25(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await add_pushups_generic(update, context, 25)

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
    application.run_async(on_startup(application))
    application.run_polling()

if __name__ == "__main__":
    main()
