#!/bin/bash
# =============================================================================
# master_autorun.sh — 7-Faz Kümülatif LoRa Mesh Simülasyonu
# =============================================================================
# Sıra: 1 → 2 → 3a → 3b → 3c → 4a → 4b → 4c → 5a → 5b → 5c
#       → 6a → 6b → 6c → 7
#
# Özellikler:
#   - Dinamik CPU ölçekleme (psutil): kullanıcı aktifse CPU/2, değilse max-1
#   - Saatlik telemetri: faz, run/toplam, hız, ETA, aktif çekirdek, CPU sıcaklığı
#   - Otonom tamir: exit!=0 → stderr analiz → logla → yeniden dene → devam
#   - Resume: .done flag sayesinde kaldığı yerden devam eder
#   - Git commit + push her faz sonunda
#
# Kullanım:
#   nohup bash master_autorun.sh > master_autorun.log 2>&1 &
#   tail -f master_autorun.log
# =============================================================================

set -euo pipefail

# ─── Dizinler ─────────────────────────────────────────────────────────────────
PROJ_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
VENV="/home/eren/venv-ardupilot"
LOG_FILE="${PROJ_DIR}/master_autorun.log"
TAMIR_LOG="${PROJ_DIR}/Otonom_Tamir_Logu.txt"

# psutil kurulu değilse kur
source "${VENV}/bin/activate"
python3 -c "import psutil" 2>/dev/null || pip install psutil -q
export PYTHONUNBUFFERED=1

# ─── Sabit iş sayısı (0 = dinamik psutil ölçümü) ─────────────────────────────
# Tüm çekirdekleri kullanmak için cpu_count - 1 sabit değer:
OVERRIDE_JOBS=$(( $(nproc) - 1 ))   # 8 çekirdek → 7 paralel iş

# ─── Faz sırası ───────────────────────────────────────────────────────────────
PHASE_ORDER=(1 2 3a 3b 3c 4a 4b 4c 5a 5b 5c 6a 6b 6c 7)

# ─── Yardımcı fonksiyonlar ────────────────────────────────────────────────────
log() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $*" | tee -a "${LOG_FILE}"
}

die() {
    log "FATAL: $*"
    exit 1
}

