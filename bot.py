import telegram
from telegram.ext import Application, CommandHandler, MessageHandler, filters, CallbackContext
from telegram.ext import JobQueue
from datetime import datetime, time
import json
import os
import re

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
currency = 'грн.'


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
    print(update)
    # TMP = context
    msg = update.message
    CHAT_ID = msg.chat.id
    text = msg.text.strip().lower()
    text_r = re.sub(r"[^\w\s]", '', text.lower())
    estate = estates[str(CHAT_ID)] if str(CHAT_ID) in estates else estate_tpl.copy()
    estate['title'] = msg.chat.title
    estate['chat_id'] = CHAT_ID
    if text.startswith("контракт:") or text.startswith("договір:"):
        new_amount = int(text.split(":")[1].strip())
        if estate['current_contract'] > 0:
            estate['prev_contracts'].append({
                'amount': estate['current_contract'],
                'end_date': datetime.now().strftime('%Y-%m-%d')
            })
        estate['current_contract'] = new_amount
        await context.bot.send_message(chat_id=CHAT_ID, text=f"Контракт змінено на {new_amount}{currency}")
    elif text.startswith("+"):
        amount = int(text[1:].strip())
        if estate['current_contract'] == 0:
            estate['current_contract'] = amount
        estate['payments'].append({
            'paid': True,
            'amount': amount,
            'date': datetime.now().strftime('%Y-%m-%d'),
            'withdrawn': False
        })
        await context.bot.send_message(chat_id=CHAT_ID, text=f"{amount}{currency} були позначені як оплачені.")
    elif text_r == "зняти" or text_r == "вивести":
        total_withdraw = sum(p['amount'] for p in estate['payments'] if not p['withdrawn'])
        for payment in estate['payments']:
            payment['withdrawn'] = True
        estate['withdrawn_payments'].append({
            'total_withdraw': total_withdraw,
            'date': datetime.now().strftime('%Y-%m-%d')
        })
        await context.bot.send_message(chat_id=CHAT_ID,
                                       text=f"Загальна сума виведених коштів: {total_withdraw}{currency}")
    elif text_r == "досплати":
        unpaid_total = sum(p['amount'] for p in estate['payments'] if not p['paid'])
        await context.bot.send_message(chat_id=CHAT_ID, text=f"Сума до сплати: {unpaid_total}{currency}")
    elif text_r == "дозняття" or text_r == "довиведення":
        unpaid_total = sum(p['amount'] for p in estate['payments'] if not p['withdrawn'])
        await context.bot.send_message(chat_id=CHAT_ID, text=f"Сума до зняття: {unpaid_total}{currency}")
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
