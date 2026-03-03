import telebot
import sqlite3
import random
import os
from datetime import datetime, timedelta
from telebot import types
import threading
import time
import re

TOKEN = os.environ['TOKEN']
bot = telebot.TeleBot(TOKEN)
CURRENCY = "💰 SuguruCoins"

# ========== ПУТЬ К БАЗЕ ДАННЫХ ==========
POSSIBLE_PATHS = [
    '/data/bot.db',
    '/storage/bot.db',
    '/opt/render/project/src/data/bot.db',
    './bot.db'
]

DB_PATH = None
for path in POSSIBLE_PATHS:
    try:
        dir_path = os.path.dirname(path)
        if os.path.exists(dir_path) and os.access(dir_path, os.W_OK):
            DB_PATH = path
            print(f"✅ База будет храниться в: {DB_PATH}")
            break
    except:
        continue

if DB_PATH is None:
    DB_PATH = 'bot.db'
    print("⚠️ Постоянное хранилище не найдено, использую локальную БД")

# ========== ГЛОБАЛЬНЫЕ ПЕРЕМЕННЫЕ (КЭШ) ==========
ADMINS = {}
BANS = {}
WARNS = {}
MAX_WARNS = 3

# ========== БАЗА ДАННЫХ ==========
def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_db()
    cursor = conn.cursor()
    
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER PRIMARY KEY,
            username TEXT,
            first_name TEXT,
            custom_name TEXT UNIQUE,
            balance INTEGER DEFAULT 0,
            exp INTEGER DEFAULT 0,
            level INTEGER DEFAULT 1,
            work_count INTEGER DEFAULT 0,
            total_earned INTEGER DEFAULT 0,
            last_daily TEXT,
            warns INTEGER DEFAULT 0,
            banned_until TEXT,
            equipped_clothes INTEGER DEFAULT NULL,
            current_city TEXT DEFAULT 'Село Молочное',
            has_car INTEGER DEFAULT 0,
            has_plane INTEGER DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS jobs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            job_name TEXT UNIQUE,
            min_exp INTEGER,
            min_reward INTEGER,
            max_reward INTEGER,
            exp_reward INTEGER,
            emoji TEXT
        )
    ''')
    
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS businesses (
            user_id INTEGER PRIMARY KEY,
            business_name TEXT,
            level INTEGER DEFAULT 1,
            raw_material INTEGER DEFAULT 0,
            raw_in_delivery INTEGER DEFAULT 0,
            raw_spent INTEGER DEFAULT 0,
            total_invested INTEGER DEFAULT 0,
            stored_profit INTEGER DEFAULT 0,
            last_update TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS deliveries (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            amount INTEGER,
            end_time TEXT,
            delivered INTEGER DEFAULT 0
        )
    ''')
    
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS business_data (
            name TEXT PRIMARY KEY,
            price INTEGER,
            emoji TEXT,
            raw_cost_per_unit INTEGER,
            profit_per_raw INTEGER,
            base_time INTEGER,
            photo_url TEXT
        )
    ''')
    
    # ========== ТАБЛИЦЫ ДЛЯ МАГАЗИНА ОДЕЖДЫ ==========
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS shop_clothes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            price INTEGER NOT NULL,
            photo_url TEXT NOT NULL,
            in_shop INTEGER DEFAULT 1
        )
    ''')
    
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS user_clothes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            clothes_id INTEGER,
            equipped INTEGER DEFAULT 1,
            purchased_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users(user_id),
            FOREIGN KEY (clothes_id) REFERENCES shop_clothes(id)
        )
    ''')
    
    # ========== ТАБЛИЦЫ ДЛЯ ГОРОДОВ ==========
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS cities (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT UNIQUE,
            description TEXT,
            has_clothes_shop INTEGER DEFAULT 1,
            has_house_shop INTEGER DEFAULT 0,
            has_plane_shop INTEGER DEFAULT 0
        )
    ''')
    
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS travels (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            from_city TEXT,
            to_city TEXT,
            transport TEXT,
            end_time TEXT,
            completed INTEGER DEFAULT 0
        )
    ''')
    
    # ========== ТАБЛИЦЫ ДЛЯ АДМИНОВ, БАНОВ И ВАРНОВ ==========
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS admins (
            user_id INTEGER PRIMARY KEY,
            level INTEGER DEFAULT 1,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS bans (
            user_id INTEGER PRIMARY KEY,
            reason TEXT,
            until REAL,
            banned_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS warns (
            user_id INTEGER PRIMARY KEY,
            count INTEGER DEFAULT 0,
            last_warn TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    # ========== ТАБЛИЦА ДЛЯ СТАТИСТИКИ РУЛЕТКИ ==========
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS roulette_stats (
            user_id INTEGER PRIMARY KEY,
            games_played INTEGER DEFAULT 0,
            wins INTEGER DEFAULT 0,
            losses INTEGER DEFAULT 0,
            total_bet INTEGER DEFAULT 0,
            total_win INTEGER DEFAULT 0,
            total_lose INTEGER DEFAULT 0,
            biggest_win INTEGER DEFAULT 0,
            biggest_lose INTEGER DEFAULT 0,
            last_game TIMESTAMP
        )
    ''')
    
    # ========== ТАБЛИЦА ДЛЯ СТАТИСТИКИ МИНИ-ИГР ==========
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS work_stats (
            user_id INTEGER,
            job_type TEXT,
            games_played INTEGER DEFAULT 0,
            perfect_games INTEGER DEFAULT 0,
            best_time REAL,
            total_earned INTEGER DEFAULT 0,
            avg_score INTEGER DEFAULT 0,
            PRIMARY KEY (user_id, job_type)
        )
    ''')
    
    # Добавляем главного админа
    cursor.execute('INSERT OR IGNORE INTO admins (user_id, level) VALUES (?, ?)', (5596589260, 4))
    
    # Заполняем города
    cursor.execute('SELECT COUNT(*) FROM cities')
    if cursor.fetchone()[0] == 0:
        cities_data = [
            ("Кропоткин", "Промышленный город с развитой инфраструктурой", 1, 1, 0),
            ("Москва", "Столица! Здесь есть всё", 1, 0, 1),
            ("Мурино", "Молодежный спальный район", 1, 1, 0),
            ("Село Молочное", "Уютное село, отличное место для старта", 1, 0, 0)
        ]
        cursor.executemany('''
            INSERT INTO cities (name, description, has_clothes_shop, has_house_shop, has_plane_shop)
            VALUES (?, ?, ?, ?, ?)
        ''', cities_data)
    
    # Заполняем магазин одеждой
    cursor.execute('SELECT COUNT(*) FROM shop_clothes')
    if cursor.fetchone()[0] == 0:
        clothes_data = [
            ("Любит_поспать", 160000000, "https://iimg.su/i/DeILfi"),
            ("БоссFKC", 700000000, "https://iimg.su/i/mZUtyC"),
            ("Фермер", 400000000, "https://iimg.su/i/1ChPnG"),
            ("Крутой", 100000000, "https://iimg.su/i/RqexQt"),
            ("Шалун", 150000000, "https://iimg.su/i/He6eQH"),
            ("Пепе", 350000000, "https://iimg.su/i/eQKrdn"),
            ("С_улицы", 70000000, "https://iimg.su/i/Jn88sT"),
            ("Спринг_бонни", 700000000, "https://iimg.su/i/wOy6tw"),
            ("Качок", 400000000, "https://iimg.su/i/XI1uhf"),
            ("Платье", 80000000, "https://iimg.su/i/UBQvJy"),
            ("Скелет", 666666666666, "https://iimg.su/i/RnLRY8"),
            ("Гангстер", 250000000, "https://iimg.su/i/dk8sE2"),
            ("Тяги", 67000000, "https://iimg.su/i/sQ6ns5"),
            ("Модный", 20000000, "https://iimg.su/i/8UkPmY"),
            ("Романтик2.0", 100000000, "https://iimg.su/i/qryc9I"),
            ("Романтик", 50000000, "https://iimg.su/i/8l70sn")
        ]
        cursor.executemany('''
            INSERT INTO shop_clothes (name, price, photo_url)
            VALUES (?, ?, ?)
        ''', clothes_data)
    
    # Обновляем business_data с фото
    businesses_data = [
        ("🥤 Киоск", 500_000, "🥤", 1_000, 2_000, 60, "https://th.bing.com/th/id/R.4634fab1300b0376abe417c30426a9b7?rik=xcaYMuQThvYHig&riu=http%3a%2f%2fidei-biz.com%2fwp-content%2fuploads%2f2015%2f04%2fkak-otkryt-kiosk.gif&ehk=Vgms8Tfzm6kKm5Me0BE8ByekknYG3Df%2fjHuMD3NjPGM%3d&risl=&pid=ImgRaw&r=0"),
        ("🍔 Фастфуд", 5_000_000, "🍔", 2_500, 5_000, 60, "https://tse1.mm.bing.net/th/id/OIP.HEYen4QlXTiaZzGiYuutCQHaEc?cb=defcache2&defcache=1&rs=1&pid=ImgDetMain&o=7&rm=3"),
        ("🏪 Минимаркет", 15_000_000, "🏪", 30_000, 60_000, 60, "https://tse1.mm.bing.net/th/id/OIP.JQQSzTluO8SxcChv5ZrjWAHaE7?cb=defcache2&defcache=1&rs=1&pid=ImgDetMain&o=7&rm=3"),
        ("⛽ Заправка", 50_000_000, "⛽", 200_000, 400_000, 60, "https://th.bing.com/th/id/R.1b578b96a209d5a4b42fafe640c98c06?rik=fhxZHgYsQRp5Yw&riu=http%3a%2f%2fcdn.motorpage.ru%2fPhotos%2f800%2f213FE.jpg&ehk=kQHdWpflr8ztgGn9DA3XNkz%2fkSj6dzlVhm3%2biuromWk%3d&risl=&pid=ImgRaw&r=0"),
        ("🏨 Отель", 1_000_000_000, "🏨", 1_000_000, 2_000_000, 120, "https://tse1.mm.bing.net/th/id/OIP.oa6wkUpT9KjcmuimacYq3gHaE6?cb=defcache2&defcache=1&rs=1&pid=ImgDetMain&o=7&rm=3")
    ]
    
    for bd in businesses_data:
        cursor.execute('''
            INSERT OR REPLACE INTO business_data (name, price, emoji, raw_cost_per_unit, profit_per_raw, base_time, photo_url)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        ''', bd)
    
    jobs_data = [
        ("🚚 Грузчик", 0, 10, 50, 5, "🚚"),
        ("🧹 Уборщик", 50, 15, 70, 7, "🧹"),
        ("📦 Курьер", 150, 20, 100, 10, "📦"),
        ("🔧 Механик", 300, 30, 150, 12, "🔧"),
        ("💻 Программист", 500, 50, 300, 15, "💻"),
        ("🕵️ Детектив", 800, 100, 500, 20, "🕵️"),
        ("👨‍🔧 Инженер", 1200, 200, 800, 25, "👨‍🔧"),
        ("👨‍⚕️ Врач", 1700, 300, 1200, 30, "👨‍⚕️"),
        ("👨‍🎤 Артист", 2300, 500, 2000, 35, "👨‍🎤"),
        ("👨‍🚀 Космонавт", 3000, 1000, 5000, 50, "👨‍🚀")
    ]
    
    for job in jobs_data:
        cursor.execute('''
            INSERT OR IGNORE INTO jobs (job_name, min_exp, min_reward, max_reward, exp_reward, emoji)
            VALUES (?, ?, ?, ?, ?, ?)
        ''', job)
    
    conn.commit()
    conn.close()
    print("✅ База данных проверена/создана")
    print("🏙️ Система городов активирована!")
    print("👕 Магазин одежды загружен с 16 комплектами!")
    print("🎰 Система рулетки активирована!")
    print("📸 Фото для бизнесов загружены!")
    print("🎮 Мини-игры для работ активированы!")

# ========== ЗАГРУЗКА ДАННЫХ ИЗ БД ==========
def load_admins_from_db():
    try:
        conn = get_db()
        cursor = conn.cursor()
        admins = cursor.execute('SELECT user_id, level FROM admins').fetchall()
        conn.close()
        
        admin_dict = {}
        for admin in admins:
            admin_dict[admin['user_id']] = admin['level']
        return admin_dict
    except Exception as e:
        print(f"Ошибка загрузки админов: {e}")
        return {5596589260: 4}

def load_bans_from_db():
    try:
        conn = get_db()
        cursor = conn.cursor()
        bans = cursor.execute('SELECT user_id, reason, until FROM bans').fetchall()
        conn.close()
        
        ban_dict = {}
        for ban in bans:
            ban_dict[ban['user_id']] = {
                'reason': ban['reason'],
                'until': ban['until']
            }
        return ban_dict
    except Exception as e:
        print(f"Ошибка загрузки банов: {e}")
        return {}

def load_warns_from_db():
    try:
        conn = get_db()
        cursor = conn.cursor()
        warns = cursor.execute('SELECT user_id, count FROM warns').fetchall()
        conn.close()
        
        warn_dict = {}
        for warn in warns:
            warn_dict[warn['user_id']] = warn['count']
        return warn_dict
    except Exception as e:
        print(f"Ошибка загрузки варнов: {e}")
        return {}

init_db()
ADMINS = load_admins_from_db()
BANS = load_bans_from_db()
WARNS = load_warns_from_db()

print(f"👑 Загружено админов: {len(ADMINS)}")
print(f"🔨 Загружено банов: {len(BANS)}")
print(f"⚠️ Загружено варнов: {len(WARNS)}")

# ========== ФУНКЦИИ ДЛЯ РАБОТЫ С АДМИНАМИ/БАНАМИ/ВАРНАМИ ==========

def get_admin_level(user_id):
    if user_id in ADMINS:
        return ADMINS[user_id]
    
    try:
        conn = get_db()
        cursor = conn.cursor()
        admin = cursor.execute('SELECT level FROM admins WHERE user_id = ?', (user_id,)).fetchone()
        conn.close()
        
        if admin:
            level = admin['level']
            ADMINS[user_id] = level
            return level
    except:
        pass
    
    return 0

def is_admin(user_id, required_level=1):
    return get_admin_level(user_id) >= required_level

def add_admin(user_id, level):
    try:
        conn = get_db()
        cursor = conn.cursor()
        
        existing = cursor.execute('SELECT user_id FROM admins WHERE user_id = ?', (user_id,)).fetchone()
        
        if existing:
            conn.close()
            return False, "❌ Пользователь уже админ"
        
        cursor.execute('INSERT INTO admins (user_id, level) VALUES (?, ?)', (user_id, level))
        conn.commit()
        conn.close()
        
        ADMINS[user_id] = level
        
        return True, f"✅ Пользователь назначен админом {level} уровня"
    except Exception as e:
        print(f"Ошибка добавления админа: {e}")
        return False, "❌ Ошибка при добавлении админа"

def remove_admin(user_id):
    try:
        conn = get_db()
        cursor = conn.cursor()
        cursor.execute('DELETE FROM admins WHERE user_id = ?', (user_id,))
        conn.commit()
        conn.close()
        
        if user_id in ADMINS:
            del ADMINS[user_id]
        
        return True
    except Exception as e:
        print(f"Ошибка удаления админа: {e}")
        return False

def set_admin_level(user_id, level):
    try:
        conn = get_db()
        cursor = conn.cursor()
        cursor.execute('UPDATE admins SET level = ? WHERE user_id = ?', (level, user_id))
        conn.commit()
        conn.close()
        
        ADMINS[user_id] = level
        
        return True
    except Exception as e:
        print(f"Ошибка изменения уровня админа: {e}")
        return False

def is_banned(user_id):
    if user_id in BANS:
        ban_info = BANS[user_id]
        if ban_info['until'] == 0:
            return True
        elif datetime.now().timestamp() < ban_info['until']:
            return True
        else:
            del BANS[user_id]
            try:
                conn = get_db()
                cursor = conn.cursor()
                cursor.execute('DELETE FROM bans WHERE user_id = ?', (user_id,))
                conn.commit()
                conn.close()
            except:
                pass
            return False
    
    try:
        conn = get_db()
        cursor = conn.cursor()
        ban = cursor.execute('SELECT until FROM bans WHERE user_id = ?', (user_id,)).fetchone()
        conn.close()
        
        if ban:
            until = ban['until']
            if until == 0:
                BANS[user_id] = {'reason': 'unknown', 'until': 0}
                return True
            elif datetime.now().timestamp() < until:
                BANS[user_id] = {'reason': 'unknown', 'until': until}
                return True
            else:
                conn = get_db()
                cursor = conn.cursor()
                cursor.execute('DELETE FROM bans WHERE user_id = ?', (user_id,))
                conn.commit()
                conn.close()
    except:
        pass
    
    return False

def add_ban(user_id, hours=0, reason="admin"):
    try:
        conn = get_db()
        cursor = conn.cursor()
        
        until = 0 if hours == 0 else (datetime.now() + timedelta(hours=hours)).timestamp()
        
        cursor.execute('DELETE FROM bans WHERE user_id = ?', (user_id,))
        
        cursor.execute('INSERT INTO bans (user_id, reason, until) VALUES (?, ?, ?)', 
                      (user_id, reason, until))
        conn.commit()
        conn.close()
        
        BANS[user_id] = {'reason': reason, 'until': until}
        
        return True
    except Exception as e:
        print(f"Ошибка добавления бана: {e}")
        return False

def remove_ban(user_id):
    try:
        conn = get_db()
        cursor = conn.cursor()
        cursor.execute('DELETE FROM bans WHERE user_id = ?', (user_id,))
        conn.commit()
        conn.close()
        
        if user_id in BANS:
            del BANS[user_id]
        
        return True
    except Exception as e:
        print(f"Ошибка снятия бана: {e}")
        return False

def add_warn(user_id):
    try:
        current = WARNS.get(user_id, 0) + 1
        
        conn = get_db()
        cursor = conn.cursor()
        
        cursor.execute('INSERT OR REPLACE INTO warns (user_id, count, last_warn) VALUES (?, ?, ?)', 
                      (user_id, current, datetime.now().isoformat()))
        conn.commit()
        conn.close()
        
        WARNS[user_id] = current
        
        if current >= MAX_WARNS:
            add_ban(user_id, hours=24*30, reason="warn")
            WARNS[user_id] = 0
            conn = get_db()
            cursor = conn.cursor()
            cursor.execute('UPDATE warns SET count = 0 WHERE user_id = ?', (user_id,))
            conn.commit()
            conn.close()
            return True, f"❌ Получен 3 варн! Бан на 30 дней."
        
        return False, f"⚠️ Варн {current}/{MAX_WARNS}"
    except Exception as e:
        print(f"Ошибка добавления варна: {e}")
        return False, "❌ Ошибка при добавлении варна"

def get_warns(user_id):
    if user_id in WARNS:
        return WARNS[user_id]
    
    try:
        conn = get_db()
        cursor = conn.cursor()
        warn = cursor.execute('SELECT count FROM warns WHERE user_id = ?', (user_id,)).fetchone()
        conn.close()
        
        if warn:
            WARNS[user_id] = warn['count']
            return warn['count']
    except:
        pass
    
    return 0

# ========== ФУНКЦИИ ==========
def add_balance(user_id, amount):
    try:
        conn = get_db()
        cursor = conn.cursor()
        cursor.execute('UPDATE users SET balance = balance + ?, total_earned = total_earned + ? WHERE user_id = ?', 
                      (amount, max(0, amount), user_id))
        conn.commit()
        conn.close()
        return True
    except Exception as e:
        print(f"Ошибка add_balance: {e}")
        return False

def get_balance(user_id):
    try:
        conn = get_db()
        cursor = conn.cursor()
        cursor.execute('SELECT balance FROM users WHERE user_id = ?', (user_id,))
        res = cursor.fetchone()
        conn.close()
        return res[0] if res else 0
    except:
        return 0

def add_exp(user_id, amount):
    try:
        conn = get_db()
        cursor = conn.cursor()
        cursor.execute('SELECT exp, level FROM users WHERE user_id = ?', (user_id,))
        result = cursor.fetchone()
        current_exp = result[0] if result else 0
        current_level = result[1] if result else 1
        
        new_exp = current_exp + amount
        new_level = new_exp // 100 + 1
        
        cursor.execute('UPDATE users SET exp = ?, level = ? WHERE user_id = ?', (new_exp, new_level, user_id))
        conn.commit()
        conn.close()
        return True
    except Exception as e:
        print(f"Ошибка add_exp: {e}")
        return False

def get_user_stats(user_id):
    try:
        conn = get_db()
        cursor = conn.cursor()
        cursor.execute('SELECT exp, level, work_count, total_earned FROM users WHERE user_id = ?', (user_id,))
        res = cursor.fetchone()
        conn.close()
        return res if res else (0, 1, 0, 0)
    except:
        return (0, 1, 0, 0)

def get_user_profile(user_id):
    try:
        conn = get_db()
        cursor = conn.cursor()
        cursor.execute('SELECT * FROM users WHERE user_id = ?', (user_id,))
        user = cursor.fetchone()
        conn.close()
        return user
    except:
        return None

def get_user_by_username(username):
    try:
        conn = get_db()
        cursor = conn.cursor()
        cursor.execute('SELECT user_id, first_name, username, custom_name, warns FROM users WHERE username = ?', (username,))
        user = cursor.fetchone()
        conn.close()
        return user
    except:
        return None

def get_user_by_custom_name(custom_name):
    try:
        conn = get_db()
        cursor = conn.cursor()
        cursor.execute('SELECT user_id, first_name, username, custom_name, warns FROM users WHERE custom_name = ? COLLATE NOCASE', (custom_name,))
        user = cursor.fetchone()
        conn.close()
        return user
    except:
        return None

def get_user_display_name(user_data):
    if not user_data:
        return "Игрок"
    
    custom = user_data[3]
    username = user_data[2]
    
    if custom:
        if username and username != "NoUsername":
            return f"{custom} (@{username})"
        return custom
    elif username and username != "NoUsername":
        return f"@{username}"
    elif user_data[1]:
        return user_data[1]
    return "Игрок"

def set_custom_name(user_id, name):
    try:
        conn = get_db()
        cursor = conn.cursor()
        cursor.execute('UPDATE users SET custom_name = ? WHERE user_id = ?', (name, user_id))
        conn.commit()
        conn.close()
        return True
    except sqlite3.IntegrityError:
        return False
    except Exception as e:
        print(f"Ошибка установки имени: {e}")
        return False

def get_available_jobs(user_id):
    try:
        conn = get_db()
        cursor = conn.cursor()
        cursor.execute('SELECT exp FROM users WHERE user_id = ?', (user_id,))
        exp = cursor.fetchone()[0]
        
        cursor.execute('''
            SELECT job_name, min_exp, min_reward, max_reward, exp_reward, emoji 
            FROM jobs 
            WHERE min_exp <= ?
            ORDER BY min_exp ASC
        ''', (exp,))
        jobs = cursor.fetchall()
        conn.close()
        return jobs
    except Exception as e:
        print(f"Ошибка get_available_jobs: {e}")
        return []

def get_user_business(user_id):
    try:
        conn = get_db()
        cursor = conn.cursor()
        cursor.execute('SELECT * FROM businesses WHERE user_id = ?', (user_id,))
        business = cursor.fetchone()
        conn.close()
        return business
    except:
        return None

def get_business_data(business_name):
    try:
        conn = get_db()
        cursor = conn.cursor()
        cursor.execute('SELECT * FROM business_data WHERE name = ?', (business_name,))
        data = cursor.fetchone()
        conn.close()
        return data
    except:
        return None

def has_active_delivery(user_id):
    try:
        conn = get_db()
        cursor = conn.cursor()
        cursor.execute('SELECT COUNT(*) as count FROM deliveries WHERE user_id = ? AND delivered = 0', (user_id,))
        result = cursor.fetchone()
        conn.close()
        return result['count'] > 0
    except:
        return False

def find_user_by_input(input_str):
    if input_str.startswith('@'):
        username = input_str[1:]
        return get_user_by_username(username)
    else:
        return get_user_by_custom_name(input_str)

# ========== ФУНКЦИИ ДЛЯ ГОРОДОВ ==========

def get_user_city(user_id):
    try:
        conn = get_db()
        cursor = conn.cursor()
        cursor.execute('SELECT current_city FROM users WHERE user_id = ?', (user_id,))
        result = cursor.fetchone()
        conn.close()
        return result[0] if result else "Село Молочное"
    except:
        return "Село Молочное"

def set_user_city(user_id, city):
    try:
        conn = get_db()
        cursor = conn.cursor()
        cursor.execute('UPDATE users SET current_city = ? WHERE user_id = ?', (city, user_id))
        conn.commit()
        conn.close()
        return True
    except:
        return False

def get_city_info(city_name):
    try:
        conn = get_db()
        cursor = conn.cursor()
        cursor.execute('SELECT * FROM cities WHERE name = ?', (city_name,))
        city = cursor.fetchone()
        conn.close()
        return city
    except:
        return None

def start_travel(user_id, to_city, transport):
    try:
        conn = get_db()
        cursor = conn.cursor()
        active = cursor.execute('''
            SELECT id FROM travels 
            WHERE user_id = ? AND completed = 0
        ''', (user_id,)).fetchone()
        
        if active:
            conn.close()
            return False, "❌ У тебя уже есть активная поездка!"
        
        from_city = get_user_city(user_id)
        
        travel_time = random.randint(30, 60)
        end_time = datetime.now() + timedelta(seconds=travel_time)
        
        cursor.execute('''
            INSERT INTO travels (user_id, from_city, to_city, transport, end_time, completed)
            VALUES (?, ?, ?, ?, ?, 0)
        ''', (user_id, from_city, to_city, transport, end_time.isoformat()))
        
        conn.commit()
        conn.close()
        
        return True, f"🚀 Ты отправился в {to_city} на {transport}! Время в пути: {travel_time} сек."
    except Exception as e:
        print(f"Ошибка поездки: {e}")
        return False, "❌ Ошибка при начале поездки"

def get_active_travel(user_id):
    try:
        conn = get_db()
        cursor = conn.cursor()
        travel = cursor.execute('''
            SELECT * FROM travels 
            WHERE user_id = ? AND completed = 0
        ''', (user_id,)).fetchone()
        conn.close()
        return travel
    except:
        return None

def complete_travel(travel_id, user_id):
    try:
        conn = get_db()
        cursor = conn.cursor()
        travel = cursor.execute('SELECT * FROM travels WHERE id = ?', (travel_id,)).fetchone()
        
        if travel:
            cursor.execute('UPDATE users SET current_city = ? WHERE user_id = ?', 
                         (travel['to_city'], user_id))
            cursor.execute('UPDATE travels SET completed = 1 WHERE id = ?', (travel_id,))
            conn.commit()
            
            bot.send_message(
                user_id,
                f"✅ Вы прибыли в {travel['to_city']}!\n"
                f"Транспорт: {travel['transport']}"
            )
        
        conn.close()
        return True
    except Exception as e:
        print(f"Ошибка завершения поездки: {e}")
        return False

# ========== ФУНКЦИИ ДЛЯ МАГАЗИНА И ПРОФИЛЯ ==========

def get_user_equipped_clothes(user_id):
    try:
        conn = get_db()
        cursor = conn.cursor()
        cursor.execute('''
            SELECT sc.* FROM shop_clothes sc
            JOIN user_clothes uc ON sc.id = uc.clothes_id
            WHERE uc.user_id = ? AND uc.equipped = 1
        ''', (user_id,))
        clothes = cursor.fetchone()
        conn.close()
        return clothes
    except:
        return None

def get_user_profile_photo(user_id):
    equipped = get_user_equipped_clothes(user_id)
    if equipped and equipped['photo_url']:
        return equipped['photo_url']
    return "https://iimg.su/i/waxabI"

def send_main_menu_with_profile(user_id, chat_id=None):
    if not chat_id:
        chat_id = user_id
    
    user_data = get_user_profile(user_id)
    if not user_data:
        return
    
    balance = get_balance(user_id)
    display_name = get_user_display_name(user_data)
    current_city = get_user_city(user_id)
    
    caption = (f"👤 *{display_name}*\n\n"
               f"💰 Баланс: {balance:,} {CURRENCY}\n"
               f"📍 Город: {current_city}")
    
    photo_url = get_user_profile_photo(user_id)
    
    bot.send_photo(
        chat_id,
        photo_url,
        caption=caption,
        parse_mode="Markdown",
        reply_markup=main_keyboard()
    )

def buy_clothes(user_id, clothes_id):
    try:
        conn = get_db()
        cursor = conn.cursor()
        
        clothes = cursor.execute('SELECT * FROM shop_clothes WHERE id = ?', (clothes_id,)).fetchone()
        if not clothes:
            conn.close()
            return False, "❌ Товар не найден"
        
        user = cursor.execute('SELECT balance FROM users WHERE user_id = ?', (user_id,)).fetchone()
        if not user or user['balance'] < clothes['price']:
            conn.close()
            return False, f"❌ Недостаточно средств! Нужно {clothes['price']:,} {CURRENCY}"
        
        cursor.execute('UPDATE users SET balance = balance - ? WHERE user_id = ?', (clothes['price'], user_id))
        
        cursor.execute('UPDATE user_clothes SET equipped = 0 WHERE user_id = ?', (user_id,))
        
        cursor.execute('''
            INSERT INTO user_clothes (user_id, clothes_id, equipped)
            VALUES (?, ?, 1)
        ''', (user_id, clothes_id))
        
        cursor.execute('UPDATE users SET equipped_clothes = ? WHERE user_id = ?', (clothes_id, user_id))
        
        conn.commit()
        conn.close()
        return True, f"✅ Поздравляем! Ты купил комплект {clothes['name']} и сразу надел его!"
    except Exception as e:
        print(f"Ошибка при покупке: {e}")
        return False, "❌ Ошибка при покупке"

def get_clothes_page(page=0):
    try:
        conn = get_db()
        cursor = conn.cursor()
        cursor.execute('SELECT * FROM shop_clothes WHERE in_shop = 1 ORDER BY id')
        all_clothes = cursor.fetchall()
        conn.close()
        
        total = len(all_clothes)
        if total == 0:
            return None, 0, 0
        
        if page < 0:
            page = 0
        elif page >= total:
            page = total - 1
        
        return all_clothes[page], page, total
    except:
        return None, 0, 0

def get_clothes_navigation_keyboard(current_page, total_items):
    markup = types.InlineKeyboardMarkup(row_width=3)
    
    buttons = []
    if current_page > 0:
        buttons.append(types.InlineKeyboardButton("◀️", callback_data=f"shop_page_{current_page-1}"))
    else:
        buttons.append(types.InlineKeyboardButton("⬜️", callback_data="noop"))
    
    buttons.append(types.InlineKeyboardButton(f"🛒 Купить", callback_data=f"shop_buy_{current_page}"))
    
    if current_page < total_items - 1:
        buttons.append(types.InlineKeyboardButton("▶️", callback_data=f"shop_page_{current_page+1}"))
    else:
        buttons.append(types.InlineKeyboardButton("⬜️", callback_data="noop"))
    
    markup.row(*buttons)
    markup.row(types.InlineKeyboardButton("❌ Закрыть", callback_data="shop_close"))
    
    return markup

# ========== ФУНКЦИИ ДЛЯ РУЛЕТКИ ==========

def parse_bet_amount(amount_str):
    """Парсит сумму ставки с поддержкой к, кк, ккк, кккк"""
    amount_str = amount_str.lower().strip()
    
    # Словарь для перевода
    multipliers = {
        'к': 1000,
        'кк': 1000000,
        'ккк': 1000000000,
        'кккк': 1000000000000,
        'kk': 1000,
        'kkk': 1000000,
        'kkkk': 1000000000,
        'kkkkk': 1000000000000,
    }
    
    # Проверяем, не "все" ли это
    if amount_str in ['все', 'алл', 'максимум', 'всё', 'all', 'max']:
        return -1
    
    # Пытаемся распарсить число с суффиксом
    for suffix, multiplier in multipliers.items():
        if amount_str.endswith(suffix):
            try:
                num = float(amount_str[:-len(suffix)])
                return int(num * multiplier)
            except:
                pass
    
    # Если нет суффикса - просто число
    try:
        return int(amount_str)
    except:
        return None

def parse_roulette_bet(text):
    """Парсит сообщение вида 'рул крас 1000' или 'рул крас все'"""
    text = text.lower().strip()
    words = text.split()
    
    if not (words[0].startswith('рул') or words[0].startswith('рулетка')):
        return None
    
    if len(words) != 3:
        return None
    
    bet_word = words[1]
    bet_value = words[2]
    
    # Парсим сумму
    bet_amount = parse_bet_amount(bet_value)
    if bet_amount is None:
        return None
    
    bet_types = {
        'крас': 'red', 'красное': 'red',
        'чер': 'black', 'черное': 'black',
        'чет': 'even', 'четное': 'even',
        'нечет': 'odd', 'нечетное': 'odd',
        'бол': 'high', 'большое': 'high',
        'мал': 'low', 'маленькое': 'low',
        '1-12': '1-12',
        '13-24': '13-24',
        '25-36': '25-36',
        'зеро': '0',
    }
    
    for key, value in bet_types.items():
        if bet_word == key or bet_word in key.split():
            return (value, bet_amount)
    
    if bet_word.isdigit():
        num = int(bet_word)
        if 0 <= num <= 36:
            return (f'num_{num}', bet_amount)
    
    return None

def update_roulette_stats(user_id, bet_amount, win_amount):
    """Обновляет статистику рулетки"""
    try:
        conn = get_db()
        cursor = conn.cursor()
        
        stats = cursor.execute('SELECT * FROM roulette_stats WHERE user_id = ?', (user_id,)).fetchone()
        
        if stats:
            games_played = stats['games_played'] + 1
            total_bet = stats['total_bet'] + bet_amount
            wins = stats['wins'] + (1 if win_amount > 0 else 0)
            losses = stats['losses'] + (1 if win_amount == 0 else 0)
            
            # Выигрыш добавляем только если реально выиграл
            total_win = stats['total_win'] + (win_amount if win_amount > 0 else 0)
            
            # Проигрыш добавляем только если реально проиграл (поставил и не выиграл)
            total_lose = stats['total_lose'] + (bet_amount if win_amount == 0 else 0)
            
            biggest_win = max(stats['biggest_win'], win_amount) if win_amount > 0 else stats['biggest_win']
            biggest_lose = max(stats['biggest_lose'], bet_amount) if win_amount == 0 else stats['biggest_lose']
            
            cursor.execute('''
                UPDATE roulette_stats 
                SET games_played = ?, wins = ?, losses = ?,
                    total_bet = ?, total_win = ?, total_lose = ?,
                    biggest_win = ?, biggest_lose = ?, last_game = ?
                WHERE user_id = ?
            ''', (games_played, wins, losses, total_bet, total_win, total_lose,
                  biggest_win, biggest_lose, datetime.now().isoformat(), user_id))
        else:
            wins = 1 if win_amount > 0 else 0
            losses = 1 if win_amount == 0 else 0
            biggest_win = win_amount if win_amount > 0 else 0
            biggest_lose = bet_amount if win_amount == 0 else 0
            
            cursor.execute('''
                INSERT INTO roulette_stats 
                (user_id, games_played, wins, losses, total_bet, total_win, total_lose, biggest_win, biggest_lose, last_game)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (user_id, 1, wins, losses, bet_amount, 
                  (win_amount if win_amount > 0 else 0), 
                  (bet_amount if win_amount == 0 else 0), 
                  biggest_win, biggest_lose, datetime.now().isoformat()))
        
        conn.commit()
        conn.close()
        return True
    except Exception as e:
        print(f"Ошибка обновления статистики рулетки: {e}")
        return False

