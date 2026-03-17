#!/usr/bin/env bash
# =============================================================================
# master_autorun.sh  —  Arazi1 7-Fazlı Kampanya Orkestratörü v2
# =============================================================================
# Kullanım:
#   nohup ./master_autorun.sh > master_autorun.log 2>&1 &
#   ./master_autorun.sh --faz 3        (belirli fazdan başla)
#   ./master_autorun.sh --config Faz1_Sc1_GW2_Mesh1_MIN  (tek config)
# =============================================================================
# set -e kapalı: setenv ve subshell exit kodlarından etkilenmeyelim

# ── Yollar ────────────────────────────────────────────────────────────────────
PROJ_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
OMNET_SETENV="/home/eren/Desktop/bitirme_lora_kod/omnetpp-6.0-linux-x86_64/omnetpp-6.0/setenv"
FLORA_DIR="/home/eren/Desktop/bitirme_lora_kod/workspace/flora"
INET_DIR="/home/eren/Desktop/bitirme_lora_kod/workspace/inet4.4"
BINARY="./lora_mesh_projesi_dbg"
NED_PATH=".:${FLORA_DIR}/src:${INET_DIR}/src"
INI="omnetpp.ini"
RESOURCE_ENGINE="./resource_engine.sh"
MASTER_LOG="${PROJ_DIR}/master_autorun.log"
FIXLOG="${PROJ_DIR}/Auto_Fix_Report.txt"
CHECKPOINT="${PROJ_DIR}/.campaign_checkpoint"
LOCKFILE="${PROJ_DIR}/.master_autorun.lock"

# ── Faz yapılandırması ────────────────────────────────────────────────────────
# Her faz: ad, run sayısı/config, sonuç dizini
declare -A FAZ_NAME=( [1]="Base_SF" [2]="Yasal_DC" [3]="Dogal_Engel"
                      [4]="Hava_Durumu" [5]="RF_Gurultu"
                      [6]="Internet_Gecikmesi" [7]="Self_Healing" )
declare -A FAZ_RUNS=( [1]=36 [2]=108 [3]=324 [4]=972 [5]=2916 [6]=8748 [7]=8748 )

START_FAZ=1
END_FAZ=7
SINGLE_CONFIG=""

# ── Tek instance kilidi (PID tabanlı — inode bağımsız) ───────────────────────
if [ -f "$LOCKFILE" ]; then
    old_pid=$(cat "$LOCKFILE" 2>/dev/null)
    if [ -n "$old_pid" ] && kill -0 "$old_pid" 2>/dev/null; then
        echo "HATA: master_autorun.sh zaten çalışıyor (PID=$old_pid). Çıkılıyor." >&2
        exit 1
    fi
fi
echo $$ > "$LOCKFILE"
# Çıkışta: tüm child prosesleri öldür (orphan subshell engeli) + kilidi sil
trap 'kill -- -$$ 2>/dev/null; wait 2>/dev/null; rm -f "$LOCKFILE"' EXIT SIGTERM SIGINT

# ── Argüman parse ─────────────────────────────────────────────────────────────
while [[ $# -gt 0 ]]; do
    case "$1" in
        --faz)    START_FAZ="$2"; shift 2 ;;
        --config) SINGLE_CONFIG="$2"; shift 2 ;;
        *) echo "Bilinmeyen argüman: $1"; exit 1 ;;
    esac
done

# ── OMNeT++ ortamını yükle ────────────────────────────────────────────────────
cd "$PROJ_DIR"
# shellcheck disable=SC1090
# set +u: setenv içindeki unset değişkenlerden korunmak için geçici kapat
set +u
source "$OMNET_SETENV" -f 2>/dev/null || true
set -u
# FLoRa + INET kütüphaneleri LD_LIBRARY_PATH'e ekle
export LD_LIBRARY_PATH="${FLORA_DIR}/src:${INET_DIR}/src${LD_LIBRARY_PATH:+:${LD_LIBRARY_PATH}}"

log() {
    echo "[$(date '+%F %T')] $*" >> "$MASTER_LOG"
}

