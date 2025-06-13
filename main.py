import logging
import os
import re
import asyncio
from datetime import datetime, timedelta, time as dt_time
from dotenv import load_dotenv
from pytz import timezone
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
    get_all_user_ids,
    update_user_settings,
    get_top_pushups_today,
)

ASK_NAME, ASK_START_TIME, ASK_END_TIME, ASK_REMINDERS = range(4)
(
    SETTINGS_ASK_START,
    SETTINGS_INPUT_START,
    SETTINGS_ASK_END,
    SETTINGS_INPUT_END,
    SETTINGS_ASK_REMINDERS,
    SETTINGS_INPUT_REMINDERS,
) = range(10, 16)

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
SETTINGS = "⚙️"
LEADERBOARD = "🏆 Топ учасників"

BACK = "⬅️ Назад"
CANCEL_EMOJI = "🛑"

ADMIN_ID = 271278573

load_dotenv()
TOKEN = os.getenv("TELEGRAM_TOKEN")

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

init_db()

reminder_tasks = {}

KIEV_TZ = timezone("Europe/Kyiv")

def get_main_keyboard():
    keyboard = [
        [KeyboardButton("🎯 +10 віджимань"), KeyboardButton("🎯 +15 віджимань")],
        [KeyboardButton("🎯 +20 віджимань"), KeyboardButton("🎯 +25 віджимань")],
        [KeyboardButton("🎲 Інша кількість"), KeyboardButton("➖ Зменшити")],
        [KeyboardButton("🏅 Мій статус"), KeyboardButton("🏆 Топ учасників")],
        [KeyboardButton(f"{SETTINGS} Налаштування")],
    ]
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True)

def get_yes_no_back_keyboard():
    keyboard = [
        [KeyboardButton("✅ Так"), KeyboardButton("❌ Ні")],
        [KeyboardButton(BACK)]
    ]
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True, one_time_keyboard=True)

