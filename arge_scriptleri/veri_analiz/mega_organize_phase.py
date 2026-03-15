#!/usr/bin/env python3
"""
mega_organize_phase.py — Evrensel Faz Analiz, Plot ve Arşiv Scripti
====================================================================
Tüm fazlar için tek script. --phase N ile çağrılır.

Desteklenen fazlar: 1, 2, 21, 3, 4

Çıktı:
  <ARCHIVE_DIR>/
    <PREFIX>Ham_Veriler.tar.gz
    summary_faz<N>.csv
    Grafikler/
      heatmap_der.png
      capacity_curve.png
      drop_analysis.png
      collision_load.png
      sent_vs_scale.png
      comparison.png          ← mevcut faz vs önceki faz
      quad_comparison.png     ← tüm mevcut faz CSV'leri

Kullanım:
    python3 mega_organize_phase.py --phase 1
    python3 mega_organize_phase.py --phase 4 --skip-tar
    python3 mega_organize_phase.py --phase 21 --skip-parse
"""

import os
import re
import csv
import time
import sys
import tarfile
import argparse
from collections import defaultdict

import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import seaborn as sns

# ─── Argümanlar ───────────────────────────────────────────────────────────────
ap = argparse.ArgumentParser()
ap.add_argument('--phase', type=int, required=True, choices=[1, 2, 21, 3, 4],
                help='Faz numarası: 1, 2, 21, 3 veya 4')
ap.add_argument('--skip-parse', action='store_true',
                help='SCA parse atla, mevcut CSV kullan')
ap.add_argument('--skip-tar', action='store_true',
                help='Tar oluşturmayı atla')
args = ap.parse_args()

PHASE = args.phase

# ─── Faz Metadata ─────────────────────────────────────────────────────────────
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJ_DIR   = os.path.abspath(os.path.join(SCRIPT_DIR, '..', '..'))

PHASE_META = {
    1:  {
        'label':      'Faz 1 — İdeal (σ=0, γ=2.75)',
        'params':     'σ=0 dB, γ=2.75, obstacle=0 dB, sendInterval=180s',
        'prefix':     'Scalable_',
        'regex':      re.compile(r'^Scalable_GW(\d+)_Mesh(\d+)_(MIN|MAX)-(\d+)\.sca$'),
        'result_dir': 'results',
        'archive':    'Faz1_Ideal_YasalSinir_Final',
        'tar_name':   'Faz1_Ham_Veriler.tar.gz',
        'csv_name':   'summary_faz1.csv',
        'color':      '#2ecc71',
        'prev':       [],
    },
    2:  {
        'label':      'Faz 2 — Beton 7dB (σ=6.0, γ=3.5)',
        'params':     'σ=6.0 dB, γ=3.5, obstacle=7.0 dB (beton), sendInterval=180s',
        'prefix':     'Faz2_',
        'regex':      re.compile(r'^Faz2_GW(\d+)_Mesh(\d+)_(MIN|MAX)-(\d+)\.sca$'),
        'result_dir': 'results_faz2',
        'archive':    'Faz2_Beton7dB_YasalSinir_Final',
        'tar_name':   'Faz2_Ham_Veriler.tar.gz',
        'csv_name':   'summary_faz2.csv',
        'color':      '#e67e22',
        'prev':       [1],
    },
    21: {
        'label':      'Faz 2.1 — Dogal (σ=4.5, γ=2.8)',
        'params':     'σ=4.5 dB, γ=2.8, obstacle=3.5 dB (foliage), sendInterval=180s',
        'prefix':     'Faz21_',
        'regex':      re.compile(r'^Faz21_GW(\d+)_Mesh(\d+)_(MIN|MAX)-(\d+)\.sca$'),
        'result_dir': 'results_faz2_v2',
        'archive':    'Faz21_Dogal_YasalSinir_Final',
        'tar_name':   'Faz21_Ham_Veriler.tar.gz',
        'csv_name':   'summary_faz21.csv',
        'color':      '#9b59b6',
        'prev':       [1, 2],
    },
    3:  {
        'label':      'Faz 3 — Gurultu (σ=5.0, γ=2.8, NF=-105dBm)',
        'params':     'σ=5.0 dB, γ=2.8, obstacle=3.5 dB, noiseFloor=-105 dBm, sendInterval=180s',
        'prefix':     'Faz3_',
        'regex':      re.compile(r'^Faz3_GW(\d+)_Mesh(\d+)_(MIN|MAX)-(\d+)\.sca$'),
        'result_dir': 'results_faz3',
        'archive':    'Faz3_Gurultu_YasalSinir_Final',
        'tar_name':   'Faz3_Ham_Veriler.tar.gz',
        'csv_name':   'summary_faz3.csv',
        'color':      '#3498db',
        'prev':       [1, 2, 21],
    },
    4:  {
        'label':      'Faz 4 — Yasal Sinir (σ=5.0, γ=2.8, NF=-105dBm, 180s)',
        'params':     'σ=5.0 dB, γ=2.8, obstacle=3.5 dB, noiseFloor=-105 dBm, sendInterval=180s',
        'prefix':     'Faz4_',
        'regex':      re.compile(r'^Faz4_GW(\d+)_Mesh(\d+)_(MIN|MAX)-(\d+)\.sca$'),
        'result_dir': 'results_faz4',
        'archive':    'Faz4_YasalSinir_Final',
        'tar_name':   'Faz4_Ham_Veriler.tar.gz',
        'csv_name':   'summary_faz4.csv',
        'color':      '#e74c3c',
        'prev':       [1, 2, 21, 3],
    },
}

