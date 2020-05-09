import config
import telebot
from telebot import apihelper
import sqlite3
import re

token = config.TOKEN

# тут у нас записывается прокси
apihelper.proxy = config.PROXY

bot = telebot.TeleBot(token)

# количество товаров
list_null_orders = str([0]*config.COUNT_PRODUCTS).replace('[','').replace(']','')

# нужно ли показывать помощь
#showhelp_orders = True
#showhelp_photo = True

# подключение к базе данных
conn = sqlite3.connect(config.DATABASE_PATH, check_same_thread=False)

cursor = conn.cursor()

# Запуск бота
@bot.message_handler(commands=['start'])
def start_message(message):
    keyboard = telebot.types.InlineKeyboardMarkup()  
    keyboard.add(telebot.types.InlineKeyboardButton("Перейти к заказу", callback_data="to_order")) # заказ
    bot.send_message(message.chat.id, "Здравствуйте! Выберите заказ. Еда доставляется курьером.", reply_markup=keyboard)
    cursor.execute("SELECT * FROM users WHERE user_id = ?", (message.chat.id,))
    result = cursor.fetchall()
    print(message)
    if len(result) == 0:
        cursor.execute("INSERT INTO users VALUES (?, ?, ?, ?)", 
                       (message.chat.id, list_null_orders, "null", 0))
        conn.commit()
    else:
        cursor.execute("""UPDATE users SET
        list_orders = ?,
        state = ?,
        price = ? 
        WHERE user_id = ?""", 
                       (list_null_orders, "null", 0, message.chat.id))
        conn.commit()

# обработка callback-ов
@bot.callback_query_handler(func=lambda call: True)
def call_handler(call):
    bot.answer_callback_query(call.id)
    data = call.data
    if data == "to_order":
        write_orders(call.message)

# пишем заказы
def write_orders(message):
    bot.send_chat_action(message.chat.id, 'typing')
    keyboard = telebot.types.ReplyKeyboardMarkup(resize_keyboard=True)
    keyboard.add(telebot.types.KeyboardButton("Добавить товары"))
    keyboard.add(telebot.types.KeyboardButton("Перейти к корзине"))
    keyboard.add(telebot.types.KeyboardButton("Отобразить фотографии"))
    keyboard.add(telebot.types.KeyboardButton("Оформить заказ"))
    keyboard.add(telebot.types.KeyboardButton("Посмотреть акции и скидки"))
    bot.send_message(message.chat.id, text_wrapper(), reply_markup=keyboard)

# добавление товаров
@bot.message_handler(regexp="Добавить товары")
def add_products(message):
    #global showhelp_orders
    bot.send_message(message.chat.id, "Введите номер товара:")
    bot.send_message(message.chat.id, "Возможно введение нескольких номеров, напрмер 1, 3, 5, 6 (через запятую)\n"
    + "Для заказа нескольких штук одного товара наберите " +
                    "номер_товара*количество_товаров, например 2*6")
    state = "order"
    set_state('order', message)
    #showhelp_orders = False

# вывод акций
@bot.message_handler(regexp="Посмотреть акции и скидки")
def show_stocks(message):
    bot.send_chat_action(message.chat.id, 'typing')
    cursor.execute("SELECT description FROM stocks")
    stocks = cursor.fetchall()[0][0]
    if stocks is not None:
        bot.send_message(message.chat.id, stocks)
    else:
        cursor.execute("SELECT placeholder FROM stocks")
        stocks = cursor.fetchall()[0][0]
        bot.send_message(message.chat.id, stocks)

# показ фотографий
@bot.message_handler(regexp="Отобразить фотографии")
def show_photo(message):
    #global showhelp_photo
    bot.send_message(message.chat.id, "Введите номер фотографии:")
    bot.send_message(message.chat.id, "Возможно введение нескольких номеров, напрмер 1, 3, 5, 6 (через запятую)")
    set_state('photo', message)
    conn.commit()
    #showhelp_photo = False

# корзина
@bot.message_handler(regexp="Перейти к корзине")
def show_(message):
    list_orders = select_list_orders(message)
    count = 0
    for i in list_orders:
        count = count + i
    show_busket(message, count)


# удаление товаров из корзины
@bot.message_handler(regexp="Удалить товары из корзины")
def delete_from_busket(message):
    bot.send_message(message.chat.id, "Введите номер товара, которые вы хотите удалить")
    bot.send_message(message.chat.id, "Возможно введение нескольких номеров, напрмер 1, 3, 5, 6 (через запятую).\n" + 
                     "Для удаления нескольких штук товара наберите номер_товара*количество_товаров, например 2*6\n")
    set_state("DFB", message)

# очистить корзину и перейти обратно к заказу
@bot.message_handler(regexp="Очистить корзину и вернуться к заказу товаров")
def clear_and_go_to_menu(message):
    update_orders(list_null_orders, message)
    conn.commit()
    write_orders(message)

# перейти обратно к заказу
@bot.message_handler(regexp="Вернуться к заказу товаров")
def go_to_menu(message):
    write_orders(message)

## перейти к заказу
#@bot.message_handler(regexp="Оформить заказ")
#def go_to_order(message):
#    write_orders(message)

