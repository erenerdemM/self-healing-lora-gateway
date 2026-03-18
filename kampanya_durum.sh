#!/usr/bin/env bash
# ============================================================
# kampanya_durum.sh — LoRa Mesh Kampanya Anlık Durum Raporu
# Kullanım:
#   bash kampanya_durum.sh           → Tek seferlik görüntü
#   bash kampanya_durum.sh --watch   → 10 sn'de bir otomatik yenile
# ============================================================

[[ "${1:-}" == "--watch" ]] && exec watch -n 10 bash "$0"

# ${#str} → karakter sayısı (byte değil) için UTF-8 zorla
export LANG=en_US.UTF-8

PROJ_DIR="/home/eren/Desktop/bitirme_lora_kod/lora_mesh_projesi"
INI="${PROJ_DIR}/omnetpp.ini"
LOG="${PROJ_DIR}/master_autorun.log"
CHECKPOINT="${PROJ_DIR}/.campaign_checkpoint"

declare -A FAZ_RUNS=([1]=36 [2]=72 [3]=144 [4]=288 [5]=576 [6]=1152 [7]=1152)
TOTAL_FAZ=7
W=57    # Kutu iç genişliği (─ sayısı)

# ── Aktif faz tespiti ─────────────────────────────────────────
AKTIF_FAZ=1
if [[ -f "$CHECKPOINT" ]]; then
    _v=$(cat "$CHECKPOINT" 2>/dev/null | tr -d '[:space:]')
    [[ "$_v" =~ ^[1-7]$ ]] && AKTIF_FAZ=$_v
else
    # Checkpoint yok → en yüksek dolu fazı bul
    for _f in 7 6 5 4 3 2 1; do
        [[ $(ls "${PROJ_DIR}/results_faz${_f}/"*.sca 2>/dev/null | wc -l) -gt 0 ]] \
            && AKTIF_FAZ=$_f && break
    done
fi

# ── Tamamlanan faz sayısı ─────────────────────────────────────
TAMAMLANAN_FAZ=0
for _f in $(seq 1 $((AKTIF_FAZ - 1))); do
    _cfg=$(grep -c "^\[Config Faz${_f}_" "$INI" 2>/dev/null || echo 168)
    _total=$(( FAZ_RUNS[$_f] * _cfg ))
    _done=$(ls "${PROJ_DIR}/results_faz${_f}/"*.sca 2>/dev/null | wc -l)
    [[ $_done -ge $_total && $_total -gt 0 ]] && (( TAMAMLANAN_FAZ++ ))
done

# ── Bu fazın çalışma sayıları ─────────────────────────────────
FAZ_CFG=$(grep -c "^\[Config Faz${AKTIF_FAZ}_" "$INI" 2>/dev/null || echo 168)
TOTAL_RUNS=$(( FAZ_RUNS[$AKTIF_FAZ] * FAZ_CFG ))
DONE_RUNS=$(ls "${PROJ_DIR}/results_faz${AKTIF_FAZ}/"*.sca 2>/dev/null | wc -l)
DONE_PCT=0
[[ $TOTAL_RUNS -gt 0 ]] && DONE_PCT=$(( DONE_RUNS * 100 / TOTAL_RUNS ))

# ── Aktif config (çalışan prosesten al; yoksa log'dan son bilinen) ──────────
AKTIF_CFG=$(ps aux 2>/dev/null \
    | grep lora_mesh_projesi_dbg \
    | grep -v grep \
    | grep -oP '(?<=-c )\S+' \
    | head -1)
if [[ -z "$AKTIF_CFG" ]]; then
    # İki config arasındaki boşlukta: log'dan son çalışan config'i al
    LAST_LOG_CFG=$(grep "\[RUN \]" "$LOG" 2>/dev/null \
        | tail -1 \
        | grep -oP 'Faz[A-Za-z0-9_]+' \
        | head -1)
    AKTIF_CFG="${LAST_LOG_CFG:-(bekleniyor)}  ⏳"
fi

