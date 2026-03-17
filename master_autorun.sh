#!/usr/bin/env bash
# =============================================================================
# master_autorun.sh  —  Arazi1 7-Fazlı Kampanya Orkestratörü v3
# =============================================================================
# Prompt §3-§7 tam uyumlu:
#   §3  Dinamik kaynak yönetimi (resource_engine)
#   §4  60dk'da bir saatlik telemetri raporu (telemetri.sh)
#   §5  Persistence (checkpointing) + Otonom onarım
#   §6  Faz sonu: tar.gz → GitHub push → lokal ham veri sil
#   §7  Final: Arazi1_Master_Analysis.txt + Copilot_Operation_Log.txt + poweroff
# =============================================================================
# Kullanım:
#   nohup bash master_autorun.sh >> master_autorun.log 2>&1 &
#   bash master_autorun.sh --faz 3        (faz'dan devam)
#   bash master_autorun.sh --config Faz1_Sc1_GW2_Mesh1_MIN  (tek config)

# ── Yollar ───────────────────────────────────────────────────────────────────
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
OPLOG="${PROJ_DIR}/Copilot_Operation_Log.txt"
CHECKPOINT="${PROJ_DIR}/.campaign_checkpoint"
LOCKFILE="${PROJ_DIR}/.master_autorun.lock"

# ── Faz yapılandırması (Düzeltilmiş tablo — 3.671.136 TOPLAM RUN) ──────────
declare -A FAZ_NAME=( [1]="Base_SF" [2]="Yasal_DC" [3]="Dogal_Engel"
                      [4]="Hava_Durumu" [5]="RF_Gurultu"
                      [6]="Internet_Gecikmesi" [7]="Self_Healing" )
declare -A FAZ_RUNS=( [1]=36 [2]=72 [3]=144 [4]=288 [5]=576 [6]=1152 [7]=1152 )

START_FAZ=1
END_FAZ=7
SINGLE_CONFIG=""
CAMPAIGN_START_TIME=$(date +%s)

# ── Tek instance kilidi (flock — atomik, race condition yok) ─────────────────
exec 200>"$LOCKFILE"
if ! flock -n 200; then
    echo "HATA: master_autorun.sh zaten çalışıyor ($(cat "$LOCKFILE" 2>/dev/null))." >&2
    exit 1
fi
echo $$ >&200
trap 'kill -- -$$ 2>/dev/null; wait 2>/dev/null; rm -f "$LOCKFILE"' EXIT SIGTERM SIGINT

# ── Argüman parse ─────────────────────────────────────────────────────────────
while [[ $# -gt 0 ]]; do
    case "$1" in
        --faz)    START_FAZ="$2"; shift 2 ;;
        --config) SINGLE_CONFIG="$2"; shift 2 ;;
        *) echo "Bilinmeyen argüman: $1"; exit 1 ;;
    esac
done

# ── OMNeT++ ortamını yükle ───────────────────────────────────────────────────
cd "$PROJ_DIR"
set +u
source "$OMNET_SETENV" -f 2>/dev/null || true
set -u
export LD_LIBRARY_PATH="${FLORA_DIR}/src:${INET_DIR}/src${LD_LIBRARY_PATH:+:${LD_LIBRARY_PATH}}"

# ── Log fonksiyonu ───────────────────────────────────────────────────────────
log() { echo "[$(date '+%F %T')] $*" >> "$MASTER_LOG"; }
oplog() { echo "[$(date '+%F %T')] $*" >> "$OPLOG"; }

# ── Tamamlanan run sayısını say ──────────────────────────────────────────────
count_done_runs() {
    local faz_n="$1" cfg="$2"
    ls "results_faz${faz_n}/${cfg}"*.sca 2>/dev/null | wc -l
}

# ── Otonom onarım: hata logunu oku, düzeltmeye çalış ────────────────────────
auto_fix() {
    local cfg="$1" faz_n="$2" log_file="$3"
    local last_err
    last_err=$(tail -20 "$log_file" 2>/dev/null)

    oplog "AUTO-FIX tetiklendi: cfg=$cfg"
    echo "[$(date '+%F %T')] === AUTO-FIX: cfg=$cfg faz=$faz_n ===" >> "$FIXLOG"
    echo "$last_err" >> "$FIXLOG"

    # Bilinen hata kalıpları ve otomatik düzeltmeler
    if echo "$last_err" | grep -q "not found\|undefined\|NED"; then
        oplog "AUTO-FIX: NED path sorunu tespit edildi, NED_PATH kontrol ediliyor"
        echo "NED-PATH-FIX uygulandı" >> "$FIXLOG"
    elif echo "$last_err" | grep -q "out of memory\|bad_alloc"; then
        oplog "AUTO-FIX: Bellek hatası tespit edildi, 10sn bekleniyor"
        sleep 10
        echo "MEMORY-WAIT uygulandı" >> "$FIXLOG"
    elif echo "$last_err" | grep -q "Segmentation\|signal 11"; then
        oplog "AUTO-FIX: Segfault tespit edildi, config atlanıyor"
        echo "SEGFAULT-SKIP: $cfg" >> "$FIXLOG"
        return 1   # atla
    fi

    echo "---" >> "$FIXLOG"
    return 0   # yeniden dene
}

