import os
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
WF_EGITIM = 250   # walk-forward: strateji seçimi için geriye bakış (işlem günü)
WF_TEST = int(os.environ.get("WF_TEST", 63))      # walk-forward: seçilen stratejinin görmeden uygulandığı dönem
HISTORY_DOSYASI = os.environ.get("HISTORY_DOSYASI", "history.json")
SECIM_SKORU = os.environ.get("SECIM_SKORU", "mdd")   # "mdd": Al-Bekle'yi yenenler arasında en düşük max drawdown | "dengeli": getiri - 0.45*maxDD
WF_PENCERE = int(os.environ.get("WF_PENCERE", 750))   # out-of-sample için kullanılan toplam geçmiş (işlem günü, 3 yıllık verinin tamamı)
SLIPAJ = 0.001    # her işlemde yön başına kayma varsayımı (binde 1)
LIKIT_N = int(os.environ.get("LIKIT_N", 30))   # likit evren: son 60 günde ortalama TL hacmi en yüksek N hisse (+ Gram Altın)
PIYASA_FILTRE = os.environ.get("PIYASA_FILTRE", "kapali")   # kapali | giris (XU100 EMA200 altındayken yeni giriş yok) | cikis (ek olarak pozisyonlardan da çık)
MOM_N, MOM_GUN = int(os.environ.get("MOM_N", 0)), int(os.environ.get("MOM_GUN", 126))   # MOM_N>0: yeni giriş yalnızca 126 günlük momentumu evrende ilk N içinde olan varlıklara
NAKIT_VARLIK = os.environ.get("NAKIT_VARLIK", "nakit")   # nakit | altin (boştaki kasa PPF yerine gram altın getirisini alır; deney)
NAKIT_CARPAN = 0.9   # nakit getirisi = politika faizi x 0,9 (mevduat/PPF net getirisi yaklaşımı)
# TCMB 1 hafta vadeli repo (politika) faizi, YAKLAŞIK ve hafızadan; doğrulayıp düzelt. (yürürlük tarihi, yıllık %)
POLITIKA_FAIZI = [("2020-12-24", 17.0), ("2021-03-18", 19.0), ("2021-09-23", 18.0), ("2021-10-21", 16.0), ("2021-11-18", 15.0), ("2021-12-16", 14.0),
                  ("2022-08-18", 13.0), ("2022-09-22", 12.0), ("2022-10-20", 10.5), ("2022-11-24", 9.0), ("2023-02-23", 8.5), ("2023-06-22", 15.0),
                  ("2023-07-27", 17.5), ("2023-08-24", 25.0), ("2023-09-21", 30.0), ("2023-10-26", 35.0), ("2023-11-23", 40.0), ("2023-12-21", 42.5),
                  ("2024-01-25", 45.0), ("2024-03-21", 50.0), ("2024-12-26", 47.5), ("2025-01-23", 45.0), ("2025-03-06", 42.5), ("2025-04-17", 46.0),
                  ("2025-07-24", 43.0), ("2025-09-11", 40.5), ("2025-10-23", 39.5), ("2025-12-11", 38.0), ("2026-01-22", 37.0), ("2026-10-22", 36.0)]
EVREN_MANUEL = None  # örn. ["AKBNK.IS", "ASELS.IS", ...] verirsen likidite sıralaması yerine bu liste kullanılır
LIMIT_ESIK = float(os.environ.get("LIMIT_ESIK", 0.095))   # BIST günlük fiyat sınırı ~%10: açılış tavan/tabandaysa alış/satış gerçekleşmez
BAD_TICK_ESIK = 0.20                       # günlük %20 üzeri sıçrama şüpheli veri
SOGUMA_GUN = int(os.environ.get("SOGUMA_GUN", 4))                             # stop sonrası yeniden giriş yasağı (işlem günü)
GAP_ESIK = float(os.environ.get("GAP_ESIK", 0.035))                           # açılış dünkü kapanışın %3,5+ altındaysa acil çıkış
KILL_PENCERE, KILL_ESIK, KILL_KILIT_GUN = 3, float(os.environ.get("KILL_ESIK", 0.06)), int(os.environ.get("KILL_KILIT_GUN", 7))   # 3 günde %6 erime -> 7 gün nakit kilidi
OYLAMA_ESIKLERI = [(0.3, -0.1), (0.2, -0.2), (0.4, 0.0)]   # (giriş, çıkış) oy skoru eşikleri

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

def _gun(i):
    i = pd.DatetimeIndex(i); i = i.tz_localize(None) if i.tz is not None else i
    return i.normalize()

def nakit_gunluk(idx):
    """Tarihlere göre günlük nakit getirisi (politika faizi tablosundan)."""
    t = pd.Series([r for _, r in POLITIKA_FAIZI], index=pd.to_datetime([d for d, _ in POLITIKA_FAIZI]))
    ix = _gun(idx); yillik = t.reindex(t.index.union(ix)).ffill().bfill().reindex(ix).values
    return (1.0 + NAKIT_CARPAN * yillik / 100.0) ** (1.0 / 252.0) - 1.0

def ek_diziler(idx, ad):
    """Pencereye hizalı ek diziler: nakit getirisi, piyasa rejimi (XU100 > EMA200), momentum sırası filtresi."""
    d = {"PPF": nakit_gunluk(idx)}; ix = _gun(idx)
    if NAKIT_VARLIK == "altin" and GRAM_GETIRI is not None:
        g = GRAM_GETIRI.reindex(ix).values; d["PPF"] = np.where(np.isnan(g), d["PPF"], g)
    if PIYASA_SERISI is not None: d["PIYASA"] = PIYASA_SERISI.reindex(ix, method="ffill").fillna(1).values
    if MOM_OK is not None and ad in MOM_OK.columns: d["MOM"] = MOM_OK[ad].reindex(ix, method="ffill").fillna(False).values.astype(bool)
    return d