def get_roulette_stats(user_id):
    """Получает статистику рулетки пользователя"""
    try:
        conn = get_db()
        cursor = conn.cursor()
        stats = cursor.execute('SELECT * FROM roulette_stats WHERE user_id = ?', (user_id,)).fetchone()
        conn.close()
        return stats
    except:
        return None

def get_roulette_result(number):
    """Определяет цвет и название числа"""
    if number == 0:
        return {'name': 'Зеро', 'emoji': '🟢', 'color': 'green'}
    
    red_numbers = [1,3,5,7,9,12,14,16,18,19,21,23,25,27,30,32,34,36]
    if number in red_numbers:
        return {'name': 'Красное', 'emoji': '🔴', 'color': 'red'}
    else:
        return {'name': 'Черное', 'emoji': '⚫', 'color': 'black'}

def check_roulette_win(number, bet_type, bet_amount):
    """Проверяет выигрыш в рулетке"""
    
    if bet_type == 'red':
        red_numbers = [1,3,5,7,9,12,14,16,18,19,21,23,25,27,30,32,34,36]
        if number in red_numbers:
            return bet_amount * 2
    
    elif bet_type == 'black':
        black_numbers = [2,4,6,8,10,11,13,15,17,20,22,24,26,28,29,31,33,35]
        if number in black_numbers:
            return bet_amount * 2
    
    elif bet_type == 'even':
        if number != 0 and number % 2 == 0:
            return bet_amount * 2
    
    elif bet_type == 'odd':
        if number % 2 == 1:
            return bet_amount * 2
    
    elif bet_type == 'high':
        if 19 <= number <= 36:
            return bet_amount * 2
    
    elif bet_type == 'low':
        if 1 <= number <= 18:
            return bet_amount * 2
    
    elif bet_type == '1-12':
        if 1 <= number <= 12:
            return bet_amount * 3
    
    elif bet_type == '13-24':
        if 13 <= number <= 24:
            return bet_amount * 3
    
    elif bet_type == '25-36':
        if 25 <= number <= 36:
            return bet_amount * 3
    
    elif bet_type == '0':
        if number == 0:
            return bet_amount * 36
    
    elif bet_type.startswith('num_'):
        target = int(bet_type.split('_')[1])
        if number == target:
            return bet_amount * 36
    
    return 0

