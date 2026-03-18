#!/usr/bin/env bash
# =============================================================================
# resource_engine.sh  —  Akıllı Kaynak Yönetim Motoru v4
# =============================================================================
# Çıktı: önerilen paralel thread sayısı (tek rakam)
# Affinity: /tmp/lora_cpu_affinity dosyasına yazar
#
# Kural:
#   CPU sıcaklığı ≥ 95°C  → COOL: 2 thread (1-7), 90°C'ye inene kadar bekle
#   Normal                → 8 thread, tüm core'lar (0-7)
# =============================================================================

ALL_THREADS=8
COOL_THREADS=2
AFFINITY_FILE="/tmp/lora_cpu_affinity"
THERMAL_HIGH=95    # °C — throttle başlangıcı
THERMAL_LOW=90     # °C — throttle bitiş (histerezis)

# ── CPU Sıcaklığı ─────────────────────────────────────────────────────────────
get_temp() {
    local t
    t=$(cat /sys/class/thermal/thermal_zone0/temp 2>/dev/null || echo 0)
    echo $(( t / 1000 ))
}

# ── Karar ─────────────────────────────────────────────────────────────────────
decide() {
    local temp prev_threads
    temp=$(get_temp)
    prev_threads=$(cat /tmp/lora_prev_threads 2>/dev/null || echo "$ALL_THREADS")

    # Termal koruma: ≥95°C → throttle
    if [[ $temp -ge $THERMAL_HIGH ]]; then
        echo "1-7" > "$AFFINITY_FILE"
        echo "$COOL_THREADS"
        return
    fi

    # Histerezis: throttle modundaysa ve hâlâ ≥90°C → devam
    if [[ $prev_threads -eq $COOL_THREADS && $temp -ge $THERMAL_LOW ]]; then
        echo "1-7" > "$AFFINITY_FILE"
        echo "$COOL_THREADS"
        return
    fi

    # Normal mod: 8 core tam hız
    echo "0-7" > "$AFFINITY_FILE"
    echo "$ALL_THREADS"
}

RESULT=$(decide)
echo "$RESULT" > /tmp/lora_prev_threads
echo "$RESULT"