def backtest_gelismis_motor(fiyatlar, acilislar, durumlar, kalkanlar, atrler, adxler, baz_stoplar, adx_esik, atr_carpan, cikis_modu, ppf=None, piyasa=None, mom_ok=None):
    """Karar gün sonu kapanışıyla verilir, emir ERTESİ GÜN AÇILIŞINDA işlenir.
    Korumalar: Gap çıkışı (stop beklemeden), stop sonrası soğuma kilidi, hisse bazlı Kill-Switch."""
    n = len(fiyatlar)
    nakit, adet, zirve, giris_bakiye, emir = 100.0, 0.0, 0.0, 0.0, 0
    kilit = kilit_sonra = 0   # kilit > 0: yeniden giriş yasak
    kazanan = toplam = olay_gap = olay_kill = 0
    bakiye = np.full(n, 100.0); poz = np.zeros(n, dtype=int); stoplar = np.zeros(n)
    for i in range(n):
        ac = acilislar[i]
        if adet > 0.0 and i > 0 and ac <= fiyatlar[i - 1] * (1.0 - GAP_ESIK):   # Gap koruması
            emir, kilit_sonra = -1, SOGUMA_GUN; olay_gap += 1
        yukari = i > 0 and ac >= fiyatlar[i - 1] * (1.0 + LIMIT_ESIK)   # tavan açılış: alış gerçekleşmez
        asagi = i > 0 and ac <= fiyatlar[i - 1] * (1.0 - LIMIT_ESIK)    # taban açılış: satış gerçekleşmez
        if emir == 1 and adet == 0.0 and not yukari:
            giris_bakiye, adet, nakit, zirve = nakit, nakit * (1.0 - KOMISYON) / (ac * (1.0 + SLIPAJ)), 0.0, ac
        elif emir == -1 and adet > 0.0 and not asagi:
            nakit, adet = adet * ac * (1.0 - SLIPAJ) * (1.0 - KOMISYON), 0.0
            toplam += 1; kazanan += int(nakit > giris_bakiye); kilit = kilit_sonra
        if not (emir == -1 and adet > 0.0):   # satış tabanda engellendiyse emir ertesi güne taşınır
            emir = kilit_sonra = 0
        fiyat, kalkan, atr = fiyatlar[i], kalkanlar[i], atrler[i]
        if np.isnan(kalkan) or np.isnan(atr):
            bakiye[i] = nakit if adet == 0.0 else adet * fiyat
            poz[i] = int(adet > 0); continue
        if adet == 0.0:
            nakit *= (1.0 + (PPF_GUNLUK_GETIRI if ppf is None else ppf[i])); bakiye[i] = nakit
            if kilit == 0 and durumlar[i] == 1 and fiyat > kalkan and adxler[i] >= adx_esik and (piyasa is None or PIYASA_FILTRE == "kapali" or piyasa[i] == 1) and (mom_ok is None or mom_ok[i]):
                emir = 1
            stoplar[i] = kalkan
        else:
            zirve = max(zirve, fiyat); bakiye[i] = adet * fiyat
            atr_stop = zirve - atr_carpan * atr
            stoplar[i] = max(kalkan * 0.98, atr_stop, baz_stoplar[i] if baz_stoplar[i] < fiyat else atr_stop)
            cik_stop = fiyat < atr_stop
            cik = (durumlar[i] == -1 or cik_stop) if cikis_modu == 0 else (cik_stop or fiyat < kalkan)
            cik = cik or (PIYASA_FILTRE == "cikis" and piyasa is not None and piyasa[i] == 0)
            if bakiye[i] <= bakiye[max(0, i - KILL_PENCERE):i + 1].max() * (1.0 - KILL_ESIK):   # Kill-Switch
                emir, kilit_sonra = -1, KILL_KILIT_GUN; olay_kill += 1
            elif cik:
                emir, kilit_sonra = -1, (SOGUMA_GUN if cik_stop else 0)
        poz[i] = int(adet > 0.0)
        if kilit > 0 and adet == 0.0:
            kilit -= 1
    son_deger = nakit if adet == 0.0 else adet * fiyatlar[-1] * (1.0 - KOMISYON)
    if adet > 0.0:
        toplam += 1; kazanan += int(son_deger > giris_bakiye)
    zirveler = np.maximum.accumulate(bakiye)
    max_dd = float(np.max((zirveler - bakiye) / np.maximum(zirveler, 1e-8)) * 100.0)
    hedef = int((adet > 0.0 and emir != -1) or emir == 1)
    return {"net_getiri": son_deger - 100.0, "max_dd": max_dd, "win_rate": (kazanan / toplam * 100.0) if toplam else 0.0,
            "islem": toplam, "kazanan": kazanan, "bakiye_serisi": bakiye, "pozisyon_serisi": poz, "stop_serisi": stoplar, "gap": olay_gap, "kill": olay_kill,
            "hedef": hedef, "kilit_kalan": int(kilit), "bekleyen_emir": int(emir)}   # yarın açılışta hedef pozisyon

def kirli_veri_temizle(df, ad):
    """Günlük %20+ sıçrama ertesi gün geri dönüyorsa hatalı veri iğnesidir: onarılır. Kalıcıysa (bölünme/veri hatası) yalnızca uyarılır."""
    c = df['Close'].values.copy(); duzeltilen = 0
    for i in range(1, len(c)):
        if abs(c[i] / c[i - 1] - 1.0) > BAD_TICK_ESIK:
            if i + 1 < len(c) and abs(c[i + 1] / c[i - 1] - 1.0) < BAD_TICK_ESIK / 2:
                for kol in ('Open', 'High', 'Low', 'Close'):
                    df.iloc[i, df.columns.get_loc(kol)] = c[i - 1]
                c[i] = c[i - 1]; duzeltilen += 1
            else:
                print(f"⚠️ {ad}: {df.index[i]:%d.%m.%Y} günlük sıçrama kalıcı (bölünme/veri hatası olabilir), düzeltilmedi.")
    if duzeltilen:
        print(f"🧹 {ad}: {duzeltilen} hatalı veri iğnesi onarıldı.")
    return df

def oylama_hesapla(df):
    """Investing.com tarzı 21 gösterge: 9 osilatör + 12 hareketli ortalama. Her biri +1 (Al), -1 (Sat) veya 0 (Nötr) oy verir."""
    c, h, l = df['Close'], df['High'], df['Low']
    mv = lambda al, sat: np.where(al, 1, np.where(sat, -1, 0))
    d = c.diff(); up = d.clip(lower=0).ewm(alpha=1/14, adjust=False).mean(); dn = (-d.clip(upper=0)).ewm(alpha=1/14, adjust=False).mean()
    rsi = 100 - 100 / (1 + up / dn.replace(0, np.nan))
    hh9, ll9 = h.rolling(9).max(), l.rolling(9).min()
    stoch = (100 * (c - ll9) / (hh9 - ll9).replace(0, np.nan)).rolling(6).mean()
    rmin, rmax = rsi.rolling(14).min(), rsi.rolling(14).max(); srsi = 100 * (rsi - rmin) / (rmax - rmin).replace(0, np.nan)
    macd = c.ewm(span=12, adjust=False).mean() - c.ewm(span=26, adjust=False).mean(); sig = macd.ewm(span=9, adjust=False).mean()
    tr = pd.concat([h - l, (h - c.shift()).abs(), (l - c.shift()).abs()], axis=1).max(axis=1); atr = tr.ewm(alpha=1/14, adjust=False).mean()
    dh, dl = h.diff(), -l.diff()
    pdi = 100 * dh.where((dh > dl) & (dh > 0), 0.0).ewm(alpha=1/14, adjust=False).mean() / atr
    mdi = 100 * dl.where((dl > dh) & (dl > 0), 0.0).ewm(alpha=1/14, adjust=False).mean() / atr
    adx = (100 * (pdi - mdi).abs() / (pdi + mdi).replace(0, np.nan)).ewm(alpha=1/14, adjust=False).mean()
    hh14, ll14 = h.rolling(14).max(), l.rolling(14).min(); wr = -100 * (hh14 - c) / (hh14 - ll14).replace(0, np.nan)
    tp = (h + l + c) / 3; sapma = tp.rolling(20).apply(lambda x: np.abs(x - x.mean()).mean(), raw=True)
    cci = (tp - tp.rolling(20).mean()) / (0.015 * sapma.replace(0, np.nan))
    e13 = c.ewm(span=13, adjust=False).mean(); bull, bear = h - e13, l - e13
    oy = {"RSI": mv(rsi < 30, rsi > 70), "Stoch": mv(stoch < 20, stoch > 80), "StochRSI": mv(srsi < 20, srsi > 80), "MACD": mv(macd > sig, macd < sig),
          "ADX": mv((adx > 25) & (pdi > mdi), (adx > 25) & (pdi < mdi)), "Williams": mv(wr < -80, wr > -20), "CCI": mv(cci < -100, cci > 100),
          "ROC": mv(c.pct_change(12) > 0, c.pct_change(12) < 0),
          "BullBear": mv((e13 > e13.shift()) & (bear < 0) & (bear > bear.shift()), (e13 < e13.shift()) & (bull > 0) & (bull < bull.shift()))}
    for per in (5, 10, 20, 50, 100, 200):
        sma = c.rolling(per).mean(); ema = c.ewm(span=per, adjust=False).mean()
        oy[f"SMA{per}"] = mv(c > sma, c < sma); oy[f"EMA{per}"] = mv(c > ema, c < ema)
    M = pd.DataFrame(oy, index=df.index)
    return M.sum(axis=1) / float(M.shape[1]), M

