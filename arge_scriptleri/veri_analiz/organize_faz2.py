#!/usr/bin/env python3
"""
organize_faz2.py — Faz 2 Düzenleme, Plot ve Arşiv Hazırlama
=============================================================
Faz 1 ile aynı yapıyı Faz 2 için oluşturur:

  Faz2_Arazi2_Stres_Final/
    Faz2_Ham_Veriler_SCA.tar   ← zaten mevcut (finalizer tarafından)
    summary_faz2.csv           ← tam kolonlu CSV (bu script üretir)
    Grafikler/
      heatmap_der.png          ← Faz 2 DER ısı haritası
      capacity_curve.png       ← Faz 2 kapasite eğrisi
      drop_analysis.png        ← Faz 2 drop analizi
      collision_load.png       ← Faz 2 çarpışma yükü
      sent_vs_scale.png        ← Faz 2 gönderilen paket ölçek
      heatmap_faz1_vs_faz2.png ← Karşılaştırma (mevcut)
      sf_resilience_matrix.png ← SF dayanıklılık matrisi
      degradation_distribution.png
      gw_der_comparison.png

Son adım: results_faz2/ klasörünü siler (7.8 GB kazanç).

Kullanım:
    python3 organize_faz2.py [--skip-parse]
"""

import os, re, csv, time, sys, shutil, argparse
from collections import defaultdict

import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import seaborn as sns

# ─── Dizinler ─────────────────────────────────────────────────────────────────
SCRIPT_DIR   = os.path.dirname(os.path.abspath(__file__))
PROJ_DIR     = os.path.abspath(os.path.join(SCRIPT_DIR, '..', '..'))
FAZ2_DIR     = os.path.join(PROJ_DIR, 'results_faz2')
ARCHIVE_DIR  = os.path.join(PROJ_DIR, 'Faz2_Arazi2_Stres_Final')
GRAF_DIR     = os.path.join(ARCHIVE_DIR, 'Grafikler')
CSV_OUT      = os.path.join(ARCHIVE_DIR, 'summary_faz2.csv')
CMP_PLOTS    = os.path.join(SCRIPT_DIR, 'plots_faz2_comparison')
TMP_CSV      = os.path.join(SCRIPT_DIR, 'summary_faz2.csv')  # önceki geçici

os.makedirs(GRAF_DIR, exist_ok=True)

# ─── Argümanlar ───────────────────────────────────────────────────────────────
ap = argparse.ArgumentParser()
ap.add_argument('--skip-parse', action='store_true',
                help='SCA parse atla, mevcut geçici CSV kullan (hızlı mod)')
args = ap.parse_args()

# ─── Regex ────────────────────────────────────────────────────────────────────
re_fname2     = re.compile(r'^Faz2_GW(\d+)_Mesh(\d+)_(MIN|MAX)-sensorSF=(\d+),meshSF=(\d+),')
re_sensor_mod = re.compile(r'sensorGW\d+\[\d+\]\.LoRaNic\.mac$')
re_ns_mod     = re.compile(r'networkServer\d+\.app\[0\]$')
re_routing    = re.compile(r'hybridGW\d+\.routingAgent$')
re_gw_radio   = re.compile(r'hybridGW\d+\.LoRaGWNic\.radio$')
re_gw_recv    = re.compile(r'hybridGW\d+\.LoRaGWNic\.radio\.receiver$')

GW_RANGE   = list(range(2, 8))
MESH_RANGE = list(range(1, 8))
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


# ═══════════════════════════════════════════════════════════════════════════════
def parse_sca(path):
    sent = rcv = drop = 0
    rcv_correct = rcv_started = collision = 0
    with open(path, encoding='utf-8', errors='replace') as fh:
        for line in fh:
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
    }


def safe_mean(lst):
    return float(np.nanmean(lst)) if lst else float('nan')


# ═══════════════════════════════════════════════════════════════════════════════
# ADIM 1: SCA PARSE veya CSV yükle
# ═══════════════════════════════════════════════════════════════════════════════
print("=" * 70)
print("  ORGANIZE FAZ 2")
print("=" * 70)

COLS = ['gw','mesh','mode','sensorSF','meshSF',
        'total_sent','total_rcv','total_drop',
        'total_rcv_correct','total_rcv_started','total_collision',
        'radio_der_pct','collision_pct','der_pct']

rows = []

