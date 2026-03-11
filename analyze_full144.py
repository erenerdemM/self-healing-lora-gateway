#!/usr/bin/env python3
"""
analyze_full144.py — Arazi1_Faz2_Full144 SCA Analiz Scripti
=============================================================
Kullanım: python3 analyze_full144.py [--results-dir PATH]

Üretilen Raporlar:
  1. Sigma Etkisi      — rcvBelowSensitivity oranı vs weatherSigma
  2. SF Darboğazı      — SF7 sensör + SF12 mesh kombinasyonunda drop oranları
  3. En iyi/kötü DER  — tüm 144 kombinasyon sıralaması
"""

import os
import re
import sys
import argparse
from collections import defaultdict

# ── Argüman parse ─────────────────────────────────────────────────────────────
parser = argparse.ArgumentParser()
parser.add_argument("--results-dir", default=os.path.join(os.path.dirname(__file__), "results"),
                    help="OMNeT++ results dizini (varsayılan: ./results)")
args = parser.parse_args()
RESULTS_DIR = args.results_dir
CONFIG = "Arazi1_Faz2_Full144"

# ── SCA dosyalarını bul ───────────────────────────────────────────────────────
sca_files = sorted([
    os.path.join(RESULTS_DIR, f)
    for f in os.listdir(RESULTS_DIR)
    if f.startswith(CONFIG) and f.endswith(".sca")
])

if not sca_files:
    print(f"HATA: {RESULTS_DIR}/ dizininde '{CONFIG}-*.sca' dosyası bulunamadı.")
    print("Önce: bash run_full144.sh  ile simülasyonları çalıştırın.")
    sys.exit(1)

print(f"Bulunan SCA dosyaları: {len(sca_files)}")

# ── SCA ayrıştırıcı ───────────────────────────────────────────────────────────
def parse_sca(filepath):
    """SCA dosyasından itervar'ları ve scalar değerleri oku."""
    itervars = {}
    scalars  = defaultdict(dict)

    with open(filepath, "r", encoding="utf-8", errors="replace") as f:
        for line in f:
            line = line.strip()

            # itervar satırı: "itervar sensorSF 7"
            if line.startswith("itervar "):
                parts = line.split(None, 2)
                if len(parts) == 3:
                    itervars[parts[1]] = parts[2].strip()

            # scalar satırı: "scalar <module> <statname> <value>"
            elif line.startswith("scalar "):
                parts = line.split(None, 3)
                if len(parts) == 4:
                    module, stat, value = parts[1], parts[2], parts[3]
                    # Tırnak içindeki stat adını temizle
                    stat_clean = stat.strip('"')
                    try:
                        scalars[module][stat_clean] = float(value)
                    except ValueError:
                        scalars[module][stat_clean] = value

    return itervars, scalars


# ── Tüm SCA dosyalarını oku ───────────────────────────────────────────────────
# Sütunlar: sensorSF, meshSF, weatherSigma, + metrikler
records = []

