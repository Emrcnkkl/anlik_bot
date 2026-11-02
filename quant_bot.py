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
WF_TEST = 63      # walk-forward: seçilen stratejinin görmeden uygulandığı dönem
HISTORY_DOSYASI = "history.json"

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

def backtest_gelismis_motor(fiyatlar, acilislar, durumlar, kalkanlar, atrler, adxler, baz_stoplar, adx_esik, atr_carpan, cikis_modu):
    """Karar gün sonu kapanışıyla verilir, emir ERTESİ GÜN AÇILIŞINDA işlenir (aynı bar look-ahead yok).
    cikis_modu 0: indikatör SAT veya ATR iz süren stop; 1: yalnızca ATR stop veya kalkan kırılımı."""
    n = len(fiyatlar)
    nakit, adet, zirve, giris_bakiye, emir = 100.0, 0.0, 0.0, 0.0, 0   # emir: 1 AL, -1 SAT (sonraki açılışta)
    kazanan = toplam = 0
    bakiye = np.full(n, 100.0); poz = np.zeros(n, dtype=int); stoplar = np.zeros(n)
    for i in range(n):
        ac = acilislar[i]
        if emir == 1 and adet == 0.0:
            giris_bakiye, adet, nakit, zirve = nakit, nakit * (1.0 - KOMISYON) / ac, 0.0, ac
        elif emir == -1 and adet > 0.0:
            nakit, adet = adet * ac * (1.0 - KOMISYON), 0.0
            toplam += 1; kazanan += int(nakit > giris_bakiye)
        emir = 0
        fiyat, kalkan, atr = fiyatlar[i], kalkanlar[i], atrler[i]
        if np.isnan(kalkan) or np.isnan(atr):
            bakiye[i] = nakit if adet == 0.0 else adet * fiyat
            poz[i] = int(adet > 0); continue
        if adet == 0.0:
            nakit *= (1.0 + PPF_GUNLUK_GETIRI)
            if durumlar[i] == 1 and fiyat > kalkan and adxler[i] >= adx_esik:
                emir = 1
            stoplar[i] = kalkan
        else:
            zirve = max(zirve, fiyat)
            atr_stop = zirve - atr_carpan * atr
            stoplar[i] = max(kalkan * 0.98, atr_stop, baz_stoplar[i] if baz_stoplar[i] < fiyat else atr_stop)
            cik = (durumlar[i] == -1 or fiyat < atr_stop) if cikis_modu == 0 else (fiyat < atr_stop or fiyat < kalkan)
            if cik:
                emir = -1
        poz[i] = int(adet > 0)
        bakiye[i] = nakit if adet == 0.0 else adet * fiyat
    son_deger = nakit if adet == 0.0 else adet * fiyatlar[-1] * (1.0 - KOMISYON)
    if adet > 0.0:
        toplam += 1; kazanan += int(son_deger > giris_bakiye)
    zirveler = np.maximum.accumulate(bakiye)
    max_dd = float(np.max((zirveler - bakiye) / np.maximum(zirveler, 1e-8)) * 100.0)
    return {"net_getiri": son_deger - 100.0, "max_dd": max_dd, "win_rate": (kazanan / toplam * 100.0) if toplam else 0.0,
            "bakiye_serisi": bakiye, "pozisyon_serisi": poz, "stop_serisi": stoplar,
            "hedef": int((adet > 0.0 and emir != -1) or emir == 1)}   # yarın açılışta hedef pozisyon

macd_ayarlari = [(8, 21), (12, 26), (5, 35), (24, 52)]
st_ayarlari = [(10, 2.0), (10, 3.0), (14, 2.5), (20, 2.0)]
ema_ayarlari = [(5, 13), (9, 21), (13, 34), (21, 50)]
donchian_ayarlari = [14, 20, 34]
# (Kalkan, ADX_Eşik, ATR_Stop_Çarpanı, Çıkış_Modu)
rejim_kombinasyonlari = [("EMA200", 18.0, 3.0, 0), ("EMA200", 22.0, 2.5, 0), ("EMA200", 14.0, 4.2, 1), ("EMA100", 16.0, 3.5, 1)]