# ── Paralel simülasyon sayısı ─────────────────────────────────
# -f: tam komut satırına bak (binary adı >15 karakter olduğu için gerekli)
PARALEL=$(pgrep -f "lora_mesh_projesi_dbg" 2>/dev/null | wc -l)

# ── Hız: son 5 dk'da üretilen SCA dosyalarından hesapla ──────
RECENT=$(find "${PROJ_DIR}/results_faz${AKTIF_FAZ}" \
    -name "*.sca" -mmin -5 2>/dev/null | wc -l)
SPEED=0
[[ $RECENT -gt 0 ]] && SPEED=$(( RECENT / 5 ))

# ── ETA hesabı ───────────────────────────────────────────────
REM=$(( TOTAL_RUNS - DONE_RUNS ))
if [[ $REM -le 0 ]]; then
    ETA_STR="Tamamlandı ✓"
elif [[ $SPEED -gt 0 ]]; then
    ETA_M=$(( REM / SPEED ))
    ETA_T=$(date -d "+${ETA_M} minutes" '+%H:%M' 2>/dev/null || echo "--:--")
    ETA_STR="~${ETA_M} dk → ${ETA_T}"
else
    ETA_STR="hesaplanıyor..."
fi

# ── CPU kullanımı (toplam + per-core) ──────────────────────────
CORES=$(nproc 2>/dev/null || echo "8")