for sca_path in sca_files:
    itervars, scalars = parse_sca(sca_path)

    # İterasyon değişkenleri
    try:
        sensor_sf  = int(itervars.get("sensorSF", 0))
        mesh_sf    = int(itervars.get("meshSF", 0))
        w_sigma    = float(itervars.get("weatherSigma", 0.0))
    except (ValueError, KeyError):
        print(f"  UYARI: itervar eksik → {os.path.basename(sca_path)}")
        continue

    # ── Gönderilen paket sayısı (tüm sensörler) ───────────────────────────────
    total_sent = 0
    for i in range(5):
        mac_mod  = f"LoraMeshNetworkArazi1.sensor[{i}].LoRaNic.mac"
        radio_tx = f"LoraMeshNetworkArazi1.sensor[{i}].LoRaNic.radio.transmitter"
        # numSent (MAC seviyesi) veya LoRaTransmissionCreated:count (radio)
        sent = scalars.get(mac_mod, {}).get("numSent",
               scalars.get(radio_tx, {}).get("LoRaTransmissionCreated:count", 0))
        total_sent += int(sent)

    # ── NS1 alınan (GW1 backhaul üzerinden, sadece t<30s SENARYO A) ───────────
    ns1_mod = "LoraMeshNetworkArazi1.networkServer1.app[0]"
    ns1_recv = int(scalars.get(ns1_mod, {}).get("totalReceivedPackets", 0))

    # ── NS2 alınan (GW2 üzerinden; t>30s SENARYO B mesh relay kaydolur) ───────
    ns2_mod = "LoraMeshNetworkArazi1.networkServer2.app[0]"
    ns2_recv = int(scalars.get(ns2_mod, {}).get("totalReceivedPackets", 0))

    total_recv  = ns1_recv + ns2_recv
    der         = (total_recv / total_sent) if total_sent > 0 else float("nan")

    # ── GW1 radio: rcvBelowSensitivity ────────────────────────────────────────
    gw1_radio = "LoraMeshNetworkArazi1.hybridGW1.LoRaGWNic.radio.receiver"
    gw1_rcv_below = int(scalars.get(gw1_radio, {}).get("rcvBelowSensitivity", 0))

    # GW1 toplam alım girişimi (correct + below sensitivity + collision)
    gw1_radio_main = "LoraMeshNetworkArazi1.hybridGW1.LoRaGWNic.radio"
    gw1_reception_started = int(scalars.get(gw1_radio_main, {}).get(
        "LoRaGWRadioReceptionStarted:count", gw1_rcv_below + 1))
    rcv_below_rate = (gw1_rcv_below / gw1_reception_started
                      if gw1_reception_started > 0 else float("nan"))

    # GW2 aynısı
    gw2_radio = "LoraMeshNetworkArazi1.hybridGW2.LoRaGWNic.radio.receiver"
    gw2_rcv_below = int(scalars.get(gw2_radio, {}).get("rcvBelowSensitivity", 0))

    # ── GW1 RoutingAgent: drop ve congestion ──────────────────────────────────
    ra1_mod = "LoraMeshNetworkArazi1.hybridGW1.routingAgent"
    gw1_dropped = int(scalars.get(ra1_mod, {}).get("droppedPacket:count", 0))
    gw1_congestion = int(scalars.get(ra1_mod, {}).get("congestionEvent:count", 0))
    gw1_drop_rate = (gw1_dropped / total_sent) if total_sent > 0 else float("nan")

    # ── GW1 DER (radio seviyesi) ───────────────────────────────────────────────
    gw1_radio_der = scalars.get(gw1_radio_main, {}).get("DER - Data Extraction Rate", float("nan"))

    records.append({
        "sensorSF":        sensor_sf,
        "meshSF":          mesh_sf,
        "weatherSigma":    w_sigma,
        "total_sent":      total_sent,
        "ns1_recv":        ns1_recv,
        "ns2_recv":        ns2_recv,
        "total_recv":      total_recv,
        "DER":             der,
        "gw1_rcvBelow":    gw1_rcv_below,
        "gw2_rcvBelow":    gw2_rcv_below,
        "rcvBelowRate":    rcv_below_rate,
        "gw1_dropped":     gw1_dropped,
        "gw1_congestion":  gw1_congestion,
        "gw1_drop_rate":   gw1_drop_rate,
        "gw1_radio_DER":   gw1_radio_der,
        "file":            os.path.basename(sca_path),
    })

if not records:
    print("HATA: Hiçbir kayıt okunamadı.")
    sys.exit(1)

print(f"Başarıyla okunan kayıt sayısı: {len(records)}/{len(sca_files)}")
print()

# =============================================================================
# ANALİZ 1: Sigma Etkisi — weatherSigma arttıkça rcvBelowSensitivity artışı
# =============================================================================
print("=" * 70)
print("ANALİZ 1: HAVASIGMASı ETKİSİ — rcvBelowSensitivity Oranı vs Sigma")
print("=" * 70)

sigma_stats = defaultdict(lambda: {"below_sum": 0, "below_rate_sum": 0.0, "count": 0})
for r in records:
    ws = r["weatherSigma"]
    sigma_stats[ws]["below_sum"]      += r["gw1_rcvBelow"]
    sigma_stats[ws]["below_rate_sum"] += r["rcvBelowRate"] if r["rcvBelowRate"] == r["rcvBelowRate"] else 0
    sigma_stats[ws]["count"]          += 1

