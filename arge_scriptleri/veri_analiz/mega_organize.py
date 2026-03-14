#!/usr/bin/env python3
"""
mega_organize.py — Faz 2.1 Düzenleme, Plot ve Arşiv Hazırlama
==============================================================
Faz 2.1 (Doğal Arazi — foliage/wood, σ=4.5, γ=2.8, +3.5 dB obstacle) için:

  Faz21_Arazi1_Dogal_Final/
    Faz21_Ham_Veriler_SCA.tar   ← results_faz2_v2/ tar arşivi
    summary_faz21.csv           ← tam kolonlu CSV
    Grafikler/
      heatmap_der.png           ← DER ısı haritası
      capacity_curve.png        ← kapasite eğrisi
      drop_analysis.png         ← drop analizi (routing layer)
      collision_load.png        ← çarpışma yükü haritası
      sent_vs_scale.png         ← gönderilen paket ölçek
      triple_comparison.png     ← Faz1 vs Faz2 vs Faz2.1 karşılaştırma

Son adım: results_faz2_v2/ tar doğrulanınca sil (disk boşalt).

Kullanım:
    python3 mega_organize.py [--skip-parse]
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
SCRIPT_DIR   = os.path.dirname(os.path.abspath(__file__))
PROJ_DIR     = os.path.abspath(os.path.join(SCRIPT_DIR, '..', '..'))
FAZ21_DIR    = os.path.join(PROJ_DIR, 'results_faz2_v2')
ARCHIVE_DIR  = os.path.join(PROJ_DIR, 'Faz21_Arazi1_Dogal_Final')
GRAF_DIR     = os.path.join(ARCHIVE_DIR, 'Grafikler')
CSV_OUT      = os.path.join(ARCHIVE_DIR, 'summary_faz21.csv')
TAR_OUT      = os.path.join(ARCHIVE_DIR, 'Faz21_Ham_Veriler_SCA.tar')

# Karşılaştırma için önceki fazların CSV'leri
FAZ1_CSV     = os.path.join(PROJ_DIR, 'Faz1_Arazi1_Olceklendirme_Final', 'summary_7x7.csv')
FAZ2_CSV     = os.path.join(PROJ_DIR, 'Faz2_Arazi2_Stres_Final', 'summary_faz2.csv')

os.makedirs(GRAF_DIR, exist_ok=True)

# ─── Argümanlar ───────────────────────────────────────────────────────────────
ap = argparse.ArgumentParser()
ap.add_argument('--skip-parse', action='store_true',
                help='SCA parse atla, mevcut CSV kullan (hızlı mod)')
ap.add_argument('--skip-tar', action='store_true',
                help='Tar oluşturmayı ve silmeyi atla')
args = ap.parse_args()

# ─── Regex & sabitler ─────────────────────────────────────────────────────────
re_fname21    = re.compile(r'^Faz21_GW(\d+)_Mesh(\d+)_(MIN|MAX)-(\d+)\.sca$')
re_gw_radio   = re.compile(r'hybridGW\d+\.LoRaGWNic\.radio$')
re_gw_recv    = re.compile(r'hybridGW\d+\.LoRaGWNic\.radio\.receiver$')
re_sensor_mod = re.compile(r'sensorGW\d+\[\d+\]\.LoRaNic\.mac$')
re_ns_mod     = re.compile(r'networkServer\d+\.app\[0\]$')
re_routing    = re.compile(r'hybridGW\d+\.routingAgent$')

GW_RANGE   = list(range(2, 8))     # 2..7
MESH_RANGE = list(range(1, 8))     # 1..7
MODES      = ['MIN', 'MAX']
SFS        = [7, 8, 9, 10, 11, 12]

# IEEE makale stili
plt.rcParams.update({
    'font.family':    'serif', 'font.size': 10,
    'axes.titlesize': 11,      'axes.labelsize': 10,
    'xtick.labelsize': 9,      'ytick.labelsize': 9,
    'legend.fontsize': 8,      'figure.dpi': 150,
})
DPI_SAVE = 300

COLS = ['gw', 'mesh', 'mode', 'sensorSF', 'meshSF',
        'total_sent', 'total_rcv', 'total_drop',
        'total_rcv_correct', 'total_rcv_started', 'total_collision',
        'radio_der_pct', 'collision_pct', 'der_pct']


# ═══════════════════════════════════════════════════════════════════════════════
def parse_sca(path):
    """Tek bir .sca dosyasından LoRa istatistiklerini çıkar."""
    sent = rcv = drop = 0
    rcv_correct = rcv_started = collision = 0
    sensorSF = meshSF = None

    with open(path, encoding='utf-8', errors='replace') as fh:
        for line in fh:
            line = line.rstrip()
            # iterationvars'tan SF bilgisini al
            if line.startswith('attr iterationvars '):
                ms = re.search(r'\$sensorSF=(\d+)', line)
                ms2 = re.search(r'\$meshSF=(\d+)', line)
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

            if stat == 'numSent' and re_sensor_mod.search(module):
                sent += int(val)
            elif stat == 'totalReceivedPackets' and re_ns_mod.search(module):
                rcv += int(val)
            elif stat == 'droppedPacket:count' and re_routing.search(module):
                drop += int(val)
            elif stat == 'LoRaGWRadioReceptionFinishedCorrect:count' and re_gw_radio.search(module):
                rcv_correct += int(val)
            elif stat == 'LoRaGWRadioReceptionStarted:count' and re_gw_radio.search(module):
                rcv_started += int(val)
            elif stat == 'LoRaReceptionCollision:count' and re_gw_recv.search(module):
                collision += int(val)

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
print("  MEGA ORGANIZE — FAZ 2.1 (Doğal Arazi, σ=4.5, γ=2.8, foliage)")
print("=" * 70)

rows = []

if args.skip_parse and os.path.exists(CSV_OUT):
    print(f"\n[1/5] Mevcut CSV yükleniyor (--skip-parse): {CSV_OUT}")
    with open(CSV_OUT, newline='') as f:
        rd = csv.DictReader(f)
        for row in rd:
            rows.append(row)
    print(f"    {len(rows)} kayıt yüklendi")

if not rows:
    if not os.path.isdir(FAZ21_DIR):
        print(f"\n  HATA: {FAZ21_DIR} bulunamadı.")
        sys.exit(1)

    files = sorted(f for f in os.listdir(FAZ21_DIR) if re_fname21.match(f))
    total = len(files)
    print(f"\n[1/5] SCA parse ediliyor: {FAZ21_DIR}  ({total} dosya)")
    t0 = time.time()

    for i, fname in enumerate(files, 1):
        m = re_fname21.match(fname)
        if not m:
            continue
        gw, mesh, mode, run_no = int(m.group(1)), int(m.group(2)), m.group(3), int(m.group(4))

        d = parse_sca(os.path.join(FAZ21_DIR, fname))

        # SF fallback: run numarasından türet (sensorSF= run//6 offset, meshSF= run%6)
        ssf = d['sensorSF'] if d['sensorSF'] is not None else (7 + run_no // 6)
        msf = d['meshSF']   if d['meshSF']   is not None else (7 + run_no %  6)

        radio_der = (d['total_rcv_correct'] / d['total_rcv_started'] * 100
                     if d['total_rcv_started'] > 0 else 0.0)
        col_pct   = (d['total_collision']   / d['total_rcv_started'] * 100
                     if d['total_rcv_started'] > 0 else 0.0)
        der_pct   = (d['total_rcv'] / d['total_sent'] * 100
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
        })
        if i % 500 == 0:
            print(f"    {i}/{total}  ({time.time()-t0:.1f}s elapsed)", flush=True)

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

for r in rows:
    key = (int(r['gw']), int(r['mesh']), r['mode'])
    agg_der[key].append(float(r['der_pct']))
    agg_radio_der[key].append(float(r['radio_der_pct']))
    agg_drop[key].append(float(r['total_drop']))
    agg_collision[key].append(float(r['collision_pct']))
    agg_sent[key].append(float(r['total_sent']))


# ═══════════════════════════════════════════════════════════════════════════════
# ADIM 2: GRAFİKLER
# ═══════════════════════════════════════════════════════════════════════════════
print(f"\n[2/5] Grafikler üretiliyor → {GRAF_DIR}")

cmap_der  = sns.diverging_palette(10, 130, n=256, as_cmap=True)
cmap_coll = sns.color_palette("RdYlGn_r", as_cmap=True)
gw_colors = plt.cm.plasma(np.linspace(0.05, 0.85, len(GW_RANGE)))

# ── GRAFİK 1: DER Heatmap ─────────────────────────────────────────────────────
fig, axes = plt.subplots(1, 2, figsize=(11, 5))
fig.suptitle(
    "Ortalama Radio-DER (%)  —  Faz 2.1 (σ=4.5 dB, γ=2.8, +3.5 dB foliage)  [7×7]",
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
    ax.set_title(f"Mode={mode}  ({'1 km' if mode == 'MIN' else '6 km'})",
                 fontweight='bold')
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
        p2 = np.poly1d(z)
        x_smooth = np.linspace(xv.min(), xv.max(), 400)
        ax.plot(x_smooth, p2(x_smooth), linewidth=2.2, color=color_map[mode],
                label=f"{mode}  (fit)")
ax.axhline(y=50, color='orange', linestyle='--', linewidth=1.2, alpha=0.8, label="50% eşik")
ax.axhline(y=80, color='gray',   linestyle='--', linewidth=1.2, alpha=0.8, label="80% eşik")
ax.set_xlabel("Toplam Ağ Düğüm Sayısı")
ax.set_ylabel("Ortalama Radio-DER (%)")
ax.set_title("Kapasite Eğrisi — Faz 2.1 (Doğal Arazi)", fontweight='bold')
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
fig.suptitle("Drop Analizi — Faz 2.1: Doğal Engel Altı Routing Kayıpları",
             fontweight='bold', y=1.02)
plt.tight_layout()
fig.savefig(os.path.join(GRAF_DIR, 'drop_analysis.png'), dpi=DPI_SAVE, bbox_inches='tight')
plt.close(fig)
print("    → drop_analysis.png")

# ── GRAFİK 4: Çarpışma Yükü ──────────────────────────────────────────────────
fig, axes = plt.subplots(1, 2, figsize=(11, 5))
fig.suptitle("Ortalama Çarpışma Yükü (%)  —  Faz 2.1 (Doğal Arazi)",
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
fig.suptitle("Gönderilen Toplam Paket — Faz 2.1 (Gerçeklik Kontrolü)",
             fontweight='bold', y=1.02)
plt.tight_layout()
fig.savefig(os.path.join(GRAF_DIR, 'sent_vs_scale.png'), dpi=DPI_SAVE, bbox_inches='tight')
plt.close(fig)
print("    → sent_vs_scale.png")

# ── GRAFİK 6: Triple Comparison (Faz1 vs Faz2 vs Faz2.1) ─────────────────────
print("    → triple_comparison.png (üç faz karşılaştırması)")
try:
    import pandas as pd

    df21 = pd.DataFrame(rows)
    df21['radio_der_pct']  = df21['radio_der_pct'].astype(float)
    df21['collision_pct']  = df21['collision_pct'].astype(float)
    df21['gw']             = df21['gw'].astype(int)
    df21['sensorSF']       = df21['sensorSF'].astype(int)
    df21['phase'] = 'Faz 2.1\n(σ=4.5,γ=2.8,foliage)'

    dfs = []
    if os.path.exists(FAZ1_CSV):
        df1 = pd.read_csv(FAZ1_CSV)
        df1['phase'] = 'Faz 1\n(σ=0,γ=2.75,ideal)'
        dfs.append(df1)
    if os.path.exists(FAZ2_CSV):
        df2 = pd.read_csv(FAZ2_CSV)
        df2['phase'] = 'Faz 2\n(σ=6.0,γ=3.5,beton)'
        dfs.append(df2)
    dfs.append(df21)

    fig, axes = plt.subplots(1, 3, figsize=(15, 5))
    fig.suptitle("Üç Faz Karşılaştırması — Faz 1 vs Faz 2 vs Faz 2.1",
                 fontsize=13, fontweight='bold', y=1.02)

    phase_colors = {
        'Faz 1\n(σ=0,γ=2.75,ideal)':    '#2ecc71',
        'Faz 2\n(σ=6.0,γ=3.5,beton)':   '#e74c3c',
        'Faz 2.1\n(σ=4.5,γ=2.8,foliage)': '#3498db',
    }

    # Panel A: ortalama DER per faz (bar)
    ax = axes[0]
    phase_means = [(df['phase'].iloc[0], df['radio_der_pct'].mean()) for df in dfs]
    labels = [p[0] for p in phase_means]
    vals   = [p[1] for p in phase_means]
    colors_bar = [phase_colors.get(l, '#95a5a6') for l in labels]
    bars = ax.bar(range(len(labels)), vals, color=colors_bar, edgecolor='black', linewidth=0.7)
    ax.set_xticks(range(len(labels)))
    ax.set_xticklabels(labels, fontsize=8)
    ax.set_ylabel("Ortalama Radio-DER (%)")
    ax.set_title("(A) Genel DER Karşılaştırması", fontweight='bold')
    ax.set_ylim(0, 55)
    ax.grid(True, alpha=0.25, linestyle=':', axis='y')
    for bar, v in zip(bars, vals):
        ax.text(bar.get_x() + bar.get_width() / 2, v + 0.8, f"{v:.1f}%",
                ha='center', va='bottom', fontsize=9, fontweight='bold')

    # Panel B: DER vs GW (line plot per faz)
    ax = axes[1]
    for df in dfs:
        phase = df['phase'].iloc[0]
        gw_mean = df.groupby('gw')['radio_der_pct'].mean()
        ax.plot(gw_mean.index, gw_mean.values, marker='o', linewidth=2,
                color=phase_colors.get(phase, '#95a5a6'),
                label=phase.replace('\n', ' '))
    ax.set_xlabel("Gateway Sayısı (GW)")
    ax.set_ylabel("Ortalama Radio-DER (%)")
    ax.set_title("(B) GW Ölçeği→DER İlişkisi", fontweight='bold')
    ax.legend(fontsize=7, loc='upper right', framealpha=0.9)
    ax.grid(True, alpha=0.25, linestyle=':')
    ax.set_xticks(GW_RANGE)

    # Panel C: DER vs sensorSF (line plot per faz)
    ax = axes[2]
    for df in dfs:
        phase = df['phase'].iloc[0]
        sf_mean = df.groupby('sensorSF')['radio_der_pct'].mean()
        ax.plot(sf_mean.index, sf_mean.values, marker='s', linewidth=2,
                color=phase_colors.get(phase, '#95a5a6'),
                label=phase.replace('\n', ' '))
    ax.set_xlabel("Sensör Spreading Factor (SF)")
    ax.set_ylabel("Ortalama Radio-DER (%)")
    ax.set_title("(C) SF Seçimi→DER İlişkisi", fontweight='bold')
    ax.legend(fontsize=7, loc='upper left', framealpha=0.9)
    ax.grid(True, alpha=0.25, linestyle=':')
    ax.set_xticks(SFS)

    plt.tight_layout()
    fig.savefig(os.path.join(GRAF_DIR, 'triple_comparison.png'), dpi=DPI_SAVE, bbox_inches='tight')
    plt.close(fig)
    print("    → triple_comparison.png  ✓")

except Exception as e:
    print(f"    !! triple_comparison.png üretilirken hata: {e}")


# ═══════════════════════════════════════════════════════════════════════════════
# ADIM 3: TAR ARŞİVİ
# ═══════════════════════════════════════════════════════════════════════════════
if not args.skip_tar:
    print(f"\n[3/5] Tar arşivi oluşturuluyor → {TAR_OUT}")
    if os.path.isdir(FAZ21_DIR):
        if os.path.exists(TAR_OUT):
            print(f"    Mevcut tar bulundu, doğrulama yapılıyor...")
        else:
            t0 = time.time()
            sca_files = [f for f in os.listdir(FAZ21_DIR) if f.endswith('.sca')]
            print(f"    Tar'a ekleniyor: {len(sca_files)} SCA dosyası...", flush=True)
            with tarfile.open(TAR_OUT, 'w') as tf:
                for fname in sorted(sca_files):
                    tf.add(os.path.join(FAZ21_DIR, fname), arcname=fname)
            size_gb = os.path.getsize(TAR_OUT) / 1024**3
            print(f"    Tar tamamlandı: {size_gb:.1f} GB  ({time.time()-t0:.0f}s)")

        # Doğrulama ve silme
        sca_count_dir = len([f for f in os.listdir(FAZ21_DIR) if f.endswith('.sca')])
        with tarfile.open(TAR_OUT, 'r') as tf:
            sca_count_tar = sum(1 for m in tf.getmembers() if m.name.endswith('.sca'))
        print(f"    Doğrulama: dizin={sca_count_dir}, tar={sca_count_tar}")
        if sca_count_tar >= sca_count_dir:
            shutil.rmtree(FAZ21_DIR)
            print(f"    ✓ {FAZ21_DIR}/ silindi — {sca_count_dir} SCA boşaltıldı")
        else:
            print(f"    !! Tar uyuşmazlığı ({sca_count_tar} vs {sca_count_dir}) — silme iptal")
    else:
        print(f"    {FAZ21_DIR}/ zaten yok (önceden temizlenmiş)")
else:
    print(f"\n[3/5] Tar arşivi ATLANDI (--skip-tar)")


# ═══════════════════════════════════════════════════════════════════════════════
# ADIM 4: logs temizle
# ═══════════════════════════════════════════════════════════════════════════════
print(f"\n[4/5] Log temizliği...")
logs_dir = os.path.join(PROJ_DIR, 'logs_massive_faz2_v2')
if os.path.isdir(logs_dir):
    size_mb = sum(
        os.path.getsize(os.path.join(root, f))
        for root, _, files in os.walk(logs_dir) for f in files
    ) / 1024**2
    shutil.rmtree(logs_dir)
    print(f"    ✓ {logs_dir}/ silindi  ({size_mb:.0f} MB kazanıldı)")
else:
    print(f"    {logs_dir}/ zaten yok")


# ═══════════════════════════════════════════════════════════════════════════════
# ADIM 5: ÖZET
# ═══════════════════════════════════════════════════════════════════════════════
print(f"\n[5/5] Düzenleme tamamlandı!\n")
print("  Faz21_Arazi1_Dogal_Final/")
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

# Disk durumu
import subprocess
df_out = subprocess.run(['df', '-h', PROJ_DIR], capture_output=True, text=True)
print(f"\n  Disk durumu:\n{df_out.stdout.strip()}")
print()
