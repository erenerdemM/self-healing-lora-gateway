#!/bin/bash
# Bağımsız telemetri monitörü — master_autorun.sh'a dokunmadan çalışır
# Her 15 dakikada bir master_autorun.log dosyasına durum raporu ekler

PROJ_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
LOG_FILE="${PROJ_DIR}/master_autorun.log"
START_TIME=$(date +%s)

while true; do
    sleep 900   # 15 dakika

    NOW=$(date +%s)
    ELAPSED=$(( (NOW - START_TIME) / 60 ))
    TS=$(date '+%Y-%m-%d %H:%M:%S')

    # Aktif simülasyon binary sayısı
    SIM_COUNT=$(pgrep -c -f "lora_mesh_projesi_dbg" 2>/dev/null || echo 0)

    # Hangi faz/config şu an çalışıyor
    ACTIVE_CFG=$(ps aux | grep "lora_mesh_projesi_dbg" | grep -v grep | head -1 | \
        grep -oP "\-c \K[^\s]+" || echo "?")

    # Son tamamlanan run
    LAST_DONE=$(grep "\[DONE\]" "${LOG_FILE}" 2>/dev/null | tail -1 | grep -oP "\d+/\d+" || echo "?")

    # Toplam DONE sayısı (son 1 saatteki log'dan)
    TOTAL_DONE=$(grep "\[DONE\]" "${LOG_FILE}" 2>/dev/null | wc -l || echo 0)

    # CPU kullanımı
    CPU_PCT=$(python3 -c "import psutil; print(f'{psutil.cpu_percent(interval=0.3):.1f}')" 2>/dev/null || echo "?")

    # Aktif çekirdek tahmini
    JOBS=$(ps aux | grep "lora_mesh_projesi_dbg" | grep -v grep | wc -l)

    {
        echo "━━━ TELEMETRİ [${TS}] ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
        echo "  Aktif simülasyon : ${SIM_COUNT} paralel"
        echo "  Çalışan config   : ${ACTIVE_CFG}"
        echo "  Son run          : ${LAST_DONE}"
        echo "  Toplam [DONE]    : ${TOTAL_DONE} satır logda"
        echo "  CPU              : %${CPU_PCT}"
        echo "  Çalışma süresi   : ${ELAPSED} dakika"
        echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    } | tee -a "${LOG_FILE}"
done
