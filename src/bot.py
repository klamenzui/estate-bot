import telegram
from telegram.ext import Application, CommandHandler, MessageHandler, filters, CallbackContext
from telegram.ext import JobQueue
from datetime import datetime, time
import json
import os
import re
import difflib  # Für die Textannäherung

# pip install python-telegram-bot
# pip install "python-telegram-bot[job-queue]"
# Initialisierung des Telegram Bots
# sudo su -c "/root/.nvm/versions/node/v21.6.2/bin/node /root/wallets/index.js"
TOKEN = '1511669163:AAEP_FZQHSc2VFNsOBzNrnGhByBTFwrmV_A'

# Update(message=Message(channel_chat_created=False, chat=Chat(api_kwargs={'all_members_are_administrators': True}, id=-818696924, title='#5: Дача', type=<ChatType.GROUP>), date=datetime.datetime(2024, 7, 16, 5, 36, 17, tzinfo=<UTC>), delete_chat_photo=False, from_user=User(first_name='Jk', id=813664714, is_bot=False, language_code='de', username='Klamenzui'), group_chat_created=False, message_id=1560, supergroup_chat_created=False, text='test'), update_id=557737089)
# TMP = None
estate_tpl = {
    'title': '',
    'chat_id': '',
    'prev_contracts': [],
    'current_contract': 0,
    'payments': [],
    'withdrawn_payments': []
}
commands = {
        'контракт': 'contract',
        'договір': 'contract:',
        'витрати': 'expenses',
        'затрати': 'expenses',
        'зняти': 'withdraw',
        'вивести': 'withdraw',
        'вывести': 'withdraw',
        'досплати': 'topay',
        'длязняття': 'towithdraw',
        'довиведення': 'towithdraw',
        'оплачено': 'add',
        'оплатили': 'add',
        'plus': 'add',
        '?': 'help'
    }

currency = 'грн.'


def normalize_text(text):
    return re.sub(r"[^\\?\\+\w\s]", '', text.lower().strip(), flags=re.UNICODE)

def get_best_match(input_text, possible_matches):
    normalized_input = normalize_text(input_text).replace("+", "plus")
    print(f"Normalized Input: {normalized_input}")  # Debugging
    matches = difflib.get_close_matches(normalized_input, possible_matches, n=1, cutoff=0.5)  # Cutoff gesenkt
    print(f"Matches found: {matches}, possible matches: {possible_matches}")  # Debugging
    return matches[0] if matches else None


# Lade oder initialisiere die Vertragsdaten
def load_data():
    estates = {}
    if os.path.exists('estates.json'):
        with open('estates.json', 'r') as file:
            estates = json.load(file)
    return estates


def save_data(estates):
    with open('estates.json', 'w') as file:
        json.dump(estates, file)


async def send_monthly_message(context: CallbackContext):
    estates = load_data()
    now = datetime.now()
    current_month = now.strftime('%Y-%m')
    for e in estates:
        estate = estates[e]
        if estate['current_contract'] > 0:
            unpaid_total = 0
            current_month_amount = estate['current_contract']
            for p in estate['payments']:
                if not p['paid']:
                    unpaid_total += p['amount']
                elif p['date'].startswith(current_month):
                    current_month_amount -= p['amount']
            unpaid_total += current_month_amount
            if current_month_amount > 0:
                estate['payments'].append({
                    'paid': False,
                    'amount': current_month_amount,
                    'date': now.strftime('%Y-%m-%d'),
                    'withdrawn': False
                })
                save_data(estates)
            if unpaid_total > 0:
                message = f"До сплати (+ {current_month}): {unpaid_total}{currency}"
            else:
                message = f"Немає несплачених сум за {current_month}."
        else:
            message = f"Контракт відсутній!"

        await context.bot.send_message(chat_id=estate['chat_id'], text=message)


