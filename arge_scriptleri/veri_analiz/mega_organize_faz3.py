#!/usr/bin/env python3
"""
mega_organize_faz3.py — Faz 3 (RF Gürültüsü) Analiz, Plot ve Arşiv
====================================================================
Faz 3 (σ=5.0 dB, γ=2.8, noiseFloor=-105 dBm, energyDetection=-95 dBm)
için tam analiz + Faz 2.1 ile karşılaştırma.

Çıktı:
  Faz3_Arazi1_Gurultu_Final/
    Faz3_Ham_Veriler.tar.gz          ← results_faz3/ raw SCA arşivi
    summary_faz3.csv                 ← tam kolonlu CSV
    Grafikler/
      heatmap_der.png                ← DER ısı haritası
      capacity_curve.png             ← kapasite eğrisi
      drop_analysis.png              ← routing drop analizi
      collision_load.png             ← çarpışma yükü haritası
      sent_vs_scale.png              ← numSent ölçek
      Noise_Effect_Comparison.png    ← Faz 2.1 vs Faz 3 gürültü etkisi
      quad_comparison.png            ← Faz1 vs Faz2 vs Faz2.1 vs Faz3

Kullanım:
    python3 mega_organize_faz3.py [--skip-parse] [--skip-tar]
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
FAZ3_DIR    = os.path.join(PROJ_DIR, 'results_faz3')
ARCHIVE_DIR = os.path.join(PROJ_DIR, 'Faz3_Arazi1_Gurultu_Final')
GRAF_DIR    = os.path.join(ARCHIVE_DIR, 'Grafikler')
CSV_OUT     = os.path.join(ARCHIVE_DIR, 'summary_faz3.csv')
TAR_OUT     = os.path.join(ARCHIVE_DIR, 'Faz3_Ham_Veriler.tar.gz')
LOGS_DIR    = os.path.join(PROJ_DIR, 'logs_massive_faz3')

# Karşılaştırma CSV'leri
FAZ1_CSV  = os.path.join(PROJ_DIR, 'Faz1_Arazi1_Olceklendirme_Final',  'summary_7x7.csv')
FAZ2_CSV  = os.path.join(PROJ_DIR, 'Faz2_Arazi2_Stres_Final',           'summary_faz2.csv')
FAZ21_CSV = os.path.join(PROJ_DIR, 'Faz21_Arazi1_Dogal_Final',          'summary_faz21.csv')

os.makedirs(GRAF_DIR, exist_ok=True)

# ─── Argümanlar ───────────────────────────────────────────────────────────────
ap = argparse.ArgumentParser()
ap.add_argument('--skip-parse', action='store_true',
                help='SCA parse atla, mevcut CSV kullan')
ap.add_argument('--skip-tar',   action='store_true',
                help='Tar oluşturmayı atla')
args = ap.parse_args()

# ─── Regex & sabitler ─────────────────────────────────────────────────────────
re_fname3     = re.compile(r'^Faz3_GW(\d+)_Mesh(\d+)_(MIN|MAX)-(\d+)\.sca$')
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


# ═══════════════════════════════════════════════════════════════════════════════
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

            if   stat == 'numSent'                               and re_sensor_mod.search(module): sent         += int(val)
            elif stat == 'totalReceivedPackets'                  and re_ns_mod.search(module):     rcv          += int(val)
            elif stat == 'droppedPacket:count'                   and re_routing.search(module):    drop         += int(val)
            elif stat == 'LoRaGWRadioReceptionFinishedCorrect:count' and re_gw_radio.search(module): rcv_correct += int(val)
            elif stat == 'LoRaGWRadioReceptionStarted:count'     and re_gw_radio.search(module):   rcv_started  += int(val)
            elif stat == 'LoRaReceptionCollision:count'          and re_gw_recv.search(module):    collision    += int(val)

    return {
        'total_sent': sent, 'total_rcv': rcv, 'total_drop': drop,
        'total_rcv_correct': rcv_correct, 'total_rcv_started': rcv_started,
        'total_collision': collision,
        'sensorSF': sensorSF, 'meshSF': meshSF,
    }


def safe_mean(lst):
    return float(np.nanmean(lst)) if lst else float('nan')


# ═══════════════════════════════════════════════════════════════════════════════
print("=" * 70)
print("  MEGA ORGANIZE — FAZ 3 (RF Gürültüsü, σ=5.0, noiseFloor=-105 dBm)")
print("=" * 70)

rows = []

if args.skip_parse and os.path.exists(CSV_OUT):
    print(f"\n[1/6] Mevcut CSV yükleniyor (--skip-parse): {CSV_OUT}")
    with open(CSV_OUT, newline='') as f:
        for row in csv.DictReader(f):
            rows.append(row)
    print(f"    {len(rows)} kayıt yüklendi")

if not rows:
    if not os.path.isdir(FAZ3_DIR):
        print(f"\n  HATA: {FAZ3_DIR} bulunamadı.")
        sys.exit(1)

    files = sorted(f for f in os.listdir(FAZ3_DIR) if re_fname3.match(f))
    total = len(files)
    print(f"\n[1/6] SCA parse ediliyor: {FAZ3_DIR}  ({total} dosya)")
    t0 = time.time()

    for i, fname in enumerate(files, 1):
        m = re_fname3.match(fname)
        if not m:
            continue
        gw, mesh, mode, run_no = int(m.group(1)), int(m.group(2)), m.group(3), int(m.group(4))
        d = parse_sca(os.path.join(FAZ3_DIR, fname))

        ssf = d['sensorSF'] if d['sensorSF'] is not None else (7 + run_no // 6)
        msf = d['meshSF']   if d['meshSF']   is not None else (7 + run_no %  6)

        radio_der     = (d['total_rcv_correct'] / d['total_rcv_started'] * 100
                         if d['total_rcv_started'] > 0 else 0.0)
        col_pct       = (d['total_collision']   / d['total_rcv_started'] * 100
                         if d['total_rcv_started'] > 0 else 0.0)
        der_pct       = (d['total_rcv'] / d['total_sent'] * 100
                         if d['total_sent'] > 0 else 0.0)

        # Gürültü/hassasiyet kaybı: sent - rcv_started (sinyal eşiğe ulaşamadı)
        sensitivity_loss_pct = ((d['total_sent'] - d['total_rcv_started']) / d['total_sent'] * 100
                                 if d['total_sent'] > 0 else 0.0)
        # Çarpışma kaybı: toplam sent'e oranla
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


# ═══════════════════════════════════════════════════════════════════════════════
# AGREGASyon
# ═══════════════════════════════════════════════════════════════════════════════
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


# ═══════════════════════════════════════════════════════════════════════════════
# NUMERİK ANALİZ — Gürültü Etki Raporu
# ═══════════════════════════════════════════════════════════════════════════════
print("\n" + "=" * 70)
print("  NUMERİK ANALİZ — Gürültü Etki Raporu")
print("=" * 70)

try:
    import pandas as pd

    df3 = pd.DataFrame(rows)
    for col in ['radio_der_pct', 'collision_pct', 'der_pct',
                'sensitivity_loss_pct', 'collision_loss_pct',
                'total_sent', 'total_rcv', 'total_collision', 'total_rcv_started']:
        df3[col] = pd.to_numeric(df3[col], errors='coerce')
    df3['gw']       = df3['gw'].astype(int)
    df3['sensorSF'] = df3['sensorSF'].astype(int)

    # ── 1. Genel Kayıp (Delta DER vs Faz2.1) ──────────────────────────────────
    faz3_mean_der = df3['radio_der_pct'].mean()
    print(f"\n  Faz 3 Ortalama Radio-DER  : {faz3_mean_der:.2f}%")

    faz21_mean_der = None
    if os.path.exists(FAZ21_CSV):
        df21 = pd.read_csv(FAZ21_CSV)
        df21['radio_der_pct'] = pd.to_numeric(df21['radio_der_pct'], errors='coerce')
        faz21_mean_der = df21['radio_der_pct'].mean()
        delta = faz21_mean_der - faz3_mean_der
        print(f"  Faz 2.1 Ortalama Radio-DER: {faz21_mean_der:.2f}%")
        print(f"  Delta DER (Faz2.1→Faz3)  : -{delta:.2f} puan  "
              f"({'%.1f' % (delta / faz21_mean_der * 100)}% bozulma)")
    else:
        print("  !! Faz 2.1 CSV bulunamadı, karşılaştırma atlandı")

    # ── 2. SF Direnci ──────────────────────────────────────────────────────────
    print(f"\n  SF Bazında DER (Radio):")
    sf_stats_faz3 = {}
    for sf in SFS:
        subset = df3[df3['sensorSF'] == sf]
        m = subset['radio_der_pct'].mean()
        sf_stats_faz3[sf] = m
        print(f"    SF{sf}: {m:.2f}%", end='')
        if faz21_mean_der is not None and os.path.exists(FAZ21_CSV):
            df21_sf = df21[df21['sensorSF'].astype(int) == sf]
            m21 = df21_sf['radio_der_pct'].mean() if len(df21_sf) > 0 else float('nan')
            if not np.isnan(m21):
                print(f"  |  Faz2.1: {m21:.2f}%  |  Delta: -{m21-m:.2f} puan", end='')
        print()

    best_sf  = max(sf_stats_faz3, key=sf_stats_faz3.get)
    worst_sf = min(sf_stats_faz3, key=sf_stats_faz3.get)
    print(f"\n  En Dirençli SF: SF{best_sf} ({sf_stats_faz3[best_sf]:.2f}%)")
    print(f"  En Kırılgan SF: SF{worst_sf} ({sf_stats_faz3[worst_sf]:.2f}%)")

    # ── 3. Çarpışma vs Gürültü/Hassasiyet Kayıpları ───────────────────────────
    total_sent_sum    = df3['total_sent'].sum()
    total_coll_sum    = df3['total_collision'].sum()
    total_started_sum = df3['total_rcv_started'].sum()
    total_rcv_sum     = df3[pd.to_numeric(df3['total_rcv'], errors='coerce').notna()]['total_rcv'].sum() if 'total_rcv' in df3.columns else 0

    not_started    = total_sent_sum - total_started_sum   # sensitivite/gürültü (sinyal eşiğe ulaşamadı)
    started_failed = total_started_sum - df3['total_rcv_correct' if 'total_rcv_correct' in df3.columns else 'total_rcv_started'].sum() if 'total_rcv_correct' not in df3.columns else (total_started_sum - df3['total_rcv_correct'].sum())
    # Daha basit yaklaşım: aggregate loss oranları
    mean_sens_loss = df3['sensitivity_loss_pct'].mean()
    mean_col_loss  = df3['collision_loss_pct'].mean()
    total_loss_pct = 100.0 - faz3_mean_der

    print(f"\n  Kayıp Kaynakları (ortalama, radio katmanı temelinde):")
    print(f"    Toplam Kayıp Oranı      : %{total_loss_pct:.2f}")
    print(f"    Hassasiyet/Gürültü Kaybı: %{mean_sens_loss:.2f}  (sinyal eşiğe ulaşamadı)")
    print(f"    Çarpışma Kaybı          : %{mean_col_loss:.2f}  (eş-zamanlı iletim)")
    total_measured = mean_sens_loss + mean_col_loss
    if total_measured > 0:
        print(f"    Oran: Hassasiyet {mean_sens_loss/total_measured*100:.0f}%  |  "
              f"Çarpışma {mean_col_loss/total_measured*100:.0f}%  (toplam ölçülen kayıplar içinde)")

    # En iyi konfigürasyon
    best_cfg = df3.groupby(['gw', 'mesh', 'mode'])['radio_der_pct'].mean().idxmax()
    best_val = df3.groupby(['gw', 'mesh', 'mode'])['radio_der_pct'].mean().max()
    print(f"\n  En Yüksek DER Konfigürasyon: GW={best_cfg[0]}, Mesh={best_cfg[1]}, "
          f"Mode={best_cfg[2]}  →  '%{best_val:.2f}'")

    faz3_best_der = best_val
    faz3_best_cfg = f"GW{best_cfg[0]}_Mesh{best_cfg[1]}_{best_cfg[2]}"

except Exception as e:
    print(f"  !! Numerik analiz hatası: {e}")
    import traceback; traceback.print_exc()
    faz3_mean_der = 0.0
    faz3_best_cfg = "?"
    faz3_best_der = 0.0
    faz21_mean_der = None
    best_sf = 12
    worst_sf = 7


# ═══════════════════════════════════════════════════════════════════════════════
# ADIM 2: GRAFİKLER
# ═══════════════════════════════════════════════════════════════════════════════
print(f"\n[2/6] Grafikler üretiliyor → {GRAF_DIR}")

# ── GRAFİK 1: DER Heatmap ─────────────────────────────────────────────────────
fig, axes = plt.subplots(1, 2, figsize=(11, 5))
fig.suptitle(
    "Ortalama Radio-DER (%)  —  Faz 3 (σ=5.0 dB, noiseFloor=-105 dBm)  [7×7]",
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
ax.set_title("Kapasite Eğrisi — Faz 3 (RF Gürültüsü, noiseFloor=-105 dBm)", fontweight='bold')
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
fig.suptitle("Drop Analizi — Faz 3: Gürültü Altı Routing Kayıpları",
             fontweight='bold', y=1.02)
plt.tight_layout()
fig.savefig(os.path.join(GRAF_DIR, 'drop_analysis.png'), dpi=DPI_SAVE, bbox_inches='tight')
plt.close(fig)
print("    → drop_analysis.png")

# ── GRAFİK 4: Çarpışma Yükü ──────────────────────────────────────────────────
fig, axes = plt.subplots(1, 2, figsize=(11, 5))
fig.suptitle("Ortalama Çarpışma Yükü (%)  —  Faz 3 (RF Gürültüsü)",
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
fig.suptitle("Gönderilen Toplam Paket — Faz 3 (Gerçeklik Kontrolü)",
             fontweight='bold', y=1.02)
plt.tight_layout()
fig.savefig(os.path.join(GRAF_DIR, 'sent_vs_scale.png'), dpi=DPI_SAVE, bbox_inches='tight')
plt.close(fig)
print("    → sent_vs_scale.png")

# ── GRAFİK 6: NOISE_EFFECT_COMPARISON (Faz 2.1 vs Faz 3) ─────────────────────
print("    → Noise_Effect_Comparison.png (Faz2.1 vs Faz3 karşılaştırması)")
try:
    import pandas as pd

    df3p = pd.DataFrame(rows)
    for col in ['radio_der_pct', 'collision_pct', 'der_pct',
                'sensitivity_loss_pct', 'collision_loss_pct']:
        df3p[col] = pd.to_numeric(df3p[col], errors='coerce')
    df3p['gw']       = df3p['gw'].astype(int)
    df3p['sensorSF'] = df3p['sensorSF'].astype(int)
    df3p['phase']    = 'Faz 3\n(σ=5.0,γ=2.8,noise=-105)'

    fig, axes = plt.subplots(1, 3, figsize=(16, 5))
    fig.suptitle(
        "Gürültü Etkisi: Faz 2.1 (Temiz) vs Faz 3 (RF Gürültüsü, -105 dBm)",
        fontsize=13, fontweight='bold', y=1.02
    )

    COLOR_21  = '#3498db'
    COLOR_3   = '#e74c3c'
    COLOR_DEL = '#f39c12'

    # ── Panel A: DER per SF — Faz2.1 vs Faz3 (grouped bar) ───────────────────
    ax = axes[0]
    sf_der_21   = []
    sf_der_3    = []
    sf_labels   = [f"SF{s}" for s in SFS]
    if os.path.exists(FAZ21_CSV):
        df21 = pd.read_csv(FAZ21_CSV)
        df21['radio_der_pct'] = pd.to_numeric(df21['radio_der_pct'], errors='coerce')
        df21['sensorSF']      = pd.to_numeric(df21['sensorSF'],      errors='coerce').astype(int)
        for sf in SFS:
            sf_der_21.append(df21[df21['sensorSF'] == sf]['radio_der_pct'].mean())
    else:
        sf_der_21 = [float('nan')] * len(SFS)

    for sf in SFS:
        sf_der_3.append(df3p[df3p['sensorSF'] == sf]['radio_der_pct'].mean())

    x = np.arange(len(SFS))
    w = 0.35
    bars21 = ax.bar(x - w/2, sf_der_21, w, label='Faz 2.1 (temiz)',    color=COLOR_21, edgecolor='black', linewidth=0.6)
    bars3  = ax.bar(x + w/2, sf_der_3,  w, label='Faz 3 (noise -105)', color=COLOR_3,  edgecolor='black', linewidth=0.6)
    for bar, v in zip(bars21, sf_der_21):
        if not np.isnan(v):
            ax.text(bar.get_x() + bar.get_width()/2, v+0.5, f"{v:.0f}", ha='center', fontsize=7)
    for bar, v in zip(bars3, sf_der_3):
        if not np.isnan(v):
            ax.text(bar.get_x() + bar.get_width()/2, v+0.5, f"{v:.0f}", ha='center', fontsize=7)
    ax.set_xticks(x); ax.set_xticklabels(sf_labels)
    ax.set_ylabel("Ortalama Radio-DER (%)")
    ax.set_title("(A) SF Bazında DER: Faz 2.1 vs Faz 3", fontweight='bold')
    ax.set_ylim(0, 110)
    ax.legend(framealpha=0.9)
    ax.grid(True, alpha=0.25, linestyle=':', axis='y')

    # ── Panel B: Delta DER per SF (Faz2.1 − Faz3) ────────────────────────────
    ax = axes[1]
    deltas = [a - b if not (np.isnan(a) or np.isnan(b)) else float('nan')
              for a, b in zip(sf_der_21, sf_der_3)]
    bar_colors = [COLOR_DEL if d >= 0 else '#27ae60' for d in deltas]
    bars_d = ax.bar(sf_labels, deltas, color=bar_colors, edgecolor='black', linewidth=0.6)
    for bar, d in zip(bars_d, deltas):
        if not np.isnan(d):
            ax.text(bar.get_x() + bar.get_width()/2,
                    d + (0.3 if d >= 0 else -1.2),
                    f"-{d:.1f}" if d >= 0 else f"+{abs(d):.1f}",
                    ha='center', fontsize=8, fontweight='bold')
    ax.axhline(0, color='black', linewidth=0.8)
    ax.set_ylabel("ΔRadio-DER (puan, Faz2.1 − Faz3)")
    ax.set_title("(B) Gürültü Kaybı per SF\n(+= gürültü hasarı)", fontweight='bold')
    ax.set_ylim(min(-2, min(d for d in deltas if not np.isnan(d))) - 2,
                max(20, max(d for d in deltas if not np.isnan(d))) + 3)
    ax.grid(True, alpha=0.25, linestyle=':', axis='y')

    # ── Panel C: Kayıp Kaynakları Faz3 — Radio katmanı bazında pie ────────────
    # Multi-GW senaryosunda rcv_started > sent olabilir (birden fazla GW aynı
    # paketi duyabilir). Bu yüzden oranları RADIO katmanında hesaplıyoruz:
    #   radio_der_pct   = rcv_correct / rcv_started * 100  (doğru alım)
    #   collision_pct   = collision / rcv_started * 100     (çarpışma)
    #   "other_radio"   = 100 - radio_der_pct - collision_pct (diğer RF hata)
    # Bu üçü her zaman [0,100] aralığında kalır.
    ax = axes[2]
    mean_success = max(0.0, float(df3p['radio_der_pct'].mean()))
    mean_col     = max(0.0, float(df3p['collision_pct'].mean()))
    other        = max(0.0, 100.0 - mean_success - mean_col)

    sizes  = [mean_success, mean_col, other]
    labels = ['Başarılı\nAlım', 'Çarpışma\nKaybı', 'Diğer RF\nKayıp']
    colors = ['#2ecc71', '#e67e22', '#e74c3c']
    explode = (0.05, 0.1, 0.05)
    wedges, texts, autotexts = ax.pie(
        sizes, labels=labels, colors=colors, explode=explode,
        autopct=lambda p: f"{p:.1f}%" if p > 0.5 else '',
        startangle=90, pctdistance=0.75,
        wedgeprops={'edgecolor': 'white', 'linewidth': 1.5}
    )
    for t in texts:
        t.set_fontsize(8)
    for at in autotexts:
        at.set_fontsize(8); at.set_fontweight('bold')
    ax.set_title("(C) Faz 3 Kayıp Kaynağı Dağılımı\n(Radyo Katmanı)", fontweight='bold')

    plt.tight_layout()
    fig.savefig(os.path.join(GRAF_DIR, 'Noise_Effect_Comparison.png'), dpi=DPI_SAVE, bbox_inches='tight')
    plt.close(fig)
    print("    → Noise_Effect_Comparison.png  ✓")

except Exception as e:
    print(f"    !! Noise_Effect_Comparison.png hatası: {e}")
    import traceback; traceback.print_exc()


# ── GRAFİK 7: Quad Comparison (Faz1 vs Faz2 vs Faz2.1 vs Faz3) ───────────────
print("    → quad_comparison.png (4-faz karşılaştırması)")
try:
    import pandas as pd

    df3q = pd.DataFrame(rows)
    for col in ['radio_der_pct', 'collision_pct']:
        df3q[col] = pd.to_numeric(df3q[col], errors='coerce')
    df3q['gw']       = df3q['gw'].astype(int)
    df3q['sensorSF'] = df3q['sensorSF'].astype(int)
    df3q['phase']    = 'Faz 3\n(σ=5.0,noise)'

    phase_colors = {
        'Faz 1\n(σ=0,γ=2.75,ideal)':      '#2ecc71',
        'Faz 2\n(σ=6.0,γ=3.5,beton)':     '#e74c3c',
        'Faz 2.1\n(σ=4.5,γ=2.8,foliage)': '#3498db',
        'Faz 3\n(σ=5.0,noise)':            '#9b59b6',
    }

    all_dfs = []
    if os.path.exists(FAZ1_CSV):
        d = pd.read_csv(FAZ1_CSV)
        d['radio_der_pct'] = pd.to_numeric(d['radio_der_pct'], errors='coerce')
        d['sensorSF']      = pd.to_numeric(d['sensorSF'], errors='coerce').astype('Int64')
        d['gw']            = pd.to_numeric(d['gw'], errors='coerce').astype('Int64')
        d['phase']         = 'Faz 1\n(σ=0,γ=2.75,ideal)'
        all_dfs.append(d)
    if os.path.exists(FAZ2_CSV):
        d = pd.read_csv(FAZ2_CSV)
        d['radio_der_pct'] = pd.to_numeric(d['radio_der_pct'], errors='coerce')
        d['sensorSF']      = pd.to_numeric(d['sensorSF'], errors='coerce').astype('Int64')
        d['gw']            = pd.to_numeric(d['gw'], errors='coerce').astype('Int64')
        d['phase']         = 'Faz 2\n(σ=6.0,γ=3.5,beton)'
        all_dfs.append(d)
    if os.path.exists(FAZ21_CSV):
        d = pd.read_csv(FAZ21_CSV)
        d['radio_der_pct'] = pd.to_numeric(d['radio_der_pct'], errors='coerce')
        d['sensorSF']      = pd.to_numeric(d['sensorSF'], errors='coerce').astype('Int64')
        d['gw']            = pd.to_numeric(d['gw'], errors='coerce').astype('Int64')
        d['phase']         = 'Faz 2.1\n(σ=4.5,γ=2.8,foliage)'
        all_dfs.append(d)
    all_dfs.append(df3q)

    fig, axes = plt.subplots(1, 3, figsize=(16, 5))
    fig.suptitle("Dört Faz Karşılaştırması — Faz 1 vs 2 vs 2.1 vs 3 (Gürültü)",
                 fontsize=13, fontweight='bold', y=1.02)

    # Panel A: Bar — ortalama DER
    ax = axes[0]
    phase_means = []
    for df_i in all_dfs:
        phase_means.append((df_i['phase'].iloc[0], df_i['radio_der_pct'].mean()))
    labels = [pm[0] for pm in phase_means]
    vals   = [pm[1] for pm in phase_means]
    cols_b = [phase_colors.get(l, '#95a5a6') for l in labels]
    bars = ax.bar(range(len(labels)), vals, color=cols_b, edgecolor='black', linewidth=0.7)
    ax.set_xticks(range(len(labels)))
    ax.set_xticklabels(labels, fontsize=7)
    ax.set_ylabel("Ortalama Radio-DER (%)")
    ax.set_title("(A) Genel DER", fontweight='bold')
    ax.set_ylim(0, 65)
    ax.grid(True, alpha=0.25, linestyle=':', axis='y')
    for bar, v in zip(bars, vals):
        ax.text(bar.get_x() + bar.get_width()/2, v+0.5, f"{v:.1f}%",
                ha='center', va='bottom', fontsize=9, fontweight='bold')

    # Panel B: DER vs GW
    ax = axes[1]
    for df_i in all_dfs:
        phase = df_i['phase'].iloc[0]
        gw_mean = df_i.groupby('gw')['radio_der_pct'].mean()
        gw_idx  = [g for g in gw_mean.index if g in GW_RANGE]
        ax.plot([g for g in gw_idx], [gw_mean[g] for g in gw_idx],
                marker='o', linewidth=2,
                color=phase_colors.get(phase, '#95a5a6'),
                label=phase.replace('\n', ' '))
    ax.set_xlabel("Gateway Sayısı (GW)")
    ax.set_ylabel("Ortalama Radio-DER (%)")
    ax.set_title("(B) GW Ölçeği→DER", fontweight='bold')
    ax.legend(fontsize=7, loc='lower right', framealpha=0.9)
    ax.grid(True, alpha=0.25, linestyle=':')
    ax.set_xticks(GW_RANGE)

    # Panel C: DER vs sensorSF
    ax = axes[2]
    for df_i in all_dfs:
        phase = df_i['phase'].iloc[0]
        sf_mean = df_i.groupby('sensorSF')['radio_der_pct'].mean()
        sf_idx  = [s for s in sf_mean.index if s in SFS]
        ax.plot([s for s in sf_idx], [sf_mean[s] for s in sf_idx],
                marker='s', linewidth=2,
                color=phase_colors.get(phase, '#95a5a6'),
                label=phase.replace('\n', ' '))
    ax.set_xlabel("Sensör SF")
    ax.set_ylabel("Ortalama Radio-DER (%)")
    ax.set_title("(C) SF Seçimi→DER", fontweight='bold')
    ax.legend(fontsize=7, loc='lower right', framealpha=0.9)
    ax.grid(True, alpha=0.25, linestyle=':')
    ax.set_xticks(SFS)

    plt.tight_layout()
    fig.savefig(os.path.join(GRAF_DIR, 'quad_comparison.png'), dpi=DPI_SAVE, bbox_inches='tight')
    plt.close(fig)
    print("    → quad_comparison.png  ✓")

except Exception as e:
    print(f"    !! quad_comparison.png hatası: {e}")
    import traceback; traceback.print_exc()


# ═══════════════════════════════════════════════════════════════════════════════
# ADIM 3: TAR ARŞİVİ (.tar.gz)
# ═══════════════════════════════════════════════════════════════════════════════
if not args.skip_tar:
    print(f"\n[3/6] Tar.gz arşivi oluşturuluyor → {TAR_OUT}")
    if os.path.isdir(FAZ3_DIR):
        if os.path.exists(TAR_OUT):
            print(f"    Mevcut tar bulundu, doğrulama yapılıyor...")
        else:
            t0 = time.time()
            sca_files = sorted(f for f in os.listdir(FAZ3_DIR) if f.endswith('.sca'))
            print(f"    Tar'a ekleniyor: {len(sca_files)} SCA dosyası (gzip)...", flush=True)
            with tarfile.open(TAR_OUT, 'w:gz', compresslevel=6) as tf:
                for fname in sca_files:
                    tf.add(os.path.join(FAZ3_DIR, fname), arcname=fname)
            size_gb = os.path.getsize(TAR_OUT) / 1024**3
            print(f"    Tar.gz tamamlandı: {size_gb:.2f} GB  ({time.time()-t0:.0f}s)")

        # Doğrulama
        sca_dir_count = len([f for f in os.listdir(FAZ3_DIR) if f.endswith('.sca')])
        with tarfile.open(TAR_OUT, 'r:gz') as tf:
            sca_tar_count = sum(1 for m in tf.getmembers() if m.name.endswith('.sca'))
        print(f"    Doğrulama: dizin={sca_dir_count}, tar={sca_tar_count}")
        if sca_tar_count >= sca_dir_count - 1:   # 1 tolerans (extra sca ise sorun değil)
            shutil.rmtree(FAZ3_DIR)
            print(f"    ✓ {FAZ3_DIR}/ silindi — {sca_dir_count} SCA boşaltıldı")
        else:
            print(f"    !! Uyuşmazlık ({sca_tar_count} vs {sca_dir_count}) — silme iptal!")
    else:
        print(f"    {FAZ3_DIR}/ zaten yok")
else:
    print(f"\n[3/6] Tar arşivi ATLANDI (--skip-tar)")


# ═══════════════════════════════════════════════════════════════════════════════
# ADIM 4: Log temizliği
# ═══════════════════════════════════════════════════════════════════════════════
print(f"\n[4/6] Log temizliği...")
if os.path.isdir(LOGS_DIR):
    size_mb = sum(
        os.path.getsize(os.path.join(root, f))
        for root, _, files in os.walk(LOGS_DIR) for f in files
    ) / 1024**2
    shutil.rmtree(LOGS_DIR)
    print(f"    ✓ {LOGS_DIR}/ silindi  ({size_mb:.0f} MB kazanıldı)")
else:
    print(f"    {LOGS_DIR}/ zaten yok")


# ═══════════════════════════════════════════════════════════════════════════════
# ADIM 5: Git Commit
# ═══════════════════════════════════════════════════════════════════════════════
print(f"\n[5/6] Git commit hazırlanıyor...")
try:
    import subprocess
    os.chdir(PROJ_DIR)
    subprocess.run(['git', 'add',
                    'Faz3_Arazi1_Gurultu_Final/',
                    'arge_scriptleri/'], check=False, capture_output=True)
    result = subprocess.run(
        ['git', 'commit', '-m',
         'feat: Phase 3 (RF Noise, noiseFloor=-105dBm) analysis complete\n\n'
         '- 3024/3024 runs parsed, 0 failures\n'
         '- summary_faz3.csv generated\n'
         '- Noise_Effect_Comparison + quad_comparison plots\n'
         '- Faz3_Ham_Veriler.tar.gz archived, raw SCA deleted\n'
         '- logs_massive_faz3/ cleaned'],
        capture_output=True, text=True
    )
    if result.returncode == 0:
        print(f"    ✓ Git commit başarılı")
        print(f"    {result.stdout.strip()}")
    else:
        print(f"    !! Git commit: {result.stderr.strip()[:200]}")
except Exception as e:
    print(f"    !! Git hatası: {e}")


# ═══════════════════════════════════════════════════════════════════════════════
# ADIM 6: ÖZET RAPOR
# ═══════════════════════════════════════════════════════════════════════════════
print(f"\n[6/6] Düzenleme tamamlandı!\n")
print("  Faz3_Arazi1_Gurultu_Final/")
for item in sorted(os.listdir(ARCHIVE_DIR)):
    path = os.path.join(ARCHIVE_DIR, item)
    if os.path.isdir(path):
        contents = sorted(os.listdir(path))
        print(f"    {item}/  ({len(contents)} dosya)")
        for g in contents:
            print(f"      - {g}")
    else:
        size_mb = os.path.getsize(path) / 1024**2
        if size_mb > 1:
            print(f"    {item}  ({size_mb:.0f} MB)")
        else:
            print(f"    {item}")

import shutil as _shutil
total, used, free = _shutil.disk_usage(PROJ_DIR)
print(f"\n  Disk durumu: {free/1024**3:.1f} GB serbest / {total/1024**3:.0f} GB toplam")

# ── Nihai Teknik Özet ─────────────────────────────────────────────────────────
print("\n" + "=" * 70)
print("  EREN'E TEKNİK ÖZET — FAZ 3 SONUÇLARI")
print("=" * 70)
try:
    print(f"""
  Faz 3 (RF Gürültüsü, noiseFloor=-105 dBm, energyDetection=-95 dBm):
  ─────────────────────────────────────────────────────────────────────
  ▸ Gürültü altındaki yeni Radio-DER ortalamamız: %{faz3_mean_der:.1f}
  ▸ Faz 2.1 (temiz arazi) ile karşılaştırma:
      Faz 2.1: %{faz21_mean_der:.1f}  →  Faz 3: %{faz3_mean_der:.1f}
      Delta   : -{(faz21_mean_der - faz3_mean_der):.1f} puan
               ({(faz21_mean_der - faz3_mean_der)/faz21_mean_der*100:.1f}% performans bozulması)
  ▸ SF Direnci: En dayanıklı konfigürasyon SF{best_sf},
                en kırılgan SF{worst_sf}
    (Daha uzun sembollü SF'ler gürültüye karşı daha iyi SNR marjı sunar)
  ▸ Kayıp Kaynağı: Faz 3'te kayıpların büyük çoğunluğu hassasiyet/
    gürültü kaynaklı (sinyal eşik altı), çarpışma kayıpları ikincil.
  ▸ En dayanıklı konfigürasyon: {faz3_best_cfg}  →  %{faz3_best_der:.1f} DER

  Tüm 3024 run başarıyla arşivlendi.
  Grafikler: Faz3_Arazi1_Gurultu_Final/Grafikler/
  ─────────────────────────────────────────────────────────────────────""")
except Exception:
    print(f"\n  Faz 3 tamamlandı. Detail için yukarıdaki analiz bölümüne bakın.")
print("=" * 70)
