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

def hesapla_temel_metrikler(df, adx_periyot=14):
    """EMA200, EMA100, ATR14 ve ADX14 değerlerini her varlık için tek seferde vektörel hesaplar."""
    temp_df = df.copy()
    close = temp_df['Close']
    high = temp_df['High']
    low = temp_df['Low']

    temp_df['EMA200'] = close.ewm(span=200, adjust=False).mean()
    temp_df['EMA100'] = close.ewm(span=100, adjust=False).mean()

    prev_close = close.shift(1)
    tr1 = high - low
    tr2 = (high - prev_close).abs()
    tr3 = (low - prev_close).abs()
    tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
    atr = tr.ewm(alpha=1.0 / adx_periyot, adjust=False).mean()
    temp_df['ATR'] = atr

    up_move = high.diff()
    down_move = -low.diff()

    plus_dm = np.where((up_move > down_move) & (up_move > 0), up_move, 0.0)
    minus_dm = np.where((down_move > up_move) & (down_move > 0), down_move, 0.0)

    plus_di = 100.0 * (pd.Series(plus_dm, index=temp_df.index).ewm(alpha=1.0 / adx_periyot, adjust=False).mean() / atr.replace(0, np.nan))
    minus_di = 100.0 * (pd.Series(minus_dm, index=temp_df.index).ewm(alpha=1.0 / adx_periyot, adjust=False).mean() / atr.replace(0, np.nan))

    dx = 100.0 * ((plus_di - minus_di).abs() / (plus_di + minus_di).replace(0, np.nan))
    temp_df['ADX'] = dx.ewm(alpha=1.0 / adx_periyot, adjust=False).mean().fillna(20.0)
    return temp_df

def ind_macd(close_series, hizli, yavas, sinyal_periyot=9):
    macd_line = close_series.ewm(span=hizli, adjust=False).mean() - close_series.ewm(span=yavas, adjust=False).mean()
    signal_line = macd_line.ewm(span=sinyal_periyot, adjust=False).mean()
    durum = np.where(macd_line > signal_line, 1, -1)
    return durum, close_series.ewm(span=yavas, adjust=False).mean().values

def ind_ema_cross(close_series, kisa, uzun):
    ema_kisa = close_series.ewm(span=kisa, adjust=False).mean()
    ema_uzun = close_series.ewm(span=uzun, adjust=False).mean()
    durum = np.where(ema_kisa > ema_uzun, 1, -1)
    return durum, ema_uzun.values