print(f"\n{'σ (sigma)':<12} {'Ort. rcvBelow (abs)':<24} {'Ort. rcvBelow/total (%)':<26} {'N run'}")
print("-" * 70)
for ws in sorted(sigma_stats):
    s = sigma_stats[ws]
    avg_below      = s["below_sum"] / s["count"]
    avg_below_rate = s["below_rate_sum"] / s["count"] * 100
    print(f"{ws:<12.1f} {avg_below:<24.1f} {avg_below_rate:<26.1f} {s['count']}")

# =============================================================================
# ANALİZ 2: SF Darboğazı — "Hızlı Sensör + Yavaş Mesh" kombinasyonu
# =============================================================================
print()
print("=" * 70)
print("ANALİZ 2: SF DARBOĞAZI — sensorSF=7 + meshSF=12 kombinasyonu")
print("  (GW1 kuyruğu dolar, mesh zinciri SF12 ile yavaş → drop artışı)")
print("=" * 70)

# Her (sensorSF, meshSF) kombinasyonu için sigma bazlı özet
combo_stats = defaultdict(lambda: {
    "drop_sum": 0, "congestion_sum": 0, "drop_rate_sum": 0.0, "count": 0, "DER_sum": 0.0
})
for r in records:
    key = (r["sensorSF"], r["meshSF"])
    combo_stats[key]["drop_sum"]        += r["gw1_dropped"]
    combo_stats[key]["congestion_sum"]  += r["gw1_congestion"]
    combo_stats[key]["drop_rate_sum"]   += r["gw1_drop_rate"] if r["gw1_drop_rate"] == r["gw1_drop_rate"] else 0
    combo_stats[key]["DER_sum"]         += r["DER"] if r["DER"] == r["DER"] else 0
    combo_stats[key]["count"]           += 1

# Sadece anlaşılır kombinasyonları göster (sensorSF ∈ {7,12}, meshSF ∈ {7,12})
print(f"\n{'sensorSF':<10} {'meshSF':<10} {'Ort. GW1 Drop':<16} {'Ort. Drop%':<14} {'Ort. CongEv':<14} {'Ort. DER'}")
print("-" * 70)
for sF in [7, 12]:
    for mSF in [7, 12]:
        key = (sF, mSF)
        if key in combo_stats:
            s = combo_stats[key]
            avg_drop  = s["drop_sum"]       / s["count"]
            avg_dp    = s["drop_rate_sum"]  / s["count"] * 100
            avg_cong  = s["congestion_sum"] / s["count"]
            avg_der   = s["DER_sum"]        / s["count"]
            label = " ← DARBOĞAZ" if sF == 7 and mSF == 12 else ""
            print(f"SF{sF:<7}   SF{mSF:<7}   {avg_drop:<16.1f} {avg_dp:<14.1f} {avg_cong:<14.1f} {avg_der:.3f}{label}")

print()
print("Tüm sensorSF × meshSF kombinasyonları (sigma ortalaması):")
print(f"\n{'sensorSF/meshSF':<18}", end="")
for mSF in [7, 8, 9, 10, 11, 12]:
    print(f"  mSF={mSF:<4}", end="")
print()
print("-" * 88)
for sF in [7, 8, 9, 10, 11, 12]:
    print(f"  sensorSF={sF:<7}", end="")
    for mSF in [7, 8, 9, 10, 11, 12]:
        key = (sF, mSF)
        if key in combo_stats:
            avg_drop_rate = combo_stats[key]["drop_rate_sum"] / combo_stats[key]["count"] * 100
            print(f"  {avg_drop_rate:>6.1f}% ", end="")
        else:
            print("    N/A  ", end="")
    print()
print("(GW1 routingAgent droppedPacket oranı, sigma ortalaması)")

# =============================================================================
# ANALİZ 3: En iyi ve en kötü DER — tüm 144 kombinasyon sıralaması
# =============================================================================
print()
print("=" * 70)
print("ANALİZ 3: EN İYİ / EN KÖTÜ DER (Teslimat Oranı) — 144 Kombinasyon")
print("=" * 70)

valid_records = [r for r in records if r["DER"] == r["DER"]]  # nan filtrele
valid_records.sort(key=lambda r: r["DER"], reverse=True)

print(f"\n{'Sıra':<6} {'sensorSF':<10} {'meshSF':<9} {'σ':<7} "
      f"{'Gönderilen':<12} {'NS1':<7} {'NS2':<7} {'Toplam':<9} {'DER':>7}  {'GW1 Drop%'}")
