#!/bin/bash
# =============================================================================
# run_faz123.sh — Arazi1_Faz1_2_3_Bindirme Batch Runner (144 Run)
# =============================================================================
# Kullanım: bash run_faz123.sh [--jobs N] [--from RUN] [--to RUN]
#   --jobs N   : paralel iş sayısı (varsayılan: 1, tavsiye: CPU_CORES/2)
#   --from R   : başlangıç run numarası (varsayılan: 0)
#   --to   R   : bitiş run numarası dahil (varsayılan: 143)
# Örnek: bash run_faz123.sh --jobs 4
#
# AMAÇ: GW1 hiç kesilmeden, saf hava şartı (sigma) etkisini ölç
#   sensorSF × meshSF × weatherSigma = 6×6×4 = 144 run
# =============================================================================

set -euo pipefail

PROJ_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BIN="${PROJ_DIR}/lora_mesh_projesi_dbg"
OMNETPP_DIR="/home/eren/Desktop/bitirme_lora_kod/omnetpp-6.0-linux-x86_64/omnetpp-6.0"
FLORA="/home/eren/Desktop/bitirme_lora_kod/workspace/flora"
INET="/home/eren/Desktop/bitirme_lora_kod/workspace/inet4.4"
CONFIG="Arazi1_Faz1_2_3_Bindirme"
TOTAL=144
LOG_DIR="${PROJ_DIR}/logs_faz123"

export LD_LIBRARY_PATH="${OMNETPP_DIR}/lib:${FLORA}/src:${INET}/src${LD_LIBRARY_PATH:+:$LD_LIBRARY_PATH}"

# ── Argüman parse ─────────────────────────────────────────────────────────────
JOBS=1
FROM_RUN=0
TO_RUN=$((TOTAL - 1))

while [[ $# -gt 0 ]]; do
    case $1 in
        --jobs)  JOBS="$2";     shift 2 ;;
        --from)  FROM_RUN="$2"; shift 2 ;;
        --to)    TO_RUN="$2";   shift 2 ;;
        *) echo "Bilinmeyen argüman: $1"; exit 1 ;;
    esac
done

mkdir -p "${LOG_DIR}"
cd "${PROJ_DIR}"

echo "=== Arazi1_Faz1_2_3_Bindirme Batch Runner ==="
echo "Config   : ${CONFIG}"
echo "Toplam   : ${TOTAL} run (run ${FROM_RUN}..${TO_RUN})"
echo "Paralel  : ${JOBS} iş"
echo "Logs     : ${LOG_DIR}/"
echo ""

# ── Tek bir run'ı çalıştıran iç fonksiyon ─────────────────────────────────────
run_one() {
    local run=$1
    local log="${LOG_DIR}/run_${run}.log"
    local done_flag="${LOG_DIR}/run_${run}.done"

    # Resume: tamamlanmış run'ları atla
    if [[ -f "${done_flag}" ]]; then
        echo "[SKIP] run=${run} (daha önce tamamlandı)"
        return 0
    fi

    echo "[START] run=${run}/$(( TOTAL-1 ))"

    "${BIN}" -m -c "${CONFIG}" -r "${run}" -u Cmdenv \
        -n ".:${FLORA}/src:${INET}/src" \
        > "${log}" 2>&1

    local exit_code=$?
    if [[ ${exit_code} -eq 0 ]]; then
        touch "${done_flag}"
        (
            flock -x 200
            DONE_COUNT=$(ls "${LOG_DIR}"/*.done 2>/dev/null | wc -l)
            echo "[DONE ] run=${run}  (${DONE_COUNT}/${TOTAL} tamamlandı)"
        ) 200>"${LOG_DIR}/.lock"
    else
        echo "[FAIL ] run=${run} — exit code: ${exit_code} — log: ${log}"
        return ${exit_code}
    fi
}

export -f run_one
export BIN CONFIG FLORA INET LOG_DIR TOTAL PROJ_DIR

WALL_START=$(date +%s)

if [[ ${JOBS} -gt 1 ]] && command -v parallel &>/dev/null; then
    echo "GNU Parallel ile ${JOBS} paralel iş başlatılıyor..."
    seq "${FROM_RUN}" "${TO_RUN}" | parallel -j "${JOBS}" --line-buffer run_one {}
else
    if [[ ${JOBS} -gt 1 ]]; then
        echo "UYARI: GNU Parallel bulunamadı, sıralı mod kullanılıyor."
    fi
    FAILED=()
    for run in $(seq "${FROM_RUN}" "${TO_RUN}"); do
        run_one "${run}" || FAILED+=("${run}")
    done
    if [[ ${#FAILED[@]} -gt 0 ]]; then
        echo ""
        echo "HATA: Şu run'lar başarısız oldu: ${FAILED[*]}"
        echo "Log dosyaları: ${LOG_DIR}/run_N.log"
        exit 1
    fi
fi

WALL_END=$(date +%s)
ELAPSED=$(( WALL_END - WALL_START ))

echo ""
echo "=== Tüm ${TOTAL} run tamamlandı ==="
echo "Toplam süre: $(( ELAPSED / 60 )) dak $(( ELAPSED % 60 )) sn"
echo "SCA dosyaları: ${PROJ_DIR}/results/${CONFIG}-*.sca"
echo ""
echo "Analiz için:"
echo "  python3 ${PROJ_DIR}/analyze_faz123.py"
