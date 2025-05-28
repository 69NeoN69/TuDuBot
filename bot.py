# используемые библиотеки
import telebot
import sqlite3
from datetime import datetime, date
from apscheduler.schedulers.background import BackgroundScheduler

TOKEN = ''
bot = telebot.TeleBot(TOKEN)
# словарь для добавления задач
user_sessions = {}

scheduler = BackgroundScheduler()
scheduler.start()

start_mes = [
    'Здравствуйте! Я бот-напоминания.'
    ' Здесь вы можете создавать для себя напоминания и задачи'
    ' на день, а также отслеживать их выполнение!'
]
# функция вывода меню
def show_main_menu(chat_id):
    keyboard = telebot.types.InlineKeyboardMarkup()
    keyboard.add(telebot.types.InlineKeyboardButton('Добавить задачу', callback_data='add_task'))
    keyboard.add(telebot.types.InlineKeyboardButton('Задачи на сегодня', callback_data='today_task'))
    keyboard.add(telebot.types.InlineKeyboardButton('Вывести все задачи', callback_data='write_all'))
    keyboard.add(telebot.types.InlineKeyboardButton('Корзина', callback_data='trash'))
    bot.send_message(chat_id, 'Меню:', reply_markup=keyboard)
# обработка команды start
@bot.message_handler(commands=['start'])
def handle_command_start(message):
    # создания SQL таблицы
    con = sqlite3.connect('todo_reminders.db')
    con.execute(f'''
        CREATE TABLE IF NOT EXISTS user_{message.chat.id} (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            task TEXT,
            date TEXT,
            notification INTEGER,
            time TEXT,
            complete INTEGER
        )
    ''')
    con.close()
    bot.send_message(message.chat.id, ' '.join(start_mes))
    show_main_menu(message.chat.id)