# CSV yollarını hesapla (her fazın arşiv dizinindeki CSV)
def get_csv_path(phase_no):
    m = PHASE_META[phase_no]
    return os.path.join(PROJ_DIR, m['archive'], m['csv_name'])

meta       = PHASE_META[PHASE]
RESULT_DIR = os.path.join(PROJ_DIR, meta['result_dir'])
ARCHIVE_DIR = os.path.join(PROJ_DIR, meta['archive'])
GRAF_DIR    = os.path.join(ARCHIVE_DIR, 'Grafikler')
CSV_OUT     = os.path.join(ARCHIVE_DIR, meta['csv_name'])
TAR_OUT     = os.path.join(ARCHIVE_DIR, meta['tar_name'])
re_fname    = meta['regex']

os.makedirs(GRAF_DIR, exist_ok=True)

# ─── OMNeT++ Regex'leri ───────────────────────────────────────────────────────
re_gw_radio   = re.compile(r'hybridGW\d+\.LoRaGWNic\.radio$')
re_gw_recv    = re.compile(r'hybridGW\d+\.LoRaGWNic\.radio\.receiver$')
re_sensor_mod = re.compile(r'sensorGW\d+\[\d+\]\.LoRaNic\.mac$')
re_ns_mod     = re.compile(r'networkServer\d+\.app\[0\]$')
re_routing    = re.compile(r'hybridGW\d+\.routingAgent$')

GW_RANGE   = list(range(2, 8))
MESH_RANGE = list(range(1, 8))
MODES      = ['MIN', 'MAX']
SFS        = [7, 8, 9, 10, 11, 12]

COLS = ['gw', 'mesh', 'mode', 'sensorSF', 'meshSF',
        'total_sent', 'total_rcv', 'total_drop',
        'total_rcv_correct', 'total_rcv_started', 'total_collision',
        'radio_der_pct', 'collision_pct', 'der_pct',
        'sensitivity_loss_pct', 'collision_loss_pct']

plt.rcParams.update({
    'font.family': 'serif', 'font.size': 10,
    'axes.titlesize': 11,   'axes.labelsize': 10,
    'xtick.labelsize': 9,   'ytick.labelsize': 9,
    'legend.fontsize': 8,   'figure.dpi': 150,
})
DPI_SAVE = 300


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


def load_csv(path):
    """CSV yükle, yoksa boş list döndür."""
    if not os.path.exists(path):
        return []
    rows = []
    with open(path, newline='') as f:
        for row in csv.DictReader(f):
            rows.append(row)
    return rows


