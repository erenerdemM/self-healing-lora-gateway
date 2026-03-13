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

sigma_stats = defaultdict(lambda: {
    "gw1_below": 0, "gw2_below": 0,
    "der_sum": 0.0, "cong_sum": 0,
    "ns1_sum": 0, "ns2_sum": 0, "tx_sum": 0,
    "count": 0
})
for r in records:
    ws = r["weatherSigma"]
    sigma_stats[ws]["gw1_below"] += r["gw1_rcvBelow"]
    sigma_stats[ws]["gw2_below"] += r["gw2_rcvBelow"]
    sigma_stats[ws]["der_sum"]   += r["DER"] if r["DER"] == r["DER"] else 0
    sigma_stats[ws]["cong_sum"]  += r["gw1_congestion"]
    sigma_stats[ws]["ns1_sum"]   += r["ns1_recv"]
    sigma_stats[ws]["ns2_sum"]   += r["ns2_recv"]
    sigma_stats[ws]["tx_sum"]    += r["total_sent"]
    sigma_stats[ws]["count"]     += 1

print(f"\n{'σ':>5}  {'N':>3}  {'Σ TX':>7}  {'Σ NS1':>6}  {'Σ NS2':>6}  "
      f"{'Ort.DER%':>9}  {'GW1↓Ort':>8}  {'GW2↓Ort':>8}  {'Cong/run':>9}")
print("-" * 72)
for ws in sorted(sigma_stats):
    s = sigma_stats[ws]
    n          = s["count"]
    avg_der    = s["der_sum"] / n * 100
    avg_gw1    = s["gw1_below"] / n
    avg_gw2    = s["gw2_below"] / n
    avg_cong   = s["cong_sum"]  / n
    print(f"  {ws:>3.1f}  {n:>3}  {s['tx_sum']:>7}  {s['ns1_sum']:>6}  {s['ns2_sum']:>6}  "
          f"{avg_der:>9.1f}  {avg_gw1:>8.1f}  {avg_gw2:>8.1f}  {avg_cong:>9.1f}")
print()
print("  NOT: GW1↓ = sensör→GW1 hassasiyet altı paket (doğrudan link)")
print("       GW2↓ = meshNode→GW2 hassasiyet altı paket (mesh relay link)")
print("       GW2↓ >> GW1↓ → sigma etkisi mesh relay hattını daha çok vuruyor")
print("       Cong = GW1 routingAgent congestionEvent ortalaması (run başı)")

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
print(f"\n{'sensorSF':<8} {'meshSF':<7} {'Cong/run':>8}  {'DER%':>6}  {'Not'}")
print("-" * 50)
for sF in [7, 12]:
    for mSF in [7, 12]:
        key = (sF, mSF)
        if key in combo_stats:
            s = combo_stats[key]
            avg_cong  = s["congestion_sum"] / s["count"]
            avg_der   = s["DER_sum"]        / s["count"] * 100
            label = "← DARBOĞAZ (FF>SF12 relay)" if sF == 7 and mSF == 12 else ""
            print(f"SF{sF:<5}   SF{mSF:<5}   {avg_cong:>8.1f}  {avg_der:>6.1f}  {label}")

print()
print("Tüm sensorSF × meshSF kombinasyonları — Ortalama GW1 CongestionEvent/run:")
print(f"\n{'sSF/mSF':<10}", end="")
for mSF in [7, 8, 9, 10, 11, 12]:
    print(f" mSF={mSF:<4}", end="")
print()
print("-" * 76)
for sF in [7, 8, 9, 10, 11, 12]:
    print(f"  sSF={sF:<5}", end="")
    for mSF in [7, 8, 9, 10, 11, 12]:
        key = (sF, mSF)
        if key in combo_stats:
            avg_cong = combo_stats[key]["congestion_sum"] / combo_stats[key]["count"]
            marker = "*" if sF <= 9 and mSF >= 11 else " "
            print(f" {avg_cong:>6.1f}{marker}", end="")
        else:
            print("   N/A  ", end="")
    print()