def calistir(ad, rej, k, s, e, fiy, acl, atr, adx):
    return backtest_gelismis_motor(fiy[s:e], acl[s:e], ad[2][s:e], k[rej[0]][s:e], atr[s:e], adx[s:e], ad[3][s:e], rej[1], rej[2], rej[3])

def en_iyi_strateji(adaylar, k, s, e, fiy, acl, atr, adx):
    """[s:e) aralığında Alfa + risk-ayarlı skora göre şampiyonu seçer."""
    bh = (fiy[e - 1] - fiy[s]) / max(1e-8, fiy[s]) * 100.0
    en_iyi, secim = -1e18, None
    for ad in adaylar:
        for rej in rejim_kombinasyonlari:
            sn = calistir(ad, rej, k, s, e, fiy, acl, atr, adx)
            skor = (5000.0 if sn["net_getiri"] - bh > 0 else 0.0) + sn["net_getiri"] - 0.45 * sn["max_dd"]
            if skor > en_iyi:
                en_iyi, secim = skor, (ad, rej, sn)
    return secim

def walk_forward(adaylar, k, fiy, acl, atr, adx):
    """Her WF_TEST günde, yalnızca önceki WF_EGITIM günle seçilen strateji sonraki döneme görmeden uygulanır."""
    n = len(fiy); katsayi = 1.0; egri = []
    s = WF_EGITIM
    while s < n:
        e = min(s + WF_TEST, n)
        ad, rej, _ = en_iyi_strateji(adaylar, k, s - WF_EGITIM, s, fiy, acl, atr, adx)
        seg = calistir(ad, rej, k, s, e, fiy, acl, atr, adx)["bakiye_serisi"] / 100.0 * katsayi
        egri.extend(seg.tolist()); katsayi = float(seg[-1]); s = e
    return np.array(egri)   # uzunluk n - WF_EGITIM, 1.0 = test başlangıcı

AYLAR = ["Ocak", "Şubat", "Mart", "Nisan", "Mayıs", "Haziran", "Temmuz", "Ağustos", "Eylül", "Ekim", "Kasım", "Aralık"]
def tr_tarih(iso):
    y, m, d = iso.split("-"); return f"{int(d)} {AYLAR[int(m) - 1]} {y}"

def gecmis_yukle():
    try:
        with open(HISTORY_DOSYASI, encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}

