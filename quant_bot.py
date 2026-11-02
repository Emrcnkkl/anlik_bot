import yfinance as yf
import pandas as pd
import numpy as np
import warnings
import json
from datetime import datetime, timedelta

warnings.filterwarnings('ignore')

bist30 = [
    "GRAM_ALTIN",
    "AKBNK.IS", "ALARK.IS", "ASELS.IS", "ASTOR.IS", "BIMAS.IS",
    "BRSAN.IS", "CIMSA.IS", "CWENE.IS", "DOAS.IS", "EKGYO.IS",
    "ENKAI.IS", "EREGL.IS", "EUPWR.IS", "FROTO.IS", "GARAN.IS",
    "GUBRF.IS", "HEKTS.IS", "ISCTR.IS", "KCHOL.IS", "KONTR.IS",
    "KOZAL.IS", "KRDMD.IS", "ODAS.IS", "PGSUS.IS", "SAHOL.IS",
    "SASA.IS", "SISE.IS", "TCELL.IS", "THYAO.IS", "TUPRS.IS", "YKBNK.IS"
]

def hesapla_macd(df, hizli, yavas, sinyal_periyot=9):
    temp_df = df.copy()
    macd_line = temp_df['Close'].ewm(span=hizli, adjust=False).mean() - temp_df['Close'].ewm(span=yavas, adjust=False).mean()
    signal_line = macd_line.ewm(span=sinyal_periyot, adjust=False).mean()
    temp_df['Durum'] = np.where(macd_line > signal_line, 1, -1)
    temp_df['Sinyal'] = temp_df['Durum'].diff() / 2
    temp_df['Stop_Seviyesi'] = temp_df['EMA200']
    return temp_df

def hesapla_supertrend(df, period, multiplier):
    temp_df = df.copy()
    high = temp_df['High'].values
    low = temp_df['Low'].values
    close = temp_df['Close'].values

    tr1 = high - low
    tr2 = np.abs(high - np.roll(close, 1))
    tr3 = np.abs(low - np.roll(close, 1))
    tr = np.maximum(tr1, np.maximum(tr2, tr3))
    tr[0] = tr1[0]

    atr = pd.Series(tr, index=temp_df.index).rolling(period).mean().values
    hl2 = (high + low) / 2.0
    basic_ub = hl2 + (multiplier * atr)
    basic_lb = hl2 - (multiplier * atr)

    n = len(temp_df)
    final_ub = np.zeros(n)
    final_lb = np.zeros(n)
    supertrend = np.zeros(n)
    trend = np.ones(n, dtype=int)

    for i in range(1, n):
        if np.isnan(basic_ub[i]):
            continue

        if np.isnan(basic_ub[i - 1]):
            final_ub[i] = basic_ub[i]
            final_lb[i] = basic_lb[i]
            supertrend[i] = final_lb[i]
            trend[i] = 1
            continue

        if basic_ub[i] < final_ub[i - 1] or close[i - 1] > final_ub[i - 1]:
            final_ub[i] = basic_ub[i]
        else:
            final_ub[i] = final_ub[i - 1]

        if basic_lb[i] > final_lb[i - 1] or close[i - 1] < final_lb[i - 1]:
            final_lb[i] = basic_lb[i]
        else:
            final_lb[i] = final_lb[i - 1]

        if supertrend[i - 1] == final_ub[i - 1]:
            if close[i] <= final_ub[i]:
                trend[i] = -1
                supertrend[i] = final_ub[i]
            else:
                trend[i] = 1
                supertrend[i] = final_lb[i]
        else:
            if close[i] >= final_lb[i]:
                trend[i] = 1
                supertrend[i] = final_lb[i]
            else:
                trend[i] = -1
                supertrend[i] = final_ub[i]

    temp_df['Durum'] = trend
    temp_df['Sinyal'] = temp_df['Durum'].diff() / 2
    temp_df['Stop_Seviyesi'] = supertrend
    return temp_df