def oy_etiket(s):
    return "Güçlü Al" if s >= 0.5 else "Al" if s >= 0.1 else "Güçlü Sat" if s <= -0.5 else "Sat" if s <= -0.1 else "Nötr"

def ind_oylama(skor, g, c):
    d = np.zeros(len(skor), dtype=int); cur = -1
    for i, s in enumerate(skor):
        cur = 1 if s >= g else -1 if s <= c else cur
        d[i] = cur
    return d

def mtf_matrisi(gun, saat):
    """Yalnızca GÖSTERGE: 1S/4S/1G/1H oylama etiketi (tamamlanmış son bar). İşlem kararına girmez."""
    def etiket(d):
        try:
            if d is None or len(d) < 30: return None
            return oy_etiket(float(oylama_hesapla(d)[0].iloc[-1]))
        except Exception:
            return None
    ohlc = {'Open': 'first', 'High': 'max', 'Low': 'min', 'Close': 'last'}
    hafta = gun[['Open', 'High', 'Low', 'Close']].resample('W-FRI').agg(ohlc).dropna()
    s4 = saat.resample('4h').agg(ohlc).dropna() if saat is not None and len(saat) else None
    return {"1S": etiket(saat), "4S": etiket(s4), "1G": etiket(gun), "1H": etiket(hafta)}

def saglik_hesapla(seri, kasalar):
    v = [x["deger"] for x in seri]; dd = (max(v) - v[-1]) / max(v) * 100.0 if v else 0.0
    son3 = (v[-1] / v[-4] - 1.0) * 100.0 if len(v) >= 4 else 0.0
    kilitli = sum(1 for k in kasalar.values() if k.get("kilit", 0) > 0)
    durum = "Kritik" if dd >= 6.0 or son3 <= -KILL_ESIK * 100.0 else "Dikkat" if dd >= 3.0 or kilitli >= 0.2 * max(1, len(kasalar)) else "Sağlıklı"
    return {"durum": durum, "dd": round(dd, 1), "son3": round(son3, 1), "kilitli": kilitli}

macd_ayarlari = [(8, 21), (12, 26), (5, 35), (24, 52)]
st_ayarlari = [(10, 2.0), (10, 3.0), (14, 2.5), (20, 2.0)]
ema_ayarlari = [(5, 13), (9, 21), (13, 34), (21, 50)]
donchian_ayarlari = [14, 20, 34]
# (Kalkan, ADX_Eşik, ATR_Stop_Çarpanı, Çıkış_Modu)
rejim_kombinasyonlari = [("EMA200", 18.0, 3.0, 0), ("EMA200", 22.0, 2.5, 0), ("EMA200", 14.0, 4.2, 1), ("EMA100", 16.0, 3.5, 1)]
if os.environ.get("REJIM_SET") == "gevsek":   # deney varyantı: EMA50 kalkanı + düşük ADX eşikleri
    rejim_kombinasyonlari = [("EMA50", 10.0, 3.0, 1), ("EMA50", 14.0, 2.5, 0), ("EMA100", 12.0, 3.5, 0), ("EMA200", 12.0, 3.0, 0)]

def calistir(ad, rej, k, s, e, fiy, acl, atr, adx):
    ek = lambda a_: (k[a_][s:e] if a_ in k else None)
    return backtest_gelismis_motor(fiy[s:e], acl[s:e], ad[2][s:e], k[rej[0]][s:e], atr[s:e], adx[s:e], ad[3][s:e], rej[1], rej[2], rej[3], ek("PPF"), ek("PIYASA"), ek("MOM"))

def en_iyi_strateji(adaylar, k, s, e, fiy, acl, atr, adx):
    """[s:e) aralığında Alfa + risk-ayarlı skora göre şampiyonu seçer."""
    bh = (fiy[e - 1] - fiy[s]) / max(1e-8, fiy[s]) * 100.0
    en_iyi, secim = -1e18, None
    for ad in adaylar:
        for rej in rejim_kombinasyonlari:
            sn = calistir(ad, rej, k, s, e, fiy, acl, atr, adx)
            skor = ((5000.0 if sn["net_getiri"] > bh else 0.0) + sn["net_getiri"] - 0.45 * sn["max_dd"]) if SECIM_SKORU == "dengeli" else ((1000.0 - sn["max_dd"] + 1e-3 * sn["net_getiri"]) if sn["net_getiri"] > bh else sn["net_getiri"] - bh)   # Al-Bekle'yi yenenler arasında en düşük max drawdown
            if skor > en_iyi:
                en_iyi, secim = skor, (ad, rej, sn)
    return secim

def aday_olustur(w, sk_s, ad_adi=""):
    """w penceresi için tüm aday stratejileri ve girdi dizilerini üretir."""
    ad = []
    for h, y in macd_ayarlari:
        d, s = ind_macd(w['Close'], h, y); ad.append(("MACD", f"H:{h}/Y:{y}", d, s))
    for p_, c_ in st_ayarlari:
        d, s = ind_supertrend(w, p_, c_); ad.append(("SuperTrend", f"P:{p_}/Ç:{c_}", d, s))
    for a, b in ema_ayarlari:
        d, s = ind_ema_cross(w['Close'], a, b); ad.append(("EMA Kesişim", f"{a}/{b}", d, s))
    for per in donchian_ayarlari:
        d, s = ind_donchian(w['High'], w['Low'], w['Close'], per); ad.append(("Donchian", f"K:{per}", d, s))
    sk = sk_s.reindex(w.index).fillna(0.0).values; baz = w['Low'].rolling(20).min().shift(1).fillna(0.0).values
    for g_, c_ in OYLAMA_ESIKLERI:
        ad.append(("Oylama", f"G:{g_}/Ç:{c_}", ind_oylama(sk, g_, c_), baz))
    k = {"EMA200": w['EMA200'].values, "EMA100": w['EMA100'].values, "EMA50": w['EMA50'].values}
    k.update(ek_diziler(w.index, ad_adi))
    return ad, k, w['Close'].values, w['Open'].values, w['ATR'].values, w['ADX'].values