def generate_animation(final_number):
    """Генерирует анимацию выпадения"""
    numbers = []
    for _ in range(5):
        numbers.append(str(random.randint(0, 36)))
    numbers.append(str(final_number))
    
    return "[" + "] [".join(numbers) + "]"

def get_bet_name(bet_type):
    """Возвращает название ставки"""
    names = {
        'red': '🔴 КРАСНОЕ',
        'black': '⚫ ЧЕРНОЕ',
        'even': '💰 ЧЕТНОЕ',
        'odd': '📊 НЕЧЕТНОЕ',
        'high': '📈 БОЛЬШОЕ (19-36)',
        'low': '📉 МАЛЕНЬКОЕ (1-18)',
        '1-12': '🎯 1-12',
        '13-24': '🎯 13-24',
        '25-36': '🎯 25-36',
        '0': '🎰 ЗЕРО',
    }
    
    if bet_type.startswith('num_'):
        number = bet_type.split('_')[1]
        return f"⚡ ЧИСЛО {number}"
    
    return names.get(bet_type, bet_type)

# ========== ФУНКЦИИ ДЛЯ МИНИ-ИГР ==========

def update_work_stats(user_id, job_type, score, time_spent, earned):
    """Обновляет статистику работ"""
    try:
        conn = get_db()
        cursor = conn.cursor()
        
        stats = cursor.execute('SELECT * FROM work_stats WHERE user_id = ? AND job_type = ?', 
                              (user_id, job_type)).fetchone()
        
        if stats:
            games_played = stats['games_played'] + 1
            perfect_games = stats['perfect_games'] + (1 if score == 100 else 0)
            best_time = min(stats['best_time'], time_spent) if stats['best_time'] > 0 else time_spent
            total_earned = stats['total_earned'] + earned
            avg_score = (stats['avg_score'] * stats['games_played'] + score) // games_played
            
            cursor.execute('''
                UPDATE work_stats 
                SET games_played = ?, perfect_games = ?, best_time = ?,
                    total_earned = ?, avg_score = ?
                WHERE user_id = ? AND job_type = ?
            ''', (games_played, perfect_games, best_time, total_earned, avg_score, user_id, job_type))
        else:
            cursor.execute('''
                INSERT INTO work_stats (user_id, job_type, games_played, perfect_games, best_time, total_earned, avg_score)
                VALUES (?, ?, 1, ?, ?, ?, ?)
            ''', (user_id, job_type, 1 if score == 100 else 0, time_spent, earned, score))
        
        conn.commit()
        conn.close()
        return True
    except Exception as e:
        print(f"Ошибка обновления статистики работ: {e}")
        return False

def start_loader_game(user_id, job_name):
    """Игра для грузчика - собирай коробки"""
    
    # Создаем поле 3x3 с коробками
    boxes = list(range(1, 10))
    random.shuffle(boxes)
    target_boxes = random.sample(range(1, 10), 3)  # 3 цели
    
    markup = types.InlineKeyboardMarkup(row_width=3)
    row = []
    for i in range(9):
        btn = types.InlineKeyboardButton(f"📦 {i+1}", callback_data=f"loader_{i+1}")
        row.append(btn)
        if (i+1) % 3 == 0:
            markup.row(*row)
            row = []
    
    game_data = {
        'boxes': boxes,
        'targets': target_boxes,
        'collected': [],
        'start_time': time.time()
    }
    
    # Сохраняем состояние игры в памяти
    loader_games[user_id] = game_data
    
    msg = (
        f"🚚 **{job_name} - Загрузи фуру!**\n\n"
        f"🎯 Нужно найти коробки с номерами: {target_boxes}\n"
        f"📦 Нажимай на кнопки с правильными номерами!\n\n"
        f"⏱️ Время пошло!"
    )
    
    return markup, msg

def check_loader_click(user_id, box_num):
    """Проверяет клик в игре грузчика"""
    if user_id not in loader_games:
        return None
    
    game = loader_games[user_id]
    
    if box_num in game['targets'] and box_num not in game['collected']:
        game['collected'].append(box_num)
        
        if len(game['collected']) == len(game['targets']):
            # Победа!
            time_spent = time.time() - game['start_time']
            score = 100  # Идеально
            del loader_games[user_id]
            return {'win': True, 'time': time_spent, 'score': score}
    
    return {'win': False, 'collected': len(game['collected']), 'total': len(game['targets'])}

def start_courier_game(user_id, job_name):
    """Игра для курьера - выбери маршрут"""
    
    routes = [
        {'name': 'Кратчайший', 'time': 15, 'correct': True},
        {'name': 'Быстрый', 'time': 25, 'correct': False},
        {'name': 'Объезд', 'time': 40, 'correct': False}
    ]
    random.shuffle(routes)
    
    markup = types.InlineKeyboardMarkup(row_width=1)
    for r in routes:
        markup.add(types.InlineKeyboardButton(
            f"🚦 {r['name']} ({r['time']} сек)", 
            callback_data=f"courier_{r['correct']}_{r['time']}"
        ))
    
    courier_games[user_id] = {'start_time': time.time()}
    
    msg = (
        f"📦 **{job_name} - Выбери маршрут!**\n\n"
        f"🗺️ Нужно доставить заказ за 30 секунд\n"
        f"Какой маршрут выберешь?\n\n"
        f"⏱️ Время пошло!"
    )
    
    return markup, msg

def check_courier_choice(user_id, is_correct, route_time):
    """Проверяет выбор курьера"""
    if user_id not in courier_games:
        return None
    
    time_spent = time.time() - courier_games[user_id]['start_time']
    del courier_games[user_id]
    
    if is_correct == 'True' and time_spent <= route_time:
        return {'win': True, 'time': time_spent, 'score': 100}
    else:
        return {'win': False, 'time': time_spent, 'score': 0}

def start_programmer_game(user_id, job_name):
    """Игра для программиста - найди баг"""
    
    bugs = [
        {'code': 'x = 10\ny = "5"\nprint(x + y)', 'answer': 'Тип данных', 'correct': 1},
        {'code': 'for i in range(10)\n    print(i)', 'answer': 'Синтаксис', 'correct': 2},
        {'code': 'if x = 5:\n    print("ok")', 'answer': 'Синтаксис', 'correct': 2}
    ]
    bug = random.choice(bugs)
    
    markup = types.InlineKeyboardMarkup(row_width=1)
    options = ['Тип данных', 'Синтаксис', 'Логика']
    for i, opt in enumerate(options, 1):
        callback = f"programmer_{'correct' if i == bug['correct'] else 'wrong'}"
        markup.add(types.InlineKeyboardButton(f"{opt}", callback_data=callback))
    
    programmer_games[user_id] = {'start_time': time.time()}
    
    msg = (
        f"💻 **{job_name} - Найди баг!**\n\n"
        f"```python\n{bug['code']}\n```\n\n"
        f"❓ Какая здесь ошибка?\n\n"
        f"⏱️ Время пошло!"
    )
    
    return markup, msg

def check_programmer_choice(user_id, is_correct):
    """Проверяет выбор программиста"""
    if user_id not in programmer_games:
        return None
    
    time_spent = time.time() - programmer_games[user_id]['start_time']
    del programmer_games[user_id]
    
    if is_correct == 'correct':
        score = max(100 - int(time_spent), 50)  # Чем быстрее, тем выше балл
        return {'win': True, 'time': time_spent, 'score': score}
    else:
        return {'win': False, 'time': time_spent, 'score': 0}

# ========== НОВЫЕ ФУНКЦИИ ДЛЯ ЧАТА ==========

def send_profile_to_chat(chat_id, user_id, target_id=None):
    """Отправляет профиль в чат"""
    if target_id is None:
        target_id = user_id
    
    user_data = get_user_profile(target_id)
    if not user_data:
        bot.send_message(chat_id, "❌ Пользователь не найден")
        return
    
    balance = get_balance(target_id)
    display_name = get_user_display_name(user_data)
    current_city = get_user_city(target_id)
    
    stats = get_user_stats(target_id)
    exp, level, work_count, total = stats
    
    equipped_clothes = get_user_equipped_clothes(target_id)
    clothes_info = f", одет: {equipped_clothes['name']}" if equipped_clothes else ""
    
    business = get_user_business(target_id)
    business_info = "Нет" if not business else f"{business['business_name']} (ур.{business['level']})"
    
    msg = f"👤 **ПРОФИЛЬ ИГРОКА**\n\n"
    msg += f"👤 Игрок: {display_name}{clothes_info}\n"
    msg += f"📍 Город: {current_city}\n"
    msg += f"💰 Баланс: {balance:,} {CURRENCY}\n"
    msg += f"⭐ Опыт: {exp} (ур.{level})\n"
    msg += f"🔨 Работ: {work_count}\n"
    msg += f"💵 Всего заработано: {total:,}\n"
    msg += f"🏭 Бизнес: {business_info}\n"
    
    if business:
        msg += f"📦 Сырье: {business['raw_material']}/1000\n"
        msg += f"💰 Прибыль на складе: {business['stored_profit']:,}"
    
    # Статистика рулетки
    roulette_stats = get_roulette_stats(target_id)
    if roulette_stats:
        profit = roulette_stats['total_win'] - roulette_stats['total_lose']
        profit_sign = "+" if profit >= 0 else ""
        win_rate = (roulette_stats['wins'] / roulette_stats['games_played'] * 100) if roulette_stats['games_played'] > 0 else 0
        
        msg += f"\n\n🎰 **РУЛЕТКА:**\n"
        msg += f"🎮 Игр: {roulette_stats['games_played']} | Побед: {win_rate:.1f}%\n"
        msg += f"💰 Выиграно: {roulette_stats['total_win']:,}\n"
        msg += f"💸 Проиграно: {roulette_stats['total_lose']:,}\n"
        msg += f"📈 Прибыль: {profit_sign}{profit:,}"
    
    # Отправляем фото профиля если есть
    photo_url = get_user_profile_photo(target_id)
    if photo_url:
        bot.send_photo(chat_id, photo_url, caption=msg, parse_mode="Markdown")
    else:
        bot.send_message(chat_id, msg, parse_mode="Markdown")