# ── Tamamlanan run sayısını say ───────────────────────────────────────────────
count_done_runs() {
    local faz_n="$1" cfg="$2"
    local dir="results_faz${faz_n}"
    ls "${dir}/${cfg}"*.sca 2>/dev/null | wc -l
}

# ── Tek bir konfigürasyonu çalıştır (checkpoint'li + per-config flock) ────────
run_config() {
    local faz_n="$1" cfg="$2" total_runs="$3"
    local result_dir="results_faz${faz_n}"
    local log_file="logs_faz${faz_n}/${cfg}.log"
    local lock_dir="${PROJ_DIR}/.config_locks"
    local cfg_lock="${lock_dir}/${cfg}.lock"

    mkdir -p "$lock_dir"

    # Per-config flock: aynı config'i birden fazla instance/worker çalıştırmasın
    exec 201>"$cfg_lock"
    if ! flock -n 201; then
        log "  [LOCK] $cfg: başka worker/instance çalıştırıyor, atlanıyor"
        exec 201>&-
        return 0
    fi

    # Checkpoint: lock alındıktan sonra kontrol et (TOCTOU-free)
    local done_count
    done_count=$(count_done_runs "$faz_n" "$cfg")
    if [[ $done_count -ge $total_runs ]]; then
        log "  [SKIP] $cfg: zaten $done_count/$total_runs run tamamlandı"
        exec 201>&-
        return 0
    fi

    log "  [RUN ] $cfg  ($done_count/$total_runs run tamamlandı, devam...)"

    local t0
    t0=$(date +%s)

    # OMNeT++ çalıştır — taskset ile core 1-7'ye pin et, core 0 sistem için boş
    if taskset -c 1-7 $BINARY -u Cmdenv -c "$cfg" -f "$INI" \
         -n "$NED_PATH" \
         --output-scalar-file="${result_dir}/${cfg}-\${runnumber}.sca" \
         2>>"$log_file"; then
        local elapsed=$(( $(date +%s) - t0 ))
        log "  [OK  ] $cfg  (${elapsed}s)"
    else
        local rc=$?
        log "  [ERR ] $cfg  exit_code=$rc — Auto_Fix_Report'a bakın"
        echo "[$(date '+%F %T')] ERROR cfg=$cfg faz=$faz_n rc=$rc" >> "$FIXLOG"
        tail -10 "$log_file" >> "$FIXLOG" 2>/dev/null
        echo "---" >> "$FIXLOG"
    fi

    # Lock serbest bırak
    exec 201>&-
}