# обработка нажатия на inline клавиатуру
@bot.callback_query_handler(func=lambda callback: True)
def handle_callback(callback):
    con = sqlite3.connect('todo_reminders.db')
    chat_id = callback.message.chat.id
    # добавление задачи:
    if callback.data == 'add_task':
        bot.send_message(chat_id, 'Напишите текст задачи')
        bot.register_next_step_handler(callback.message, save_task)
    # добавление задачи: добавление напоминания
    elif callback.data == 'answer_1':
        bot.send_message(chat_id, 'Введите время напоминания в формате ЧЧ:ММ')
        bot.register_next_step_handler(callback.message, save_time)
    # добавление задачи: сохранение задачи без напоминания
    elif callback.data == 'answer_2':
        session = user_sessions.get(chat_id)
        if session:
            con.execute(
                f"INSERT INTO user_{chat_id} (task, date, notification, time, complete) VALUES ('{session['task']}', '{session['date']}', 0, '', 0)"
            )
            con.commit()
        user_sessions.pop(chat_id, None)
        bot.send_message(chat_id, 'Задача сохранена без напоминания.')
        show_main_menu(chat_id)
    # вывод запланированных задач
    elif callback.data == 'write_all':
        today = date.today()
        tasks = con.execute(f'SELECT task, date, id, complete FROM user_{chat_id}').fetchall()
        tasks = [t for t in tasks if datetime.strptime(t[1], '%d.%m.%Y').date() >= today]
        tasks.sort(key=lambda task: datetime.strptime(task[1], '%d.%m.%Y'))
        keyboard = telebot.types.InlineKeyboardMarkup()
        for task in tasks:
            mark = '✅' if task[3] else '❌'
            keyboard.add(telebot.types.InlineKeyboardButton(f"{mark} {task[0]}", callback_data=str(task[2])))
        bot.send_message(chat_id, 'Ваши актуальные задачи:', reply_markup=keyboard)
    # вывод "корзины"
    elif callback.data == 'trash':
        today = date.today()
        tasks = con.execute(f'SELECT task, date FROM user_{chat_id}').fetchall()
        old = [t for t in tasks if datetime.strptime(t[1], '%d.%m.%Y').date() < today]
        if old:
            text = "\n".join([f"- {t[0]} ({t[1]})" for t in old])
        else:
            text = 'Устаревших задач нет.'
        bot.send_message(chat_id, f'Корзина задач:\n{text}')
    # вывод "персонального меню" для задачи
    elif callback.data.isdigit():
        task = con.execute(f"SELECT task, date, time, notification FROM user_{chat_id} WHERE id = {int(callback.data)}").fetchone()
        keyboard = telebot.types.InlineKeyboardMarkup()
        keyboard.add(telebot.types.InlineKeyboardButton('Пометить как выполненную', callback_data=f'done_{callback.data}'))
        keyboard.add(telebot.types.InlineKeyboardButton('Удалить задачу', callback_data=f'del_one_{callback.data}'))
        keyboard.add(telebot.types.InlineKeyboardButton('Изменить текст задачи', callback_data=f'change_txt_{callback.data}'))
        keyboard.add(telebot.types.InlineKeyboardButton('Изменить дату задачи', callback_data=f'change_date_{callback.data}'))
        keyboard.add(telebot.types.InlineKeyboardButton('Изменить время напоминания', callback_data=f'change_time_{callback.data}'))
        task_text = f"🗒 Задача: {task[0]}\n📅 Дата: {task[1]}"
        if task[3] and task[2]:
            task_text += f"\n⏰ Напоминание: {task[2]}"
        bot.send_message(chat_id, task_text, reply_markup=keyboard)
    # измененение статуса задачи на "выполнено"
    elif callback.data.startswith('done_'):
        task_id = callback.data.split('_')[-1]
        con.execute(f"UPDATE user_{chat_id} SET complete = 1 WHERE id = {task_id}")
        con.commit()
        bot.send_message(chat_id, 'Задача отмечена как выполненная.')
        show_main_menu(chat_id)
    # удаление задачи
    elif callback.data.startswith('del_one'):
        task_id = callback.data.split('_')[-1]
        con.execute(f"DELETE FROM user_{chat_id} WHERE id = {task_id}")
        con.commit()
        bot.send_message(chat_id, 'Задача удалена.')
        show_main_menu(chat_id)
    # изменение текста задачи
    elif callback.data.startswith('change_txt'):
        task_id = callback.data.split('_')[-1]
        user_sessions[chat_id] = {'edit_id': task_id, 'action': 'text'}
        bot.send_message(chat_id, 'Введите новый текст задачи:')
        bot.register_next_step_handler(callback.message, edit_task)
    # изменение даты задачи
    elif callback.data.startswith('change_date'):
        task_id = callback.data.split('_')[-1]
        user_sessions[chat_id] = {'edit_id': task_id, 'action': 'date'}
        bot.send_message(chat_id, 'Введите новую дату в формате ДД.ММ.ГГГГ:')
        bot.register_next_step_handler(callback.message, edit_task)
    # изменение времени отпраки уведомления-напоминания
    elif callback.data.startswith('change_time'):
        task_id = callback.data.split('_')[-1]
        user_sessions[chat_id] = {'edit_id': task_id, 'action': 'time'}
        bot.send_message(chat_id, 'Введите новое время в формате ЧЧ:ММ')
        bot.register_next_step_handler(callback.message, edit_task)
    # вывод задач на сегодня
    elif callback.data == 'today_task':
        today_str = date.today().strftime('%d.%m.%Y')
        tasks = con.execute(f"SELECT task, id FROM user_{chat_id} WHERE date = '{today_str}'").fetchall()
        keyboard = telebot.types.InlineKeyboardMarkup()
        for task in tasks:
            keyboard.add(telebot.types.InlineKeyboardButton(task[0], callback_data=str(task[1])))
        bot.send_message(chat_id, 'Задачи на сегодня:', reply_markup=keyboard)

    con.close()