def walk_forward(adaylar, k, fiy, acl, atr, adx):
    """Her WF_TEST günde, yalnızca önceki WF_EGITIM günle seçilen strateji sonraki döneme görmeden uygulanır."""
    n = len(fiy); katsayi = 1.0; egri = []; maruz = []; islem = kaz = 0
    s = WF_EGITIM
    while s < n:
        e = min(s + WF_TEST, n)
        ad, rej, _ = en_iyi_strateji(adaylar, k, s - WF_EGITIM, s, fiy, acl, atr, adx)
        sn = calistir(ad, rej, k, s, e, fiy, acl, atr, adx); seg = sn["bakiye_serisi"] / 100.0 * katsayi; maruz.extend(sn["pozisyon_serisi"].tolist()); islem += sn["islem"]; kaz += sn["kazanan"]
        egri.extend(seg.tolist()); katsayi = float(seg[-1]); s = e
    return np.array(egri), (float(np.mean(maruz)) if maruz else 0.0), islem, kaz, np.array(maruz)   # uzunluk n - WF_EGITIM, 1.0 = test başlangıcı

AYLAR = ["Ocak", "Şubat", "Mart", "Nisan", "Mayıs", "Haziran", "Temmuz", "Ağustos", "Eylül", "Ekim", "Kasım", "Aralık"]
def tr_tarih(iso):
    y, m, d = iso.split("-"); return f"{int(d)} {AYLAR[int(m) - 1]} {y}"

def gecmis_yukle():
    try:
        with open(HISTORY_DOSYASI, encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}

def _sat(k, h, v, neden, olaylar):
    satis = v["acilis"] * (1.0 - SLIPAJ)
    g = round((satis / k["giris_fiyat"] - 1.0) * 100.0, 1) if k["giris_fiyat"] else None
    k["nakit"] = k["adet"] * satis * (1.0 - KOMISYON); k["adet"] = 0.0
    olaylar.append({"tarih": v["tarih"], "hisse": h, "islem": neden, "fiyat": round(v["acilis"], 2), "getiri": g, "strateji": v["strateji"]})

def canli_kitabi_guncelle(gecmis, hedefler, veriler):
    """İLERİYE DÖNÜK, DONDURULMUŞ kayıt. Dünkü karar bugünün açılışında işlenir; geçmiş günler yeniden hesaplanmaz.
    Canlı korumalar: Gap acil çıkışı, stop sonrası kilit, hisse bazlı Kill-Switch."""
    kitap = gecmis.setdefault("kitap", {}); kasalar = kitap.setdefault("kasalar", {}); olaylar = gecmis.setdefault("olaylar", [])
    ilk = not kasalar; bekleyen = kitap.get("bekleyen", {}); pay = BASLANGIC_SERMAYE / max(1, len(veriler)); zorla_cik = set()
    for h, v in veriler.items():
        if not ilk and h not in kasalar:
            continue
        k = kasalar.setdefault(h, {"nakit": pay, "adet": 0.0, "son_tarih": None, "giris_fiyat": None, "son_fiyat": v["kapanis"], "kilit": 0, "dg": []})
        if k["son_tarih"] is None:
            k["son_tarih"] = v["tarih"]
        elif v["tarih"] > k["son_tarih"]:
            if k["adet"] > 0.0 and k["son_fiyat"] * (1.0 - LIMIT_ESIK) < v["acilis"] <= k["son_fiyat"] * (1.0 - GAP_ESIK):
                _sat(k, h, v, "Acil Çıkış (Gap)", olaylar); k["kilit"] = SOGUMA_GUN
            elif bekleyen.get(h, 0) == 1 and k["adet"] == 0.0 and k.get("kilit", 0) == 0 and v["acilis"] < k["son_fiyat"] * (1.0 + LIMIT_ESIK):
                k["giris_fiyat"] = v["acilis"] * (1.0 + SLIPAJ); k["adet"] = k["nakit"] * (1.0 - KOMISYON) / k["giris_fiyat"]; k["nakit"] = 0.0
                olaylar.append({"tarih": v["tarih"], "hisse": h, "islem": "Trend Girişi", "fiyat": round(v["acilis"], 2), "getiri": None, "strateji": v["strateji"]})
            elif bekleyen.get(h, 0) == 0 and k["adet"] > 0.0 and v["acilis"] > k["son_fiyat"] * (1.0 - LIMIT_ESIK):
                _sat(k, h, v, k.pop("neden", None) or "Trend Çıkışı", olaylar)
            if k["adet"] == 0.0:
                k["nakit"] *= (1.0 + PPF_GUNLUK_GETIRI) ** max(1, v["yeni_bar"])
            k["kilit"] = max(0, k.get("kilit", 0) - max(1, v["yeni_bar"])); k["son_tarih"] = v["tarih"]
        k["son_fiyat"] = v["kapanis"]
        dg = k.setdefault("dg", []); simdi = k["nakit"] + k["adet"] * v["kapanis"]
        if k.get("dg_tarih") == v["tarih"] and dg: dg[-1] = simdi
        else: dg.append(simdi); k["dg_tarih"] = v["tarih"]
        del dg[:-(KILL_PENCERE + 1)]
        if k["adet"] > 0.0 and dg[-1] <= max(dg) * (1.0 - KILL_ESIK):   # Kill-Switch: yarın açılışta çık, 7 gün nakitte kal
            k["kilit"] = KILL_KILIT_GUN; k["neden"] = "Devre Kesici (Kill-Switch)"; zorla_cik.add(h)
    yeni = {**bekleyen, **{h: int(x) for h, x in hedefler.items()}}
    for h, k in kasalar.items():
        if h in zorla_cik or k.get("kilit", 0) > 0:
            yeni[h] = 0
    kitap["bekleyen"] = yeni
    deger = sum(k["nakit"] + k["adet"] * k["son_fiyat"] for k in kasalar.values())
    bugun = max(k["son_tarih"] for k in kasalar.values())
    kitap.setdefault("baslangic", bugun)
    seri = gecmis.setdefault("deger_serisi", [])
    kayit = {"tarih": bugun, "deger": round(deger, 2)}
    if seri and seri[-1]["tarih"] == bugun: seri[-1] = kayit
    else: seri.append(kayit)
    gecmis["olaylar"] = olaylar[-1000:]
    return kasalar, deger

gecmis = gecmis_yukle()
kitap_son = {h: k.get("son_tarih") for h, k in gecmis.get("kitap", {}).get("kasalar", {}).items()}

print("⏳ BIST100 ve Gram Altın Verileri İndiriliyor...")
def sayi(x): return pd.to_numeric(x.squeeze())
aday_hisseler = [h for h in bist100 if h != "GRAM_ALTIN"]
evren = gecmis.get("evren")
indir = aday_hisseler if evren is None else [h for h in evren if h != "GRAM_ALTIN"]
toplu_veri = yf.download(indir + ["GC=F", "TRY=X", "XU100.IS"], period=os.environ.get("GECMIS", "3y"), interval="1d", group_by='ticker', progress=False, threads=True)
if evren is None:   # ilk çalışma: likit evreni seç ve DONDUR (history.json'a yazılır)
    if EVREN_MANUEL:
        secilen = list(EVREN_MANUEL)
    else:
        hacim = {}
        for h in indir:
            if h in toplu_veri.columns.levels[0]:
                try: hacim[h] = float((sayi(toplu_veri[h]['Close']) * sayi(toplu_veri[h]['Volume'])).dropna().tail(60).mean())
                except Exception: pass
        secilen = sorted(hacim, key=hacim.get, reverse=True)[:LIKIT_N]
    evren = secilen + ["GRAM_ALTIN"]; gecmis["evren"] = evren
    print("🔎 Likit evren seçildi:", ", ".join(h.replace(".IS", "") for h in secilen))