# ввод значений
@bot.message_handler(regexp=r'[\d\s,\*]+')
def string_wrapper(message):
    if re.match(r'[\d\s,\*]+', message.text)[0] == message.text:
        temp_str = []
        cursor.execute("SELECT state FROM users WHERE user_id = ?", (message.chat.id,))
        state = cursor.fetchall()[0][0]
        list_orders = ""
        if state == "order":
            temp_str = message.text.split(",")
            temp_str = list(map(lambda x: x.replace(' ', '').split('*'), temp_str))
            set_state('null', message)
            temp_str = to_order_list(temp_str)
            count = 0
            for i in temp_str:
                count = count + i
            bot.send_message(message.chat.id, case_form(count))

            list_orders = select_list_orders(message)
            list_orders = str([x+y for x,y in zip(temp_str, list_orders)]).replace('[','').replace(']','')
            update_orders(list_orders, message)

        if state == "photo":
            temp_str = message.text.split(",")
            show_photos(temp_str, message)
            set_state('null', message)

        if state == "DFB":
            temp_str = message.text.split(",")
            temp_str = list(map(lambda x: x.replace(' ', '').split('*'), temp_str))
            set_state('null', message)
            temp_str = to_order_list(temp_str)
            count = 0
            list_orders = select_list_orders(message)

            for i in range(0, config.COUNT_PRODUCTS-1):
                if list_orders[i] - temp_str[i] >= 0:
                    count = count + temp_str[i]
                else:
                    count = count + list_orders[i]

            bot.send_message(message.chat.id, case_form_deleted(count))
            list_orders = [(lambda x,y: max(x-y, 0))(x, y) for x,y in zip(list_orders, temp_str)]
            update_orders(str(list_orders).replace('[','').replace(']',''), message)

            count = 0

            for i in list_orders:
                count = count + i

            show_busket(message, count)
    else:
        bot.send_message(message.chat.id, "Введена неверная команда")

def show_photos(photos_list, message):
    cursor.execute("SELECT image_id FROM products")
    image_ids = cursor.fetchall()

    for i in photos_list:
        bot.send_photo(message.chat.id, image_ids[int(i)-1][0])


# сообщения с неясными целями
@bot.message_handler(content_types=['text'])
def standert_answer(message):
    bot.send_message(message.chat.id, "К сожалению, распознать команду не удалось")

# --- вспомогательные функции ---

def set_state(state, message):
    cursor.execute("""UPDATE users SET
        state = ?
        WHERE user_id = ?""", (state, message.chat.id))
    conn.commit()

def update_orders(list_orders, message):
    cursor.execute("""UPDATE users SET 
        list_orders = ?
        WHERE user_id = ?""", (list_orders, message.chat.id))
    conn.commit()

def select_list_orders(message):
    cursor.execute("SELECT list_orders FROM users WHERE user_id = ?", (message.chat.id,))
    list_orders = list(map(lambda x: int(x), cursor.fetchall()[0][0].split(',')))
    return list_orders

def text_wrapper():
    cursor.execute("SELECT price, desciption FROM products")
    f = cursor.fetchall()

    text = "Меню:\n"
    num = 0
    curr = config.CURRENCY

    for line in f:
        text = text + str(num+1) + ". " + line[1] + " - " + str(line[0]) + ' ' + curr + '\n'
        num = num + 1
    return text

def to_order_list(orders):
    temp_list = [0]*config.COUNT_PRODUCTS
    for i in orders:
        if len(i) == 1:
            temp_list[int(i[0])-1] = temp_list[int(i[0])-1] + 1
        else:
            temp_list[int(i[0])-1] = temp_list[int(i[0])-1] + int(i[1])
    return temp_list

def case_form(count):
    if count == 1:
        return "В корзину добавлен 1 товар"
    if count >= 2 and count <= 4:
        return "В корзину добавлено " + str(count) + " товара"
    if count >= 5:
        return "В корзину добавлено " + str(count) + " товаров"

def case_form_deleted(count):
    if count == 1:
        return "Из корзины удалён 1 товар"
    if count >= 2 and count <= 4:
        return "Из корзины удалено " + str(count) + " товара"
    if count >= 5:
        return "Из корзины удалены " + str(count) + " товаров"

def show_busket(message, count):
    bot.send_chat_action(message.chat.id, 'typing')
    if count != 0:
        temp_str = "В корзине находится:\n"
        lines = []
        cursor.execute("SELECT name FROM products")
        lines = cursor.fetchall()

        list_orders = select_list_orders(message)
        price = 0

        cursor.execute("SELECT price FROM products")
        list_prices = cursor.fetchall()

        for i in range(0, config.COUNT_PRODUCTS-1):
            if list_orders[i] != 0:
                temp_str = temp_str + str(i+1) + ". " + lines[i][0] + " - " + str(list_orders[i]) + " шт.\n"
                price = price + list_orders[i]*list_prices[i][0]

        temp_str = temp_str + "К оплате: " + str(price) + ' ' + config.CURRENCY

        cursor.execute("""UPDATE users SET
        price = ?
        WHERE user_id = ?""", (price, message.chat.id))
        conn.commit()

        keyboard = telebot.types.ReplyKeyboardMarkup(resize_keyboard=True)
        keyboard.add(telebot.types.KeyboardButton("Оформить заказ"))
        keyboard.add(telebot.types.KeyboardButton("Удалить товары из корзины"))
        keyboard.add(telebot.types.KeyboardButton("Вернуться к заказу товаров"))
        keyboard.add(telebot.types.KeyboardButton("Очистить корзину и вернуться к заказу товаров"))
        bot.send_message(message.chat.id, temp_str, reply_markup=keyboard)

    else:
        bot.send_message(message.chat.id, "Корзина пуста")

bot.polling(none_stop=True, timeout=5)

conn.close()