# добавление задачи: сохранение текста
def save_task(message):
    user_sessions[message.chat.id] = {'task': message.text}
    bot.send_message(message.chat.id, 'Введите дату задачи в формате ДД.ММ.ГГГГ')
    bot.register_next_step_handler(message, save_date)
# добавление задачи: сохранение даты
def save_date(message):
    try:
        datetime.strptime(message.text, '%d.%m.%Y')
        user_sessions[message.chat.id]['date'] = message.text
        keyboard = telebot.types.InlineKeyboardMarkup()
        keyboard.add(
            telebot.types.InlineKeyboardButton('Да', callback_data='answer_1'),
            telebot.types.InlineKeyboardButton('Нет', callback_data='answer_2')
        )
        bot.send_message(message.chat.id, 'Хотите ли вы получить напоминание?', reply_markup=keyboard)
    except ValueError:
        bot.send_message(message.chat.id, 'Некорректный формат. Попробуйте снова: ДД.ММ.ГГГГ')
        bot.register_next_step_handler(message, save_date)
# добавление задачи: сохранение времени отправки уведомления-напоминания
def save_time(message):
    try:
        datetime.strptime(message.text, '%H:%M')
        session = user_sessions[message.chat.id]
        con = sqlite3.connect('todo_reminders.db')
        con.execute(
            f"INSERT INTO user_{message.chat.id} (task, date, notification, time, complete) VALUES ('{session['task']}', '{session['date']}', 1, '{message.text}', 0)"
        )
        con.commit()
        con.close()
        bot.send_message(message.chat.id, 'Задача сохранена с напоминанием.')
        user_sessions.pop(message.chat.id, None)
        show_main_menu(message.chat.id)
    except ValueError:
        bot.send_message(message.chat.id, 'Некорректный формат времени. Попробуйте снова: ЧЧ:ММ')
        bot.register_next_step_handler(message, save_time)
# изменение текста, даты, времени отправки уведомления-напоминания задачи
def edit_task(message):
    session = user_sessions.get(message.chat.id)
    if not session:
        bot.send_message(message.chat.id, 'Что-то пошло не так. Попробуйте снова.')
        return

    con = sqlite3.connect('todo_reminders.db')
    try:
        if session['action'] == 'text':
            con.execute(f"UPDATE user_{message.chat.id} SET task = '{message.text}' WHERE id = {session['edit_id']}")
        elif session['action'] == 'date':
            datetime.strptime(message.text, '%d.%m.%Y')
            con.execute(f"UPDATE user_{message.chat.id} SET date = '{message.text}' WHERE id = {session['edit_id']}")
        elif session['action'] == 'time':
            datetime.strptime(message.text, '%H:%M')
            con.execute(f"UPDATE user_{message.chat.id} SET time = '{message.text}', notification = 1 WHERE id = {session['edit_id']}")
        con.commit()
        bot.send_message(message.chat.id, 'Изменения сохранены.')
    except ValueError:
        bot.send_message(message.chat.id, 'Неверный формат. Попробуйте снова.')
        bot.register_next_step_handler(message, edit_task)
        return
    finally:
        con.close()
        user_sessions.pop(message.chat.id, None)
        show_main_menu(message.chat.id)
# отправка уведомления  
def check_reminders():
    con = sqlite3.connect('todo_reminders.db')
    now = datetime.now()
    today_str = now.strftime('%d.%m.%Y')
    time_str = now.strftime('%H:%M')
    for row in con.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall():
        table = row[0]
        if not table.startswith('user_'):
            continue
        tasks = con.execute(f"SELECT id, task FROM {table} WHERE date = '{today_str}' AND time = 'time_str' AND notification = 1 AND complete = 0").fetchall()
        user_id = table.replace('user_', '')
        for task in tasks:
            bot.send_message(user_id, f'⏰ Напоминание: {task[1]}')
    con.close()

scheduler.add_job(check_reminders, 'interval', seconds=30)

print('Сервер запущен.')
bot.polling(non_stop=True)