bist100 = evren
normal_hisseler = [h for h in bist100 if h != "GRAM_ALTIN"]

def _norm(s):
    s = s.copy(); s.index = _gun(s.index); return s[~s.index.duplicated()].sort_index()
try:
    xu_ = _norm(sayi(toplu_veri["XU100.IS"]['Close']).dropna()); PIYASA_SERISI = (xu_ > xu_.ewm(span=200, adjust=False).mean()).astype(int)
except Exception:
    PIYASA_SERISI = None
    if PIYASA_FILTRE != "kapali": print("⚠️ XU100 verisi alınamadı, piyasa filtresi devre dışı.")
MOM_OK = None
if MOM_N > 0:
    kd = {h.replace(".IS", ""): _norm(sayi(toplu_veri[h]['Close']).dropna()) for h in normal_hisseler if h in toplu_veri.columns.levels[0]}
    try:
        gr_ = pd.concat([sayi(toplu_veri["GC=F"]['Close']), sayi(toplu_veri["TRY=X"]['Close'])], axis=1, join='inner').dropna()
        kd["GRAM_ALTIN"] = _norm(gr_.iloc[:, 0] * gr_.iloc[:, 1] / 31.1034768)
    except Exception: pass
    MOM_OK = pd.DataFrame(kd).pct_change(MOM_GUN).rank(axis=1, ascending=False, method="min") <= MOM_N
try:
    gr0 = pd.concat([sayi(toplu_veri["GC=F"]['Close']), sayi(toplu_veri["TRY=X"]['Close'])], axis=1, join='inner').dropna()
    GRAM_KAPANIS = _norm(gr0.iloc[:, 0] * gr0.iloc[:, 1] / 31.1034768); GRAM_GETIRI = GRAM_KAPANIS.pct_change()
except Exception:
    GRAM_KAPANIS = GRAM_GETIRI = None
site_verileri, canli_veriler, hedefler = [], {}, {}
stop_map, gram_close = {}, None
try:   # 1S / 4S trend göstergeleri için saatlik veri (yalnızca görüntü amaçlı)
    saatlik = None if os.environ.get("SAATLIK") == "0" else yf.download(normal_hisseler, period="120d", interval="1h", group_by='ticker', progress=False, threads=True)
except Exception:
    saatlik = None
is_egrileri, bh_egrileri, oos_algo_egrileri, oos_bh_egrileri = [], [], [], []
perf2, perf6, perf_oos, oos_maruz, oos_islem, oos_poz = [], [], [], [], [], []

def sayi(x): return pd.to_numeric(x.squeeze())

