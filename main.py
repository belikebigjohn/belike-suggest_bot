import telebot
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton
from config import TOKEN, ADMIN_IDS, CHANNEL_ID

#TOKEN = ""
#ADMIN_IDS = []
#CHANNEL_ID = -100

bot = telebot.TeleBot(TOKEN)

# храним предложки: message_id у админа -> (user_id, тип медиа, file_id)
pending_posts = {}


@bot.message_handler(commands=['start'])
def handle_start(message):
    bot.send_message(message.chat.id,
                     "Привет, есть что отправить в группу?\nБот анонимно отправит фото/видео в группу, не выдавая твою личность.")
    bot.send_message(message.chat.id, "Приступим?\nОтправь желаемое и добавь к нему текст, чтобы всё отправилось одним сообщением")

@bot.message_handler(content_types=['photo', 'video'])
def handle_user_submission(message):
    if not message.caption:
        bot.reply_to(message, "Добавь текст к фото или видео (одним сообщением)")
        return

    user = message.from_user
    username = user.username or f"id{user.id}"

    # определяем что прислали
    if message.photo:
        file_id = message.photo[-1].file_id
        media_type = "photo"
        send_method = bot.send_photo
    else:
        file_id = message.video.file_id
        media_type = "video"
        send_method = bot.send_video

    # кнопки
    markup = InlineKeyboardMarkup()
    markup.add(
        InlineKeyboardButton("✅", callback_data=f"approve_{user.id}"),
        InlineKeyboardButton("❌", callback_data=f"reject_{user.id}")
    )

    caption_for_admins = f"Предложка от @{username}\n\n{message.caption}"

    # рассылаем всем админам
    for admin_id in ADMIN_IDS:
        try:
            sent_message = send_method(
                admin_id,
                file_id,
                caption=caption_for_admins,
                reply_markup=markup
            )
            # запоминаем
            pending_posts[sent_message.message_id] = (user.id, media_type, file_id, message.caption)
        except Exception as e:
            print(f"Не удалось отправить админу {admin_id}: {e}")

    bot.reply_to(message, "Отправлено")


@bot.callback_query_handler(func=lambda query: True)
def handle_admin_decision(query):
    # сразу отвечаем телеграму, чтобы не блокировал обновления
    bot.answer_callback_query(query.id)

    if query.from_user.id not in ADMIN_IDS:
        return

    try:

        action, user_id_str = query.data.split("_")
        user_id = int(user_id_str)

    except:
        return

    # убираем кнопки с этого сообщения
    try:
        bot.edit_message_reply_markup(
            query.message.chat.id,
            query.message.message_id,
            reply_markup=None
        )
    except:
        pass



    # если пост уже обработан кем-то другим - выходим
    if query.message.message_id not in pending_posts:
        return

    # достаём данные
    stored_user_id, media_type, file_id, original_caption = (
        pending_posts.pop(query.message.message_id))

    # берём только текст пользователя
    post_text = original_caption.split("\n\n", 1)[1] \
        if "\n\n" in original_caption else original_caption

    if action == "approve":
        try:
            if media_type == "photo":
                bot.send_photo(CHANNEL_ID, file_id, caption=post_text)
            else:
                bot.send_video(CHANNEL_ID, file_id, caption=post_text)

            bot.send_message(stored_user_id, "✅ Опубликовано")
            print(f"✅ Опубликовано (админ {query.from_user.id} | {query.from_user.username})")
        except Exception as e:
            print(f"Ошибка публикации: {e}")

    elif action == "reject":
        bot.send_message(stored_user_id, "❌ Отклонено")
        print(f"❌ Отклонено (админ {query.from_user.id} | {query.from_user.username})")

print("Запуск бота...")
bot.polling()