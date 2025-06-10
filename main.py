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
    add_user(
        user.id,
        context.user_data["name"],
        context.user_data["start_time"],
        context.user_data["end_time"],
        context.user_data["reminders"]
    )

    # Клавиатура с быстрыми кнопками и статусом
    keyboard = [
        [KeyboardButton("/add10"), KeyboardButton("/add15")],
        [KeyboardButton("/add20"), KeyboardButton("/add25")],
        [KeyboardButton("/add"), KeyboardButton("/status")]
    ]
    reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)

    await update.message.reply_text(
        f"{DEVIL} Приветствую в Devil's 100 challenge! Сегодня первый день челленджа, а значит ты должен сделать первые 100 отжиманий! Удачи! {CLOVER}",
        reply_markup=reply_markup
    )
    # Сразу же выводим /status
    await status(update, context)
    return ConversationHandler.END