async def handle_message(update: telegram.Update, context: CallbackContext):
    estates = load_data()
    msg = update.message
    CHAT_ID = msg.chat.id
    text = msg.text.strip().lower()
    text_r = normalize_text(text)
    print(text_r)
    estate = estates.get(str(CHAT_ID), estate_tpl.copy())
    estate['title'] = msg.chat.title
    estate['chat_id'] = CHAT_ID
    best_match = get_best_match(text, commands.keys())
    print(best_match)
    if best_match:
        command = commands[best_match]
        if command == 'contract':
            new_amount = int(text.split(":")[1].strip())
            if estate['current_contract'] > 0:
                estate['prev_contracts'].append({
                    'amount': estate['current_contract'],
                    'end_date': datetime.now().strftime('%Y-%m')
                })
            estate['current_contract'] = new_amount
            await context.bot.send_message(chat_id=CHAT_ID, text=f"Контракт змінено на {new_amount}{currency}")
        elif command == 'add':
            # Muster für "10.2024 +4500"
            # Muster für "01.10.2024 оплачено 4500"
            pattern_plus = r'((?:\d{1,2}\.)?\d{1,2}\.\d{2,4})\s*\+\s*(\d+)'
            payment_date = datetime.now().strftime('%Y-%m')
            is_now = True
            is_found = False
            # Datum und Betrag aus dem ersten Format extrahieren
            match_plus = re.match(pattern_plus, text)
            if match_plus:
                date_str = match_plus.group(1)
                amount = int(match_plus.group(2))

                # Optional: Datum validieren und in standardisiertes Format umwandeln
                try:
                    payment_date = datetime.strptime(date_str, '%d.%m.%Y').strftime('%Y-%m')
                except ValueError:
                    payment_date = datetime.strptime(date_str, '%m.%Y').strftime(f'%Y-{date_str[3:5]}')
                is_now = payment_date == datetime.now().strftime('%Y-%m')
            else:
                try:
                    amount = int(text[1:].strip())
                except:
                    amount=0
            if estate['current_contract'] == 0:
                estate['current_contract'] = amount
            for p in estate['payments']:
                if p['date'] == payment_date:
                    p['amount'] = amount
                    p['paid'] = True
                    is_found = True
                    print('update', payment_date, amount)
                    break
            if is_now and not is_found:
                print('add', payment_date, amount)
                is_found = True
                estate['payments'].append({
                    'paid': True,
                    'amount': amount,
                    'date': payment_date,
                    'withdrawn': False
                })
            if is_found:
                await context.bot.send_message(chat_id=CHAT_ID, text=f"{amount}{currency} були позначені як оплачені (за {payment_date}).")
            else:
                await context.bot.send_message(chat_id=CHAT_ID, text=f"запис з {payment_date} не знайдений у базі")
        elif command == 'withdraw':
            total_withdraw = sum(p['amount'] for p in estate['payments'] if not p['withdrawn'])
            for payment in estate['payments']:
                payment['withdrawn'] = True
            estate['withdrawn_payments'].append({
                'total_withdraw': total_withdraw,
                'date': datetime.now().strftime('%Y-%m')
            })
            await context.bot.send_message(chat_id=CHAT_ID,
                                           text=f"Загальна сума виведених коштів: {total_withdraw}{currency}")
        elif command == 'topay':
            unpaid_total = sum(p['amount'] for p in estate['payments'] if not p['paid'])
            await context.bot.send_message(chat_id=CHAT_ID, text=f"Сума до сплати: {unpaid_total}{currency}")
        elif command == 'towithdraw':
            unpaid_total = sum(p['amount'] for p in estate['payments'] if not p['withdrawn'])
            await context.bot.send_message(chat_id=CHAT_ID, text=f"Сума до зняття: {unpaid_total}{currency}")
        elif command == 'help':
            help = "контракт: 1000\n"
            help += "01.01. оплачено 1000\n"
            await context.bot.send_message(chat_id=CHAT_ID, text=f"допомога: {help}")

    estates[str(CHAT_ID)] = estate
    save_data(estates)
    # await send_monthly_message(TMP)


def main():
    application = Application.builder().token(TOKEN).build()

    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    # Monatsendenachricht einrichten
    job_queue = application.job_queue or JobQueue()
    job_queue.set_application(application)
    job_queue.run_monthly(send_monthly_message, when=time(hour=0, minute=0, second=0), day=1)

    application.run_polling()


if __name__ == '__main__':
    main()