def hesapla_ema_cross(df, kisa, uzun):
    temp_df = df.copy()
    ema_kisa = temp_df['Close'].ewm(span=kisa, adjust=False).mean()
    ema_uzun = temp_df['Close'].ewm(span=uzun, adjust=False).mean()
    temp_df['Durum'] = np.where(ema_kisa > ema_uzun, 1, -1)
    temp_df['Sinyal'] = temp_df['Durum'].diff() / 2
    temp_df['Stop_Seviyesi'] = ema_uzun
    return temp_df

def backtest_saf_trend(df):
    baslangic = 100.0
    nakit = baslangic
    hisse_adedi = 0.0
    komisyon = 0.002
    PPF_GUNLUK_GETIRI = 0.0011

    fiyatlar = df['Close'].values
    durumlar = df['Durum'].values
    ema200ler = df['EMA200'].values

    for i in range(len(df)):
        fiyat = fiyatlar[i]
        durum = durumlar[i]
        ema200 = ema200ler[i]

        if np.isnan(durum) or np.isnan(ema200):
            continue

        if nakit > 0:
            nakit *= (1.0 + PPF_GUNLUK_GETIRI)

        # İndikatör pozitif trenddeyse ve fiyat EMA200 üzerindeyse alım yap
        if durum == 1 and nakit > 0 and fiyat > ema200:
            hisse_adedi = (nakit * (1.0 - komisyon)) / fiyat
            nakit = 0.0

        # İndikatör negatif trende dönerse sat ve nakite (PPF) geç
        elif durum == -1 and hisse_adedi > 0:
            satis_tutari = hisse_adedi * fiyat
            nakit = satis_tutari * (1.0 - komisyon)
            hisse_adedi = 0.0

    if hisse_adedi > 0:
        son_fiyat = fiyatlar[-1]
        nakit = (hisse_adedi * son_fiyat) * (1.0 - komisyon)

    return ((nakit - baslangic) / baslangic) * 100.0

site_verileri = []
macd_ayarlari = [(8, 21), (12, 26), (24, 52)]
st_ayarlari = [(10, 3.0), (14, 2.0), (20, 2.0)]
ema_ayarlari = [(9, 21), (13, 34), (21, 50)]

print("⏳ Web Sitesi İçin Güncel Sinyaller Hesaplanıyor...")

