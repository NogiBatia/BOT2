import os
import logging
import sqlite3
import telebot
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton, ReplyKeyboardMarkup, KeyboardButton
from flask import Flask
from threading import Thread

# Веб-сервер для здоровья приложения на Railway
app = Flask('')

@app.route('/')
def home():
    return "🤖 NFT Marketplace Bot is running!"

def run():
    app.run(host='0.0.0.0', port=8080)

def keep_alive():
    t = Thread(target=run)
    t.start()

# Запускаем веб-сервер
keep_alive()

# Настройка логирования
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Токен бота из переменных окружения Railway
BOT_TOKEN = os.environ.get("BOT_TOKEN")

# ID администратора (ваш ID)
ADMIN_ID = 1343332712
ADMINS = [ADMIN_ID]  # Список админов

# Канал для обязательной подписки
REQUIRED_CHANNEL = "@GetGemsNFTseller"
CHANNEL_ID = "@GetGemsNFTseller"  # ID канала

# Создаем бота
bot = telebot.TeleBot(BOT_TOKEN)

# Инициализация базы данных
def init_db():
    conn = sqlite3.connect('nft_market.db', check_same_thread=False)
    cursor = conn.cursor()
    
    tables = {
        'user_states': '''
            CREATE TABLE IF NOT EXISTS user_states (
                user_id INTEGER PRIMARY KEY,
                state TEXT,
                state_data TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''',
        'users': '''
            CREATE TABLE IF NOT EXISTS users (
                user_id INTEGER PRIMARY KEY,
                username TEXT,
                full_name TEXT,
                rating_seller REAL DEFAULT 0,
                rating_buyer REAL DEFAULT 0,
                total_sales INTEGER DEFAULT 0,
                total_purchases INTEGER DEFAULT 0,
                successful_sales INTEGER DEFAULT 0,
                successful_purchases INTEGER DEFAULT 0,
                failed_sales INTEGER DEFAULT 0,
                failed_purchases INTEGER DEFAULT 0,
                balance REAL DEFAULT 0,
                is_banned BOOLEAN DEFAULT FALSE,
                is_admin BOOLEAN DEFAULT FALSE,
                has_subscribed BOOLEAN DEFAULT FALSE
            )
        ''',
        'slots': '''
            CREATE TABLE IF NOT EXISTS slots (
                slot_id INTEGER PRIMARY KEY AUTOINCREMENT,
                seller_id INTEGER,
                nft_photo TEXT,
                description TEXT,
                price_rub REAL,
                contact_info TEXT,
                is_active BOOLEAN DEFAULT TRUE,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (seller_id) REFERENCES users (user_id)
            )
        ''',
        'purchases': '''
            CREATE TABLE IF NOT EXISTS purchases (
                purchase_id INTEGER PRIMARY KEY AUTOINCREMENT,
                slot_id INTEGER,
                buyer_id INTEGER,
                seller_id INTEGER,
                amount REAL,
                status TEXT DEFAULT 'pending',
                nft_sent BOOLEAN DEFAULT FALSE,
                nft_received BOOLEAN DEFAULT FALSE,
                buyer_rated BOOLEAN DEFAULT FALSE,
                seller_rated BOOLEAN DEFAULT FALSE,
                buyer_rating INTEGER DEFAULT 0,
                seller_rating INTEGER DEFAULT 0,
                buyer_review TEXT,
                seller_review TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (slot_id) REFERENCES slots (slot_id),
                FOREIGN KEY (buyer_id) REFERENCES users (user_id),
                FOREIGN KEY (seller_id) REFERENCES users (user_id)
            )
        ''',
        'reviews': '''
            CREATE TABLE IF NOT EXISTS reviews (
                review_id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                reviewer_id INTEGER,
                review_type TEXT,
                rating INTEGER,
                review_text TEXT,
                purchase_id INTEGER,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users (user_id),
                FOREIGN KEY (reviewer_id) REFERENCES users (user_id),
                FOREIGN KEY (purchase_id) REFERENCES purchases (purchase_id)
            )
        ''',
        'transactions': '''
            CREATE TABLE IF NOT EXISTS transactions (
                transaction_id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                amount REAL,
                type TEXT,
                description TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users (user_id)
            )
        ''',
        'support_tickets': '''
            CREATE TABLE IF NOT EXISTS support_tickets (
                ticket_id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                message TEXT,
                admin_response TEXT,
                status TEXT DEFAULT 'open',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users (user_id)
            )
        ''',
        'withdraw_requests': '''
            CREATE TABLE IF NOT EXISTS withdraw_requests (
                withdraw_id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                amount REAL,
                card_number TEXT,
                status TEXT DEFAULT 'pending',
                admin_comment TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users (user_id)
            )
        ''',
        'promocodes': '''
            CREATE TABLE IF NOT EXISTS promocodes (
                promocode_id INTEGER PRIMARY KEY AUTOINCREMENT,
                code TEXT UNIQUE,
                amount REAL,
                max_activations INTEGER,
                current_activations INTEGER DEFAULT 0,
                created_by INTEGER,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (created_by) REFERENCES users (user_id)
            )
        ''',
        'promocode_activations': '''
            CREATE TABLE IF NOT EXISTS promocode_activations (
                activation_id INTEGER PRIMARY KEY AUTOINCREMENT,
                promocode_id INTEGER,
                user_id INTEGER,
                activated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (promocode_id) REFERENCES promocodes (promocode_id),
                FOREIGN KEY (user_id) REFERENCES users (user_id)
            )
        '''
    }
    
    for table_name, table_sql in tables.items():
        cursor.execute(table_sql)
    
    # Добавляем основного админа если его нет
    cursor.execute('SELECT is_admin FROM users WHERE user_id = ?', (ADMIN_ID,))
    admin_exists = cursor.fetchone()
    if not admin_exists:
        cursor.execute('INSERT OR REPLACE INTO users (user_id, username, full_name, is_admin) VALUES (?, ?, ?, ?)',
                     (ADMIN_ID, "Admin", "Administrator", True))
    
    conn.commit()
    conn.close()
    logger.info("✅ База данных инициализирована")

# Функция проверки подписки на канал
def check_subscription(user_id):
    try:
        chat_member = bot.get_chat_member(CHANNEL_ID, user_id)
        return chat_member.status in ['member', 'administrator', 'creator']
    except Exception as e:
        logger.error(f"Error checking subscription: {e}")
        return False

# Функция для показа сообщения о необходимости подписки
def show_subscription_required(chat_id):
    keyboard = InlineKeyboardMarkup()
    keyboard.add(InlineKeyboardButton("📢 Подписаться на канал", url=f"https://t.me/{REQUIRED_CHANNEL[1:]}"))
    keyboard.add(InlineKeyboardButton("✅ Я подписался", callback_data="check_subscription"))
    
    bot.send_message(
        chat_id,
        f"📢 Для использования бота необходимо подписаться на наш канал:\n{REQUIRED_CHANNEL}\n\n"
        f"После подписки нажмите кнопку '✅ Я подписался'",
        reply_markup=keyboard
    )

# Функции для работы с состояниями
def set_user_state(user_id, state, state_data=None):
    conn = sqlite3.connect('nft_market.db', check_same_thread=False)
    cursor = conn.cursor()
    
    if state_data:
        cursor.execute('REPLACE INTO user_states (user_id, state, state_data) VALUES (?, ?, ?)', 
                      (user_id, state, state_data))
    else:
        cursor.execute('REPLACE INTO user_states (user_id, state) VALUES (?, ?)', 
                      (user_id, state))
    
    conn.commit()
    conn.close()

def get_user_state(user_id):
    conn = sqlite3.connect('nft_market.db', check_same_thread=False)
    cursor = conn.cursor()
    
    cursor.execute('SELECT state, state_data FROM user_states WHERE user_id = ?', (user_id,))
    result = cursor.fetchone()
    conn.close()
    
    if result:
        return result[0], result[1]
    return None, None

def clear_user_state(user_id):
    conn = sqlite3.connect('nft_market.db', check_same_thread=False)
    cursor = conn.cursor()
    
    cursor.execute('DELETE FROM user_states WHERE user_id = ?', (user_id,))
    conn.commit()
    conn.close()

# Основные функции
def get_or_create_user(user_id, username, full_name=None):
    conn = sqlite3.connect('nft_market.db', check_same_thread=False)
    cursor = conn.cursor()
    
    cursor.execute('SELECT * FROM users WHERE user_id = ?', (user_id,))
    user = cursor.fetchone()
    
    if not user:
        cursor.execute(
            'INSERT INTO users (user_id, username, full_name, balance, is_banned, is_admin, has_subscribed) VALUES (?, ?, ?, ?, ?, ?, ?)',
            (user_id, username or "Не указан", full_name or "", 0, False, False, False)
        )
        conn.commit()
        cursor.execute('SELECT * FROM users WHERE user_id = ?', (user_id,))
        user = cursor.fetchone()
    elif full_name and (not user[2] or user[2] != full_name):
        cursor.execute('UPDATE users SET full_name = ? WHERE user_id = ?', (full_name, user_id))
        conn.commit()
    
    conn.close()
    return user

def update_user_subscription(user_id, status):
    conn = sqlite3.connect('nft_market.db', check_same_thread=False)
    cursor = conn.cursor()
    cursor.execute('UPDATE users SET has_subscribed = ? WHERE user_id = ?', (status, user_id))
    conn.commit()
    conn.close()

def is_user_banned(user_id):
    conn = sqlite3.connect('nft_market.db', check_same_thread=False)
    cursor = conn.cursor()
    try:
        cursor.execute('SELECT is_banned FROM users WHERE user_id = ?', (user_id,))
        result = cursor.fetchone()
        conn.close()
        return result[0] if result else False
    except sqlite3.OperationalError:
        conn.close()
        return False

def is_user_admin(user_id):
    conn = sqlite3.connect('nft_market.db', check_same_thread=False)
    cursor = conn.cursor()
    try:
        cursor.execute('SELECT is_admin FROM users WHERE user_id = ?', (user_id,))
        result = cursor.fetchone()
        conn.close()
        return result[0] if result else False
    except sqlite3.OperationalError:
        conn.close()
        return False

def has_user_subscribed(user_id):
    conn = sqlite3.connect('nft_market.db', check_same_thread=False)
    cursor = conn.cursor()
    try:
        cursor.execute('SELECT has_subscribed FROM users WHERE user_id = ?', (user_id,))
        result = cursor.fetchone()
        conn.close()
        return result[0] if result else False
    except sqlite3.OperationalError:
        conn.close()
        return False

def update_global_admins():
    global ADMINS
    conn = sqlite3.connect('nft_market.db', check_same_thread=False)
    cursor = conn.cursor()
    cursor.execute('SELECT user_id FROM users WHERE is_admin = TRUE')
    admins = cursor.fetchall()
    ADMINS = [admin[0] for admin in admins]
    conn.close()

# Функции форматирования чисел
def format_balance(balance):
    """Форматирует баланс без копеек"""
    return f"{int(balance)}"

def format_rating(rating):
    """Форматирует рейтинг без лишних нулей"""
    if rating == 0:
        return "0"
    elif rating == int(rating):
        return f"{int(rating)}"
    else:
        return f"{rating:.1f}".rstrip('0').rstrip('.')

# Функция для получения username (админы показываются как обычные пользователи)
def get_user_display(user_id, username):
    """Возвращает username для отображения (админы показываются как обычные пользователи)"""
    return username or "Не указан"

# Функция проверки доступа (подписка + бан)
def check_access(user_id):
    """Проверяет доступ пользователя к функциям бота"""
    if is_user_banned(user_id):
        return False, "❌ Вы забанены и не можете использовать бота."
    
    if not is_user_admin(user_id) and not check_subscription(user_id):
        return False, "subscribe_required"
    
    return True, "access_granted"

# КОМАНДЫ
@bot.message_handler(commands=['start'])
def start(message):
    user = message.from_user
    get_or_create_user(user.id, user.username, f"{user.first_name or ''} {user.last_name or ''}".strip())
    update_global_admins()
    
    # Проверяем доступ
    access, message_text = check_access(user.id)
    if not access:
        if message_text == "subscribe_required":
            show_subscription_required(message.chat.id)
        else:
            bot.send_message(message.chat.id, message_text)
        return
        
    show_main_menu(message.chat.id, "Добро пожаловать в NFT Marketplace! 🎨\n\nЗдесь вы можете покупать и продавать NFT подарки.\nВыберите действие:")