print("(* = 'Ferrari-sensör + Kamyon-relay' bölgesi — yüksek tıkanma beklenir)")
print("Açıklama: congestionEvent = GW1 routingAgent'ın SF12 relay yüzünden")
print("          iletimi geciktirme/bekletme olayı. Gerçek paket kaybı değil,")
print("          ancak yüksek değerler kuyruk doluluğuna işaret eder.")

# =============================================================================
# ANALİZ 3: En iyi ve en kötü DER — tüm 144 kombinasyon sıralaması
# =============================================================================
print()
print("=" * 70)
print("ANALİZ 3: EN İYİ / EN KÖTÜ DER (Teslimat Oranı) — 144 Kombinasyon")
print("=" * 70)

valid_records = [r for r in records if r["DER"] == r["DER"]]  # nan filtrele
valid_records.sort(key=lambda r: r["DER"], reverse=True)

print(f"\n  {'#':>3}  {'sSF':>4} {'mSF':>4}  {'σ':>4}  "
      f"{'TX':>5}  {'NS1':>4} {'NS2':>5} {'Tot':>5}  {'DER%':>6}  {'Cong':>4}")
print("  " + "-" * 48)

# İlk 5 (en iyi)
print("  [ EN İYİ 5 ]")
for i, r in enumerate(valid_records[:5], 1):
    print(f"  {i:>3}  SF{r['sensorSF']:<2} SF{r['meshSF']:<2}  {r['weatherSigma']:>4.1f}  "
          f"{int(r['total_sent']):>5}  {int(r['ns1_recv']):>4} {int(r['ns2_recv']):>5} "
          f"{int(r['total_recv']):>5}  {r['DER']*100:>6.1f}  {int(r['gw1_congestion']):>4}")

print()
# Son 5 (en kötü)
print("  [ EN KÖTÜ 5 ]")
for i, r in enumerate(reversed(valid_records[-5:]), 1):
    rank = len(valid_records) - 5 + i
    print(f"  {rank:>3}  SF{r['sensorSF']:<2} SF{r['meshSF']:<2}  {r['weatherSigma']:>4.1f}  "
          f"{int(r['total_sent']):>5}  {int(r['ns1_recv']):>4} {int(r['ns2_recv']):>5} "
          f"{int(r['total_recv']):>5}  {r['DER']*100:>6.1f}  {int(r['gw1_congestion']):>4}")

# ── Özet İstatistik ───────────────────────────────────────────────────────────
print()
print("=" * 70)
print("ÖZET")
print("=" * 70)
all_der = [r["DER"] for r in valid_records]
all_drop = [r["gw1_drop_rate"] * 100 for r in valid_records if r["gw1_drop_rate"] == r["gw1_drop_rate"]]
all_below = [r["rcvBelowRate"] * 100 for r in valid_records if r["rcvBelowRate"] == r["rcvBelowRate"]]

def _fmt(vals, label, fmt=".1f"):
    if not vals:
        print(f"  {label}: N/A")
        return
    print(f"  {label:<28}: min={min(vals):{fmt}}  max={max(vals):{fmt}}  "
          f"ort={sum(vals)/len(vals):{fmt}}")

all_der_pct = [d * 100 for d in all_der]
_fmt(all_der_pct, "DER% (teslimat oranı)")
_fmt(all_drop,    "GW1 drop oranı (%)")
_fmt(all_below,   "rcvBelowSensitivity oranı (%)")

print()
best  = valid_records[0]
worst = valid_records[-1]
print(f"  En iyi DER : SF{best['sensorSF']} + SF{best['meshSF']} / σ={best['weatherSigma']:.1f}"
      f"  →  DER={best['DER']*100:.1f}%  (NS1={int(best['ns1_recv'])}, NS2={int(best['ns2_recv'])})")
print(f"  En kötü DER: SF{worst['sensorSF']} + SF{worst['meshSF']} / σ={worst['weatherSigma']:.1f}"
      f"  →  DER={worst['DER']*100:.1f}%  (NS1={int(worst['ns1_recv'])}, NS2={int(worst['ns2_recv'])})")
print()
print("  NOT: DER = (NS1 + NS2 teslim alınan) / toplam sensör TX")
print("       İdeal DER=100% ama t=30s backhaul kesilişinde ve mesh gecikmesiyle")
print("       max teorik DER = 60s/120s = ~50% beklenir, ~40% iyi sonuc sayılır.")
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
