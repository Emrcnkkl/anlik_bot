import yfinance as yf
import pandas as pd
import json
from datetime import datetime
import pytz

BIST30 = [
    "AKBNK.IS", "ALARK.IS", "ASELS.IS", "ASTOR.IS", "BIMAS.IS",
    "BRSAN.IS", "CIMSA.IS", "CWENE.IS", "DOAS.IS", "EKGYO.IS",
    "ENKAI.IS", "EREGL.IS", "EUPWR.IS", "FROTO.IS", "GARAN.IS",
    "GUBRF.IS", "HEKTS.IS", "ISCTR.IS", "KCHOL.IS", "KONTR.IS",
    "KRDMD.IS", "PGSUS.IS", "SAHOL.IS", "SASA.IS", "SISE.IS",
    "TCELL.IS", "THYAO.IS", "TUPRS.IS", "YKBNK.IS"
]

def hesapla_rsi(data, periyot=14):
    delta = data.diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=periyot).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=periyot).mean()
    rs = gain / loss
    return 100 - (100 / (1 + rs))

def hesapla_macd(data, hizli=12, yavas=26, sinyal_periyodu=9):
    exp1 = data.ewm(span=hizli, adjust=False).mean()
    exp2 = data.ewm(span=yavas, adjust=False).mean()
    macd = exp1 - exp2
    sinyal_cizgisi = macd.ewm(span=sinyal_periyodu, adjust=False).mean()
    return macd, sinyal_cizgisi

print("⚡ Kısa Vadeli Taraması Başlıyor...")

signals_data = []
tz = pytz.timezone('Europe/Istanbul')
simdi = datetime.now(tz).strftime("%d.%m.%Y %H:%M")

for hisse in BIST30:
    try:
        # Son 60 günün "Saatlik" verisi
        df = yf.download(hisse, period="60d", interval="1h", progress=False)
        if df.empty or len(df) < 30:
            continue

        kapanis = df['Close'].squeeze()
        df['RSI'] = hesapla_rsi(kapanis)
        df['MACD'], df['MACD_Signal'] = hesapla_macd(kapanis)
        df['EMA9'] = kapanis.ewm(span=9, adjust=False).mean()
        df['EMA21'] = kapanis.ewm(span=21, adjust=False).mean()

        son_fiyat = float(kapanis.iloc[-1])
        son_rsi = float(df['RSI'].iloc[-1])
        
        onceki_macd = df['MACD'].iloc[-2]
        son_macd = df['MACD'].iloc[-1]
        onceki_macd_sig = df['MACD_Signal'].iloc[-2]
        son_macd_sig = df['MACD_Signal'].iloc[-1]
        
        onceki_ema9 = df['EMA9'].iloc[-2]
        son_ema9 = df['EMA9'].iloc[-1]
        onceki_ema21 = df['EMA21'].iloc[-2]
        son_ema21 = df['EMA21'].iloc[-1]

        # Strateji
        ema_yukari = (onceki_ema9 <= onceki_ema21) and (son_ema9 > son_ema21)
        macd_yukari = (onceki_macd <= onceki_macd_sig) and (son_macd > son_macd_sig)
        
        ema_asagi = (onceki_ema9 >= onceki_ema21) and (son_ema9 < son_ema21)
        macd_asagi = (onceki_macd >= onceki_macd_sig) and (son_macd < son_macd_sig)

        sinyal = "TUT"
        sebep = "Beklemede"

        if (ema_yukari or macd_yukari) and son_rsi < 70:
            sinyal = "AL"
            sebep = "Hızlı EMA Kesimi" if ema_yukari else "MACD Kesimi"
        elif ema_asagi or macd_asagi or son_rsi > 80:
            sinyal = "SAT"
            sebep = "Aşırı Alım (RSI>80)" if son_rsi > 80 else ("EMA Kesimi" if ema_asagi else "MACD Kesimi")

        # Veriyi site için listeye ekle
        signals_data.append({
            "hisse": hisse.replace('.IS', ''),
            "fiyat": round(son_fiyat, 2),
            "sinyal": sinyal,
            "sebep": sebep,
            "rsi": round(son_rsi, 1),
            "zaman": simdi
        })

    except Exception as e:
        print(f"Hata ({hisse}): {e}")

# Web sitesinin okuyacağı JSON dosyasını oluştur
with open("signals.json", "w", encoding="utf-8") as f:
    json.dump(signals_data, f, ensure_ascii=False, indent=2)

print("✅ signals.json dosyası site için başarıyla oluşturuldu!")
