#!/usr/bin/env python3
"""
analyze_faz123.py — Arazi1_Faz1_2_3_Bindirme Analizi
======================================================
AMAÇ: GW1 hiç kesilmezken (backhaulCutTime=-1s), sadece
      weatherSigma'nın paket teslimatına etkisini ölçmek.

GİRDİ : results/Arazi1_Faz1_2_3_Bindirme-*.sca  (144 dosya)

ÇIKTI :
  Rapor 1 — Hava × SF Matrisi       : hava_sf_matrisi.txt
  Rapor 2 — Sigma Gruplarına Göre DER: sigma_der_raporu.txt
  Ham CSV                             : faz123_raw.csv
"""

import re
import sys
import glob
import os
import csv
from collections import defaultdict

# ── Yollar ────────────────────────────────────────────────────────────────────
SCRIPT_DIR   = os.path.dirname(os.path.abspath(__file__))
RESULTS_DIR  = os.path.join(SCRIPT_DIR, "results")
CONFIG       = "Arazi1_Faz1_2_3_Bindirme"
PATTERN      = os.path.join(RESULTS_DIR, f"{CONFIG}-*.sca")

OUT_MATRIX   = os.path.join(SCRIPT_DIR, "hava_sf_matrisi.txt")
OUT_SIGMA    = os.path.join(SCRIPT_DIR, "sigma_der_raporu.txt")
OUT_CSV      = os.path.join(SCRIPT_DIR, "faz123_raw.csv")

# ── SCA Parser ────────────────────────────────────────────────────────────────
def parse_sca(path: str) -> dict | None:
    """Tek bir .sca dosyasını parse eder; gerekli tüm değerleri döndürür."""
    rec = {
        "sensorSF": None, "meshSF": None, "weatherSigma": None,
        # sensor TX
        "s0_sent": 0, "s1_sent": 0, "s2_sent": 0, "s3_sent": 0, "s4_sent": 0,
        # GW radyo
        "gw1_below": 0.0,
        "gw2_below": 0.0,
        # NS alınan
        "ns1_rcv": 0,
        "ns2_rcv": 0,
        # GW routingAgent
        "gw1_dropped": 0,
        "gw1_congestion": 0,
    }

    try:
        with open(path, encoding="utf-8", errors="replace") as fh:
            for line in fh:
                # itervar satırları
                if line.startswith("itervar "):
                    parts = line.split(None, 2)
                    if len(parts) >= 3:
                        key, val = parts[1], parts[2].strip()
                        if key == "sensorSF":
                            rec["sensorSF"] = int(val)
                        elif key == "meshSF":
                            rec["meshSF"] = int(val)
                        elif key == "weatherSigma":
                            rec["weatherSigma"] = float(val)
                    continue

                # scalar satırları
                if not line.startswith("scalar "):
                    continue

                m = re.match(
                    r'^scalar\s+(\S+)\s+"?([^"]+?)"?\s+([-\d.]+(?:e[+-]?\d+)?)\s*$',
                    line
                )
                if not m:
                    continue
                module, stat, raw_val = m.group(1), m.group(2).strip(), m.group(3)
                try:
                    val = float(raw_val)
                except ValueError:
                    continue

                # sensor numSent
                sm = re.match(
                    r'LoraMeshNetworkArazi1\.sensor\[(\d)\]\.LoRaNic\.mac$',
                    module
                )
                if sm and stat == "numSent":
                    idx = int(sm.group(1))
                    rec[f"s{idx}_sent"] = int(val)
                    continue

                # hybridGW1/GW2 radio.receiver rcvBelowSensitivity
                if module == "LoraMeshNetworkArazi1.hybridGW1.LoRaGWNic.radio.receiver" \
                        and stat == "rcvBelowSensitivity":
                    rec["gw1_below"] = val
                    continue
                if module == "LoraMeshNetworkArazi1.hybridGW2.LoRaGWNic.radio.receiver" \
                        and stat == "rcvBelowSensitivity":
                    rec["gw2_below"] = val
                    continue

                # NS totalReceivedPackets
                if module == "LoraMeshNetworkArazi1.networkServer1.app[0]" \
                        and stat == "totalReceivedPackets":
                    rec["ns1_rcv"] = int(val)
                    continue
                if module == "LoraMeshNetworkArazi1.networkServer2.app[0]" \
                        and stat == "totalReceivedPackets":
                    rec["ns2_rcv"] = int(val)
                    continue

                # GW1 routingAgent droppedPacket, congestion
                if module == "LoraMeshNetworkArazi1.hybridGW1.routingAgent":
                    if stat == "droppedPacket:count":
                        rec["gw1_dropped"] = int(val)
                    elif stat == "congestionEvent:count":
                        rec["gw1_congestion"] = int(val)

    except OSError as exc:
        print(f"HATA: dosya okunamadı: {path} → {exc}", file=sys.stderr)
        return None

    if any(rec[k] is None for k in ("sensorSF", "meshSF", "weatherSigma")):
        print(f"UYARI: itervar eksik → {os.path.basename(path)}", file=sys.stderr)
        return None

    return rec


