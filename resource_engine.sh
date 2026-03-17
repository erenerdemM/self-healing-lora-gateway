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
ALL_THREADS=$NCPU                          # 8  — gece tam boşta (core 0 dahil)
IDLE_THREADS=$(( NCPU - 1 ))               # 7  — normal idle
ACTIVE_THREADS=$(( NCPU * 40 / 100 ))      # 3  — kullanıcı aktifken (%40)
[[ $ACTIVE_THREADS -lt 1 ]] && ACTIVE_THREADS=1
COOL_THREADS=$(( ACTIVE_THREADS - 1 ))     # 2  — termal koruma
[[ $COOL_THREADS -lt 1 ]] && COOL_THREADS=1
AFFINITY_FILE="/tmp/lora_cpu_affinity"

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
    # Yöntem 1: loginctl ile oturum idle süresi
    if command -v loginctl &>/dev/null; then
        local session_id idle_hint
        session_id=$(loginctl list-sessions --no-legend 2>/dev/null | awk 'NR==1{print $1}')
        if [[ -n "$session_id" ]]; then
            idle_hint=$(loginctl show-session "$session_id" -p IdleHint 2>/dev/null | cut -d= -f2)
            local idle_since idle_ts now_ts
            if [[ "$idle_hint" == "yes" ]]; then
                idle_since=$(loginctl show-session "$session_id" -p IdleSinceHint 2>/dev/null \
                    | cut -d= -f2)
                if [[ -n "$idle_since" && "$idle_since" != "0" ]]; then
                    idle_ts=$(( idle_since / 1000000 ))
                    now_ts=$(date +%s)
                    local idle_min=$(( (now_ts - idle_ts) / 60 ))
                    [[ $idle_min -le 5 ]]
                    return $?
                fi
                return 1  # idle=yes ama süre belli değil → idle say
            fi
            return 0  # IdleHint=no → aktif
        fi
    fi
    # Fallback: son tty aktivitesi
    local last_active
    last_active=$(find /dev/pts /dev/tty* -maxdepth 0 -newer /proc/1/stat 2>/dev/null | wc -l)
    [[ $last_active -gt 0 ]]
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

    local thermal_limit=90
    [[ "${MAX_PERF:-0}" == "1" ]] && thermal_limit=97

    # Termal koruma
    if [[ $temp -ge $thermal_limit ]]; then
        echo "1-7" > "$AFFINITY_FILE"
        echo "$COOL_THREADS"
        return
    fi

    if [[ "${MAX_PERF:-0}" == "1" ]]; then
        # Kullanıcı aktif değilse → gece modu: tüm 8 çekirdek (core 0 dahil)
        if ! user_cpu_high && ! user_active_input && ! high_load; then
            echo "0-7" > "$AFFINITY_FILE"
            echo "$ALL_THREADS"   # 8
            return
        fi
        # Kullanıcı aktif → core 0'ı serbest bırak
        echo "1-7" > "$AFFINITY_FILE"
        echo "$IDLE_THREADS"      # 7
        return
    fi

    # Kullanıcı aktif mi? (CPU >%15 VEYA girdi ≤5dk)
    if user_cpu_high || user_active_input; then
        echo "1-7" > "$AFFINITY_FILE"
        echo "$ACTIVE_THREADS"    # 3
        return
    fi

    # Sistem yükü yüksek mi?
    if high_load; then
        echo "1-7" > "$AFFINITY_FILE"
        echo "$ACTIVE_THREADS"
        return
    fi

    # Normal idle
    echo "1-7" > "$AFFINITY_FILE"
    echo "$IDLE_THREADS"          # 7
}

decide