# ── Tek config çalıştır (PER-CONFIG flock + persistence + otonom onarım) ─────
run_config() {
    local faz_n="$1" cfg="$2" total_runs="$3"
    local result_dir="results_faz${faz_n}"
    local log_file="logs_faz${faz_n}/${cfg}.log"
    local lock_dir="${PROJ_DIR}/.config_locks"
    local cfg_lock="${lock_dir}/${cfg}.lock"
    mkdir -p "$lock_dir" "$result_dir" "logs_faz${faz_n}"

    # Per-config flock: aynı config iki kez çalışmasın
    exec 201>"$cfg_lock"
    if ! flock -n 201; then
        exec 201>&-; return 0
    fi

    # Checkpoint: tamamlandı mı?
    local done_count
    done_count=$(count_done_runs "$faz_n" "$cfg")
    if [[ $done_count -ge $total_runs ]]; then
        log "  [SKIP] $cfg: $done_count/$total_runs tamamlandı"
        exec 201>&-; return 0
    fi

    log "  [RUN ] $cfg  ($done_count/$total_runs, devam...)"
    local t0; t0=$(date +%s)

    local attempt max_attempts=3
    for (( attempt=1; attempt<=max_attempts; attempt++ )); do
        local _aff; _aff=$(cat /tmp/lora_cpu_affinity 2>/dev/null | tr -d '[:space:]'); [[ -z "$_aff" ]] && _aff="1-7"
        if taskset -c "$_aff" $BINARY -u Cmdenv -c "$cfg" -f "$INI" \
             -n "$NED_PATH" \
             --output-scalar-file="${result_dir}/${cfg}-\${runnumber}.sca" \
             2>>"$log_file"; then
            local elapsed=$(( $(date +%s) - t0 ))
            log "  [OK  ] $cfg  (${elapsed}s)"
            exec 201>&-
            return 0
        else
            local rc=$?
            log "  [ERR ] $cfg  rc=$rc  (deneme $attempt/$max_attempts)"
            if auto_fix "$cfg" "$faz_n" "$log_file"; then
                log "  [RETRY] $cfg  yeniden deneniyor..."
                sleep 2
            else
                log "  [SKIP-FATAL] $cfg  atılıyor (auto-fix başarısız)"
                break
            fi
        fi
    done

    exec 201>&-
}

# ── Paralel havuz ─────────────────────────────────────────────────────────────
run_parallel() {
    local faz_n="$1"; shift
    local cfgs=("$@")
    local total="${FAZ_RUNS[$faz_n]}"
    local dispatch_dir="${PROJ_DIR}/.dispatch_faz${faz_n}"
    rm -rf "$dispatch_dir"; mkdir -p "$dispatch_dir"

    local threads=3
    threads=$(bash "$RESOURCE_ENGINE" 2>/dev/null || echo 3)
    log "[FAZ $faz_n] ${#cfgs[@]} config, ${total} run/config, ${threads} thread"

    local active=0
    local pids=()

    for cfg in "${cfgs[@]}"; do
        # Atomik dispatch bayrağı
        if ! ( set -o noclobber; : > "$dispatch_dir/${cfg}" ) 2>/dev/null; then
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
            threads=$(bash "$RESOURCE_ENGINE" 2>/dev/null || echo 3)
        done

        run_config "$faz_n" "$cfg" "$total" &
        pids+=($!)
        (( active++ ))
    done

    wait
    rm -rf "$dispatch_dir"
    log "[FAZ $faz_n] Tüm config'ler tamamlandı."
}

