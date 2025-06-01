import logging
import warnings
import gspread
import pandas as pd
from oauth2client.service_account import ServiceAccountCredentials
from telegram.ext import Updater, CommandHandler, MessageHandler, Filters
import math
import time
import os

# ========== KONFIGURASI ==========
BATAS_PRIORITAS_MINIMAL = 0.8
TELEGRAM_TOKEN = os.getenv("BOT_TOKEN")
CREDENTIALS_FILE = "credentials.json"
# =================================

warnings.simplefilter(action='ignore', category=pd.errors.SettingWithCopyWarning)

# Autentikasi Google Sheets
scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
creds = ServiceAccountCredentials.from_json_keyfile_name(CREDENTIALS_FILE, scope)
client = gspread.authorize(creds)

def safe_get_records(sheet, retries=3, delay=3):
    for _ in range(retries):
        try:
            return sheet.get_all_records()
        except:
            time.sleep(delay)
    return []

# Load Sheets
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

def cekhpp(update, context):
    try:
        args = context.args
        if not args:
            update.message.reply_text("Format: /cekhpp [nama item]")
            return
        keyword = " ".join(args).lower()
        cocok = df_stok[df_stok['nama item'].str.lower().str.contains(keyword)]
        if cocok.empty:
            update.message.reply_text("Item tidak ditemukan.")
            return
        elif len(cocok) == 1:
            tampilkan_histori(update, cocok.iloc[0]['kode item'], cocok.iloc[0]['nama item'])
        else:
            pilihan = []
            teks = [f"🔍 Ditemukan {len(cocok)} item:\n"]
            for i, (_, row) in enumerate(cocok.iterrows(), 1):
                teks.append(f"{i}. {row['nama item']} ({row['kode item']})")
                pilihan.append({'kode item': row['kode item'], 'nama item': row['nama item']})
                if i >= 10:
                    teks.append("⚠️ Maks 10.")
                    break
            context.user_data['cekhpp_selection'] = pilihan
            update.message.reply_text("\n".join(teks) + "\n\nKetik angka (1-10) untuk pilih.")
    except Exception as e:
        update.message.reply_text(f"Terjadi kesalahan: {e}")

def tampilkan_histori(update, kode, nama):
    df_item = df_beli[df_beli['kode item'] == kode].copy()
    if df_item.empty:
        update.message.reply_text(f"Histori kosong untuk: {nama}")
        return
    df_item['tanggal pembelian'] = pd.to_datetime(df_item['tanggal pembelian'], errors='coerce')
    df_item = df_item.sort_values(by='tanggal pembelian', ascending=False)
    hasil = [f"🛒 {nama} ({kode})"]
    for _, row in df_item.head(5).iterrows():
        hasil.append(f"• {row['tanggal pembelian'].date()} – Rp{int(row['harga dasar']):,} – {row['supplier']}".replace(",", "."))
    update.message.reply_text("\n".join(hasil), parse_mode='HTML')

def handler_pilihan_angka(update, context):
    if 'cekhpp_selection' not in context.user_data:
        return
    try:
        angka = int(update.message.text.strip())
        pilihan = context.user_data['cekhpp_selection']
        if 1 <= angka <= len(pilihan):
            item = pilihan[angka - 1]
            tampilkan_histori(update, item['kode item'], item['nama item'])
        else:
            update.message.reply_text("Angka tidak valid.")
    except:
        update.message.reply_text("Masukkan angka valid.")
    finally:
        context.user_data.pop('cekhpp_selection', None)

def is_discontinued(supplier_raw):
    return "discontinou" in str(supplier_raw).lower()