def process_raw_order(user_id, chat_id):
    """Обрабатывает заказ сырья 'все'"""
    business = get_user_business(user_id)
    if not business:
        bot.send_message(chat_id, "❌ У тебя нет бизнеса!")
        return
    
    data = get_business_data(business['business_name'])
    if not data:
        bot.send_message(chat_id, "❌ Ошибка загрузки данных бизнеса")
        return
    
    balance = get_balance(user_id)
    raw_cost = data['raw_cost_per_unit']
    max_by_money = balance // raw_cost
    
    total_raw = business['raw_material'] + business['raw_in_delivery']
    free_space = 1000 - total_raw
    
    amount = min(max_by_money, free_space)
    
    if amount <= 0:
        if free_space <= 0:
            bot.send_message(chat_id, f"❌ Склад переполнен! Свободно места: 0/1000")
        else:
            bot.send_message(chat_id, f"❌ У тебя недостаточно денег! Нужно минимум {raw_cost:,} {CURRENCY}")
        return
    
    total_cost = amount * raw_cost
    
    if not add_balance(user_id, -total_cost):
        bot.send_message(chat_id, "❌ Ошибка при списании денег")
        return
    
    if has_active_delivery(user_id):
        bot.send_message(chat_id, "❌ У тебя уже есть активная доставка! Дождись её завершения.")
        add_balance(user_id, total_cost)
        return
    
    conn = get_db()
    cursor = conn.cursor()
    
    end_time = datetime.now() + timedelta(minutes=15)
    cursor.execute('''
        INSERT INTO deliveries (user_id, amount, end_time, delivered)
        VALUES (?, ?, ?, 0)
    ''', (user_id, amount, end_time.isoformat()))
    
    cursor.execute('''
        UPDATE businesses 
        SET raw_in_delivery = raw_in_delivery + ?,
            total_invested = total_invested + ?
        WHERE user_id = ?
    ''', (amount, total_cost, user_id))
    
    conn.commit()
    conn.close()
    
    new_total = total_raw + amount
    bot.send_message(chat_id, f"✅ Заказ на {amount} сырья оформлен!\n💰 Стоимость: {total_cost:,} {CURRENCY}\n📦 Будет: {new_total}/1000\n⏱️ Доставка через 15 минут")

def send_top_to_chat(chat_id):
    """Отправляет топ в чат"""
    try:
        conn = get_db()
        cursor = conn.cursor()
        cursor.execute('SELECT first_name, username, custom_name, balance FROM users ORDER BY balance DESC LIMIT 10')
        top = cursor.fetchall()
        conn.close()
        
        if not top:
            bot.send_message(chat_id, "❌ В топе пока никого нет!")
            return
        
        msg = "🏆 **ТОП 10 БОГАЧЕЙ**\n\n"
        for i, (first_name, username, custom_name, balance) in enumerate(top, 1):
            medal = "🥇" if i == 1 else "🥈" if i == 2 else "🥉" if i == 3 else f"{i}."
            
            if custom_name:
                display_name = custom_name
            elif username and username != "NoUsername":
                display_name = f"@{username}"
            else:
                display_name = first_name
            
            msg += f"{medal} {display_name}: {balance:,} {CURRENCY}\n"
        
        bot.send_message(chat_id, msg, parse_mode="Markdown")
    except Exception as e:
        print(f"Ошибка топа: {e}")
        bot.send_message(chat_id, "❌ Ошибка загрузки топа")

# ========== ХРАНИЛИЩЕ ДЛЯ ИГР ==========
loader_games = {}
courier_games = {}
programmer_games = {}

# ========== АДМИН КОМАНДЫ ==========
@bot.message_handler(commands=['adminhelp'])
def admin_help(message):
    user_id = message.from_user.id
    level = get_admin_level(user_id)
    
    if level == 0:
        bot.reply_to(message, "❌ Эта команда только для администраторов!")
        return
    
    help_text = f"👑 **АДМИН ПАНЕЛЬ (Уровень {level})**\n\n"
    
    help_text += "**Уровень 1:**\n"
    help_text += "  /giveme [сумма] - выдать деньги себе\n"
    help_text += "  /addexpm [количество] - выдать опыт себе\n\n"
    
    if level >= 2:
        help_text += "**Уровень 2:**\n"
        help_text += "  /give [@user или ник] [сумма] - выдать деньги\n"
        help_text += "  /addexp [@user или ник] [количество] - выдать опыт\n"
        help_text += "  /profile [@user или ник] - посмотреть профиль\n\n"
    
    if level >= 3:
        help_text += "**Уровень 3:**\n"
        help_text += "  /addadmin [@user или ник] [уровень] - назначить админа\n"
        help_text += "  /adminlist - список админов\n"
        help_text += "  /reset [@user или ник] - обнулить аккаунт\n"
        help_text += "  /wipe [@user или ник] - стереть баланс и опыт\n\n"
    
    if level >= 4:
        help_text += "**Уровень 4:**\n"
        help_text += "  /removeadmin [@user или ник] - снять админа\n"
        help_text += "  /setadminlevel [@user или ник] [уровень] - изменить уровень\n"
        help_text += "  /ban [@user или ник] [часы] - забанить (0 = навсегда)\n"
        help_text += "  /unban [@user или ник] - разбанить\n"
        help_text += "  /warn [@user или ник] - выдать варн\n"
        help_text += "  /warns [@user или ник] - показать варны\n"
    
    bot.reply_to(message, help_text, parse_mode="Markdown")

@bot.message_handler(commands=['giveme'])
def give_me(message):
    user_id = message.from_user.id
    
    if not is_admin(user_id, 1):
        bot.reply_to(message, "❌ У тебя нет прав администратора 1 уровня!")
        return
    
    try:
        parts = message.text.split()
        if len(parts) != 2:
            bot.reply_to(message, "❌ Формат: /giveme [сумма]")
            return
        
        amount = int(parts[1])
        
        if add_balance(user_id, amount):
            new_balance = get_balance(user_id)
            bot.reply_to(message, f"✅ Выдано {amount} {CURRENCY} себе\nНовый баланс: {new_balance}")
        else:
            bot.reply_to(message, "❌ Ошибка при выдаче денег")
            
    except ValueError:
        bot.reply_to(message, "❌ Сумма должна быть числом")

@bot.message_handler(commands=['addexpm'])
def add_exp_me(message):
    user_id = message.from_user.id
    
    if not is_admin(user_id, 1):
        bot.reply_to(message, "❌ У тебя нет прав администратора 1 уровня!")
        return
    
    try:
        parts = message.text.split()
        if len(parts) != 2:
            bot.reply_to(message, "❌ Формат: /addexpm [количество]")
            return
        
        amount = int(parts[1])
        
        if add_exp(user_id, amount):
            new_stats = get_user_stats(user_id)
            bot.reply_to(message, f"✅ Выдано {amount}⭐ опыта себе\nТеперь опыта: {new_stats[0]}, уровень: {new_stats[1]}")
        else:
            bot.reply_to(message, "❌ Ошибка при выдаче опыта")
            
    except ValueError:
        bot.reply_to(message, "❌ Количество должно быть числом")

@bot.message_handler(commands=['give'])
def give_money(message):
    user_id = message.from_user.id
    
    if not is_admin(user_id, 2):
        bot.reply_to(message, "❌ У тебя нет прав администратора 2 уровня!")
        return
    
    try:
        parts = message.text.split()
        
        if len(parts) == 2:
            amount = int(parts[1])
            if add_balance(user_id, amount):
                new_balance = get_balance(user_id)
                bot.reply_to(message, f"✅ Выдано {amount} {CURRENCY} себе\nНовый баланс: {new_balance}")
            else:
                bot.reply_to(message, "❌ Ошибка при выдаче денег")
        
        elif len(parts) == 3:
            target_input = parts[1]
            amount = int(parts[2])
            
            user_data = find_user_by_input(target_input)
            
            if not user_data:
                bot.reply_to(message, f"❌ Пользователь {target_input} не найден")
                return
            
            target_id = user_data[0]
            display_name = get_user_display_name(user_data)
            
            if add_balance(target_id, amount):
                new_balance = get_balance(target_id)
                bot.send_message(target_id, f"💰 Админ выдал тебе {amount} {CURRENCY}!\nБаланс: {new_balance}")
                bot.reply_to(message, f"✅ Выдано {amount} {CURRENCY} {display_name}\nНовый баланс: {new_balance}")
            else:
                bot.reply_to(message, "❌ Ошибка при выдаче денег")
        
        else:
            bot.reply_to(message, "❌ Формат: /give [сумма] - себе\n/give [@user или ник] [сумма] - другому")
            
    except ValueError:
        bot.reply_to(message, "❌ Сумма должна быть числом")
    except Exception as e:
        bot.reply_to(message, f"❌ Ошибка: {e}")

@bot.message_handler(commands=['addexp'])
def add_exp_command(message):
    user_id = message.from_user.id
    
    if not is_admin(user_id, 2):
        bot.reply_to(message, "❌ У тебя нет прав администратора 2 уровня!")
        return
    
    try:
        parts = message.text.split()
        
        if len(parts) == 2:
            amount = int(parts[1])
            if add_exp(user_id, amount):
                new_stats = get_user_stats(user_id)
                bot.reply_to(message, f"✅ Выдано {amount}⭐ опыта себе\nТеперь опыта: {new_stats[0]}, уровень: {new_stats[1]}")
            else:
                bot.reply_to(message, "❌ Ошибка при выдаче опыта")
        
        elif len(parts) == 3:
            target_input = parts[1]
            amount = int(parts[2])
            
            user_data = find_user_by_input(target_input)
            
            if not user_data:
                bot.reply_to(message, f"❌ Пользователь {target_input} не найден")
                return
            
            target_id = user_data[0]
            display_name = get_user_display_name(user_data)
            
            if add_exp(target_id, amount):
                new_stats = get_user_stats(target_id)
                bot.send_message(target_id, f"⭐ Админ выдал тебе {amount} опыта!")
                bot.reply_to(message, f"✅ Выдано {amount}⭐ опыта {display_name}\nТеперь опыта: {new_stats[0]}, уровень: {new_stats[1]}")
            else:
                bot.reply_to(message, "❌ Ошибка при выдаче опыта")
        
        else:
            bot.reply_to(message, "❌ Формат: /addexp [количество] - себе\n/addexp [@user или ник] [количество] - другому")
            
    except ValueError:
        bot.reply_to(message, "❌ Количество опыта должно быть числом")
    except Exception as e:
        bot.reply_to(message, f"❌ Ошибка: {e}")

@bot.message_handler(commands=['profile'])
def profile_command(message):
    user_id = message.from_user.id
    
    if not is_admin(user_id, 2):
        bot.reply_to(message, "❌ У тебя нет прав администратора 2 уровня!")
        return
    
    try:
        parts = message.text.split()
        
        if len(parts) != 2:
            bot.reply_to(message, "❌ Формат: /profile [@user или ник]")
            return
        
        target_input = parts[1]
        
        user_data = find_user_by_input(target_input)
        
        if not user_data:
            bot.reply_to(message, f"❌ Пользователь {target_input} не найден")
            return
        
        target_id = user_data[0]
        display_name = get_user_display_name(user_data)
        
        send_profile_to_chat(message.chat.id, user_id, target_id)
        
    except Exception as e:
        bot.reply_to(message, f"❌ Ошибка: {e}")

@bot.message_handler(commands=['addadmin'])
def add_admin_command(message):
    user_id = message.from_user.id
    
    if not is_admin(user_id, 3):
        bot.reply_to(message, "❌ У тебя нет прав администратора 3 уровня!")
        return
    
    try:
        parts = message.text.split()
        
        if len(parts) != 3:
            bot.reply_to(message, "❌ Формат: /addadmin [@user или ник] [уровень]")
            return
        
        target_input = parts[1]
        level = int(parts[2])
        
        if level < 1 or level > 3:
            bot.reply_to(message, "❌ Уровень должен быть от 1 до 3")
            return
        
        user_data = find_user_by_input(target_input)
        
        if not user_data:
            bot.reply_to(message, f"❌ Пользователь {target_input} не найден")
            return
        
        target_id = user_data[0]
        display_name = get_user_display_name(user_data)
        
        success, msg_text = add_admin(target_id, level)
        if success:
            bot.send_message(target_id, f"👑 Вам выданы права администратора {level} уровня!\n/adminhelp - список команд")
            bot.reply_to(message, f"✅ Пользователь {display_name} теперь администратор {level} уровня!")
        else:
            bot.reply_to(message, msg_text)
            
    except ValueError:
        bot.reply_to(message, "❌ Уровень должен быть числом")
    except Exception as e:
        bot.reply_to(message, f"❌ Ошибка: {e}")

@bot.message_handler(commands=['adminlist'])
def admin_list(message):
    user_id = message.from_user.id
    
    if not is_admin(user_id, 3):
        bot.reply_to(message, "❌ У тебя нет прав администратора 3 уровня!")
        return
    
    admins_info = []
    for admin_id, level in ADMINS.items():
        try:
            user_data = get_user_profile(admin_id)
            if user_data:
                display = get_user_display_name((user_data[0], user_data[1], user_data[2], user_data[3], 0))
                admins_info.append(f"• {display} - уровень {level} (`{admin_id}`)")
            else:
                admins_info.append(f"• Админ с ID: `{admin_id}` - уровень {level}")
        except:
            admins_info.append(f"• Админ с ID: `{admin_id}` - уровень {level}")
    
    msg = "👑 **СПИСОК АДМИНИСТРАТОРОВ**\n\n" + "\n".join(admins_info)
    bot.reply_to(message, msg, parse_mode="Markdown")

@bot.message_handler(commands=['reset'])
def reset_account(message):
    user_id = message.from_user.id
    
    if not is_admin(user_id, 3):
        bot.reply_to(message, "❌ У тебя нет прав администратора 3 уровня!")
        return
    
    try:
        parts = message.text.split()
        
        if len(parts) != 2:
            bot.reply_to(message, "❌ Формат: /reset [@user или ник]")
            return
        
        target_input = parts[1]
        user_data = find_user_by_input(target_input)
        
        if not user_data:
            bot.reply_to(message, f"❌ Пользователь {target_input} не найден")
            return
        
        target_id = user_data[0]
        display_name = get_user_display_name(user_data)
        
        conn = get_db()
        cursor = conn.cursor()
        
        cursor.execute('DELETE FROM businesses WHERE user_id = ?', (target_id,))
        cursor.execute('DELETE FROM deliveries WHERE user_id = ?', (target_id,))
        cursor.execute('DELETE FROM user_clothes WHERE user_id = ?', (target_id,))
        cursor.execute('DELETE FROM travels WHERE user_id = ?', (target_id,))
        cursor.execute('DELETE FROM warns WHERE user_id = ?', (target_id,))
        cursor.execute('DELETE FROM bans WHERE user_id = ?', (target_id,))
        cursor.execute('DELETE FROM roulette_stats WHERE user_id = ?', (target_id,))
        cursor.execute('DELETE FROM work_stats WHERE user_id = ?', (target_id,))
        
        cursor.execute('''
            UPDATE users 
            SET balance = 0, exp = 0, level = 1, work_count = 0, 
                total_earned = 0, custom_name = NULL, equipped_clothes = NULL,
                current_city = 'Село Молочное', has_car = 0, has_plane = 0
            WHERE user_id = ?
        ''', (target_id,))
        
        conn.commit()
        conn.close()
        
        if target_id in WARNS:
            del WARNS[target_id]
        if target_id in BANS:
            del BANS[target_id]
        
        bot.send_message(target_id, "♻️ Ваш аккаунт был полностью сброшен администратором.")
        bot.reply_to(message, f"✅ Аккаунт {display_name} полностью обнулен")
        
    except Exception as e:
        bot.reply_to(message, f"❌ Ошибка: {e}")

@bot.message_handler(commands=['wipe'])
def wipe_account(message):
    user_id = message.from_user.id
    
    if not is_admin(user_id, 3):
        bot.reply_to(message, "❌ У тебя нет прав администратора 3 уровня!")
        return
    
    try:
        parts = message.text.split()
        
        if len(parts) != 2:
            bot.reply_to(message, "❌ Формат: /wipe [@user или ник]")
            return
        
        target_input = parts[1]
        user_data = find_user_by_input(target_input)
        
        if not user_data:
            bot.reply_to(message, f"❌ Пользователь {target_input} не найден")
            return
        
        target_id = user_data[0]
        display_name = get_user_display_name(user_data)
        
        conn = get_db()
        cursor = conn.cursor()
        
        cursor.execute('UPDATE users SET balance = 0, exp = 0, level = 1 WHERE user_id = ?', (target_id,))
        
        conn.commit()
        conn.close()
        
        bot.send_message(target_id, "🧹 Ваши баланс и опыт были обнулены администратором.")
        bot.reply_to(message, f"✅ Баланс и опыт {display_name} обнулены")
        
    except Exception as e:
        bot.reply_to(message, f"❌ Ошибка: {e}")

