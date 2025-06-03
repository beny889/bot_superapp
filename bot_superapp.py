import logging
import warnings
import gspread
import pandas as pd
from flask import Flask, request
from oauth2client.service_account import ServiceAccountCredentials
from telegram import Bot, Update
from telegram.ext import Dispatcher, CommandHandler, MessageHandler, Filters, CallbackContext
import math
import time
import os
import json

# ========== KONFIGURASI ==========
BATAS_PRIORITAS_MINIMAL = 0.8
TELEGRAM_TOKEN = os.getenv("BOT_TOKEN")
GOOGLE_CREDENTIALS = os.getenv("GOOGLE_CREDENTIALS")
PORT = int(os.environ.get('PORT', 5000))
URL_WEBHOOK = os.getenv("URL_WEBHOOK")  # contoh: https://bot-superapp.onrender.com/webhook
# =================================

warnings.simplefilter(action='ignore', category=pd.errors.SettingWithCopyWarning)

# Setup Google Sheets API
scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
creds_dict = json.loads(GOOGLE_CREDENTIALS)
creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, scope)
client = gspread.authorize(creds)

def safe_get_records(sheet, retries=3, delay=3):
    for _ in range(retries):
        try:
            return sheet.get_all_records()
        except:
            time.sleep(delay)
    return []

# Load data
sheet_stok = client.open_by_url("https://docs.google.com/spreadsheets/d/1og2koBwTwIX4VLzCMWhlBub6eQD8DXN5pOxWCLsviXs/edit").sheet1
sheet_supplier = client.open_by_url("https://docs.google.com/spreadsheets/d/1k26gU7ozWqwRDhyDksF5ktjq50rrtZImn4O2nXaUW40/edit").sheet1
sheet_beli = client.open_by_url("https://docs.google.com/spreadsheets/d/1UbrJP3m-6IU5o1Kuo7njOYMsYwQPWoy0rECjUt0lSeY/edit").sheet1

df_stok = pd.DataFrame(safe_get_records(sheet_stok))
df_supplier = pd.DataFrame(safe_get_records(sheet_supplier))
df_beli = pd.DataFrame(safe_get_records(sheet_beli))

for df in [df_stok, df_supplier, df_beli]:
    df.columns = df.columns.str.strip().str.lower()

df_stok['kode item'] = df_stok['kode item'].str.upper().str.strip()
df_supplier['kode item'] = df_supplier['kode item'].str.upper().str.strip()
df_beli['kode item'] = df_beli['kode item'].str.upper().str.strip()

user_order_cache = {}
logging.basicConfig(level=logging.INFO)

def is_discontinued(supplier_raw):
    return "discontinou" in str(supplier_raw).lower()

# ==== COMMANDS ====

def help(update: Update, context: CallbackContext):
    update.message.reply_text(
        "📌 Perintah Bot:\n"
        "• /order [supplier] [cabang]\n"
        "• /cekhpp [nama item]\n"
        "• /cekstok [keyword] [cabang]\n"
        "• /orderkeyword [keyword] [cabang]\n"
        "• Balas hasil order pakai tanda ! untuk revisi"
    )

# ... (seluruh fungsi seperti order, cekstok, orderkeyword, cekhpp, tampilkan_histori, handler_revisi_manual, handler_pilihan_angka tetap sama)
# Karena terlalu panjang, bisa saya kirim terpisah jika kamu butuh ulang dari fungsi-fungsinya.

# === FLASK APP ===
app = Flask(__name__)
bot = Bot(token=TELEGRAM_TOKEN)
dispatcher = Dispatcher(bot, None, workers=4)

# Register all handlers
dispatcher.add_handler(CommandHandler("help", help))
dispatcher.add_handler(CommandHandler("order", order))
dispatcher.add_handler(CommandHandler("cekhpp", cekhpp))
dispatcher.add_handler(CommandHandler("cekstok", cekstok))
dispatcher.add_handler(CommandHandler("orderkeyword", orderkeyword))
dispatcher.add_handler(MessageHandler(Filters.text & Filters.regex(r"^revisi:"), handler_revisi_manual))
dispatcher.add_handler(MessageHandler(Filters.text & ~Filters.command, handler_pilihan_angka))
dispatcher.add_handler(MessageHandler(Filters.text & ~Filters.command, handler_revisi_manual))

@app.route('/')
def index():
    return "Bot is running!"

@app.route('/webhook', methods=['POST'])
def webhook():
    update = Update.de_json(request.get_json(force=True), bot)
    dispatcher.process_update(update)
    return 'ok'

# Set webhook on startup
if __name__ == '__main__':
    bot.set_webhook(URL_WEBHOOK + "/webhook")
    app.run(host='0.0.0.0', port=PORT)