def cekstok(update, context):
    try:
        args = context.args
        if not args:
            update.message.reply_text("Format: /cekstok [keyword] [cabang (opsional)]")
            return

        cabang_opsi = ['pkp', 'bjg', 'cld']
        if args[-1].lower() in cabang_opsi:
            cabang = args[-1].lower()
            keyword = " ".join(args[:-1]).lower()
        else:
            cabang = "all"
            keyword = " ".join(args).lower()

        cocok = df_stok[df_stok['nama item'].str.lower().str.contains(keyword)]
        hasil = []

        for _, row in cocok.iterrows():
            kode = row['kode item']
            supp = df_supplier[df_supplier['kode item'] == kode]

            # Filter jika supplier termasuk discontinou
            if not supp.empty and is_discontinued(supp.iloc[0].get('supplier')):
                continue

            nama = row['nama item']
            if cabang == "all":
                stok_text = f"PKP:{row.get('stok cab. pkp', 0)} | BJG:{row.get('stok cab. bjg', 0)} | CLD:{row.get('stok cab. cld', 0)}"
            else:
                stok_text = f"{cabang.upper()}: {row.get(f'stok cab. {cabang}', 0)}"

            hasil.append(f"• {nama} ({kode}) → {stok_text}")

        if not hasil:
            update.message.reply_text("Tidak ditemukan.")
        else:
            update.message.reply_text("\n".join(hasil[:10]) + ("\n⚠️ Maks 10 item." if len(hasil) > 10 else ""))

    except Exception as e:
        update.message.reply_text(f"Terjadi kesalahan: {e}")


def orderkeyword(update, context):
    try:
        args = context.args
        if not args:
            update.message.reply_text("Format: /orderkeyword [keyword] [cabang/all]")
            return
        cabang_opsi = ['pkp', 'bjg', 'cld']
        if args[-1].lower() in cabang_opsi:
            cabang = args[-1].lower()
            keyword = " ".join(args[:-1]).lower()
        else:
            cabang = "pkp"
            keyword = " ".join(args).lower()

        kolom_stok = f"stok cab. {cabang}"
        kolom_min = f"minimal stok {cabang}"

        cocok = df_supplier[df_supplier['nama item'].str.lower().str.contains(keyword)]
        hasil, total = [], 0
        for _, row in cocok.iterrows():
            if is_discontinued(row.get('supplier')): continue
            kode = row['kode item']
            nama = row['nama item']
            min_stok = int(float(row.get(kolom_min, 0) or 0))
            stok_row = df_stok[df_stok['kode item'] == kode]
            if stok_row.empty: continue
            stok_aktual = int(float(stok_row.iloc[0].get(kolom_stok, 0) or 0))
            kekurangan = max(0, min_stok - stok_aktual)
            if kekurangan == 0: continue
            qty = int(row.get('qty satuan order', 1) or 1)
            order_qty = int(math.ceil(kekurangan / qty) * qty)

            df_item = df_beli[df_beli['kode item'] == kode].copy()
            harga = 0
            if not df_item.empty:
                df_item['tanggal pembelian'] = pd.to_datetime(df_item['tanggal pembelian'], errors='coerce')
                harga = df_item.sort_values(by='tanggal pembelian', ascending=False).iloc[0].get('harga dasar', 0)

            if kekurangan / (stok_aktual + 1) < BATAS_PRIORITAS_MINIMAL: continue
            total += order_qty * harga
            hasil.append(f"• {nama} // {order_qty}pc #{stok_aktual}")

        if not hasil:
            update.message.reply_text("Tidak ada item yang layak.")
            return
        teks = f"🧾 Order Keyword: \"{keyword}\" – Cabang: {cabang.upper()}\n\n" + "\n".join(hasil)
        teks += f"\n\n💰 Total Order: Rp{int(total):,}".replace(",", ".")
        update.message.reply_text(teks, parse_mode='HTML')
    except Exception as e:
        update.message.reply_text(f"Terjadi kesalahan: {e}")

def handler_revisi_manual(update, context):
    teks = update.message.text
    if "📦 Order List" not in teks:
        return
    baris = teks.strip().splitlines()
    header, hasil = [], []
    for line in baris:
        if line.strip().startswith("•") and "!" in line:
            continue
        elif line.strip().startswith("•"):
            hasil.append(line)
        else:
            header.append(line)
    if not hasil:
        update.message.reply_text("Semua item dihapus. List kosong.")
    else:
        update.message.reply_text("\n".join(header + [""] + hasil))