if args.skip_parse and os.path.exists(TMP_CSV):
    print(f"\n[1/4] Mevcut CSV yükleniyor (--skip-parse): {TMP_CSV}")
    # Geçici CSV'nin kolonu eksik olabilir — tekrar parse gerekebilir
    with open(TMP_CSV, newline='') as f:
        rd = csv.DictReader(f)
        existing_cols = rd.fieldnames or []
        if 'total_drop' not in existing_cols:
            print("    !! Geçici CSV'de total_drop yok → parse yapılacak")
            args.skip_parse = False
        else:
            for row in rd:
                rows.append({k: (int(row[k]) if k not in ('mode','radio_der_pct','collision_pct','der_pct') else row[k])
                              for k in row})

if not args.skip_parse:
    if not os.path.isdir(FAZ2_DIR):
        print(f"\n  HATA: {FAZ2_DIR} bulunamadı. --skip-parse kullanmayı deneyin.")
        sys.exit(1)

    print(f"\n[1/4] SCA dosyaları parse ediliyor: {FAZ2_DIR}")
    t0 = time.time()
    files = sorted(os.listdir(FAZ2_DIR))
    total = len(files)
    for i, fname in enumerate(files, 1):
        m = re_fname2.match(fname)
        if not m:
            continue
        gw, mesh, mode = int(m.group(1)), int(m.group(2)), m.group(3)
        ssf, msf       = int(m.group(4)), int(m.group(5))
        d = parse_sca(os.path.join(FAZ2_DIR, fname))
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
        if i % 300 == 0:
            print(f"    {i}/{total}  ({time.time()-t0:.1f}s)", flush=True)

    print(f"    {len(rows)} kayıt parse edildi ({time.time()-t0:.1f}s)")

# CSV kaydet (arşiv dizinine, Faz 1 format uyumu)
with open(CSV_OUT, 'w', newline='') as f:
    w = csv.DictWriter(f, fieldnames=COLS)
    w.writeheader()
    for r in rows:
        w.writerow({c: r[c] for c in COLS})
print(f"    CSV → {CSV_OUT}")

# Geçici CSV (arge_scriptleri/summary_faz2.csv) → sil
if os.path.exists(TMP_CSV) and os.path.abspath(TMP_CSV) != os.path.abspath(CSV_OUT):
    os.remove(TMP_CSV)
    print(f"    Geçici CSV silindi: {TMP_CSV}")


# ═══════════════════════════════════════════════════════════════════════════════
# AGREGASyon (Faz 1 ile birebir aynı strüktür)
# ═══════════════════════════════════════════════════════════════════════════════
agg_der       = defaultdict(list)
agg_radio_der = defaultdict(list)
agg_drop      = defaultdict(list)
agg_collision = defaultdict(list)
agg_sent      = defaultdict(list)

for r in rows:
    key = (r['gw'], r['mesh'], r['mode'])
    agg_der[key].append(float(r['der_pct']))
    agg_radio_der[key].append(float(r['radio_der_pct']))
    agg_drop[key].append(int(r['total_drop']))
    agg_collision[key].append(float(r['collision_pct']))
    agg_sent[key].append(int(r['total_sent']))


# ═══════════════════════════════════════════════════════════════════════════════
# ADIM 2: GRAFİKLER — Faz 1 ile aynı 5 grafik
# ═══════════════════════════════════════════════════════════════════════════════
print(f"\n[2/4] Grafikler üretiliyor → {GRAF_DIR}")

cmap_der  = sns.diverging_palette(10, 130, n=256, as_cmap=True)
cmap_coll = sns.color_palette("RdYlGn_r", as_cmap=True)
gw_colors = plt.cm.plasma(np.linspace(0.05, 0.85, len(GW_RANGE)))

# ── GRAFİK 1: DER Heatmap ─────────────────────────────────────────────────────
fig, axes = plt.subplots(1, 2, figsize=(11, 5))
fig.suptitle(
    "Ortalama Radio-DER (%)  —  Faz 2 (σ=6 dB, γ=3.5)  [7×7 Topoloji]",
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
                cbar_kws={'label':'Radio-DER (%)', 'shrink':0.85},
                annot_kws={'size':8})
    ax.set_title(f"Mode={mode}  (hop: {'1 km' if mode=='MIN' else '6 km'})",
                 fontweight='bold')
    ax.set_xlabel("Mesh Node Sayısı"); ax.set_ylabel("Gateway Sayısı")
    ax.set_yticklabels(ax.get_yticklabels(), rotation=0)
plt.tight_layout()
p = os.path.join(GRAF_DIR, 'heatmap_der.png')
fig.savefig(p, dpi=DPI_SAVE, bbox_inches='tight'); plt.close(fig)
print(f"    → heatmap_der.png")