@bot.message_handler(commands=['ban'])
def ban_user(message):
    user_id = message.from_user.id
    
    if not is_admin(user_id, 4):
        bot.reply_to(message, "❌ У тебя нет прав администратора 4 уровня!")
        return
    
    try:
        parts = message.text.split()
        
        if len(parts) not in [2, 3]:
            bot.reply_to(message, "❌ Формат: /ban [@user или ник] [часы]\n/ban [@user или ник] 0 - навсегда")
            return
        
        target_input = parts[1]
        hours = int(parts[2]) if len(parts) == 3 else 0
        
        user_data = find_user_by_input(target_input)
        
        if not user_data:
            bot.reply_to(message, f"❌ Пользователь {target_input} не найден")
            return
        
        target_id = user_data[0]
        display_name = get_user_display_name(user_data)
        
        if add_ban(target_id, hours, "admin"):
            ban_text = "навсегда" if hours == 0 else f"на {hours} ч."
            bot.send_message(target_id, f"🔨 Вы забанены администратором {ban_text}")
            bot.reply_to(message, f"✅ Пользователь {display_name} забанен {ban_text}")
        else:
            bot.reply_to(message, "❌ Ошибка при бане")
        
    except ValueError:
        bot.reply_to(message, "❌ Часы должны быть числом")
    except Exception as e:
        bot.reply_to(message, f"❌ Ошибка: {e}")

@bot.message_handler(commands=['unban'])
def unban_user(message):
    user_id = message.from_user.id
    
    if not is_admin(user_id, 4):
        bot.reply_to(message, "❌ У тебя нет прав администратора 4 уровня!")
        return
    
    try:
        parts = message.text.split()
        
        if len(parts) != 2:
            bot.reply_to(message, "❌ Формат: /unban [@user или ник]")
            return
        
        target_input = parts[1]
        user_data = find_user_by_input(target_input)
        
        if not user_data:
            bot.reply_to(message, f"❌ Пользователь {target_input} не найден")
            return
        
        target_id = user_data[0]
        display_name = get_user_display_name(user_data)
        
        if remove_ban(target_id):
            bot.send_message(target_id, "✅ Вы разбанены администратором")
            bot.reply_to(message, f"✅ Пользователь {display_name} разбанен")
        else:
            bot.reply_to(message, f"❌ Ошибка при разбане")
        
    except Exception as e:
        bot.reply_to(message, f"❌ Ошибка: {e}")

@bot.message_handler(commands=['warn'])
def warn_user(message):
    user_id = message.from_user.id
    
    if not is_admin(user_id, 4):
        bot.reply_to(message, "❌ У тебя нет прав администратора 4 уровня!")
        return
    
    try:
        parts = message.text.split()
        
        if len(parts) != 2:
            bot.reply_to(message, "❌ Формат: /warn [@user или ник]")
            return
        
        target_input = parts[1]
        user_data = find_user_by_input(target_input)
        
        if not user_data:
            bot.reply_to(message, f"❌ Пользователь {target_input} не найден")
            return
        
        target_id = user_data[0]
        display_name = get_user_display_name(user_data)
        
        banned, msg_text = add_warn(target_id)
        
        bot.send_message(target_id, msg_text)
        bot.reply_to(message, f"✅ Варн выдан {display_name}\n{msg_text}")
        
    except Exception as e:
        bot.reply_to(message, f"❌ Ошибка: {e}")

@bot.message_handler(commands=['warns'])
def show_warns(message):
    user_id = message.from_user.id
    
    if not is_admin(user_id, 4):
        bot.reply_to(message, "❌ У тебя нет прав администратора 4 уровня!")
        return
    
    try:
        parts = message.text.split()
        
        if len(parts) != 2:
            bot.reply_to(message, "❌ Формат: /warns [@user или ник]")
            return
        
        target_input = parts[1]
        user_data = find_user_by_input(target_input)
        
        if not user_data:
            bot.reply_to(message, f"❌ Пользователь {target_input} не найден")
            return
        
        target_id = user_data[0]
        display_name = get_user_display_name(user_data)
        warns = get_warns(target_id)
        
        bot.reply_to(message, f"⚠️ У {display_name} {warns}/3 варнов")
        
    except Exception as e:
        bot.reply_to(message, f"❌ Ошибка: {e}")

@bot.message_handler(commands=['removeadmin'])
def remove_admin_command(message):
    user_id = message.from_user.id
    
    if not is_admin(user_id, 4):
        bot.reply_to(message, "❌ У тебя нет прав администратора 4 уровня!")
        return
    
    try:
        parts = message.text.split()
        
        if len(parts) != 2:
            bot.reply_to(message, "❌ Формат: /removeadmin [@user или ник]")
            return
        
        target_input = parts[1]
        
        user_data = find_user_by_input(target_input)
        
        if not user_data:
            bot.reply_to(message, f"❌ Пользователь {target_input} не найден")
            return
        
        target_id = user_data[0]
        display_name = get_user_display_name(user_data)
        
        if target_id == 5596589260:
            bot.reply_to(message, "❌ Нельзя снять права с главного администратора!")
            return
        
        if remove_admin(target_id):
            bot.send_message(target_id, "👑 Ваши права администратора были сняты")
            bot.reply_to(message, f"✅ Права администратора сняты с {display_name}")
        else:
            bot.reply_to(message, f"❌ Ошибка при снятии прав")
            
    except Exception as e:
        bot.reply_to(message, f"❌ Ошибка: {e}")

@bot.message_handler(commands=['setadminlevel'])
def set_admin_level_command(message):
    user_id = message.from_user.id
    
    if not is_admin(user_id, 4):
        bot.reply_to(message, "❌ У тебя нет прав администратора 4 уровня!")
        return
    
    try:
        parts = message.text.split()
        
        if len(parts) != 3:
            bot.reply_to(message, "❌ Формат: /setadminlevel [@user или ник] [уровень]")
            return
        
        target_input = parts[1]
        level = int(parts[2])
        
        if level < 1 or level > 4:
            bot.reply_to(message, "❌ Уровень должен быть от 1 до 4")
            return
        
        user_data = find_user_by_input(target_input)
        
        if not user_data:
            bot.reply_to(message, f"❌ Пользователь {target_input} не найден")
            return
        
        target_id = user_data[0]
        display_name = get_user_display_name(user_data)
        
        if target_id == 5596589260:
            bot.reply_to(message, "❌ Нельзя изменить уровень главного администратора!")
            return
        
        if set_admin_level(target_id, level):
            bot.send_message(target_id, f"👑 Ваш уровень администратора изменен на {level}")
            bot.reply_to(message, f"✅ Уровень администратора {display_name} изменен на {level}")
        else:
            bot.reply_to(message, f"❌ Пользователь не является администратором")
            
    except ValueError:
        bot.reply_to(message, "❌ Уровень должен быть числом")
    except Exception as e:
        bot.reply_to(message, f"❌ Ошибка: {e}")

# ========== КОМАНДА ТОП ==========
@bot.message_handler(commands=['top'])
def top_command(message):
    user_id = message.from_user.id
    
    markup = types.InlineKeyboardMarkup(row_width=2)
    markup.add(
        types.InlineKeyboardButton("💰 Топ по деньгам", callback_data="top_money"),
        types.InlineKeyboardButton("⭐ Топ по опыту", callback_data="top_exp")
    )
    
    bot.send_message(
        user_id,
        "🏆 **ВЫБЕРИ ТОП**\n\n"
        "По какому показателю показать рейтинг?",
        parse_mode="Markdown",
        reply_markup=markup
    )

def send_top_by_type(user_id, top_type):
    try:
        conn = get_db()
        cursor = conn.cursor()
        
        if top_type == "money":
            cursor.execute('''
                SELECT first_name, username, custom_name, balance 
                FROM users 
                ORDER BY balance DESC 
                LIMIT 10
            ''')
            title = "💰 ТОП 10 ПО ДЕНЬГАМ"
        else:  # exp
            cursor.execute('''
                SELECT first_name, username, custom_name, exp 
                FROM users 
                ORDER BY exp DESC 
                LIMIT 10
            ''')
            title = "⭐ ТОП 10 ПО ОПЫТУ"
        
        top = cursor.fetchall()
        conn.close()
        
        if not top:
            bot.send_message(user_id, "❌ В топе пока никого нет!")
            return
        
        msg = f"🏆 **{title}**\n\n"
        for i, (first_name, username, custom_name, value) in enumerate(top, 1):
            medal = "🥇" if i == 1 else "🥈" if i == 2 else "🥉" if i == 3 else f"{i}."
            
            if custom_name:
                display_name = custom_name
            elif username and username != "NoUsername":
                display_name = f"@{username}"
            else:
                display_name = first_name
            
            msg += f"{medal} {display_name}: {value:,}\n"
        
        bot.send_message(user_id, msg, parse_mode="Markdown")
        
    except Exception as e:
        print(f"Ошибка топа: {e}")
        bot.send_message(user_id, "❌ Ошибка загрузки топа")

# ========== КЛАВИАТУРЫ ==========
def main_keyboard():
    markup = types.ReplyKeyboardMarkup(row_width=2, resize_keyboard=True)
    markup.row(
        types.KeyboardButton("💼 Работы"),
        types.KeyboardButton("🏭 Бизнесы")
    )
    markup.row(
        types.KeyboardButton("📊 Статистика"),
        types.KeyboardButton("🏙️ ГОРОДА")
    )
    markup.row(
        types.KeyboardButton("🎁 Ежедневно"),
        types.KeyboardButton("⚙️ Настройки")
    )
    markup.row(
        types.KeyboardButton("👕 МАГАЗИН ОДЕЖДЫ"),
        types.KeyboardButton("🔄")
    )
    return markup

def cities_keyboard():
    markup = types.ReplyKeyboardMarkup(row_width=2, resize_keyboard=True)
    markup.row(
        types.KeyboardButton("🏙️ Кропоткин"),
        types.KeyboardButton("🏙️ Москва")
    )
    markup.row(
        types.KeyboardButton("🏙️ Мурино"),
        types.KeyboardButton("🏙️ Село Молочное")
    )
    markup.row(types.KeyboardButton("🔙 Назад"))
    return markup

def transport_keyboard(city):
    markup = types.ReplyKeyboardMarkup(row_width=2, resize_keyboard=True)
    markup.row(
        types.KeyboardButton("🚕 Такси"),
        types.KeyboardButton("🚗 Личная машина")
    )
    markup.row(
        types.KeyboardButton("✈️ Личный самолет"),
        types.KeyboardButton("🔙 Назад")
    )
    return markup

def city_menu_keyboard(city_name):
    markup = types.ReplyKeyboardMarkup(row_width=2, resize_keyboard=True)
    
    city_info = get_city_info(city_name)
    
    markup.row(
        types.KeyboardButton("💼 Работы"),
        types.KeyboardButton("🏭 Бизнесы")
    )
    markup.row(
        types.KeyboardButton("📊 Статистика"),
        types.KeyboardButton("👕 Магазин одежды")
    )
    
    extra_buttons = []
    if city_info and city_info['has_house_shop']:
        extra_buttons.append("🏠 Магазин домов")
    if city_info and city_info['has_plane_shop']:
        extra_buttons.append("✈️ Магазин самолетов")
    
    if extra_buttons:
        markup.row(*[types.KeyboardButton(btn) for btn in extra_buttons])
    
    markup.row(
        types.KeyboardButton("🎁 Ежедневно"),
        types.KeyboardButton("⚙️ Настройки")
    )
    markup.row(
        types.KeyboardButton("🔙 Назад"),
        types.KeyboardButton("🔄")
    )
    return markup

def jobs_keyboard(user_id):
    jobs = get_available_jobs(user_id)
    markup = types.ReplyKeyboardMarkup(row_width=2, resize_keyboard=True)
    
    for job in jobs:
        markup.add(types.KeyboardButton(f"{job[5]} {job[0]}"))
    
    markup.row(types.KeyboardButton("🔙 Назад"))
    return markup

def businesses_main_keyboard():
    markup = types.ReplyKeyboardMarkup(row_width=2, resize_keyboard=True)
    markup.row(
        types.KeyboardButton("📊 Мой бизнес"),
        types.KeyboardButton("💰 Собрать прибыль")
    )
    markup.row(
        types.KeyboardButton("📦 Закупить на всё"),
        types.KeyboardButton("🏪 Купить бизнес")
    )
    markup.row(
        types.KeyboardButton("💰 Продать бизнес"),
        types.KeyboardButton("🔙 Назад")
    )
    return markup

def buy_business_keyboard():
    markup = types.ReplyKeyboardMarkup(row_width=2, resize_keyboard=True)
    markup.row(
        types.KeyboardButton("🥤 Киоск"),
        types.KeyboardButton("🍔 Фастфуд")
    )
    markup.row(
        types.KeyboardButton("🏪 Минимаркет"),
        types.KeyboardButton("⛽ Заправка")
    )
    markup.row(
        types.KeyboardButton("🏨 Отель"),
        types.KeyboardButton("🔙 Назад")
    )
    return markup

def settings_keyboard():
    markup = types.ReplyKeyboardMarkup(row_width=2, resize_keyboard=True)
    markup.row(
        types.KeyboardButton("✏️ Сменить никнейм")
    )
    markup.row(
        types.KeyboardButton("📋 Помощь")
    )
    markup.row(
        types.KeyboardButton("🔙 Назад")
    )
    return markup

# ========== СТАРТ ==========
@bot.message_handler(commands=['start'])
def start(message):
    user_id = message.from_user.id
    
    if is_banned(user_id):
        ban_info = BANS.get(user_id, {})
        if ban_info.get('until') == 0:
            bot.reply_to(message, "🔨 Вы забанены навсегда.")
        else:
            until = datetime.fromtimestamp(ban_info['until'])
            bot.reply_to(message, f"🔨 Вы забанены до {until.strftime('%d.%m.%Y %H:%M')}")
        return
    
    username = message.from_user.username or "NoUsername"
    first_name = message.from_user.first_name
    
    conn = get_db()
    cursor = conn.cursor()
    
    cursor.execute('SELECT * FROM users WHERE user_id = ?', (user_id,))
    user = cursor.fetchone()
    
    if not user:
        cursor.execute('''
            INSERT INTO users (user_id, username, first_name, balance, exp, level, work_count, total_earned, current_city)
            VALUES (?, ?, ?, 0, 0, 1, 0, 0, 'Село Молочное')
        ''', (user_id, username, first_name))
        conn.commit()
        conn.close()
        
        welcome_text = (
            "🌟 **ДОБРО ПОЖАЛОВАТЬ В МИР SuguruCoins!** 🌟\n\n"
            f"👋 Рады видеть тебя, {first_name}!\n\n"
            "🎮 Здесь ты сможешь:\n"
            "💼 **Работать** в мини-играх и зарабатывать деньги\n"
            "🏭 **Покупать бизнесы** и получать пассивный доход\n"
            "🏙️ **Путешествовать по городам** и открывать новые магазины\n"
            "👕 **Покупать крутую одежду** и менять свой стиль\n"
            "🎰 **Играть в рулетку** и выигрывать миллионы\n"
            "🏆 **Соревноваться** с другими игроками (/top)\n\n"
            "✨ Но сначала выбери себе игровой никнейм!\n"
            "Он будет отображаться в топе и в игре."
        )
        
        bot.send_message(user_id, welcome_text, parse_mode="Markdown")
        
        markup = types.ForceReply(selective=True)
        msg = bot.send_message(
            user_id, 
            "🔤 **Напиши свой игровой никнейм:**\n\n"
            "📝 Он может быть любым (буквы, цифры, символы)\n"
            "✨ Например: `DarkKnight`, `КиберПанк`, `SuguruKing`\n\n"
            "⚠️ **Важно:** Никнейм должен быть **уникальным**!",
            parse_mode="Markdown",
            reply_markup=markup
        )
        
        bot.register_next_step_handler(msg, process_name_step)
        
    else:
        conn.close()
        level = get_admin_level(user_id)
        
        welcome_text = f"👋 С возвращением, {first_name}!"
        
        if level > 0:
            welcome_text += f"\n\n👑 У вас права администратора {level} уровня!\n/adminhelp - список команд админа"
        
        bot.send_message(user_id, welcome_text)
        send_main_menu_with_profile(user_id)