def canli_kitabi_guncelle(gecmis, hedefler, veriler):
    """İLERİYE DÖNÜK, DONDURULMUŞ kayıt: dünkü karar bugünün açılışında işlenir, geçmiş günler asla yeniden hesaplanmaz."""
    kitap = gecmis.setdefault("kitap", {}); kasalar = kitap.setdefault("kasalar", {}); olaylar = gecmis.setdefault("olaylar", [])
    ilk = not kasalar; bekleyen = kitap.get("bekleyen", {}); pay = BASLANGIC_SERMAYE / max(1, len(veriler))
    for h, v in veriler.items():
        if not ilk and h not in kasalar:
            continue
        k = kasalar.setdefault(h, {"nakit": pay, "adet": 0.0, "son_tarih": None, "giris_fiyat": None, "son_fiyat": v["kapanis"]})
        if k["son_tarih"] is None:
            k["son_tarih"] = v["tarih"]
        elif v["tarih"] > k["son_tarih"]:
            if bekleyen.get(h, 0) == 1 and k["adet"] == 0.0:
                k["adet"] = k["nakit"] * (1.0 - KOMISYON) / v["acilis"]; k["nakit"] = 0.0; k["giris_fiyat"] = v["acilis"]
                olaylar.append({"tarih": v["tarih"], "hisse": h, "islem": "Trend Girişi", "fiyat": round(v["acilis"], 2), "getiri": None, "strateji": v["strateji"]})
            elif bekleyen.get(h, 0) == 0 and k["adet"] > 0.0:
                k["nakit"] = k["adet"] * v["acilis"] * (1.0 - KOMISYON)
                g = round((v["acilis"] / k["giris_fiyat"] - 1.0) * 100.0, 1) if k["giris_fiyat"] else None
                k["adet"] = 0.0
                olaylar.append({"tarih": v["tarih"], "hisse": h, "islem": "Trend Çıkışı", "fiyat": round(v["acilis"], 2), "getiri": g, "strateji": v["strateji"]})
            if k["adet"] == 0.0:
                k["nakit"] *= (1.0 + PPF_GUNLUK_GETIRI) ** max(1, v["yeni_bar"])
            k["son_tarih"] = v["tarih"]
        k["son_fiyat"] = v["kapanis"]
    kitap["bekleyen"] = {h: int(x) for h, x in hedefler.items()}
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
normal_hisseler = [h for h in bist100 if h != "GRAM_ALTIN"]
toplu_veri = yf.download(normal_hisseler + ["GC=F", "TRY=X"], period="3y", interval="1d", group_by='ticker', progress=False, threads=True)

site_verileri, canli_veriler, hedefler = [], {}, {}
is_egrileri, bh_egrileri, oos_algo_egrileri, oos_bh_egrileri = [], [], [], []
perf2, perf6, perf_oos = [], [], []

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
        if len(df) < 250:
            continue

        df = hesapla_temel_metrikler(df)
        test = df.tail(500).copy(); n = len(test)
        fiy, acl, atr, adx = test['Close'].values, test['Open'].values, test['ATR'].values, test['ADX'].values
        k = {"EMA200": test['EMA200'].values, "EMA100": test['EMA100'].values}
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

        ad, rej, sonuc = en_iyi_strateji(adaylar, k, 0, n, fiy, acl, atr, adx)   # güncel şampiyon (in-sample)
        strateji = f"{ad[0]} ({ad[1]} • {'Trend' if rej[3] == 1 else 'ADX'})"
        bakiye = sonuc["bakiye_serisi"]; temiz = hisse.replace(".IS", "")
        hedefler[temiz] = sonuc["hedef"]

        algo_2yil, bh_r = round(sonuc["net_getiri"], 1), round(bh_2yil, 1)
        g6 = min(126, n - 1)
        bh_6 = round((fiy[-1] - fiy[-g6]) / max(1e-8, fiy[-g6]) * 100.0, 1)
        algo_6 = round((bakiye[-1] - bakiye[-g6]) / max(1e-8, bakiye[-g6]) * 100.0, 1)
        st = float(sonuc["stop_serisi"][-1])

        tarih_iso = test.index.strftime("%Y-%m-%d")
        canli_veriler[temiz] = {"acilis": float(acl[-1]), "kapanis": float(fiy[-1]), "tarih": tarih_iso[-1], "strateji": strateji,
                                "yeni_bar": int((tarih_iso > (kitap_son.get(temiz) or "9999")).sum()) if kitap_son.get(temiz) else 1}
        site_verileri.append({
            "hisse": temiz, "sinyal": "İZLE", "fiyat": round(float(fiy[-1]), 2), "ema200": round(float(k["EMA200"][-1]), 2),
            "adx": round(float(adx[-1]), 1), "max_dd": round(sonuc["max_dd"], 1), "win_rate": round(sonuc["win_rate"], 1),
            "strateji": strateji, "stop": f"{round(st, 2)} ₺" if st > 0 else "Trend Çıkışı", "getiri": algo_2yil, "bh_getiri": bh_r,
            "alfa": round(algo_2yil - bh_r, 1), "gecmis": [round(float(x), 2) for x in fiy[-30:]], "tarihler": [d.strftime("%d.%m") for d in test.index[-30:]]})
        perf2.append({"hisse": temiz, "bh": bh_r, "algo": algo_2yil, "yendi": bool(algo_2yil > bh_r)})
        perf6.append({"hisse": temiz, "bh": bh_6, "algo": algo_6, "yendi": bool(algo_6 > bh_6)})
        is_egrileri.append(pd.Series(bakiye, index=test.index)); bh_egrileri.append(pd.Series(fiy / fiy[0] * 100.0, index=test.index))

        if n >= WF_EGITIM + 20:   # OUT-OF-SAMPLE (walk-forward)
            egri = walk_forward(adaylar, k, fiy, acl, atr, adx)
            idx = test.index[WF_EGITIM:]; bh_c = fiy[WF_EGITIM:] / fiy[WF_EGITIM - 1]
            oa, ob = round((egri[-1] - 1.0) * 100.0, 1), round((bh_c[-1] - 1.0) * 100.0, 1)
            perf_oos.append({"hisse": temiz, "bh": ob, "algo": oa, "yendi": bool(oa > ob)})
            oos_algo_egrileri.append(pd.Series(egri * 100.0, index=idx)); oos_bh_egrileri.append(pd.Series(bh_c * 100.0, index=idx))
    except Exception as e:
        print(f"⚠️ {hisse} hesaplanırken hata: {e}")

