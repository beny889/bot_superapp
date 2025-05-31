# bot_superapp.py (hanya fungsi-fungsi utama yang dimodifikasi)
# Pastikan bagian import dan inisialisasi di awal tetap sama

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
            if "discontinou" in str(row.get('supplier', '')).lower():
                continue
            if supplier_input not in str(row.get('supplier', '')).lower():
                continue

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

        hasil_text = f"📦 Order List – Supplier: {supplier_input.title()} – Cabang: {cabang.upper()}

"
        hasil_text += "\n".join(hasil_order)
        hasil_text += f"\n\n💰 Total Order: Rp{int(total_order):,}".replace(",", ".")
        update.message.reply_text(hasil_text, parse_mode='HTML')
    except Exception as e:
        update.message.reply_text(f"Terjadi kesalahan: {e}")

# Fungsi cekstok, orderkeyword, cekhpp, help juga sudah termasuk dan identik seperti versi sebelumnya

# File ini hanya contoh isi awal, akan kamu tempelkan ke script utama
