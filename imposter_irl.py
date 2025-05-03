import shortuuid
import time
import os
import random

from dotenv import load_dotenv
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ApplicationBuilder, CommandHandler, CallbackQueryHandler, ContextTypes

load_dotenv()
bot_token = os.getenv("IMPOSTER_IRL_BOT_TOKEN")

lobbies = {}
players = {}
used_words = set()


def load_tasks():
    if os.path.exists("tasks.txt"):
        with open("tasks.txt", "r", encoding="utf-8") as file:
            return [line.strip() for line in file.readlines()]
    return []


TASKS = load_tasks()


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
        'players': [{'user_id': user_id, 'username': user.username or f"user_{user_id}"}],
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

    if 'leader' in lobbies[lobby_id] and lobbies[lobby_id]['leader']['user_id'] == user_id:
        del lobbies[lobby_id]['leader']

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


async def set_leader(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id

    if user_id not in players:
        await update.message.reply_text("Вы не находитесь ни в одном лобби.")
        return

    if len(context.args) == 0:
        await update.message.reply_text("Укажите имя пользователя ведущего после команды /leader.")
        return

    username_to_set = context.args[0].lstrip("@")

    lobby_id = players[user_id]
    lobby = lobbies.get(lobby_id)

    for player in lobby['players']:
        if player['username'] == username_to_set:
            lobby['leader'] = player
            await update.message.reply_text(f"Пользователь @{username_to_set} назначен ведущим.")
            return

    await update.message.reply_text(f"Пользователь @{username_to_set} не найден в вашем лобби.")


async def play_game(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id

    if user_id not in players:
        await update.message.reply_text("Вы не находитесь ни в одном лобби.")
        return

    lobby_id = players[user_id]
    lobby = lobbies.get(lobby_id)

    leader = lobby.get("leader")
    if not leader:
        await update.message.reply_text("Сначала выберите ведущего командой /leader.")
        return

    non_leaders = [p for p in lobby["players"] if p["user_id"] != leader["user_id"]]

    if len(non_leaders) < 2:
        await update.message.reply_text("Недостаточно игроков для начала игры (нужны минимум 2 без ведущего).")
        return

    mafia_player = random.choice(non_leaders)
    task = random.choice(TASKS)

    for player in non_leaders:
        if player["user_id"] == mafia_player["user_id"]:
            try:
                await context.bot.send_message(
                    chat_id=player["user_id"],
                    text=f"Ты мафия. Твое задание: {task}"
                )
            except Exception:
                await update.message.reply_text(f"Не удалось отправить сообщение игроку @{player['username']}")
        else:
            try:
                await context.bot.send_message(
                    chat_id=player["user_id"],
                    text="Увы, ты мирняк."
                )
            except Exception:
                await update.message.reply_text(f"Не удалось отправить сообщение игроку @{player['username']}")

    try:
        await context.bot.send_message(
            chat_id=leader["user_id"],
            text=f"Раунд начался!\nМафия: @{mafia_player['username']}\nЗадание: {task}"
        )
    except Exception:
        await update.message.reply_text("Не удалось отправить сообщение ведущему.")

    await update.message.reply_text("Игра началась! Участники получили свои роли в личных сообщениях.")


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    help_text = (
        "🔧 *Доступные команды:*\n\n"
        "📌 */start* — Получите приветственное сообщение от бота.\n\n"
        "🏗 */create <название>* — Создайте новое лобби с выбранным именем.\n\n"
        "📋 */list* — Посмотрите список доступных лобби и присоединитесь к одному из них.\n\n"
        "🚪 */leave* — Покиньте текущее лобби. Если вы были последним игроком, лобби удалится.\n\n"
        "👥 */players* — Посмотрите список участников в текущем лобби.\n\n"
        "🧑‍⚖️ */leader <@username>* — Назначьте ведущего, который будет следить за соблюдением правил.\n\n"
        "🎲 */play* — Начать игру. Один из игроков станет мафией и получит задание. Остальные получат сообщение, что они мирные жители.\n\n"
        "📖 */rules* — Узнайте правила игры.\n\n"
        "❓ */help* — Показать это сообщение с командами."
    )
    await update.message.reply_text(help_text, parse_mode='Markdown')


async def rules(update: Update, context: ContextTypes.DEFAULT_TYPE):
    rules_text = (
        "*Правила игры \"Брехло: Мафия\"* 👤🔍\n\n"
        "1. Один из участников выбирается ведущим командой */leader*.\n\n"
        "2. Ведущий запускает раунд командой */play*.\n\n"
        "3. Один случайный игрок становится *мафией* и получает личное задание (например, произнести слово, действовать определённым образом и т.д.).\n\n"
        "4. Остальные игроки становятся *мирными жителями* и получают сообщение, что они не мафия. Им не известно задание мафии.\n\n"
        "5. В течение раунда игроки взаимодействуют, обсуждают и пытаются вычислить, кто мафия по поведению.\n\n"
        "6. Ведущий может останавливать раунд, следить за выполнением задания и, по желанию, назначать штрафы.\n\n"
        "7. В конце игры можно обсудить, кто мафия и было ли выполнено задание.\n\n"
        "❗Важно: Только мафия и ведущий знают задание. Цель мафии — выполнить его и не быть раскрытым."
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
    app.add_handler(CommandHandler('leader', set_leader))
    app.add_handler(CommandHandler('play', play_game))
    app.add_handler(CommandHandler('rules', rules))

    app.add_handler(CallbackQueryHandler(join_lobby, pattern=r"^join_"))

    app.run_polling()


if __name__ == '__main__':
    main()