for hisse in bist100:
    try:
        if hisse == "GRAM_ALTIN":
            o, u = toplu_veri["GC=F"], toplu_veri["TRY=X"]
            ortak = pd.concat([sayi(o['Close']), sayi(o['High']), sayi(o['Low']), sayi(o['Open']), sayi(u['Close'])], axis=1, join='inner').dropna()
            ortak.columns = ['C', 'H', 'L', 'O', 'U']
            df = pd.DataFrame({'Close': ortak.C * ortak.U / 31.1034768, 'High': ortak.H * ortak.U / 31.1034768,
                               'Low': ortak.L * ortak.U / 31.1034768, 'Open': ortak.O * ortak.U / 31.1034768}, index=ortak.index)
        else:
            if hisse not in toplu_veri.columns.levels[0]:
                continue
            df = toplu_veri[hisse].copy()
            for c in ('Close', 'High', 'Low', 'Open'):
                df[c] = sayi(df[c])
            df['Open'] = df['Open'].fillna(df['Close'])
            df.dropna(subset=['Close', 'High', 'Low'], inplace=True)
        df = kirli_veri_temizle(df, hisse)
        if len(df) < 250:
            continue

        df = hesapla_temel_metrikler(df)
        df['EMA50'] = df['Close'].ewm(span=50, adjust=False).mean()
        if hisse == "GRAM_ALTIN": gram_close = df['Close'].copy()
        test = df.tail(500).copy(); n = len(test)
        fiy, acl, atr, adx = test['Close'].values, test['Open'].values, test['ATR'].values, test['ADX'].values
        k = {"EMA200": test['EMA200'].values, "EMA100": test['EMA100'].values, "EMA50": test['EMA50'].values}; k.update(ek_diziler(test.index, hisse.replace(".IS", "")))
        bh_2yil = (fiy[-1] - fiy[0]) / max(1e-8, fiy[0]) * 100.0

        adaylar = []
        for h, y in macd_ayarlari:
            d, s = ind_macd(test['Close'], h, y); adaylar.append(("MACD", f"H:{h}/Y:{y}", d, s))
        for p, c in st_ayarlari:
            d, s = ind_supertrend(test, p, c); adaylar.append(("SuperTrend", f"P:{p}/Ç:{c}", d, s))
        for a, b in ema_ayarlari:
            d, s = ind_ema_cross(test['Close'], a, b); adaylar.append(("EMA Kesişim", f"{a}/{b}", d, s))
        for per in donchian_ayarlari:
            d, s = ind_donchian(test['High'], test['Low'], test['Close'], per); adaylar.append(("Donchian", f"K:{per}", d, s))

        sk_s, M = oylama_hesapla(df); skor_s = sk_s.reindex(test.index).fillna(0.0).values
        baz_alt = test['Low'].rolling(20).min().shift(1).fillna(0.0).values
        for g_, c_ in OYLAMA_ESIKLERI:
            adaylar.append(("Oylama", f"G:{g_}/Ç:{c_}", ind_oylama(skor_s, g_, c_), baz_alt))
        oy_son = {"etiket": oy_etiket(float(sk_s.iloc[-1])), "skor": round(float(sk_s.iloc[-1]), 2), "al": int((M.iloc[-1] > 0).sum()),
                  "sat": int((M.iloc[-1] < 0).sum()), "notr": int((M.iloc[-1] == 0).sum())}
        ad, rej, sonuc = en_iyi_strateji(adaylar, k, 0, n, fiy, acl, atr, adx)   # güncel şampiyon (in-sample)
        strateji = f"{ad[0]} ({ad[1]} • {'Trend' if rej[3] == 1 else 'ADX'})"
        giris_engelleri = []
        if not sonuc["hedef"]:
            if sonuc["bekleyen_emir"] == -1:
                giris_engelleri.append("Çıkış emri bekliyor")
            else:
                if sonuc["kilit_kalan"] > 0:
                    giris_engelleri.append(f"Soğuma/devre kesici kilidi: {sonuc['kilit_kalan']} gün")
                if ad[2][-1] != 1:
                    giris_engelleri.append("Seçilen strateji AL yönünde değil")
                kalkan = float(k[rej[0]][-1])
                if np.isfinite(kalkan) and fiy[-1] <= kalkan:
                    giris_engelleri.append(f"Fiyat {rej[0]} kalkanının altında")
                if np.isfinite(adx[-1]) and adx[-1] < rej[1]:
                    giris_engelleri.append(f"ADX {adx[-1]:.1f}, gerekli eşik {rej[1]:.0f}")
                if "PIYASA" in k and PIYASA_FILTRE != "kapali" and k["PIYASA"][-1] != 1:
                    giris_engelleri.append("XU100 piyasa filtresi kapalı")
                if "MOM" in k and not k["MOM"][-1]:
                    giris_engelleri.append("Momentum sıralama filtresi dışında")
                if not giris_engelleri:
                    giris_engelleri.append("Giriş koşulları oluşmadı; motor durumu incelenmeli")
        bakiye = sonuc["bakiye_serisi"]; temiz = hisse.replace(".IS", "")
        hedefler[temiz] = sonuc["hedef"]

        algo_2yil, bh_r = round(sonuc["net_getiri"], 1), round(bh_2yil, 1)
        g6 = min(126, n - 1)
        bh_6 = round((fiy[-1] - fiy[-g6]) / max(1e-8, fiy[-g6]) * 100.0, 1)
        algo_6 = round((bakiye[-1] - bakiye[-g6]) / max(1e-8, bakiye[-g6]) * 100.0, 1)
        st = float(sonuc["stop_serisi"][-1]); stop_map[temiz] = st

        tarih_iso = test.index.strftime("%Y-%m-%d")
        canli_veriler[temiz] = {"acilis": float(acl[-1]), "kapanis": float(fiy[-1]), "tarih": tarih_iso[-1], "strateji": strateji,
                                "yeni_bar": int((tarih_iso > (kitap_son.get(temiz) or "9999")).sum()) if kitap_son.get(temiz) else 1}
        site_verileri.append({
            "hisse": temiz, "sinyal": "İZLE", "fiyat": round(float(fiy[-1]), 2), "ema200": round(float(k["EMA200"][-1]), 2),
            "adx": round(float(adx[-1]), 1), "max_dd": round(sonuc["max_dd"], 1), "win_rate": round(sonuc["win_rate"], 1),
            "strateji": strateji, "giris_engelleri": giris_engelleri, "kalkan_tipi": rej[0], "kalkan": round(float(k[rej[0]][-1]), 2), "adx_esik": rej[1],
            "stop": f"{round(st, 2)} ₺" if st > 0 else "Trend Çıkışı", "getiri": algo_2yil, "bh_getiri": bh_r,
            "alfa": round(algo_2yil - bh_r, 1), "gecmis": [round(float(x), 2) for x in fiy[-30:]], "tarihler": [d.strftime("%d.%m") for d in test.index[-30:]]})
        try: sa = saatlik[hisse][['Open', 'High', 'Low', 'Close']].dropna() if (saatlik is not None and hisse in saatlik.columns.levels[0]) else None
        except Exception: sa = None
        site_verileri[-1].update({"oylama": oy_son, "mtf": mtf_matrisi(df, sa)})
        perf2.append({"hisse": temiz, "bh": bh_r, "algo": algo_2yil, "yendi": bool(algo_2yil > bh_r)})
        perf6.append({"hisse": temiz, "bh": bh_6, "algo": algo_6, "yendi": bool(algo_6 > bh_6)})
        is_egrileri.append(pd.Series(bakiye, index=test.index)); bh_egrileri.append(pd.Series(fiy / fiy[0] * 100.0, index=test.index))

        uzun = df.tail(WF_PENCERE).copy()
        if len(uzun) >= WF_EGITIM + 252:   # OUT-OF-SAMPLE: tüm geçmişte rolling walk-forward
            ad_u, k_u, fiy_u, acl_u, atr_u, adx_u = aday_olustur(uzun, sk_s, hisse.replace(".IS", ""))
            egri, mz, isl, kaz, pz = walk_forward(ad_u, k_u, fiy_u, acl_u, atr_u, adx_u); oos_maruz.append(mz); oos_islem.append((isl, kaz, len(egri))); oos_poz.append(pd.Series(pz, index=uzun.index[WF_EGITIM:]))
            idx = uzun.index[WF_EGITIM:]; bh_c = fiy_u[WF_EGITIM:] / fiy_u[WF_EGITIM - 1]
            oa, ob = round((egri[-1] - 1.0) * 100.0, 1), round((bh_c[-1] - 1.0) * 100.0, 1)
            perf_oos.append({"hisse": temiz, "bh": ob, "algo": oa, "yendi": bool(oa > ob)})
            site_verileri[-1]["oos_getiri"], site_verileri[-1]["oos_bh"] = oa, ob
            oos_algo_egrileri.append(pd.Series(egri * 100.0, index=idx)); oos_bh_egrileri.append(pd.Series(bh_c * 100.0, index=idx))
    except Exception as e:
        print(f"⚠️ {hisse} hesaplanırken hata: {e}")

# İLERİYE DÖNÜK (dondurulmuş) model portföy
beklenen = len(gecmis.get("kitap", {}).get("kasalar", {})) or len(bist100)
if len(canli_veriler) < 0.7 * beklenen:
    raise SystemExit(f"❌ Veri eksik veya evren değişti. history.json eski evrenle kalmışsa silip yeniden başlat ({len(canli_veriler)}/{beklenen} varlık). Dosyalar güncellenmedi.")
kasalar, guncel = canli_kitabi_guncelle(gecmis, hedefler, canli_veriler)
for d in site_verileri:
    kz = kasalar.get(d["hisse"]); poz = bool(kz and kz["adet"] > 0); hdf = gecmis["kitap"]["bekleyen"].get(d["hisse"], hedefler.get(d["hisse"], 0))
    d["sinyal"] = "TUT" if poz and hdf else "SAT" if poz else "AL" if hdf else "İZLE"
    if d["sinyal"] == "AL": d["sinyal_nedeni"] = "Bir sonraki açılış için giriş emri sırada"
    elif d["sinyal"] == "TUT": d["sinyal_nedeni"] = "Model pozisyonda kalıyor"
    elif d["sinyal"] == "SAT": d["sinyal_nedeni"] = "Bir sonraki açılış için çıkış emri sırada"
    else:
        engeller = list(d.get("giris_engelleri", []))
        if kz and kz.get("kilit", 0) > 0:
            engeller.insert(0, f"Canlı model kitabı kilidi: {kz['kilit']} gün")
        d["giris_engelleri"] = engeller
        d["sinyal_nedeni"] = "; ".join(engeller) or "Giriş koşulu oluşmadı"
with open(HISTORY_DOSYASI, "w", encoding="utf-8") as f:
    json.dump(gecmis, f, ensure_ascii=False, indent=1)

