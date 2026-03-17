#!/usr/bin/env bash
# =============================================================================
# telemetri.sh  —  Arazi1 60-dk'lık Telemetri Raporu (Prompt §4)
# =============================================================================
# Her 3600 saniyede bir terminale VE log dosyasına aşağıdaki formatı yazar:
#
#   FAZ X: [%25 Bitti] - 12.500 / 50.000 Run
#   Anlık Hız: 850 Run/Saat | Aktif Çekirdek: 7/8
#   Tahmini Kalan Süre: 14 Saat 20 Dakika | KESİN BİTİŞ: 18 Nis 09:15
#   Kullanıcı Modu: [Idle/Active] | CPU Sıcaklığı: 78°C
# =============================================================================

PROJ_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
TELELOG="${PROJ_DIR}/telemetri.log"
MASTER_LOG="${PROJ_DIR}/master_autorun.log"
CHECKPOINT="${PROJ_DIR}/.campaign_checkpoint"
INTERVAL=3600   # saniye: her 60 dk

# ── Run tarihçesi (hız hesaplama için) ─────────────────────────────────────
PREV_DONE=0
PREV_TIME=$(date +%s)

tele_log() { echo "[$(date '+%F %T')] $*" | tee -a "$TELELOG"; }

# ── Aktif faz bilgisi ───────────────────────────────────────────────────────
get_current_faz() {
    if [ -f "$CHECKPOINT" ]; then cat "$CHECKPOINT"; else echo "1"; fi
}

# ── Toplam ve tamamlanan run ────────────────────────────────────────────────
declare -A FAZ_TOTAL_RUNS=(
    [1]=6048     [2]=12096   [3]=24192
    [4]=48384    [5]=96768   [6]=193536  [7]=193536
)
GRAND_TOTAL=574560   # 168 config × (36+72+144+288+576+1152+1152)

cumulative_done() {
    local total=0
    for f in 1 2 3 4 5 6 7; do
        local sca_cnt
        sca_cnt=$(ls "${PROJ_DIR}/results_faz${f}/"*.sca 2>/dev/null | wc -l)
        local runs_per_cfg
        runs_per_cfg=$(case $f in 1)echo 36;;2)echo 108;;3)echo 324;;4)echo 972;;5)echo 2916;;6)echo 8748;;7)echo 8748;;esac)
        total=$(( total + sca_cnt * runs_per_cfg ))
    done
    echo "$total"
}

get_faz_done() {
    local faz_n="$1"
    local sca_cnt
    sca_cnt=$(ls "${PROJ_DIR}/results_faz${faz_n}/"*.sca 2>/dev/null | wc -l)
    local runs_per_cfg
    runs_per_cfg=$(case $faz_n in 1)echo 36;;2)echo 108;;3)echo 324;;4)echo 972;;5)echo 2916;;6)echo 8748;;7)echo 8748;;esac)
    echo $(( sca_cnt * runs_per_cfg ))
}

# ── CPU sıcaklığı ────────────────────────────────────────────────────────────
get_temp() {
    local t
    t=$(sensors 2>/dev/null | grep -oP 'Package id 0:\s+\+\K[0-9]+' | head -1)
    [ -z "$t" ] && t=$(sensors 2>/dev/null | grep -oP '\+[0-9]+\.[0-9]+°C' | head -1 | grep -oP '[0-9]+' | head -1)
    echo "${t:-?}"
}

# ── Kullanıcı aktifliği ──────────────────────────────────────────────────────
get_user_mode() {
    local idle_sec
    idle_sec=$(who -s 2>/dev/null | awk '{print $NF}' | head -1 | tr -d '()' 2>/dev/null)
    local cpu_pct
    cpu_pct=$(top -bn1 2>/dev/null | grep "Cpu(s)" | \
              sed 's/[,\.]/ /g' | awk '{sum=$2+$4; printf "%.0f", sum}' 2>/dev/null || echo "0")
    if [[ $cpu_pct -gt 15 ]]; then
        echo "Active"
    else
        echo "Idle"
    fi
}

# ── Aktif sim process sayısı ─────────────────────────────────────────────────
active_threads() {
    pgrep -c lora_mesh_projesi_dbg 2>/dev/null || echo 0
}

# ── Ana telemetri döngüsü ────────────────────────────────────────────────────
while true; do
    sleep "$INTERVAL"

    faz_n=$(get_current_faz)
    faz_done=$(get_faz_done "$faz_n")
    faz_total="${FAZ_TOTAL_RUNS[$faz_n]:-0}"
    grand_done=$(cumulative_done)

    # Yüzde
    if [[ $faz_total -gt 0 ]]; then
        faz_pct=$(( faz_done * 100 / faz_total ))
    else
        faz_pct=0
    fi

    # Hız (run/saat bu interval)
    now=$(date +%s)
    delta_run=$(( grand_done - PREV_DONE ))
    delta_sec=$(( now - PREV_TIME ))
    if [[ $delta_sec -gt 0 ]]; then
        speed_per_hour=$(( delta_run * 3600 / delta_sec ))
    else
        speed_per_hour=0
    fi
    PREV_DONE=$grand_done
    PREV_TIME=$now

    # Kalan süre
    remaining=$(( GRAND_TOTAL - grand_done ))
    if [[ $speed_per_hour -gt 0 ]]; then
        remaining_sec=$(( remaining * 3600 / speed_per_hour ))
        eta_epoch=$(( now + remaining_sec ))
        kalan_sa=$(( remaining_sec / 3600 ))
        kalan_dk=$(( (remaining_sec % 3600) / 60 ))
        bitis_str=$(date -d "@${eta_epoch}" '+%-d %b %H:%M')
        kalan_str="${kalan_sa} Saat ${kalan_dk} Dakika"
    else
        bitis_str="?"
        kalan_str="Hesaplanamadı"
    fi

    threads=$(active_threads)
    temp=$(get_temp)
    mode=$(get_user_mode)

    # Biçimlendirme: Türkçe virgüllü sayı
    fmt_num() { printf "%'.0f\n" "$1" | tr ',' '.'; }

    # ── Çıktı  (§4 formatı) ──────────────────────────────────────────────────
    MSG=$(printf "FAZ %s [%s]: %%%-3s Bitti — %s / %s Run
Anlık Hız: %s Run/Saat | Aktif Thread: %s/8
Tahmini Kalan Süre: %s | KESİN BİTİŞ: %s
Kullanıcı Modu: [%s] | CPU Sıcaklığı: %s°C
----" \
        "$faz_n" "${FAZ_TOTAL_RUNS[$faz_n]}" \
        "$faz_pct" \
        "$(fmt_num $faz_done)" "$(fmt_num $faz_total)" \
        "$(fmt_num $speed_per_hour)" \
        "$threads" \
        "$kalan_str" \
        "$bitis_str" \
        "$mode" "$temp")

    tele_log ""
    tele_log "══════ 60dk RAPOR ══════════════════════════════"
    echo "$MSG" | while IFS= read -r line; do tele_log "$line"; done
    tele_log "════════════════════════════════════════════════"
done