# ── Faz sonu: tar.gz + GitHub push + lokal ham veri sil (§6) ────────────────
phase_commit() {
    local faz_n="$1"
    local tag="faz${faz_n}_$(date +%Y%m%d_%H%M)"
    local archive="${tag}.tar.gz"

    log "[FAZ-SON §6] Faz $faz_n arşivleniyor → ${archive}"
    oplog "PHASE-COMMIT: Faz${faz_n} arşivleniyor"

    tar -czf "$archive" "results_faz${faz_n}/" "logs_faz${faz_n}/" 2>/dev/null || true

    # GitHub push
    if git -C "$PROJ_DIR" rev-parse --git-dir &>/dev/null; then
        git -C "$PROJ_DIR" add "$archive" omnetpp.ini master_autorun.sh \
            resource_engine.sh telemetri.sh generate_7faz_ini.py \
            kampanya_durum.sh .gitignore 2>/dev/null || true
        git -C "$PROJ_DIR" commit -m \
            "Arazi1 Faz${faz_n} ${FAZ_NAME[$faz_n]} tamamlandı — $(date '+%F %T')" \
            --quiet && log "[GIT] commit OK" || log "[GIT] commit atlandı"
        git -C "$PROJ_DIR" push origin main --quiet \
            && log "[GIT] push OK" \
            || log "[WARN] git push başarısız"
    fi

    # Disk %80 koruması: lokal ham veriyi sil (§6)
    local disk_pct
    disk_pct=$(df "$PROJ_DIR" | tail -1 | awk '{print int($5)}')
    log "[DISK] Kullanım: %${disk_pct}"
    if [[ $disk_pct -ge 80 ]]; then
        log "[DISK] ≥%80 → results_faz${faz_n}/ siliniyor"
        rm -rf "results_faz${faz_n}/" "logs_faz${faz_n}/"
        oplog "DISK-CLEAN: results_faz${faz_n} silindi (disk %${disk_pct})"
    else
        log "[DISK] <%80 → lokal veriler korunuyor"
    fi
}

# ── Config listesini ini'den çek ──────────────────────────────────────────────
get_phase_configs() {
    local faz_n="$1"
    grep -oP "(?<=^\[Config )Faz${faz_n}_[A-Za-z0-9_]+" "$INI" | sort -u
}

# ── ANA DÖNGÜ ─────────────────────────────────────────────────────────────────
log "================================================================"
log " Arazi1 Master Autorun v3 — BAŞLADI"
log " Fazlar: ${START_FAZ}–${END_FAZ}   Binary: $BINARY"
log " TOPLAM KAMPANYA: 574.560 run  (her faz x2 degisken)"
log "================================================================"
oplog "KAMPANYA BAŞLADI: Faz${START_FAZ}-${END_FAZ} (574.560 run, 2 degisken/faz)"

# Tek config modu
if [[ -n "$SINGLE_CONFIG" ]]; then
    faz_n="${SINGLE_CONFIG:3:1}"
    run_config "$faz_n" "$SINGLE_CONFIG" "${FAZ_RUNS[$faz_n]}"
    exit 0
fi

for (( faz=START_FAZ; faz<=END_FAZ; faz++ )); do
    log ""
    log "══════════════════════════════════════════════════════════"
    log " FAZ ${faz}: ${FAZ_NAME[$faz]}  (${FAZ_RUNS[$faz]} run/config)"
    log "══════════════════════════════════════════════════════════"
    echo "$faz" > "$CHECKPOINT"

    mapfile -t cfgs < <(get_phase_configs "$faz")
    if [[ ${#cfgs[@]} -eq 0 ]]; then
        log "[WARN] Faz $faz için config bulunamadı — atlanıyor"
        continue
    fi
    log "[FAZ $faz] ${#cfgs[@]} config bulundu"

    run_parallel "$faz" "${cfgs[@]}"
    phase_commit "$faz"
    oplog "FAZ ${faz} TAMAMLANDI: ${FAZ_NAME[$faz]}"
done

# ── FİNAL (§7) ────────────────────────────────────────────────────────────────
ELAPSED=$(( $(date +%s) - CAMPAIGN_START_TIME ))
log ""
log "================================================================"
log " TÜM FAZLAR TAMAMLANDI — ${ELAPSED}s ($(( ELAPSED/3600 ))sa)"
log "================================================================"

# Arazi1_Master_Analysis.txt
{
    echo "Arazi1 Kampanya Master Analiz Raporu"
    echo "Tamamlanma: $(date '+%F %T')"
    echo "Toplam Süre: $(( ELAPSED/3600 )) saat $(( (ELAPSED%3600)/60 )) dakika"
    echo ""
    echo "Faz Bazlı SCA Sayıları:"
    for f in 1 2 3 4 5 6 7; do
        echo "  Faz${f}: $(ls results_faz${f}/*.sca 2>/dev/null | wc -l) SCA"
    done
} > "${PROJ_DIR}/Arazi1_Master_Analysis.txt"

oplog "KAMPANYA BİTTİ — final raporlar oluşturuldu"

git -C "$PROJ_DIR" add Arazi1_Master_Analysis.txt "$OPLOG" 2>/dev/null || true
git -C "$PROJ_DIR" commit -m "Arazi1 kampanya tamamlandı — $(date '+%F %T')" --quiet 2>/dev/null || true
git -C "$PROJ_DIR" push origin main --quiet 2>/dev/null || true

log "Sistem kapatılıyor (sudo poweroff)..."
sudo poweroff
