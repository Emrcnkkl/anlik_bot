import yfinance as yf
import pandas as pd
import numpy as np
import time

BIST30 = [
    "AKBNK.IS", "ALARK.IS", "ASELS.IS", "ASTOR.IS", "BIMAS.IS",
    "BRSAN.IS", "CIMSA.IS", "CWENE.IS", "DOAS.IS", "EKGYO.IS",
    "ENKAI.IS", "EREGL.IS", "EUPWR.IS", "FROTO.IS", "GARAN.IS",
    "GUBRF.IS", "HEKTS.IS", "ISCTR.IS", "KCHOL.IS", "KONTR.IS",
    "KRDMD.IS", "PGSUS.IS", "SAHOL.IS", "SASA.IS", "SISE.IS",
    "TCELL.IS", "THYAO.IS", "TUPRS.IS", "YKBNK.IS"
]

def hesapla_supertrend(df, period=10, multiplier=3):
    hl2 = (df['High'] + df['Low']) / 2
    tr1 = df['High'] - df['Low']
    tr2 = (df['High'] - df['Close'].shift(1)).abs()
    tr3 = (df['Low'] - df['Close'].shift(1)).abs()
    tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
    atr = tr.rolling(period).mean()
    
    upperband = hl2 + (multiplier * atr)
    lowerband = hl2 - (multiplier * atr)
    
    in_uptrend = np.full(len(df), True)
    
    # HATANIN ÇÖZÜLDÜĞÜ YER: .copy() eklendi
    ub = upperband.values.copy()
    lb = lowerband.values.copy()
    close = df['Close'].values.copy()
    
    for i in range(period, len(df)):
        if lb[i] < lb[i-1] and close[i-1] > lb[i-1]:
            lb[i] = lb[i-1]
        if ub[i] > ub[i-1] and close[i-1] < ub[i-1]:
            ub[i] = ub[i-1]
            
        if close[i-1] <= ub[i-1] and close[i] > ub[i]:
            in_uptrend[i] = True
        elif close[i-1] >= lb[i-1] and close[i] < lb[i]:
            in_uptrend[i] = False
        else:
            in_uptrend[i] = in_uptrend[i-1]
            
    df['In_Uptrend'] = in_uptrend
    return df

print("⏳ SUPERTREND KESKİN NİŞANCI BACKTESTİ (Günlük - Son 2 Yıllık Aktif İşlem)...")
print("-" * 75)
print(f"{'HİSSE':<12} | {'İŞLEM SAYISI':<15} | {'BAŞARI ORANI':<15} | {'AL & BEKLE':<12} | {'ALGORİTMA GETİRİSİ'}")
print("-" * 75)

toplam_algo = 0
toplam_bh = 0
gecerli_hisse = 0
basarili_hisse = 0

for hisse in BIST30:
    try:
        time.sleep(0.5)
        df = yf.download(hisse, period="3y", interval="1d", progress=False)
        
        if df.empty:
            continue
        if len(df) < 250:
            continue
            
        if isinstance(df.columns, pd.MultiIndex):
            df.columns = df.columns.get_level_values(0)

        df['Close'] = pd.to_numeric(df['Close'].squeeze())
        df['High'] = pd.to_numeric(df['High'].squeeze())
        df['Low'] = pd.to_numeric(df['Low'].squeeze())

        df.dropna(subset=['Close', 'High', 'Low'], inplace=True)
        
        df = hesapla_supertrend(df, period=10, multiplier=3)
        df['EMA200'] = df['Close'].ewm(span=200, adjust=False).mean()
        
        df['ST_Sinyal_AL'] = (df['In_Uptrend'] == True) & (df['In_Uptrend'].shift(1) == False)
        df['ST_Sinyal_SAT'] = (df['In_Uptrend'] == False) & (df['In_Uptrend'].shift(1) == True)

        df.dropna(inplace=True)

        in_position = False
        entry_price = 0
        trades = []
        algo_bakiye = 100.0
        
        for index, row in df.iterrows():
            if row['ST_Sinyal_AL'] and (row['Close'] > row['EMA200']):
                if not in_position:
                    in_position = True
                    entry_price = row['Close']
            
            elif row['ST_Sinyal_SAT']:
                if in_position:
                    in_position = False
                    exit_price = row['Close']
                    profit_pct = (exit_price - entry_price) / entry_price
                    trades.append(profit_pct)
                    algo_bakiye *= (1 + profit_pct)

        if in_position:
            exit_price = df['Close'].iloc[-1]
            profit_pct = (exit_price - entry_price) / entry_price
            trades.append(profit_pct)
            algo_bakiye *= (1 + profit_pct)

        total_trades = len(trades)
        win_rate = (sum(1 for t in trades if t > 0) / total_trades * 100) if total_trades > 0 else 0
        
        algo_net = algo_bakiye - 100.0
        ilk_fiyat = df['Close'].iloc[0]
        son_fiyat = df['Close'].iloc[-1]
        bh_net = ((son_fiyat - ilk_fiyat) / ilk_fiyat) * 100

        toplam_algo += algo_net
        toplam_bh += bh_net
        gecerli_hisse += 1
        if algo_net > bh_net:
            basarili_hisse += 1

        hisse_adi = hisse.replace('.IS', '')
        print(f"{hisse_adi:<12} | {total_trades:<15} | %{win_rate:<14.1f} | %{bh_net:<11.1f} | %{algo_net:.1f}")

    except Exception as e:
        print(f"{hisse} Hata: {e}")

print("-" * 75)
if gecerli_hisse > 0:
    print(f"BİST30 AL-BEKLE ORTALAMASI  : %{(toplam_bh / gecerli_hisse):.2f}")
    print(f"ALGORİTMA (GÜNLÜK) ORTALAMASI: %{(toplam_algo / gecerli_hisse):.2f}")
    print(f"ALGORİTMANIN YENDİĞİ HİSSE  : {basarili_hisse} / {gecerli_hisse}")