print("-" * 85)

# İlk 10 (en iyi)
print("  [ EN İYİ 10 ]")
for i, r in enumerate(valid_records[:10], 1):
    dp = r["gw1_drop_rate"] * 100 if r["gw1_drop_rate"] == r["gw1_drop_rate"] else float("nan")
    print(f"  {i:<5} SF{r['sensorSF']:<7}  SF{r['meshSF']:<6}  {r['weatherSigma']:<7.1f} "
          f"{r['total_sent']:<12} {r['ns1_recv']:<7} {r['ns2_recv']:<7} {r['total_recv']:<9} "
          f"{r['DER']:>7.3f}  {dp:>6.1f}%")

print()
# Son 10 (en kötü)
print("  [ EN KÖTÜ 10 ]")
for i, r in enumerate(reversed(valid_records[-10:]), 1):
    dp = r["gw1_drop_rate"] * 100 if r["gw1_drop_rate"] == r["gw1_drop_rate"] else float("nan")
    rank = len(valid_records) - 10 + i
    print(f"  {rank:<5} SF{r['sensorSF']:<7}  SF{r['meshSF']:<6}  {r['weatherSigma']:<7.1f} "
          f"{r['total_sent']:<12} {r['ns1_recv']:<7} {r['ns2_recv']:<7} {r['total_recv']:<9} "
          f"{r['DER']:>7.3f}  {dp:>6.1f}%")

# ── Özet İstatistik ───────────────────────────────────────────────────────────
print()
print("=" * 70)
print("ÖZET")
print("=" * 70)
all_der = [r["DER"] for r in valid_records]
all_drop = [r["gw1_drop_rate"] * 100 for r in valid_records if r["gw1_drop_rate"] == r["gw1_drop_rate"]]
all_below = [r["rcvBelowRate"] * 100 for r in valid_records if r["rcvBelowRate"] == r["rcvBelowRate"]]

def _fmt(vals, label, fmt=".3f"):
    if not vals:
        print(f"  {label}: N/A")
        return
    print(f"  {label}: min={min(vals):{fmt}}  max={max(vals):{fmt}}  "
          f"ort={sum(vals)/len(vals):{fmt}}")

_fmt(all_der,   "DER (teslimat oranı)")
_fmt(all_drop,  "GW1 drop oranı (%)", ".1f")
_fmt(all_below, "rcvBelowSensitivity oranı (%)", ".1f")

print()
best  = valid_records[0]
worst = valid_records[-1]
print(f"  En iyi DER : SF{best['sensorSF']} / SF{best['meshSF']} / σ={best['weatherSigma']:.1f}"
      f"  →  DER={best['DER']:.3f}  (NS1={best['ns1_recv']}, NS2={best['ns2_recv']})")
print(f"  En kötü DER: SF{worst['sensorSF']} / SF{worst['meshSF']} / σ={worst['weatherSigma']:.1f}"
      f"  →  DER={worst['DER']:.3f}  (NS1={worst['ns1_recv']}, NS2={worst['ns2_recv']})")
print()

# ── CSV dışa aktar ────────────────────────────────────────────────────────────
csv_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "full144_results.csv")
with open(csv_path, "w", encoding="utf-8") as f:
    header = ("sensorSF,meshSF,weatherSigma,total_sent,ns1_recv,ns2_recv,total_recv,"
              "DER,gw1_rcvBelow,gw2_rcvBelow,rcvBelowRate,gw1_dropped,gw1_congestion,"
              "gw1_drop_rate,gw1_radio_DER,file\n")
    f.write(header)
    for r in sorted(records, key=lambda x: (x["sensorSF"], x["meshSF"], x["weatherSigma"])):
        f.write(",".join(str(r[k]) for k in [
            "sensorSF", "meshSF", "weatherSigma", "total_sent", "ns1_recv", "ns2_recv",
            "total_recv", "DER", "gw1_rcvBelow", "gw2_rcvBelow", "rcvBelowRate",
            "gw1_dropped", "gw1_congestion", "gw1_drop_rate", "gw1_radio_DER", "file"
        ]) + "\n")
print(f"CSV dışa aktarıldı: {csv_path}")