def get_back_keyboard():
    keyboard = [
        [KeyboardButton(BACK)]
    ]
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True, one_time_keyboard=True)
def get_settings_only_keyboard():
    keyboard = [
        [KeyboardButton(f"{SETTINGS} Налаштування")]
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

def is_within_today_working_period(start_time, end_time):
    now = datetime.now(KIEV_TZ)
    today = now.date()
    start_dt = KIEV_TZ.localize(datetime.combine(today, datetime.strptime(start_time, "%H:%M").time()))
    end_dt = KIEV_TZ.localize(datetime.combine(today, datetime.strptime(end_time, "%H:%M").time()))
    return start_dt <= now < end_dt

async def send_reminders_loop(application, user_id, chat_id):
    u = get_user(user_id)
    if not u:
        return
    skip_day = False
    if u["day"] == 1 and not is_within_today_working_period(u["start_time"], u["end_time"]):
        skip_day = True
    while True:
        u = get_user(user_id)
        if not u:
            return
        start_time = u["start_time"]
        end_time = u["end_time"]
        reminders_count = u["reminders"]
        now = datetime.now(KIEV_TZ)
        today = now.date()
        start_dt = KIEV_TZ.localize(datetime.combine(today, datetime.strptime(start_time, "%H:%M").time()))
        end_dt = KIEV_TZ.localize(datetime.combine(today, datetime.strptime(end_time, "%H:%M").time()))
        if skip_day:
            if now >= end_dt:
                next_start_dt = KIEV_TZ.localize(datetime.combine(today + timedelta(days=1), datetime.strptime(start_time, "%H:%M").time()))
                await asyncio.sleep((next_start_dt - now).total_seconds())
            elif now < start_dt:
                await asyncio.sleep((start_dt - now).total_seconds())
            skip_day = False
            continue
        if now < start_dt:
            await asyncio.sleep((start_dt - now).total_seconds())
        u = get_user(user_id)
        if u:
            day_num = u["day"]
            if day_num == 1:
                await application.bot.send_message(
                    chat_id=chat_id,
                    text=f"{DEVIL} Вітаю в Devil's 100 Challenge, *{u['username'] or u['name'] or 'друг'}*! Сьогодні перший день челленджу, а отже тебі необхідно зробити перші 100 віджимань! Хай щастить і гарного дня! {CLOVER}",
                    parse_mode="Markdown",
                    reply_markup=get_main_keyboard()
                )
            else:
                await application.bot.send_message(
                    chat_id=chat_id,
                    text=f"Знову вітаю в Devil's 100 Challenge! {DEVIL} Сьогодні {emoji_number(day_num)} день змагання, а значить тобі треба зробити чергові 100 віджимань! Хай щастить і гарного дня! {CLOVER}",
                    parse_mode="Markdown",
                    reply_markup=get_main_keyboard()
                )

            # --- Запускаем таск экстра-напоминания ---
            async def extra_reminder():
                # Ждем до 15 минут до конца дня
                now = datetime.now(KIEV_TZ)
                reminder_15min_dt = end_dt - timedelta(minutes=15)
                if reminder_15min_dt > now:
                    await asyncio.sleep((reminder_15min_dt - now).total_seconds())
                # Проверяем pushups только в этот момент
                pushups = get_pushups_today(user_id)
                if pushups < 100:
                    user_name = u["username"] or u["name"] or "друг"
                    await application.bot.send_message(
                        chat_id=chat_id,
                        text=f"Лишилось 15 хвилин до кінця дня! Або збільшуй в налаштуваннях 'кінець дня' або добивай віджимання. За роботу, {user_name}! 👊",
                        reply_markup=get_main_keyboard()
                    )
            extra_task = asyncio.create_task(extra_reminder())

            # --- Рассылка напоминаний ---
            times = get_reminder_times(start_time, end_time, reminders_count)
            now = datetime.now(KIEV_TZ)
            today = now.date()
            reminder_datetimes = []
            for t in times:
                reminder_dt = KIEV_TZ.localize(datetime.combine(today, t))
                if reminder_dt > now:
                    reminder_datetimes.append(reminder_dt)
            for reminder_dt in reminder_datetimes:
                seconds = (reminder_dt - datetime.now(KIEV_TZ)).total_seconds()
                if seconds > 0:
                    await asyncio.sleep(seconds)
                pushups = get_pushups_today(user_id)
                if pushups >= 100:
                    continue
                await application.bot.send_message(
                    chat_id=chat_id,
                    text="Агов! Ти не забув(ла) про челлендж? Відожмись! 💪",
                    reply_markup=get_main_keyboard()
                )

            # --- Ждем до конца дня ---
            seconds_to_end = (end_dt - datetime.now(KIEV_TZ)).total_seconds()
            if seconds_to_end > 0:
                await asyncio.sleep(seconds_to_end)

            # --- Убедимся, что экстра-напоминание завершено ---
            if not extra_task.done():
                await extra_task

            # --- Итог дня ---
            u = get_user(user_id)
            if u:
                user_name = u["username"] or u["name"] or "друг"
                if u["pushups_today"] >= 100:
                    day_completed = u["day"]
                    next_day(user_id)
                    if day_completed >= 90:
                        await application.bot.send_message(
                            chat_id=chat_id,
                            text=(
                                "🎉 Вітаю з перемогою в Devil's 100 Challenge! 💪🔥\n"
                                "Ти довів(ла), що сила — не лише в м'язах, а й у характері.\n"
                                "Кожен ранок, кожен підхід, кожна крапля поту — це крок до перемоги над собою.\n"
                                "Ти — натхнення для всіх, хто прагне до дісципліни та самовдосконалення! 🌟\n"
                                "👏 Браво, чемпіоне! Нехай цей успіх стане лише початком нових звершень! 🚀\n"
                                "🏆 #90ДнівСили #ЗалізнаВоля👊"
                            ),
                            parse_mode="Markdown",
                            reply_markup=get_main_keyboard()
                        )
                    else:
                        await application.bot.send_message(
                            chat_id=chat_id,
                            text=f"Вітаю, *{user_name}*, ти молодець! Сьогоднішня сотка зроблена, побачимося завтра! {STRONG}",
                            parse_mode="Markdown",
                            reply_markup=get_main_keyboard()
                        )
                else:
                    fails = fail_day(user_id)
                    if fails < 3:
                        await application.bot.send_message(
                            chat_id=chat_id,
                            text=f"Пу-пу-пу… *{user_name}*, сьогодні ти не осилив(ла) сотку. Нажаль це мінус жізнь. В тебе лишилось усього: {hearts(fails)}",
                            parse_mode="Markdown",
                            reply_markup=get_main_keyboard()
                        )
                    else:
                        await application.bot.send_message(
                            chat_id=chat_id,
                            text=f"Нажаль ти зафейлив(ла) третій раз! {SKULL}\nДля тебе, *{user_name}*, Devil's 100 Challenge закінчено… цього разу!\nДля перезапуску напиши /reset",
                            reply_markup=ReplyKeyboardRemove(),
                            parse_mode="Markdown"
                        )
            tomorrow = KIEV_TZ.localize(datetime.combine(now.date() + timedelta(days=1), dt_time(0,0)))
            await asyncio.sleep((tomorrow - datetime.now(KIEV_TZ)).total_seconds())

def start_reminders(application, user_id, chat_id):
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
            "Ти вже зареєстрований(на)! Напиши /reset, щоб розпочати все з нуля.",
            reply_markup=get_main_keyboard()
        )
        return ConversationHandler.END
    await update.message.reply_text("Як до тебе звертатись? 📝")
    return ASK_NAME

