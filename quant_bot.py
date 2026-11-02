import yfinance as yf
import pandas as pd
import numpy as np
import warnings
import json
from datetime import datetime, timedelta

warnings.filterwarnings('ignore')

PORTFOY_BASLANGIC_TARIHI = "2026-10-21"
BASLANGIC_SERMAYE = 100000.0
PPF_GUNLUK_GETIRI = 0.0011
KOMISYON = 0.002

# Gram Altın + BIST100 Hisseleri
bist100 = [
    "GRAM_ALTIN",
    "AEFES.IS", "AGHOL.IS", "AGROT.IS", "AHGAZ.IS", "AKBNK.IS", "AKCNS.IS", "AKFGY.IS", "AKFYE.IS", "AKSA.IS", "AKSEN.IS",
    "ALARK.IS", "ALBRK.IS", "ALFAS.IS", "ALTNY.IS", "ANHYT.IS", "ANSGR.IS", "ARCLK.IS", "ARDYZ.IS", "ASELS.IS", "ASTOR.IS",
    "BERA.IS", "BFREN.IS", "BIENY.IS", "BIMAS.IS", "BIOEN.IS", "BOBET.IS", "BRSAN.IS", "BRYAT.IS", "BTCIM.IS", "CANTE.IS",
    "CCOLA.IS", "CIMSA.IS", "CLEBI.IS", "CWENE.IS", "DOAS.IS", "DOHOL.IS", "ECILC.IS", "ECZYT.IS", "EGEEN.IS", "EKGYO.IS",
    "ENERY.IS", "ENJSA.IS", "ENKAI.IS", "EREGL.IS", "EUPWR.IS", "EUREN.IS", "FROTO.IS", "GARAN.IS", "GENIL.IS", "GESAN.IS",
    "GOLTS.IS", "GUBRF.IS", "GWIND.IS", "HALKB.IS", "HEKTS.IS", "IMASM.IS", "IPEKE.IS", "ISCTR.IS", "ISDMR.IS", "ISGYO.IS",
    "ISMEN.IS", "IZENR.IS", "KAYSE.IS", "KCAER.IS", "KCHOL.IS", "KLSER.IS", "KONTR.IS", "KONYA.IS", "KOZAA.IS", "KOZAL.IS",
    "KRDMD.IS", "KTLEV.IS", "LMKDC.IS", "MAVI.IS", "MGROS.IS", "MIATK.IS", "ODAS.IS", "OTKAR.IS", "OYAKC.IS", "PAPIL.IS",
    "PEKGY.IS", "PETKM.IS", "PGSUS.IS", "QUAGR.IS", "REEDR.IS", "SAHOL.IS", "SASA.IS", "SDTTR.IS", "SISE.IS", "SKBNK.IS",
    "SMRTG.IS", "SOKM.IS", "TABGD.IS", "TAVHL.IS", "TCELL.IS", "THYAO.IS", "TKFEN.IS", "TOASO.IS", "TSKB.IS", "TTKOM.IS",
    "TTRAK.IS", "TUKAS.IS", "TUPRS.IS", "TURSG.IS", "ULKER.IS", "VAKBN.IS", "VESBE.IS", "VESTL.IS", "YEOTK.IS", "YKBNK.IS",
    "YYLGD.IS", "ZOREN.IS"
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

    fiyatlar = df['Close'].values
    durumlar = df['Durum'].values
    ema200ler = df['EMA200'].values
    n = len(df)
    bakiye_serisi = np.full(n, baslangic, dtype=float)

    for i in range(n):
        fiyat = fiyatlar[i]
        durum = durumlar[i]
        ema200 = ema200ler[i]

        if np.isnan(durum) or np.isnan(ema200):
            if i > 0:
                bakiye_serisi[i] = bakiye_serisi[i - 1]
            continue

        if nakit > 0:
            nakit *= (1.0 + PPF_GUNLUK_GETIRI)

        # Pozisyona giriş
        if durum == 1 and nakit > 0 and fiyat > ema200:
            hisse_adedi = (nakit * (1.0 - KOMISYON)) / fiyat
            nakit = 0.0

        # Pozisyondan çıkış
        elif durum == -1 and hisse_adedi > 0:
            satis_tutari = hisse_adedi * fiyat
            nakit = satis_tutari * (1.0 - KOMISYON)
            hisse_adedi = 0.0

        # O günkü toplam portföy ederi
        bakiye_serisi[i] = nakit if nakit > 0 else (hisse_adedi * fiyat)

    son_deger = nakit if nakit > 0 else (hisse_adedi * fiyatlar[-1] * (1.0 - KOMISYON))
    skor = ((son_deger - baslangic) / baslangic) * 100.0
    return skor, pd.Series(bakiye_serisi, index=df.index)

macd_ayarlari = [(8, 21), (12, 26), (24, 52)]
st_ayarlari = [(10, 3.0), (14, 2.0), (20, 2.0)]
ema_ayarlari = [(9, 21), (13, 34), (21, 50)]

print("⏳ BIST100 ve Gram Altın Verileri Paralel İndiriliyor...")

normal_hisseler = [h for h in bist100 if h != "GRAM_ALTIN"]
toplu_veri = yf.download(normal_hisseler + ["GC=F", "TRY=X"], period="3y", interval="1d", group_by='ticker', progress=False, threads=True)

site_verileri = []
portfoy_egrileri = []

for hisse in bist100:
    try:
        if hisse == "GRAM_ALTIN":
            ons_df = toplu_veri["GC=F"].copy()
            usd_df = toplu_veri["TRY=X"].copy()

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
            if hisse not in toplu_veri.columns.levels[0]:
                continue
            df = toplu_veri[hisse].copy()
            df['Close'] = pd.to_numeric(df['Close'].squeeze())
            df['High'] = pd.to_numeric(df['High'].squeeze())
            df['Low'] = pd.to_numeric(df['Low'].squeeze())
            df.dropna(subset=['Close', 'High', 'Low'], inplace=True)

        if len(df) < 250:
            continue

        df['EMA200'] = df['Close'].ewm(span=200, adjust=False).mean()
        test_verisi = df.tail(500).copy()

        en_iyi_skor = -999.0
        en_iyi_isim = ""
        en_iyi_param = ""
        en_iyi_df = None
        en_iyi_egri = None

        for h, y in macd_ayarlari:
            t_df = hesapla_macd(test_verisi, h, y)
            skor, egri = backtest_saf_trend(t_df)
            if skor > en_iyi_skor:
                en_iyi_skor = skor
                en_iyi_isim = "MACD"
                en_iyi_param = f"H:{h}/Y:{y}"
                en_iyi_df = t_df
                en_iyi_egri = egri

        for p, c in st_ayarlari:
            t_df = hesapla_supertrend(test_verisi, p, c)
            skor, egri = backtest_saf_trend(t_df)
            if skor > en_iyi_skor:
                en_iyi_skor = skor
                en_iyi_isim = "SuperTrend"
                en_iyi_param = f"P:{p}/Ç:{c}"
                en_iyi_df = t_df
                en_iyi_egri = egri

        for kisa, uzun in ema_ayarlari:
            t_df = hesapla_ema_cross(test_verisi, kisa, uzun)
            skor, egri = backtest_saf_trend(t_df)
            if skor > en_iyi_skor:
                en_iyi_skor = skor
                en_iyi_isim = "EMA Kesişim"
                en_iyi_param = f"{kisa}/{uzun}"
                en_iyi_df = t_df
                en_iyi_egri = egri

        if en_iyi_df is not None:
            son_satir = en_iyi_df.iloc[-1]
            onceki_satir = en_iyi_df.iloc[-2]

            sinyal_kodu = son_satir['Sinyal']
            durum_kodu = son_satir['Durum']
            fiyat = float(son_satir['Close'])
            ema200 = float(son_satir['EMA200'])
            stop_fiyat = float(son_satir['Stop_Seviyesi'])

            yeni_ema_kirilimi = (durum_kodu == 1 and fiyat > ema200 and onceki_satir['Close'] <= onceki_satir['EMA200'])
            if (sinyal_kodu == 1 and fiyat > ema200) or yeni_ema_kirilimi:
                sinyal_yazi = "AL"
            elif sinyal_kodu == -1:
                sinyal_yazi = "SAT"
            elif durum_kodu == 1 and fiyat > ema200:
                sinyal_yazi = "TUT"
            else:
                sinyal_yazi = "İZLE"

            # X-Ray Grafiği için son 30 işlem gününün gerçek kapanışları ve tarihleri
            son_30_df = en_iyi_df.tail(30)
            gecmis_fiyatlar = [round(float(x), 2) for x in son_30_df['Close'].values]
            gecmis_tarihler = [d.strftime("%d.%m") for d in son_30_df.index]

            site_verileri.append({
                "hisse": hisse.replace(".IS", ""),
                "sinyal": sinyal_yazi,
                "fiyat": round(fiyat, 2),
                "ema200": round(ema200, 2),
                "strateji": f"{en_iyi_isim} ({en_iyi_param})",
                "stop": f"{round(stop_fiyat, 2)} TL" if stop_fiyat > 0 else "Trend Çıkışı",
                "getiri": round(en_iyi_skor, 1),
                "gecmis": gecmis_fiyatlar,
                "tarihler": gecmis_tarihler
            })

            if en_iyi_egri is not None:
                portfoy_egrileri.append(en_iyi_egri)

    except Exception as e:
        print(f"⚠️ {hisse} hesaplanırken hata: {e}")

# GERÇEK 100.000 TL FON HESABI (21 Ekim 2026'dan Bugüne)
guncel_bakiye = BASLANGIC_SERMAYE
net_kar_yuzde = 0.0
net_kar_tl = 0.0

if portfoy_egrileri:
    birlesik_egri_df = pd.concat(portfoy_egrileri, axis=1).ffill().bfill()
    canli_donem_df = birlesik_egri_df[birlesik_egri_df.index >= PORTFOY_BASLANGIC_TARIHI]

    if len(canli_donem_df) >= 1:
        # Başlangıç gününü 1.0 kabul edip tüm varlıkların eşit ağırlıklı gerçek büyümesini al
        normalize_df = canli_donem_df.div(canli_donem_df.iloc[0], axis=1)
        portfoy_serisi = normalize_df.mean(axis=1) * BASLANGIC_SERMAYE
        guncel_bakiye = float(portfoy_serisi.iloc[-1])
        net_kar_tl = guncel_bakiye - BASLANGIC_SERMAYE
        net_kar_yuzde = ((guncel_bakiye - BASLANGIC_SERMAYE) / BASLANGIC_SERMAYE) * 100.0

aktif_pozisyon_sayisi = sum(1 for x in site_verileri if x['sinyal'] in ['AL', 'TUT'])
toplam_varlik_sayisi = len(site_verileri)
nakit_orani = round(((toplam_varlik_sayisi - aktif_pozisyon_sayisi) / max(1, toplam_varlik_sayisi)) * 100, 1)

veri_paketi = {
    "guncellenme_tarihi": (datetime.utcnow() + timedelta(hours=3)).strftime("%d.%m.%Y %H:%M"),
    "portfoy": {
        "baslangic_tarihi": "21 Ekim 2026",
        "baslangic_sermaye": round(BASLANGIC_SERMAYE, 2),
        "guncel_bakiye": round(guncel_bakiye, 2),
        "net_kar_tl": round(net_kar_tl, 2),
        "net_kar_yuzde": round(net_kar_yuzde, 2),
        "aktif_pozisyon": aktif_pozisyon_sayisi,
        "toplam_varlik": toplam_varlik_sayisi,
        "ppf_nakit_orani": nakit_orani
    },
    "sinyaller": site_verileri
}

with open("signals.json", "w", encoding="utf-8") as f:
    json.dump(veri_paketi, f, ensure_ascii=False, indent=4)

print(f"✅ BIST100 Algoritması {toplam_varlik_sayisi} varlık ve gerçek portföy verisiyle signals.json dosyasını güncelledi!")