@bot.message_handler(commands=['admin'])
def admin_command(message):
    if not is_user_admin(message.from_user.id):
        bot.send_message(message.chat.id, "❌ У вас нет прав доступа")
        return
    
    show_admin_menu(message.chat.id)

@bot.message_handler(commands=['help'])
def help_command(message):
    help_text = """
🤖 Доступные команды:

/start - Главное меню
/help - Помощь
/profile - Мой профиль
/mynft - Мои NFT

Для админа:
/admin - Админ панель
    """
    bot.send_message(message.chat.id, help_text)

@bot.message_handler(commands=['profile'])
def profile_command(message):
    show_profile_text(message)

@bot.message_handler(commands=['mynft'])
def mynft_command(message):
    show_my_nft_text(message)

# ОБРАБОТЧИК ТЕКСТОВЫХ СООБЩЕНИЙ
@bot.message_handler(content_types=['text'])
def handle_text(message):
    user_id = message.from_user.id
    text = message.text
    
    # Сначала проверяем, не является ли текст командой меню
    menu_commands = [
        "🎁 Выставить NFT", "🔍 Найти слоты", "📊 Мой профиль", "🛒 Мои NFT", 
        "📞 Поддержка", "⬅️ Главное меню", "📊 Статистика", "📞 Тикеты", 
        "👥 Пользователи", "💳 Управление балансом", "💰 Заявки на вывод", 
        "🎁 Промокоды", "📢 Рассылка", "👑 Управление админами"
    ]
    
    if text in menu_commands:
        # Если это команда меню - очищаем состояние и выполняем команду
        clear_user_state(user_id)
        handle_menu_commands(message, text)
        return
    
    # ВТОРОЕ - проверяем состояние пользователя
    state, state_data = get_user_state(user_id)
    if state:
        # Если у пользователя есть состояние, обрабатываем как ввод данных
        handle_user_state(message, state, state_data)
        return
    
    # ТРЕТЬЕ - проверяем бан
    if is_user_banned(user_id):
        bot.send_message(message.chat.id, "❌ Вы забанены и не можете использовать бота.")
        return
    
    # ЧЕТВЕРТОЕ - проверяем доступ для основных команд
    access, message_text = check_access(user_id)
    if not access:
        if message_text == "subscribe_required":
            show_subscription_required(message.chat.id)
        else:
            bot.send_message(message.chat.id, message_text)
        return
    
    # Если не команда меню, нет состояния и доступ есть - показываем сообщение
    bot.send_message(message.chat.id, "Используйте кнопки меню для навигации")

def handle_menu_commands(message, text):
    """Обработка команд главного меню"""
    # Проверяем доступ для команд меню
    access, message_text = check_access(message.from_user.id)
    if not access:
        if message_text == "subscribe_required":
            show_subscription_required(message.chat.id)
        else:
            bot.send_message(message.chat.id, message_text)
        return
    
    if text == "🎁 Выставить NFT":
        create_slot_start_text(message)
    elif text == "🔍 Найти слоты":
        find_slots_text(message)
    elif text == "📊 Мой профиль":
        show_profile_text(message)
    elif text == "🛒 Мои NFT":
        show_my_nft_text(message)
    elif text == "📞 Поддержка":
        support_start_text(message)
    elif text == "⬅️ Главное меню":
        show_main_menu(message.chat.id, "Главное меню:")
    
    # Админские команды
    elif is_user_admin(message.from_user.id):
        if text == "📊 Статистика":
            show_stats(message)
        elif text == "📞 Тикеты":
            show_tickets(message)
        elif text == "👥 Пользователи":
            show_users_management(message)
        elif text == "💳 Управление балансом":
            show_balance_management(message)
        elif text == "💰 Заявки на вывод":
            show_withdraw_requests(message)
        elif text == "🎁 Промокоды":
            show_promocodes_management(message)
        elif text == "📢 Рассылка":
            show_broadcast_management(message)
        elif text == "👑 Управление админами":
            show_admin_management(message)

# ОБРАБОТКА СОСТОЯНИЙ ПОЛЬЗОВАТЕЛЯ
def handle_user_state(message, state, state_data):
    user_id = message.from_user.id
    text = message.text
    
    # Сначала проверяем, не является ли текст командой меню
    menu_commands = [
        "🎁 Выставить NFT", "🔍 Найти слоты", "📊 Мой профиль", "🛒 Мои NFT", 
        "📞 Поддержка", "⬅️ Главное меню", "📊 Статистика", "📞 Тикеты", 
        "👥 Пользователи", "💳 Управление балансом", "💰 Заявки на вывод", 
        "🎁 Промокоды", "📢 Рассылка", "👑 Управление админами"
    ]
    
    if text in menu_commands:
        # Если это команда меню - очищаем состояние и выполняем команду
        clear_user_state(user_id)
        handle_menu_commands(message, text)
        return
    
    # Для состояний ввода проверяем только бан (не подписку)
    if is_user_banned(user_id):
        bot.send_message(message.chat.id, "❌ Вы забанены и не можете использовать бота.")
        clear_user_state(user_id)
        return
    
    # Обрабатываем состояния
    if state == "waiting_promocode":
        process_promocode_activation(message, user_id)
    elif state == "waiting_nft_photo":
        process_nft_photo(message)
    elif state == "waiting_nft_description":
        user_data = {'photo_id': state_data} if state_data else {}
        process_description(message, user_data)
    elif state == "waiting_nft_price":
        user_data = {'photo_id': state_data.split('|')[0], 'description': state_data.split('|')[1]} if state_data else {}
        process_price(message, user_data)
    elif state == "waiting_nft_contact":
        user_data = {'photo_id': state_data.split('|')[0], 'description': state_data.split('|')[1], 'price': state_data.split('|')[2]} if state_data else {}
        process_contact_info(message, user_data)
    elif state == "waiting_withdraw_card":
        process_withdraw_card(message, float(state_data), user_id)
    elif state == "waiting_withdraw_amount":
        parts = state_data.split('|')
        balance = float(parts[0])
        card_number = parts[1]
        process_withdraw_amount(message, balance, user_id, card_number)
    elif state == "waiting_name_change":
        process_name_change(message, user_id)
    elif state == "waiting_support_message":
        process_support_message(message)
    elif state == "waiting_admin_balance":
        if is_user_admin(user_id):
            process_admin_balance(message)
    elif state == "waiting_admin_ban":
        if is_user_admin(user_id):
            process_admin_ban(message)
    elif state == "waiting_admin_unban":
        if is_user_admin(user_id):
            process_admin_unban(message)
    elif state == "waiting_reject_reason":
        if is_user_admin(user_id):
            withdraw_id = state_data
            process_reject_reason(message, withdraw_id)
    elif state == "waiting_ticket_reply":
        if is_user_admin(user_id):
            ticket_id = state_data
            process_ticket_reply(message, ticket_id)
    elif state == "waiting_transfer_user":
        process_transfer_user(message, user_id)
    elif state == "waiting_transfer_amount":
        parts = state_data.split('|')
        target_user_id = int(parts[0])
        process_transfer_amount(message, user_id, target_user_id)
    elif state == "waiting_rating":
        parts = state_data.split('|')
        purchase_id = int(parts[0])
        rate_type = parts[1]
        rating = int(parts[2])
        process_review(message, purchase_id, rate_type, rating)
    elif state == "waiting_add_admin":
        if is_user_admin(user_id):
            process_add_admin(message)
    elif state == "waiting_remove_admin":
        if is_user_admin(user_id):
            process_remove_admin(message)
    elif state == "waiting_promocode_name":
        if is_user_admin(user_id):
            process_promocode_name(message)
    elif state == "waiting_promocode_amount":
        if is_user_admin(user_id):
            parts = state_data.split('|')
            code = parts[0]
            process_promocode_amount(message, code)
    elif state == "waiting_promocode_activations":
        if is_user_admin(user_id):
            parts = state_data.split('|')
            code = parts[0]
            amount = float(parts[1])
            process_promocode_activations(message, code, amount)
    elif state == "waiting_broadcast_message":
        if is_user_admin(user_id):
            process_broadcast_message(message)
    else:
        # Если состояние неизвестно - очищаем его
        clear_user_state(user_id)
        bot.send_message(message.chat.id, "❌ Неизвестное состояние. Возврат в главное меню.")
        show_main_menu(message.chat.id, "Главное меню:")

# ОСНОВНЫЕ ФУНКЦИИ МЕНЮ
def show_main_menu(chat_id, text):
    keyboard = ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    keyboard.add(
        KeyboardButton("🎁 Выставить NFT"),
        KeyboardButton("🔍 Найти слоты"),
        KeyboardButton("📊 Мой профиль"),
        KeyboardButton("🛒 Мои NFT"),
        KeyboardButton("📞 Поддержка")
    )
    
    bot.send_message(chat_id, text, reply_markup=keyboard)

def show_admin_menu(chat_id):
    keyboard = ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    keyboard.add(
        KeyboardButton("📊 Статистика"),
        KeyboardButton("📞 Тикеты"),
        KeyboardButton("👥 Пользователи"),
        KeyboardButton("💳 Управление балансом"),
        KeyboardButton("💰 Заявки на вывод"),
        KeyboardButton("🎁 Промокоды"),
        KeyboardButton("📢 Рассылка"),
        KeyboardButton("👑 Управление админами"),
        KeyboardButton("⬅️ Главное меню")
    )
    
    bot.send_message(chat_id, "👨‍💼 Админ панель\n\nВыберите действие:", reply_markup=keyboard)

# ПОКАЗАТЬ ПРОФИЛЬ
def show_profile_text(message):
    user_id = message.from_user.id
    conn = sqlite3.connect('nft_market.db', check_same_thread=False)
    cursor = conn.cursor()
    
    cursor.execute('SELECT * FROM users WHERE user_id = ?', (user_id,))
    user = cursor.fetchone()
    
    # Получаем статистику сделок
    cursor.execute('SELECT COUNT(*) FROM purchases WHERE (buyer_id = ? OR seller_id = ?) AND status = "completed"', (user_id, user_id))
    successful_deals = cursor.fetchone()[0]
    
    cursor.execute('SELECT COUNT(*) FROM purchases WHERE (buyer_id = ? OR seller_id = ?) AND status = "pending"', (user_id, user_id))
    pending_deals = cursor.fetchone()[0]
    
    conn.close()

    if user:
        user_id, username, full_name, rating_seller, rating_buyer, total_sales, total_purchases, successful_sales, successful_purchases, failed_sales, failed_purchases, balance, is_banned, is_admin, has_subscribed = user
        
        # Используем новую функцию для отображения username
        display_username = get_user_display(user_id, username)
        
        message_text = (
            f"📊 Ваш профиль\n\n"
            f"👤 ID: {user_id}\n"
            f"📛 Имя: {full_name or 'Не указано'}\n"
            f"🔗 Username: @{display_username}\n"
            f"💰 Баланс: {format_balance(balance)} руб\n"
            f"⭐ Рейтинг продавца: {format_rating(rating_seller)}/5\n"
            f"⭐ Рейтинг покупателя: {format_rating(rating_buyer)}/5\n"
            f"🛒 Продано NFT: {total_sales}\n"
            f"🛍️ Куплено NFT: {total_purchases}\n"
            f"✅ Успешных сделок: {successful_deals}\n"
            f"⏳ Ожидающих сделок: {pending_deals}"
        )
        
        keyboard = InlineKeyboardMarkup()
        keyboard.add(
            InlineKeyboardButton("✏️ Изменить имя", callback_data="change_name"),
            InlineKeyboardButton("💰 Вывести средства", callback_data="withdraw_balance")
        )
        keyboard.add(
            InlineKeyboardButton("🎁 Отправить другу", callback_data="transfer_money"),
            InlineKeyboardButton("📊 Мои отзывы", callback_data="my_reviews"),
            InlineKeyboardButton("🎁 Промокод", callback_data="activate_promocode")
        )
        keyboard.add(InlineKeyboardButton("⬅️ Назад", callback_data="back_to_main"))
        
        bot.send_message(message.chat.id, message_text, reply_markup=keyboard)
    else:
        bot.send_message(message.chat.id, "❌ Ошибка загрузки профиля")

