#!/bin/bash
# =============================================================================
# master_autorun.sh — Tüm Fazları Sırayla Çalıştırır ve Git Push Yapar
# =============================================================================
# Sıra: Faz 4 → 1 → 2 → 21 → 3
# Her faz: topoloji üret → simülasyon → organize → git push
# Sonunda: sudo poweroff
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
JOBS=8

# ─── Python ortamı ─────────────────────────────────────────────────────────
source "${VENV}/bin/activate"
export PYTHONUNBUFFERED=1

# ─── Faz sırası ───────────────────────────────────────────────────────────────
# Phase → run_script eşlemesi
declare -A RUN_SCRIPTS=(
    [4]="run_faz4.sh"
    [1]="run_massive.sh"
    [2]="run_faz2.sh"
    [21]="run_faz21.sh"
    [3]="run_faz3.sh"
)

# Etiketler (git commit mesajı için)
declare -A PHASE_LABELS=(
    [4]="Faz4 YasalSinir 180s"
    [1]="Faz1 Ideal 180s"
    [2]="Faz2 Beton7dB 180s"
    [21]="Faz21 Dogal 180s"
    [3]="Faz3 Gurultu 180s"
)

PHASE_ORDER=(4 1 2 21 3)

# ─── Yardımcı fonksiyon ───────────────────────────────────────────────────────
log() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $*" | tee -a "${LOG_FILE}"
}

die() {
    log "HATA: $*"
    exit 1
}

# ─── Başlangıç ────────────────────────────────────────────────────────────────
log "============================================================"
log "  MASTER AUTORUN BAŞLIYOR"
log "  Sıra: ${PHASE_ORDER[*]}"
log "  Jobs: ${JOBS}"
log "  Proje: ${PROJ_DIR}"
log "============================================================"
cd "${PROJ_DIR}"

START_TOTAL=$(date +%s)

# ─── HER FAZ ──────────────────────────────────────────────────────────────────
for PHASE in "${PHASE_ORDER[@]}"; do
    log ""
    log "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    log "  FAZ ${PHASE}: ${PHASE_LABELS[$PHASE]}"
    log "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

    START_PHASE=$(date +%s)

    # ── Adım 1: Topoloji Üret ────────────────────────────────────────────────
    log "[Faz ${PHASE}] Adım 1/3: Topoloji ve konfigürasyon üretiliyor..."
    python3 arge_scriptleri/topoloji_jenerator/generate_massive_topology.py \
        --phase "${PHASE}" \
        || die "Faz ${PHASE} — generate_massive_topology.py BAŞARISIZ"

    RUN_SCRIPT="${RUN_SCRIPTS[$PHASE]}"
    [[ -f "${PROJ_DIR}/${RUN_SCRIPT}" ]] \
        || die "Run script bulunamadı: ${RUN_SCRIPT}"

    log "[Faz ${PHASE}] Adım 1/3: Topoloji ✓ — ${RUN_SCRIPT} hazır"

    # ── Adım 2: Simülasyon ───────────────────────────────────────────────────
    log "[Faz ${PHASE}] Adım 2/3: Simülasyon başlatılıyor (--jobs ${JOBS})..."
    bash "${PROJ_DIR}/${RUN_SCRIPT}" --jobs "${JOBS}" \
        || die "Faz ${PHASE} — ${RUN_SCRIPT} BAŞARISIZ"

    END_SIM=$(date +%s)
    log "[Faz ${PHASE}] Adım 2/3: Simülasyon tamamlandı  ($(( (END_SIM - START_PHASE) / 60 )) dk)"

    # ── Adım 3: Organize & Arşiv ─────────────────────────────────────────────
    log "[Faz ${PHASE}] Adım 3/3: Analiz ve arşivleme..."
    python3 arge_scriptleri/veri_analiz/mega_organize_phase.py \
        --phase "${PHASE}" \
        || die "Faz ${PHASE} — mega_organize_phase.py BAŞARISIZ"

    log "[Faz ${PHASE}] Adım 3/3: Analiz tamamlandı ✓"

    # ── Git Push ──────────────────────────────────────────────────────────────
    log "[Faz ${PHASE}] Git commit + push..."
    git add -A
    git commit -m "data: ${PHASE_LABELS[$PHASE]} simülasyon tamamlandı" \
        || log "[Faz ${PHASE}] Git commit: değişiklik yok veya hata (devam ediliyor)"
    git push origin main \
        || log "[Faz ${PHASE}] Git push BAŞARISIZ — bağlantı sorunu olabilir, devam ediliyor"

    END_PHASE=$(date +%s)
    log "[Faz ${PHASE}] TAMAMLANDI  (toplam: $(( (END_PHASE - START_PHASE) / 60 )) dk)"
done

# ─── MASTER ÖZET RAPOR ────────────────────────────────────────────────────────
log ""
log "============================================================"
log "  TÜM FAZLAR TAMAMLANDI — MASTER RAPOR"
log "============================================================"

REPORT_FILE="${PROJ_DIR}/MASTER_REPORT.txt"
{
    echo "========================================================"
    echo "  MASTER AUTORUN RAPORU"
    echo "  Tarih: $(date '+%Y-%m-%d %H:%M:%S')"
    echo "  Toplam süre: $(( ($(date +%s) - START_TOTAL) / 60 )) dakika"
    echo "========================================================"
    echo ""
    echo "Çalışılan fazlar: 4 → 1 → 2 → 21 → 3"
    echo "sendInterval: 180s (BTK/KET SF12 %1 DC GlobalMax)"
    echo ""
    echo "Arşiv dizinleri:"
    for PHASE in "${PHASE_ORDER[@]}"; do
        case $PHASE in
            4)  echo "  Faz 4  → Faz4_YasalSinir_Final/" ;;
            1)  echo "  Faz 1  → Faz1_Ideal_YasalSinir_Final/" ;;
            2)  echo "  Faz 2  → Faz2_Beton7dB_YasalSinir_Final/" ;;
            21) echo "  Faz 21 → Faz21_Dogal_YasalSinir_Final/" ;;
            3)  echo "  Faz 3  → Faz3_Gurultu_YasalSinir_Final/" ;;
        esac
    done
    echo ""
    echo "Özet CSV'ler:"
    for csv_f in summary_faz*.csv; do
        [[ -f "${PROJ_DIR}/${csv_f}" ]] && echo "  ${csv_f}"
    done
    echo ""
    echo "DURUM: TAMAMLANDI ✓"
} > "${REPORT_FILE}"

cat "${REPORT_FILE}"
log "Master rapor → ${REPORT_FILE}"

# Son git push
git add -A
git commit -m "final: tüm fazlar tamamlandı — MASTER_REPORT eklendi" \
    || log "Son commit: değişiklik yok"
git push origin main \
    || log "Son git push BAŞARISIZ"

log ""
log "============================================================"
log "  TÜM FAZLAR + GIT PUSH TAMAMLANDI"
log "  Bilgisayar kapatılıyor..."
log "============================================================"

sleep 5
sudo poweroff