async def ask_start_time(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    context.user_data["name"] = update.message.text
    await update.message.reply_text(
        "Вкажи час у форматі ГОДИНИ:ХВИЛИНИ (наприклад, 07:00), коли бот починає працювати (початок дня) й коли ти зможешь почати записувати свої віджимання 🕒"
    )
    return ASK_START_TIME

async def ask_end_time(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    time_text = update.message.text.strip()
    if not is_valid_time(time_text):
        await update.message.reply_text(
            "Будь ласка, вкажи час у форматі ГОДИНИ:ХВИЛИНИ (наприклад, 07:00)"
        )
        return ASK_START_TIME
    context.user_data["start_time"] = time_text
    await update.message.reply_text(
        "Вкажи час у форматі ГОДИНИ:ХВИЛИНИ (наприклад, 22:00), коли бот завершує роботу (кінець дня) 🕒 й ти більше не зможеш додавати віджимання в цей день"
    )
    return ASK_END_TIME

async def ask_reminders(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    time_text = update.message.text.strip()
    if not is_valid_time(time_text):
        await update.message.reply_text(
            "Будь ласка, вкажи час у форматі ГОДИНИ:ХВИЛИНИ (наприклад, 22:00)"
        )
        return ASK_END_TIME

    start_time = context.user_data.get("start_time")
    end_time = time_text

    if time_to_minutes(end_time) <= time_to_minutes(start_time):
        await update.message.reply_text(
            "Час кінця дня має бути пізніше часу початку дня!\n"
            "Будь ласка, вкажи час у форматі ГОДИНИ:ХВИЛИНИ (наприклад, 22:00), коли бот завершує роботу (кінець дня)"
        )
        return ASK_END_TIME

    context.user_data["end_time"] = end_time
    await update.message.reply_text(
        "Сікільки разів на день тобі нагадувать про віджимання? Мінімум 2, максимум 10 🔔 Нагадування будут рівномірно розподілені по робочему дню"
    )
    return ASK_REMINDERS

async def save_reminders(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    try:
        reminders = int(update.message.text)
    except ValueError:
        await update.message.reply_text(
            "Будь ласка, вкажи число (від 2 до 10)\nСікільки разів на день тобі нагадувать про віджимання? Мінімум 2, максимум 10 🔔 Нагадування будут рівномірно розподілені по робочему дню"
        )
        return ASK_REMINDERS
    if reminders < 2 or reminders > 10:
        await update.message.reply_text(
            "Число має бути від 2 до 10\nСікільки разів на день тобі нагадувать про віджимання? Мінімум 2, максимум 10 🔔 Нагадування будут рівномірно розподілені по робочему дню"
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
        f"{DEVIL} Вітаю з реєстрацією в Devil's 100 Challenge, *{user_name}*! Очікуй на початок першого дня згідно з налаштуваннями (в момент початку дня, який ти встановив(ла) при реєстрації, і стартує челендж!) Побачимось! 👋",
        reply_markup=get_settings_only_keyboard(),
        parse_mode="Markdown"
    )

    start_reminders(context.application, user.id, update.effective_chat.id)
    return ConversationHandler.END

async def reset(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    reset_user(user.id)
    old_task = reminder_tasks.get(user.id)
    if old_task:
        old_task.cancel()
        reminder_tasks.pop(user.id)
    await update.message.reply_text(
        "Усі дані скинуто! Можеш пройти реєстрацію наново через /start.",
        reply_markup=ReplyKeyboardRemove()
    )

def parse_pushup_command(text):
    mapping = {
        "🎯 +10 віджимань": 10,
        "🎯 +15 віджимань": 15,
        "🎯 +20 віджимань": 20,
        "🎯 +25 віджимань": 25
    }
    return mapping.get(text.strip(), None)

async def add_pushups_generic(update, context, count):
    user = update.effective_user
    user_db = get_user(user.id)
    if not user_db:
        await update.message.reply_text("Спочатку зареєструйся через /start", reply_markup=get_main_keyboard())
        return

    user_name = user_db["username"] or user_db["name"] or "друг"
    cur = user_db["pushups_today"]

    if cur >= 100:
        await update.message.reply_text(
            "Не можна додавати більше 100 віджимань на день!",
            reply_markup=get_main_keyboard()
        )
        return

    ok = add_pushups(user.id, count)
    new_count = get_pushups_today(user.id)

    await update.message.reply_text(
        f"Чудово! {emoji_number(count)} віджимань додано до сьогоднішнього прогресу {UP}",
        parse_mode="Markdown",
        reply_markup=get_main_keyboard()
    )
    await update.message.reply_text(
        f"Поточний прогрес: {emoji_number(new_count)}",
        reply_markup=get_main_keyboard()
    )
    if new_count >= 100 and cur < 100:
        await update.message.reply_text(
            f"Юху! *{user_name}*, сьогоднішня сотка зроблена! Вітаю! {STRONG} 💯",
            parse_mode="Markdown",
            reply_markup=get_main_keyboard()
        )

async def add_custom(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["awaiting_custom"] = True
    await update.message.reply_text("Вкажи кількість зроблених віджимань (наприклад, 13):", reply_markup=get_main_keyboard())

async def decrease_pushups(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    user_db = get_user(user.id)
    if not user_db:
        await update.message.reply_text("Спочатку зареєструйся через /start", reply_markup=get_main_keyboard())
        return

    await update.message.reply_text(
        "На скільки зменшити кількість віджимань? Вкажи число (наприклад, 10):",
        reply_markup=get_main_keyboard()
    )
    context.user_data["awaiting_decrease"] = True

async def handle_custom_pushups(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip()
    if context.user_data.get("awaiting_decrease"):
        try:
            dec_count = int(text)
        except ValueError:
            await update.message.reply_text("Будь ласка, вкажи число", reply_markup=get_main_keyboard())
            return
        user = update.effective_user
        user_db = get_user(user.id)
        cur = user_db["pushups_today"]
        new_val = max(0, cur - dec_count)
        conn = get_db()
        cur_db = conn.cursor()
        cur_db.execute("UPDATE users SET pushups_today=? WHERE user_id=?", (new_val, user.id))
        conn.commit()
        context.user_data["awaiting_decrease"] = False
        await update.message.reply_text(
            f"Кількість зменшено! Новий прогрес: {emoji_number(new_val)}",
            reply_markup=get_main_keyboard()
        )
        return
    count = parse_pushup_command(text)
    if count is not None:
        await add_pushups_generic(update, context, count)
        return
    if text == "🎲 Інша кількість":
        await add_custom(update, context)
        return
    if text == "🏅 Мій статус":
        await status(update, context)
        return
    if text == f"{SETTINGS} Налаштування":
        await settings_entry(update, context)
        return
    if context.user_data.get("awaiting_custom"):
        try:
            count = int(text)
        except ValueError:
            await update.message.reply_text("Будь ласка, вкажи число", reply_markup=get_main_keyboard())
            return
        await add_pushups_generic(update, context, count)
        context.user_data["awaiting_custom"] = False

async def status(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    u = get_user(user.id)
    if not u:
        await update.message.reply_text("Спочатку зареєструйся через /start", reply_markup=get_main_keyboard())
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

async def lobby(update: Update, context: ContextTypes.DEFAULT_TYPE):
    top = get_top_pushups_today(5)
    if not top:
        await update.message.reply_text("Поки ще ніхто не віджимався сьогодні! Будь першим! 💪", reply_markup=get_main_keyboard())
        return
    msg = f"{LEADERBOARD}\n\n"
    for idx, user in enumerate(top, 1):
        name = user["username"] or user["name"] or "Безіменний"
        count = user["pushups_today"]
        # Показываем время финиша, если чел сделал 100+
        if count >= 100 and user["completed_time"]:
            # Только часы и минуты (например, 09:15)
            time_str = user["completed_time"][11:16]
            msg += f"{idx}. {name} — {count} віджимань (фініш о {time_str})\n"
        else:
            msg += f"{idx}. {name} — {count} віджимань\n"
    await update.message.reply_text(msg, reply_markup=get_main_keyboard())

async def check_end_of_day(user_id, update):
    u = get_user(user_id)
    user_name = u["username"] or u["name"] or "друг"
    if u and u["pushups_today"] < 100:
        fails = fail_day(user_id)
        if fails < 3:
            await update.message.reply_text(
                f"Пу-пу-пу… *{user_name}*, сьогодні ти не осилив(ла) сотку. Нажаль це мінус жізнь. В тебе лишилось усього: {hearts(fails)}",
                parse_mode="Markdown",
                reply_markup=get_main_keyboard()
            )
        else:
            await update.message.reply_text(
                f"Нажаль ти зафейлив(ла) третій раз! {SKULL}\nДля тебе, *{user_name}*, Devil's 100 Challenge закінчено… цього разу!\nДля перезапуску напиши /reset",
                reply_markup=ReplyKeyboardRemove(),
                parse_mode="Markdown"
            )

async def addday(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        return
    user = update.effective_user
    u = get_user(user.id)
    user_name = u["username"] or u["name"] or "друг"
    if not u:
        await update.message.reply_text("Спочатку зареєструйся через /start", reply_markup=get_main_keyboard())
        return
    if u["pushups_today"] < 100:
        await check_end_of_day(user.id, update)
    else:
        next_day(user.id)
        await update.message.reply_text(
            f"Вітаю, *{user_name}*, ти молодець! Сьогоднішня сотка зроблена, побачимося завтра! {STRONG}",
            parse_mode="Markdown",
            reply_markup=get_main_keyboard()
        )
    await status(update, context)

async def on_startup(application: Application):
    for user_id in get_all_user_ids():
        user = get_user(user_id)
        if user:
            chat_id = user_id
            start_reminders(application, user_id, chat_id)

async def add10(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await add_pushups_generic(update, context, 10)

async def add15(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await add_pushups_generic(update, context, 15)

async def add20(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await add_pushups_generic(update, context, 20)

async def add25(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await add_pushups_generic(update, context, 25)

async def cancel_settings(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        f"Усі зміни скасовані! {CANCEL_EMOJI}",
        reply_markup=get_main_keyboard()
    )
    return ConversationHandler.END

async def settings_entry(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    u = get_user(user.id)
    start_time = u["start_time"] if u else "не задано"
    await update.message.reply_text(
        f"Змінити час початку дня? (поточне значення: {start_time})",
        reply_markup=get_yes_no_back_keyboard()
    )
    return SETTINGS_ASK_START

async def settings_ask_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    answer = update.message.text.strip()
    user = update.effective_user
    u = get_user(user.id)
    end_time = u["end_time"] if u else "не задано"

    if answer == BACK:
        return await cancel_settings(update, context)
    if answer == "✅ Так":
        await update.message.reply_text(
            "Вкажи новий час початку дня в форматі ГОДИНИ:ХВИЛИНИ (наприклад, 07:00):",
            reply_markup=get_back_keyboard()
        )
        return SETTINGS_INPUT_START
    if answer == "❌ Ні":
        await update.message.reply_text(
            f"Змінити час кінця дня? (поточне значення: {end_time})",
            reply_markup=get_yes_no_back_keyboard()
        )
        return SETTINGS_ASK_END
    await update.message.reply_text(
        "Будь ласка, скористайся кнопками для відповіді",
        reply_markup=get_yes_no_back_keyboard()
    )
    return SETTINGS_ASK_START

async def settings_input_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    time_text = update.message.text.strip()
    if time_text == BACK:
        return await cancel_settings(update, context)
    if not is_valid_time(time_text):
        await update.message.reply_text(
            "Будь ласка, вкажи час у форматі ГОДИНИ:ХВИЛИНИ (наприклад, 07:00):",
            reply_markup=get_back_keyboard()
        )
        return SETTINGS_INPUT_START
    user_db = get_user(update.effective_user.id)
    end_time = context.user_data.get("new_end_time") or user_db["end_time"]
    if time_to_minutes(time_text) >= time_to_minutes(end_time):
        await update.message.reply_text(
            "Час кінця дня має бути візніше часу початку дня! Спробуй знову.\nВкажи новий час початку дня в форматі ГОДИНИ:ХВИЛИНИ (наприклад, 07:00):",
            reply_markup=get_back_keyboard()
        )
        return SETTINGS_INPUT_START
    context.user_data["new_start_time"] = time_text
    await update.message.reply_text(
        f"Змінити час кінця дня? (поточне значення: {end_time})",
        reply_markup=get_yes_no_back_keyboard()
    )
    return SETTINGS_ASK_END

async def settings_ask_end(update: Update, context: ContextTypes.DEFAULT_TYPE):
    answer = update.message.text.strip()
    user = update.effective_user
    u = get_user(user.id)
    reminders = u["reminders"] if u else "не задано"

    if answer == BACK:
        return await cancel_settings(update, context)
    if answer == "✅ Так":
        await update.message.reply_text(
            "Вкажи новий час кінця дня в форматі ГОДИНИ:ХВИЛИНИ (наприклад, 22:00):",
            reply_markup=get_back_keyboard()
        )
        return SETTINGS_INPUT_END
    if answer == "❌ Ні":
        await update.message.reply_text(
            f"Змінити кількість нагадувань? (зараз їх кількість: {reminders})",
            reply_markup=get_yes_no_back_keyboard()
        )
        return SETTINGS_ASK_REMINDERS
    await update.message.reply_text(
        "Будь ласка, скористайся кнопками для відповіді.",
        reply_markup=get_yes_no_back_keyboard()
    )
    return SETTINGS_ASK_END

async def settings_input_end(update: Update, context: ContextTypes.DEFAULT_TYPE):
    time_text = update.message.text.strip()
    if time_text == BACK:
        return await cancel_settings(update, context)
    if not is_valid_time(time_text):
        await update.message.reply_text(
            "Будь ласка, вкажи час в форматі ГОДИНИ:ХВИЛИНИ (наприклад, 22:00):",
            reply_markup=get_back_keyboard()
        )
        return SETTINGS_INPUT_END
    user_db = get_user(update.effective_user.id)
    start_time = context.user_data.get("new_start_time") or user_db["start_time"]
    if time_to_minutes(time_text) <= time_to_minutes(start_time):
        await update.message.reply_text(
            "Час кінця дня має бути пізніше часу початку дня! Спробуй знову.\nВкажи новий час кінця дня в форматі ГОДИНИ:ХВИЛИНИ (наприклад, 22:00):",
            reply_markup=get_back_keyboard()
        )
        return SETTINGS_INPUT_END
    context.user_data["new_end_time"] = time_text
    reminders = user_db["reminders"] if user_db else "не задано"
    await update.message.reply_text(
        f"Змінити кількість нагадувань? (зараз їх кількість: {reminders} рвіномірно протягом робочого дня)",
        reply_markup=get_yes_no_back_keyboard()
    )
    return SETTINGS_ASK_REMINDERS

async def settings_ask_reminders(update: Update, context: ContextTypes.DEFAULT_TYPE):
    answer = update.message.text.strip()
    if answer == BACK:
        return await cancel_settings(update, context)
    if answer == "✅ Так":
        await update.message.reply_text(
            "Вкажи нову кількість нагадувань (від 2 до 10):",
            reply_markup=get_back_keyboard()
        )
        return SETTINGS_INPUT_REMINDERS
    if answer == "❌ Ні":
        return await settings_apply(update, context)
    await update.message.reply_text(
        "Будь ласка, скористайся кнопками для відповіді.",
        reply_markup=get_yes_no_back_keyboard()
    )
    return SETTINGS_ASK_REMINDERS

async def settings_input_reminders(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip()
    if text == BACK:
        return await cancel_settings(update, context)
    try:
        reminders = int(text)
    except ValueError:
        await update.message.reply_text(
            "Будь ласка, вкажи число (від 2 до 10):",
            reply_markup=get_back_keyboard()
        )
        return SETTINGS_INPUT_REMINDERS
    if reminders < 2 or reminders > 10:
        await update.message.reply_text(
            "Число має бути від 2 до 10:",
            reply_markup=get_back_keyboard()
        )
        return SETTINGS_INPUT_REMINDERS
    context.user_data["new_reminders"] = reminders
    return await settings_apply(update, context)

async def settings_apply(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    user_db = get_user(user.id)
    if not user_db:
        await update.message.reply_text("Спочатку зареєструйся через /start", reply_markup=get_main_keyboard())
        return ConversationHandler.END

    keys = context.user_data.keys()
    if not any(k in keys for k in ["new_start_time", "new_end_time", "new_reminders"]):
        await update.message.reply_text(
            "Зміни не внесено!",
            reply_markup=get_main_keyboard()
        )
        return ConversationHandler.END

    start_time = context.user_data["new_start_time"] if "new_start_time" in context.user_data else user_db["start_time"]
    end_time = context.user_data["new_end_time"] if "new_end_time" in context.user_data else user_db["end_time"]
    reminders = context.user_data["new_reminders"] if "new_reminders" in context.user_data else user_db["reminders"]

    if time_to_minutes(end_time) <= time_to_minutes(start_time):
        await update.message.reply_text(
            "Час кінця дня має бути пізніше часу початку дня! Зміни не збережено.",
            reply_markup=get_main_keyboard()
        )
        return ConversationHandler.END

    update_user_settings(user.id, start_time, end_time, reminders)
    start_reminders(context.application, user.id, update.effective_chat.id)

    await update.message.reply_text(
        "Налаштування оновлено! Новий розклад:\n"
        f"Початок дня: {start_time}\n"
        f"Кінець дня: {end_time}\n"
        f"кількість нагадувань: {reminders}",
        reply_markup=get_main_keyboard()
    )
    return ConversationHandler.END

async def settestreminders(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        return
    args = context.args
    user = update.effective_user
    if len(args) != 3:
        await update.message.reply_text("Используй: /settestreminders <start> <end> <count>\nнапример: /settestreminders 15:11 15:14 3")
        return
    start_time, end_time, count_str = args
    if not is_valid_time(start_time) or not is_valid_time(end_time):
        await update.message.reply_text("Время должно быть в формате ЧЧ:ММ, например 15:11")
        return
    try:
        count = int(count_str)
    except Exception:
        await update.message.reply_text("Количество напоминаний должно быть числом")
        return
    if count < 1 or count > 10:
        await update.message.reply_text("Количество напоминаний — от 1 до 10")
        return
    update_user_settings(user.id, start_time, end_time, count)
    start_reminders(context.application, user.id, update.effective_chat.id)
    await update.message.reply_text(
        f"Тестовые напоминания установлены:\nНачало: {start_time}\nКонец: {end_time}\nКол-во: {count}",
        reply_markup=get_main_keyboard()
    )

async def dump_users(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # Только для админа!
    if update.effective_user.id != ADMIN_ID:
        await update.message.reply_text("Тільки для адміністратора.")
        return
    conn = get_db()
    cur = conn.cursor()
    cur.execute("SELECT * FROM users")
    rows = cur.fetchall()
    if not rows:
        await update.message.reply_text("Таблиця пуста.")
        return
    msg = ""
    for row in rows:
        msg += (
            f"ID: {row['user_id']}, Name: {row['name']}, Username: {row['username']}, "
            f"Pushups: {row['pushups_today']}, Day: {row['day']}, "
            f"Fails: {row['fails']}, Completed: {row['completed_time']}, "
            f"LastDate: {row['last_date']}\n"
        )
    # Ограничим максимум до 4000 символов для Telegram
    for i in range(0, len(msg), 4000):
        await update.message.reply_text(msg[i:i+4000])

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

    settings_conv = ConversationHandler(
        entry_points=[
            CommandHandler("settings", settings_entry),
            MessageHandler(filters.Regex(f"^{SETTINGS} Налаштування$"), settings_entry)
        ],
        states={
            SETTINGS_ASK_START: [MessageHandler(filters.TEXT & ~filters.COMMAND, settings_ask_start)],
            SETTINGS_INPUT_START: [MessageHandler(filters.TEXT & ~filters.COMMAND, settings_input_start)],
            SETTINGS_ASK_END: [MessageHandler(filters.TEXT & ~filters.COMMAND, settings_ask_end)],
            SETTINGS_INPUT_END: [MessageHandler(filters.TEXT & ~filters.COMMAND, settings_input_end)],
            SETTINGS_ASK_REMINDERS: [MessageHandler(filters.TEXT & ~filters.COMMAND, settings_ask_reminders)],
            SETTINGS_INPUT_REMINDERS: [MessageHandler(filters.TEXT & ~filters.COMMAND, settings_input_reminders)],
        },
        fallbacks=[],
    )

    application.add_handler(conv_handler)
    application.add_handler(settings_conv)
    application.add_handler(CommandHandler("addday", addday))
    application.add_handler(CommandHandler("settestreminders", settestreminders))
    application.add_handler(CommandHandler("reset", reset))
    application.add_handler(CommandHandler("status", status))
    application.add_handler(CommandHandler("add10", add10))
    application.add_handler(CommandHandler("add15", add15))
    application.add_handler(CommandHandler("add20", add20))
    application.add_handler(CommandHandler("add25", add25))
    application.add_handler(CommandHandler("add", add_custom))
    application.add_handler(CommandHandler("lobby", lobby))
    application.add_handler(MessageHandler(filters.Regex(f"^{LEADERBOARD}$"), lobby))
    application.add_handler(CommandHandler("dumpusers", dump_users))
    application.add_handler(MessageHandler(filters.Regex("^➖ Зменшити кількість$"), decrease_pushups))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_custom_pushups))
        
    logger.info("Bot started!")
    application.post_init = on_startup
    application.run_polling()

if __name__ == "__main__":
    main()