# СОЗДАНИЕ NFT
def create_slot_start_text(message):
    set_user_state(message.from_user.id, "waiting_nft_photo")
    keyboard = InlineKeyboardMarkup()
    keyboard.add(InlineKeyboardButton("⬅️ Назад", callback_data="back_to_main"))
    
    bot.send_message(
        message.chat.id,
        "🎨 Создание нового слота для NFT\n\nПришлите ФОТО NFT:",
        reply_markup=keyboard
    )

@bot.message_handler(content_types=['photo'])
def handle_photo(message):
    state, state_data = get_user_state(message.from_user.id)
    
    if state == "waiting_nft_photo":
        process_nft_photo(message)

def process_nft_photo(message):
    if not message.photo:
        bot.send_message(message.chat.id, "❌ Пожалуйста, пришлите фото. Попробуйте снова:")
        return
    
    photo_id = message.photo[-1].file_id
    set_user_state(message.from_user.id, "waiting_nft_description", photo_id)
    bot.send_message(message.chat.id, "📝 Теперь введите описание NFT:")

def process_description(message, user_data):
    description = message.text
    photo_id = user_data.get('photo_id', '')
    set_user_state(message.from_user.id, "waiting_nft_price", f"{photo_id}|{description}")
    bot.send_message(message.chat.id, "💰 Введите цену в рублях:")

def process_price(message, user_data):
    try:
        price = float(message.text)
        if price <= 0:
            bot.send_message(message.chat.id, "❌ Цена должна быть больше 0.")
            return
            
        photo_id = user_data.get('photo_id', '')
        description = user_data.get('description', '')
        set_user_state(message.from_user.id, "waiting_nft_contact", f"{photo_id}|{description}|{price}")
        bot.send_message(message.chat.id, "📞 Введите контактные данные для связи (например, ваш username в Telegram):")
        
    except ValueError:
        bot.send_message(message.chat.id, "❌ Пожалуйста, введите корректную цену (число):")

def process_contact_info(message, user_data):
    contact_info = message.text
    if len(contact_info) < 3:
        bot.send_message(message.chat.id, "❌ Контактные данные слишком короткие")
        return
        
    user_id = message.from_user.id
    photo_id = user_data.get('photo_id', '')
    description = user_data.get('description', '')
    price = user_data.get('price', '')
    
    conn = sqlite3.connect('nft_market.db', check_same_thread=False)
    cursor = conn.cursor()
    
    cursor.execute('''
        INSERT INTO slots (seller_id, nft_photo, description, price_rub, contact_info)
        VALUES (?, ?, ?, ?, ?)
    ''', (user_id, photo_id, description, price, contact_info))
    
    conn.commit()
    conn.close()
    
    clear_user_state(user_id)
    bot.send_message(message.chat.id, "✅ Слот успешно создан!")
    show_main_menu(message.chat.id, "Главное меню:")

# ПОИСК СЛОТОВ
def find_slots_text(message):
    conn = sqlite3.connect('nft_market.db', check_same_thread=False)
    cursor = conn.cursor()
    
    cursor.execute('''
        SELECT s.slot_id, s.description, s.price_rub, u.username, u.user_id
        FROM slots s 
        JOIN users u ON s.seller_id = u.user_id 
        WHERE s.is_active = TRUE AND s.seller_id != ?
    ''', (message.from_user.id,))
    slots = cursor.fetchall()
    conn.close()
    
    if not slots:
        bot.send_message(message.chat.id, "🔍 Активных слотов не найдено")
        return
    
    keyboard = InlineKeyboardMarkup()
    for slot in slots:
        slot_id, description, price, username, seller_id = slot
        btn_text = f"🎁 {description[:20]}... - {format_balance(price)} руб"
        keyboard.add(InlineKeyboardButton(btn_text, callback_data=f"slot_{slot_id}"))
    
    keyboard.add(InlineKeyboardButton("⬅️ Назад", callback_data="back_to_main"))
    
    bot.send_message(message.chat.id, "🔍 Доступные слоты:", reply_markup=keyboard)

# ФУНКЦИЯ ДЛЯ ПОКАЗА ДЕТАЛЕЙ СЛОТА
def show_slot_details(call, slot_id):
    conn = sqlite3.connect('nft_market.db', check_same_thread=False)
    cursor = conn.cursor()
    
    cursor.execute('''
        SELECT s.slot_id, s.nft_photo, s.description, s.price_rub, s.contact_info, 
               u.username, u.user_id, u.rating_seller
        FROM slots s 
        JOIN users u ON s.seller_id = u.user_id 
        WHERE s.slot_id = ? AND s.is_active = TRUE
    ''', (slot_id,))
    slot = cursor.fetchone()
    conn.close()
    
    if not slot:
        bot.answer_callback_query(call.id, "❌ Слот не найден")
        return
    
    slot_id, nft_photo, description, price, contact_info, username, seller_id, rating_seller = slot
    
    # Используем новую функцию для отображения username
    display_username = get_user_display(seller_id, username)
    
    message_text = (
        f"🎁 Детали слота\n\n"
        f"📝 Описание: {description}\n"
        f"💰 Цена: {format_balance(price)} руб\n"
        f"👤 Продавец: @{display_username}\n"
        f"⭐ Рейтинг продавца: {format_rating(rating_seller)}/5\n"
    )
    
    keyboard = InlineKeyboardMarkup()
    keyboard.add(
        InlineKeyboardButton("💰 Купить", callback_data=f"buy_{slot_id}"),
        InlineKeyboardButton("📞 Контакты", callback_data=f"contact_{slot_id}")
    )
    keyboard.add(
        InlineKeyboardButton("⭐ Отзывы о продавце", callback_data=f"reviews_{seller_id}_seller")
    )
    keyboard.add(InlineKeyboardButton("⬅️ Назад", callback_data="back_to_slots"))
    
    try:
        bot.send_photo(call.message.chat.id, nft_photo, caption=message_text, reply_markup=keyboard)
    except:
        bot.send_message(call.message.chat.id, message_text, reply_markup=keyboard)

# ФУНКЦИЯ ДЛЯ ПОКУПКИ NFT
def buy_nft(call, slot_id):
    user_id = call.from_user.id
    
    conn = sqlite3.connect('nft_market.db', check_same_thread=False)
    cursor = conn.cursor()
    
    # Получаем информацию о слоте
    cursor.execute('SELECT seller_id, price_rub, description FROM slots WHERE slot_id = ? AND is_active = TRUE', (slot_id,))
    slot = cursor.fetchone()
    
    if not slot:
        bot.answer_callback_query(call.id, "❌ Слот не найден")
        conn.close()
        return
    
    seller_id, price, description = slot
    
    if seller_id == user_id:
        bot.answer_callback_query(call.id, "❌ Нельзя купить свой собственный NFT")
        conn.close()
        return
    
    # Проверяем баланс покупателя
    cursor.execute('SELECT balance FROM users WHERE user_id = ?', (user_id,))
    buyer_balance = cursor.fetchone()[0]
    
    if buyer_balance < price:
        bot.answer_callback_query(call.id, f"❌ Недостаточно средств. Нужно: {format_balance(price)} руб")
        conn.close()
        return
    
    # Создаем запись о покупке
    cursor.execute('INSERT INTO purchases (slot_id, buyer_id, seller_id, amount) VALUES (?, ?, ?, ?)',
                  (slot_id, user_id, seller_id, price))
    
    # Резервируем средства у покупателя
    cursor.execute('UPDATE users SET balance = balance - ? WHERE user_id = ?', (price, user_id))
    
    # Делаем слот неактивным
    cursor.execute('UPDATE slots SET is_active = FALSE WHERE slot_id = ?', (slot_id,))
    
    # Записываем транзакцию
    cursor.execute('INSERT INTO transactions (user_id, amount, type, description) VALUES (?, ?, ?, ?)',
                  (user_id, -price, 'purchase', f'Покупка NFT: {description}'))
    
    conn.commit()
    conn.close()
    
    # Получаем информацию о покупателе для уведомления продавцу
    conn_buyer = sqlite3.connect('nft_market.db', check_same_thread=False)
    cursor_buyer = conn_buyer.cursor()
    cursor_buyer.execute('SELECT username, full_name FROM users WHERE user_id = ?', (user_id,))
    buyer_info = cursor_buyer.fetchone()
    conn_buyer.close()
    
    buyer_username = buyer_info[0] if buyer_info else "Не указан"
    buyer_full_name = buyer_info[1] if buyer_info else "Не указано"
    display_buyer_username = get_user_display(user_id, buyer_username)
    
    # Получаем информацию о продавце для уведомления покупателю
    conn_seller = sqlite3.connect('nft_market.db', check_same_thread=False)
    cursor_seller = conn_seller.cursor()
    cursor_seller.execute('SELECT username, full_name FROM users WHERE user_id = ?', (seller_id,))
    seller_info = cursor_seller.fetchone()
    conn_seller.close()
    
    seller_username = seller_info[0] if seller_info else "Не указан"
    seller_full_name = seller_info[1] if seller_info else "Не указано"
    display_seller_username = get_user_display(seller_id, seller_username)
    
    # Уведомляем продавца
    try:
        seller_keyboard = InlineKeyboardMarkup()
        seller_keyboard.add(InlineKeyboardButton("✅ Подтвердить отправку", callback_data=f"confirm_send_{slot_id}"))
        
        seller_message = (
            f"🛒 Новый покупатель!\n\n"
            f"🎁 NFT: {description}\n"
            f"💰 Сумма: {format_balance(price)} руб\n"
            f"👤 Покупатель ID: {user_id}\n"
            f"📛 Имя: {buyer_full_name}\n"
            f"🔗 Username: @{display_buyer_username}\n\n"
            f"✅ Подтвердите отправку NFT:"
        )
        
        bot.send_message(seller_id, seller_message, reply_markup=seller_keyboard)
    except:
        pass
    
    # Уведомляем покупателя
    buyer_keyboard = InlineKeyboardMarkup()
    buyer_keyboard.add(
        InlineKeyboardButton("✅ Подтвердить получение", callback_data=f"confirm_receive_{slot_id}"),
        InlineKeyboardButton("❌ Отменить сделку", callback_data=f"cancel_deal_{slot_id}")
    )
    
    bot.answer_callback_query(call.id, "✅ Покупка оформлена!")
    bot.send_message(
        call.message.chat.id,
        f"✅ Покупка оформлена!\n\n"
        f"🎁 NFT: {description}\n"
        f"💰 Сумма: {format_balance(price)} руб\n"
        f"👤 Продавец ID: {seller_id}\n"
        f"📛 Имя: {seller_full_name}\n"
        f"🔗 Username: @{display_seller_username}\n\n"
        f"Продавец уведомлен о покупке.\n"
        f"После получения NFT подтвердите получение:",
        reply_markup=buyer_keyboard
    )

# МОИ NFT
def show_my_nft_text(message):
    user_id = message.from_user.id
    conn = sqlite3.connect('nft_market.db', check_same_thread=False)
    cursor = conn.cursor()
    
    cursor.execute('''
        SELECT slot_id, description, price_rub
        FROM slots 
        WHERE seller_id = ? AND is_active = TRUE
    ''', (user_id,))
    slots = cursor.fetchall()
    conn.close()
    
    if not slots:
        bot.send_message(message.chat.id, "🛒 У вас нет активных NFT слотов")
        return
    
    keyboard = InlineKeyboardMarkup()
    for slot in slots:
        slot_id, description, price = slot
        keyboard.add(InlineKeyboardButton(f"🎁 {description[:20]}... - {format_balance(price)} руб", callback_data=f"myslot_{slot_id}"))
    
    keyboard.add(InlineKeyboardButton("⬅️ Назад", callback_data="back_to_main"))
    
    bot.send_message(message.chat.id, "🛒 Ваши NFT слоты:", reply_markup=keyboard)