def risk(v, rf=None):
    v = np.array(v, dtype=float)
    if len(v) < 30: return None
    r = np.diff(v) / v[:-1] - (PPF_GUNLUK_GETIRI if rf is None else np.asarray(rf, dtype=float)[1:len(v)]); sd = r.std(ddof=1); dsd = np.sqrt(np.mean(np.minimum(r, 0.0) ** 2)); pk = np.maximum.accumulate(v)
    return {"sharpe": round(float(r.mean() / sd * np.sqrt(252)), 2) if sd > 0 else None, "sortino": round(float(r.mean() / dsd * np.sqrt(252)), 2) if dsd > 0 else None,
            "max_dd": round(float(np.max((pk - v) / pk) * 100.0), 1), "getiri": round(float((v[-1] / v[0] - 1.0) * 100.0), 1)}

def hizala(close, tarihler, baslangic):
    if close is None or not tarihler: return []
    c = close.dropna().copy(); c.index = c.index.strftime("%Y-%m-%d"); c = c[~c.index.duplicated()]
    ilk = c[c.index <= baslangic]
    if ilk.empty: return []
    b0 = float(ilk.iloc[-1]); cikti = []
    for t in tarihler:
        u = c[c.index <= t]; cikti.append(round(BASLANGIC_SERMAYE * float(u.iloc[-1]) / b0, 2) if len(u) else None)
    return cikti

def oos_paketi(a, b):
    """Varlıkların günlük getiri ortalamasından (eşit ağırlık, eldeki varlıklar) birleşik OOS eğrisi; nakit eğrisi zamana göre faizle."""
    if not a: return {"tarihler": [], "algo": [], "bist": [], "nakit": []}, np.array([])
    kum = lambda L: 100.0 * (1.0 + pd.concat([s / s.shift(1).fillna(100.0) - 1.0 for s in L], axis=1).mean(axis=1, skipna=True)).cumprod()
    A, B = kum(a), kum(b); rf = nakit_gunluk(A.index); N = 100.0 * np.cumprod(1.0 + rf)
    return {"tarihler": [d.strftime("%d.%m.%Y") for d in A.index], "algo": [round(float(x), 2) for x in A.values],
            "bist": [round(float(x), 2) for x in B.reindex(A.index).ffill().values], "nakit": [round(float(x), 2) for x in N]}, rf

def hazirlik_hesapla(oos, seri, canli, oz):
    """Gerçek paraya geçiş için kural tabanlı kapı. Eşikler yazarın seçimidir, değiştirilebilir; hepsi geçse bile yeterli değildir."""
    ra = (oos.get("risk") or {}).get("algo") or {}; nk = oos.get("nakit_getiri")
    nl = len(oos.get("liste", [])); yn = oos.get("yenen_sayisi", 0); gc = len(seri)
    cg = (seri[-1]["deger"] / seri[0]["deger"] - 1.0) * 100.0 if gc > 1 else 0.0
    cn = (canli["ppf"][-1] / canli["ppf"][0] - 1.0) * 100.0 if canli.get("ppf") and len(canli["ppf"]) > 1 else 0.0
    dd = ra.get("max_dd"); sh = ra.get("sharpe"); kp = oz.get("kapanan", 0) or 0
    k = [("Out-of-sample süresi", f"{oos.get('gun', 0)} gün", "≥ 500 gün", oos.get("gun", 0) >= 500),
         ("OOS getiri nakdi geçiyor", f"%{ra.get('getiri')} vs %{nk}", "algoritma > nakit", bool(ra) and nk is not None and ra.get("getiri", -1e9) > nk),
         ("OOS Sharpe (nakit üzeri)", str(sh), "≥ 0,5", sh is not None and sh >= 0.5),
         ("OOS max drawdown", f"%{dd}", "≤ %20", dd is not None and dd <= 20),
         ("OOS'ta Al-Bekle'yi yenen varlık oranı", f"{yn}/{nl}", "≥ %55", nl > 0 and yn / nl >= 0.55),
         ("Canlı (ileriye dönük) kayıt süresi", f"{gc} gün", "≥ 120 gün", gc >= 120),
         ("Canlı kayıt nakdi geçiyor", f"%{cg:.1f} vs %{cn:.1f}", "120+ günde algoritma > nakit", gc >= 120 and cg > cn),
         ("Canlı kapanan işlem sayısı", str(kp), "≥ 30", kp >= 30)]
    return {"gecen": sum(1 for x in k if x[3]), "toplam": len(k), "kriterler": [{"ad": a, "deger": d, "esik": e, "ok": bool(o)} for a, d, e, o in k]}

def konsantre(algo, poz, tavan, rf):
    """Aynı sinyallerle sermayeyi yalnızca pozisyondaki varlıklara eşit paylaştırır (varlık başına en fazla `tavan`); kalanı nakitte tutar."""
    R = pd.concat([s / s.shift(1).fillna(100.0) - 1.0 for s in algo], axis=1)
    Pv = np.nan_to_num(pd.concat(poz, axis=1).reindex(R.index).values); Rv = R.values
    onceki = np.vstack([np.zeros((1, Pv.shape[1])), Pv[:-1]])
    aktif = ((Pv == 1) | (onceki == 1)) & ~np.isnan(Rv); c = 100.0; cikti = []
    for t in range(len(Rv)):
        n = int(aktif[t].sum())
        if n:
            w = min(tavan, 1.0 / n); gelir = w * float(Rv[t][aktif[t]].sum()) + (1.0 - n * w) * rf[t]
        else:
            gelir = rf[t]
        c *= 1.0 + gelir; cikti.append(c)
    return cikti

def egri_paketi(a, b):
    if not a: return {"tarihler": [], "algo": [], "bist": []}
    A = pd.concat(a, axis=1).ffill().bfill().mean(axis=1); B = pd.concat(b, axis=1).ffill().bfill().mean(axis=1)
    return {"tarihler": [d.strftime("%d.%m.%Y") for d in A.index], "algo": [round(float(x), 2) for x in A.values], "bist": [round(float(x), 2) for x in B.values]}

def ozet(liste):
    if not liste: return {"yenen_sayisi": 0, "bist_ort": 0.0, "algo_ort": 0.0, "liste": []}
    liste.sort(key=lambda x: x["algo"] - x["bh"], reverse=True)
    return {"yenen_sayisi": sum(1 for x in liste if x["yendi"]), "bist_ort": round(float(np.median([x["bh"] for x in liste])), 1),
            "algo_ort": round(float(np.median([x["algo"] for x in liste])), 1), "liste": liste}

toplam = len(site_verileri)
aktif = sum(1 for kz in kasalar.values() if kz["adet"] > 0)
nakit_deger = sum(kz["nakit"] for kz in kasalar.values())
seri = gecmis["deger_serisi"]
oos = ozet(perf_oos); oos["grafik"], oos_rf = oos_paketi(oos_algo_egrileri, oos_bh_egrileri); oos["gun"] = len(oos["grafik"]["algo"])
oos["risk"] = {"algo": risk(oos["grafik"]["algo"], oos_rf), "bist": risk(oos["grafik"]["bist"], oos_rf)}
oos["nakit_getiri"] = round(oos["grafik"]["nakit"][-1] - 100.0, 1) if oos["gun"] else None
oos["gram_getiri"] = None
if GRAM_KAPANIS is not None and oos["gun"]:   # aynı dönemde gram altın Al-Bekle (altın rallisi mi, algoritma mı ayırt etmek için)
    gk = GRAM_KAPANIS.reindex(_gun(pd.to_datetime(oos["grafik"]["tarihler"], format="%d.%m.%Y")), method="ffill")
    oos["gram_getiri"] = round(float(gk.iloc[-1] / gk.iloc[0] - 1.0) * 100.0, 1)
