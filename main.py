import shortuuid
import time
import os
import random

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ApplicationBuilder, CommandHandler, CallbackQueryHandler, ContextTypes

bot_token = ''

lobbies = {}
players = {}
used_words = set()


def load_words():
    if os.path.exists("words.txt"):
        with open("words.txt", "r", encoding="utf-8") as file:
            return [line.strip() for line in file.readlines()]
    return []


words = load_words()


async def start(update: Update, context):
    await update.message.reply_text(
        "Привет! Я Брехло!\nНапишите /help, чтобы узнать доступные команды, \n/rules, чтобы узнать правила игры. ")


async def create_lobby(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    user_id = user.id

    if len(context.args) == 0:
        await update.message.reply_text("Введите название для лобби после команды /create.")
        return

    lobby_name = ' '.join(context.args)

    lobby_id = str(shortuuid.uuid())

    lobbies[lobby_id] = {
        'name': lobby_name,
        'players': [{'user_id': user_id, 'username': user.username}],
        'created_at': time.time()
    }
    players[user_id] = lobby_id

    await update.message.reply_text(f"Лобби '{lobby_name}' создано с идентификатором: {lobby_id}")
    await update.message.reply_text(f"Вы присоединились к лобби '{lobby_name}'!")


async def list_lobbies(update: Update, context):
    if not lobbies:
        await update.message.reply_text("Нет активных лобби.")
        return

    keyboard = []
    for lobby_id, lobby_data in lobbies.items():
        keyboard.append(
            [InlineKeyboardButton(f"{lobby_data['name']} (ID: {lobby_id})", callback_data=f"join_{lobby_id}")])

    reply_markup = InlineKeyboardMarkup(keyboard)

    await update.message.reply_text("Выберите лобби для присоединения:", reply_markup=reply_markup)


async def players_list(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id

    if user_id not in players:
        await update.message.reply_text("Вы не находитесь ни в одном лобби.")
        return

    lobby_id = players[user_id]
    lobby = lobbies[lobby_id]

    lobby_creation_time = time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(lobby['created_at']))

    player_count = len(lobby['players'])
    player_list = ', '.join(f"{player['username']} (User ID: {player['user_id']})" for player in lobby['players'])

    stats_message = (
        f"Лобби: {lobby['name']}\n"
        f"Количество участников: {player_count}\n"
        f"Участники: {player_list}\n"
        f"Время создания лобби: {lobby_creation_time}"
    )

    await update.message.reply_text(stats_message)


async def join_lobby(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    user = update.effective_user
    user_id = user.id

    lobby_id = query.data.split("_")[1]

    if lobby_id not in lobbies:
        await query.edit_message_text(text="Лобби не существует или было удалено.")
        return

    if user_id in players:
        await query.edit_message_text(text="Вы уже присоединились к другому лобби!")
        return

    if 'players' not in lobbies[lobby_id]:
        lobbies[lobby_id]['players'] = []

    lobbies[lobby_id]['players'].append({'user_id': user_id, 'username': user.username})
    players[user_id] = lobby_id

    lobby_name = lobbies[lobby_id]['name']
    await query.edit_message_text(text=f"Вы присоединились к лобби '{lobby_name}'!")


async def leave(update: Update, context):
    user = update.effective_user
    user_id = user.id

    if user_id not in players:
        await update.message.reply_text("Вы не находитесь ни в одном лобби.")
        return

    lobby_id = players[user_id]
    lobby_name = lobbies[lobby_id]['name']

    player_found = False
    for player in lobbies[lobby_id]['players']:
        if player['user_id'] == user_id:
            lobbies[lobby_id]['players'].remove(player)
            player_found = True
            break

    if not player_found:
        await update.message.reply_text(
            "Не удалось удалить вас из лобби, так как ваше имя не найдено в списке участников.")
        return

    del players[user_id]

    if not lobbies[lobby_id]['players']:
        del lobbies[lobby_id]
        await update.message.reply_text(
            f"Вы покинули лобби '{lobby_name}', и оно было удалено, так как не осталось участников.")
    else:
        await update.message.reply_text(f"Вы покинули лобби '{lobby_name}'.")


async def play(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    user_id = user.id

    lobby_id = players.get(user_id)
    print(lobbies)

    if not lobby_id:
        await update.message.reply_text("Вы не находитесь в лобби.")
        return

    if len(used_words) >= len(words):
        await update.message.reply_text("Все слова уже были использованы.")
        return

    available_words = list(set(words) - used_words)
    chosen_word = random.choice(available_words)

    players_in_lobby = lobbies[lobby_id]['players']
    liar = random.choice(players_in_lobby)

    used_words.add(chosen_word)

    for player in players_in_lobby:
        await context.bot.send_message(chat_id=player['user_id'], text="Игра началась! Проверьте свои сообщения.")
        if player == liar:
            await context.bot.send_message(chat_id=player['user_id'], text="Ваше слово: Брехло")
        else:
            await context.bot.send_message(chat_id=player['user_id'], text=f"Ваше слово: {chosen_word}")


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    help_text = (
        "Доступные команды:\n\n"
        "1. **/start**: Запустите бота и получите приветственное сообщение. Вы также получите информацию о доступных функциях и командах.\n\n"
        "2. **/create**: Создайте новое лобби для игры. Бот запросит название лобби.\n\n"
        "3. **/list**: Просмотрите список всех доступных лобби, созданных другими пользователями, с указанием их названия и количества участников.\n\n"
        "4. **/leave**: Покиньте текущее лобби. Если в лобби не осталось участников, оно будет автоматически удалено.\n\n"
        "5. **/players**: Посмотрите список всех игроков, присутствующих в текущем лобби, включая их имена и статусы.\n\n"
        "6. **/play**: Запустите игровую сессию в текущем лобби, если достаточно участников. Начните игровой процесс и взаимодействие между участниками.\n\n"
        "7. **/rules**: Выводит подробные правила игры \"Брехло\" с описанием всех этапов игры.\n\n"
        "8. **/help**: Выводит полное описание всех доступных команд бота."
    )
    await update.message.reply_text(help_text, parse_mode='Markdown')



async def rules(update: Update, context: ContextTypes.DEFAULT_TYPE):
    rules_text = (
        "Правила игры \"Брехло\":\n\n"
        "1. **Выдача карточек**: Каждому игроку раздаётся карточка с загаданным словом, но одному игроку даётся карточка с надписью «Брехло». Этот игрок не знает загаданного слова, но должен притворяться, что знает.\n\n"
        "2. **Ассоциации**: Каждый игрок по очереди называет ассоциацию к загаданному слову. Цель игроков, знающих слово, — назвать ассоциацию, не слишком очевидную для \"Брехло\", но понятную другим игрокам.\n\n"
        "3. **Задача Брехло**: Игрок с карточкой «Брехло» должен придумывать ассоциации и не выдавать, что он не знает слово.\n\n"
        "4. **Обсуждение и голосование**: После нескольких кругов ассоциаций, игроки обсуждают и голосуют, пытаясь угадать, кто «Брехло».\n\n"
        "5. **Окончание игры**: Если «Брехло» угадан, он проигрывает. Если никто не угадал, или если «Брехло» угадывает слово, он выигрывает."
    )
    await update.message.reply_text(rules_text, parse_mode='Markdown')


def main():
    token = bot_token

    app = ApplicationBuilder().token(token).build()

    app.add_handler(CommandHandler('start', start))
    app.add_handler(CommandHandler('create', create_lobby))
    app.add_handler(CommandHandler('list', list_lobbies))
    app.add_handler(CommandHandler('leave', leave))
    app.add_handler(CommandHandler('help', help_command))
    app.add_handler(CommandHandler('players', players_list))
    app.add_handler(CommandHandler('play', play))
    app.add_handler(CommandHandler('rules', rules))

    app.add_handler(CallbackQueryHandler(join_lobby, pattern=r"^join_"))

    app.run_polling()


if __name__ == '__main__':
    main()