def show_my_slot_details(call, slot_id):
    keyboard = InlineKeyboardMarkup()
    keyboard.add(InlineKeyboardButton("❌ Удалить", callback_data=f"delete_{slot_id}"))
    keyboard.add(InlineKeyboardButton("⬅️ Назад", callback_data="back_to_my_nft"))
    
    bot.send_message(
        call.message.chat.id,
        "🎁 Ваш NFT слот\n\nУправление слотом:",
        reply_markup=keyboard
    )

def delete_slot(call, slot_id):
    user_id = call.from_user.id
    conn = sqlite3.connect('nft_market.db', check_same_thread=False)
    cursor = conn.cursor()
    
    # Проверяем, принадлежит ли слот пользователю
    cursor.execute('SELECT seller_id FROM slots WHERE slot_id = ?', (slot_id,))
    slot = cursor.fetchone()
    
    if not slot or slot[0] != user_id:
        bot.answer_callback_query(call.id, "❌ Вы не можете удалить этот слот")
        conn.close()
        return
    
    # Удаляем слот
    cursor.execute('DELETE FROM slots WHERE slot_id = ?', (slot_id,))
    conn.commit()
    conn.close()
    
    bot.answer_callback_query(call.id, "✅ Слот удален")
    bot.send_message(call.message.chat.id, "✅ Слот успешно удален")

# ПОДДЕРЖКА
def support_start_text(message):
    set_user_state(message.from_user.id, "waiting_support_message")
    keyboard = InlineKeyboardMarkup()
    keyboard.add(InlineKeyboardButton("⬅️ Назад", callback_data="back_to_main"))
    
    bot.send_message(
        message.chat.id,
        "📞 Поддержка\n\nОпишите вашу проблему или вопрос:",
        reply_markup=keyboard
    )

def process_support_message(message):
    user = message.from_user
    
    conn = sqlite3.connect('nft_market.db', check_same_thread=False)
    cursor = conn.cursor()
    cursor.execute(
        'INSERT INTO support_tickets (user_id, message) VALUES (?, ?)',
        (user.id, message.text)
    )
    ticket_id = cursor.lastrowid
    conn.commit()
    conn.close()
    
    clear_user_state(user.id)
    
    try:
        # Отправляем всем админам
        for admin_id in ADMINS:
            try:
                # Используем новую функцию для отображения username
                display_username = get_user_display(user.id, user.username)
                bot.send_message(
                    admin_id,
                    f"📞 Новый тикет #{ticket_id}\n\n"
                    f"👤 Пользователь: @{display_username} (ID: {user.id})\n"
                    f"💬 Сообщение: {message.text}"
                )
            except:
                continue
        bot.send_message(message.chat.id, "✅ Ваше сообщение отправлено администратору.")
    except:
        bot.send_message(message.chat.id, "❌ Ошибка при отправке сообщения.")
    
    show_main_menu(message.chat.id, "Главное меню:")

# ПРОМОКОДЫ - ТОЛЬКО В ПРОФИЛЕ
def process_promocode_activation(message, user_id):
    promocode = message.text.strip().upper()
    
    # Если пользователь ввел команду "назад" или подобное
    if promocode in ["⬅️ Назад", "назад", "отмена", "cancel"]:
        clear_user_state(user_id)
        show_main_menu(message.chat.id, "Главное меню:")
        return
    
    conn = sqlite3.connect('nft_market.db', check_same_thread=False)
    cursor = conn.cursor()
    
    # Проверяем существование промокода
    cursor.execute('SELECT promocode_id, amount, max_activations, current_activations FROM promocodes WHERE code = ?', (promocode,))
    promocode_data = cursor.fetchone()
    
    if not promocode_data:
        bot.send_message(message.chat.id, "❌ Промокод не найден. Попробуйте еще раз:")
        conn.close()
        return
    
    promocode_id, amount, max_activations, current_activations = promocode_data
    
    # Проверяем лимит активаций
    if current_activations >= max_activations:
        bot.send_message(message.chat.id, "❌ Лимит активаций промокода исчерпан")
        conn.close()
        clear_user_state(user_id)
        return
    
    # Проверяем, активировал ли пользователь уже этот промокод
    cursor.execute('SELECT activation_id FROM promocode_activations WHERE promocode_id = ? AND user_id = ?', (promocode_id, user_id))
    existing_activation = cursor.fetchone()
    
    if existing_activation:
        bot.send_message(message.chat.id, "❌ Вы уже активировали этот промокод")
        conn.close()
        clear_user_state(user_id)
        return
    
    # Активируем промокод
    cursor.execute('UPDATE promocodes SET current_activations = current_activations + 1 WHERE promocode_id = ?', (promocode_id,))
    cursor.execute('UPDATE users SET balance = balance + ? WHERE user_id = ?', (amount, user_id))
    cursor.execute('INSERT INTO promocode_activations (promocode_id, user_id) VALUES (?, ?)', (promocode_id, user_id))
    cursor.execute('INSERT INTO transactions (user_id, amount, type, description) VALUES (?, ?, ?, ?)',
                 (user_id, amount, 'promocode', f'Активация промокода {promocode}'))
    
    conn.commit()
    conn.close()
    
    clear_user_state(user_id)
    bot.send_message(message.chat.id, f"✅ Промокод активирован! На ваш баланс зачислено {format_balance(amount)} руб")
    show_main_menu(message.chat.id, "Главное меню:")

# УПРАВЛЕНИЕ ПРОМОКОДАМИ (АДМИН)
def show_promocodes_management(message):
    keyboard = InlineKeyboardMarkup()
    keyboard.add(
        InlineKeyboardButton("➕ Создать промокод", callback_data="admin_create_promocode"),
        InlineKeyboardButton("📋 Список промокодов", callback_data="admin_list_promocodes")
    )
    keyboard.add(InlineKeyboardButton("⬅️ Назад", callback_data="back_to_admin"))
    
    bot.send_message(
        message.chat.id,
        "🎁 Управление промокодами\n\nВыберите действие:",
        reply_markup=keyboard
    )

def process_promocode_name(message):
    code = message.text.strip().upper()
    
    if len(code) < 3:
        bot.send_message(message.chat.id, "❌ Промокод должен содержать минимум 3 символа")
        return
    
    conn = sqlite3.connect('nft_market.db', check_same_thread=False)
    cursor = conn.cursor()
    
    # Проверяем, существует ли уже такой промокод
    cursor.execute('SELECT promocode_id FROM promocodes WHERE code = ?', (code,))
    existing_promocode = cursor.fetchone()
    
    if existing_promocode:
        bot.send_message(message.chat.id, "❌ Промокод с таким названием уже существует")
        conn.close()
        return
    
    conn.close()
    
    set_user_state(message.from_user.id, "waiting_promocode_amount", code)
    bot.send_message(message.chat.id, f"🎁 Промокод: {code}\n💰 Введите сумму вознаграждения:")

def process_promocode_amount(message, code):
    try:
        amount = float(message.text)
        
        if amount <= 0:
            bot.send_message(message.chat.id, "❌ Сумма должна быть больше 0")
            return
        
        set_user_state(message.from_user.id, "waiting_promocode_activations", f"{code}|{amount}")
        bot.send_message(message.chat.id, f"🎁 Промокод: {code}\n💰 Сумма: {format_balance(amount)} руб\n\nВведите количество активаций:")
        
    except ValueError:
        bot.send_message(message.chat.id, "❌ Введите корректную сумму")

def process_promocode_activations(message, code, amount):
    try:
        max_activations = int(message.text)
        
        if max_activations <= 0:
            bot.send_message(message.chat.id, "❌ Количество активаций должно быть больше 0")
            return
        
        conn = sqlite3.connect('nft_market.db', check_same_thread=False)
        cursor = conn.cursor()
        
        cursor.execute('INSERT INTO promocodes (code, amount, max_activations, created_by) VALUES (?, ?, ?, ?)',
                     (code, amount, max_activations, message.from_user.id))
        
        conn.commit()
        conn.close()
        
        clear_user_state(message.from_user.id)
        bot.send_message(message.chat.id, f"✅ Промокод создан!\n\n🎁 Код: {code}\n💰 Сумма: {format_balance(amount)} руб\n🔄 Активаций: {max_activations}")
        
    except ValueError:
        bot.send_message(message.chat.id, "❌ Введите корректное число")

# РАССЫЛКА (АДМИН)
def show_broadcast_management(message):
    keyboard = InlineKeyboardMarkup()
    keyboard.add(InlineKeyboardButton("📢 Сделать рассылку", callback_data="admin_broadcast"))
    keyboard.add(InlineKeyboardButton("⬅️ Назад", callback_data="back_to_admin"))
    
    bot.send_message(
        message.chat.id,
        "📢 Управление рассылкой\n\nВыберите действие:",
        reply_markup=keyboard
    )

def process_broadcast_message(message):
    broadcast_text = message.text
    
    conn = sqlite3.connect('nft_market.db', check_same_thread=False)
    cursor = conn.cursor()
    
    cursor.execute('SELECT user_id FROM users WHERE is_banned = FALSE')
    users = cursor.fetchall()
    conn.close()
    
    total_users = len(users)
    successful_sends = 0
    failed_sends = 0
    
    bot.send_message(message.chat.id, f"📢 Начинаю рассылку для {total_users} пользователей...")
    
    for user in users:
        user_id = user[0]
        try:
            bot.send_message(user_id, broadcast_text)
            successful_sends += 1
        except:
            failed_sends += 1
    
    clear_user_state(message.from_user.id)
    bot.send_message(
        message.chat.id,
        f"✅ Рассылка завершена!\n\n"
        f"👥 Всего пользователей: {total_users}\n"
        f"✅ Успешно отправлено: {successful_sends}\n"
        f"❌ Не удалось отправить: {failed_sends}"
    )

# АДМИН ФУНКЦИИ
def show_stats(message):
    conn = sqlite3.connect('nft_market.db', check_same_thread=False)
    cursor = conn.cursor()
    
    cursor.execute('SELECT COUNT(*) FROM users')
    total_users = cursor.fetchone()[0]
    
    cursor.execute('SELECT COUNT(*) FROM slots WHERE is_active = TRUE')
    active_slots = cursor.fetchone()[0]
    
    cursor.execute('SELECT SUM(balance) FROM users')
    total_balance = cursor.fetchone()[0] or 0
    
    cursor.execute('SELECT COUNT(*) FROM support_tickets WHERE status = "open"')
    open_tickets = cursor.fetchone()[0]
    
    cursor.execute('SELECT COUNT(*) FROM withdraw_requests WHERE status = "pending"')
    pending_withdrawals = cursor.fetchone()[0]
    
    cursor.execute('SELECT COUNT(*) FROM purchases WHERE status = "pending"')
    pending_purchases = cursor.fetchone()[0]
    
    # Статистика сделок
    cursor.execute('SELECT COUNT(*) FROM purchases WHERE status = "completed"')
    successful_deals = cursor.fetchone()[0]
    
    cursor.execute('SELECT COUNT(*) FROM purchases WHERE status = "pending"')
    failed_deals = cursor.fetchone()[0]
    
    conn.close()
    
    stats_text = (
        f"📊 Статистика платформы\n\n"
        f"👥 Всего пользователей: {total_users}\n"
        f"🎁 Активных слотов: {active_slots}\n"
        f"💰 Общий баланс: {format_balance(total_balance)} руб\n"
        f"📞 Открытых тикетов: {open_tickets}\n"
        f"💸 Заявок на вывод: {pending_withdrawals}\n"
        f"🛒 Ожидающих сделок: {pending_purchases}\n"
        f"✅ Успешных сделок: {successful_deals}\n"
        f"❌ Неудачных сделок: {failed_deals}"
    )
    
    keyboard = InlineKeyboardMarkup()
    keyboard.add(InlineKeyboardButton("⬅️ Назад", callback_data="back_to_admin"))
    
    bot.send_message(message.chat.id, stats_text, reply_markup=keyboard)

