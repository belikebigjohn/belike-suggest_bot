import telebot
import threading
from telebot import types
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton
from config import TOKEN, ADMIN_IDS, CHANNEL_ID

bot = telebot.TeleBot(TOKEN)

# храним пользователей, которые нажали /start
active_users = set()

# храним предложки: message_id у админа -> (user_id, тип медиа, media_data, caption)
pending_posts = {}
# храним все message_id одной предложки для удаления кнопок у всех админов
post_admin_messages = {}  # user_id -> [(admin_id, message_id), ...]

# ожидаемые медиа от пользователя: user_id -> {'type': 'photo'|'video'|'text', 'media': [...], 'caption': str}
pending_media = {}


@bot.message_handler(commands=['start'])
def handle_start(message):
    active_users.add(message.from_user.id)
    bot.send_message(message.chat.id,
                     "Привет, есть что отправить в группу?\nБот анонимно отправит фото/видео/текст в группу, не выдавая твою личность.")
    bot.send_message(message.chat.id, "Приступим?\nОтправь фото/видео с подписью или просто текст.")


@bot.message_handler(commands=['send'])
def handle_send_text(message):
    if message.from_user.id not in active_users:
        return
    bot.send_message(message.chat.id, "⌨️ Напиши текст, который хочешь опубликовать:")


def process_text_submission(message):
    """Обработка текстовых сообщений от активных пользователей"""
    if message.from_user.id not in active_users:
        return
    
    if not message.text or message.text.startswith('/'):
        return

    user = message.from_user
    username = user.username or f"id{user.id}"

    send_post(user, username, "text", None, message.text)


@bot.message_handler(content_types=['text'])
def handle_text_message(message):
    """Обработка текстовых сообщений от активных пользователей"""
    process_text_submission(message)


@bot.message_handler(content_types=['photo', 'video', 'document', 'audio'])
def handle_media_submission(message):
    """Обработка медиа - поддержка одиночных сообщений и альбомов"""
    if message.from_user.id not in active_users:
        return

    user = message.from_user
    username = user.username or f"id{user.id}"

    # Проверяем, является ли сообщение частью альбома
    if message.media_group_id:
        # Это часть альбома
        handle_album_media(message, user, username)
    else:
        # Одиночное медиа
        handle_single_media(message, user, username)


def handle_single_media(message, user, username):
    """Обработка одиночного медиа (фото/видео)"""
    if message.photo:
        file_id = message.photo[-1].file_id
        media_type = "photo"
        caption = message.caption or ""
    elif message.video:
        file_id = message.video.file_id
        media_type = "video"
        caption = message.caption or ""
    elif message.document:
        file_id = message.document.file_id
        media_type = "document"
        caption = message.caption or ""
    elif message.audio:
        file_id = message.audio.file_id
        media_type = "audio"
        caption = message.caption or ""
    else:
        return

    send_post(user, username, media_type, file_id, caption)


def handle_album_media(message, user, username):
    """Обработка альбома (несколько фото/видео)"""
    media_group_id = message.media_group_id
    
    # Инициализируем или добавляем в ожидающий альбом
    if media_group_id not in pending_media:
        pending_media[media_group_id] = {
            'user': user,
            'username': username,
            'media': [],
            'caption': message.caption or "",
            'chat_id': message.chat.id,
            'first_message_id': message.message_id
        }
        
    # Добавляем медиа
    if message.photo:
        file_id = message.photo[-1].file_id
        pending_media[media_group_id]['media'].append(('photo', file_id))
    elif message.video:
        file_id = message.video.file_id
        pending_media[media_group_id]['media'].append(('video', file_id))
    elif message.document:
        file_id = message.document.file_id
        pending_media[media_group_id]['media'].append(('document', file_id))
    elif message.audio:
        file_id = message.audio.file_id
        pending_media[media_group_id]['media'].append(('audio', file_id))
    
    # Запускаем таймер для отправки альбома через 2 секунды
    if media_group_id in pending_media:
        timer = threading.Timer(2.0, send_pending_album, args=[media_group_id])
        timer.daemon = True
        timer.start()


def send_pending_album(media_group_id):
    """Отправка ожидающего альбома"""
    if media_group_id not in pending_media:
        return
    
    album_data = pending_media.pop(media_group_id)
    try:
        bot.send_message(album_data['chat_id'], "⏳ Получаю медиа...", reply_to_message_id=album_data['first_message_id'])
    except:
        pass
    
    send_album_post(album_data['user'], album_data['username'], 
                   album_data['media'], album_data['caption'])