def process_name_step(message):
    user_id = message.from_user.id
    custom_name = message.text.strip()
    
    if len(custom_name) < 2 or len(custom_name) > 30:
        bot.send_message(
            user_id, 
            "❌ Никнейм должен быть от 2 до 30 символов!\n\nПопробуй еще раз:"
        )
        bot.register_next_step_handler(message, process_name_step)
        return
    
    allowed_chars = set("abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_ -!@#$%^&*()")
    if not all(c in allowed_chars for c in custom_name):
        bot.send_message(
            user_id,
            "❌ Никнейм содержит недопустимые символы!\n\n"
            "Разрешены: буквы, цифры, пробел и символы _ - ! @ # $ % ^ & * ( )\n\nПопробуй еще раз:"
        )
        bot.register_next_step_handler(message, process_name_step)
        return
    
    existing_user = get_user_by_custom_name(custom_name)
    if existing_user:
        bot.send_message(
            user_id,
            f"❌ Никнейм **{custom_name}** уже занят другим игроком!\n\n"
            "Пожалуйста, выбери другой никнейм:",
            parse_mode="Markdown"
        )
        bot.register_next_step_handler(message, process_name_step)
        return
    
    if set_custom_name(user_id, custom_name):
        success_text = (
            f"✅ **Отлично!** Твой никнейм `{custom_name}` сохранен!\n\n"
            "🎉 Теперь ты готов к приключениям!\n"
            "💰 У тебя 0 монет, но это временно.\n"
            "💪 Работай в мини-играх, зарабатывай, покупай бизнесы и путешествуй!\n"
            "👕 Загляни в **МАГАЗИН ОДЕЖДЫ** - там есть очень крутые комплекты!\n"
            "🎰 А в **РУЛЕТКЕ** можешь испытать удачу!\n\n"
            "👇 Твоё главное меню с фото профиля:"
        )
        bot.send_message(user_id, success_text, parse_mode="Markdown")
        send_main_menu_with_profile(user_id)
    else:
        bot.send_message(
            user_id,
            "❌ Произошла ошибка при сохранении ника. Попробуй еще раз /start"
        )

def change_nickname_step(message):
    user_id = message.from_user.id
    new_nickname = message.text.strip()
    
    if len(new_nickname) < 2 or len(new_nickname) > 30:
        bot.send_message(
            user_id, 
            "❌ Никнейм должен быть от 2 до 30 символов!\n\nПопробуй еще раз:"
        )
        bot.register_next_step_handler(message, change_nickname_step)
        return
    
    allowed_chars = set("abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_ -!@#$%^&*()")
    if not all(c in allowed_chars for c in new_nickname):
        bot.send_message(
            user_id,
            "❌ Никнейм содержит недопустимые символы!\n\n"
            "Разрешены: буквы, цифры, пробел и символы _ - ! @ # $ % ^ & * ( )\n\nПопробуй еще раз:"
        )
        bot.register_next_step_handler(message, change_nickname_step)
        return
    
    existing_user = get_user_by_custom_name(new_nickname)
    if existing_user:
        bot.send_message(
            user_id,
            f"❌ Никнейм **{new_nickname}** уже занят другим игроком!\n\n"
            "Пожалуйста, выбери другой никнейм:",
            parse_mode="Markdown"
        )
        bot.register_next_step_handler(message, change_nickname_step)
        return
    
    user_data = get_user_profile(user_id)
    old_nickname = user_data[3] if user_data and user_data[3] else "Не установлен"
    
    if set_custom_name(user_id, new_nickname):
        success_text = (
            f"✅ **Никнейм успешно изменен!**\n\n"
            f"🔄 Старый ник: `{old_nickname}`\n"
            f"✨ Новый ник: `{new_nickname}`\n\n"
            f"Теперь ты будешь отображаться в игре под новым именем!"
        )
        bot.send_message(user_id, success_text, parse_mode="Markdown", reply_markup=settings_keyboard())
    else:
        bot.send_message(
            user_id,
            "❌ Произошла ошибка при сохранении ника. Попробуй еще раз."
        )
        bot.register_next_step_handler(message, change_nickname_step)

# ========== ОБРАБОТЧИК РУЛЕТКИ ==========
@bot.message_handler(func=lambda message: message.text and message.text.lower().strip().startswith(('рул', 'рулетка')))
def roulette_handler(message):
    user_id = message.from_user.id
    
    if is_banned(user_id):
        return
    
    bet_info = parse_roulette_bet(message.text)
    if not bet_info:
        bot.reply_to(message, 
            "❌ **Неправильный формат!**\n\n"
            "📝 **Примеры ставок:**\n"
            "• `рул крас 5000` - на красное\n"
            "• `рулетка чер все` - **ВЕСЬ БАЛАНС** на черное\n"
            "• `рул чет алл` - **ВЕСЬ БАЛАНС** на четное\n"
            "• `рул нечет максимум` - **ВЕСЬ БАЛАНС** на нечетное\n"
            "• `рул бол 15000` - на 19-36\n"
            "• `рул мал 3000` - на 1-18\n"
            "• `рул 1-12 5000` - первая дюжина\n"
            "• `рул 13-24 5000` - вторая дюжина\n"
            "• `рул 25-36 5000` - третья дюжина\n"
            "• `рул зеро все` - **ВЕСЬ БАЛАНС** на зеро\n"
            "• `рул 7 все` - **ВЕСЬ БАЛАНС** на число 7\n\n"
            "💰 **Сокращения:**\n"
            "• `1к` = 1,000\n"
            "• `5кк` = 5,000,000\n"
            "• `100кк` = 100,000,000\n"
            "• `2ккк` = 2,000,000,000\n"
            "• `1кккк` = 1,000,000,000,000\n\n"
            "💎 Для ставки всего баланса пиши: `все`, `алл` или `максимум`")
        return
    
    bet_type, bet_amount = bet_info
    
    balance = get_balance(user_id)
    
    # Если ставка = -1, значит ставим весь баланс
    if bet_amount == -1:
        bet_amount = balance
    
    if balance < bet_amount:
        bot.reply_to(message, f"❌ Недостаточно средств! Твой баланс: {balance:,} {CURRENCY}")
        return
    
    if bet_amount < 1:
        bot.reply_to(message, f"❌ Минимальная ставка: 1 {CURRENCY}")
        return
    
    number = random.randint(0, 36)
    result = get_roulette_result(number)
    
    win_amount = check_roulette_win(number, bet_type, bet_amount)
    
    if win_amount > 0:
        add_balance(user_id, win_amount - bet_amount)
        new_balance = get_balance(user_id)
        update_roulette_stats(user_id, bet_amount, win_amount)
        
        # Красивое сообщение для ALL-IN
        if bet_amount == balance and bet_amount > 0:
            allin_text = "⚡ **ALL-IN!** ⚡\n"
        else:
            allin_text = ""
        
        response = (
            f"🎡 **КРУТИМ РУЛЕТКУ!**\n\n"
            f"{allin_text}"
            f"👤 Игрок: {message.from_user.first_name}\n"
            f"💰 Ставка: {bet_amount:,} на {get_bet_name(bet_type)}\n\n"
            f"⚪ Шарик скачет по цифрам...\n"
            f"{generate_animation(number)}\n\n"
            f"🎯 Выпало: **{number} {result['emoji']} {result['name']}**!\n\n"
            f"🎉 **ВЫИГРЫШ!** +{win_amount:,}💰\n"
            f"💎 Новый баланс: {new_balance:,} {CURRENCY}"
        )
    else:
        add_balance(user_id, -bet_amount)
        new_balance = get_balance(user_id)
        update_roulette_stats(user_id, bet_amount, 0)
        
        # Красивое сообщение для проигрыша всего баланса
        if bet_amount == balance and bet_amount > 0:
            allin_text = "💔 **ПРОИГРАЛ ВСЁ!** 💔\n"
        else:
            allin_text = ""
        
        response = (
            f"🎡 **КРУТИМ РУЛЕТКУ!**\n\n"
            f"{allin_text}"
            f"👤 Игрок: {message.from_user.first_name}\n"
            f"💰 Ставка: {bet_amount:,} на {get_bet_name(bet_type)}\n\n"
            f"⚪ Шарик скачет по цифрам...\n"
            f"{generate_animation(number)}\n\n"
            f"🎯 Выпало: **{number} {result['emoji']} {result['name']}**!\n\n"
            f"😭 **ПРОИГРЫШ** -{bet_amount:,}💰\n"
            f"💎 Новый баланс: {new_balance:,} {CURRENCY}"
        )
    
    bot.send_message(message.chat.id, response, parse_mode="Markdown")

# ========== ОБРАБОТЧИК СТАТИСТИКИ КАЗИНО ==========
@bot.message_handler(func=lambda message: message.text and message.text.lower().strip() in [
    'статистика', 'стата', 'статс', 
    'моя статистика', 'моя стата', 'моя статс',
    'общая статистика', 'статистика казино'
])
def casino_stats_handler(message):
    user_id = message.from_user.id
    
    if is_banned(user_id):
        return
    
    text = message.text.lower().strip()
    
    # Общая статистика (топ)
    if text in ['общая статистика', 'статистика казино']:
        send_top_to_chat(message.chat.id)
        return
    
    # Личная статистика
    stats = get_roulette_stats(user_id)
    
    if not stats:
        bot.reply_to(message, "📊 Ты еще не играл в казино! Попробуй рулетку: `рул крас 1000`")
        return
    
    profit = stats['total_win'] - stats['total_lose']
    profit_sign = "+" if profit >= 0 else ""
    win_rate = (stats['wins'] / stats['games_played'] * 100) if stats['games_played'] > 0 else 0
    
    msg = (
        f"🎰 **ТВОЯ СТАТИСТИКА КАЗИНО**\n\n"
        f"🎮 Сыграно игр: {stats['games_played']}\n"
        f"✅ Побед: {stats['wins']} ({win_rate:.1f}%)\n"
        f"❌ Поражений: {stats['losses']}\n\n"
        f"💰 Всего выиграно: {stats['total_win']:,} {CURRENCY}\n"
        f"💸 Всего проиграно: {stats['total_lose']:,} {CURRENCY}\n"
        f"📈 Чистая прибыль: {profit_sign}{profit:,} {CURRENCY}\n\n"
        f"🏆 Лучший выигрыш: {stats['biggest_win']:,} {CURRENCY}\n"
        f"💔 Худший проигрыш: {stats['biggest_lose']:,} {CURRENCY}"
    )
    
    bot.reply_to(message, msg, parse_mode="Markdown")

# ========== НОВЫЕ ОБРАБОТЧИКИ ДЛЯ ЧАТА ==========

@bot.message_handler(func=lambda message: message.text and message.text.lower().strip() == 'я')
def me_command(message):
    """Обработчик команды 'я' - показывает профиль"""
    user_id = message.from_user.id
    
    if is_banned(user_id):
        return
    
    send_profile_to_chat(message.chat.id, user_id, user_id)

@bot.message_handler(func=lambda message: message.text and message.text.lower().strip() == 'сырье все')
def raw_all_command(message):
    """Обработчик команды 'сырье все' - заказывает сырьё на всё"""
    user_id = message.from_user.id
    
    if is_banned(user_id):
        return
    
    process_raw_order(user_id, message.chat.id)

@bot.message_handler(func=lambda message: message.text and message.text.lower().strip() == 'топ')
def top_chat_command(message):
    """Обработчик команды 'топ' для чата"""
    user_id = message.from_user.id
    
    if is_banned(user_id):
        return
    
    send_top_to_chat(message.chat.id)

# ========== ОБРАБОТЧИК КОЛБЭКОВ ==========
@bot.callback_query_handler(func=lambda call: True)
def callback_handler(call):
    user_id = call.from_user.id
    
    if is_banned(user_id):
        bot.answer_callback_query(call.id, "🔨 Вы забанены!", show_alert=True)
        return
    
    data = call.data
    
    if data == "top_money":
        bot.delete_message(user_id, call.message.message_id)
        send_top_by_type(user_id, "money")
        bot.answer_callback_query(call.id)
    
    elif data == "top_exp":
        bot.delete_message(user_id, call.message.message_id)
        send_top_by_type(user_id, "exp")
        bot.answer_callback_query(call.id)
    
    # ===== ОБРАБОТЧИКИ МИНИ-ИГР =====
    elif data.startswith("loader_"):
        box_num = int(data.split("_")[1])
        result = check_loader_click(user_id, box_num)
        
        if result is None:
            bot.answer_callback_query(call.id, "❌ Игра не найдена или уже закончилась")
            return
        
        if result['win']:
            # Расчет награды
            base_reward = 50
            exp_reward = 10
            speed_bonus = max(1.0, 30 / result['time'])  # Чем быстрее, тем больше
            total = int(base_reward * speed_bonus)
            
            add_balance(user_id, total)
            add_exp(user_id, exp_reward)
            update_work_stats(user_id, "Грузчик", result['score'], result['time'], total)
            
            bot.edit_message_text(
                f"✅ **ПОБЕДА!**\n\n"
                f"⏱️ Время: {result['time']:.1f} сек\n"
                f"💰 Награда: +{total} {CURRENCY}\n"
                f"⭐ Опыт: +{exp_reward}\n\n"
                f"Можешь поработать еще!",
                chat_id=user_id,
                message_id=call.message.message_id
            )
        else:
            bot.answer_callback_query(call.id, f"✅ Собрано {result['collected']}/{result['total']}")
    
    elif data.startswith("courier_"):
        parts = data.split("_")
        is_correct = parts[1]
        route_time = int(parts[2])
        
        result = check_courier_choice(user_id, is_correct, route_time)
        
        if result is None:
            bot.answer_callback_query(call.id, "❌ Игра не найдена или уже закончилась")
            return
        
        if result['win']:
            base_reward = 70
            exp_reward = 15
            speed_bonus = max(1.0, 20 / result['time'])
            total = int(base_reward * speed_bonus)
            
            add_balance(user_id, total)
            add_exp(user_id, exp_reward)
            update_work_stats(user_id, "Курьер", result['score'], result['time'], total)
            
            bot.edit_message_text(
                f"✅ **ДОСТАВЛЕНО!**\n\n"
                f"⏱️ Время: {result['time']:.1f} сек\n"
                f"💰 Награда: +{total} {CURRENCY}\n"
                f"⭐ Опыт: +{exp_reward}\n\n"
                f"Отличная работа!",
                chat_id=user_id,
                message_id=call.message.message_id
            )
        else:
            bot.edit_message_text(
                f"❌ **НЕУДАЧА**\n\n"
                f"Ты выбрал неправильный маршрут!\n"
                f"Попробуй еще раз!",
                chat_id=user_id,
                message_id=call.message.message_id
            )
    
    elif data.startswith("programmer_"):
        is_correct = data.split("_")[1]
        
        result = check_programmer_choice(user_id, is_correct)
        
        if result is None:
            bot.answer_callback_query(call.id, "❌ Игра не найдена или уже закончилась")
            return
        
        if result['win']:
            base_reward = 100
            exp_reward = 20
            total = int(base_reward * (result['score'] / 100))
            
            add_balance(user_id, total)
            add_exp(user_id, exp_reward)
            update_work_stats(user_id, "Программист", result['score'], result['time'], total)
            
            bot.edit_message_text(
                f"✅ **БАГ ИСПРАВЛЕН!**\n\n"
                f"⏱️ Время: {result['time']:.1f} сек\n"
                f"📊 Точность: {result['score']}%\n"
                f"💰 Награда: +{total} {CURRENCY}\n"
                f"⭐ Опыт: +{exp_reward}\n\n"
                f"Ты настоящий кодер!",
                chat_id=user_id,
                message_id=call.message.message_id
            )
        else:
            bot.edit_message_text(
                f"❌ **НЕПРАВИЛЬНО**\n\n"
                f"Попробуй еще раз найти баг!",
                chat_id=user_id,
                message_id=call.message.message_id
            )
    
    elif data.startswith("shop_page_"):
        page = int(data.split("_")[2])
        clothes, current_page, total = get_clothes_page(page)
        
        if clothes:
            caption = (f"👕 *{clothes['name']}*\n\n"
                      f"💰 Цена: {clothes['price']:,} {CURRENCY}\n\n"
                      f"🛍️ Всего комплектов: {total}")
            
            try:
                bot.edit_message_media(
                    types.InputMediaPhoto(media=clothes['photo_url'], caption=caption, parse_mode="Markdown"),
                    chat_id=user_id,
                    message_id=call.message.message_id,
                    reply_markup=get_clothes_navigation_keyboard(current_page, total)
                )
            except:
                bot.send_photo(
                    user_id,
                    clothes['photo_url'],
                    caption=caption,
                    parse_mode="Markdown",
                    reply_markup=get_clothes_navigation_keyboard(current_page, total)
                )
                bot.delete_message(user_id, call.message.message_id)
        
        bot.answer_callback_query(call.id)
    
    elif data.startswith("shop_buy_"):
        page = int(data.split("_")[2])
        clothes, current_page, total = get_clothes_page(page)
        
        if clothes:
            conn = get_db()
            cursor = conn.cursor()
            existing = cursor.execute('''
                SELECT id FROM user_clothes 
                WHERE user_id = ? AND clothes_id = ?
            ''', (user_id, clothes['id'])).fetchone()
            
            if existing:
                conn.close()
                bot.answer_callback_query(call.id, "❌ У тебя уже есть этот комплект!", show_alert=True)
                return
            
            conn.close()
            
            success, message_text = buy_clothes(user_id, clothes['id'])
            
            if success:
                caption = (f"👕 *{clothes['name']}*\n\n"
                          f"💰 Цена: {clothes['price']:,} {CURRENCY}\n\n"
                          f"✅ *КУПЛЕНО!* Комплект надет на тебя!")
                
                markup = types.InlineKeyboardMarkup()
                markup.add(types.InlineKeyboardButton("◀️ В магазин", callback_data=f"shop_page_{current_page}"))
                markup.add(types.InlineKeyboardButton("❌ Закрыть", callback_data="shop_close"))
                
                try:
                    bot.edit_message_media(
                        types.InputMediaPhoto(media=clothes['photo_url'], caption=caption, parse_mode="Markdown"),
                        chat_id=user_id,
                        message_id=call.message.message_id,
                        reply_markup=markup
                    )
                except:
                    pass
                
                bot.answer_callback_query(call.id, "✅ Покупка успешна!", show_alert=True)
            else:
                bot.answer_callback_query(call.id, message_text, show_alert=True)
    
    elif data == "shop_close":
        bot.delete_message(user_id, call.message.message_id)
        send_main_menu_with_profile(user_id)
        bot.answer_callback_query(call.id)
    
    elif data == "noop":
        bot.answer_callback_query(call.id)