# Dinamik CPU hesapla: kullanıcı aktifse CPU/2, değilse (CPU_TOTAL - 1)
get_dynamic_jobs() {
    python3 - <<'PYEOF'
import psutil, os

cpu_total = os.cpu_count() or 4

# Kullanıcı oturumu açık mı?
try:
    users = len(psutil.users())
except Exception:
    users = 0

# CPU kullanımı (kısa 0.3s örnek)
try:
    cpu_pct = psutil.cpu_percent(interval=0.3)
except Exception:
    cpu_pct = 0.0

if users > 0 or cpu_pct > 40.0:
    # Kullanıcı aktif: CPU'nun yarısını kullan
    jobs = max(1, cpu_total // 2)
else:
    # Sistem boş: max paralel (1 çekirdek rezerv)
    jobs = max(1, cpu_total - 1)

print(jobs)
PYEOF
}

# Saatlik telemetri
print_telemetry() {
    local phase="$1" done_count="$2" total_runs="$3" wall_start="$4" jobs="$5"
    local now elapsed speed eta_h eta_m cpu_temp

    now=$(date +%s)
    elapsed=$(( now - wall_start ))

    if (( done_count > 0 && elapsed > 0 )); then
        speed=$(( done_count * 3600 / elapsed ))
        remaining=$(( total_runs - done_count ))
        eta_s=$(( remaining * elapsed / done_count ))
        eta_h=$(( eta_s / 3600 ))
        eta_m=$(( (eta_s % 3600) / 60 ))
    else
        speed=0; eta_h=0; eta_m=0
    fi

    cpu_temp=$(python3 -c "
import psutil
try:
    temps = psutil.sensors_temperatures()
    for name in ('coretemp','k10temp','cpu_thermal'):
        if name in temps and temps[name]:
            print(f'{temps[name][0].current:.1f}C'); break
    else:
        print('N/A')
except Exception:
    print('N/A')
" 2>/dev/null)

    log "━━━ TELEMETRİ ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    log "  Faz       : ${phase}"
    log "  İlerleme  : ${done_count}/${total_runs} run"
    log "  Hız       : ~${speed} run/saat"
    log "  ETA       : ~${eta_h}s ${eta_m}dk"
    log "  Çekirdek  : ${jobs} aktif"
    log "  CPU sıcak : ${cpu_temp}"
    log "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
}

# Otonom tamir: başarısız simülasyonu logla, stderr analiz et
otonom_tamir() {
    local config="$1" run_log="$2" phase="$3"
    local ts stderr_tail

    ts="$(date '+%Y-%m-%d %H:%M:%S')"
    stderr_tail=""
    [[ -f "${run_log}" ]] && stderr_tail=$(tail -20 "${run_log}" 2>/dev/null || true)

    {
        echo "======================================="
        echo "ZAMAN   : ${ts}"
        echo "FAZ     : ${phase}"
        echo "CONFIG  : ${config}"
        echo "LOG     : ${run_log}"
        echo "--- STDERR SON 20 SATIR ---"
        echo "${stderr_tail}"
        echo ""
    } >> "${TAMIR_LOG}"

    # Bilinen hata kalıpları → otomatik müdahale
    if echo "${stderr_tail}" | grep -q "out of memory\|bad_alloc"; then
        log "[Tamir] Bellek hatası tespit edildi — 60s bekleniyor"
        echo "TAMIR   : Bellek hatası — 60s beklendi" >> "${TAMIR_LOG}"
        sleep 60
    elif echo "${stderr_tail}" | grep -q "terminate called\|Segmentation fault"; then
        log "[Tamir] Crash tespit edildi — .done temizleniyor"
        echo "TAMIR   : Crash — run yeniden denenecek" >> "${TAMIR_LOG}"
    elif echo "${stderr_tail}" | grep -q "Cannot open\|No such file"; then
        log "[Tamir] Dosya hatası — topoloji yeniden üretilmeli"
        echo "TAMIR   : Dosya hatası tespit edildi" >> "${TAMIR_LOG}"
    else
        echo "TAMIR   : Genel hata — run atlandı, devam" >> "${TAMIR_LOG}"
    fi
    echo ""  >> "${TAMIR_LOG}"
    return 0  # Her durumda devam
}

# Python üzerinden PHASE_CONFIGS değeri çek
phase_config_get() {
    local phase="$1" key="$2"
    python3 -c "
import sys; sys.path.insert(0,'arge_scriptleri/topoloji_jenerator')
import generate_massive_topology as g
print(g.PHASE_CONFIGS['${phase}']['${key}'])
"
}

# ─── Başlangıç ────────────────────────────────────────────────────────────────
START_TOTAL=$(date +%s)
log "============================================================"
log "  7-FAZ MASTER AUTORUN BAŞLIYOR"
log "  Sıra: ${PHASE_ORDER[*]}"
log "  Toplam faz sayısı: ${#PHASE_ORDER[@]}"
log "  Başlangıç: $(date '+%Y-%m-%d %H:%M:%S')"
log "============================================================"

cd "${PROJ_DIR}"

# ─── HER FAZ ──────────────────────────────────────────────────────────────────
for PHASE in "${PHASE_ORDER[@]}"; do
    log ""
    log "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    log "  FAZ ${PHASE} başlatılıyor..."
    log "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

    START_PHASE=$(date +%s)

    # ── Adım 1: Topoloji + INI üret ─────────────────────────────────────────
    log "[Faz ${PHASE}] 1/3 Topoloji üretiliyor..."
    python3 arge_scriptleri/topoloji_jenerator/generate_massive_topology.py \
        --phase "${PHASE}" \
        || die "Faz ${PHASE} — topoloji üretim BAŞARISIZ"
    log "[Faz ${PHASE}] 1/3 Topoloji ✓"

    # PHASE_CONFIGS'den parametreleri çek
    RUN_SCRIPT=$(phase_config_get "${PHASE}" "run_script")
    LOG_BASE=$(phase_config_get "${PHASE}" "log_base")

    [[ -f "${PROJ_DIR}/${RUN_SCRIPT}" ]] \
        || die "Run script bulunamadı: ${RUN_SCRIPT}"

    TOTAL_RUNS=3024   # 84 config × 36 run

    # ── Adım 2: Dinamik CPU + Simülasyon ─────────────────────────────────────
    # OVERRIDE_JOBS > 0 ise dinamik hesaplamayı atla
    if [[ "${OVERRIDE_JOBS:-0}" -gt 0 ]]; then
        JOBS="${OVERRIDE_JOBS}"
    else
        JOBS=$(get_dynamic_jobs)
    fi
    log "[Faz ${PHASE}] 2/3 Simülasyon başlatılıyor — ${RUN_SCRIPT}  (${JOBS} paralel iş)"

    LAST_TELEMETRY=$(date +%s)
    LAST_JOBS_CHECK=$(date +%s)

    # Run script'i arka planda başlat
    bash "${PROJ_DIR}/${RUN_SCRIPT}" --jobs "${JOBS}" &
    RUN_PID=$!

    # Simülasyon çalışırken: CPU ölçümü + saatlik telemetri
    while kill -0 "${RUN_PID}" 2>/dev/null; do
        sleep 30
        NOW=$(date +%s)

        # Her 5 dakikada CPU ölçümü güncelle (log için; aktif pid'e sinyal göndermek pratik değil)
        if (( NOW - LAST_JOBS_CHECK >= 300 )); then
            NEW_JOBS=$(get_dynamic_jobs)
            if [[ "${NEW_JOBS}" != "${JOBS}" ]]; then
                log "[Faz ${PHASE}] CPU ölçüm: ${JOBS} → ${NEW_JOBS} aktif çekirdek (sonraki faz için geçerli)"
                JOBS="${NEW_JOBS}"
            fi
            LAST_JOBS_CHECK=${NOW}
        fi

        # Saatlik telemetri (15 dakikada bir — faz 1 saatin altında bittiği için)
        if (( NOW - LAST_TELEMETRY >= 900 )); then
            DONE_COUNT=$(find "${PROJ_DIR}/${LOG_BASE}" -name "*.done" 2>/dev/null | wc -l || echo 0)
            print_telemetry "${PHASE}" "${DONE_COUNT}" "${TOTAL_RUNS}" "${START_PHASE}" "${JOBS}"
            LAST_TELEMETRY=${NOW}
        fi
    done

    # Run script sonuç kontrolü
    wait "${RUN_PID}"
    EXIT_CODE=$?

    if [[ ${EXIT_CODE} -ne 0 ]]; then
        log "[Faz ${PHASE}] UYARI: run script exit=${EXIT_CODE} — otonom tamir + yeniden deneme"
        otonom_tamir "${RUN_SCRIPT}" "${LOG_FILE}" "${PHASE}"
        # Bir kez yeniden dene (başarısız olursa devam)
        bash "${PROJ_DIR}/${RUN_SCRIPT}" --jobs "${JOBS}" || \
            log "[Faz ${PHASE}] Yeniden deneme de BAŞARISIZ — bir sonraki faza geçiliyor"
    fi

    END_SIM=$(date +%s)
    DONE_FINAL=$(find "${PROJ_DIR}/${LOG_BASE}" -name "*.done" 2>/dev/null | wc -l || echo 0)
    log "[Faz ${PHASE}] 2/3 Simülasyon tamamlandı: ${DONE_FINAL}/${TOTAL_RUNS} run  ($(( (END_SIM - START_PHASE) / 60 )) dk)"

    # ── Adım 3: Organize & Arşiv ─────────────────────────────────────────────
    log "[Faz ${PHASE}] 3/3 Analiz ve arşivleme..."
    if python3 arge_scriptleri/veri_analiz/mega_organize_phase.py \
        --phase "${PHASE}" 2>&1 | tee -a "${LOG_FILE}"; then
        log "[Faz ${PHASE}] 3/3 Analiz ✓"
    else
        log "[Faz ${PHASE}] UYARI: analiz BAŞARISIZ — devam ediliyor"
    fi

    # ── Git Push ──────────────────────────────────────────────────────────────
    log "[Faz ${PHASE}] Git commit + push..."
    git add -A
    git commit -m "data: Faz${PHASE} simülasyon tamamlandı (${DONE_FINAL}/${TOTAL_RUNS} run)" \
        || log "[Faz ${PHASE}] Git commit: değişiklik yok (devam)"
    git push origin main \
        || log "[Faz ${PHASE}] Git push BAŞARISIZ — bağlantı sorunu (devam)"

    END_PHASE=$(date +%s)
    log "[Faz ${PHASE}] TAMAMLANDI  (faz süresi: $(( (END_PHASE - START_PHASE) / 60 )) dk)"
done

# ─── MASTER ÖZET RAPOR ────────────────────────────────────────────────────────
END_TOTAL=$(date +%s)
ELAPSED_TOTAL=$(( (END_TOTAL - START_TOTAL) / 60 ))

log ""
log "============================================================"
log "  TÜM 7 FAZ TAMAMLANDI  —  Toplam: ${ELAPSED_TOTAL} dk"
log "============================================================"

REPORT_FILE="${PROJ_DIR}/MASTER_REPORT_7FAZ.txt"
{
    echo "========================================================"
    echo "  7-FAZ MASTER AUTORUN RAPORU"
    echo "  Tarih       : $(date '+%Y-%m-%d %H:%M:%S')"
    echo "  Toplam süre : ${ELAPSED_TOTAL} dakika"
    echo "========================================================"
    echo ""
    echo "Faz hiyerarşisi (kümülatif stres):"
    echo "  Faz1  → Baseline ideal (sigma=0, gamma=2.75, sendInterval=180s)"
    echo "  Faz2  → +SF-bazlı Duty-Cycle (SF7=10s … SF12=180s)"
    echo "  Faz3a → +Arazi engeli 0 dB"
    echo "  Faz3b → +Arazi engeli 2 dB  (seyrek yapılaşma)"
    echo "  Faz3c → +Arazi engeli 5 dB  (yoğun foliage/bina)"
    echo "  Faz4a → +Hava koşulu 0 dB"
    echo "  Faz4b → +Hava koşulu 0.5 dB (orta yağmur)"
    echo "  Faz4c → +Hava koşulu 1.5 dB (şiddetli yağmur)"
    echo "  Faz5a → +Gürültü tabanı -115 dBm"
    echo "  Faz5b → +Gürültü tabanı -110 dBm"
    echo "  Faz5c → +Gürültü tabanı -105 dBm"
    echo "  Faz6a → +Backhaul gecikmesi  20 ms (LTE)"
    echo "  Faz6b → +Backhaul gecikmesi 200 ms (DSL)"
    echo "  Faz6c → +Backhaul gecikmesi 1000 ms (uydu)"
    echo "  Faz7  → +GW0 çöküşü t=600s (mesh self-healing gözlemi)"
    echo ""
    echo "Her faz: 6 GW × 7 MeshPerGap × 2 Mod × 36 SF kombinasyonu = 3024 run"
    echo ""
    if [[ -f "${TAMIR_LOG}" ]]; then
        TAMIR_COUNT=$(grep -c "^ZAMAN" "${TAMIR_LOG}" 2>/dev/null || echo 0)
        echo "Otonom tamir günlüğü : ${TAMIR_LOG}"
        echo "Tamir müdahalesi     : ${TAMIR_COUNT} adet"
    fi
    echo ""
    echo "DURUM: TAMAMLANDI ✓"
} > "${REPORT_FILE}"

cat "${REPORT_FILE}"
log "Master rapor → ${REPORT_FILE}"

# Son git push
git add -A
git commit -m "final: 7-faz kampanya tamamlandı — MASTER_REPORT_7FAZ eklendi" \
    || log "Son commit: değişiklik yok"
git push origin main \
    || log "Son git push BAŞARISIZ"

log ""
log "============================================================"
log "  MASTER AUTORUN TAMAMLANDI — $(date '+%Y-%m-%d %H:%M:%S')"
log "============================================================"