# ── İstatistik araçları ───────────────────────────────────────────────────────
def safe_div(a, b):
    return a / b if b else 0.0


def pct(a, b):
    return round(safe_div(a, b) * 100, 2)


# ── Ana analiz ────────────────────────────────────────────────────────────────
def main():
    sca_files = sorted(glob.glob(PATTERN))
    if not sca_files:
        print(f"HATA: '{PATTERN}' eşleşmesi bulunamadı.", file=sys.stderr)
        sys.exit(1)

    print(f"Bulunan SCA dosyası: {len(sca_files)}")

    rows = []
    for path in sca_files:
        rec = parse_sca(path)
        if rec:
            rows.append(rec)

    print(f"Başarıyla parse edilen: {len(rows)} / {len(sca_files)}")
    if not rows:
        print("HATA: Parse edilecek veri yok.", file=sys.stderr)
        sys.exit(1)

    # Türetilmiş sütunlar
    for r in rows:
        r["total_tx"]   = r["s0_sent"] + r["s1_sent"] + r["s2_sent"] + \
                          r["s3_sent"] + r["s4_sent"]
        r["total_below"]= r["gw1_below"] + r["gw2_below"]
        r["total_rcv"]  = r["ns1_rcv"]   + r["ns2_rcv"]
        r["der_pct"]    = pct(r["total_rcv"], r["total_tx"])

    # Ham CSV yaz
    fieldnames = [
        "sensorSF", "meshSF", "weatherSigma",
        "s0_sent","s1_sent","s2_sent","s3_sent","s4_sent","total_tx",
        "gw1_below","gw2_below","total_below",
        "ns1_rcv","ns2_rcv","total_rcv","der_pct",
        "gw1_dropped","gw1_congestion",
    ]
    with open(OUT_CSV, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames, extrasaction="ignore")
        w.writeheader()
        w.writerows(sorted(rows, key=lambda r: (r["sensorSF"], r["meshSF"], r["weatherSigma"])))
    print(f"Ham CSV → {OUT_CSV}")

    # ── Rapor 1: Hava × SF Matrisi ────────────────────────────────────────────
    # Pivot: rows=sensorSF(7..12), cols=weatherSigma(0.0,3.0,6.0,9.0)
    # Her hücre: tüm meshSF değerleri üzerinden ortalama GW1 rcvBelowSensitivity
    #            ve ortalama DER%
    SIGMAS   = sorted({r["weatherSigma"] for r in rows})
    SFVALS   = sorted({r["sensorSF"]     for r in rows})
    MESHVALS = sorted({r["meshSF"]       for r in rows})

    # group: (sensorSF, weatherSigma) → list of rows
    from collections import defaultdict
    grp_sf_sigma = defaultdict(list)
    for r in rows:
        grp_sf_sigma[(r["sensorSF"], r["weatherSigma"])].append(r)

    # ── Oluştur ──
    lines_m = []
    SEP = "─" * 100

    lines_m.append("=" * 100)
    lines_m.append("RAPOR 1 — HAVA ŞARTLARI × SF MATRİSİ")
    lines_m.append("  (Her hücre: tüm meshSF değerleri üzeri ortalama)")
    lines_m.append("=" * 100)

    # --- Alt Tablo A: Ortalama GW1 rcvBelowSensitivity ---
    lines_m.append("")
    lines_m.append("TABLO A — GW1 rcvBelowSensitivity Ortalaması")
    lines_m.append("  (Kaç paket GW1'de hassasiyet eşiğinin altında kaldı?)")
    lines_m.append("")
    hdr = f"{'sensorSF':>10}" + "".join(f"  sigma={s:4.1f}" for s in SIGMAS)
    lines_m.append(hdr)
    lines_m.append(SEP)
    for sf in SFVALS:
        cells = []
        for sigma in SIGMAS:
            grp = grp_sf_sigma[(sf, sigma)]
            if grp:
                avg = sum(g["gw1_below"] for g in grp) / len(grp)
                cells.append(f"{avg:10.2f}")
            else:
                cells.append(f"{'N/A':>10}")
        lines_m.append(f"{'SF'+str(sf):>10}" + "".join(cells))
    lines_m.append(SEP)

    # --- Alt Tablo B: Ortalama DER% ---
    lines_m.append("")
    lines_m.append("TABLO B — Ortalama DER% (Paket Teslimat Oranı)")
    lines_m.append("  DER = (NS1_rcv + NS2_rcv) / total_sensor_TX × 100")
    lines_m.append("")
    lines_m.append(hdr)
    lines_m.append(SEP)
    for sf in SFVALS:
        cells = []
        for sigma in SIGMAS:
            grp = grp_sf_sigma[(sf, sigma)]
            if grp:
                avg_der = sum(g["der_pct"] for g in grp) / len(grp)
                cells.append(f"{avg_der:9.1f}%")
            else:
                cells.append(f"{'N/A':>10}")
        lines_m.append(f"{'SF'+str(sf):>10}" + "".join(cells))
    lines_m.append(SEP)

    # --- Alt Tablo C: Ortalama toplam_below (GW1+GW2) ---
    lines_m.append("")
    lines_m.append("TABLO C — Toplam rcvBelowSensitivity (GW1+GW2) Ortalaması")
    lines_m.append("")
    lines_m.append(hdr)
    lines_m.append(SEP)
    for sf in SFVALS:
        cells = []
        for sigma in SIGMAS:
            grp = grp_sf_sigma[(sf, sigma)]
            if grp:
                avg = sum(g["total_below"] for g in grp) / len(grp)
                cells.append(f"{avg:10.2f}")
            else:
                cells.append(f"{'N/A':>10}")
        lines_m.append(f"{'SF'+str(sf):>10}" + "".join(cells))
    lines_m.append(SEP)

    # --- Alt Tablo D: Ortalama total_tx ---
    lines_m.append("")
    lines_m.append("TABLO D — Ortalama Toplam TX (5 Sensör)")
    lines_m.append("")
    lines_m.append(hdr)
    lines_m.append(SEP)
    for sf in SFVALS:
        cells = []
        for sigma in SIGMAS:
            grp = grp_sf_sigma[(sf, sigma)]
            if grp:
                avg = sum(g["total_tx"] for g in grp) / len(grp)
                cells.append(f"{avg:10.1f}")
            else:
                cells.append(f"{'N/A':>10}")
        lines_m.append(f"{'SF'+str(sf):>10}" + "".join(cells))
    lines_m.append(SEP)

    # --- Delta-DER tablo: DER(sigma) - DER(sigma=0) ---
    lines_m.append("")
    lines_m.append("TABLO E — ΔDER% (Hava Sönümü Farkı — sigma vs sigma=0)")
    lines_m.append("  Negatif değer: sigma artıkça DER düştü (hava kaybı)")
    lines_m.append("")
    parts_hdr = "".join(f"  σ={s:4.1f}→Δ" for s in SIGMAS)
    lines_m.append(f"{'sensorSF':>10}" + parts_hdr)
    lines_m.append(SEP)
    for sf in SFVALS:
        cells = []
        base_grp = grp_sf_sigma[(sf, 0.0)]
        base_der = (sum(g["der_pct"] for g in base_grp) / len(base_grp)) if base_grp else None
        for sigma in SIGMAS:
            grp = grp_sf_sigma[(sf, sigma)]
            if grp and base_der is not None:
                avg_der = sum(g["der_pct"] for g in grp) / len(grp)
                delta = avg_der - base_der
                cells.append(f"{delta:+10.2f}%")
            else:
                cells.append(f"{'N/A':>11}")
        lines_m.append(f"{'SF'+str(sf):>10}" + "".join(cells))
    lines_m.append(SEP)

    with open(OUT_MATRIX, "w", encoding="utf-8") as f:
        f.write("\n".join(lines_m) + "\n")
    print(f"Rapor 1 → {OUT_MATRIX}")

    # ── Rapor 2: Sigma Gruplarına Göre DER ────────────────────────────────────
    # group: weatherSigma → list of rows
    grp_sigma = defaultdict(list)
    for r in rows:
        grp_sigma[r["weatherSigma"]].append(r)

    # group: (weatherSigma, sensorSF) → list of rows
    grp_sigma_sf = defaultdict(list)
    for r in rows:
        grp_sigma_sf[(r["weatherSigma"], r["sensorSF"])].append(r)

    lines_s = []
    lines_s.append("=" * 100)
    lines_s.append("RAPOR 2 — SIGMA GRUPLARINA GÖRE DER (Paket Teslimat Oranı)")
    lines_s.append("  GW1 daima çevrimiçi — Mesh relay tetiklenmiyor")
    lines_s.append("  DER_GW1 = NS1_rcv / (5 sensör × avg_numSent)")
    lines_s.append("  DER_GW2 = NS2_rcv / (5 sensör × avg_numSent)")
    lines_s.append("  DER_tot = (NS1+NS2) / total_TX")
    lines_s.append("=" * 100)

    # --- 2A: Sigma bazlı özet (tüm SF ve meshSF üzerinden) ---
    lines_s.append("")
    lines_s.append("TABLO 2A — Sigma Bazlı Genel Özet")
    lines_s.append(f"  (Her sigma: {len(SFVALS)*len(MESHVALS)} run ortalaması)")
    lines_s.append("")
    hdr2 = (f"{'sigma':>8}  {'runs':>5}  "
            f"{'tot_TX':>7}  {'GW1_below':>10}  {'GW2_below':>10}  "
            f"{'NS1_rcv':>8}  {'NS2_rcv':>8}  "
            f"{'DER_GW1%':>9}  {'DER_GW2%':>9}  {'DER_tot%':>9}  "
            f"{'GW1_drop':>9}  {'GW1_cong':>9}")
    lines_s.append(hdr2)
    lines_s.append(SEP)
    for sigma in SIGMAS:
        grp = grp_sigma[sigma]
        n   = len(grp)
        if not n:
            continue
        tot_tx   = sum(g["total_tx"]    for g in grp) / n
        gw1_b    = sum(g["gw1_below"]   for g in grp) / n
        gw2_b    = sum(g["gw2_below"]   for g in grp) / n
        ns1_r    = sum(g["ns1_rcv"]     for g in grp) / n
        ns2_r    = sum(g["ns2_rcv"]     for g in grp) / n
        der_gw1  = pct(ns1_r, tot_tx)
        der_gw2  = pct(ns2_r, tot_tx)
        der_tot  = pct(ns1_r + ns2_r, tot_tx)
        gw1_drop = sum(g["gw1_dropped"]    for g in grp) / n
        gw1_cong = sum(g["gw1_congestion"] for g in grp) / n
        lines_s.append(
            f"{sigma:>8.1f}  {n:>5}  "
            f"{tot_tx:>7.1f}  {gw1_b:>10.2f}  {gw2_b:>10.2f}  "
            f"{ns1_r:>8.1f}  {ns2_r:>8.1f}  "
            f"{der_gw1:>8.1f}%  {der_gw2:>8.1f}%  {der_tot:>8.1f}%  "
            f"{gw1_drop:>9.2f}  {gw1_cong:>9.2f}"
        )
    lines_s.append(SEP)

    # --- 2B: Sigma × sensorSF çapraz ---
    lines_s.append("")
    lines_s.append("TABLO 2B — DER% → Sigma × sensorSF Çapraz Tablosu")
    lines_s.append("  (Her hücre: tüm meshSF değerleri üzeri ortalama)")
    lines_s.append("")
    hdr3 = f"{'sigma\\SF':>10}" + "".join(f"   SF{sf:2d}" for sf in SFVALS)
    lines_s.append(hdr3)
    lines_s.append(SEP)
    for sigma in SIGMAS:
        cells = []
        for sf in SFVALS:
            grp = grp_sigma_sf[(sigma, sf)]
            if grp:
                avg_der = sum(g["der_pct"] for g in grp) / len(grp)
                cells.append(f"{avg_der:7.1f}%")
            else:
                cells.append(f"{'N/A':>8}")
        lines_s.append(f"{sigma:>10.1f}" + "".join(cells))
    lines_s.append(SEP)

    # --- 2C: rcvBelowSensitivity → Sigma × sensorSF ---
    lines_s.append("")
    lines_s.append("TABLO 2C — GW1 rcvBelowSensitivity → Sigma × sensorSF")
    lines_s.append("")
    lines_s.append(hdr3)
    lines_s.append(SEP)
    for sigma in SIGMAS:
        cells = []
        for sf in SFVALS:
            grp = grp_sigma_sf[(sigma, sf)]
            if grp:
                avg = sum(g["gw1_below"] for g in grp) / len(grp)
                cells.append(f"{avg:8.2f}")
            else:
                cells.append(f"{'N/A':>8}")
        lines_s.append(f"{sigma:>10.1f}" + "".join(cells))
    lines_s.append(SEP)

    # --- 2D: En kötü / en iyi 5 run ---
    lines_s.append("")
    lines_s.append("TABLO 2D — En Düşük DER% — İlk 10 Run")
    lines_s.append(f"  {'sensorSF':>8}  {'meshSF':>7}  {'sigma':>7}  "
                   f"{'TX':>5}  {'NS1_rcv':>7}  {'NS2_rcv':>7}  {'DER%':>7}  "
                   f"{'GW1_below':>10}")
    lines_s.append(SEP)
    worst = sorted(rows, key=lambda r: r["der_pct"])[:10]
    for r in worst:
        lines_s.append(
            f"  {'SF'+str(r['sensorSF']):>8}  {'SF'+str(r['meshSF']):>7}  "
            f"{r['weatherSigma']:>7.1f}  "
            f"{r['total_tx']:>5}  {r['ns1_rcv']:>7}  {r['ns2_rcv']:>7}  "
            f"{r['der_pct']:>6.1f}%  {r['gw1_below']:>10.0f}"
        )
    lines_s.append("")
    lines_s.append("TABLO 2E — En Yüksek DER% — İlk 10 Run")
    lines_s.append(f"  {'sensorSF':>8}  {'meshSF':>7}  {'sigma':>7}  "
                   f"{'TX':>5}  {'NS1_rcv':>7}  {'NS2_rcv':>7}  {'DER%':>7}  "
                   f"{'GW1_below':>10}")
    lines_s.append(SEP)
    best = sorted(rows, key=lambda r: r["der_pct"], reverse=True)[:10]
    for r in best:
        lines_s.append(
            f"  {'SF'+str(r['sensorSF']):>8}  {'SF'+str(r['meshSF']):>7}  "
            f"{r['weatherSigma']:>7.1f}  "
            f"{r['total_tx']:>5}  {r['ns1_rcv']:>7}  {r['ns2_rcv']:>7}  "
            f"{r['der_pct']:>6.1f}%  {r['gw1_below']:>10.0f}"
        )
    lines_s.append(SEP)

    # --- Özet istatistikler ---
    total_runs = len(rows)
    overall_tx  = sum(r["total_tx"]      for r in rows)
    overall_rcv = sum(r["total_rcv"]     for r in rows)
    overall_der = pct(overall_rcv, overall_tx)
    overall_b1  = sum(r["gw1_below"]     for r in rows)
    overall_b2  = sum(r["gw2_below"]     for r in rows)

    lines_s.append("")
    lines_s.append("─" * 100)
    lines_s.append("GENEL ÖZET")
    lines_s.append(f"  Toplam run          : {total_runs}")
    lines_s.append(f"  Toplam TX (kümülatif): {int(overall_tx)}")
    lines_s.append(f"  Toplam RCV (kümülatif): {int(overall_rcv)}")
    lines_s.append(f"  Genel DER           : {overall_der:.2f}%")
    lines_s.append(f"  GW1 toplam below    : {int(overall_b1)}")
    lines_s.append(f"  GW2 toplam below    : {int(overall_b2)}")
    lines_s.append("─" * 100)

    with open(OUT_SIGMA, "w", encoding="utf-8") as f:
        f.write("\n".join(lines_s) + "\n")
    print(f"Rapor 2 → {OUT_SIGMA}")
    print("─" * 60)
    print(f"Genel DER: {overall_der:.2f}%  "
          f"(TX={int(overall_tx)}, RCV={int(overall_rcv)}, "
          f"below_GW1={int(overall_b1)}, below_GW2={int(overall_b2)})")


if __name__ == "__main__":
    main()