# ========== ОСНОВНОЙ ОБРАБОТЧИК ==========
@bot.message_handler(func=lambda message: True)
def handle(message):
    user_id = message.from_user.id
    text = message.text
    
    if is_banned(user_id):
        ban_info = BANS.get(user_id, {})
        if ban_info.get('until') == 0:
            bot.reply_to(message, "🔨 Вы забанены навсегда.")
        else:
            until = datetime.fromtimestamp(ban_info['until'])
            bot.reply_to(message, f"🔨 Вы забанены до {until.strftime('%d.%m.%Y %H:%M')}")
        return
    
    print(f"Получено сообщение: {text} от {user_id}")
    
    try:
        conn = get_db()
        cursor = conn.cursor()
        cursor.execute('INSERT OR IGNORE INTO users (user_id) VALUES (?)', (user_id,))
        conn.commit()
        conn.close()
    except:
        pass
    
    user_data = get_user_profile(user_id)
    display_name = get_user_display_name(user_data) if user_data else "Игрок"
    
    active_travel = get_active_travel(user_id)
    if active_travel:
        end_time = datetime.fromisoformat(active_travel['end_time'])
        if datetime.now() >= end_time:
            complete_travel(active_travel['id'], user_id)
            current_city = get_user_city(user_id)
            bot.send_message(
                user_id,
                f"🏙️ Ты находишься в городе {current_city}",
                reply_markup=city_menu_keyboard(current_city)
            )
            return
    
    if text == "🏙️ ГОРОДА":
        markup = cities_keyboard()
        bot.send_message(
            user_id,
            "🏙️ **ВЫБЕРИ ГОРОД**\n\n"
            "Куда хочешь отправиться?",
            parse_mode="Markdown",
            reply_markup=markup
        )
    
    elif text in ["🏙️ Кропоткин", "🏙️ Москва", "🏙️ Мурино", "🏙️ Село Молочное"]:
        city_name = text.replace("🏙️ ", "")
        current_city = get_user_city(user_id)
        
        if city_name == current_city:
            bot.send_message(
                user_id,
                f"🏙️ Ты уже находишься в городе {city_name}",
                reply_markup=city_menu_keyboard(city_name)
            )
        else:
            bot.send_message(
                user_id,
                f"🚀 Выбери транспорт для поездки в {city_name}:",
                reply_markup=transport_keyboard(city_name)
            )
            bot.register_next_step_handler(message, process_travel, city_name)
    
    elif text in ["🚕 Такси", "🚗 Личная машина", "✈️ Личный самолет"]:
        pass
    
    # ===== МАГАЗИНЫ =====
    elif text.lower() == "👕 магазин одежды":
        clothes, current_page, total = get_clothes_page(0)
        
        if clothes:
            welcome_text = ("🛍️ **ДОБРО ПОЖАЛОВАТЬ В МАГАЗИН ОДЕЖДЫ!**\n\n"
                           "Мы подобрали самые лучшие и красивые комплекты одежды.\n"
                           "Выберите какой вам понравится и нажмите купить!\n\n"
                           "👉 При покупке комплект сразу надевается на тебя!")
            
            bot.send_message(user_id, welcome_text, parse_mode="Markdown")
            
            caption = (f"👕 *{clothes['name']}*\n\n"
                      f"💰 Цена: {clothes['price']:,} {CURRENCY}\n\n"
                      f"🛍️ Всего комплектов: {total}")
            
            bot.send_photo(
                user_id,
                clothes['photo_url'],
                caption=caption,
                parse_mode="Markdown",
                reply_markup=get_clothes_navigation_keyboard(current_page, total)
            )
        else:
            bot.send_message(user_id, "❌ В магазине пока нет товаров!")
    
    elif text.lower() == "🏠 магазин домов":
        bot.send_message(user_id, "🏠 Магазин домов скоро откроется! Следи за обновлениями!")
    
    elif text.lower() == "✈️ магазин самолетов":
        bot.send_message(user_id, "✈️ Магазин самолетов скоро откроется! Следи за обновлениями!")
    
    # ===== ИСПРАВЛЕННАЯ КНОПКА ОБНОВЛЕНИЯ =====
    elif text == "🔄":
        # Только показываем профиль, не трогаем меню города
        user_data = get_user_profile(user_id)
        if user_data:
            balance = get_balance(user_id)
            display_name = get_user_display_name(user_data)
            photo_url = get_user_profile_photo(user_id)
            
            caption = (f"👤 *{display_name}*\n\n"
                       f"💰 Баланс: {balance:,} {CURRENCY}")
            
            bot.send_photo(
                user_id,
                photo_url,
                caption=caption,
                parse_mode="Markdown"
            )
        else:
            bot.send_message(user_id, "❌ Ошибка загрузки профиля")
    
    # ===== РАБОТЫ С МИНИ-ИГРАМИ =====
    elif text == "💼 Работы":
        bot.send_message(user_id, "🔨 Выбери работу:", reply_markup=jobs_keyboard(user_id))
    
    elif text in ["🚚 Грузчик", "🧹 Уборщик", "📦 Курьер", "🔧 Механик", "💻 Программист", "🕵️ Детектив", "👨‍🔧 Инженер", "👨‍⚕️ Врач", "👨‍🎤 Артист", "👨‍🚀 Космонавт"]:
        job_name = text
        
        if "Грузчик" in job_name:
            markup, msg = start_loader_game(user_id, job_name)
            bot.send_message(user_id, msg, reply_markup=markup)
        
        elif "Курьер" in job_name:
            markup, msg = start_courier_game(user_id, job_name)
            bot.send_message(user_id, msg, reply_markup=markup)
        
        elif "Программист" in job_name:
            markup, msg = start_programmer_game(user_id, job_name)
            bot.send_message(user_id, msg, parse_mode="Markdown", reply_markup=markup)
        
        else:
            # Для остальных работ пока старая система
            rewards = {
                "🚚 Грузчик": (10, 50, 5),
                "🧹 Уборщик": (15, 70, 7),
                "📦 Курьер": (20, 100, 10),
                "🔧 Механик": (30, 150, 12),
                "💻 Программист": (50, 300, 15),
                "🕵️ Детектив": (100, 500, 20),
                "👨‍🔧 Инженер": (200, 800, 25),
                "👨‍⚕️ Врач": (300, 1200, 30),
                "👨‍🎤 Артист": (500, 2000, 35),
                "👨‍🚀 Космонавт": (1000, 5000, 50)
            }
            
            min_r, max_r, exp_r = rewards[job_name]
            earn = random.randint(min_r, max_r)
            
            if add_balance(user_id, earn) and add_exp(user_id, exp_r):
                bot.send_message(user_id, f"✅ {job_name}\n💰 +{earn}\n⭐ +{exp_r} опыта")
            else:
                bot.send_message(user_id, "❌ Ошибка, попробуй позже")
    
    # ===== БИЗНЕСЫ =====
    elif text == "🏭 Бизнесы":
        bot.send_message(user_id, "🏪 Управление бизнесом:", reply_markup=businesses_main_keyboard())
    
    elif text == "📊 Статистика":
        exp, level, work_count, total = get_user_stats(user_id)
        equipped = get_user_equipped_clothes(user_id)
        clothes_info = f", одет: {equipped['name']}" if equipped else ""
        current_city = get_user_city(user_id)
        
        msg = f"📊 **СТАТИСТИКА**\n\n"
        msg += f"👤 Игрок: {display_name}{clothes_info}\n"
        msg += f"📍 Город: {current_city}\n"
        msg += f"⭐ Опыт: {exp}\n"
        msg += f"📈 Уровень: {level}\n"
        msg += f"🔨 Работ: {work_count}\n"
        msg += f"💰 Всего заработано: {total:,}"
        bot.send_message(user_id, msg, parse_mode="Markdown")
    
    elif text == "🎁 Ежедневно":
        try:
            conn = get_db()
            cursor = conn.cursor()
            cursor.execute('SELECT last_daily FROM users WHERE user_id = ?', (user_id,))
            result = cursor.fetchone()
            last = result[0] if result else None
            now = datetime.now().isoformat()
            
            if last:
                last_time = datetime.fromisoformat(last)
                if datetime.now() - last_time < timedelta(hours=24):
                    next_time = last_time + timedelta(hours=24)
                    time_left = next_time - datetime.now()
                    hours = time_left.seconds // 3600
                    minutes = (time_left.seconds % 3600) // 60
                    bot.send_message(user_id, f"⏳ След. бонус через {hours}ч {minutes}м")
                    conn.close()
                    return
            
            bonus = random.randint(500, 2000)
            bonus_exp = random.randint(50, 200)
            cursor.execute('UPDATE users SET balance = balance + ?, exp = exp + ?, last_daily = ? WHERE user_id = ?', 
                          (bonus, bonus_exp, now, user_id))
            conn.commit()
            conn.close()
            bot.send_message(user_id, f"🎁 Бонус: +{bonus} {CURRENCY} и +{bonus_exp}⭐!")
        except Exception as e:
            print(f"Ошибка daily: {e}")
            bot.send_message(user_id, "❌ Ошибка")
    
    elif text == "⚙️ Настройки":
        bot.send_message(user_id, "🔧 **НАСТРОЙКИ**\n\nВыбери что хочешь изменить:", reply_markup=settings_keyboard(), parse_mode="Markdown")
    
    elif text == "✏️ Сменить никнейм":
        current_nick = display_name if display_name != "Игрок" else "Не установлен"
        msg = bot.send_message(
            user_id,
            f"🎮 **СМЕНА ИГРОВОГО НИКНЕЙМА**\n\n"
            f"Текущий ник: `{current_nick}`\n\n"
            f"🔤 **Напиши новый никнейм:**\n\n"
            f"📝 Он может быть любым (буквы, цифры, символы)\n"
            f"✨ Например: `DarkKnight`, `КиберПанк`, `SuguruKing`\n\n"
            f"⚠️ **Важно:** Никнейм должен быть **уникальным**!",
            parse_mode="Markdown"
        )
        bot.register_next_step_handler(msg, change_nickname_step)
    
    elif text == "📋 Помощь":
        help_text = (
            "📚 **ПОЛНОЕ РУКОВОДСТВО ПО ИГРЕ** 📚\n\n"
            "💼 **РАБОТЫ**\n"
            "• Доступно 10 видов работ\n"
            "• Некоторые работы теперь с мини-играми!\n"
            "• Чем лучше сыграешь - тем больше денег\n"
            "• Работы можно выполнять бесконечно\n\n"
            "🏭 **БИЗНЕСЫ**\n"
            "• Можно купить только один бизнес\n"
            "• 5 видов бизнеса\n"
            "• У каждого бизнеса 3 уровня прокачки\n"
            "• Склад вмещает максимум 1000 сырья\n"
            "• Доставка сырья - 15 минут\n"
            "• Прибыль накапливается на складе, нужно собирать вручную\n\n"
            "📊 **ДАННЫЕ БИЗНЕСОВ**\n"
            "🥤 Киоск - 500к | 1 сырьё = 1.000💰 | профит 2.000💰\n"
            "🍔 Фастфуд - 5M | 1 сырьё = 2.500💰 | профит 5.000💰\n"
            "🏪 Минимаркет - 15M | 1 сырьё = 30.000💰 | профит 60.000💰\n"
            "⛽ Заправка - 50M | 1 сырьё = 200.000💰 | профит 400.000💰\n"
            "🏨 Отель - 1B | 1 сырьё = 1.000.000💰 | профит 2.000.000💰\n\n"
            "🏙️ **ГОРОДА**\n"
            "• Можно путешествовать между 4 городами\n"
            "• В каждом городе свои магазины\n"
            "• Время в пути: 30-60 секунд\n"
            "• Транспорт: Такси, Личная машина, Личный самолет\n"
            "• Для машины и самолета нужно их купить\n\n"
            "👕 **МАГАЗИН ОДЕЖДЫ**\n"
            "• Покупай крутые комплекты одежды\n"
            "• При покупке комплект сразу надевается\n"
            "• Одежда видна в главном меню и статистике\n\n"
            "🎰 **РУЛЕТКА**\n"
            "• Играй прямо в чате: `рул крас 1000`\n"
            "• Можно ставить на цвет, число, дюжины\n"
            "• Поддержка сокращений: `1к` = 1000, `5кк` = 5 млн\n"
            "• Команда `рул крас все` - поставить весь баланс\n"
            "• Вся статистика сохраняется!\n\n"
            "🏆 **ТОП 10** (команда /top)\n"
            "• Можно выбрать топ по деньгам или опыту\n"
            "• Соревнуйся с другими игроками\n\n"
            "🎁 **ЕЖЕДНЕВНЫЙ БОНУС**\n"
            "• Получай бонус раз в 24 часа\n"
            "• Рандомный бонус от 500 до 2000💰\n"
            "• Дополнительно 50-200⭐ опыта"
        )
        bot.send_message(user_id, help_text, parse_mode="Markdown")
    
    elif text == "❓ Помощь":
        help_text = "🤖 **ПОМОЩЬ**\n\n"
        help_text += "💼 Работы - работай в мини-играх\n"
        help_text += "🏭 Бизнесы - управление бизнесом\n"
        help_text += "🏙️ Города - путешествуй между городами\n"
        help_text += "👕 Магазин одежды - покупай крутые комплекты\n"
        help_text += "🎰 Рулетка - играй в чате: рул крас 1000\n"
        help_text += "📊 Статистика - твои показатели\n"
        help_text += "🏆 Топ 10 - лучшие игроки (команда /top)\n"
        help_text += "🎁 Ежедневно - бонус каждый день\n"
        help_text += "⚙️ Настройки - изменить никнейм и полная помощь\n"
        help_text += "🔄 - показать твой профиль"
        
        level = get_admin_level(user_id)
        if level > 0:
            help_text += f"\n\n👑 У вас права администратора {level} уровня!\n/adminhelp - список команд админа"
        
        bot.send_message(user_id, help_text, parse_mode="Markdown")
    
    # ===== УПРАВЛЕНИЕ БИЗНЕСОМ =====
    elif text == "📊 Мой бизнес":
        business = get_user_business(user_id)
        if not business:
            bot.send_message(user_id, "📭 У тебя еще нет бизнеса!")
            return
        
        data = get_business_data(business['business_name'])
        if not data:
            bot.send_message(user_id, "❌ Ошибка загрузки данных бизнеса")
            return
        
        speed_multiplier = {1: 1.0, 2: 1.2, 3: 2.0}
        current_speed = speed_multiplier.get(business['level'], 1.0)
        time_per_raw = data['base_time'] / current_speed
        
        total_raw = business['raw_material'] + business['raw_in_delivery']
        total_potential = business['raw_material'] * data['profit_per_raw']
        
        msg = f"{data['emoji']} **{business['business_name']}**\n\n"
        msg += f"📊 Уровень: {business['level']}\n"
        msg += f"⏱️ Время на 1 сырье: {time_per_raw:.0f} сек\n"
        msg += f"📦 На складе: {business['raw_material']}/1000 сырья\n"
        msg += f"🚚 В доставке: {business['raw_in_delivery']} сырья\n"
        msg += f"📊 Всего: {total_raw}/1000\n"
        msg += f"💰 Прибыль на складе: {business['stored_profit']:,} {CURRENCY}\n"
        msg += f"💵 Всего вложено: {business['total_invested']:,} {CURRENCY}\n"
        msg += f"🎯 Потенциальная прибыль: {total_potential:,} {CURRENCY}"
        
        # Отправляем фото бизнеса
        if data['photo_url']:
            bot.send_photo(user_id, data['photo_url'], caption=msg, parse_mode="Markdown")
        else:
            bot.send_message(user_id, msg, parse_mode="Markdown")
    
    elif text == "💰 Собрать прибыль":
        business = get_user_business(user_id)
        if not business:
            bot.send_message(user_id, "📭 У тебя еще нет бизнеса!")
            return
        
        if business['stored_profit'] <= 0:
            bot.send_message(user_id, "❌ На складе нет прибыли! Сырье еще перерабатывается.")
            return
        
        profit = business['stored_profit']
        
        conn = get_db()
        cursor = conn.cursor()
        cursor.execute('UPDATE businesses SET stored_profit = 0 WHERE user_id = ?', (user_id,))
        conn.commit()
        conn.close()
        
        add_balance(user_id, profit)
        
        bot.send_message(user_id, f"✅ Ты собрал {profit:,} {CURRENCY} прибыли с бизнеса!")
    
    elif text == "📦 Закупить на всё":
        business = get_user_business(user_id)
        if not business:
            bot.send_message(user_id, "❌ Сначала купи бизнес!")
            return
        
        data = get_business_data(business['business_name'])
        if not data:
            bot.send_message(user_id, "❌ Ошибка загрузки данных бизнеса")
            return
        
        balance = get_balance(user_id)
        raw_cost = data['raw_cost_per_unit']
        max_by_money = balance // raw_cost
        
        total_raw = business['raw_material'] + business['raw_in_delivery']
        free_space = 1000 - total_raw
        
        amount = min(max_by_money, free_space)
        
        if amount <= 0:
            if free_space <= 0:
                bot.send_message(user_id, f"❌ Склад переполнен! Свободно места: 0/1000")
            else:
                bot.send_message(user_id, f"❌ У тебя недостаточно денег! Нужно минимум {raw_cost:,} {CURRENCY}")
            return
        
        total_cost = amount * raw_cost
        
        if not add_balance(user_id, -total_cost):
            bot.send_message(user_id, "❌ Ошибка при списании денег")
            return
        
        if has_active_delivery(user_id):
            bot.send_message(user_id, "❌ У тебя уже есть активная доставка! Дождись её завершения.")
            add_balance(user_id, total_cost)
            return
        
        conn = get_db()
        cursor = conn.cursor()
        
        end_time = datetime.now() + timedelta(minutes=15)
        cursor.execute('''
            INSERT INTO deliveries (user_id, amount, end_time, delivered)
            VALUES (?, ?, ?, 0)
        ''', (user_id, amount, end_time.isoformat()))
        
        cursor.execute('''
            UPDATE businesses 
            SET raw_in_delivery = raw_in_delivery + ?,
                total_invested = total_invested + ?
            WHERE user_id = ?
        ''', (amount, total_cost, user_id))
        
        conn.commit()
        conn.close()
        
        new_total = total_raw + amount
        bot.send_message(user_id, f"✅ Заказ на {amount} сырья оформлен!\n💰 Стоимость: {total_cost:,} {CURRENCY}\n📦 Будет: {new_total}/1000\n⏱️ Доставка через 15 минут")
    
    elif text == "🏪 Купить бизнес":
        bot.send_message(user_id, "Выбери бизнес для покупки:", reply_markup=buy_business_keyboard())
    
    elif text == "💰 Продать бизнес":
        business = get_user_business(user_id)
        if not business:
            bot.send_message(user_id, "❌ У тебя нет бизнеса!")
            return
        
        data = get_business_data(business['business_name'])
        if not data:
            bot.send_message(user_id, "❌ Ошибка")
            return
        
        sell_price = data['price'] // 2
        if add_balance(user_id, sell_price):
            try:
                conn = get_db()
                cursor = conn.cursor()
                cursor.execute('DELETE FROM businesses WHERE user_id = ?', (user_id,))
                cursor.execute('DELETE FROM deliveries WHERE user_id = ?', (user_id,))
                conn.commit()
                conn.close()
                bot.send_message(user_id, f"💰 Бизнес продан за {sell_price:,} {CURRENCY}!")
            except Exception as e:
                print(f"Ошибка при продаже: {e}")
                bot.send_message(user_id, "❌ Ошибка при продаже")
                add_balance(user_id, -sell_price)
    
    elif text in ["🥤 Киоск", "🍔 Фастфуд", "🏪 Минимаркет", "⛽ Заправка", "🏨 Отель"]:
        
        if get_user_business(user_id):
            bot.send_message(user_id, "❌ У тебя уже есть бизнес!")
            return
        
        data = get_business_data(text)
        if not data:
            bot.send_message(user_id, "❌ Бизнес не найден")
            return
        
        price = data['price']
        balance = get_balance(user_id)
        
        if balance < price:
            bot.send_message(user_id, f"❌ Не хватает {price - balance:,}💰")
            return
        
        if add_balance(user_id, -price):
            try:
                conn = get_db()
                cursor = conn.cursor()
                cursor.execute('''
                    INSERT INTO businesses (user_id, business_name, level, raw_material, raw_in_delivery, raw_spent, total_invested, stored_profit, last_update)
                    VALUES (?, ?, 1, 0, 0, 0, 0, 0, ?)
                ''', (user_id, text, datetime.now().isoformat()))
                conn.commit()
                conn.close()
                bot.send_message(user_id, f"✅ Ты купил {text} за {price:,}💰!")
            except Exception as e:
                print(f"Ошибка при покупке: {e}")
                bot.send_message(user_id, "❌ Ошибка при покупке")
                add_balance(user_id, price)
    
    elif text == "🔙 Назад":
        if "🏙️" in text or "🚕" in text or "🚗" in text or "✈️" in text:
            send_main_menu_with_profile(user_id)
        else:
            current_city = get_user_city(user_id)
            bot.send_message(
                user_id,
                f"🏙️ Ты в городе {current_city}",
                reply_markup=city_menu_keyboard(current_city)
            )