# İLERİYE DÖNÜK (dondurulmuş) model portföy
kasalar, guncel = canli_kitabi_guncelle(gecmis, hedefler, canli_veriler)
for d in site_verileri:
    kz = kasalar.get(d["hisse"]); poz = bool(kz and kz["adet"] > 0); hdf = hedefler.get(d["hisse"], 0)
    d["sinyal"] = "TUT" if poz and hdf else "SAT" if poz else "AL" if hdf else "İZLE"
with open(HISTORY_DOSYASI, "w", encoding="utf-8") as f:
    json.dump(gecmis, f, ensure_ascii=False, indent=1)

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
oos = ozet(perf_oos); oos["gun"] = max(0, 500 - WF_EGITIM); oos["grafik"] = egri_paketi(oos_algo_egrileri, oos_bh_egrileri)

veri_paketi = {
    "guncellenme_tarihi": (datetime.utcnow() + timedelta(hours=3)).strftime("%d.%m.%Y %H:%M"),
    "portfoy": {"baslangic_tarihi": tr_tarih(gecmis["kitap"]["baslangic"]), "baslangic_sermaye": round(BASLANGIC_SERMAYE, 2),
                "guncel_bakiye": round(guncel, 2), "net_kar_tl": round(guncel - BASLANGIC_SERMAYE, 2),
                "net_kar_yuzde": round((guncel / BASLANGIC_SERMAYE - 1.0) * 100.0, 2), "aktif_pozisyon": aktif,
                "toplam_varlik": toplam, "ppf_nakit_orani": round(nakit_deger / max(1e-8, guncel) * 100.0, 1)},
    "canli": {"tarihler": [x["tarih"] for x in seri], "deger": [x["deger"] for x in seri]},
    "islem_gecmisi": gecmis["olaylar"][-60:][::-1],
    "performans": {"toplam_varlik": toplam, "alti_ay": ozet(perf6), "iki_yil": ozet(perf2), "oos": oos,
                   "grafik": egri_paketi(is_egrileri, bh_egrileri)},
    "sinyaller": site_verileri}
with open("signals.json", "w", encoding="utf-8") as f:
    json.dump(veri_paketi, f, ensure_ascii=False, indent=4)
print(f"✅ {toplam} varlık analiz edildi | Backtest (in-sample) yenen: {veri_paketi['performans']['iki_yil']['yenen_sayisi']} | Out-of-sample yenen: {oos['yenen_sayisi']}/{len(perf_oos)}")