# ── GRAFİK 2: Kapasite Eğrisi ────────────────────────────────────────────────
fig, ax = plt.subplots(figsize=(7, 4.5))
color_map  = {'MIN':'#e74c3c', 'MAX':'#27ae60'}
marker_map = {'MIN':'o',       'MAX':'s'}
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
                label=f"{mode}  (fit: {z[0]:+.4f}x²{z[1]:+.3f}x{z[2]:+.1f})")
ax.axhline(y=50, color='orange', linestyle='--', linewidth=1.2, alpha=0.8,
           label="50% DER eşiği")
ax.axhline(y=80, color='gray',   linestyle='--', linewidth=1.2, alpha=0.8,
           label="80% DER eşiği")
ax.set_xlabel("Toplam Ağ Düğümü Sayısı  (GW×10 sensör + GW + Mesh)")
ax.set_ylabel("Ortalama Radio-DER (%)")
ax.set_title("Kapasite Eğrisi — Faz 2 (Kentsel Shadowing)", fontweight='bold')
ax.set_ylim(0, 107)
ax.legend(loc='upper right', framealpha=0.9)
ax.grid(True, alpha=0.25, linestyle=':')
plt.tight_layout()
p = os.path.join(GRAF_DIR, 'capacity_curve.png')
fig.savefig(p, dpi=DPI_SAVE, bbox_inches='tight'); plt.close(fig)
print(f"    → capacity_curve.png")

# ── GRAFİK 3: Drop Analizi ────────────────────────────────────────────────────
fig, axes = plt.subplots(1, 2, figsize=(12, 4.5), sharey=False)
for ax, mode in zip(axes, MODES):
    for gi, gw in enumerate(GW_RANGE):
        xs, ys = [], []
        for mesh in MESH_RANGE:
            v = agg_drop.get((gw, mesh, mode), [])
            if v:
                xs.append(mesh); ys.append(safe_mean(v))
        if xs:
            ax.plot(xs, ys, marker='o', linewidth=1.8, markersize=5,
                    color=gw_colors[gi], label=f"GW={gw}")
    ax.set_title(f"Mode={mode}  ({'1 km' if mode=='MIN' else '6 km'})",
                 fontweight='bold')
    ax.set_xlabel("Mesh Node Sayısı")
    ax.set_ylabel("Ortalama Düşen Paket (Drop Count)")
    ax.set_xticks(MESH_RANGE)
    ax.legend(fontsize=8, ncol=2, loc='upper left', framealpha=0.8)
    ax.grid(True, alpha=0.25, linestyle=':')
fig.suptitle("Drop Analizi — Faz 2: Routing Katmanı Kuyruk Taşmaları",
             fontweight='bold', y=1.02)
plt.tight_layout()
p = os.path.join(GRAF_DIR, 'drop_analysis.png')
fig.savefig(p, dpi=DPI_SAVE, bbox_inches='tight'); plt.close(fig)
print(f"    → drop_analysis.png")

# ── GRAFİK 4: Çarpışma Yükü ──────────────────────────────────────────────────
fig, axes = plt.subplots(1, 2, figsize=(11, 5))
fig.suptitle("Ortalama Çarpışma Yükü (%)  —  Faz 2 (Shadowing Altında)",
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
                cbar_kws={'label':'Çarpışma Yükü (%)', 'shrink':0.85},
                annot_kws={'size':8})
    ax.set_title(f"Mode={mode}  ({'1 km' if mode=='MIN' else '6 km'})",
                 fontweight='bold')
    ax.set_xlabel("Mesh Node Sayısı"); ax.set_ylabel("Gateway Sayısı")
    ax.set_yticklabels(ax.get_yticklabels(), rotation=0)
plt.tight_layout()
p = os.path.join(GRAF_DIR, 'collision_load.png')
fig.savefig(p, dpi=DPI_SAVE, bbox_inches='tight'); plt.close(fig)
print(f"    → collision_load.png")

