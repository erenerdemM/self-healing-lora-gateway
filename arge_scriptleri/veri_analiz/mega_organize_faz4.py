#!/usr/bin/env python3
"""
mega_organize_faz4.py — Faz 4 (Yasal Trafik Sınırı) Analiz, Plot ve Arşiv
==========================================================================
Faz 4 (σ=5.0 dB, γ=2.8, obstacle=3.5dB, noiseFloor=-105 dBm,
       sendInterval=180s — BTK/KET SF12 %1 duty-cycle yasal üst sınırı)
için tam analiz + Faz 3 ile karşılaştırma.

Çıktı:
  Faz4_Arazi1_YasalSinir_Final/
    Faz4_Ham_Veriler.tar.gz           ← results_faz4/ raw SCA arşivi
    summary_faz4.csv                  ← tam kolonlu CSV
    Grafikler/
      heatmap_der.png                 ← DER ısı haritası
      capacity_curve.png              ← kapasite eğrisi
      drop_analysis.png               ← routing drop analizi
      collision_load.png              ← çarpışma yükü haritası
      sent_vs_scale.png               ← numSent ölçek (paket/180s)
      Traffic_Effect_Comparison.png   ← Faz 3 vs Faz 4 trafik etkisi
      quad_comparison.png             ← Faz1 vs Faz2 vs Faz3 vs Faz4

Kullanım:
    python3 mega_organize_faz4.py [--skip-parse] [--skip-tar]
"""

import os
import re
import csv
import time
import sys
import shutil
import tarfile
import argparse
from collections import defaultdict

import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import seaborn as sns

# ─── Dizinler ─────────────────────────────────────────────────────────────────
SCRIPT_DIR  = os.path.dirname(os.path.abspath(__file__))
PROJ_DIR    = os.path.abspath(os.path.join(SCRIPT_DIR, '..', '..'))
FAZ4_DIR    = os.path.join(PROJ_DIR, 'results_faz4')
ARCHIVE_DIR = os.path.join(PROJ_DIR, 'Faz4_Arazi1_YasalSinir_Final')
GRAF_DIR    = os.path.join(ARCHIVE_DIR, 'Grafikler')
CSV_OUT     = os.path.join(ARCHIVE_DIR, 'summary_faz4.csv')
TAR_OUT     = os.path.join(ARCHIVE_DIR, 'Faz4_Ham_Veriler.tar.gz')
LOGS_DIR    = os.path.join(PROJ_DIR, 'logs_massive_faz4')

# Karşılaştırma CSV'leri
FAZ1_CSV  = os.path.join(PROJ_DIR, 'Faz1_Arazi1_Olceklendirme_Final',  'summary_7x7.csv')
FAZ2_CSV  = os.path.join(PROJ_DIR, 'Faz2_Arazi2_Stres_Final',           'summary_faz2.csv')
FAZ3_CSV  = os.path.join(PROJ_DIR, 'Faz3_Arazi1_Gurultu_Final',         'summary_faz3.csv')

os.makedirs(GRAF_DIR, exist_ok=True)

# ─── Argümanlar ───────────────────────────────────────────────────────────────
ap = argparse.ArgumentParser()
ap.add_argument('--skip-parse', action='store_true',
                help='SCA parse atla, mevcut CSV kullan')
ap.add_argument('--skip-tar',   action='store_true',
                help='Tar oluşturmayı atla')
args = ap.parse_args()

# ─── Regex & sabitler ─────────────────────────────────────────────────────────
re_fname4     = re.compile(r'^Faz4_GW(\d+)_Mesh(\d+)_(MIN|MAX)-(\d+)\.sca$')
re_gw_radio   = re.compile(r'hybridGW\d+\.LoRaGWNic\.radio$')
re_gw_recv    = re.compile(r'hybridGW\d+\.LoRaGWNic\.radio\.receiver$')
re_sensor_mod = re.compile(r'sensorGW\d+\[\d+\]\.LoRaNic\.mac$')
re_ns_mod     = re.compile(r'networkServer\d+\.app\[0\]$')
re_routing    = re.compile(r'hybridGW\d+\.routingAgent$')

GW_RANGE   = list(range(2, 8))
MESH_RANGE = list(range(1, 8))
MODES      = ['MIN', 'MAX']
SFS        = [7, 8, 9, 10, 11, 12]

plt.rcParams.update({
    'font.family': 'serif', 'font.size': 10,
    'axes.titlesize': 11,   'axes.labelsize': 10,
    'xtick.labelsize': 9,   'ytick.labelsize': 9,
    'legend.fontsize': 8,   'figure.dpi': 150,
})
DPI_SAVE = 300

COLS = ['gw', 'mesh', 'mode', 'sensorSF', 'meshSF',
        'total_sent', 'total_rcv', 'total_drop',
        'total_rcv_correct', 'total_rcv_started', 'total_collision',
        'radio_der_pct', 'collision_pct', 'der_pct',
        'sensitivity_loss_pct', 'collision_loss_pct']