# ══════════════════════════════════════════════════════════════════════════════
print("=" * 70)
print(f"  MEGA ORGANIZE — {meta['label']}")
print(f"  {meta['params']}")
print("=" * 70)

# ── ADIM 1: SCA PARSE ─────────────────────────────────────────────────────────
rows = []

if args.skip_parse and os.path.exists(CSV_OUT):
    print(f"\n[1/6] Mevcut CSV yükleniyor (--skip-parse): {CSV_OUT}")
    rows = load_csv(CSV_OUT)
    print(f"    {len(rows)} kayıt yüklendi")

if not rows:
    if not os.path.isdir(RESULT_DIR):
        print(f"\n  HATA: Sonuç dizini bulunamadı: {RESULT_DIR}")
        sys.exit(1)

    files  = sorted(f for f in os.listdir(RESULT_DIR) if re_fname.match(f))
    total  = len(files)
    if total == 0:
        print(f"\n  HATA: {RESULT_DIR} içinde eşleşen SCA dosyası bulunamadı.")
        sys.exit(1)
    print(f"\n[1/6] SCA parse ediliyor: {RESULT_DIR}  ({total} dosya)")
    t0 = time.time()

    for i, fname in enumerate(files, 1):
        m = re_fname.match(fname)
        if not m:
            continue
        gw, mesh, mode, run_no = int(m.group(1)), int(m.group(2)), m.group(3), int(m.group(4))
        d = parse_sca(os.path.join(RESULT_DIR, fname))

        ssf = d['sensorSF'] if d['sensorSF'] is not None else (7 + run_no // 6)
        msf = d['meshSF']   if d['meshSF']   is not None else (7 + run_no %  6)

        radio_der  = (d['total_rcv_correct'] / d['total_rcv_started'] * 100
                      if d['total_rcv_started'] > 0 else 0.0)
        col_pct    = (d['total_collision']   / d['total_rcv_started'] * 100
                      if d['total_rcv_started'] > 0 else 0.0)
        der_pct    = (d['total_rcv'] / d['total_sent'] * 100
                      if d['total_sent'] > 0 else 0.0)
        sens_loss  = ((d['total_sent'] - d['total_rcv_started']) / d['total_sent'] * 100
                       if d['total_sent'] > 0 else 0.0)
        col_loss   = (d['total_collision'] / d['total_sent'] * 100
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
            'sensitivity_loss_pct': sens_loss,
            'collision_loss_pct':   col_loss,
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

# ── AGREGASyon ─────────────────────────────────────────────────────────────────
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

# ── NUMERİK ANALİZ ────────────────────────────────────────────────────────────
print(f"\n[Analiz] {meta['label']}")
try:
    import pandas as pd
    df_cur = pd.DataFrame(rows)
    for col in ['radio_der_pct', 'collision_pct', 'der_pct',
                'sensitivity_loss_pct', 'collision_loss_pct',
                'total_sent', 'total_rcv', 'total_collision', 'total_rcv_started']:
        df_cur[col] = pd.to_numeric(df_cur[col], errors='coerce')
    df_cur['gw']       = df_cur['gw'].astype(int)
    df_cur['sensorSF'] = df_cur['sensorSF'].astype(int)

    mean_der  = df_cur['radio_der_pct'].mean()
    mean_col  = df_cur['collision_pct'].mean()
    mean_sent = df_cur['total_sent'].mean()

    print(f"  Ortalama Radio-DER     : {mean_der:.2f}%")
    print(f"  Ortalama Carpısma       : {mean_col:.2f}%")
    print(f"  Ortalama numSent        : {mean_sent:.1f} paket/run")
    print(f"  SF Bazinda DER:")
    sf_stats = {}
    for sf in SFS:
        sub = df_cur[df_cur['sensorSF'] == sf]
        m = sub['radio_der_pct'].mean()
        sf_stats[sf] = m
        print(f"    SF{sf}: {m:.2f}%")
    best_sf  = max(sf_stats, key=sf_stats.get) if sf_stats else 12
    worst_sf = min(sf_stats, key=sf_stats.get) if sf_stats else 7

    mean_sens_loss = df_cur['sensitivity_loss_pct'].mean()
    mean_col_loss  = df_cur['collision_loss_pct'].mean()
    best_cfg = df_cur.groupby(['gw', 'mesh', 'mode'])['radio_der_pct'].mean().idxmax()
    best_val = df_cur.groupby(['gw', 'mesh', 'mode'])['radio_der_pct'].mean().max()
    best_cfg_str = f"GW{best_cfg[0]}_Mesh{best_cfg[1]}_{best_cfg[2]}"
    print(f"  En iyi konfig: {best_cfg_str} → %{best_val:.2f}")

except Exception as e:
    print(f"  !! Analiz hatasi: {e}")
    import traceback; traceback.print_exc()
    mean_der = mean_col = mean_sent = 0.0
    sf_stats = {sf: 0.0 for sf in SFS}
    best_sf = worst_sf = 12
    mean_sens_loss = mean_col_loss = 0.0
    best_cfg_str = "?"
    best_val = 0.0
    df_cur = pd.DataFrame(rows) if 'pd' in dir() else None

# ══════════════════════════════════════════════════════════════════════════════
# ADIM 2: GRAFİKLER
# ══════════════════════════════════════════════════════════════════════════════
print(f"\n[2/6] Grafikler uretiliyor → {GRAF_DIR}")

phase_title = meta['label']

# ── GRAFİK 1: DER Heatmap ─────────────────────────────────────────────────────
fig, axes = plt.subplots(1, 2, figsize=(11, 5))
fig.suptitle(f"Ortalama Radio-DER (%)  —  {phase_title}  [7×7]",
             fontsize=12, fontweight='bold', y=1.01)
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
    ax.set_xlabel("Mesh Node Sayisi")
    ax.set_ylabel("Gateway Sayisi")
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
                xs.append(gw * 10 + mesh)
                ys.append(safe_mean(v))
    if not xs:
        continue
    xs, ys = np.array(xs), np.array(ys)
    valid  = ~np.isnan(ys)
    xv, yv = xs[valid], ys[valid]
    ax.scatter(xv, yv, alpha=0.30, s=20, color=color_map[mode],
               marker=marker_map[mode], zorder=2)
    if len(xv) >= 3:
        z = np.polyfit(xv, yv, 2)
        x_smooth = np.linspace(xv.min(), xv.max(), 400)
        ax.plot(x_smooth, np.poly1d(z)(x_smooth), linewidth=2.2,
                color=color_map[mode], label=f"{mode}  (fit)")
ax.axhline(y=50, color='orange', linestyle='--', linewidth=1.2, alpha=0.8, label="50% esik")
ax.axhline(y=80, color='gray',   linestyle='--', linewidth=1.2, alpha=0.8, label="80% esik")
ax.set_xlabel("GW×10+Mesh (agirlik indeksi)")
ax.set_ylabel("Ortalama Radio-DER (%)")
ax.set_title(f"Kapasite Egrisi — {phase_title}", fontweight='bold')
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
    ax.set_xlabel("Mesh Node Sayisi")
    ax.set_ylabel("Ortalama Drop Count")
    ax.set_xticks(MESH_RANGE)
    ax.legend(fontsize=8, ncol=2, loc='upper left', framealpha=0.8)
    ax.grid(True, alpha=0.25, linestyle=':')
fig.suptitle(f"Drop Analizi — {phase_title}", fontweight='bold', y=1.02)
plt.tight_layout()
fig.savefig(os.path.join(GRAF_DIR, 'drop_analysis.png'), dpi=DPI_SAVE, bbox_inches='tight')
plt.close(fig)
print("    → drop_analysis.png")

# ── GRAFİK 4: Çarpışma Yükü ──────────────────────────────────────────────────
fig, axes = plt.subplots(1, 2, figsize=(11, 5))
fig.suptitle(f"Ortalama Carpısma Yuku (%)  —  {phase_title}",
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
                cbar_kws={'label': 'Carpısma Yuku (%)', 'shrink': 0.85},
                annot_kws={'size': 8})
    ax.set_title(f"Mode={mode}  ({'1 km' if mode == 'MIN' else '6 km'})", fontweight='bold')
    ax.set_xlabel("Mesh Node Sayisi")
    ax.set_ylabel("Gateway Sayisi")
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
    ax.set_xlabel("Mesh Node Sayisi")
    ax.set_ylabel("Ortalama numSent (paket)")
    ax.set_xticks(MESH_RANGE)
    ax.legend(fontsize=8, ncol=2, loc='upper left', framealpha=0.8)
    ax.grid(True, alpha=0.25, linestyle=':')
fig.suptitle(f"Gonderilen Toplam Paket — {phase_title}", fontweight='bold', y=1.02)
plt.tight_layout()
fig.savefig(os.path.join(GRAF_DIR, 'sent_vs_scale.png'), dpi=DPI_SAVE, bbox_inches='tight')
plt.close(fig)
print("    → sent_vs_scale.png")

# ── GRAFİK 6: Karşılaştırma (mevcut vs önceki faz) ───────────────────────────
print("    → comparison.png (mevcut faz vs onceki faz)")
try:
    import pandas as pd

    prev_phases = meta['prev']
    prev_dfs = []
    for pno in prev_phases:
        pcsv = get_csv_path(pno)
        if os.path.exists(pcsv):
            dftmp = pd.read_csv(pcsv)
            dftmp['radio_der_pct'] = pd.to_numeric(dftmp['radio_der_pct'], errors='coerce')
            dftmp['collision_pct'] = pd.to_numeric(dftmp['collision_pct'], errors='coerce')
            dftmp['total_sent']    = pd.to_numeric(dftmp['total_sent'],    errors='coerce')
            dftmp['sensorSF']      = pd.to_numeric(dftmp['sensorSF'],      errors='coerce')
            dftmp['phase_label']   = PHASE_META[pno]['label']
            dftmp['phase_color']   = PHASE_META[pno]['color']
            prev_dfs.append((pno, dftmp))

    df_c = df_cur.copy() if df_cur is not None else pd.DataFrame(rows)
    for col in ['radio_der_pct', 'collision_pct', 'total_sent', 'sensorSF']:
        df_c[col] = pd.to_numeric(df_c[col], errors='coerce')
    df_c['phase_label'] = meta['label']
    df_c['phase_color'] = meta['color']

    all_phases_for_plot = prev_dfs + [(PHASE, df_c)]

    n_panels = 3
    fig, axes = plt.subplots(1, n_panels, figsize=(6 * n_panels, 5))
    fig.suptitle(
        f"Karşılaştırma: {' vs '.join([PHASE_META[p]['label'].split('—')[0].strip() for p, _ in all_phases_for_plot])}",
        fontsize=12, fontweight='bold', y=1.02
    )

    # Panel A: Radio-DER kutu
    ax = axes[0]
    der_data, der_lbls, box_cols = [], [], []
    for pno, dftmp in all_phases_for_plot:
        vals = dftmp['radio_der_pct'].dropna().values
        if len(vals) > 0:
            der_data.append(vals)
            der_lbls.append(f"Faz {pno}" if pno != 21 else "Faz 2.1")
            box_cols.append(PHASE_META[pno]['color'])
    if der_data:
        positions = list(range(1, len(der_data) + 1))
        bp = ax.boxplot(der_data, positions=positions, patch_artist=True,
                        medianprops=dict(color='black', linewidth=2), widths=0.55)
        for patch, col in zip(bp['boxes'], box_cols):
            patch.set_facecolor(col); patch.set_alpha(0.75)
        ax.set_xticks(positions)
        ax.set_xticklabels(der_lbls, fontsize=8)
    ax.set_title("Radio-DER Dağılımı", fontweight='bold')
    ax.set_ylabel("Radio-DER (%)")
    ax.set_ylim(0, 108)
    ax.axhline(y=50, color='orange', linestyle='--', linewidth=1, alpha=0.7)
    ax.axhline(y=80, color='gray',   linestyle='--', linewidth=1, alpha=0.7)
    ax.grid(True, alpha=0.2, linestyle=':', axis='y')
    plt.suptitle(
        f"Karşılaştırma: {' vs '.join([PHASE_META[p]['label'].split('—')[0].strip() for p, _ in all_phases_for_plot])}",
        fontsize=12, fontweight='bold', y=1.02
    )

    # Panel B: SF bazında DER çubuk
    ax = axes[1]
    x = np.arange(len(SFS))
    width = 0.8 / max(len(all_phases_for_plot), 1)
    for idx, (pno, dftmp) in enumerate(all_phases_for_plot):
        sf_means = []
        for sf in SFS:
            sub = dftmp[dftmp['sensorSF'] == sf]
            sf_means.append(sub['radio_der_pct'].mean() if len(sub) > 0 else 0.0)
        offset = (idx - (len(all_phases_for_plot) - 1) / 2) * width
        bars = ax.bar(x + offset, sf_means, width * 0.92,
                      label=f"Faz {pno}" if pno != 21 else "Faz 2.1",
                      color=PHASE_META[pno]['color'], alpha=0.8, edgecolor='white')
        for bar in bars:
            h = bar.get_height()
            if not np.isnan(h) and h > 3:
                ax.annotate(f'{h:.0f}', xy=(bar.get_x() + bar.get_width()/2, h),
                            xytext=(0, 2), textcoords='offset points',
                            ha='center', va='bottom', fontsize=6)
    ax.set_title("SF Bazında Radio-DER", fontweight='bold')
    ax.set_xlabel("Spreading Factor")
    ax.set_ylabel("Ort. Radio-DER (%)")
    ax.set_xticks(x)
    ax.set_xticklabels([f"SF{sf}" for sf in SFS])
    ax.set_ylim(0, 115)
    ax.legend(framealpha=0.9, fontsize=7)
    ax.grid(True, alpha=0.2, linestyle=':', axis='y')

    # Panel C: Ort. DER çubuk + Çarpışma ikincil
    ax   = axes[2]
    ax2  = ax.twinx()
    lbls, der_means, col_means, bar_cols_c = [], [], [], []
    for pno, dftmp in all_phases_for_plot:
        lbls.append(f"Faz {pno}" if pno != 21 else "Faz 2.1")
        der_means.append(dftmp['radio_der_pct'].mean())
        col_means.append(dftmp['collision_pct'].mean())
        bar_cols_c.append(PHASE_META[pno]['color'])
    x3   = np.arange(len(lbls))
    bars = ax.bar(x3, der_means, color=bar_cols_c, alpha=0.8, edgecolor='white',
                  width=0.5, label='Ort. Radio-DER')
    ax.set_title("Ort. DER & Çarpışma Karşılaştırması", fontweight='bold')
    ax.set_ylabel("Radio-DER (%)")
    ax.set_xticks(x3)
    ax.set_xticklabels(lbls)
    ax.set_ylim(0, 115)
    ax.grid(True, alpha=0.2, linestyle=':', axis='y')
    for bar, val in zip(bars, der_means):
        if not np.isnan(val):
            ax.text(bar.get_x() + bar.get_width()/2, val + 1,
                    f'{val:.1f}%', ha='center', va='bottom', fontsize=9, fontweight='bold')
    col_max = max((v for v in col_means if not np.isnan(v)), default=10)
    ax2.plot(x3, col_means, 'D--', color='#c0392b', linewidth=2, markersize=8,
             label='Ort. Çarpışma', alpha=0.9)
    ax2.set_ylabel("Çarpışma Oranı (%)", color='#c0392b')
    ax2.tick_params(axis='y', labelcolor='#c0392b')
    ax2.set_ylim(0, max(col_max * 2.0, 15))
    for xi, cv in zip(x3, col_means):
        if not np.isnan(cv):
            ax2.text(xi + 0.12, cv + 0.3, f'{cv:.1f}%', ha='left', va='bottom',
                     fontsize=8, color='#c0392b', fontweight='bold')
    lines1, labels1 = ax.get_legend_handles_labels()
    lines2, labels2 = ax2.get_legend_handles_labels()
    ax.legend(lines1 + lines2, labels1 + labels2, fontsize=8, loc='lower left', framealpha=0.9)

    plt.tight_layout()
    fig.savefig(os.path.join(GRAF_DIR, 'comparison.png'), dpi=DPI_SAVE, bbox_inches='tight')
    plt.close(fig)
    print("    → comparison.png ✓")

except Exception as e:
    print(f"    !! comparison.png hatası: {e}")
    import traceback; traceback.print_exc()
    plt.close('all')

# ── GRAFİK 7: QUAD COMPARISON (tüm mevcut fazlar) ────────────────────────────
print("    → quad_comparison.png (tum mevcut fazlar)")
try:
    import pandas as pd

    all_phase_order  = [1, 2, 21, 3, 4]
    quad_phase_csvs = []
    for pno in all_phase_order:
        pcsv = get_csv_path(pno)
        if os.path.exists(pcsv):
            quad_phase_csvs.append((pno, pcsv, PHASE_META[pno]))

    if len(quad_phase_csvs) < 1:
        print("    !! quad_comparison: hic CSV bulunamadi, atlanıyor.")
    else:
        fig, axes = plt.subplots(1, 2, figsize=(14, 6))
        fig.suptitle(
            "Tüm Fazlar Karşılaştırması: İdeal → Beton → Dogal → Gurultu → Yasal",
            fontsize=12, fontweight='bold', y=1.02
        )

        # Panel A: Radio-DER kutular
        ax = axes[0]
        der_data, der_lbls, box_cols = [], [], []
        for pno, pcsv, pmeta in quad_phase_csvs:
            dftmp = pd.read_csv(pcsv)
            dftmp['radio_der_pct'] = pd.to_numeric(dftmp['radio_der_pct'], errors='coerce')
            vals = dftmp['radio_der_pct'].dropna().values
            if len(vals) > 0:
                der_data.append(vals)
                der_lbls.append(f"Faz {pno}" if pno != 21 else "Faz 2.1")
                box_cols.append(pmeta['color'])
        if der_data:
            positions = list(range(1, len(der_data) + 1))
            bp = ax.boxplot(der_data, positions=positions, patch_artist=True,
                            medianprops=dict(color='black', linewidth=2), widths=0.55)
            for patch, col in zip(bp['boxes'], box_cols):
                patch.set_facecolor(col); patch.set_alpha(0.75)
            ax.set_xticks(positions)
            ax.set_xticklabels(der_lbls, fontsize=8)
            for pos, data in zip(positions, der_data):
                med = float(np.median(data))
                ax.text(pos, med + 1.5, f'{med:.1f}%', ha='center', va='bottom',
                        fontsize=8, fontweight='bold')
        ax.set_title("Radio-DER Dağılımı (Tüm Fazlar)", fontweight='bold')
        ax.set_ylabel("Radio-DER (%)")
        ax.set_ylim(0, 110)
        ax.axhline(y=50, color='orange', linestyle='--', linewidth=1.2, alpha=0.7)
        ax.axhline(y=80, color='gray',   linestyle='--', linewidth=1.2, alpha=0.7)
        ax.grid(True, alpha=0.2, linestyle=':', axis='y')

        # Panel B: Ort. DER çubuk + Çarpışma çizgi
        ax   = axes[1]
        ax2t = ax.twinx()
        lbls_q, der_q, col_q, bar_q = [], [], [], []
        for pno, pcsv, pmeta in quad_phase_csvs:
            dftmp = pd.read_csv(pcsv)
            dftmp['radio_der_pct'] = pd.to_numeric(dftmp['radio_der_pct'], errors='coerce')
            dftmp['collision_pct'] = pd.to_numeric(dftmp['collision_pct'], errors='coerce')
            lbls_q.append(f"Faz {pno}" if pno != 21 else "Faz 2.1")
            der_q.append(dftmp['radio_der_pct'].mean())
            col_q.append(dftmp['collision_pct'].mean())
            bar_q.append(pmeta['color'])
        x3   = np.arange(len(lbls_q))
        bars = ax.bar(x3, der_q, color=bar_q, alpha=0.8, edgecolor='white',
                      width=0.5, label='Ort. Radio-DER')
        ax.set_title("Ort. Radio-DER & Çarpışma (Tüm Fazlar)", fontweight='bold')
        ax.set_ylabel("Radio-DER (%)")
        ax.set_xticks(x3)
        ax.set_xticklabels(lbls_q, fontsize=8)
        ax.set_ylim(0, 115)
        ax.grid(True, alpha=0.2, linestyle=':', axis='y')
        for bar, val in zip(bars, der_q):
            if not np.isnan(val):
                ax.text(bar.get_x() + bar.get_width()/2, val + 1,
                        f'{val:.1f}%', ha='center', va='bottom', fontsize=9, fontweight='bold')
        col_max_q = max((v for v in col_q if not np.isnan(v)), default=10)
        ax2t.plot(x3, col_q, 'D--', color='#c0392b', linewidth=2, markersize=8,
                  label='Ort. Çarpışma', alpha=0.9)
        ax2t.set_ylabel("Çarpışma Oranı (%)", color='#c0392b')
        ax2t.tick_params(axis='y', labelcolor='#c0392b')
        ax2t.set_ylim(0, max(col_max_q * 2.0, 15))
        for xi, cv in zip(x3, col_q):
            if not np.isnan(cv) and cv > 0.1:
                ax2t.text(xi + 0.12, cv + 0.3, f'{cv:.1f}%', ha='left', va='bottom',
                          fontsize=8, color='#c0392b', fontweight='bold')
        lines1, labels1 = ax.get_legend_handles_labels()
        lines2, labels2 = ax2t.get_legend_handles_labels()
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
# ADIM 3: ARŞİV
# ══════════════════════════════════════════════════════════════════════════════
print(f"\n[3/6] SCA arsivi olusturuluyor → {TAR_OUT}")
if args.skip_tar:
    print("    (--skip-tar, atlandi)")
else:
    t0 = time.time()
    with tarfile.open(TAR_OUT, 'w:gz') as tar:
        tar.add(RESULT_DIR, arcname=meta['result_dir'])
    size_mb = os.path.getsize(TAR_OUT) / 1024 / 1024
    print(f"    → {TAR_OUT}  ({size_mb:.0f} MB, {time.time()-t0:.1f}s)")

# ══════════════════════════════════════════════════════════════════════════════
# ÖZET RAPOR
# ══════════════════════════════════════════════════════════════════════════════
print("\n" + "=" * 70)
print(f"  ÖZET — {meta['label']}")
print("=" * 70)
# Önceki fazların DER'lerini topla (karşılaştırma için)
prev_der_str = ""
for pno in meta['prev'][-1:]:  # sadece son önceki faz
    pcsv = get_csv_path(pno)
    if os.path.exists(pcsv):
        try:
            import pandas as pd
            dftmp = pd.read_csv(pcsv)
            prev_mean = pd.to_numeric(dftmp['radio_der_pct'], errors='coerce').mean()
            delta = prev_mean - mean_der
            sign  = '-' if delta >= 0 else '+'
            prev_der_str = f"  Önceki Faz ({pno}) DER: {prev_mean:.2f}%  |  Delta: {sign}{abs(delta):.2f} puan"
        except Exception:
            pass

print(f"""
  Faz Kodu     : Faz {PHASE}
  Parametreler : {meta['params']}

  Radio-DER    : {mean_der:.2f}%
  Çarpışma     : {mean_col:.2f}%
  Ort. numSent : {mean_sent:.1f} paket/run
{prev_der_str}

  En İyi Konfig    : {best_cfg_str}  → %{best_val:.2f}
  En Dirençli SF   : SF{best_sf}  ({sf_stats.get(best_sf,0):.2f}%)
  En Kırılgan SF   : SF{worst_sf} ({sf_stats.get(worst_sf,0):.2f}%)

  Arşiv   : {ARCHIVE_DIR}
  CSV     : {CSV_OUT}
  Tar.gz  : {TAR_OUT}
  Grafikler: {GRAF_DIR}/
""")
print("  TAMAMLANDI.")