oos["konsantre"] = {}
rf_bos = oos_rf   # boştaki payın getirisi: nakit (PPF) ya da altın varyantında gram altın
if NAKIT_VARLIK == "altin" and GRAM_GETIRI is not None and oos["gun"]:
    gg = GRAM_GETIRI.reindex(_gun(pd.to_datetime(oos["grafik"]["tarihler"], format="%d.%m.%Y"))).values; rf_bos = np.where(np.isnan(gg), oos_rf, gg)
if oos_algo_egrileri and len(oos_poz) == len(oos_algo_egrileri):   # risk artırma analizi: aynı sinyaller, daha yoğun pozisyon
    for ad_k, tv in (("taban 1/N (mevcut)", 1.0 / len(oos_algo_egrileri)), ("tavan %10", 0.10), ("tavan %20", 0.20)):
        oos["konsantre"][ad_k] = risk(konsantre(oos_algo_egrileri, oos_poz, tv, rf_bos), oos_rf)

tarihler_c = [x["tarih"] for x in seri]; bas = gecmis["kitap"]["baslangic"]
try: xu = sayi(toplu_veri["XU100.IS"]['Close'])
except Exception: xu = None
canli_paket = {"tarihler": tarihler_c, "deger": [x["deger"] for x in seri], "bist100": hizala(xu, tarihler_c, bas), "gram_altin": hizala(gram_close, tarihler_c, bas),
               "ppf": [round(BASLANGIC_SERMAYE * (1.0 + PPF_GUNLUK_GETIRI) ** i, 2) for i in range(len(seri))]}
son_giris = {o["hisse"]: o["tarih"] for o in gecmis["olaylar"] if o["islem"] == "Trend Girişi"}
pozisyonlar = sorted([{"hisse": h, "giris_tarih": son_giris.get(h, "-"), "giris_fiyat": round(kz["giris_fiyat"], 2), "fiyat": round(kz["son_fiyat"], 2),
                       "kz": round((kz["son_fiyat"] / kz["giris_fiyat"] - 1.0) * 100.0, 1), "stop": round(stop_map.get(h, 0.0), 2),
                       "stop_mesafe": round((kz["son_fiyat"] - stop_map[h]) / kz["son_fiyat"] * 100.0, 1) if stop_map.get(h, 0) > 0 else None}
                      for h, kz in kasalar.items() if kz["adet"] > 0 and kz["giris_fiyat"]], key=lambda x: -x["kz"])
kapanan = [o["getiri"] for o in gecmis["olaylar"] if o["islem"] != "Trend Girişi" and o.get("getiri") is not None]
islem_ozeti = {"kapanan": len(kapanan), "kazanma_orani": round(100.0 * sum(1 for g in kapanan if g > 0) / len(kapanan), 1) if kapanan else None,
               "ort_getiri": round(float(np.mean(kapanan)), 1) if kapanan else None}

veri_paketi = {
    "guncellenme_tarihi": (datetime.utcnow() + timedelta(hours=3)).strftime("%d.%m.%Y %H:%M"),
    "portfoy": {"baslangic_tarihi": tr_tarih(gecmis["kitap"]["baslangic"]), "baslangic_sermaye": round(BASLANGIC_SERMAYE, 2),
                "guncel_bakiye": round(guncel, 2), "net_kar_tl": round(guncel - BASLANGIC_SERMAYE, 2),
                "net_kar_yuzde": round((guncel / BASLANGIC_SERMAYE - 1.0) * 100.0, 2), "aktif_pozisyon": aktif,
                "toplam_varlik": toplam, "ppf_nakit_orani": round(nakit_deger / max(1e-8, guncel) * 100.0, 1)},
    "canli": canli_paket, "pozisyonlar": pozisyonlar, "islem_ozeti": islem_ozeti,
    "islem_gecmisi": gecmis["olaylar"][-60:][::-1],
    "performans": {"toplam_varlik": toplam, "alti_ay": ozet(perf6), "iki_yil": ozet(perf2), "oos": oos,
                   "grafik": egri_paketi(is_egrileri, bh_egrileri)},
    "sinyaller": site_verileri}
durum_sayilari = {etiket: sum(1 for d in site_verileri if d.get("sinyal") == etiket) for etiket in ("AL", "TUT", "SAT", "İZLE")}
engel_sayilari = {}
for d in site_verileri:
    if d.get("sinyal") == "İZLE":
        for neden in d.get("giris_engelleri", []): engel_sayilari[neden] = engel_sayilari.get(neden, 0) + 1
veri_paketi["sinyal_ozeti"] = {"durumlar": durum_sayilari, "giris_engelleri": dict(sorted(engel_sayilari.items(), key=lambda x: -x[1])[:5])}
veri_paketi["portfoy"]["saglik"] = saglik_hesapla(seri, kasalar)
veri_paketi["hazirlik"] = hazirlik_hesapla(oos, seri, canli_paket, islem_ozeti)
with open(os.environ.get("SIGNALS_DOSYASI", "signals.json"), "w", encoding="utf-8") as f:
    json.dump(veri_paketi, f, ensure_ascii=False, indent=4)
print(f"✅ {toplam} varlık analiz edildi | Backtest (in-sample) yenen: {veri_paketi['performans']['iki_yil']['yenen_sayisi']} | Out-of-sample yenen: {oos['yenen_sayisi']}/{len(perf_oos)}")
ra, rb = oos["risk"]["algo"] or {}, oos["risk"]["bist"] or {}
print(f"DENEY | {os.environ.get('DENEY_ADI', 'varsayilan')} | OOS gün {oos['gun']} | algo %{ra.get('getiri')} | nakit %{oos['nakit_getiri']} | evren %{rb.get('getiri')} | Sharpe {ra.get('sharpe')} | maxDD %{ra.get('max_dd')} | yenen {oos['yenen_sayisi']}/{len(perf_oos)} | piyasada kalma %{round(100 * float(np.mean(oos_maruz)), 1) if oos_maruz else '-'}")
if oos_islem:
    ti, tk, tn = (sum(x[j] for x in oos_islem) for j in range(3))
    print(f"DENEY+ | {os.environ.get('DENEY_ADI', 'varsayilan')} | OOS hisse {len(oos_islem)} | işlem/hisse/yıl {ti / (tn / 252):.1f} | işlem kazanma %{100 * tk / max(1, ti):.0f}")
_ad = os.environ.get('DENEY_ADI', 'varsayilan')
if oos.get("gram_getiri") is not None: print(f"DENEY++ | {_ad} | gram altın Al-Bekle %{oos['gram_getiri']} (aynı dönem)")
for _k, _v in (oos.get("konsantre") or {}).items():
    if _v: print(f"DENEY++ | {_ad} | pozisyon yoğunlaştırma {_k} | algo %{_v.get('getiri')} | Sharpe {_v.get('sharpe')} | maxDD %{_v.get('max_dd')}")