def show_tickets(message):
    conn = sqlite3.connect('nft_market.db', check_same_thread=False)
    cursor = conn.cursor()
    
    cursor.execute('''
        SELECT ticket_id, user_id, message, created_at 
        FROM support_tickets 
        WHERE status = 'open'
        ORDER BY created_at DESC
    ''')
    tickets = cursor.fetchall()
    
    if not tickets:
        bot.send_message(message.chat.id, "📭 Нет открытых тикетов")
        conn.close()
        return
    
    for ticket in tickets:
        ticket_id, user_id, ticket_message, created_at = ticket
        
        # Получаем username пользователя используя тот же курсор
        cursor.execute('SELECT username FROM users WHERE user_id = ?', (user_id,))
        user_info = cursor.fetchone()
        username = user_info[0] if user_info else "Не указан"
        
        # Используем новую функцию для отображения username
        display_username = get_user_display(user_id, username)
        
        ticket_text = (
            f"📞 Тикет #{ticket_id}\n\n"
            f"👤 ID пользователя: {user_id}\n"
            f"🔗 Username: @{display_username}\n"
            f"💬 Сообщение: {ticket_message}\n"
            f"📅 Создан: {created_at}"
        )
        
        keyboard = InlineKeyboardMarkup()
        keyboard.add(InlineKeyboardButton("💬 Ответить", callback_data=f"reply_ticket_{ticket_id}"))
        keyboard.add(InlineKeyboardButton("⬅️ Назад", callback_data="back_to_admin"))
        
        bot.send_message(message.chat.id, ticket_text, reply_markup=keyboard)
    
    conn.close()