def help(update, context):
    teks = (
        "📌 Perintah Bot:\n"
        "• /order [supplier] [cabang]\n"
        "• /cekhpp [nama item]\n"
        "• /cekstok [keyword] [cabang]\n"
        "• /orderkeyword [keyword] [cabang]\n"
        "• Balas hasil order pakai tanda ! untuk revisi\n"
    )
    update.message.reply_text(teks)
def order(update, context):
    try:
        args = context.args
        if len(args) < 2:
            update.message.reply_text("Format: /order [supplier] [cabang]")
            return
        cabang = args[-1].lower()
        supplier_input = " ".join(args[:-1]).lower()

        mapping = {
            'pkp': ('stok cab. pkp', 'minimal stok pkp'),
            'bjg': ('stok cab. bjg', 'minimal stok bjg'),
            'cld': ('stok cab. cld', 'minimal stok cld')
        }
        if cabang not in mapping:
            update.message.reply_text("Cabang tidak dikenal.")
            return
        kolom_stok, kolom_min = mapping[cabang]

        hasil_order, total_order = [], 0

        for _, row in df_supplier.iterrows():
            if is_discontinued(row.get('supplier', '')): continue
            if supplier_input not in str(row.get('supplier', '')).lower(): continue

            kode = row.get('kode item')
            nama = row.get('nama item')
            min_stok = row.get(kolom_min)
            if min_stok in (None, "", "-", "N/A"): continue
            min_stok = int(float(min_stok))
            qty_satuan = row.get('qty satuan order', 1) or 1

            stok_row = df_stok[df_stok['kode item'] == kode]
            if stok_row.empty: continue
            stok_aktual = int(float(stok_row.iloc[0].get(kolom_stok, 0) or 0))

            kekurangan = max(0, min_stok - stok_aktual)
            if kekurangan == 0: continue

            qty_order = int(math.ceil(kekurangan / qty_satuan) * qty_satuan)
            if qty_order == 0: continue

            harga = 0
            df_item_beli = df_beli[df_beli['kode item'] == kode].copy()
            if not df_item_beli.empty:
                df_item_beli['tanggal pembelian'] = pd.to_datetime(df_item_beli['tanggal pembelian'], errors='coerce')
                harga = df_item_beli.sort_values(by='tanggal pembelian', ascending=False).iloc[0].get('harga dasar', 0)

            prioritas = kekurangan / (stok_aktual + 1)
            if prioritas < BATAS_PRIORITAS_MINIMAL: continue

            total_order += qty_order * harga
            hasil_order.append(f"• {nama} // {qty_order}pc #{stok_aktual}")

        if not hasil_order:
            update.message.reply_text("Tidak ada item yang layak diorder.")
            return

        user_order_cache[update.message.from_user.id] = hasil_order

        hasil_text = f"📦 Order List – Supplier: {supplier_input.title()} – Cabang: {cabang.upper()}\n\n"
        hasil_text += "\n".join(hasil_order)
        hasil_text += f"\n\n💰 Total Order: Rp{int(total_order):,}".replace(",", ".")
        update.message.reply_text(hasil_text, parse_mode='HTML')
    except Exception as e:
        update.message.reply_text(f"Terjadi kesalahan: {e}")


def main():
    updater = Updater(TELEGRAM_TOKEN, use_context=True)
    dp = updater.dispatcher
    dp.add_handler(CommandHandler("order", order))
    dp.add_handler(CommandHandler("cekhpp", cekhpp))
    dp.add_handler(CommandHandler("cekstok", cekstok))
    dp.add_handler(CommandHandler("orderkeyword", orderkeyword))
    dp.add_handler(CommandHandler("help", help))
    dp.add_handler(MessageHandler(Filters.text & Filters.regex(r"^revisi:"), handler_revisi_manual))
    dp.add_handler(MessageHandler(Filters.text & ~Filters.command, handler_pilihan_angka))
    dp.add_handler(MessageHandler(Filters.text & ~Filters.command, handler_revisi_manual))
    updater.start_polling()
    updater.idle()

if __name__ == "__main__":
    main()