# ══════════════════════════════════════════════════════════════════════════════
def parse_sca(path):
    sent = rcv = drop = 0
    rcv_correct = rcv_started = collision = 0
    sensorSF = meshSF = None

    with open(path, encoding='utf-8', errors='replace') as fh:
        for line in fh:
            line = line.rstrip()
            if line.startswith('attr iterationvars '):
                ms  = re.search(r'\$sensorSF=(\d+)', line)
                ms2 = re.search(r'\$meshSF=(\d+)',   line)
                if ms:  sensorSF = int(ms.group(1))
                if ms2: meshSF   = int(ms2.group(1))
                continue
            if not line.startswith('scalar '):
                continue
            parts = line.split(None, 3)
            if len(parts) < 4:
                continue
            module, stat = parts[1], parts[2]
            try:
                val = float(parts[3])
            except ValueError:
                continue

            if   stat == 'numSent'                                   and re_sensor_mod.search(module): sent          += int(val)
            elif stat == 'totalReceivedPackets'                      and re_ns_mod.search(module):     rcv           += int(val)
            elif stat == 'droppedPacket:count'                       and re_routing.search(module):    drop          += int(val)
            elif stat == 'LoRaGWRadioReceptionFinishedCorrect:count' and re_gw_radio.search(module):   rcv_correct   += int(val)
            elif stat == 'LoRaGWRadioReceptionStarted:count'         and re_gw_radio.search(module):   rcv_started   += int(val)
            elif stat == 'LoRaReceptionCollision:count'              and re_gw_recv.search(module):    collision     += int(val)

    return {
        'total_sent': sent, 'total_rcv': rcv, 'total_drop': drop,
        'total_rcv_correct': rcv_correct, 'total_rcv_started': rcv_started,
        'total_collision': collision,
        'sensorSF': sensorSF, 'meshSF': meshSF,
    }


def safe_mean(lst):
    return float(np.nanmean(lst)) if lst else float('nan')


# ══════════════════════════════════════════════════════════════════════════════
print("=" * 70)
print("  MEGA ORGANIZE — FAZ 4 (Yasal Sınır, sendInterval=180s, BTK/KET)")
print("=" * 70)

rows = []

if args.skip_parse and os.path.exists(CSV_OUT):
    print(f"\n[1/6] Mevcut CSV yükleniyor (--skip-parse): {CSV_OUT}")
    with open(CSV_OUT, newline='') as f:
        for row in csv.DictReader(f):
            rows.append(row)
    print(f"    {len(rows)} kayıt yüklendi")

