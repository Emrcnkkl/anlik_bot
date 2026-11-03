#!/usr/bin/env bash
# Varyantları AYNI veriyle çalıştırır. Geçici dosyalara yazar; gerçek history.json / signals.json'a dokunmaz.
PY="${PY:-python}"; export SAATLIK=0
calistir() {
  ad="$1"; shift; rm -f /tmp/deney_h.json
  satir=$(env DENEY_ADI="$ad" HISTORY_DOSYASI=/tmp/deney_h.json SIGNALS_DOSYASI=/tmp/deney_s.json "$@" $PY quant_bot.py 2>&1 | grep "^DENEY")
  echo "$satir"; [ -n "$GITHUB_STEP_SUMMARY" ] && echo "- $satir" >> "$GITHUB_STEP_SUMMARY"
}
calistir "1-temel (mevcut)"
calistir "2-secim-dengeli" SECIM_SKORU=dengeli
calistir "3-gevsek-kilit" SOGUMA_GUN=2 KILL_ESIK=0.08 KILL_KILIT_GUN=4
calistir "4-gevsek-rejim (EMA50, dusuk ADX)" REJIM_SET=gevsek
calistir "5-hepsi-gevsek" SECIM_SKORU=dengeli SOGUMA_GUN=2 KILL_ESIK=0.08 KILL_KILIT_GUN=4 REJIM_SET=gevsek
calistir "6-korumasiz (kilit, gap, kill kapali)" SOGUMA_GUN=0 KILL_ESIK=1.0 GAP_ESIK=0.99
