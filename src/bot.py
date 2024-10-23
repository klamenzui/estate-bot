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
bot_memory = {}
estate_tpl = {
    'title': '',
    'chat_id': '',
    'prev_contracts': [],
    'current_contract': 0,
    'payments': [],
    'expenses': [],
    'withdrawn_payments': []
}
commands = {
    'контракт': 'contract',
    'договір': 'contract',
    'договірпідписано': 'contract',
    'зняти': 'withdraw',
    'вивести': 'withdraw',
    'вывести': 'withdraw',
    'досплати': 'topay',
    'длязняття': 'towithdraw',
    'довиведення': 'towithdraw',
    'payed': 'add',
    'payment': 'add',
    'заплачено': 'add',
    'заплатила': 'add',
    'заплатив': 'add',
    'оплачено': 'add',
    'оплатили': 'add',
    'plus': 'add',
    'язаплатилаза': 'expenses',
    'язаплатила': 'expenses',
    'витрати': 'expenses',
    'затрати': 'expenses',
    'minus': 'expenses',
    '?': 'help',
    'якце': 'help',
}

currency = 'грн.'
def get_best_match(input_text, possible_matches):
    #print(possible_matches)
    #matches = difflib.get_close_matches(input_text, possible_matches, n=1, cutoff=0.5)  # Cutoff gesenkt
    ratios = []
    for cmd in possible_matches:
        seq_match = difflib.SequenceMatcher(None, input_text, cmd)
        ratios.append(seq_match.ratio())
    #print(ratios)  # Check the similarity of the two strings
    maximum = max(ratios)
    #maximum = sorted(ratios, reverse=True)
    #print(possible_matches)
    #print(ratios)
    #return matches[0] if matches else None
    index = ratios.index(maximum)
    res = possible_matches[index] if maximum > 0.3 else None
    return res, possible_matches[index]

def extract_date_amount(text):
    # Patterns to capture dates and amounts with optional currency
    date_pattern = r'\b(\d{1,2})[-./](\d{1,2})(?:[-./](\d{2,4}))?\b'
    amount_pattern = r'(\+?\-?\d+)\s*(\$|€|£|₴)?'

    # Get the current year
    current_year = datetime.now().year

    # Find all date matches
    date_matches = re.findall(date_pattern, text)
    p = re.compile(date_pattern)
    date = None
    for m in p.finditer(text):
        # Pick the first valid date match
        day, month, year = m.groups()
        if month and len(month) == 4:
            year = month
            month = day
            day = 1
        year = int(year) if year else current_year
        if year < 100:
            year += 2000
        try:
            date = datetime(year, int(month), int(day)).date()
        except ValueError:
            date = None
        text = text.replace(m.group(), '')
        break

    # Find all amount matches
    amount_matches = re.findall(amount_pattern, text)
    amount, currency = None, None
    if amount_matches:
        # Pick the first valid amount match
        amount_str, currency_symbol = amount_matches[0]
        amount = int(re.sub(r'[^\d+]', '', amount_str))  # Remove non-numeric characters from the amount
        currency = currency_symbol if currency_symbol else None
        text = text.replace(str(amount), '')
        if currency is not None:
            text = text.replace(currency, '')

    return date, amount, currency, text

# Lade oder initialisiere die Vertragsdaten
def load_data():
    estates = {}
    if os.path.exists('src/estates.json'):
        with open('src/estates.json', 'r') as file:
            estates = json.load(file)
    return estates


def save_data(estates):
    with open('src/estates.json', 'w') as file:
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
    cur_month = datetime.now().strftime('%Y-%m')
    estates = load_data()
    print(update)
    msg = update.message
    title = msg.reply_to_message.forum_topic_created.name if msg.is_topic_message else msg.chat.title
    estate_id = title.split(":")[0]
    message_id = msg.message_id
    CHAT_ID = msg.chat.id
    message = msg.text.strip().lower()
    estate = estates.get(str(estate_id), estate_tpl.copy())
    estate['title'] = title
    estate['id'] = estate_id

    date, amount, msg_currency, text = extract_date_amount(message)
    text = text.replace("+", "plus").replace("-", "minus")
    text = text.strip().lower()
    if text == '':
        text = 'plus'
    keys_list = [*commands]
    res, best_match = get_best_match(text, keys_list)
    if res:
        command = commands[res]
        if command == 'contract':
            if estate['current_contract'] > 0:
                estate['prev_contracts'].append({
                    'amount': estate['current_contract'],
                    'end_date': datetime.now().strftime('%Y-%m')
                })
            estate['current_contract'] = amount
            await context.bot.send_message(chat_id=CHAT_ID, reply_to_message_id=message_id,
                                           text=f"Контракт змінено на {amount}{currency}")
        elif command == 'add':
            payment_date = date.strftime('%Y-%m') if date is not None else cur_month
            is_now = payment_date == cur_month
            is_found = False
            if amount is None:
                return
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
                await context.bot.send_message(chat_id=CHAT_ID, reply_to_message_id=message_id,
                                               text=f"{amount}{currency} були позначені як оплачені (за {payment_date}).")
            else:
                await context.bot.send_message(chat_id=CHAT_ID, reply_to_message_id=message_id,
                                               text=f"запис з {payment_date} не знайдений у базі")
        elif command == 'expenses':
            payment_date = date.strftime('%Y-%m') if date is not None else cur_month
            estate['expenses'] = estate['expenses'] if 'expenses' in estate else []
            if amount is None:
                return
            print('minus', payment_date, amount)
            estate['expenses'].append({
                'amount': amount,
                'date': payment_date,
                'withdrawn': False,
                'comment': text
            })
            await context.bot.send_message(chat_id=CHAT_ID, reply_to_message_id=message_id,
                                           text=f"{amount}{currency} були позначені як витрати (у {payment_date}).")
        elif command == 'withdraw':
            total_withdraw = sum(p['amount'] for p in estate['payments'] if not p['withdrawn'])
            total_expenses = sum(p['amount'] for p in estate['expenses'] if not p['withdrawn'])
            total_withdraw = total_withdraw - total_expenses
            for payment in estate['payments']:
                payment['withdrawn'] = True
            for expense in estate['expenses']:
                expense['withdrawn'] = True
            estate['withdrawn_payments'].append({
                'total_withdraw': total_withdraw,
                'date': cur_month
            })
            await context.bot.send_message(chat_id=CHAT_ID, reply_to_message_id=message_id,
                                           text=f"Загальна сума виведених коштів: {total_withdraw}{currency}")
        elif command == 'topay':
            unpaid_total = sum(p['amount'] for p in estate['payments'] if not p['paid'])
            await context.bot.send_message(chat_id=CHAT_ID, reply_to_message_id=message_id,
                                           text=f"Сума до сплати: {unpaid_total}{currency}")
        elif command == 'towithdraw':
            unpaid_total = sum(p['amount'] for p in estate['payments'] if not p['withdrawn'])
            expenses_total = sum(p['amount'] for p in estate['expenses'] if not p['withdrawn'])
            unpaid_total = unpaid_total - expenses_total
            await context.bot.send_message(chat_id=CHAT_ID, reply_to_message_id=message_id,
                                           text=f"Сума до зняття: {unpaid_total}{currency}")
        elif command == 'help':
            help = "контракт: 1000\n"
            help += "01.01. оплачено 1000\n"
            await context.bot.send_message(chat_id=CHAT_ID, reply_to_message_id=message_id, text=f"допомога: {help}")
    else:
        print('gues', commands[best_match])



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