for hisse in bist30:
    try:
        if hisse == "GRAM_ALTIN":
            ons_df = yf.download("GC=F", period="3y", interval="1d", progress=False)
            usd_df = yf.download("TRY=X", period="3y", interval="1d", progress=False)

            if isinstance(ons_df.columns, pd.MultiIndex):
                ons_df.columns = ons_df.columns.get_level_values(0)
            if isinstance(usd_df.columns, pd.MultiIndex):
                usd_df.columns = usd_df.columns.get_level_values(0)

            ortak = pd.concat([
                pd.to_numeric(ons_df['Close'].squeeze()),
                pd.to_numeric(ons_df['High'].squeeze()),
                pd.to_numeric(ons_df['Low'].squeeze()),
                pd.to_numeric(usd_df['Close'].squeeze())
            ], axis=1, join='inner').dropna()
            ortak.columns = ['Ons_Close', 'Ons_High', 'Ons_Low', 'UsdTry']

            df = pd.DataFrame(index=ortak.index)
            df['Close'] = (ortak['Ons_Close'] * ortak['UsdTry']) / 31.1034768
            df['High'] = (ortak['Ons_High'] * ortak['UsdTry']) / 31.1034768
            df['Low'] = (ortak['Ons_Low'] * ortak['UsdTry']) / 31.1034768

        else:
            df = yf.download(hisse, period="3y", interval="1d", progress=False)
            if len(df) < 250:
                continue

            if isinstance(df.columns, pd.MultiIndex):
                df.columns = df.columns.get_level_values(0)

            df['Close'] = pd.to_numeric(df['Close'].squeeze())
            df['High'] = pd.to_numeric(df.get('High', df['Close']).squeeze())
            df['Low'] = pd.to_numeric(df.get('Low', df['Close']).squeeze())
            df.dropna(subset=['Close'], inplace=True)

        # Her iki blok (GRAM_ALTIN ve BIST30) için ortak hesaplama
        df['EMA200'] = df['Close'].ewm(span=200, adjust=False).mean()
        test_verisi = df.tail(500).copy()

        en_iyi_skor = -999.0
        en_iyi_isim = ""
        en_iyi_param = ""
        en_iyi_df = None

        for h, y in macd_ayarlari:
            t_df = hesapla_macd(test_verisi, h, y)
            skor = backtest_saf_trend(t_df)
            if skor > en_iyi_skor:
                en_iyi_skor = skor
                en_iyi_isim = "MACD"
                en_iyi_param = f"H:{h}/Y:{y}"
                en_iyi_df = t_df.copy()

        for p, c in st_ayarlari:
            t_df = hesapla_supertrend(test_verisi, p, c)
            skor = backtest_saf_trend(t_df)
            if skor > en_iyi_skor:
                en_iyi_skor = skor
                en_iyi_isim = "SuperTrend"
                en_iyi_param = f"P:{p}/Ç:{c}"
                en_iyi_df = t_df.copy()

        for kisa, uzun in ema_ayarlari:
            t_df = hesapla_ema_cross(test_verisi, kisa, uzun)
            skor = backtest_saf_trend(t_df)
            if skor > en_iyi_skor:
                en_iyi_skor = skor
                en_iyi_isim = "EMA Kesişim"
                en_iyi_param = f"{kisa}/{uzun}"
                en_iyi_df = t_df.copy()

        if en_iyi_df is not None:
            son_satir = en_iyi_df.iloc[-1]
            onceki_satir = en_iyi_df.iloc[-2]
            
            sinyal_kodu = son_satir['Sinyal']
            durum_kodu = son_satir['Durum']
            fiyat = float(son_satir['Close'])
            ema200 = float(son_satir['EMA200'])
            stop_fiyat = float(son_satir['Stop_Seviyesi'])

            # Sinyal ve Pozisyon Durumu Mantığı
            yeni_ema_kirilimi = (durum_kodu == 1 and fiyat > ema200 and onceki_satir['Close'] <= onceki_satir['EMA200'])
            if (sinyal_kodu == 1 and fiyat > ema200) or yeni_ema_kirilimi:
                sinyal_yazi = "AL"
            elif sinyal_kodu == -1:
                sinyal_yazi = "SAT"
            elif durum_kodu == 1 and fiyat > ema200:
                sinyal_yazi = "TUT"
            else:
                sinyal_yazi = "İZLE"

            site_verileri.append({
                "hisse": hisse.replace(".IS", ""),
                "sinyal": sinyal_yazi,
                "fiyat": round(fiyat, 2),
                "ema200": round(ema200, 2),
                "strateji": f"{en_iyi_isim} ({en_iyi_param})",
                "stop": f"{round(stop_fiyat, 2)} TL" if stop_fiyat > 0 else "Trend Çıkışı",
                "getiri": round(en_iyi_skor, 1)
            })

    except Exception as e:
        print(f"⚠️ {hisse} hesaplanırken hata oluştu: {e}")

veri_paketi = {
    "guncellenme_tarihi": (datetime.utcnow() + timedelta(hours=3)).strftime("%d.%m.%Y %H:%M"),
    "sinyaller": site_verileri
}

with open("signals.json", "w", encoding="utf-8") as f:
    json.dump(veri_paketi, f, ensure_ascii=False, indent=4)

print(f"✅ Kurumsal Fon Algoritması {len(site_verileri)} varlık için signals.json dosyasını güncelledi!")