# ── Paralel havuz ─────────────────────────────────────────────────────────────
run_parallel() {
    local faz_n="$1"
    shift
    local cfgs=("$@")
    local total="${FAZ_RUNS[$faz_n]}"

    # Thread sayısını resource_engine'den al
    local threads=3
    threads=$(bash "$RESOURCE_ENGINE" 2>/dev/null || echo 3)
    log "[FAZ $faz_n] ${#cfgs[@]} config, ${total} run/config, ${threads} thread"

    # Dispatch takip dizini: aynı config iki kez başlatılmasın (noclobber ile atomik)
    local dispatch_dir="${PROJ_DIR}/.dispatch_faz${faz_n}"
    rm -rf "$dispatch_dir"
    mkdir -p "$dispatch_dir"

    local active=0
    local pids=()

    for cfg in "${cfgs[@]}"; do
        # Atomik dispatch bayrağı — noclobber ile race-condition'sız
        if ! ( set -o noclobber; : > "$dispatch_dir/${cfg}" ) 2>/dev/null; then
            log "  [DUP ] $cfg: zaten dispatch edildi, atlanıyor"
            continue
        fi

        # Boş slot bekle
        while [[ $active -ge $threads ]]; do
            sleep 1
            local new_pids=()
            for (( k=0; k<${#pids[@]}; k++ )); do
                if kill -0 "${pids[$k]}" 2>/dev/null; then
                    new_pids+=("${pids[$k]}")
                else
                    (( active-- ))
                fi
            done
            pids=("${new_pids[@]+"${new_pids[@]}"}")
            # Periyodik thread kontrolü: her 5 dakikada thread sayısını güncelle
            threads=$(bash "$RESOURCE_ENGINE" 2>/dev/null || echo 3)
        done

        # Yeni run başlat (arka planda)
        run_config "$faz_n" "$cfg" "$total" &
        pids+=($!)
        (( active++ ))
    done

    # Kalan işleri bekle
    wait
    rm -rf "$dispatch_dir"
    log "[FAZ $faz_n] Tüm config'ler tamamlandı."
}

# ── Git push + arşiv ─────────────────────────────────────────────────────────
phase_commit() {
    local faz_n="$1"
    local tag="faz${faz_n}_$(date +%Y%m%d_%H%M)"
    local archive="faz${faz_n}_results_${tag}.tar.gz"

    log "[GIT ] Faz $faz_n arşivleniyor → $archive"
    tar -czf "$archive" "results_faz${faz_n}/" "logs_faz${faz_n}/" 2>/dev/null || true

    if git -C "$PROJ_DIR" rev-parse --git-dir &>/dev/null; then
        # Sadece kod dosyalarını commit et (arşiv .gitignore'da zaten hariç)
        git -C "$PROJ_DIR" add omnetpp.ini master_autorun.sh resource_engine.sh \
            telemetri.sh generate_7faz_ini.py .gitignore 2>/dev/null || true
        git -C "$PROJ_DIR" commit -m "Arazi1 Faz${faz_n} ${FAZ_NAME[$faz_n]} tamamlandı — $(date '+%F %T')" \
            --quiet && log "[GIT ] commit ok" || log "[GIT ] commit atlandı (değişiklik yok?)"
        git -C "$PROJ_DIR" push origin main --quiet && log "[GIT ] push ok" || \
            log "[WARN] git push başarısız (remote bağlantısı yok?)"
    else
        log "[WARN] Git repo yok; commit atlandı."
    fi
}

# ── Config listesini ini'den çek ──────────────────────────────────────────────
get_phase_configs() {
    local faz_n="$1"
    grep -oP "(?<=^\[Config )Faz${faz_n}_[A-Za-z0-9_]+" "$INI" | sort
}

# ── Ana döngü ─────────────────────────────────────────────────────────────────
log "================================================================"
log " Arazi1 Master Autorun v2 — BAŞLADI"
log " Fazlar: ${START_FAZ}–${END_FAZ}   Binary: $BINARY"
log "================================================================"

if [[ -n "$SINGLE_CONFIG" ]]; then
    faz_n="${SINGLE_CONFIG:3:1}"
    log "[MANUAL] Tek config modu: $SINGLE_CONFIG (Faz $faz_n)"
    run_config "$faz_n" "$SINGLE_CONFIG" "${FAZ_RUNS[$faz_n]}"
    exit 0
fi

CAMPAIGN_START=$(date +%s)
for (( faz=START_FAZ; faz<=END_FAZ; faz++ )); do
    log ""
    log "══════════════════════════════════════════════════════════"
    log " FAZ ${faz}: ${FAZ_NAME[$faz]}  (${FAZ_RUNS[$faz]} run/config)"
    log "══════════════════════════════════════════════════════════"

    mapfile -t cfgs < <(get_phase_configs "$faz")
    if [[ ${#cfgs[@]} -eq 0 ]]; then
        log "[WARN] Faz $faz için config bulunamadı — atlanıyor"
        continue
    fi

    log "[FAZ $faz] ${#cfgs[@]} config bulundu"
    echo "$faz" > "$CHECKPOINT"
    run_parallel "$faz" "${cfgs[@]}"
    phase_commit "$faz"
done

ELAPSED=$(( $(date +%s) - CAMPAIGN_START ))
HOURS=$(( ELAPSED / 3600 ))
MINS=$(( (ELAPSED % 3600) / 60 ))
log ""
log "================================================================"
log " TÜM FAZ TAMAMLANDI  —  Süre: ${HOURS}s ${MINS}dk"
log "================================================================"
rm -f "$CHECKPOINT"

# İsteğe bağlı: poweroff
# log "[SYS ] Kapanıyor..."
# sudo poweroff