def send_post(user, username, media_type, file_id, caption):
    """Отправка одиночной предложки админам"""
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
            elif media_type == "photo":
                sent_message = bot.send_photo(admin_id, file_id, caption=caption_for_admins, reply_markup=markup)
            elif media_type == "video":
                sent_message = bot.send_video(admin_id, file_id, caption=caption_for_admins, reply_markup=markup)
            elif media_type == "document":
                sent_message = bot.send_document(admin_id, file_id, caption=caption_for_admins, reply_markup=markup)
            elif media_type == "audio":
                sent_message = bot.send_audio(admin_id, file_id, caption=caption_for_admins, reply_markup=markup)
            
            admin_message_ids.append((admin_id, sent_message.message_id))
            pending_posts[sent_message.message_id] = (user.id, media_type, file_id, caption)
        except Exception as e:
            print(f"Не удалось отправить админу {admin_id}: {e}")

    post_admin_messages[user.id] = admin_message_ids

    bot.send_message(user.id, "✅ Отправлено на модерацию\n\nДля новой отправки снова нажми /start")
    # Убираем пользователя из активных - для следующей отправки нужно снова нажать /start
    active_users.discard(user.id)


def send_album_post(user, username, media_list, caption):
    """Отправка альбома админам: альбом + сообщение с кнопками"""
    markup = InlineKeyboardMarkup()
    markup.add(
        InlineKeyboardButton("✅", callback_data=f"approve_{user.id}"),
        InlineKeyboardButton("❌", callback_data=f"reject_{user.id}")
    )

    caption_for_admins = f"Предложка от @{username}\n\n{caption}"

    admin_message_ids = []
    for admin_id in ADMIN_IDS:
        try:
            # Формируем MediaGroup
            media_group = []
            for i, (media_type, file_id) in enumerate(media_list):
                if i == 0:
                    if media_type == "photo":
                        media_group.append(types.InputMediaPhoto(file_id, caption=caption_for_admins))
                    elif media_type == "video":
                        media_group.append(types.InputMediaVideo(file_id, caption=caption_for_admins))
                    elif media_type == "document":
                        media_group.append(types.InputMediaDocument(file_id, caption=caption_for_admins))
                    elif media_type == "audio":
                        media_group.append(types.InputMediaAudio(file_id, caption=caption_for_admins))
                else:
                    if media_type == "photo":
                        media_group.append(types.InputMediaPhoto(file_id))
                    elif media_type == "video":
                        media_group.append(types.InputMediaVideo(file_id))
                    elif media_type == "document":
                        media_group.append(types.InputMediaDocument(file_id))
                    elif media_type == "audio":
                        media_group.append(types.InputMediaAudio(file_id))

            # 1. Отправляем альбом (без кнопок — API не поддерживает)
            sent_album = bot.send_media_group(admin_id, media_group)

            # 2. Сразу под ним — сообщение с кнопками
            btn_message = bot.send_message(
                admin_id,
                "Одобрить или отклонить?",
                reply_markup=markup
            )

            msg_ids = [(admin_id, msg.message_id) for msg in sent_album]
            msg_ids.append((admin_id, btn_message.message_id))
            admin_message_ids.extend(msg_ids)

            # Сохраняем: id сообщения с кнопками -> данные предложки
            pending_posts[btn_message.message_id] = (user.id, "album", media_list, caption)
        except Exception as e:
            print(f"Не удалось отправить альбом админу {admin_id}: {e}")

    post_admin_messages[user.id] = admin_message_ids

    bot.send_message(user.id, "✅ Отправлено на модерацию\n\nДля новой отправки снова нажми /start")
    active_users.discard(user.id)


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
    stored_user_id, media_type, media_data, original_caption = (
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
            if media_type == "album":
                # Публикация альбома ОДНИМ сообщением через MediaGroup
                media_list = media_data
                media_group = []
                for i, (item_type, file_id) in enumerate(media_list):
                    if i == 0:
                        # Первый элемент с подписью
                        if item_type == "photo":
                            media_group.append(types.InputMediaPhoto(file_id, caption=post_text))
                        elif item_type == "video":
                            media_group.append(types.InputMediaVideo(file_id, caption=post_text))
                        elif item_type == "document":
                            media_group.append(types.InputMediaDocument(file_id, caption=post_text))
                        elif item_type == "audio":
                            media_group.append(types.InputMediaAudio(file_id, caption=post_text))
                    else:
                        # Остальные элементы без подписи
                        if item_type == "photo":
                            media_group.append(types.InputMediaPhoto(file_id))
                        elif item_type == "video":
                            media_group.append(types.InputMediaVideo(file_id))
                        elif item_type == "document":
                            media_group.append(types.InputMediaDocument(file_id))
                        elif item_type == "audio":
                            media_group.append(types.InputMediaAudio(file_id))
                
                if media_group:
                    bot.send_media_group(CHANNEL_ID, media_group)
            elif media_type == "photo":
                bot.send_photo(CHANNEL_ID, media_data, caption=post_text)
            elif media_type == "video":
                bot.send_video(CHANNEL_ID, media_data, caption=post_text)
            elif media_type == "document":
                bot.send_document(CHANNEL_ID, media_data, caption=post_text)
            elif media_type == "audio":
                bot.send_audio(CHANNEL_ID, media_data, caption=post_text)
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