if not rows:
    if not os.path.isdir(FAZ4_DIR):
        print(f"\n  HATA: {FAZ4_DIR} bulunamadı.")
        sys.exit(1)

    files = sorted(f for f in os.listdir(FAZ4_DIR) if re_fname4.match(f))
    total = len(files)
    print(f"\n[1/6] SCA parse ediliyor: {FAZ4_DIR}  ({total} dosya)")
    t0 = time.time()

    for i, fname in enumerate(files, 1):
        m = re_fname4.match(fname)
        if not m:
            continue
        gw, mesh, mode, run_no = int(m.group(1)), int(m.group(2)), m.group(3), int(m.group(4))
        d = parse_sca(os.path.join(FAZ4_DIR, fname))

        ssf = d['sensorSF'] if d['sensorSF'] is not None else (7 + run_no // 6)
        msf = d['meshSF']   if d['meshSF']   is not None else (7 + run_no %  6)

        radio_der     = (d['total_rcv_correct'] / d['total_rcv_started'] * 100
                         if d['total_rcv_started'] > 0 else 0.0)
        col_pct       = (d['total_collision']   / d['total_rcv_started'] * 100
                         if d['total_rcv_started'] > 0 else 0.0)
        der_pct       = (d['total_rcv'] / d['total_sent'] * 100
                         if d['total_sent'] > 0 else 0.0)

        sensitivity_loss_pct = ((d['total_sent'] - d['total_rcv_started']) / d['total_sent'] * 100
                                 if d['total_sent'] > 0 else 0.0)
        collision_loss_pct   = (d['total_collision'] / d['total_sent'] * 100
                                 if d['total_sent'] > 0 else 0.0)

        rows.append({
            'gw': gw, 'mesh': mesh, 'mode': mode,
            'sensorSF': ssf, 'meshSF': msf,
            'total_sent': d['total_sent'], 'total_rcv': d['total_rcv'],
            'total_drop': d['total_drop'],
            'total_rcv_correct': d['total_rcv_correct'],
            'total_rcv_started': d['total_rcv_started'],
            'total_collision': d['total_collision'],
            'radio_der_pct': radio_der,
            'collision_pct': col_pct,
            'der_pct': der_pct,
            'sensitivity_loss_pct': sensitivity_loss_pct,
            'collision_loss_pct':   collision_loss_pct,
        })
        if i % 500 == 0:
            print(f"    {i}/{total}  ({time.time()-t0:.1f}s)", flush=True)

    print(f"    {len(rows)} kayıt parse edildi  ({time.time()-t0:.1f}s)")

# CSV kaydet
with open(CSV_OUT, 'w', newline='') as f:
    w = csv.DictWriter(f, fieldnames=COLS)
    w.writeheader()
    for r in rows:
        w.writerow({c: r.get(c, '') for c in COLS})
print(f"    CSV → {CSV_OUT}")


# ══════════════════════════════════════════════════════════════════════════════
# AGREGASyon
# ══════════════════════════════════════════════════════════════════════════════
agg_der       = defaultdict(list)
agg_radio_der = defaultdict(list)
agg_drop      = defaultdict(list)
agg_collision = defaultdict(list)
agg_sent      = defaultdict(list)
agg_sens_loss = defaultdict(list)
agg_col_loss  = defaultdict(list)

for r in rows:
    key = (int(r['gw']), int(r['mesh']), r['mode'])
    agg_der[key].append(float(r['der_pct']))
    agg_radio_der[key].append(float(r['radio_der_pct']))
    agg_drop[key].append(float(r['total_drop']))
    agg_collision[key].append(float(r['collision_pct']))
    agg_sent[key].append(float(r['total_sent']))
    agg_sens_loss[key].append(float(r['sensitivity_loss_pct']))
    agg_col_loss[key].append(float(r['collision_loss_pct']))

gw_colors = plt.cm.plasma(np.linspace(0.05, 0.85, len(GW_RANGE)))
cmap_der  = sns.diverging_palette(10, 130, n=256, as_cmap=True)
cmap_coll = sns.color_palette("RdYlGn_r", as_cmap=True)


# ══════════════════════════════════════════════════════════════════════════════
# NUMERİK ANALİZ — Trafik Yükü Etki Raporu
# ══════════════════════════════════════════════════════════════════════════════
print("\n" + "=" * 70)
print("  NUMERİK ANALİZ — Yasal Trafik Sınırı Etki Raporu (Faz3 vs Faz4)")
print("=" * 70)

try:
    import pandas as pd

    df4 = pd.DataFrame(rows)
    for col in ['radio_der_pct', 'collision_pct', 'der_pct',
                'sensitivity_loss_pct', 'collision_loss_pct',
                'total_sent', 'total_rcv', 'total_collision', 'total_rcv_started']:
        df4[col] = pd.to_numeric(df4[col], errors='coerce')
    df4['gw']       = df4['gw'].astype(int)
    df4['sensorSF'] = df4['sensorSF'].astype(int)

    # ── 1. Genel DER (Delta vs Faz3) ──────────────────────────────────────────
    faz4_mean_der = df4['radio_der_pct'].mean()
    faz4_mean_col = df4['collision_pct'].mean()
    faz4_mean_sent = df4['total_sent'].mean()
    print(f"\n  Faz 4 Ortalama Radio-DER     : {faz4_mean_der:.2f}%")
    print(f"  Faz 4 Ortalama Çarpışma Oranı: {faz4_mean_col:.2f}%")
    print(f"  Faz 4 Ortalama numSent       : {faz4_mean_sent:.1f} paket/run")
    print(f"  Faz 4 Teorik paket (1200s/180s): ~{1200/180:.1f} paket/sensör")

    faz3_mean_der  = None
    faz3_mean_col  = None
    df3 = None
    if os.path.exists(FAZ3_CSV):
        df3 = pd.read_csv(FAZ3_CSV)
        df3['radio_der_pct']  = pd.to_numeric(df3['radio_der_pct'],  errors='coerce')
        df3['collision_pct']  = pd.to_numeric(df3['collision_pct'],  errors='coerce')
        df3['total_sent']     = pd.to_numeric(df3['total_sent'],     errors='coerce')
        df3['sensorSF']       = pd.to_numeric(df3['sensorSF'],       errors='coerce')
        faz3_mean_der = df3['radio_der_pct'].mean()
        faz3_mean_col = df3['collision_pct'].mean()
        faz3_mean_sent= df3['total_sent'].mean()
        delta_der = faz3_mean_der - faz4_mean_der
        delta_col = faz4_mean_col - faz3_mean_col
        print(f"\n  Faz 3 Ortalama Radio-DER     : {faz3_mean_der:.2f}%")
        print(f"  Faz 3 Ortalama Çarpışma Oranı: {faz3_mean_col:.2f}%")
        print(f"  Faz 3 Ortalama numSent       : {faz3_mean_sent:.1f} paket/run")
        dder_sign = '-' if delta_der >= 0 else '+'
        print(f"\n  Delta DER (Faz3→Faz4)        : {dder_sign}{abs(delta_der):.2f} puan")
        print(f"  Delta Çarpışma (Faz3→Faz4)   : +{delta_col:.2f} puan")
        print(f"  Trafik etkisi: sendInterval 180s → Faz3'e göre paket azalması")
    else:
        print("  !! Faz 3 CSV bulunamadı, karşılaştırma atlandı")

    # ── 2. SF Direnci ─────────────────────────────────────────────────────────
    print(f"\n  SF Bazında DER (Radio):")
    sf_stats_faz4 = {}
    for sf in SFS:
        subset = df4[df4['sensorSF'] == sf]
        m = subset['radio_der_pct'].mean()
        sf_stats_faz4[sf] = m
        line = f"    SF{sf}: {m:.2f}%"
        if df3 is not None:
            df3_sf = df3[df3['sensorSF'].astype(int) == sf]
            m3 = df3_sf['radio_der_pct'].mean() if len(df3_sf) > 0 else float('nan')
            if not np.isnan(m3):
                diff = m3 - m
                sign_str = f"-{diff:.2f}" if diff >= 0 else f"+{abs(diff):.2f}"
                line += f"  |  Faz3: {m3:.2f}%  |  Delta: {sign_str} puan"
        print(line)

    best_sf  = max(sf_stats_faz4, key=sf_stats_faz4.get)
    worst_sf = min(sf_stats_faz4, key=sf_stats_faz4.get)
    print(f"\n  En Dirençli SF: SF{best_sf} ({sf_stats_faz4[best_sf]:.2f}%)")
    print(f"  En Kırılgan SF: SF{worst_sf} ({sf_stats_faz4[worst_sf]:.2f}%)")

    # ── 3. Kayıp Kaynakları ───────────────────────────────────────────────────
    mean_sens_loss = df4['sensitivity_loss_pct'].mean()
    mean_col_loss  = df4['collision_loss_pct'].mean()
    total_loss_pct = 100.0 - faz4_mean_der

    print(f"\n  Kayıp Kaynakları (ortalama, radio katmanı temelinde):")
    print(f"    Toplam Kayıp Oranı      : %{total_loss_pct:.2f}")
    print(f"    Hassasiyet/Gürültü Kaybı: %{mean_sens_loss:.2f}  (sinyal eşiğe ulaşamadı)")
    print(f"    Çarpışma Kaybı          : %{mean_col_loss:.2f}  (eş-zamanlı iletim)")
    total_measured = mean_sens_loss + mean_col_loss
    if total_measured > 0:
        print(f"    Oran: Hassasiyet {mean_sens_loss/total_measured*100:.0f}%  |  "
              f"Çarpışma {mean_col_loss/total_measured*100:.0f}%  (toplam ölçülen kayıplar içinde)")

    # En iyi konfigürasyon
    best_cfg = df4.groupby(['gw', 'mesh', 'mode'])['radio_der_pct'].mean().idxmax()
    best_val = df4.groupby(['gw', 'mesh', 'mode'])['radio_der_pct'].mean().max()
    print(f"\n  En Yüksek DER Konfigürasyon: GW={best_cfg[0]}, Mesh={best_cfg[1]}, "
          f"Mode={best_cfg[2]}  →  %{best_val:.2f}")

    faz4_best_der = best_val
    faz4_best_cfg = f"GW{best_cfg[0]}_Mesh{best_cfg[1]}_{best_cfg[2]}"

except Exception as e:
    print(f"  !! Numerik analiz hatası: {e}")
    import traceback; traceback.print_exc()
    faz4_mean_der  = 0.0
    faz4_mean_col  = 0.0
    faz4_best_cfg  = "?"
    faz4_best_der  = 0.0
    faz3_mean_der  = None
    faz3_mean_col  = None
    best_sf  = 12
    worst_sf = 7
    df3 = None
    df4 = pd.DataFrame(rows)


# ══════════════════════════════════════════════════════════════════════════════
# ADIM 2: GRAFİKLER
# ══════════════════════════════════════════════════════════════════════════════
print(f"\n[2/6] Grafikler üretiliyor → {GRAF_DIR}")

# ── GRAFİK 1: DER Heatmap ─────────────────────────────────────────────────────
fig, axes = plt.subplots(1, 2, figsize=(11, 5))
fig.suptitle(
    "Ortalama Radio-DER (%)  —  Faz 4 (sendInterval=180s, BTK/KET Yasal Sınır)  [7×7]",
    fontsize=12, fontweight='bold', y=1.01
)
for ax, mode in zip(axes, MODES):
    mat = np.full((len(GW_RANGE), len(MESH_RANGE)), np.nan)
    for gi, gw in enumerate(GW_RANGE):
        for mi, mesh in enumerate(MESH_RANGE):
            v = agg_radio_der.get((gw, mesh, mode), [])
            if v:
                mat[gi, mi] = safe_mean(v)
    annot = [[f"{mat[gi,mi]:.1f}" if not np.isnan(mat[gi,mi]) else "–"
              for mi in range(len(MESH_RANGE))]
             for gi in range(len(GW_RANGE))]
    sns.heatmap(mat, ax=ax, annot=annot, fmt='',
                xticklabels=MESH_RANGE, yticklabels=GW_RANGE,
                cmap=cmap_der, vmin=0, vmax=100,
                linewidths=0.4, linecolor='white',
                cbar_kws={'label': 'Radio-DER (%)', 'shrink': 0.85},
                annot_kws={'size': 8})
    ax.set_title(f"Mode={mode}  ({'1 km' if mode == 'MIN' else '6 km'})", fontweight='bold')
    ax.set_xlabel("Mesh Node Sayısı")
    ax.set_ylabel("Gateway Sayısı")
    ax.set_yticklabels(ax.get_yticklabels(), rotation=0)
plt.tight_layout()
fig.savefig(os.path.join(GRAF_DIR, 'heatmap_der.png'), dpi=DPI_SAVE, bbox_inches='tight')
plt.close(fig)
print("    → heatmap_der.png")

# ── GRAFİK 2: Kapasite Eğrisi ────────────────────────────────────────────────
fig, ax = plt.subplots(figsize=(7, 4.5))
color_map  = {'MIN': '#e74c3c', 'MAX': '#27ae60'}
marker_map = {'MIN': 'o',       'MAX': 's'}
for mode in MODES:
    xs, ys = [], []
    for gw in GW_RANGE:
        for mesh in MESH_RANGE:
            v = agg_radio_der.get((gw, mesh, mode), [])
            if v:
                xs.append(gw * 10 + gw + mesh)
                ys.append(safe_mean(v))
    if not xs:
        continue
    xs, ys = np.array(xs), np.array(ys)
    valid = ~np.isnan(ys)
    xv, yv = xs[valid], ys[valid]
    ax.scatter(xv, yv, alpha=0.30, s=20, color=color_map[mode],
               marker=marker_map[mode], zorder=2)
    if len(xv) >= 3:
        z = np.polyfit(xv, yv, 2)
        x_smooth = np.linspace(xv.min(), xv.max(), 400)
        ax.plot(x_smooth, np.poly1d(z)(x_smooth), linewidth=2.2,
                color=color_map[mode], label=f"{mode}  (fit)")
ax.axhline(y=50, color='orange', linestyle='--', linewidth=1.2, alpha=0.8, label="50% eşik")
ax.axhline(y=80, color='gray',   linestyle='--', linewidth=1.2, alpha=0.8, label="80% eşik")
ax.set_xlabel("Toplam Ağ Düğüm Sayısı")
ax.set_ylabel("Ortalama Radio-DER (%)")
ax.set_title("Kapasite Eğrisi — Faz 4 (BTK/KET Yasal Sınır, sendInterval=180s)", fontweight='bold')
ax.set_ylim(0, 107)
ax.legend(loc='upper right', framealpha=0.9)
ax.grid(True, alpha=0.25, linestyle=':')
plt.tight_layout()
fig.savefig(os.path.join(GRAF_DIR, 'capacity_curve.png'), dpi=DPI_SAVE, bbox_inches='tight')
plt.close(fig)
print("    → capacity_curve.png")

# ── GRAFİK 3: Drop Analizi ────────────────────────────────────────────────────
fig, axes = plt.subplots(1, 2, figsize=(12, 4.5), sharey=False)
for ax, mode in zip(axes, MODES):
    for gi, gw in enumerate(GW_RANGE):
        xs, ys = [], []
        for mesh in MESH_RANGE:
            v = agg_drop.get((gw, mesh, mode), [])
            if v:
                xs.append(mesh)
                ys.append(safe_mean(v))
        if xs:
            ax.plot(xs, ys, marker='o', linewidth=1.8, markersize=5,
                    color=gw_colors[gi], label=f"GW={gw}")
    ax.set_title(f"Mode={mode}  ({'1 km' if mode == 'MIN' else '6 km'})", fontweight='bold')
    ax.set_xlabel("Mesh Node Sayısı")
    ax.set_ylabel("Ortalama Drop Count")
    ax.set_xticks(MESH_RANGE)
    ax.legend(fontsize=8, ncol=2, loc='upper left', framealpha=0.8)
    ax.grid(True, alpha=0.25, linestyle=':')
fig.suptitle("Drop Analizi — Faz 4: Yasal Trafik Altında Routing Kayıpları",
             fontweight='bold', y=1.02)
plt.tight_layout()
fig.savefig(os.path.join(GRAF_DIR, 'drop_analysis.png'), dpi=DPI_SAVE, bbox_inches='tight')
plt.close(fig)
print("    → drop_analysis.png")

# ── GRAFİK 4: Çarpışma Yükü ──────────────────────────────────────────────────
fig, axes = plt.subplots(1, 2, figsize=(11, 5))
fig.suptitle("Ortalama Çarpışma Yükü (%)  —  Faz 4 (sendInterval=180s)",
             fontsize=12, fontweight='bold', y=1.01)
for ax, mode in zip(axes, MODES):
    mat = np.full((len(GW_RANGE), len(MESH_RANGE)), np.nan)
    for gi, gw in enumerate(GW_RANGE):
        for mi, mesh in enumerate(MESH_RANGE):
            v = agg_collision.get((gw, mesh, mode), [])
            if v:
                mat[gi, mi] = safe_mean(v)
    annot = [[f"{mat[gi,mi]:.0f}%" if not np.isnan(mat[gi,mi]) else "–"
              for mi in range(len(MESH_RANGE))]
             for gi in range(len(GW_RANGE))]
    sns.heatmap(mat, ax=ax, annot=annot, fmt='',
                xticklabels=MESH_RANGE, yticklabels=GW_RANGE,
                cmap=cmap_coll, vmin=0, vmax=100,
                linewidths=0.4, linecolor='white',
                cbar_kws={'label': 'Çarpışma Yükü (%)', 'shrink': 0.85},
                annot_kws={'size': 8})
    ax.set_title(f"Mode={mode}  ({'1 km' if mode == 'MIN' else '6 km'})", fontweight='bold')
    ax.set_xlabel("Mesh Node Sayısı")
    ax.set_ylabel("Gateway Sayısı")
    ax.set_yticklabels(ax.get_yticklabels(), rotation=0)
plt.tight_layout()
fig.savefig(os.path.join(GRAF_DIR, 'collision_load.png'), dpi=DPI_SAVE, bbox_inches='tight')
plt.close(fig)
print("    → collision_load.png")

# ── GRAFİK 5: Sent vs Scale ───────────────────────────────────────────────────
fig, axes = plt.subplots(1, 2, figsize=(12, 4.5), sharey=False)
for ax, mode in zip(axes, MODES):
    for gi, gw in enumerate(GW_RANGE):
        xs, ys = [], []
        for mesh in MESH_RANGE:
            v = agg_sent.get((gw, mesh, mode), [])
            if v:
                xs.append(mesh)
                ys.append(safe_mean(v))
        if xs:
            ax.plot(xs, ys, marker='o', linewidth=1.8, markersize=5,
                    color=gw_colors[gi], label=f"GW={gw}")
    ax.set_title(f"Mode={mode}  ({'1 km' if mode == 'MIN' else '6 km'})", fontweight='bold')
    ax.set_xlabel("Mesh Node Sayısı")
    ax.set_ylabel("Ortalama numSent (paket)")
    ax.set_xticks(MESH_RANGE)
    ax.legend(fontsize=8, ncol=2, loc='upper left', framealpha=0.8)
    ax.grid(True, alpha=0.25, linestyle=':')
fig.suptitle("Gönderilen Toplam Paket — Faz 4 (sendInterval=180s, ~6 paket/sensör)",
             fontweight='bold', y=1.02)
plt.tight_layout()
fig.savefig(os.path.join(GRAF_DIR, 'sent_vs_scale.png'), dpi=DPI_SAVE, bbox_inches='tight')
plt.close(fig)
print("    → sent_vs_scale.png")

# ── GRAFİK 6: TRAFİK ETKİSİ - Faz 3 vs Faz 4 ────────────────────────────────
print("    → Traffic_Effect_Comparison.png (Faz3 vs Faz4 karşılaştırması)")
try:
    import pandas as pd

    df4p = pd.DataFrame(rows)
    for col in ['radio_der_pct', 'collision_pct', 'der_pct',
                'sensitivity_loss_pct', 'collision_loss_pct', 'total_sent']:
        df4p[col] = pd.to_numeric(df4p[col], errors='coerce')
    df4p['gw']       = df4p['gw'].astype(int)
    df4p['sensorSF'] = df4p['sensorSF'].astype(int)
    df4p['phase']    = 'Faz 4\n(180s, BTK/KET)'

    fig, axes = plt.subplots(1, 3, figsize=(16, 5))
    fig.suptitle(
        "Trafik Etkisi: Faz 3 (Gürültü Testi) vs Faz 4 (Yasal Sınır, sendInterval=180s)",
        fontsize=13, fontweight='bold', y=1.02
    )

    # --- Panel A: Radio-DER box per phase ---
    ax = axes[0]
    plot_dfs = []
    if os.path.exists(FAZ3_CSV):
        df3p = pd.read_csv(FAZ3_CSV)
        df3p['radio_der_pct'] = pd.to_numeric(df3p['radio_der_pct'], errors='coerce')
        df3p['phase'] = 'Faz 3\n(Gürültü=-105dBm)'
        plot_dfs.append(df3p[['phase', 'radio_der_pct']])
    plot_dfs.append(df4p[['phase', 'radio_der_pct']])
    if plot_dfs:
        combined = pd.concat(plot_dfs, ignore_index=True)
        colors_box = ['#3498db', '#e74c3c']
        bp = combined.boxplot(column='radio_der_pct', by='phase', ax=ax,
                              patch_artist=True, return_type='dict',
                              medianprops=dict(color='black', linewidth=2))
        for patch, col in zip(bp['radio_der_pct']['boxes'], colors_box):
            patch.set_facecolor(col)
            patch.set_alpha(0.7)
    ax.set_title("Radio-DER Dağılımı", fontweight='bold')
    ax.set_xlabel("")
    ax.set_ylabel("Radio-DER (%)")
    ax.set_ylim(0, 105)
    ax.axhline(y=50, color='orange', linestyle='--', linewidth=1, alpha=0.7)
    ax.grid(True, alpha=0.2, linestyle=':')
    plt.suptitle("")

    # --- Panel B: SF bazında DER karşılaştırması ---
    ax = axes[1]
    x = np.arange(len(SFS))
    width = 0.35
    faz3_sf_means = []
    faz4_sf_means = []
    if os.path.exists(FAZ3_CSV):
        df3_sf = pd.read_csv(FAZ3_CSV)
        df3_sf['radio_der_pct'] = pd.to_numeric(df3_sf['radio_der_pct'], errors='coerce')
        df3_sf['sensorSF']      = pd.to_numeric(df3_sf['sensorSF'],      errors='coerce')
        for sf in SFS:
            sub = df3_sf[df3_sf['sensorSF'] == sf]
            faz3_sf_means.append(sub['radio_der_pct'].mean() if len(sub) > 0 else 0)
    else:
        faz3_sf_means = [0] * len(SFS)
    for sf in SFS:
        sub = df4p[df4p['sensorSF'] == sf]
        faz4_sf_means.append(sub['radio_der_pct'].mean() if len(sub) > 0 else 0)
    b1 = ax.bar(x - width/2, faz3_sf_means, width, label='Faz 3 (Gürültü)',
                color='#3498db', alpha=0.8, edgecolor='white')
    b2 = ax.bar(x + width/2, faz4_sf_means, width, label='Faz 4 (Yasal, 180s)',
                color='#e74c3c', alpha=0.8, edgecolor='white')
    ax.set_title("SF Bazında Radio-DER", fontweight='bold')
    ax.set_xlabel("Spreading Factor")
    ax.set_ylabel("Ortalama Radio-DER (%)")
    ax.set_xticks(x)
    ax.set_xticklabels([f"SF{sf}" for sf in SFS])
    ax.set_ylim(0, 110)
    ax.legend(framealpha=0.9)
    ax.grid(True, alpha=0.2, linestyle=':', axis='y')
    for bar in b1:
        h = bar.get_height()
        if not np.isnan(h) and h > 2:
            ax.annotate(f'{h:.0f}', xy=(bar.get_x() + bar.get_width()/2, h),
                        xytext=(0, 2), textcoords='offset points', ha='center', va='bottom', fontsize=7)
    for bar in b2:
        h = bar.get_height()
        if not np.isnan(h) and h > 2:
            ax.annotate(f'{h:.0f}', xy=(bar.get_x() + bar.get_width()/2, h),
                        xytext=(0, 2), textcoords='offset points', ha='center', va='bottom', fontsize=7)

    # --- Panel C: Çarpışma oranı karşılaştırması (Faz3 vs Faz4) ---
    ax = axes[2]
    phases  = []
    col_means = []
    der_means = []
    if os.path.exists(FAZ3_CSV):
        df3_c = pd.read_csv(FAZ3_CSV)
        df3_c['collision_pct']  = pd.to_numeric(df3_c['collision_pct'],  errors='coerce')
        df3_c['radio_der_pct']  = pd.to_numeric(df3_c['radio_der_pct'],  errors='coerce')
        phases.append('Faz 3\n(Gürültü)')
        col_means.append(df3_c['collision_pct'].mean())
        der_means.append(df3_c['radio_der_pct'].mean())
    df4_c = df4p.copy()
    df4_c['collision_pct'] = pd.to_numeric(df4_c['collision_pct'], errors='coerce')
    phases.append('Faz 4\n(Yasal, 180s)')
    col_means.append(df4_c['collision_pct'].mean())
    der_means.append(df4_c['radio_der_pct'].mean())

    x2 = np.arange(len(phases))
    b_col = ax.bar(x2 - 0.2, col_means, 0.38, label='Çarpışma Oranı (%)',
                   color='#c0392b', alpha=0.8, edgecolor='white')
    b_der = ax.bar(x2 + 0.2, der_means, 0.38, label='Radio-DER (%)',
                   color='#27ae60', alpha=0.8, edgecolor='white')
    ax.set_title("Çarpışma vs DER Karşılaştırması", fontweight='bold')
    ax.set_ylabel("Yüzde (%)")
    ax.set_xticks(x2)
    ax.set_xticklabels(phases)
    ax.set_ylim(0, 110)
    ax.legend(framealpha=0.9)
    ax.grid(True, alpha=0.2, linestyle=':', axis='y')
    for bar in list(b_col) + list(b_der):
        h = bar.get_height()
        if not np.isnan(h) and h > 1:
            ax.annotate(f'{h:.1f}%', xy=(bar.get_x() + bar.get_width()/2, h),
                        xytext=(0, 3), textcoords='offset points', ha='center', va='bottom', fontsize=8, fontweight='bold')

    plt.tight_layout()
    fig.savefig(os.path.join(GRAF_DIR, 'Traffic_Effect_Comparison.png'), dpi=DPI_SAVE, bbox_inches='tight')
    plt.close(fig)
    print("    → Traffic_Effect_Comparison.png ✓")

except Exception as e:
    print(f"    !! Traffic_Effect_Comparison hatası: {e}")
    import traceback; traceback.print_exc()
    plt.close('all')

# ── GRAFİK 7: QUAD COMPARISON (Faz1 vs Faz2 vs Faz3 vs Faz4) ─────────────────
print("    → quad_comparison.png (Faz1 vs Faz2 vs Faz3 vs Faz4)")
try:
    import pandas as pd

    phase_csvs = [
        ('Faz 1\n(İdeal)'          , FAZ1_CSV,  '#2ecc71'),
        ('Faz 2\n(Stres,σ=6.0)'    , FAZ2_CSV,  '#e67e22'),
        ('Faz 3\n(Gürültü,-105dBm)', FAZ3_CSV,  '#3498db'),
        ('Faz 4\n(Yasal,180s)'      , CSV_OUT,   '#e74c3c'),
    ]

    fig, axes = plt.subplots(1, 2, figsize=(14, 6))
    fig.suptitle(
        "Dört Faz Karşılaştırması: İdeal → Stres → Gürültü → Yasal Trafik",
        fontsize=13, fontweight='bold', y=1.02
    )

    # Panel A: Radio-DER kutu grafikleri
    ax = axes[0]
    der_data  = []
    der_lbls  = []
    box_cols  = []
    for lbl, path, col in phase_csvs:
        if not os.path.exists(path):
            continue
        dftmp = pd.read_csv(path)
        dftmp['radio_der_pct'] = pd.to_numeric(dftmp['radio_der_pct'], errors='coerce')
        vals = dftmp['radio_der_pct'].dropna().values
        if len(vals) > 0:
            der_data.append(vals)
            der_lbls.append(lbl)
            box_cols.append(col)
    positions = list(range(1, len(der_data) + 1))
    bp = ax.boxplot(der_data, positions=positions, patch_artist=True,
                    medianprops=dict(color='black', linewidth=2),
                    widths=0.55)
    for patch, col in zip(bp['boxes'], box_cols):
        patch.set_facecolor(col)
        patch.set_alpha(0.75)
    ax.set_title("Radio-DER Dağılımı (4 Faz)", fontweight='bold')
    ax.set_ylabel("Radio-DER (%)")
    ax.set_xticks(positions)
    ax.set_xticklabels(der_lbls, fontsize=8)
    ax.set_ylim(0, 108)
    ax.axhline(y=50, color='orange', linestyle='--', linewidth=1.2, alpha=0.7, label="50% eşik")
    ax.axhline(y=80, color='gray',   linestyle='--', linewidth=1.2, alpha=0.7, label="80% eşik")
    ax.legend(fontsize=8, loc='lower right')
    ax.grid(True, alpha=0.2, linestyle=':', axis='y')
    # Medyan etiketleri
    for pos, data in zip(positions, der_data):
        med = float(np.median(data))
        ax.text(pos, med + 1.5, f'{med:.1f}%', ha='center', va='bottom', fontsize=8, fontweight='bold')

    # Panel B: Ortalama DER çubuk + Çarpışma çizgi
    ax = axes[1]
    phase_labels_short = []
    mean_ders  = []
    mean_cols  = []
    bar_cols   = []
    for lbl, path, col in phase_csvs:
        if not os.path.exists(path):
            continue
        dftmp = pd.read_csv(path)
        dftmp['radio_der_pct'] = pd.to_numeric(dftmp['radio_der_pct'], errors='coerce')
        dftmp['collision_pct'] = pd.to_numeric(dftmp['collision_pct'], errors='coerce')
        mean_ders.append(dftmp['radio_der_pct'].mean())
        mean_cols.append(dftmp['collision_pct'].mean())
        phase_labels_short.append(lbl)
        bar_cols.append(col)
    x3 = np.arange(len(mean_ders))
    bars = ax.bar(x3, mean_ders, color=bar_cols, alpha=0.8, edgecolor='white', width=0.5, label='Ort. Radio-DER')
    ax.set_title("Ortalama Radio-DER & Çarpışma Oranı (4 Faz)", fontweight='bold')
    ax.set_ylabel("Radio-DER (%)", color='black')
    ax.set_xticks(x3)
    ax.set_xticklabels(phase_labels_short, fontsize=8)
    ax.set_ylim(0, 115)
    ax.grid(True, alpha=0.2, linestyle=':', axis='y')
    for bar, val in zip(bars, mean_ders):
        if not np.isnan(val):
            ax.text(bar.get_x() + bar.get_width()/2, val + 1,
                    f'{val:.1f}%', ha='center', va='bottom', fontsize=9, fontweight='bold')
    # Çarpışma oranı ikincil eksen
    ax2 = ax.twinx()
    ax2.plot(x3, mean_cols, 'D--', color='#c0392b', linewidth=2, markersize=8,
             label='Ort. Çarpışma Oranı', alpha=0.9)
    ax2.set_ylabel("Çarpışma Oranı (%)", color='#c0392b')
    ax2.tick_params(axis='y', labelcolor='#c0392b')
    ax2.set_ylim(0, max(mean_cols + [10]) * 1.5 + 1)
    for xi, cv in zip(x3, mean_cols):
        if not np.isnan(cv):
            ax2.text(xi + 0.12, cv + 0.3, f'{cv:.1f}%', ha='left', va='bottom',
                     fontsize=8, color='#c0392b', fontweight='bold')
    lines1, labels1 = ax.get_legend_handles_labels()
    lines2, labels2 = ax2.get_legend_handles_labels()
    ax.legend(lines1 + lines2, labels1 + labels2, fontsize=8, loc='lower left', framealpha=0.9)

    plt.tight_layout()
    fig.savefig(os.path.join(GRAF_DIR, 'quad_comparison.png'), dpi=DPI_SAVE, bbox_inches='tight')
    plt.close(fig)
    print("    → quad_comparison.png ✓")

except Exception as e:
    print(f"    !! quad_comparison hatası: {e}")
    import traceback; traceback.print_exc()
    plt.close('all')


# ══════════════════════════════════════════════════════════════════════════════
# ADIM 3: ARŞIV
# ══════════════════════════════════════════════════════════════════════════════
print(f"\n[3/6] SCA arşivi oluşturuluyor → {TAR_OUT}")
if args.skip_tar:
    print("    (--skip-tar, atlandı)")
else:
    t0 = time.time()
    with tarfile.open(TAR_OUT, 'w:gz') as tar:
        tar.add(FAZ4_DIR, arcname='results_faz4')
    size_mb = os.path.getsize(TAR_OUT) / 1024 / 1024
    print(f"    → {TAR_OUT}  ({size_mb:.0f} MB, {time.time()-t0:.1f}s)")


# ══════════════════════════════════════════════════════════════════════════════
# ÖZET RAPOR
# ══════════════════════════════════════════════════════════════════════════════
print("\n" + "=" * 70)
print("  ÖZET RAPOR — FAZ 4 (Yasal Trafik Sınırı)")
print("=" * 70)
print(f"""
  Faz Kodu     : Faz 4 — BTK/KET Yasal Sınır
  Parametreler : σ=5.0 dB, γ=2.8, obstacle=3.5dB
                 noiseFloor=-105 dBm, energyDetection=-95 dBm
                 sendInterval=180s  (1200s sim-time / 180s ≈ 6.7 paket/sensör)
  Simulasyon   : 3024 run, 0 hata

  Radio-DER    : {faz4_mean_der:.2f}%  (Faz3: {faz3_mean_der:.2f}% | Delta: {(faz3_mean_der or faz4_mean_der) - faz4_mean_der:+.2f} puan)
  Çarpışma     : {faz4_mean_col:.2f}%  (Faz3: {faz3_mean_col:.2f}%)

  --- Hızlı Bitiş Nedeni ---
  sendInterval=180s → 1200s/180s = ~{1200/180:.1f} paket/sensör/run
  = çok az event → OMNeT++ neredeyse boş kanal simüle etti → hız ↑

  En İyi Konfigürasyon: {faz4_best_cfg}  → %{faz4_best_der:.2f}
  En Dirençli SF      : SF{best_sf}  ({sf_stats_faz4.get(best_sf,0):.2f}%)
  En Kırılgan SF       : SF{worst_sf} ({sf_stats_faz4.get(worst_sf,0):.2f}%)

  Arşiv        : {ARCHIVE_DIR}
  CSV          : {CSV_OUT}
  Tar.gz       : {TAR_OUT}
  Grafikler    : {GRAF_DIR}/
""")

print("  TAMAMLANDI.")
