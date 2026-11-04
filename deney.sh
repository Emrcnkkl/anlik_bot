#!/usr/bin/env bash
# Kullanım:  bash deney.sh kisa   -> 3 yıl, 30 hisse: koruma / seçim / rejim varyantları
#            bash deney.sh uzun   -> 5 yıl, ~100 hisse: piyasa filtresi ve momentum varyantları
# Geçici dosyalara yazar; gerçek history.json / signals.json'a dokunmaz.
PY="${PY:-python}"; export SAATLIK=0
calistir() {
  ad="$1"; shift; rm -f /tmp/deney_h.json
  satir=$(env DENEY_ADI="$ad" HISTORY_DOSYASI=/tmp/deney_h.json SIGNALS_DOSYASI=/tmp/deney_s.json "$@" $PY quant_bot.py 2>&1 | grep "^DENEY")
  echo "$satir"; [ -n "$GITHUB_STEP_SUMMARY" ] && echo "$satir" | sed 's/^/- /' >> "$GITHUB_STEP_SUMMARY"
}
if [ "${1:-kisa}" = "uzun" ]; then
  export GECMIS=5y WF_PENCERE=1300 LIKIT_N=100
  calistir "U1-temel (5y, ~100 hisse)"
  calistir "U2-piyasa-filtre-giris" PIYASA_FILTRE=giris
  calistir "U3-piyasa-filtre-cikis" PIYASA_FILTRE=cikis
  calistir "U4-momentum-ilk15" MOM_N=15
  calistir "U5-momentum-ilk8" MOM_N=8
  calistir "U6-piyasa-giris+momentum15" PIYASA_FILTRE=giris MOM_N=15
else
  calistir "1-temel (mevcut)"
  calistir "2-secim-dengeli" SECIM_SKORU=dengeli
  calistir "3-gevsek-kilit" SOGUMA_GUN=2 KILL_ESIK=0.08 KILL_KILIT_GUN=4
  calistir "4-gevsek-rejim (EMA50, dusuk ADX)" REJIM_SET=gevsek
  calistir "5-hepsi-gevsek" SECIM_SKORU=dengeli SOGUMA_GUN=2 KILL_ESIK=0.08 KILL_KILIT_GUN=4 REJIM_SET=gevsek
  calistir "6-korumasiz (kilit, gap, kill kapali)" SOGUMA_GUN=0 KILL_ESIK=1.0 GAP_ESIK=0.99
fi