# mpstat varsa per-core, yoksa top fallback
if command -v mpstat &>/dev/null; then
    # LC_ALL=C → ondalık nokta; Average: satırlarını kullan (daha kararlı)
    MPSTAT_OUT=$(LC_ALL=C mpstat -P ALL 1 1 2>/dev/null | grep "^Average:")
    CPU=$(echo "$MPSTAT_OUT" | awk '$2=="all"{printf "%.1f", 100-$NF}')
    [[ -z "$CPU" ]] && CPU="?"
    # Her core için kullanım yüzdesi
    CORE_USAGE=$(echo "$MPSTAT_OUT" | awk '
        $2!="all" && $2~/^[0-9]/ {
            used = 100 - $NF
            printf "C%s:%2.0f%%  ", $2, used
        }' | sed 's/[[:space:]]*$//')
else
    CPU=$(top -bn2 -d0.3 2>/dev/null \
        | grep -E "^(%Cpu|Cpu)" \
        | tail -1 \
        | grep -oP '[\d]+[.,][\d]+(?=\s*us)' \
        | head -1 \
        | tr ',' '.')
    [[ -z "$CPU" ]] && CPU="?"
    # Fallback: /proc/stat'tan per-core hesapla (tek snapshot, yaklaşık)
    CORE_USAGE=$(awk '/^cpu[0-9]/{                               \
        name=$1; usr=$2; nic=$3; sys=$4; idle=$5;               \
        tot=usr+nic+sys+idle+$6+$7+$8;                          \
        if(tot>0) used=int((tot-idle)*100/tot);                  \
        else used=0;                                             \
        printf "C%s:%d%%  ", substr(name,4,99), used            \
    }' /proc/stat | sed 's/  *$//')
fi

# Affinity modu
AFF=$(cat /tmp/lora_cpu_affinity 2>/dev/null || echo "0-7")
if [[ "$AFF" == "0-7" ]]; then
    AFF_MOD="8 CORE TAM HIZ"
else
    AFF_MOD="2 CORE (TERMAL KORUMA)"
fi

# Sıcaklık
TEMP=$(cat /sys/class/thermal/thermal_zone0/temp 2>/dev/null | awk '{printf "%.0f", $1/1000}')
[[ -z "$TEMP" ]] && TEMP="?"

# ── Tüm kampanyanın bitiş tahmini ───────────────────────────────────────────
NOW_S=$(date +%s)
CAMP_BITIS_STR="hesaplanıyor..."
if [[ $SPEED -gt 0 ]]; then
    # Kalan tüm fazların toplam run sayısını hesapla
    KALAN_TOPLAM=0
    for _ff in $(seq "$AKTIF_FAZ" 7); do
        _fcfg=$(grep -c "^\[Config Faz${_ff}_" "$INI" 2>/dev/null || echo 168)
        _ftotal=$(( FAZ_RUNS[$_ff] * _fcfg ))
        if [[ $_ff -eq $AKTIF_FAZ ]]; then
            _fdone=$(ls "${PROJ_DIR}/results_faz${_ff}/"*.sca 2>/dev/null | wc -l)
            KALAN_TOPLAM=$(( KALAN_TOPLAM + _ftotal - _fdone ))
        else
            KALAN_TOPLAM=$(( KALAN_TOPLAM + _ftotal ))
        fi
    done
    KALAN_M=$(( KALAN_TOPLAM / SPEED ))
    BITIS_T=$(date -d "+${KALAN_M} minutes" '+%d %b %H:%M' 2>/dev/null || echo "--")
    KALAN_H=$(( KALAN_M / 60 ))
    KALAN_GUN=$(( KALAN_M / 1440 ))
    if [[ $KALAN_GUN -ge 1 ]]; then
        CAMP_BITIS_STR="~${KALAN_GUN} gün → ${BITIS_T}"
    elif [[ $KALAN_H -ge 1 ]]; then
        CAMP_BITIS_STR="~${KALAN_H} sa → ${BITIS_T}"
    else
        CAMP_BITIS_STR="~${KALAN_M} dk → ${BITIS_T}"
    fi
fi

# ── Kutu çizim yardımcıları ─────────────────────────────────
hrule() {
    printf '%.0s─' $(seq 1 "$W")
}

# Sol hizalı satır: içerik + sağa boşluk doldur → toplam W karakter
row() {
    local s="$1" rpad
    rpad=$(( W - ${#s} ))
    [[ $rpad -lt 0 ]] && rpad=0
    printf "│%s%*s│\n" "$s" "$rpad" ""
}

# Başlık satırı: kutu içinde ortala
center_row() {
    local s="$1" lp rp
    lp=$(( (W - ${#s}) / 2 ))
    rp=$(( W - ${#s} - lp ))
    printf "│%*s%s%*s│\n" "$lp" "" "$s" "$rp" ""
}

# ── Raporu yazdır ─────────────────────────────────────────────
ZAMAN=$(date '+%H:%M:%S')

# ── Per-core satırları (4'er core'luk 2 satır) ─────────────────
# C0:85%  C1:92%  C2:78%  C3:95%
make_core_rows() {
    local all=()
    # CORE_USAGE'ı diziye ayır
    IFS='  ' read -ra all <<< "$CORE_USAGE"
    local line="  "
    local count=0
    for item in "${all[@]}"; do
        [[ -z "$item" ]] && continue
        line+="${item}  "
        (( count++ ))
        if [[ $count -eq 4 ]]; then
            row "$line"
            line="  "
            count=0
        fi
    done
    [[ $count -gt 0 ]] && row "$line"
}

printf "┌%s┐\n" "$(hrule)"
center_row "KAMPANYA DURUM RAPORU — ${ZAMAN}"
printf "├%s┤\n" "$(hrule)"
row "  Aktif Faz              : Faz${AKTIF_FAZ}  (${TAMAMLANAN_FAZ}/${TOTAL_FAZ})"
row "  Faz İlerlemesi         : ${DONE_RUNS}/${TOTAL_RUNS} run  (%${DONE_PCT})"
row "  Aktif Config           : ${AKTIF_CFG}"
row "  Hız                    : ~${SPEED} run/dk"
row "  ETA (bu faz)           : ${ETA_STR}"
row "  Paralel Simülasyon     : ${PARALEL} adet  [ mod: ${AFF_MOD} ]"
row "  CPU Toplam             : %${CPU}  |  Sıcaklık: ${TEMP}°C"
printf "├%s┤\n" "$(hrule)"
center_row "— Per-Core Kullanım —"
make_core_rows
printf "├%s┤\n" "$(hrule)"
row "  Kampanya Bitişi        : ${CAMP_BITIS_STR}"
row "  Tamamlanan Faz         : ${TAMAMLANAN_FAZ}/${TOTAL_FAZ}"
printf "└%s┘\n" "$(hrule)"