def ind_donchian(high_series, low_series, close_series, periyot):
    ust_kanal = high_series.rolling(periyot).max().shift(1)
    alt_kanal = low_series.rolling(periyot // 2).min().shift(1)
    orta_bant = ((ust_kanal + alt_kanal) / 2.0).bfill().values

    close_v = close_series.values
    ust_v = ust_kanal.values
    alt_v = alt_kanal.values
    n = len(close_v)
    durum = np.full(n, -1, dtype=int)

    for i in range(1, n):
        if np.isnan(ust_v[i]) or np.isnan(alt_v[i]):
            durum[i] = durum[i - 1]
        elif close_v[i] > ust_v[i]:
            durum[i] = 1
        elif close_v[i] < alt_v[i]:
            durum[i] = -1
        else:
            durum[i] = durum[i - 1]

    return durum, orta_bant

def ind_supertrend(df, period, multiplier):
    high = df['High'].values
    low = df['Low'].values
    close = df['Close'].values

    tr1 = high - low
    tr2 = np.abs(high - np.roll(close, 1))
    tr3 = np.abs(low - np.roll(close, 1))
    tr = np.maximum(tr1, np.maximum(tr2, tr3))
    tr[0] = tr1[0]

    atr = pd.Series(tr, index=df.index).rolling(period).mean().values
    hl2 = (high + low) / 2.0
    basic_ub = hl2 + (multiplier * atr)
    basic_lb = hl2 - (multiplier * atr)

    n = len(df)
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

        final_ub[i] = basic_ub[i] if (basic_ub[i] < final_ub[i - 1] or close[i - 1] > final_ub[i - 1]) else final_ub[i - 1]
        final_lb[i] = basic_lb[i] if (basic_lb[i] > final_lb[i - 1] or close[i - 1] < final_lb[i - 1]) else final_lb[i - 1]

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

    return trend, supertrend

def backtest_gelismis_motor(fiyatlar, durumlar, kalkanlar, atrler, adxler, baz_stoplar, adx_esik, atr_carpan, cikis_modu):
    """
    cikis_modu 0 (Hassas): İndikatör SAT verdiğinde veya ATR İz Süren Stop kırıldığında çıkar.
    cikis_modu 1 (Trend Sürücü): Rallide ufak kesişimleri yok sayar, sadece ATR İz Süren Stop veya Kalkan kırıldığında çıkar.
    """
    baslangic = 100.0
    nakit = baslangic
    hisse_adedi = 0.0
    n = len(fiyatlar)

    bakiye_serisi = np.full(n, baslangic, dtype=float)
    pozisyon_serisi = np.zeros(n, dtype=int)
    dinamik_stop_serisi = np.zeros(n, dtype=float)

    zirve_fiyat = 0.0
    giris_bakiye = 0.0
    kazanan_islem = 0
    toplam_islem = 0

    for i in range(n):
        fiyat = fiyatlar[i]
        durum = durumlar[i]
        kalkan = kalkanlar[i]
        atr = atrler[i]
        adx = adxler[i]

        if np.isnan(durum) or np.isnan(kalkan) or np.isnan(atr):
            if i > 0:
                bakiye_serisi[i] = bakiye_serisi[i - 1]
            continue

        # Nakitteyken günlük PPF getirisi işler
        if nakit > 0:
            nakit *= (1.0 + PPF_GUNLUK_GETIRI)

        # POZİSYONA GİRİŞ (Trend Onayı + Kalkan + ADX Filtresi)
        if hisse_adedi == 0.0:
            if durum == 1 and fiyat > kalkan and adx >= adx_esik:
                giris_bakiye = nakit
                hisse_adedi = (nakit * (1.0 - KOMISYON)) / fiyat
                nakit = 0.0
                zirve_fiyat = fiyat
                pozisyon_serisi[i] = 1
                dinamik_stop_serisi[i] = max(kalkan, zirve_fiyat - (atr_carpan * atr))
            else:
                pozisyon_serisi[i] = 0
                dinamik_stop_serisi[i] = kalkan

        # POZİSYONDAYKEN İZ SÜREN STOP VE ÇIKIŞ KONTROLÜ
        else:
            if fiyat > zirve_fiyat:
                zirve_fiyat = fiyat

            atr_stop = zirve_fiyat - (atr_carpan * atr)
            aktif_stop = max(kalkan * 0.98, atr_stop, baz_stoplar[i] if baz_stoplar[i] < fiyat else atr_stop)
            dinamik_stop_serisi[i] = aktif_stop

            cikis_sarti = False
            if cikis_modu == 0:
                # Hassas mod: İndikatör negatif kesişirse veya ATR iz süren stop kırılırsa çık
                if durum == -1 or fiyat < atr_stop:
                    cikis_sarti = True
            else:
                # Trend Sürücü mod: Fiyat ATR iz süren stopun veya ana kalkanın altına inmedikçe rallide kal
                if fiyat < atr_stop or fiyat < kalkan:
                    cikis_sarti = True

            if cikis_sarti:
                satis_tutari = hisse_adedi * fiyat
                nakit = satis_tutari * (1.0 - KOMISYON)
                hisse_adedi = 0.0
                toplam_islem += 1
                if nakit > giris_bakiye:
                    kazanan_islem += 1
                pozisyon_serisi[i] = 0
            else:
                pozisyon_serisi[i] = 1

        bakiye_serisi[i] = nakit if nakit > 0 else (hisse_adedi * fiyat)

    son_deger = nakit if nakit > 0 else (hisse_adedi * fiyatlar[-1] * (1.0 - KOMISYON))
    if hisse_adedi > 0:
        toplam_islem += 1
        if son_deger > giris_bakiye:
            kazanan_islem += 1

    net_getiri = ((son_deger - baslangic) / baslangic) * 100.0

    # Max Drawdown Hesabı
    zirveler = np.maximum.accumulate(bakiye_serisi)
    dd_serisi = ((zirveler - bakiye_serisi) / np.maximum(zirveler, 1e-8)) * 100.0
    max_dd = float(np.max(dd_serisi))
    win_rate = (kazanan_islem / toplam_islem * 100.0) if toplam_islem > 0 else 100.0

    return {
        "net_getiri": net_getiri,
        "max_dd": max_dd,
        "win_rate": win_rate,
        "bakiye_serisi": bakiye_serisi,
        "pozisyon_serisi": pozisyon_serisi,
        "stop_serisi": dinamik_stop_serisi
    }

# Genişletilmiş Strateji Havuzu
macd_ayarlari = [(8, 21), (12, 26), (5, 35), (24, 52)]
st_ayarlari = [(10, 2.0), (10, 3.0), (14, 2.5), (20, 2.0)]
ema_ayarlari = [(5, 13), (9, 21), (13, 34), (21, 50)]
donchian_ayarlari = [14, 20, 34]

# Her indikatör için test edilecek Rejim / Filtre Kombinasyonları: (Kalkan, ADX_Eşik, ATR_Stop_Çarpanı, Çıkış_Modu)
rejim_kombinasyonlari = [
    ("EMA200", 18.0, 3.0, 0),  # Klasik Kalkan + ADX Filtresi + Standart ATR Stop
    ("EMA200", 22.0, 2.5, 0),  # Sıkı Yatay Piyasa Koruması (Testere Kalkanı)
    ("EMA200", 14.0, 4.2, 1),  # Boğa Trend Sürücü (Erken Çıkışı Engeller)
    ("EMA100", 16.0, 3.5, 1),  # Hızlı Trend Yakalayıcı + Geniş İz Süren Stop
]

print("⏳ BIST100 ve Gram Altın Verileri Paralel İndiriliyor...")

normal_hisseler = [h for h in bist100 if h != "GRAM_ALTIN"]
toplu_veri = yf.download(normal_hisseler + ["GC=F", "TRY=X"], period="3y", interval="1d", group_by='ticker', progress=False, threads=True)

site_verileri = []
portfoy_egrileri = []
bist_bh_egrileri = []
performans_2yil_listesi = []
performans_6ay_listesi = []

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

        df = hesapla_temel_metrikler(df)
        test_verisi = df.tail(500).copy()

        fiyatlar = test_verisi['Close'].values
        atrler = test_verisi['ATR'].values
        adxler = test_verisi['ADX'].values

        # Al-Bekle (Buy & Hold) 2 Yıllık Getiri
        bh_2yil = ((fiyatlar[-1] - fiyatlar[0]) / max(1e-8, fiyatlar[0])) * 100.0

        # Aday İndikatör Sinyallerini Hazırla
        aday_indikatorler = []
        for h, y in macd_ayarlari:
            d_arr, s_arr = ind_macd(test_verisi['Close'], h, y)
            aday_indikatorler.append(("MACD", f"H:{h}/Y:{y}", d_arr, s_arr))

        for p, c in st_ayarlari:
            d_arr, s_arr = ind_supertrend(test_verisi, p, c)
            aday_indikatorler.append(("SuperTrend", f"P:{p}/Ç:{c}", d_arr, s_arr))

        for kisa, uzun in ema_ayarlari:
            d_arr, s_arr = ind_ema_cross(test_verisi['Close'], kisa, uzun)
            aday_indikatorler.append(("EMA Kesişim", f"{kisa}/{uzun}", d_arr, s_arr))

        for per in donchian_ayarlari:
            d_arr, s_arr = ind_donchian(test_verisi['High'], test_verisi['Low'], test_verisi['Close'], per)
            aday_indikatorler.append(("Donchian", f"K:{per}", d_arr, s_arr))

        en_iyi_optimizasyon_skoru = -999999.0
        sampiyon = None

        for ind_isim, ind_param, durum_arr, baz_stop_arr in aday_indikatorler:
            for kalkan_adi, adx_esik, atr_carp, c_modu in rejim_kombinasyonlari:
                kalkan_arr = test_verisi[kalkan_adi].values
                sonuc = backtest_gelismis_motor(
                    fiyatlar, durum_arr, kalkan_arr, atrler, adxler, baz_stop_arr,
                    adx_esik, atr_carp, c_modu
                )

                net_getiri = sonuc["net_getiri"]
                max_dd = sonuc["max_dd"]
                alfa = net_getiri - bh_2yil

                # ALFA + RİSK-AYARLI SKORLAMA:
                # Al-Bekle'yi yenen (alfa > 0) stratejilere +5000 öncelik puanı verilir
                # Kendi içlerinde ise Yüksek Getiri ve Düşük Max Drawdown (Calmar dengesi) seçilir
                alfa_bonusu = 5000.0 if alfa > 0 else 0.0
                opt_skoru = alfa_bonusu + net_getiri - (0.45 * max_dd)

                if opt_skoru > en_iyi_optimizasyon_skoru:
                    en_iyi_optimizasyon_skoru = opt_skoru
                    mod_etiket = "Trend" if c_modu == 1 else "ADX"
                    sampiyon = {
                        "isim": ind_isim,
                        "param": f"{ind_param} • {mod_etiket}",
                        "sonuc": sonuc,
                        "kalkan_adi": kalkan_adi
                    }

        if sampiyon is not None:
            sonuc = sampiyon["sonuc"]
            poz_serisi = sonuc["pozisyon_serisi"]
            stop_serisi = sonuc["stop_serisi"]
            bakiye_serisi = sonuc["bakiye_serisi"]

            fiyat = float(fiyatlar[-1])
            ema200 = float(test_verisi['EMA200'].iloc[-1])
            guncel_adx = float(adxler[-1])
            stop_fiyat = float(stop_serisi[-1])

            bugun_poz = int(poz_serisi[-1])
            dun_poz = int(poz_serisi[-2]) if len(poz_serisi) > 1 else 0

            if bugun_poz == 1 and dun_poz == 0:
                sinyal_yazi = "AL"
            elif bugun_poz == 0 and dun_poz == 1:
                sinyal_yazi = "SAT"
            elif bugun_poz == 1 and dun_poz == 1:
                sinyal_yazi = "TUT"
            else:
                sinyal_yazi = "İZLE"

            son_30_df = test_verisi.tail(30)
            gecmis_fiyatlar = [round(float(x), 2) for x in son_30_df['Close'].values]
            gecmis_tarihler = [d.strftime("%d.%m") for d in son_30_df.index]

            temiz_ad = hisse.replace(".IS", "")
            algo_2yil = round(sonuc["net_getiri"], 1)
            bh_2yil_yuvarlak = round(bh_2yil, 1)
            alfa_2yil = round(algo_2yil - bh_2yil_yuvarlak, 1)

            # 6 Aylık (Son 126 İşlem Günü) Al-Bekle vs Algoritma Karşılaştırması
            gun_6ay = min(126, len(fiyatlar) - 1)
            bh_6ay = round(((fiyatlar[-1] - fiyatlar[-gun_6ay]) / max(1e-8, fiyatlar[-gun_6ay])) * 100.0, 1)
            algo_6ay = round(((bakiye_serisi[-1] - bakiye_serisi[-gun_6ay]) / max(1e-8, bakiye_serisi[-gun_6ay])) * 100.0, 1)

            site_verileri.append({
                "hisse": temiz_ad,
                "sinyal": sinyal_yazi,
                "fiyat": round(fiyat, 2),
                "ema200": round(ema200, 2),
                "adx": round(guncel_adx, 1),
                "max_dd": round(sonuc["max_dd"], 1),
                "win_rate": round(sonuc["win_rate"], 1),
                "strateji": f"{sampiyon['isim']} ({sampiyon['param']})",
                "stop": f"{round(stop_fiyat, 2)} ₺" if stop_fiyat > 0 else "Trend Çıkışı",
                "getiri": algo_2yil,
                "bh_getiri": bh_2yil_yuvarlak,
                "alfa": alfa_2yil,
                "gecmis": gecmis_fiyatlar,
                "tarihler": gecmis_tarihler
            })

            performans_2yil_listesi.append({
                "hisse": temiz_ad,
                "bh": bh_2yil_yuvarlak,
                "algo": algo_2yil,
                "yendi": bool(algo_2yil > bh_2yil_yuvarlak)
            })

            performans_6ay_listesi.append({
                "hisse": temiz_ad,
                "bh": bh_6ay,
                "algo": algo_6ay,
                "yendi": bool(algo_6ay > bh_6ay)
            })

            portfoy_egrileri.append(pd.Series(bakiye_serisi, index=test_verisi.index))
            bh_egri = (test_verisi['Close'] / test_verisi['Close'].iloc[0]) * 100.0
            bist_bh_egrileri.append(bh_egri)

    except Exception as e:
        print(f"⚠️ {hisse} hesaplanırken hata: {e}")

# 1. GERÇEK 100.000 TL FON HESABI (21 Ekim 2026'dan Bugüne)
guncel_bakiye = BASLANGIC_SERMAYE
net_kar_yuzde = 0.0
net_kar_tl = 0.0

hedef_grafik_algo = []
hedef_grafik_bist = []
hedef_grafik_tarihler = []

if portfoy_egrileri:
    birlesik_egri_df = pd.concat(portfoy_egrileri, axis=1).ffill().bfill()
    birlesik_bh_df = pd.concat(bist_bh_egrileri, axis=1).ffill().bfill()

    # 2 Yıllık Ana Grafik Serisi (BIST100 Eşit Ağırlıklı Al-Bekle vs Algoritma)
    toplam_algo_serisi = birlesik_egri_df.mean(axis=1)
    toplam_bh_serisi = birlesik_bh_df.mean(axis=1)

    hedef_grafik_algo = [round(float(x), 2) for x in toplam_algo_serisi.values]
    hedef_grafik_bist = [round(float(x), 2) for x in toplam_bh_serisi.values]
    hedef_grafik_tarihler = [d.strftime("%d.%m.%Y") for d in toplam_algo_serisi.index]

    # Canlı Fon Başlangıç Tarihinden İtibaren Büyüme
    canli_donem_df = birlesik_egri_df[birlesik_egri_df.index >= PORTFOY_BASLANGIC_TARIHI]
    if len(canli_donem_df) >= 1:
        normalize_df = canli_donem_df.div(canli_donem_df.iloc[0], axis=1)
        portfoy_serisi = normalize_df.mean(axis=1) * BASLANGIC_SERMAYE
        guncel_bakiye = float(portfoy_serisi.iloc[-1])
        net_kar_tl = guncel_bakiye - BASLANGIC_SERMAYE
        net_kar_yuzde = ((guncel_bakiye - BASLANGIC_SERMAYE) / BASLANGIC_SERMAYE) * 100.0

aktif_pozisyon_sayisi = sum(1 for x in site_verileri if x['sinyal'] in ['AL', 'TUT'])
toplam_varlik_sayisi = len(site_verileri)
nakit_orani = round(((toplam_varlik_sayisi - aktif_pozisyon_sayisi) / max(1, toplam_varlik_sayisi)) * 100, 1)

# 2. PERFORMANS ÖZET İSTATİSTİKLERİ (6 Ay ve 2 Yıl)
yenen_2yil = sum(1 for x in performans_2yil_listesi if x["yendi"])
yenen_6ay = sum(1 for x in performans_6ay_listesi if x["yendi"])

ort_bh_2yil = round(float(np.mean([x["bh"] for x in performans_2yil_listesi])), 2) if performans_2yil_listesi else 0.0
ort_algo_2yil = round(float(np.mean([x["algo"] for x in performans_2yil_listesi])), 2) if performans_2yil_listesi else 0.0

ort_bh_6ay = round(float(np.mean([x["bh"] for x in performans_6ay_listesi])), 2) if performans_6ay_listesi else 0.0
ort_algo_6ay = round(float(np.mean([x["algo"] for x in performans_6ay_listesi])), 2) if performans_6ay_listesi else 0.0

# Listeleri Alfa farkına göre büyükten küçüğe sırala
performans_2yil_listesi.sort(key=lambda x: (x["algo"] - x["bh"]), reverse=True)
performans_6ay_listesi.sort(key=lambda x: (x["algo"] - x["bh"]), reverse=True)

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
    "performans": {
        "toplam_varlik": toplam_varlik_sayisi,
        "alti_ay": {
            "yenen_sayisi": yenen_6ay,
            "bist_ort": ort_bh_6ay,
            "algo_ort": ort_algo_6ay,
            "liste": performans_6ay_listesi
        },
        "iki_yil": {
            "yenen_sayisi": yenen_2yil,
            "bist_ort": ort_bh_2yil,
            "algo_ort": ort_algo_2yil,
            "liste": performans_2yil_listesi
        },
        "grafik": {
            "tarihler": hedef_grafik_tarihler,
            "algo": hedef_grafik_algo,
            "bist": hedef_grafik_bist
        }
    },
    "sinyaller": site_verileri
}

with open("signals.json", "w", encoding="utf-8") as f:
    json.dump(veri_paketi, f, ensure_ascii=False, indent=4)

print(f"✅ BIST100 Algoritması {toplam_varlik_sayisi} varlığı analiz etti!")
print(f"🏆 2 Yıllık Testte Al-Bekle'yi Yenen: {yenen_2yil} / {toplam_varlik_sayisi} Varlık")
print(f"🏆 6 Aylık Testte Al-Bekle'yi Yenen: {yenen_6ay} / {toplam_varlik_sayisi} Varlık")
