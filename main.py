import telebot
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton
from config import TOKEN, ADMIN_IDS, CHANNEL_ID

#TOKEN = ""
#ADMIN_IDS = []
#CHANNEL_ID = -100

bot = telebot.TeleBot(TOKEN)

# храним предложки: message_id у админа -> (user_id, тип медиа, file_id, caption)
pending_posts = {}
# храним все message_id одной предложки для удаления кнопок у всех админов
post_admin_messages = {}  # user_id -> [message_id1, message_id2, ...]


@bot.message_handler(commands=['start'])
def handle_start(message):
    bot.send_message(message.chat.id,
                     "Привет, есть что отправить в группу?\nБот анонимно отправит фото/видео/текст в группу, не выдавая твою личность.")
    bot.send_message(message.chat.id, "Приступим?\nОтправь фото/видео с подписью или просто текст.")

@bot.message_handler(content_types=['photo', 'video', 'text'])
def handle_user_submission(message):
    # если текст — проверяем что не команда
    if message.text and message.text.startswith('/'):
        return

    user = message.from_user
    username = user.username or f"id{user.id}"

    # определяем что прислали
    if message.photo:
        file_id = message.photo[-1].file_id
        media_type = "photo"
        send_method = bot.send_photo
        caption = message.caption
        if not caption:
            bot.reply_to(message, "Добавь текст к фото (одним сообщением)")
            return
    elif message.video:
        file_id = message.video.file_id
        media_type = "video"
        send_method = bot.send_video
        caption = message.caption
        if not caption:
            bot.reply_to(message, "Добавь текст к видео (одним сообщением)")
            return
    else:
        # только текст
        media_type = "text"
        file_id = None
        send_method = None
        caption = message.text

    # кнопки
    markup = InlineKeyboardMarkup()
    markup.add(
        InlineKeyboardButton("✅", callback_data=f"approve_{user.id}"),
        InlineKeyboardButton("❌", callback_data=f"reject_{user.id}")
    )

    caption_for_admins = f"Предложка от @{username}\n\n{caption}"

    # рассылаем всем админам
    admin_message_ids = []
    for admin_id in ADMIN_IDS:
        try:
            if media_type == "text":
                sent_message = bot.send_message(
                    admin_id,
                    caption_for_admins,
                    reply_markup=markup
                )
            else:
                sent_message = send_method(
                    admin_id,
                    file_id,
                    caption=caption_for_admins,
                    reply_markup=markup
                )
            admin_message_ids.append((admin_id, sent_message.message_id))
            # запоминаем
            pending_posts[sent_message.message_id] = (user.id, media_type, file_id, caption)
        except Exception as e:
            print(f"Не удалось отправить админу {admin_id}: {e}")

    # сохраняем связь user_id -> message_ids для удаления кнопок у всех
    post_admin_messages[user.id] = admin_message_ids

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

    # если пост уже обработан кем-то другим - выходим
    if query.message.message_id not in pending_posts:
        return

    # достаём данные
    stored_user_id, media_type, file_id, original_caption = (
        pending_posts.pop(query.message.message_id))

    # убираем кнопки у ВСЕХ сообщений этой предложки
    if stored_user_id in post_admin_messages:
        for admin_id, msg_id in post_admin_messages.pop(stored_user_id, []):
            try:
                bot.edit_message_reply_markup(admin_id, msg_id, reply_markup=None)
            except:
                pass

    # берём только текст пользователя
    post_text = original_caption

    if action == "approve":
        try:
            if media_type == "photo":
                bot.send_photo(CHANNEL_ID, file_id, caption=post_text)
            elif media_type == "video":
                bot.send_video(CHANNEL_ID, file_id, caption=post_text)
            else:
                bot.send_message(CHANNEL_ID, post_text)

            bot.send_message(stored_user_id, "✅ Опубликовано")
            print(f"✅ Опубликовано (админ {query.from_user.id} | {query.from_user.username})")
        except Exception as e:
            print(f"Ошибка публикации: {e}")

    elif action == "reject":
        bot.send_message(stored_user_id, "❌ Отклонено")
        print(f"❌ Отклонено (админ {query.from_user.id} | {query.from_user.username})")

print("Запуск бота...")
bot.polling()