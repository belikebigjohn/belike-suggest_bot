import telebot
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton
from  config import TOKEN, ADMIN_ID, CHANNEL_ID

#TOKEN = ""
#ADMIN_ID =
#CHANNEL_ID =

bot = telebot.TeleBot(TOKEN)


@bot.message_handler(content_types=['photo', 'video'])
def handle_media(message):
    if not message.caption:
        bot.reply_to(message, "Добавь текст к фото или видео")
        return

    user = message.from_user
    username = f"@{user.username}"

    # опред тип
    if message.photo:
        media_id = message.photo[-1].file_id
        send_func_admin = bot.send_photo


    else:  # video
        media_id = message.video.file_id
        send_func_admin = bot.send_video


#publish reject

    # кнопки
    markup = InlineKeyboardMarkup()
    markup.add(
        InlineKeyboardButton("✅", callback_data=f"pub_{user.id}"),
        InlineKeyboardButton("❌", callback_data=f"rej_{user.id}")
    )

    # отправляем админу
    caption_admin = f"Предложка от {username}\n\n{message.caption}"

    try:

        send_func_admin(ADMIN_ID,media_id, caption=caption_admin, reply_markup=markup)
        bot.reply_to(message, "Отправлено")

    except Exception as e:
        bot.reply_to(message, "Не получилось отправить админу/handle_media()")
        print(e)


@bot.callback_query_handler(func=lambda call: True)
def callback_handler(call):
    if call.from_user.id != ADMIN_ID:
        bot.answer_callback_query(call.id, "Нет прав")
        return

    action, user_id = call.data.split("_")
    user_id = int(user_id)

    # убираем кнопки
    try:
        bot.edit_message_reply_markup(chat_id=call.message.chat.id,
                                      message_id=call.message.message_id,
                                      reply_markup=None)
    except:
        pass

    if action == "pub":
        try:
            # берём чистый текст пользователя (всё после первой пустой строки)
            if call.message.caption and "\n\n" in call.message.caption:
                clean_text = call.message.caption.split("\n\n", 1)[1]
            else:
                clean_text = call.message.caption or ""

            # опред тип
            if call.message.photo:
                media_id = call.message.photo[-1].file_id
                send_func = bot.send_photo
            else:
                media_id = call.message.video.file_id
                send_func = bot.send_video

            send_func(CHANNEL_ID, media_id, caption=clean_text)

            bot.send_message(user_id, "✅ Опубликовално!")
            bot.answer_callback_query(call.id, "Опубликовано")
        except Exception as e:
            bot.answer_callback_query(call.id, f"Ошибка: {str(e)}", show_alert=True)
            print(e)

    elif action == "rej":
        bot.send_message(user_id, "❌ Отклонено")
        bot.answer_callback_query(call.id, "Отклонено")


bot.polling()