# ── GRAFİK 5: numSent Ölçek ──────────────────────────────────────────────────
fig, axes = plt.subplots(1, 2, figsize=(12, 4.5), sharey=False)
for ax, mode in zip(axes, MODES):
    for gi, gw in enumerate(GW_RANGE):
        xs, ys = [], []
        for mesh in MESH_RANGE:
            v = agg_sent.get((gw, mesh, mode), [])
            if v:
                xs.append(mesh); ys.append(safe_mean(v))
        if xs:
            ax.plot(xs, ys, marker='o', linewidth=1.8, markersize=5,
                    color=gw_colors[gi], label=f"GW={gw}")
    ax.set_title(f"Mode={mode}  ({'1 km' if mode=='MIN' else '6 km'})",
                 fontweight='bold')
    ax.set_xlabel("Mesh Node Sayısı")
    ax.set_ylabel("Ortalama numSent (paket)")
    ax.set_xticks(MESH_RANGE)
    ax.legend(fontsize=8, ncol=2, loc='upper left', framealpha=0.8)
    ax.grid(True, alpha=0.25, linestyle=':')
fig.suptitle("Gönderilen Toplam Paket Sayısı — Faz 2 (Simülasyon Gerçeklik Kontrolü)",
             fontweight='bold', y=1.02)
plt.tight_layout()
p = os.path.join(GRAF_DIR, 'sent_vs_scale.png')
fig.savefig(p, dpi=DPI_SAVE, bbox_inches='tight'); plt.close(fig)
print(f"    → sent_vs_scale.png")


# ─── Karşılaştırma grafikleri kopyala ─────────────────────────────────────────
CMP_FILES = [
    'heatmap_faz1_vs_faz2.png',
    'sf_resilience_matrix.png',
    'degradation_distribution.png',
    'gw_der_comparison.png',
]
for fname in CMP_FILES:
    src = os.path.join(CMP_PLOTS, fname)
    dst = os.path.join(GRAF_DIR, fname)
    if os.path.exists(src):
        shutil.copy2(src, dst)
        print(f"    → {fname}  (kopyalandı)")
    else:
        print(f"    !! {fname} bulunamadı, atlandı")


# ═══════════════════════════════════════════════════════════════════════════════
# ADIM 3: GEREKSİZ DOSYA TEMİZLİĞİ
# ═══════════════════════════════════════════════════════════════════════════════
print(f"\n[3/4] Gereksiz dosyalar temizleniyor...")

# plots_faz2_comparison/ dizinini temizle (artık Grafikler/ altında)
if os.path.isdir(CMP_PLOTS):
    shutil.rmtree(CMP_PLOTS)
    print(f"    Silindi: {CMP_PLOTS}/")

# arge_scriptleri'ndeki eski analyze_faz2_comparison.py script'ini koru — sadece
# ham sonuç dosyası (TMP_CSV) zaten üstte silindi.

# results_faz2/ — TAR doğrulaması yapıp sil
tar_path = os.path.join(ARCHIVE_DIR, 'Faz2_Ham_Veriler_SCA.tar')
if os.path.exists(tar_path) and os.path.isdir(FAZ2_DIR):
    # Spot-check: tar içindeki dosya sayısı vs dizindeki dosya sayısı
    import subprocess
    count_dir = len([f for f in os.listdir(FAZ2_DIR) if f.endswith('.sca')])
    result = subprocess.run(
        ['tar', 'tf', tar_path], capture_output=True, text=True
    )
    count_tar = sum(1 for l in result.stdout.splitlines() if l.endswith('.sca'))
    print(f"    Tar doğrulama: dizin={count_dir} sca, tar içinde={count_tar} sca")
    if count_tar >= count_dir:
        shutil.rmtree(FAZ2_DIR)
        print(f"    ✓ results_faz2/ silindi — {count_dir} dosya, 7.8 GB kazanıldı")
    else:
        print(f"    !! UYARI: Tar ve dizin uyuşmuyor ({count_tar} vs {count_dir}). Silme iptal.")
elif not os.path.isdir(FAZ2_DIR):
    print(f"    results_faz2/ zaten yok (önceden silinmiş)")
else:
    print(f"    !! UYARI: {tar_path} bulunamadı. Silme iptal.")


# ═══════════════════════════════════════════════════════════════════════════════
# ADIM 4: ÖZET
# ═══════════════════════════════════════════════════════════════════════════════
print(f"\n[4/4] Düzenleme tamamlandı.")
print()
print(f"  Faz2_Arazi2_Stres_Final/")
for item in sorted(os.listdir(ARCHIVE_DIR)):
    path = os.path.join(ARCHIVE_DIR, item)
    if os.path.isdir(path):
        grafler = sorted(os.listdir(path))
        print(f"    {item}/ ({len(grafler)} dosya)")
        for g in grafler:
            print(f"      - {g}")
    else:
        size_mb = os.path.getsize(path) / 1024**2
        if size_mb > 1:
            print(f"    {item}  ({size_mb:.0f} MB)")
        else:
            print(f"    {item}")
print()
