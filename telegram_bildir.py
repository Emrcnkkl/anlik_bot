"""QuantBIST Telegram bildirimi.  Kullanım: python telegram_bildir.py sabah | aksam | hata
Token ve sohbet kimliği YALNIZCA ortam değişkenlerinden okunur (GitHub Secrets):
TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID. Dosyaya yazma. Tanımlı değillerse mesaj yalnızca ekrana yazdırılır."""
import json, os, sys, urllib.parse, urllib.request
from datetime import datetime, timedelta

SITE = "https://emrcnkkl.github.io/anlik_bot/"
UYARI = "⚠️ Yatırım tavsiyesi değildir. Bunlar bir modelin simülasyon çıktısıdır, kişiye özel değildir."

def yukle(ad):
    try:
        with open(ad, encoding="utf-8") as f: return json.load(f)
    except Exception: return {}

def tl(x): return f"{x:,.0f}".replace(",", ".") + " ₺"
def liste(x): return ", ".join(x) if x else "yok"

def mesaj(mod):
    if mod == "hata":
        return "⚠️ QuantBIST: bot çalışması başarısız oldu. GitHub Actions kayıtlarına bak.\n" + SITE
    s, h = yukle("signals.json"), yukle("history.json")
    simdi = datetime.utcnow() + timedelta(hours=3); bugun = simdi.strftime("%Y-%m-%d")
    p, sig = s.get("portfoy", {}), s.get("sinyaller", [])
    son = (s.get("canli", {}).get("tarihler") or [""])[-1]
    giris = [d["hisse"] for d in sig if d.get("sinyal") == "AL"]; cikis = [d["hisse"] for d in sig if d.get("sinyal") == "SAT"]
    gen = sum(1 for d in sig if d.get("fiyat") and d.get("ema200") and d["fiyat"] > d["ema200"])
    sg = p.get("saglik", {})
    fon = (f"Model portföy (simülasyon): {tl(p['guncel_bakiye'])} (%{p['net_kar_yuzde']:+.2f}) · Açık pozisyon: {p.get('aktif_pozisyon', 0)}/{p.get('toplam_varlik', 0)}"
           f" · Kill-Switch: {sg.get('durum', '-')}") if p else "Model portföy verisi yok."
    fon += f"\nPiyasa genişliği: {gen}/{len(sig)} varlık EMA200 üzerinde"
    hz = s.get("hazirlik")
    if hz: fon += f"\nGerçek para hazırlık kriterleri: {hz['gecen']}/{hz['toplam']} (modelin kendi ölçütleri)"
    uyari = ""
    try:
        g = datetime.strptime(s.get("guncellenme_tarihi", ""), "%d.%m.%Y %H:%M")
        if simdi - g > timedelta(hours=40): uyari = f"\n⚠️ Veri bayat (son güncelleme {s['guncellenme_tarihi']}). Akşam çalışması başarısız olmuş olabilir."
    except Exception:
        uyari = "\n⚠️ signals.json okunamadı."
    if mod == "sabah":
        govde = [f"🌅 QuantBIST · Sabah bülteni · {simdi:%d.%m.%Y}", "",
                 "Dünkü kapanış kararına göre bugün açılışta modelde işlenecek emirler:",
                 f"• Trend Girişi: {liste(giris)}", f"• Trend Çıkışı: {liste(cikis)}", "", fon]
    else:
        islenen = [o for o in h.get("olaylar", []) if o.get("tarih") == son]
        satir = [f"• {o['islem']} · {o['hisse']} · {o['fiyat']} ₺" + (f" · %{o['getiri']:+.1f}" if o.get("getiri") is not None else "") for o in islenen]
        govde = [f"🌙 QuantBIST · Akşam raporu · {simdi:%d.%m.%Y}", ""]
        if son and son < bugun: govde += [f"ℹ️ Bugün yeni piyasa verisi yok (tatil olabilir). Son veri: {son}", ""]
        govde += ["Son seansta açılışta işlenenler:"] + (satir or ["• yok"]) + ["", "Yarın açılışta modelde işlenecek emirler:",
                  f"• Trend Girişi: {liste(giris)}", f"• Trend Çıkışı: {liste(cikis)}", "", fon]
    return "\n".join(govde) + uyari + f"\n\n{SITE}\n{UYARI}"

def bol(metin, n=3900):
    parca, cur = [], ""
    for satir in metin.split("\n"):
        if len(cur) + len(satir) + 1 > n: parca.append(cur); cur = ""
        cur += satir + "\n"
    return parca + [cur] if cur.strip() else parca

def gonder(metin):
    token, chat = os.environ.get("TELEGRAM_BOT_TOKEN"), os.environ.get("TELEGRAM_CHAT_ID")
    if not token or not chat:
        print("TELEGRAM_BOT_TOKEN / TELEGRAM_CHAT_ID tanımlı değil; mesaj yalnızca yazdırılıyor:\n\n" + metin); return
    for parca in bol(metin):
        veri = urllib.parse.urlencode({"chat_id": chat, "text": parca, "disable_web_page_preview": "true"}).encode()
        try:
            urllib.request.urlopen(urllib.request.Request(f"https://api.telegram.org/bot{token}/sendMessage", data=veri), timeout=20).read()
            print("✅ Telegram mesajı gönderildi.")
        except Exception as e:   # hata metnini basma: URL'de token var
            print(f"⚠️ Telegram mesajı gönderilemedi ({type(e).__name__}); çalışma devam ediyor.")

if __name__ == "__main__":
    gonder(mesaj(sys.argv[1] if len(sys.argv) > 1 else "aksam"))
