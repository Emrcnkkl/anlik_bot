import yfinance as yf
import pandas as pd
import numpy as np
import warnings
import json
from datetime import datetime, timedelta

warnings.filterwarnings('ignore')

bist30 = [
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
    temp_df['MACD_Durum'] = np.where(macd_line > signal_line, 1, -1)
    temp_df['Sinyal'] = temp_df['MACD_Durum'].diff() / 2
    return temp_df

def hesapla_supertrend(df, period, multiplier):
    temp_df = df.copy()
    temp_df['High-Low'] = temp_df['High'] - temp_df['Low']
    temp_df['High-PrevClose'] = np.abs(temp_df['High'] - temp_df['Close'].shift(1))
    temp_df['Low-PrevClose'] = np.abs(temp_df['Low'] - temp_df['Close'].shift(1))
    temp_df['TR'] = temp_df[['High-Low', 'High-PrevClose', 'Low-PrevClose']].max(axis=1)
    temp_df['ATR'] = temp_df['TR'].rolling(period).mean()

    hl2 = (temp_df['High'] + temp_df['Low']) / 2
    temp_df['Basic_UB'] = hl2 + (multiplier * temp_df['ATR'])
    temp_df['Basic_LB'] = hl2 - (multiplier * temp_df['ATR'])
    
    final_ub = [temp_df['Basic_UB'].iloc[0] if not pd.isna(temp_df['Basic_UB'].iloc[0]) else 0.0]
    final_lb = [temp_df['Basic_LB'].iloc[0] if not pd.isna(temp_df['Basic_LB'].iloc[0]) else 0.0]
    supertrend = [0.0]; trend = [1]

    ub = temp_df['Basic_UB'].values
    lb = temp_df['Basic_LB'].values
    close = temp_df['Close'].values

    for i in range(1, len(temp_df)):
        if pd.isna(ub[i]):
            final_ub.append(final_ub[i-1]); final_lb.append(final_lb[i-1]); trend.append(1); supertrend.append(0.0)
            continue
        if ub[i] < final_ub[i-1] or close[i-1] > final_ub[i-1]:
            final_ub.append(ub[i])
        else: final_ub.append(final_ub[i-1])
            
        if lb[i] > final_lb[i-1] or close[i-1] < final_lb[i-1]:
            final_lb.append(lb[i])
        else: final_lb.append(final_lb[i-1])
            
        if supertrend[i-1] == final_ub[i-1] and close[i] <= final_ub[i]:
            trend.append(-1); supertrend.append(final_ub[i])
        elif supertrend[i-1] == final_ub[i-1] and close[i] > final_ub[i]:
            trend.append(1); supertrend.append(final_lb[i])
        elif supertrend[i-1] == final_lb[i-1] and close[i] >= final_lb[i]:
            trend.append(1); supertrend.append(final_lb[i])
        elif supertrend[i-1] == final_lb[i-1] and close[i] < final_lb[i]:
            trend.append(-1); supertrend.append(final_ub[i])
        else:
            trend.append(trend[i-1]); supertrend.append(supertrend[i-1])

    temp_df['ST_Trend'] = trend
    temp_df['Sinyal'] = temp_df['ST_Trend'].diff() / 2
    return temp_df

def hesapla_ema_cross(df, kisa, uzun):
    temp_df = df.copy()
    ema_kisa = temp_df['Close'].ewm(span=kisa, adjust=False).mean()
    ema_uzun = temp_df['Close'].ewm(span=uzun, adjust=False).mean()
    temp_df['Trend_Durum'] = np.where(ema_kisa > ema_uzun, 1, -1)
    temp_df['Sinyal'] = temp_df['Trend_Durum'].diff() / 2
    return temp_df

def backtest_saf_trend(df):
    baslangic = 100.0; nakit = baslangic; hisse_adedi = 0.0; komisyon = 0.002
    giris_fiyati = 0.0; PPF_GUNLUK_GETIRI = 0.0011 
    
    for _, satir in df.iterrows():
        fiyat = satir['Close']
        sinyal = satir['Sinyal']
        ema200 = satir['EMA200']
        
        if pd.isna(sinyal) or pd.isna(ema200): continue
        if nakit > 0: nakit *= (1 + PPF_GUNLUK_GETIRI)
            
        if sinyal == 1 and nakit > 0 and fiyat > ema200:
            giris_fiyati = fiyat
            hisse_adedi = (nakit - (nakit * komisyon)) / fiyat
            nakit = 0.0
            
        elif sinyal == -1 and hisse_adedi > 0:
            satis_tutari = hisse_adedi * fiyat
            nakit = satis_tutari - (satis_tutari * komisyon)
            hisse_adedi = 0.0
            
    if hisse_adedi > 0:
        son_fiyat = df['Close'].iloc[-1]
        nakit = (hisse_adedi * son_fiyat) - (hisse_adedi * son_fiyat * komisyon)
        
    return ((nakit - baslangic) / baslangic) * 100

site_verileri = []
macd_ayarlari = [(8, 21), (12, 26), (24, 52)]
st_ayarlari = [(10, 3.0), (14, 2.0), (20, 2.0)]
ema_ayarlari = [(9, 21), (13, 34), (21, 50)]

print("⏳ Web Sitesi İçin Güncel Sinyaller Hesaplanıyor...")

for hisse in bist30:
    try:
        df = yf.download(hisse, period="3y", interval="1d", progress=False)
        if len(df) < 250: continue
        
        if isinstance(df.columns, pd.MultiIndex): df.columns = df.columns.get_level_values(0)
        df['Close'] = pd.to_numeric(df['Close'].squeeze())
        df['High'] = pd.to_numeric(df.get('High', df['Close']).squeeze())
        df['Low'] = pd.to_numeric(df.get('Low', df['Close']).squeeze())
        df.dropna(subset=['Close'], inplace=True)
        
        df['EMA200'] = df['Close'].ewm(span=200, adjust=False).mean()
        test_verisi = df.tail(500).copy()
        
        en_iyi_skor = -999; en_iyi_isim = ""; en_iyi_param = ""; en_iyi_df = None
        
        for h, y in macd_ayarlari:
            t_df = hesapla_macd(test_verisi, h, y)
            skor = backtest_saf_trend(t_df)
            if skor > en_iyi_skor: 
                en_iyi_skor = skor; en_iyi_isim = "MACD"; en_iyi_param = f"H:{h}/Y:{y}"; en_iyi_df = t_df.copy()
        
        for p, c in st_ayarlari:
            t_df = hesapla_supertrend(test_verisi, p, c)
            skor = backtest_saf_trend(t_df)
            if skor > en_iyi_skor: 
                en_iyi_skor = skor; en_iyi_isim = "SuperTrend"; en_iyi_param = f"P:{p}/Ç:{c}"; en_iyi_df = t_df.copy()
                
        for kisa, uzun in ema_ayarlari:
            t_df = hesapla_ema_cross(test_verisi, kisa, uzun)
            skor = backtest_saf_trend(t_df)
            if skor > en_iyi_skor: 
                en_iyi_skor = skor; en_iyi_isim = "EMA Kesişim"; en_iyi_param = f"{kisa}/{uzun}"; en_iyi_df = t_df.copy()

        if en_iyi_df is not None:
            son_satir = en_iyi_df.iloc[-1]
            sinyal_kodu = son_satir['Sinyal']
            fiyat = son_satir['Close']
            ema200 = son_satir['EMA200']

            # Son sinyal AL olsa bile fiyat EMA200'ün altındaysa NÖTR kabul et
            if sinyal_kodu == 1 and fiyat > ema200:
                sinyal_yazi = "AL"
            elif sinyal_kodu == -1:
                sinyal_yazi = "SAT"
            else:
                sinyal_yazi = "TUT"

            site_verileri.append({
                "hisse": hisse.replace(".IS", ""),
                "sinyal": sinyal_yazi,
                "fiyat": round(fiyat, 2),
                "strateji": f"{en_iyi_isim} ({en_iyi_param})",
                "stop": "Trend Çıkışı", # Sabit stop kaldırıldığı için güncellendi
                "getiri": round(en_iyi_skor, 1)
            })
            
    except Exception as e:
        pass

veri_paketi = {
    "guncellenme_tarihi": (datetime.utcnow() + timedelta(hours=3)).strftime("%d.%m.%Y %H:%M"),
    "sinyaller": site_verileri
}


with open("signals.json", "w", encoding="utf-8") as f:
    json.dump(veri_paketi, f, ensure_ascii=False, indent=4)

print("✅ Kurumsal Fon Algoritması signals.json dosyasını güncelledi!")
