#!/usr/bin/env bash
# =============================================================================
# resource_engine.sh  —  Akıllı Kaynak Yönetim Motoru v3
# =============================================================================
# Çıktı: önerilen paralel thread sayısı (tek rakam)
#
# Kural (Prompt §3):
#   CPU sıcaklığı ≥ 90°C            → COOL (soğuma modu, vites küçült)
#   Kullanıcı aktif (CPU>%15 veya girdi ≤5dk) → floor(NCPU * 0.40)
#   Sistem idle (≥5dk inaktif, düşük yük)     → NCPU - 1
# =============================================================================

NCPU=$(nproc)                               # 8 (i5-10300H)
IDLE_THREADS=$(( NCPU - 1 ))               # 7  — sistem boştayken
ACTIVE_THREADS=$(( NCPU * 40 / 100 ))      # 3  — kullanıcı aktifken (%40)
[[ $ACTIVE_THREADS -lt 1 ]] && ACTIVE_THREADS=1
COOL_THREADS=$(( ACTIVE_THREADS - 1 ))     # 2  — termal koruma
[[ $COOL_THREADS -lt 1 ]] && COOL_THREADS=1

# ── CPU Sıcaklığı ─────────────────────────────────────────────────────────────
get_temp() {
    local t=0
    local hwmon_file
    hwmon_file=$(find /sys/class/hwmon -name "temp*_input" 2>/dev/null | head -1)
    if [[ -n "$hwmon_file" ]]; then
        t=$(cat "$hwmon_file" 2>/dev/null || echo 0)
    else
        t=$(cat /sys/class/thermal/thermal_zone0/temp 2>/dev/null || echo 0)
    fi
    echo $(( t / 1000 ))
}

# ── Kullanıcı CPU kullanımı (%15 eşiği) ───────────────────────────────────────
user_cpu_high() {
    # Simülasyon prosesleri HARİÇ CPU kullanımını ölç
    local sim_cpu
    sim_cpu=$(ps aux 2>/dev/null | grep lora_mesh_projesi_dbg | grep -v grep \
              | awk '{sum+=$3} END {print int(sum)}')
    local total_cpu
    total_cpu=$(top -bn2 -d0.3 2>/dev/null | grep -E "^(%Cpu|Cpu)" | tail -1 \
                | grep -oP '[\d]+[.,][\d]+(?=\s*us)' | head -1 | tr ',' '.')
    total_cpu=${total_cpu:-0}
    # kullanıcı cpu = toplam - sim
    local user_cpu
    user_cpu=$(echo "$total_cpu $sim_cpu" | awk '{v=$1-$2; if(v<0)v=0; print int(v)}')
    [[ $user_cpu -gt 15 ]]
}

# ── Kullanıcı girdi aktivitesi (≤5 dk) ───────────────────────────────────────
user_active_input() {
    if command -v xprintidle &>/dev/null; then
        local idle_ms
        idle_ms=$(DISPLAY=:0 xprintidle 2>/dev/null || echo 999999999)
        [[ $(( idle_ms / 60000 )) -le 5 ]]
        return $?
    fi
    # Fallback: birisi oturum açıksa aktif say
    [[ $(who | wc -l) -gt 0 ]]
}

# ── Sistem yük ortalaması (yüksek yük eşiği) ─────────────────────────────────
high_load() {
    local load1
    load1=$(awk '{print $1}' /proc/loadavg 2>/dev/null || echo "0.0")
    local threshold
    threshold=$(echo "$NCPU * 0.75" | awk '{printf "%.1f", $1}')
    awk -v l="$load1" -v t="$threshold" 'BEGIN{exit (l > t) ? 0 : 1}'
}

# ── Karar ─────────────────────────────────────────────────────────────────────
decide() {
    local temp
    temp=$(get_temp)

    # Termal koruma — 90°C eşiği
    if [[ $temp -ge 90 ]]; then
        echo "$COOL_THREADS"
        return
    fi

    # Kullanıcı aktif mi? (CPU >%15 VEYA girdi ≤5dk)
    if user_cpu_high || user_active_input; then
        echo "$ACTIVE_THREADS"   # %40 çekirdek
        return
    fi

    # Sistem yükü yüksek mi?
    if high_load; then
        echo "$ACTIVE_THREADS"
        return
    fi

    # Tam hız — idle mod
    echo "$IDLE_THREADS"         # N-1 çekirdek
}

decide