def show_withdraw_requests(message):
    try:
        conn = sqlite3.connect('nft_market.db', check_same_thread=False)
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT withdraw_id, user_id, amount, card_number, created_at 
            FROM withdraw_requests 
            WHERE status = 'pending'
            ORDER BY created_at DESC
        ''')
        requests = cursor.fetchall()
        
        if not requests:
            bot.send_message(message.chat.id, "📭 Нет заявок на вывод")
            conn.close()
            return
        
        for req in requests:
            withdraw_id, user_id, amount, card_number, created_at = req
            
            # Получаем username пользователя используя тот же курсор
            cursor.execute('SELECT username FROM users WHERE user_id = ?', (user_id,))
            user_info = cursor.fetchone()
            username = user_info[0] if user_info else "Не указан"
            
            # Используем новую функцию для отображения username
            display_username = get_user_display(user_id, username)
            
            request_text = (
                f"💰 Заявка на вывод #{withdraw_id}\n\n"
                f"👤 ID пользователя: {user_id}\n"
                f"🔗 Username: @{display_username}\n"
                f"💳 Карта: {card_number}\n"
                f"💸 Сумма: {format_balance(amount)} руб\n"
                f"📅 Создана: {created_at}"
            )
            
            keyboard = InlineKeyboardMarkup()
            keyboard.add(
                InlineKeyboardButton("✅ Одобрить", callback_data=f"approve_withdraw_{withdraw_id}"),
                InlineKeyboardButton("❌ Отклонить", callback_data=f"reject_withdraw_{withdraw_id}")
            )
            keyboard.add(InlineKeyboardButton("⬅️ Назад", callback_data="back_to_admin"))
            
            bot.send_message(message.chat.id, request_text, reply_markup=keyboard)
        
        conn.close()
        
    except Exception as e:
        logger.error(f"Error in show_withdraw_requests: {e}")
        bot.send_message(message.chat.id, "❌ Ошибка при загрузке заявок на вывод")

def show_users_management(message):
    keyboard = InlineKeyboardMarkup()
    keyboard.add(
        InlineKeyboardButton("👤 Забанить пользователя", callback_data="admin_ban"),
        InlineKeyboardButton("👤 Разбанить пользователя", callback_data="admin_unban"),
        InlineKeyboardButton("📋 Список пользователей", callback_data="admin_list_users")
    )
    keyboard.add(InlineKeyboardButton("⬅️ Назад", callback_data="back_to_admin"))
    
    bot.send_message(
        message.chat.id,
        "👥 Управление пользователями\n\nВыберите действие:",
        reply_markup=keyboard
    )

def show_balance_management(message):
    keyboard = InlineKeyboardMarkup()
    keyboard.add(
        InlineKeyboardButton("💸 Пополнить баланс", callback_data="admin_add_balance"),
        InlineKeyboardButton("📋 Балансы пользователей", callback_data="admin_list_balances")
    )
    keyboard.add(InlineKeyboardButton("⬅️ Назад", callback_data="back_to_admin"))
    
    bot.send_message(
        message.chat.id,
        "💳 Управление балансами\n\nВыберите действие:",
        reply_markup=keyboard
    )

def show_admin_management(message):
    keyboard = InlineKeyboardMarkup()
    keyboard.add(
        InlineKeyboardButton("👑 Добавить админа", callback_data="admin_add_admin"),
        InlineKeyboardButton("👑 Удалить админа", callback_data="admin_remove_admin"),
        InlineKeyboardButton("📋 Список админов", callback_data="admin_list_admins")
    )
    keyboard.add(InlineKeyboardButton("⬅️ Назад", callback_data="back_to_admin"))
    
    bot.send_message(
        message.chat.id,
        "👑 Управление администраторами\n\nВыберите действие:",
        reply_markup=keyboard
    )

# ОБРАБОТЧИК ИНЛАЙН КНОПОК
@bot.callback_query_handler(func=lambda call: True)
def handle_callback(call):
    user_id = call.from_user.id
    data = call.data
    
    # Проверяем доступ для всех callback'ов (кроме админов и проверки подписки)
    if data != "check_subscription" and not is_user_admin(user_id):
        access, message_text = check_access(user_id)
        if not access:
            if message_text == "subscribe_required":
                show_subscription_required(call.message.chat.id)
            else:
                bot.send_message(call.message.chat.id, message_text)
            bot.answer_callback_query(call.id)
            return
    
    try:
        if data == "back_to_main":
            show_main_menu(call.message.chat.id, "Главное меню:")
        elif data == "back_to_admin":
            show_admin_menu(call.message.chat.id)
        elif data == "back_to_slots":
            find_slots_text(call.message)
        elif data == "back_to_my_nft":
            show_my_nft_text(call.message)
        elif data == "check_subscription":
            handle_subscription_check(call)
        elif data == "change_name":
            set_user_state(user_id, "waiting_name_change")
            bot.send_message(call.message.chat.id, "✏️ Введите ваше новое имя:")
        elif data == "withdraw_balance":
            withdraw_start_callback(call)
        elif data == "transfer_money":
            transfer_money_start(call)
        elif data == "my_reviews":
            show_my_reviews(call)
        elif data == "activate_promocode":
            # Для промокода в профиле не проверяем подписку дополнительно
            set_user_state(user_id, "waiting_promocode")
            keyboard = InlineKeyboardMarkup()
            keyboard.add(InlineKeyboardButton("⬅️ Назад", callback_data="back_to_main"))
            
            bot.send_message(
                call.message.chat.id,
                "🎁 Активация промокода\n\nВведите промокод:",
                reply_markup=keyboard
            )
            bot.answer_callback_query(call.id)
        elif data.startswith("slot_"):
            slot_id = int(data.split("_")[1])
            show_slot_details(call, slot_id)
        elif data.startswith("myslot_"):
            slot_id = int(data.split("_")[1])
            show_my_slot_details(call, slot_id)
        elif data.startswith("buy_"):
            slot_id = int(data.split("_")[1])
            buy_nft(call, slot_id)
        elif data.startswith("delete_"):
            slot_id = int(data.split("_")[1])
            delete_slot(call, slot_id)
        elif data.startswith("contact_"):
            slot_id = int(data.split("_")[1])
            show_contact_info(call, slot_id)
        elif data.startswith("reviews_"):
            user_id_to_show = int(data.split("_")[1])
            review_type = data.split("_")[2]
            show_reviews(call, user_id_to_show, review_type)
        elif data.startswith("rate_buyer_"):
            purchase_id = int(data.split("_")[2])
            start_rating(call, purchase_id, "buyer")
        elif data.startswith("rate_seller_"):
            purchase_id = int(data.split("_")[2])
            start_rating(call, purchase_id, "seller")
        elif data.startswith("rating_"):
            parts = data.split("_")
            purchase_id = int(parts[1])
            rate_type = parts[2]
            rating = int(parts[3])
            set_user_state(user_id, "waiting_rating", f"{purchase_id}|{rate_type}|{rating}")
            bot.send_message(call.message.chat.id, f"💬 Напишите отзыв (или отправьте '-' если не хотите писать отзыв):")
        elif data.startswith("admin_"):
            if is_user_admin(user_id):
                handle_admin_callback(call)
        elif data.startswith("reply_ticket_"):
            if is_user_admin(user_id):
                ticket_id = int(data.split("_")[2])
                set_user_state(user_id, "waiting_ticket_reply", str(ticket_id))
                bot.send_message(call.message.chat.id, f"💬 Введите ответ на тикет #{ticket_id}:")
        elif data.startswith("approve_withdraw_"):
            if is_user_admin(user_id):
                withdraw_id = int(data.split("_")[2])
                approve_withdraw(call, withdraw_id)
        elif data.startswith("reject_withdraw_"):
            if is_user_admin(user_id):
                withdraw_id = int(data.split("_")[2])
                set_user_state(user_id, "waiting_reject_reason", str(withdraw_id))
                bot.send_message(call.message.chat.id, f"📝 Введите причину отказа для заявки #{withdraw_id}:")
        elif data.startswith("select_user_"):
            if is_user_admin(user_id):
                parts = data.split("_")
                user_id_selected = int(parts[2])
                action_type = parts[3]
                handle_selected_user_action(call, user_id_selected, action_type)
        elif data.startswith("confirm_send_"):
            slot_id = int(data.split("_")[2])
            confirm_send_nft(call, slot_id)
        elif data.startswith("confirm_receive_"):
            slot_id = int(data.split("_")[2])
            confirm_receive_nft(call, slot_id)
        elif data.startswith("cancel_deal_"):
            slot_id = int(data.split("_")[2])
            cancel_deal(call, slot_id)
        else:
            bot.answer_callback_query(call.id, "❌ Неизвестная команда")
    except Exception as e:
        logger.error(f"Error in callback handler: {e}")
        bot.answer_callback_query(call.id, "❌ Ошибка обработки команды")

# ФУНКЦИЯ ДЛЯ ПРОВЕРКИ ПОДПИСКИ
def handle_subscription_check(call):
    user_id = call.from_user.id
    
    if check_subscription(user_id):
        update_user_subscription(user_id, True)
        bot.answer_callback_query(call.id, "✅ Спасибо за подписку!")
        show_main_menu(call.message.chat.id, "Добро пожаловать в NFT Marketplace! 🎨\n\nЗдесь вы можете покупать и продавать NFT подарки.\nВыберите действие:")
    else:
        bot.answer_callback_query(call.id, "❌ Вы не подписаны на канал")
        show_subscription_required(call.message.chat.id)

def handle_admin_callback(call):
    data = call.data
    
    if data == "admin_ban":
        show_user_selection(call.message, "ban")
    elif data == "admin_unban":
        show_user_selection(call.message, "unban")
    elif data == "admin_add_balance":
        show_user_selection(call.message, "balance")
    elif data == "admin_list_users":
        show_all_users(call)
    elif data == "admin_list_balances":
        show_all_balances(call)
    elif data == "admin_create_promocode":
        set_user_state(call.from_user.id, "waiting_promocode_name")
        bot.send_message(call.message.chat.id, "🎁 Введите название промокода:")
    elif data == "admin_list_promocodes":
        show_all_promocodes(call)
    elif data == "admin_broadcast":
        set_user_state(call.from_user.id, "waiting_broadcast_message")
        bot.send_message(call.message.chat.id, "📢 Введите сообщение для рассылки:")
    elif data == "admin_add_admin":
        set_user_state(call.from_user.id, "waiting_add_admin")
        bot.send_message(call.message.chat.id, "👑 Введите ID пользователя для добавления в админы:")
    elif data == "admin_remove_admin":
        show_user_selection(call.message, "remove_admin")
    elif data == "admin_list_admins":
        show_all_admins(call)

# ДОПОЛНИТЕЛЬНЫЕ ФУНКЦИИ
def withdraw_start_callback(call):
    user_id = call.from_user.id
    conn = sqlite3.connect('nft_market.db', check_same_thread=False)
    cursor = conn.cursor()
    cursor.execute('SELECT balance FROM users WHERE user_id = ?', (user_id,))
    result = cursor.fetchone()
    conn.close()
    
    if not result or result[0] <= 0:
        bot.answer_callback_query(call.id, "❌ На балансе нет средств")
        return
    
    balance = result[0]
    set_user_state(user_id, "waiting_withdraw_card", str(balance))
    bot.send_message(call.message.chat.id, f"💰 Ваш баланс: {format_balance(balance)} руб\n\nВведите номер карты:")

def process_withdraw_card(message, balance, user_id):
    card = message.text.strip()
    if len(card) < 16:
        bot.send_message(message.chat.id, "❌ Неверный номер карты")
        return
    
    set_user_state(user_id, "waiting_withdraw_amount", f"{balance}|{card}")
    bot.send_message(message.chat.id, f"💳 Карта: {card}\n💰 Доступно: {format_balance(balance)} руб\n\nВведите сумму:")

def process_withdraw_amount(message, balance, user_id, card):
    try:
        amount = float(message.text)
        if amount <= 0 or amount > balance:
            bot.send_message(message.chat.id, f"❌ Неверная сумма. Максимум: {format_balance(balance)} руб")
            return
        
        conn = sqlite3.connect('nft_market.db', check_same_thread=False)
        cursor = conn.cursor()
        cursor.execute('UPDATE users SET balance = balance - ? WHERE user_id = ?', (amount, user_id))
        cursor.execute('INSERT INTO withdraw_requests (user_id, amount, card_number) VALUES (?, ?, ?)',
                     (user_id, amount, card))
        conn.commit()
        conn.close()
        
        clear_user_state(user_id)
        bot.send_message(message.chat.id, f"✅ Заявка на вывод {format_balance(amount)} руб создана!")
        show_main_menu(message.chat.id, "Главное меню:")
        
    except ValueError:
        bot.send_message(message.chat.id, "❌ Введите число")

def transfer_money_start(call):
    set_user_state(call.from_user.id, "waiting_transfer_user")
    bot.send_message(call.message.chat.id, "👤 Введите ID пользователя, которому хотите перевести средства:")

def process_transfer_user(message, user_id):
    try:
        target_user_id = int(message.text.strip())
        
        if target_user_id == user_id:
            bot.send_message(message.chat.id, "❌ Нельзя переводить средства самому себе")
            return
            
        conn = sqlite3.connect('nft_market.db', check_same_thread=False)
        cursor = conn.cursor()
        cursor.execute('SELECT user_id FROM users WHERE user_id = ?', (target_user_id,))
        target_user = cursor.fetchone()
        conn.close()
        
        if not target_user:
            bot.send_message(message.chat.id, "❌ Пользователь не найден")
            return
            
        set_user_state(user_id, "waiting_transfer_amount", str(target_user_id))
        bot.send_message(message.chat.id, f"👤 Получатель: {target_user_id}\n💰 Введите сумму для перевода:")
        
    except ValueError:
        bot.send_message(message.chat.id, "❌ Введите корректный ID пользователя (число)")

def process_transfer_amount(message, user_id, target_user_id):
    try:
        amount = float(message.text)
        
        if amount <= 0:
            bot.send_message(message.chat.id, "❌ Сумма должна быть больше 0")
            return
            
        conn = sqlite3.connect('nft_market.db', check_same_thread=False)
        cursor = conn.cursor()
        
        # Проверяем баланс отправителя
        cursor.execute('SELECT balance FROM users WHERE user_id = ?', (user_id,))
        sender_balance = cursor.fetchone()[0]
        
        if sender_balance < amount:
            bot.send_message(message.chat.id, f"❌ Недостаточно средств. На вашем балансе: {format_balance(sender_balance)} руб")
            conn.close()
            return
            
        # Выполняем перевод
        cursor.execute('UPDATE users SET balance = balance - ? WHERE user_id = ?', (amount, user_id))
        cursor.execute('UPDATE users SET balance = balance + ? WHERE user_id = ?', (amount, target_user_id))
        
        # Записываем транзакции
        cursor.execute('INSERT INTO transactions (user_id, amount, type, description) VALUES (?, ?, ?, ?)',
                     (user_id, -amount, 'transfer_out', f'Перевод пользователю {target_user_id}'))
        cursor.execute('INSERT INTO transactions (user_id, amount, type, description) VALUES (?, ?, ?, ?)',
                     (target_user_id, amount, 'transfer_in', f'Перевод от пользователя {user_id}'))
        
        conn.commit()
        conn.close()
        
        clear_user_state(user_id)
        
        # Уведомляем получателя
        try:
            bot.send_message(target_user_id, f"💰 Вам переведено {format_balance(amount)} руб от пользователя {user_id}")
        except:
            pass
            
        bot.send_message(message.chat.id, f"✅ Средства успешно переведены!\n👤 Получатель: {target_user_id}\n💰 Сумма: {format_balance(amount)} руб")
        show_main_menu(message.chat.id, "Главное меню:")
        
    except ValueError:
        bot.send_message(message.chat.id, "❌ Введите корректную сумму")

def process_name_change(message, user_id):
    name = message.text.strip()
    if len(name) < 2:
        bot.send_message(message.chat.id, "❌ Имя слишком короткое")
        return
    
    conn = sqlite3.connect('nft_market.db', check_same_thread=False)
    cursor = conn.cursor()
    cursor.execute('UPDATE users SET full_name = ? WHERE user_id = ?', (name, user_id))
    conn.commit()
    conn.close()
    
    clear_user_state(user_id)
    bot.send_message(message.chat.id, f"✅ Имя изменено на: {name}")
    show_main_menu(message.chat.id, "Главное меню:")

def show_my_reviews(call):
    user_id = call.from_user.id
    
    keyboard = InlineKeyboardMarkup()
    keyboard.add(
        InlineKeyboardButton("⭐ Отзывы как продавца", callback_data=f"reviews_{user_id}_seller"),
        InlineKeyboardButton("⭐ Отзывы как покупателя", callback_data=f"reviews_{user_id}_buyer")
    )
    keyboard.add(InlineKeyboardButton("⬅️ Назад", callback_data="back_to_main"))
    
    bot.send_message(call.message.chat.id, "📊 Мои отзывы\n\nВыберите тип отзывов:", reply_markup=keyboard)

def show_contact_info(call, slot_id):
    conn = sqlite3.connect('nft_market.db', check_same_thread=False)
    cursor = conn.cursor()
    
    cursor.execute('''
        SELECT s.contact_info, s.description, u.username, u.user_id
        FROM slots s 
        JOIN users u ON s.seller_id = u.user_id 
        WHERE s.slot_id = ?
    ''', (slot_id,))
    slot = cursor.fetchone()
    conn.close()
    
    if not slot:
        bot.answer_callback_query(call.id, "❌ Слот не найден")
        return
    
    contact_info, description, username, seller_id = slot
    
    # Используем новую функцию для отображения username
    display_username = get_user_display(seller_id, username)
    
    message_text = (
        f"📞 Контактные данные продавца\n\n"
        f"🎁 NFT: {description}\n"
        f"👤 Продавец: @{display_username}\n"
        f"📱 Контакт: {contact_info}\n\n"
        f"💬 Напишите продавцу в личные сообщения для уточнения деталей."
    )
    
    bot.send_message(call.message.chat.id, message_text)

def show_reviews(call, user_id, review_type):
    conn = sqlite3.connect('nft_market.db', check_same_thread=False)
    cursor = conn.cursor()
    
    # Получаем информацию о пользователе
    cursor.execute('SELECT username, full_name FROM users WHERE user_id = ?', (user_id,))
    user_info = cursor.fetchone()
    
    if not user_info:
        bot.answer_callback_query(call.id, "❌ Пользователь не найден")
        conn.close()
        return
    
    username, full_name = user_info
    
    # Используем новую функцию для отображения username
    display_username = get_user_display(user_id, username)
    
    # Получаем отзывы
    cursor.execute('''
        SELECT r.rating, r.review_text, u.username, r.created_at, u.user_id
        FROM reviews r 
        JOIN users u ON r.reviewer_id = u.user_id 
        WHERE r.user_id = ? AND r.review_type = ?
        ORDER BY r.created_at DESC
    ''', (user_id, review_type))
    
    reviews = cursor.fetchall()
    conn.close()
    
    review_type_text = "продавца" if review_type == "seller" else "покупателя"
    user_text = f"{full_name or 'Без имени'} (@{display_username})"
    
    if not reviews:
        message_text = f"📊 Отзывы о {review_type_text}\n\n👤 {user_text}\n\n📝 Пока нет отзывов"
        bot.send_message(call.message.chat.id, message_text)
        return
    
    message_text = f"📊 Отзывы о {review_type_text}\n\n👤 {user_text}\n\n"
    
    for i, review in enumerate(reviews[:10], 1):  # Показываем последние 10 отзывов
        rating, review_text, reviewer_username, created_at, reviewer_id = review
        stars = "⭐" * rating + "☆" * (5 - rating)
        review_display = review_text if review_text != "-" else "Без отзыва"
        # Используем новую функцию для отображения username рецензента
        display_reviewer_username = get_user_display(reviewer_id, reviewer_username)
        message_text += f"{i}. {stars}\n👤 @{display_reviewer_username or 'аноним'}\n💬 {review_display}\n📅 {created_at[:16]}\n\n"
    
    keyboard = InlineKeyboardMarkup()
    keyboard.add(InlineKeyboardButton("⬅️ Назад", callback_data="back_to_main"))
    
    bot.send_message(call.message.chat.id, message_text, reply_markup=keyboard)

def start_rating(call, purchase_id, rate_type):
    keyboard = InlineKeyboardMarkup(row_width=5)
    keyboard.add(
        InlineKeyboardButton("1⭐", callback_data=f"rating_{purchase_id}_{rate_type}_1"),
        InlineKeyboardButton("2⭐", callback_data=f"rating_{purchase_id}_{rate_type}_2"),
        InlineKeyboardButton("3⭐", callback_data=f"rating_{purchase_id}_{rate_type}_3"),
        InlineKeyboardButton("4⭐", callback_data=f"rating_{purchase_id}_{rate_type}_4"),
        InlineKeyboardButton("5⭐", callback_data=f"rating_{purchase_id}_{rate_type}_5")
    )
    
    rate_type_text = "продавца" if rate_type == "seller" else "покупателя"
    bot.send_message(call.message.chat.id, f"⭐ Оцените {rate_type_text} от 1 до 5 звезд:", reply_markup=keyboard)

def process_review(message, purchase_id, rate_type, rating):
    review_text = message.text.strip()
    
    conn = sqlite3.connect('nft_market.db', check_same_thread=False)
    cursor = conn.cursor()
    
    # Получаем информацию о покупке
    cursor.execute('SELECT buyer_id, seller_id FROM purchases WHERE purchase_id = ?', (purchase_id,))
    purchase = cursor.fetchone()
    
    if not purchase:
        bot.send_message(message.chat.id, "❌ Покупка не найдена")
        conn.close()
        return
    
    buyer_id, seller_id = purchase
    
    # Определяем кто кого оценивает
    if rate_type == "seller":
        user_id = seller_id  # Того, кого оценивают
        reviewer_id = buyer_id  # Тот, кто оценивает
        rating_field = "seller_rated"
        rating_value_field = "seller_rating"
        review_field = "seller_review"
    else:  # rate_type == "buyer"
        user_id = buyer_id
        reviewer_id = seller_id
        rating_field = "buyer_rated"
        rating_value_field = "buyer_rating"
        review_field = "buyer_review"
    
    # Сохраняем оценку в покупке
    cursor.execute(f'UPDATE purchases SET {rating_field} = TRUE, {rating_value_field} = ?, {review_field} = ? WHERE purchase_id = ?', 
                  (rating, review_text, purchase_id))
    
    # Сохраняем отзыв
    cursor.execute('''
        INSERT INTO reviews (user_id, reviewer_id, review_type, rating, review_text, purchase_id)
        VALUES (?, ?, ?, ?, ?, ?)
    ''', (user_id, reviewer_id, rate_type, rating, review_text, purchase_id))
    
    # Обновляем рейтинг пользователя
    if rate_type == "seller":
        cursor.execute('''
            UPDATE users SET rating_seller = (
                SELECT AVG(r.rating) FROM reviews r 
                WHERE r.user_id = ? AND r.review_type = 'seller'
            ) WHERE user_id = ?
        ''', (user_id, user_id))
    else:
        cursor.execute('''
            UPDATE users SET rating_buyer = (
                SELECT AVG(r.rating) FROM reviews r 
                WHERE r.user_id = ? AND r.review_type = 'buyer'
            ) WHERE user_id = ?
        ''', (user_id, user_id))
    
    conn.commit()
    conn.close()
    
    clear_user_state(message.from_user.id)
    
    rate_type_text = "продавца" if rate_type == "seller" else "покупателя"
    bot.send_message(message.chat.id, f"✅ Вы оценили {rate_type_text}!")
    show_main_menu(message.chat.id, "Главное меню:")

def approve_withdraw(call, withdraw_id):
    conn = sqlite3.connect('nft_market.db', check_same_thread=False)
    cursor = conn.cursor()
    
    cursor.execute('SELECT user_id, amount FROM withdraw_requests WHERE withdraw_id = ?', (withdraw_id,))
    withdraw = cursor.fetchone()
    
    if not withdraw:
        bot.answer_callback_query(call.id, "❌ Заявка не найдена")
        conn.close()
        return
    
    user_id, amount = withdraw
    
    cursor.execute('UPDATE withdraw_requests SET status = "approved" WHERE withdraw_id = ?', (withdraw_id,))
    cursor.execute('INSERT INTO transactions (user_id, amount, type, description) VALUES (?, ?, ?, ?)',
                 (user_id, -amount, 'withdraw', f'Вывод средств (заявка #{withdraw_id})'))
    
    conn.commit()
    conn.close()
    
    try:
        bot.send_message(user_id, f"✅ Ваша заявка на вывод {format_balance(amount)} руб одобрена!")
    except:
        pass
    
    bot.answer_callback_query(call.id, "✅ Заявка одобрена")
    bot.send_message(call.message.chat.id, f"✅ Заявка #{withdraw_id} одобрена")

def handle_selected_user_action(call, user_id_selected, action_type):
    """Обрабатывает выбранного пользователя"""
    try:
        if action_type == "ban":
            ban_user(call, user_id_selected)
        elif action_type == "unban":
            unban_user(call, user_id_selected)
        elif action_type == "balance":
            set_user_state(call.from_user.id, "waiting_admin_balance", str(user_id_selected))
            bot.send_message(call.message.chat.id, f"💸 Введите сумму для пополнения баланса пользователя {user_id_selected}:")
        elif action_type == "add_admin":
            add_admin(call, user_id_selected)
        elif action_type == "remove_admin":
            remove_admin(call, user_id_selected)
        else:
            bot.answer_callback_query(call.id, "❌ Неизвестное действие")
    except Exception as e:
        logger.error(f"Error in handle_selected_user_action: {e}")
        bot.answer_callback_query(call.id, "❌ Ошибка обработки")

def ban_user(call, user_id):
    conn = sqlite3.connect('nft_market.db', check_same_thread=False)
    cursor = conn.cursor()
    
    cursor.execute('UPDATE users SET is_banned = TRUE WHERE user_id = ?', (user_id,))
    conn.commit()
    conn.close()
    
    try:
        bot.send_message(user_id, "❌ Вы были забанены администратором.")
    except:
        pass
    
    bot.answer_callback_query(call.id, "✅ Пользователь забанен")
    bot.send_message(call.message.chat.id, f"✅ Пользователь {user_id} забанен")

def unban_user(call, user_id):
    conn = sqlite3.connect('nft_market.db', check_same_thread=False)
    cursor = conn.cursor()
    
    cursor.execute('UPDATE users SET is_banned = FALSE WHERE user_id = ?', (user_id,))
    conn.commit()
    conn.close()
    
    try:
        bot.send_message(user_id, "✅ Вы были разбанены администратором.")
    except:
        pass
    
    bot.answer_callback_query(call.id, "✅ Пользователь разбанен")
    bot.send_message(call.message.chat.id, f"✅ Пользователь {user_id} разбанен")

def add_admin(call, user_id):
    conn = sqlite3.connect('nft_market.db', check_same_thread=False)
    cursor = conn.cursor()
    
    cursor.execute('UPDATE users SET is_admin = TRUE WHERE user_id = ?', (user_id,))
    conn.commit()
    conn.close()
    
    update_global_admins()
    
    try:
        bot.send_message(user_id, "👑 Вы были назначены администратором!")
    except:
        pass
    
    bot.answer_callback_query(call.id, "✅ Пользователь добавлен в админы")
    bot.send_message(call.message.chat.id, f"✅ Пользователь {user_id} добавлен в админы")

def remove_admin(call, user_id):
    if user_id == ADMIN_ID:
        bot.answer_callback_query(call.id, "❌ Нельзя удалить главного администратора")
        return
        
    conn = sqlite3.connect('nft_market.db', check_same_thread=False)
    cursor = conn.cursor()
    
    cursor.execute('UPDATE users SET is_admin = FALSE WHERE user_id = ?', (user_id,))
    conn.commit()
    conn.close()
    
    update_global_admins()
    
    try:
        bot.send_message(user_id, "👑 Вы были удалены из администраторов.")
    except:
        pass
    
    bot.answer_callback_query(call.id, "✅ Пользователь удален из админов")
    bot.send_message(call.message.chat.id, f"✅ Пользователь {user_id} удален из админов")

def confirm_send_nft(call, slot_id):
    user_id = call.from_user.id
    
    conn = sqlite3.connect('nft_market.db', check_same_thread=False)
    cursor = conn.cursor()
    
    # Получаем информацию о покупке
    cursor.execute('''
        SELECT p.purchase_id, p.buyer_id, p.amount, s.description 
        FROM purchases p 
        JOIN slots s ON p.slot_id = s.slot_id 
        WHERE p.slot_id = ? AND p.status = 'pending'
    ''', (slot_id,))
    purchase = cursor.fetchone()
    
    if not purchase:
        bot.answer_callback_query(call.id, "❌ Покупка не найдена")
        conn.close()
        return
    
    purchase_id, buyer_id, amount, description = purchase
    
    # Обновляем статус покупки - NFT отправлен
    cursor.execute('UPDATE purchases SET nft_sent = TRUE WHERE purchase_id = ?', (purchase_id,))
    
    conn.commit()
    conn.close()
    
    # Уведомляем покупателя
    try:
        bot.send_message(
            buyer_id,
            f"📦 Продавец подтвердил отправку NFT!\n\n"
            f"🎁 {description}\n\n"
            f"✅ Пожалуйста, проверьте получение NFT и подтвердите его получение."
        )
    except:
        pass
    
    bot.answer_callback_query(call.id, "✅ Отправка NFT подтверждена!")
    bot.send_message(
        call.message.chat.id,
        "✅ Вы подтвердили отправку NFT. Ожидайте подтверждения получения от покупателя."
    )

def confirm_receive_nft(call, slot_id):
    user_id = call.from_user.id
    
    conn = sqlite3.connect('nft_market.db', check_same_thread=False)
    cursor = conn.cursor()
    
    # Получаем информацию о покупке
    cursor.execute('''
        SELECT p.purchase_id, p.seller_id, p.amount, s.description, p.nft_sent
        FROM purchases p 
        JOIN slots s ON p.slot_id = s.slot_id 
        WHERE p.slot_id = ? AND p.buyer_id = ? AND p.status = 'pending'
    ''', (slot_id, user_id))
    purchase = cursor.fetchone()
    
    if not purchase:
        bot.answer_callback_query(call.id, "❌ Покупка не найдена")
        conn.close()
        return
    
    purchase_id, seller_id, amount, description, nft_sent = purchase
    
    if not nft_sent:
        bot.answer_callback_query(call.id, "❌ Продавец еще не подтвердил отправку NFT")
        conn.close()
        return
    
    # Обновляем статус покупки - завершена
    cursor.execute('UPDATE purchases SET status = "completed", nft_received = TRUE WHERE purchase_id = ?', (purchase_id,))
    
    # Переводим средства продавцу
    cursor.execute('UPDATE users SET balance = balance + ? WHERE user_id = ?', (amount, seller_id))
    
    # Обновляем статистику
    cursor.execute('UPDATE users SET total_sales = total_sales + 1, successful_sales = successful_sales + 1 WHERE user_id = ?', (seller_id,))
    cursor.execute('UPDATE users SET total_purchases = total_purchases + 1, successful_purchases = successful_purchases + 1 WHERE user_id = ?', (user_id,))
    
    # Добавляем транзакцию
    cursor.execute('INSERT INTO transactions (user_id, amount, type, description) VALUES (?, ?, ?, ?)',
                 (seller_id, amount, 'sale', f'Продажа NFT: {description}'))
    
    conn.commit()
    conn.close()
    
    # Уведомляем продавца
    try:
        keyboard = InlineKeyboardMarkup()
        keyboard.add(InlineKeyboardButton("⭐ Оценить покупателя", callback_data=f"rate_buyer_{purchase_id}"))
        
        seller_message = (
            f"💰 Покупатель подтвердил получение NFT!\n\n"
            f"🎁 {description}\n"
            f"💸 Сумма: {format_balance(amount)} руб переведена на ваш баланс\n\n"
            f"✅ Сделка успешно завершена!\n"
            f"Оцените покупателя:"
        )
        
        bot.send_message(seller_id, seller_message, reply_markup=keyboard)
    except:
        pass
    
    # Уведомляем покупателя
    keyboard = InlineKeyboardMarkup()
    keyboard.add(InlineKeyboardButton("⭐ Оценить продавца", callback_data=f"rate_seller_{purchase_id}"))
    
    bot.answer_callback_query(call.id, "✅ Получение NFT подтверждено!")
    bot.send_message(
        call.message.chat.id,
        f"✅ Вы подтвердили получение NFT. Сделка завершена!\n\n"
        f"🎁 {description}\n"
        f"💰 Сумма: {format_balance(amount)} руб переведена продавцу\n\n"
        f"Оцените продавца:",
        reply_markup=keyboard
    )

def cancel_deal(call, slot_id):
    user_id = call.from_user.id
    
    conn = sqlite3.connect('nft_market.db', check_same_thread=False)
    cursor = conn.cursor()
    
    # Получаем информацию о покупке
    cursor.execute('''
        SELECT p.purchase_id, p.seller_id, p.amount, s.description
        FROM purchases p 
        JOIN slots s ON p.slot_id = s.slot_id 
        WHERE p.slot_id = ? AND p.buyer_id = ? AND p.status = 'pending'
    ''', (slot_id, user_id))
    purchase = cursor.fetchone()
    
    if not purchase:
        bot.answer_callback_query(call.id, "❌ Покупка не найдена")
        conn.close()
        return
    
    purchase_id, seller_id, amount, description = purchase
    
    # Возвращаем средства покупателю
    cursor.execute('UPDATE users SET balance = balance + ? WHERE user_id = ?', (amount, user_id))
    
    # Обновляем статистику неудачных сделок
    cursor.execute('UPDATE users SET failed_sales = failed_sales + 1 WHERE user_id = ?', (seller_id,))
    cursor.execute('UPDATE users SET failed_purchases = failed_purchases + 1 WHERE user_id = ?', (user_id,))
    
    # Делаем слот активным снова
    cursor.execute('UPDATE slots SET is_active = TRUE WHERE slot_id = ?', (slot_id,))
    
    # Удаляем покупку
    cursor.execute('DELETE FROM purchases WHERE purchase_id = ?', (purchase_id,))
    
    conn.commit()
    conn.close()
    
    # Уведомляем продавца
    try:
        bot.send_message(
            seller_id,
            f"❌ Покупатель отменил сделку!\n\n"
            f"🎁 {description}\n"
            f"💰 Сумма: {format_balance(amount)} руб возвращена покупателю\n"
            f"📈 Ваш слот снова активен для продажи"
        )
    except:
        pass
    
    bot.answer_callback_query(call.id, "✅ Сделка отменена!")
    bot.send_message(
        call.message.chat.id,
        f"✅ Вы отменили сделку.\n\n"
        f"🎁 {description}\n"
        f"💰 Сумма: {format_balance(amount)} руб возвращена на ваш баланс\n"
        f"📈 Слот снова доступен для покупки"
    )

# ФУНКЦИЯ ДЛЯ ВЫБОРА ПОЛЬЗОВАТЕЛЯ
def show_user_selection(message, action_type):
    """Показывает список пользователей для выбора"""
    conn = sqlite3.connect('nft_market.db', check_same_thread=False)
    cursor = conn.cursor()
    
    cursor.execute('SELECT user_id, username, full_name FROM users ORDER BY user_id')
    users = cursor.fetchall()
    conn.close()
    
    if not users:
        bot.send_message(message.chat.id, "👥 Нет пользователей")
        return
    
    keyboard = InlineKeyboardMarkup()
    for user in users:
        user_id, username, full_name = user
        # Используем новую функцию для отображения username
        display_username = get_user_display(user_id, username)
        user_display = f"🆔 {user_id} | @{display_username} | {full_name or 'нет имени'}"
        keyboard.add(InlineKeyboardButton(user_display, callback_data=f"select_user_{user_id}_{action_type}"))
    
    keyboard.add(InlineKeyboardButton("⬅️ Назад", callback_data="back_to_admin"))
    
    action_names = {
        "ban": "бана",
        "unban": "разбана", 
        "balance": "пополнения баланса",
        "add_admin": "добавления в админы",
        "remove_admin": "удаления из админов"
    }
    
    bot.send_message(
        message.chat.id,
        f"👥 Выберите пользователя для {action_names.get(action_type, 'действия')}:",
        reply_markup=keyboard
    )

def show_all_users(call):
    conn = sqlite3.connect('nft_market.db', check_same_thread=False)
    cursor = conn.cursor()
    
    cursor.execute('SELECT user_id, username, full_name, is_banned FROM users ORDER BY user_id')
    users = cursor.fetchall()
    conn.close()
    
    if not users:
        bot.send_message(call.message.chat.id, "👥 Нет пользователей")
        return
    
    users_text = "👥 Список пользователей:\n\n"
    for user in users:
        user_id, username, full_name, is_banned = user
        status = "❌ Забанен" if is_banned else "✅ Активен"
        # Используем новую функцию для отображения username
        display_username = get_user_display(user_id, username)
        users_text += f"🆔 {user_id} | @{display_username} | {full_name or 'нет'} | {status}\n"
    
    keyboard = InlineKeyboardMarkup()
    keyboard.add(InlineKeyboardButton("⬅️ Назад", callback_data="back_to_admin"))
    
    bot.send_message(call.message.chat.id, users_text, reply_markup=keyboard)

def show_all_balances(call):
    conn = sqlite3.connect('nft_market.db', check_same_thread=False)
    cursor = conn.cursor()
    
    cursor.execute('SELECT user_id, username, balance FROM users WHERE balance > 0 ORDER BY balance DESC')
    users = cursor.fetchall()
    conn.close()
    
    if not users:
        bot.send_message(call.message.chat.id, "💰 Нет пользователей с балансом")
        return
    
    balances_text = "💰 Балансы пользователей:\n\n"
    for user in users:
        user_id, username, balance = user
        # Используем новую функцию для отображения username
        display_username = get_user_display(user_id, username)
        balances_text += f"🆔 {user_id} | @{display_username} | {format_balance(balance)} руб\n"
    
    keyboard = InlineKeyboardMarkup()
    keyboard.add(InlineKeyboardButton("⬅️ Назад", callback_data="back_to_admin"))
    
    bot.send_message(call.message.chat.id, balances_text, reply_markup=keyboard)

def show_all_admins(call):
    conn = sqlite3.connect('nft_market.db', check_same_thread=False)
    cursor = conn.cursor()
    
    cursor.execute('SELECT user_id, username, full_name FROM users WHERE is_admin = TRUE ORDER BY user_id')
    admins = cursor.fetchall()
    conn.close()
    
    if not admins:
        bot.send_message(call.message.chat.id, "👑 Нет администраторов")
        return
    
    admins_text = "👑 Список администраторов:\n\n"
    for admin in admins:
        user_id, username, full_name = admin
        # Используем новую функцию для отображения username
        display_username = get_user_display(user_id, username)
        admins_text += f"🆔 {user_id} | @{display_username} | {full_name or 'нет имени'}\n"
    
    keyboard = InlineKeyboardMarkup()
    keyboard.add(InlineKeyboardButton("⬅️ Назад", callback_data="back_to_admin"))
    
    bot.send_message(call.message.chat.id, admins_text, reply_markup=keyboard)

def show_all_promocodes(call):
    conn = sqlite3.connect('nft_market.db', check_same_thread=False)
    cursor = conn.cursor()
    
    cursor.execute('''
        SELECT p.code, p.amount, p.max_activations, p.current_activations, p.created_at, u.username 
        FROM promocodes p 
        LEFT JOIN users u ON p.created_by = u.user_id 
        ORDER BY p.created_at DESC
    ''')
    promocodes = cursor.fetchall()
    conn.close()
    
    if not promocodes:
        bot.send_message(call.message.chat.id, "🎁 Нет созданных промокодов")
        return
    
    promocodes_text = "🎁 Список промокодов:\n\n"
    for promo in promocodes:
        code, amount, max_activations, current_activations, created_at, creator_username = promo
        status = "🟢 Активен" if current_activations < max_activations else "🔴 Завершен"
        promocodes_text += f"🎁 {code}\n💰 {format_balance(amount)} руб\n🔄 {current_activations}/{max_activations}\n📅 {created_at[:16]}\n👤 Создал: @{get_user_display(0, creator_username)}\n{status}\n\n"
    
    keyboard = InlineKeyboardMarkup()
    keyboard.add(InlineKeyboardButton("⬅️ Назад", callback_data="back_to_admin"))
    
    bot.send_message(call.message.chat.id, promocodes_text, reply_markup=keyboard)

def process_admin_balance(message):
    try:
        amount = float(message.text)
        
        if amount <= 0:
            bot.send_message(message.chat.id, "❌ Сумма должна быть больше 0")
            return
        
        state, state_data = get_user_state(message.from_user.id)
        user_id = int(state_data) if state_data else None
        
        if not user_id:
            bot.send_message(message.chat.id, "❌ Ошибка: пользователь не выбран")
            return
        
        conn = sqlite3.connect('nft_market.db', check_same_thread=False)
        cursor = conn.cursor()
        
        cursor.execute('UPDATE users SET balance = balance + ? WHERE user_id = ?', (amount, user_id))
        cursor.execute('INSERT INTO transactions (user_id, amount, type, description) VALUES (?, ?, ?, ?)',
                     (user_id, amount, 'admin_add', f'Пополнение администратором'))
        
        conn.commit()
        conn.close()
        
        try:
            bot.send_message(user_id, f"💰 Ваш баланс пополнен на {format_balance(amount)} руб администратором!")
        except:
            pass
        
        bot.send_message(message.chat.id, f"✅ Баланс пользователя {user_id} пополнен на {format_balance(amount)} руб")
        clear_user_state(message.from_user.id)
        
    except ValueError:
        bot.send_message(message.chat.id, "❌ Введите корректную сумму")

def process_admin_ban(message):
    show_user_selection(message, "ban")

def process_admin_unban(message):
    show_user_selection(message, "unban")

def process_reject_reason(message, withdraw_id):
    reason = message.text
    
    conn = sqlite3.connect('nft_market.db', check_same_thread=False)
    cursor = conn.cursor()
    
    cursor.execute('SELECT user_id, amount FROM withdraw_requests WHERE withdraw_id = ?', (withdraw_id,))
    withdraw = cursor.fetchone()
    
    if not withdraw:
        bot.send_message(message.chat.id, "❌ Заявка не найдена")
        conn.close()
        return
    
    user_id, amount = withdraw
    
    cursor.execute('UPDATE users SET balance = balance + ? WHERE user_id = ?', (amount, user_id))
    cursor.execute('UPDATE withdraw_requests SET status = "rejected", admin_comment = ? WHERE withdraw_id = ?', 
                  (reason, withdraw_id))
    
    conn.commit()
    conn.close()
    
    try:
        bot.send_message(user_id, f"❌ Ваша заявка на вывод {format_balance(amount)} руб отклонена.\n\nПричина: {reason}")
    except:
        pass
    
    bot.send_message(message.chat.id, f"✅ Заявка #{withdraw_id} отклонена")
    clear_user_state(message.from_user.id)

def process_ticket_reply(message, ticket_id):
    reply_text = message.text
    
    conn = sqlite3.connect('nft_market.db', check_same_thread=False)
    cursor = conn.cursor()
    
    cursor.execute('SELECT user_id FROM support_tickets WHERE ticket_id = ?', (ticket_id,))
    ticket = cursor.fetchone()
    
    if not ticket:
        bot.send_message(message.chat.id, "❌ Тикет не найден")
        conn.close()
        return
    
    user_id = ticket[0]
    
    cursor.execute('UPDATE support_tickets SET status = "closed", admin_response = ? WHERE ticket_id = ?', 
                  (reply_text, ticket_id))
    
    conn.commit()
    conn.close()
    
    try:
        bot.send_message(user_id, f"📞 Ответ от поддержки:\n\n{reply_text}")
    except:
        pass
    
    bot.send_message(message.chat.id, f"✅ Ответ на тикет #{ticket_id} отправлен")
    clear_user_state(message.from_user.id)

def process_add_admin(message):
    try:
        user_id = int(message.text.strip())
        
        conn = sqlite3.connect('nft_market.db', check_same_thread=False)
        cursor = conn.cursor()
        cursor.execute('SELECT user_id FROM users WHERE user_id = ?', (user_id,))
        target_user = cursor.fetchone()
        conn.close()
        
        if not target_user:
            bot.send_message(message.chat.id, "❌ Пользователь не найден")
            return
            
        add_admin_by_id(message, user_id)
        
    except ValueError:
        bot.send_message(message.chat.id, "❌ Введите корректный ID пользователя (число)")

def add_admin_by_id(message, user_id):
    conn = sqlite3.connect('nft_market.db', check_same_thread=False)
    cursor = conn.cursor()
    
    cursor.execute('UPDATE users SET is_admin = TRUE WHERE user_id = ?', (user_id,))
    conn.commit()
    conn.close()
    
    update_global_admins()
    
    try:
        bot.send_message(user_id, "👑 Вы были назначены администратором!")
    except:
        pass
    
    bot.send_message(message.chat.id, f"✅ Пользователь {user_id} добавлен в админы")
    clear_user_state(message.from_user.id)

def process_remove_admin(message):
    try:
        user_id = int(message.text.strip())
        
        if user_id == ADMIN_ID:
            bot.send_message(message.chat.id, "❌ Нельзя удалить главного администратора")
            return
            
        conn = sqlite3.connect('nft_market.db', check_same_thread=False)
        cursor = conn.cursor()
        cursor.execute('SELECT user_id FROM users WHERE user_id = ?', (user_id,))
        target_user = cursor.fetchone()
        conn.close()
        
        if not target_user:
            bot.send_message(message.chat.id, "❌ Пользователь не найден")
            return
            
        remove_admin_by_id(message, user_id)
        
    except ValueError:
        bot.send_message(message.chat.id, "❌ Введите корректный ID пользователя (число)")

def remove_admin_by_id(message, user_id):
    conn = sqlite3.connect('nft_market.db', check_same_thread=False)
    cursor = conn.cursor()
    
    cursor.execute('UPDATE users SET is_admin = FALSE WHERE user_id = ?', (user_id,))
    conn.commit()
    conn.close()
    
    update_global_admins()
    
    try:
        bot.send_message(user_id, "👑 Вы были удалены из администраторов.")
    except:
        pass
    
    bot.send_message(message.chat.id, f"✅ Пользователь {user_id} удален из админов")
    clear_user_state(message.from_user.id)

# Запуск бота
if __name__ == '__main__':
    init_db()
    update_global_admins()
    logger.info("🤖 Бот запущен!")
    bot.infinity_polling()