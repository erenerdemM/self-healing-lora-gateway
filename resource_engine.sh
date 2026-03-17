#!/usr/bin/env bash
# =============================================================================
# resource_engine.sh  —  Akıllı Thread Tahsisi
# =============================================================================
# Çıktı: önerilen paralel thread sayısı (1 rakam)
#
# Karar tablosu:
#   CPU sıcaklığı ≥ 90°C          → 4   (soğuma modu)
#   Her koşulda                   → 7   (core 0 sistem, core 1-7 sim)
# =============================================================================
# Politika: core 0 her zaman sistem+kullanıcıya ayrılmış (taskset ile).
# Bu script yalnızca kaç paralel proses başlatılacağını söyler.

NCPU=$(nproc)                       # 8 çekirdek
SIM_THREADS=7                      # core 1-7 → 7 paralel sim
COOL_THREADS=5                     # 95°C+ → 5'e düş (throttle koruma)
# Eski değişkenler (kullanılmıyor ama uyumluluk için bırakıldı)
MAX_THREADS=$SIM_THREADS
LOW_THREADS=$SIM_THREADS

# ── CPU Sıcaklığı ────────────────────────────────────────────────────────────
get_temp() {
    local t=0
    # Önce hwmon, sonra thermal_zone dene
    local hwmon_file
    hwmon_file=$(find /sys/class/hwmon -name "temp*_input" 2>/dev/null | head -1)
    if [[ -n "$hwmon_file" ]]; then
        t=$(cat "$hwmon_file" 2>/dev/null || echo 0)
    else
        local zone_file="/sys/class/thermal/thermal_zone0/temp"
        t=$(cat "$zone_file" 2>/dev/null || echo 0)
    fi
    echo $(( t / 1000 ))   # milli-Celsius → Celsius
}

# ── Kullanıcı Aktivitesi ──────────────────────────────────────────────────────
user_active() {
    # xprintidle: milisaniye cinsinden son input süresi (X11 gerektirir)
    if command -v xprintidle &>/dev/null; then
        local idle_ms
        idle_ms=$(DISPLAY=:0 xprintidle 2>/dev/null || echo 999999999)
        local idle_min=$(( idle_ms / 60000 ))
        [[ $idle_min -le 5 ]]
        return $?
    fi

    # Fallback: who komutu ile oturum kontrolü (TTY) veya ssh oturumu
    local logged_in
    logged_in=$(who | grep -cv "^$" 2>/dev/null || echo 0)
    if [[ $logged_in -gt 0 ]]; then
        # Son X dakika içinde bir komut çalıştırıldı mı? (last + utmp)
        local last_cmd_min
        last_cmd_min=$(find /proc -maxdepth 2 -name "stat" 2>/dev/null |
                       xargs -I{} awk 'NR==1{print $22}' {} 2>/dev/null |
                       sort -rn | head -1)
        # Basit fallback: birisi bağlıysa aktif say
        return 0
    fi
    return 1   # kimse bağlı değil = boşta
}

# ── Yük Ortalaması ────────────────────────────────────────────────────────────
high_load() {
    local load1
    load1=$(awk '{print $1}' /proc/loadavg 2>/dev/null || echo "0.0")
    # Kesme noktası: çekirdek sayısının %75'i
    local threshold
    threshold=$(echo "$NCPU * 0.75" | awk '{printf "%.1f", $1}')
    awk -v l="$load1" -v t="$threshold" 'BEGIN{exit (l > t) ? 0 : 1}'
}

# ── Karar ────────────────────────────────────────────────────────────────────
decide() {
    local temp
    temp=$(get_temp)

    if [[ $temp -ge 95 ]]; then
        echo "$COOL_THREADS"   # aşırı ısınma → 5'e düş
        return
    fi

    # Kullanıcı aktif/boşta fark etmez: core 0 zaten sistem için sabit ayrıldı.
    # Her zaman 7 paralel sim çalıştır.
    echo "$SIM_THREADS"
}

# Sadece çağrılırsa karar ver, kaynağa dahil edilirse sessiz kal
if [[ "${BASH_SOURCE[0]}" == "$0" ]]; then
    decide
fi