def process_travel(message, target_city):
    user_id = message.from_user.id
    transport = message.text
    
    if transport not in ["🚕 Такси", "🚗 Личная машина", "✈️ Личный самолет"]:
        bot.send_message(user_id, "❌ Пожалуйста, выбери транспорт из предложенных!")
        bot.register_next_step_handler(message, process_travel, target_city)
        return
    
    if transport == "🔙 Назад":
        send_main_menu_with_profile(user_id)
        return
    
    conn = get_db()
    cursor = conn.cursor()
    user = cursor.execute('SELECT has_car, has_plane FROM users WHERE user_id = ?', (user_id,)).fetchone()
    conn.close()
    
    if transport == "🚗 Личная машина" and (not user or user['has_car'] == 0):
        bot.send_message(
            user_id, 
            "❌ У вас нет личной машины!\n"
            "🚕 Можете воспользоваться такси или купить машину позже."
        )
        bot.send_message(
            user_id,
            f"🚀 Выбери транспорт для поездки в {target_city}:",
            reply_markup=transport_keyboard(target_city)
        )
        return
    
    if transport == "✈️ Личный самолет" and (not user or user['has_plane'] == 0):
        bot.send_message(
            user_id, 
            "❌ У вас нет личного самолета!\n"
            "🚕 Можете воспользоваться такси или купить самолет позже."
        )
        bot.send_message(
            user_id,
            f"🚀 Выбери транспорт для поездки в {target_city}:",
            reply_markup=transport_keyboard(target_city)
        )
        return
    
    success, msg = start_travel(user_id, target_city, transport)
    
    if success:
        bot.send_message(user_id, msg)
        current_city = get_user_city(user_id)
        bot.send_message(
            user_id,
            f"⏳ Ты в пути... Прибудешь через некоторое время.\n"
            f"📍 Текущий город: {current_city}",
            reply_markup=main_keyboard()
        )
    else:
        bot.send_message(user_id, msg)
        bot.send_message(
            user_id,
            "🏙️ Выбери город:",
            reply_markup=cities_keyboard()
        )

# ========== ФОНОВАЯ ПРОВЕРКА ПОЕЗДОК ==========
def check_travels():
    while True:
        try:
            conn = get_db()
            cursor = conn.cursor()
            
            travels = cursor.execute('''
                SELECT * FROM travels 
                WHERE completed = 0 AND end_time <= ?
            ''', (datetime.now().isoformat(),)).fetchall()
            
            for t in travels:
                cursor.execute('UPDATE users SET current_city = ? WHERE user_id = ?', 
                             (t['to_city'], t['user_id']))
                cursor.execute('UPDATE travels SET completed = 1 WHERE id = ?', (t['id'],))
                
                try:
                    bot.send_message(
                        t['user_id'],
                        f"✅ Вы прибыли в {t['to_city']}!\n"
                        f"Транспорт: {t['transport']}",
                        reply_markup=city_menu_keyboard(t['to_city'])
                    )
                except:
                    pass
                
                conn.commit()
            
            conn.close()
            time.sleep(5)
        except Exception as e:
            print(f"Ошибка проверки поездок: {e}")
            time.sleep(5)

# ========== ФОНОВАЯ ПЕРЕРАБОТКА СЫРЬЯ ==========
def process_raw_material():
    while True:
        try:
            conn = get_db()
            cursor = conn.cursor()
            businesses = cursor.execute('SELECT * FROM businesses').fetchall()
            
            for b in businesses:
                if b['raw_material'] > 0:
                    data = get_business_data(b['business_name'])
                    if data:
                        speed_multiplier = {1: 1.0, 2: 1.2, 3: 2.0}
                        current_speed = speed_multiplier.get(b['level'], 1.0)
                        time_per_raw = data['base_time'] / current_speed
                        
                        last_update = datetime.fromisoformat(b['last_update'])
                        time_passed = (datetime.now() - last_update).total_seconds()
                        
                        units_to_process = int(time_passed / time_per_raw)
                        
                        if units_to_process > 0 and b['raw_material'] > 0:
                            process = min(units_to_process, b['raw_material'])
                            profit = process * data['profit_per_raw']
                            
                            cursor.execute('''
                                UPDATE businesses 
                                SET raw_material = raw_material - ?,
                                    raw_spent = raw_spent + ?,
                                    stored_profit = stored_profit + ?,
                                    last_update = ?
                                WHERE user_id = ?
                            ''', (process, process, profit, datetime.now().isoformat(), b['user_id']))
                            
                            total_spent = b['raw_spent'] + process
                            
                            if total_spent >= 50000 and b['level'] == 1:
                                cursor.execute('UPDATE businesses SET level = 2 WHERE user_id = ?', (b['user_id'],))
                                try:
                                    bot.send_message(b['user_id'], "🎉 Твой бизнес достиг 2 уровня! Скорость +20%!")
                                except:
                                    pass
                            elif total_spent >= 200000 and b['level'] == 2:
                                cursor.execute('UPDATE businesses SET level = 3 WHERE user_id = ?', (b['user_id'],))
                                try:
                                    bot.send_message(b['user_id'], "🎉 Твой бизнес достиг 3 уровня! Скорость +100%!")
                                except:
                                    pass
                            
                            conn.commit()
            
            conn.close()
            time.sleep(10)
        except Exception as e:
            print(f"Ошибка переработки: {e}")
            time.sleep(10)

# ========== ФОНОВАЯ ПРОВЕРКА ДОСТАВОК ==========
def check_deliveries():
    while True:
        try:
            conn = get_db()
            cursor = conn.cursor()
            
            deliveries = cursor.execute('''
                SELECT * FROM deliveries 
                WHERE delivered = 0 AND end_time <= ?
            ''', (datetime.now().isoformat(),)).fetchall()
            
            for d in deliveries:
                cursor.execute('''
                    UPDATE businesses 
                    SET raw_material = raw_material + ?,
                        raw_in_delivery = raw_in_delivery - ?
                    WHERE user_id = ?
                ''', (d['amount'], d['amount'], d['user_id']))
                
                cursor.execute('UPDATE deliveries SET delivered = 1 WHERE id = ?', (d['id'],))
                
                try:
                    business = get_user_business(d['user_id'])
                    if business:
                        total_raw = business['raw_material'] + d['amount']
                        bot.send_message(
                            d['user_id'],
                            f"✅ Сырье доставлено на склад!\n📦 +{d['amount']} сырья\n📦 Теперь на складе: {total_raw}/1000"
                        )
                except:
                    pass
            
            conn.commit()
            conn.close()
            time.sleep(30)
        except Exception as e:
            print(f"Ошибка в доставках: {e}")
            time.sleep(30)

threading.Thread(target=process_raw_material, daemon=True).start()
threading.Thread(target=check_deliveries, daemon=True).start()
threading.Thread(target=check_travels, daemon=True).start()

# ========== ЗАПУСК ==========
from flask import Flask
from threading import Thread

app = Flask('')

@app.route('/')
def home():
    return "Бот работает!"

def run():
    app.run(host='0.0.0.0', port=8080)

def keep_alive():
    t = Thread(target=run)
    t.start()

keep_alive()
print("✅ Бот запущен!")
print(f"👑 Загружено админов: {len(ADMINS)}")
print(f"🔨 Загружено банов: {len(BANS)}")
print(f"⚠️ Загружено варнов: {len(WARNS)}")
print("🏙️ Система городов активна! 4 города ждут путешественников!")
print("👕 Магазин одежды загружен с 16 комплектами!")
print("🎰 Рулетка активна! Играй: рул крас 1000")
print("📸 Фото для бизнесов загружены!")
print("🎮 Мини-игры для работ активированы! (Грузчик, Курьер, Программист)")
print("📌 Админ команды: /adminhelp")
print("📢 Команды для чата: я, топ, сырье все")
print("🔄 - показать профиль (не трогает меню)")
bot.infinity_polling()
смотри что мы уде сделалм с другим и
