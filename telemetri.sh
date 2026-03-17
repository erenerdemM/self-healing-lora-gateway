#!/usr/bin/env bash
# =============================================================================
# telemetri.sh  —  Kampanya Sağlık Raporu (60 dakikada bir)
# =============================================================================
# Kullanım:  nohup ./telemetri.sh >> telemetri.log 2>&1 &
# =============================================================================
PROJ_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
LOG="$PROJ_DIR/telemetri.log"
MASTER_LOG="$PROJ_DIR/master_autorun.log"
INTERVAL=3600   # 60 dakika

declare -A FAZ_RUNS=( [1]=36 [2]=108 [3]=324 [4]=972 [5]=2916 [6]=8748 [7]=8748 )
TOTAL_CFGS=168   # 84 topoloji × 2 senaryo

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

report() {
    local ts
    ts=$(date '+%F %T')
    local temp
    temp=$(get_temp)
    local load
    load=$(awk '{print $1,$2,$3}' /proc/loadavg)
    local mem_free
    mem_free=$(free -h | awk '/^Mem:/{print $4}')
    local disk_free
    disk_free=$(df -h . | awk 'NR==2{print $4}')

    # Aktif OMNeT++ process sayısı
    local active_procs
    active_procs=$(pgrep -c lora_mesh_projesi_dbg 2>/dev/null || echo 0)

    # Mevcut checkpoint (aktif faz)
    local chk_faz="?"
    if [[ -f "$PROJ_DIR/.campaign_checkpoint" ]]; then
        chk_faz=$(cat "$PROJ_DIR/.campaign_checkpoint")
    fi

    # Her faz için tamamlanan .sca dosyası sayısı
    local total_done=0
    local phase_status=""
    for faz_n in $(seq 1 7); do
        local dir="${PROJ_DIR}/results_faz${faz_n}"
        local done_count=0
        if [[ -d "$dir" ]]; then
            done_count=$(ls "$dir"/*.sca 2>/dev/null | wc -l)
        fi
        local expected=$(( TOTAL_CFGS * FAZ_RUNS[$faz_n] ))
        local pct=0
        if [[ $expected -gt 0 ]]; then
            pct=$(( done_count * 100 / expected ))
        fi
        phase_status+="  Faz${faz_n}: ${done_count}/${expected} run (%${pct})\n"
        total_done=$(( total_done + done_count ))
    done

    # Run hızı (son 60 dakika): master_log'daki son 3600s içindeki OK satır sayısı
    local recent_ok=0
    if [[ -f "$MASTER_LOG" ]]; then
        recent_ok=$(awk -v cutoff="$(date -d '1 hour ago' '+%F %T')" \
            '$1" "$2 >= cutoff && /\[OK  \]/' "$MASTER_LOG" 2>/dev/null | wc -l)
    fi

    {
        echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
        echo " Telemetri  ${ts}"
        echo "───────────────────────────────────────────────────────"
        echo " CPU Sıcaklık  : ${temp}°C"
        echo " Yük Ortalaması: ${load}"
        echo " Bellek (boş)  : ${mem_free}"
        echo " Disk (boş)    : ${disk_free}"
        echo " Aktif Proc    : ${active_procs} (lora_mesh_projesi_dbg)"
        echo " Aktif Faz     : Faz ${chk_faz}"
        echo " Son 1s Biten  : ${recent_ok} run"
        echo "───────────────────────────────────────────────────────"
        echo " FAZ DURUMU:"
        echo -e "$phase_status"
        echo " Toplam Biten  : ${total_done} run"
        echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
        echo ""
    } | tee -a "$LOG"
}

# İlk raporu hemen ver
report

# Sonra her INTERVAL saniyede bir
while true; do
    sleep "$INTERVAL"
    report
done
