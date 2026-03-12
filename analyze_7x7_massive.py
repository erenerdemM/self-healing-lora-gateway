#!/usr/bin/env python3
"""
analyze_7x7_massive.py — 7×7 Ölçeklenebilirlik (Scalability) Analizi
======================================================================
GW=2..7, Mesh=1..7 konfigürasyonlarını analiz eder.

Kullanım:
    python3 analyze_7x7_massive.py [--results-dir PATH] [--max-gw N] [--max-mesh N]

Üretilen çıktılar:
    plots_7x7/heatmap_der.png           — Ortalama DER ısı haritası (MIN & MAX)
    plots_7x7/capacity_curve.png        — Kapasite çöküş eğrisi
    plots_7x7/drop_analysis.png         — Darboğaz (drop) analizi
    plots_7x7/collision_load.png        — Çarpışma yükü analizi
    plots_7x7/sent_vs_scale.png         — Gönderilen paket ölçek analizi
    summary_7x7.csv                     — Tüm ham veri

Teşhis Notu:
    FLoRa simülasyonunda tüm config'ler DER=0% gösteriyorsa, bunun sebebi
    max_sensitivity_dBm=-141.0 parametresinin communicationRange'i ~30km'ye
    genişletmesidir. Tüm sensörler birbirini interferans kaynağı olarak görür.
    Bu durumda script alternatif metrikler (çarpışma yükü, ağ yoğunluğu)
    üretir ve teşhis raporu yazar.
"""

import os
import re
import sys
import csv
import time
import argparse
from collections import defaultdict

import numpy as np

# matplotlib backend'i ekran gerektirmeyen Agg'a ayarla
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import seaborn as sns

# ─── Argüman ayrıştırma ───────────────────────────────────────────────────────
parser = argparse.ArgumentParser(description="7×7 LoRa Mesh Ölçeklenebilirlik Analizi")
parser.add_argument("--results-dir",
                    default=os.path.join(os.path.dirname(os.path.abspath(__file__)), "results"),
                    help="OMNeT++ results dizini (varsayılan: ./results)")
parser.add_argument("--max-gw",   type=int, default=7,  help="Max GW sayısı (varsayılan: 7)")
parser.add_argument("--max-mesh", type=int, default=7,  help="Max Mesh sayısı (varsayılan: 7)")
args = parser.parse_args()

SCRIPT_DIR  = os.path.dirname(os.path.abspath(__file__))
RESULTS_DIR = args.results_dir
PLOTS_DIR   = os.path.join(SCRIPT_DIR, "plots_7x7")
CSV_OUT     = os.path.join(SCRIPT_DIR, "summary_7x7.csv")
MAX_GW      = args.max_gw
MAX_MESH    = args.max_mesh

# ─── Regex kalıpları ──────────────────────────────────────────────────────────
# Dosya adı: Scalable_GW3_Mesh2_MAX-sensorSF=9,meshSF=8,...-#0.sca
re_fname = re.compile(
    r'^Scalable_GW(\d+)_Mesh(\d+)_(MIN|MAX)-'
    r'sensorSF=(\d+),meshSF=(\d+),'
)

# Scalar modül eşleşmeleri
re_sensor_mod     = re.compile(r'sensorGW\d+\[\d+\]\.LoRaNic\.mac$')
re_ns_mod         = re.compile(r'networkServer\d+\.app\[0\]$')
re_routing_mod    = re.compile(r'hybridGW\d+\.routingAgent$')
re_gw_radio_mod   = re.compile(r'hybridGW\d+\.LoRaGWNic\.radio$')
re_gw_radio_recv  = re.compile(r'hybridGW\d+\.LoRaGWNic\.radio\.receiver$')


# ─── .sca Ayrıştırıcı ────────────────────────────────────────────────────────
def parse_sca(path: str):
    """
    Tek .sca dosyasını parse eder.
    Döndürür: dict ile:
      - total_sent        : tüm sensorGW[*].LoRaNic.mac numSent toplamı
      - total_rcv         : tüm networkServer*.app[0] totalReceivedPackets toplamı
      - total_drop        : tüm hybridGW*.routingAgent droppedPacket:count toplamı
      - total_rcv_correct : tüm hybridGW*.LoRaGWNic.radio LoRaGWRadioReceptionFinishedCorrect:count
      - total_rcv_started : tüm hybridGW*.LoRaGWNic.radio LoRaGWRadioReceptionStarted:count
      - total_collision   : tüm hybridGW*.LoRaGWNic.radio.receiver LoRaReceptionCollision:count
    """
    sent = rcv = drop = 0
    rcv_correct = rcv_started = collision = 0
    with open(path, encoding='utf-8', errors='replace') as fh:
        for line in fh:
            if not line.startswith('scalar '):
                continue
            # Format: "scalar <MODULE> <STAT> <VALUE>"
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
            elif stat == 'droppedPacket:count' and re_routing_mod.search(module):
                drop += int(val)
            elif stat == 'LoRaGWRadioReceptionFinishedCorrect:count' and re_gw_radio_mod.search(module):
                rcv_correct += int(val)
            elif stat == 'LoRaGWRadioReceptionStarted:count' and re_gw_radio_mod.search(module):
                rcv_started += int(val)
            elif stat == 'LoRaReceptionCollision:count' and re_gw_radio_recv.search(module):
                collision += int(val)

    return {
        'total_sent':        sent,
        'total_rcv':         rcv,
        'total_drop':        drop,
        'total_rcv_correct': rcv_correct,
        'total_rcv_started': rcv_started,
        'total_collision':   collision,
    }


# ─────────────────────────────────────────────────────────────────────────────
# ADIM 1: Hedef dosyaları tara ve filtrele
# ─────────────────────────────────────────────────────────────────────────────
print("=" * 65)
print("  7×7 LORA MESH ÖLÇEKLENEBİLİRLİK ANALİZİ")
print(f"  GW: 2..{MAX_GW}  |  Mesh: 1..{MAX_MESH}")
print("=" * 65)
print(f"\n[1/5] Dosyalar taranıyor: {RESULTS_DIR}", flush=True)

t_start = time.time()

if not os.path.isdir(RESULTS_DIR):
    print(f"HATA: '{RESULTS_DIR}' dizini bulunamadı!", file=sys.stderr)
    sys.exit(1)

target_files = []
for fname in os.listdir(RESULTS_DIR):
    if not fname.endswith('.sca'):
        continue
    m = re_fname.match(fname)
    if not m:
        continue
    gw, mesh, mode = int(m.group(1)), int(m.group(2)), m.group(3)
    if gw <= MAX_GW and mesh <= MAX_MESH:
        target_files.append((fname, gw, mesh, mode, int(m.group(4)), int(m.group(5))))

target_files.sort()
print(f"    → {len(target_files)} .sca dosyası bulundu  ({time.time()-t_start:.1f}s)")

if not target_files:
    print("HATA: Hiç dosya bulunamadı. results/ dizinini kontrol edin.", file=sys.stderr)
    sys.exit(1)

GW_RANGE   = list(range(2, MAX_GW + 1))    # [2,3,4,5,6,7]
MESH_RANGE = list(range(1, MAX_MESH + 1))  # [1,2,3,4,5,6,7]
MODES      = ["MIN", "MAX"]


# ─────────────────────────────────────────────────────────────────────────────
# ADIM 2: Parse
# ─────────────────────────────────────────────────────────────────────────────
print(f"\n[2/5] {len(target_files)} dosya parse ediliyor...", flush=True)

rows = []
errors = 0
t_parse = time.time()
for idx, (fname, gw, mesh, mode, sensorSF, meshSF) in enumerate(target_files, 1):
    if idx % 300 == 0 or idx == len(target_files):
        elapsed = time.time() - t_parse
        eta = elapsed / idx * (len(target_files) - idx)
        pct = idx / len(target_files) * 100
        print(f"    [{idx:>4}/{len(target_files)}] %{pct:4.0f}  "
              f"geçen={elapsed:.0f}s  kalan≈{eta:.0f}s", flush=True)

    path = os.path.join(RESULTS_DIR, fname)
    try:
        stats = parse_sca(path)
    except OSError as exc:
        print(f"  UYARI: {fname}: {exc}", file=sys.stderr)
        errors += 1
        continue

    sent    = stats['total_sent']
    rcv     = stats['total_rcv']
    drop    = stats['total_drop']
    started = stats['total_rcv_started']
    correct = stats['total_rcv_correct']
    collis  = stats['total_collision']

    # DER: uygulama katmanı  (totalReceivedPackets / numSent)
    der = (rcv / sent * 100.0) if sent > 0 else float('nan')
    # Radio-layer DER (GW fiziksel alım oranı)
    radio_der = (correct / started * 100.0) if started > 0 else float('nan')
    # Çarpışma yükü oranı
    coll_ratio = (collis / started * 100.0) if started > 0 else float('nan')

    rows.append({
        'gw': gw, 'mesh': mesh, 'mode': mode,
        'sensorSF': sensorSF, 'meshSF': meshSF,
        'total_sent': sent, 'total_rcv': rcv,
        'total_drop': drop, 'der_pct': der,
        'total_rcv_started': started,
        'total_rcv_correct': correct,
        'total_collision':   collis,
        'radio_der_pct':     radio_der,
        'collision_pct':     coll_ratio,
    })

print(f"    → {len(rows)} başarılı, {errors} hata  ({time.time()-t_parse:.1f}s)")


# ─────────────────────────────────────────────────────────────────────────────
# ADIM 3: CSV'ye kaydet
# ─────────────────────────────────────────────────────────────────────────────
print(f"\n[3/5] CSV kaydediliyor: {CSV_OUT}", flush=True)
fieldnames = ['gw', 'mesh', 'mode', 'sensorSF', 'meshSF',
              'total_sent', 'total_rcv', 'total_drop', 'der_pct',
              'total_rcv_started', 'total_rcv_correct', 'total_collision',
              'radio_der_pct', 'collision_pct']
with open(CSV_OUT, 'w', newline='') as f:
    w = csv.DictWriter(f, fieldnames=fieldnames)
    w.writeheader()
    w.writerows(rows)
print(f"    → {len(rows)} satır yazıldı")


# ─────────────────────────────────────────────────────────────────────────────
# ADIM 4: Toplama — her (gw, mesh, mode) için istatistikler
# ─────────────────────────────────────────────────────────────────────────────
print("\n[4/5] Metrikler hesaplanıyor...", flush=True)

# agg_der[(gw, mesh, mode)]        → uygulama DER listesi (boş ise DER=0 veya NaN)
# agg_drop[(gw, mesh, mode)]       → drop sayısı listesi
# agg_collision[(gw, mesh, mode)]  → çarpışma yükü (%) listesi
# agg_sent[(gw, mesh, mode)]       → toplam numSent listesi
agg_der       = defaultdict(list)
agg_drop      = defaultdict(list)
agg_collision = defaultdict(list)
agg_sent      = defaultdict(list)

for r in rows:
    key = (r['gw'], r['mesh'], r['mode'])
    if not (r['der_pct'] != r['der_pct']):    # NaN kontrolü
        agg_der[key].append(r['der_pct'])
    agg_drop[key].append(r['total_drop'])
    if not (r['collision_pct'] != r['collision_pct']):
        agg_collision[key].append(r['collision_pct'])
    agg_sent[key].append(r['total_sent'])


def safe_mean(lst):
    return float(np.nanmean(lst)) if lst else float('nan')


# ─────────────────────────────────────────────────────────────────────────────
# ADIM 5: GÖRSELLEŞTİRME
# ─────────────────────────────────────────────────────────────────────────────
print("\n[5/5] Grafikler çiziliyor...", flush=True)
os.makedirs(PLOTS_DIR, exist_ok=True)

# IEEE makale stili
plt.rcParams.update({
    'font.family':       'serif',
    'font.size':         10,
    'axes.titlesize':    11,
    'axes.labelsize':    10,
    'xtick.labelsize':    9,
    'ytick.labelsize':    9,
    'legend.fontsize':    8,
    'figure.dpi':        150,   # ekranda önizleme için
})
DPI_SAVE = 300   # kayıt çözünürlüğü


# ── GRAFİK 1: Isı Haritası (Heatmap) ─────────────────────────────────────────
print("  → Heatmap...", flush=True)

fig, axes = plt.subplots(1, 2, figsize=(11, 5))
fig.suptitle(
    "Ortalama Paket Teslimat Oranı (DER %)  —  7×7 Ölçeklenebilirlik",
    fontsize=12, fontweight='bold', y=1.01
)

cmap = sns.diverging_palette(10, 130, n=256, as_cmap=True)

for ax, mode in zip(axes, MODES):
    mat = np.full((len(GW_RANGE), len(MESH_RANGE)), np.nan)
    for gi, gw in enumerate(GW_RANGE):
        for mi, mesh in enumerate(MESH_RANGE):
            vals = agg_der.get((gw, mesh, mode), [])
            if vals:
                mat[gi, mi] = safe_mean(vals)

    # Hücre etiketleri: "%.1f" veya "–" (veri yoksa)
    annot = [[f"{mat[gi,mi]:.1f}" if not np.isnan(mat[gi,mi]) else "–"
              for mi in range(len(MESH_RANGE))]
             for gi in range(len(GW_RANGE))]

    im = sns.heatmap(
        mat, ax=ax,
        annot=annot, fmt='',
        xticklabels=MESH_RANGE,
        yticklabels=GW_RANGE,
        cmap=cmap, vmin=0, vmax=100,
        linewidths=0.4, linecolor='white',
        cbar_kws={'label': 'DER (%)', 'shrink': 0.85},
        annot_kws={'size': 8}
    )
    ax.set_title(f"Mode = {mode}  (hop mesafesi {'1 km' if mode=='MIN' else '6 km'})",
                 fontweight='bold')
    ax.set_xlabel("Mesh Node Sayısı (adet)")
    ax.set_ylabel("Gateway Sayısı (adet)")
    ax.set_yticklabels(ax.get_yticklabels(), rotation=0)
    # GW ekseni yukarıdan aşağıya (2→7) yerine aşağıdan yukarıya (7→2) olabilir;
    # seaborn varsayılanı satır sırasına göre — GW_RANGE=[2..7] demek
    # satır 0 = GW2, satır 5 = GW7. Yticklabels zaten doğru sırada.

plt.tight_layout()
heatmap_path = os.path.join(PLOTS_DIR, "heatmap_der.png")
fig.savefig(heatmap_path, dpi=DPI_SAVE, bbox_inches='tight')
plt.close(fig)
print(f"     Kaydedildi: {heatmap_path}")


# ── GRAFİK 2: Kapasite Çöküş Eğrisi ─────────────────────────────────────────
print("  → Kapasite eğrisi...", flush=True)

fig, ax = plt.subplots(figsize=(7, 4.5))

color_map  = {'MIN': '#e74c3c', 'MAX': '#27ae60'}
marker_map = {'MIN': 'o',       'MAX': 's'}

for mode in MODES:
    xs, ys = [], []
    for gw in GW_RANGE:
        for mesh in MESH_RANGE:
            vals = agg_der.get((gw, mesh, mode), [])
            if vals:
                # Toplam ağ düğümü = gw×10 sensör + gw gateway + mesh_node
                total_nodes = gw * 10 + gw + mesh
                xs.append(total_nodes)
                ys.append(safe_mean(vals))

    if not xs:
        continue

    xs, ys = np.array(xs), np.array(ys)
    valid = ~np.isnan(ys)
    xv, yv = xs[valid], ys[valid]

    # Nokta bulutu
    ax.scatter(xv, yv, alpha=0.30, s=20,
               color=color_map[mode], marker=marker_map[mode], zorder=2)

    # 2. derece polinom fit + düzgün eğri
    if len(xv) >= 3:
        z = np.polyfit(xv, yv, 2)
        p = np.poly1d(z)
        x_smooth = np.linspace(xv.min(), xv.max(), 400)
        ax.plot(x_smooth, p(x_smooth), linewidth=2.2,
                color=color_map[mode],
                label=f"{mode}  (fit: {z[0]:+.4f}x²{z[1]:+.3f}x{z[2]:+.1f})")

# %95 DER eşik çizgisi
ax.axhline(y=95, color='gray', linestyle='--', linewidth=1.2, alpha=0.8,
           label="95% DER eşiği")

ax.set_xlabel("Toplam Ağ Düğümü Sayısı  (GW×10 sensör + GW + MeshNode)")
ax.set_ylabel("Ortalama DER (%)")
ax.set_title("Ağ Ölçeği Büyüdükçe Paket Teslimat Oranı (DER) Değişimi",
             fontweight='bold')
ax.set_ylim(0, 107)
ax.legend(loc='lower left', framealpha=0.9)
ax.grid(True, alpha=0.25, linestyle=':')

plt.tight_layout()
cap_path = os.path.join(PLOTS_DIR, "capacity_curve.png")
fig.savefig(cap_path, dpi=DPI_SAVE, bbox_inches='tight')
plt.close(fig)
print(f"     Kaydedildi: {cap_path}")


# ── GRAFİK 3: Darboğaz (Drop) Analizi ────────────────────────────────────────
print("  → Drop analizi...", flush=True)

fig, axes = plt.subplots(1, 2, figsize=(12, 4.5), sharey=False)
gw_colors = plt.cm.plasma(np.linspace(0.05, 0.85, len(GW_RANGE)))

for ax, mode in zip(axes, MODES):
    for gi, gw in enumerate(GW_RANGE):
        xs, ys = [], []
        for mesh in MESH_RANGE:
            vals = agg_drop.get((gw, mesh, mode), [])
            if vals:
                xs.append(mesh)
                ys.append(safe_mean(vals))
        if xs:
            ax.plot(xs, ys, marker='o', linewidth=1.8, markersize=5,
                    color=gw_colors[gi], label=f"GW={gw}")

    ax.set_title(f"Mode = {mode}  (hop mesafesi {'1 km' if mode=='MIN' else '6 km'})",
                 fontweight='bold')
    ax.set_xlabel("Mesh Node Sayısı")
    ax.set_ylabel("Ortalama Düşen Paket (Drop Count)")
    ax.set_xticks(MESH_RANGE)
    ax.legend(fontsize=8, ncol=2, loc='upper left', framealpha=0.8)
    ax.grid(True, alpha=0.25, linestyle=':')

fig.suptitle("Darboğaz Analizi: Ağ Yükü Arttıkça Gateway Kuyruk Taşmaları",
             fontweight='bold', y=1.02)
plt.tight_layout()
drop_path = os.path.join(PLOTS_DIR, "drop_analysis.png")
fig.savefig(drop_path, dpi=DPI_SAVE, bbox_inches='tight')
plt.close(fig)
print(f"     Kaydedildi: {drop_path}")


# ── GRAFİK 4: Çarpışma Yükü Isı Haritası ─────────────────────────────────────
print("  → Çarpışma yükü heatmap...", flush=True)

# Hangi veride manidar değer var?
all_coll_vals = [v for lst in agg_collision.values() for v in lst]
has_collision_data = len(all_coll_vals) > 0

if has_collision_data:
    fig, axes = plt.subplots(1, 2, figsize=(11, 5))
    fig.suptitle(
        "Ortalama Çarpışma Yükü (%)  —  LoRa GW Radyo Alım Katmanı",
        fontsize=12, fontweight='bold', y=1.01
    )
    cmap_coll = sns.color_palette("RdYlGn_r", as_cmap=True)
    for ax, mode in zip(axes, MODES):
        mat = np.full((len(GW_RANGE), len(MESH_RANGE)), np.nan)
        for gi, gw in enumerate(GW_RANGE):
            for mi, mesh in enumerate(MESH_RANGE):
                vals = agg_collision.get((gw, mesh, mode), [])
                if vals:
                    mat[gi, mi] = safe_mean(vals)
        annot = [[f"{mat[gi,mi]:.0f}%" if not np.isnan(mat[gi,mi]) else "–"
                  for mi in range(len(MESH_RANGE))]
                 for gi in range(len(GW_RANGE))]
        sns.heatmap(mat, ax=ax, annot=annot, fmt='',
                    xticklabels=MESH_RANGE, yticklabels=GW_RANGE,
                    cmap=cmap_coll, vmin=0, vmax=100,
                    linewidths=0.4, linecolor='white',
                    cbar_kws={'label': 'Çarpışma Yükü (%)', 'shrink': 0.85},
                    annot_kws={'size': 8})
        ax.set_title(f"Mode = {mode}  (hop: {'1 km' if mode=='MIN' else '6 km'})",
                     fontweight='bold')
        ax.set_xlabel("Mesh Node Sayısı")
        ax.set_ylabel("Gateway Sayısı")
        ax.set_yticklabels(ax.get_yticklabels(), rotation=0)
    plt.tight_layout()
    coll_path = os.path.join(PLOTS_DIR, "collision_load.png")
    fig.savefig(coll_path, dpi=DPI_SAVE, bbox_inches='tight')
    plt.close(fig)
    print(f"     Kaydedildi: {coll_path}")
else:
    print("     Çarpışma verisi bulunamadı, grafik atlandı.")


# ── GRAFİK 5: Gönderilen Paket — Ağ Yükü ─────────────────────────────────────
print("  → Ağ yükü (numSent) analizi...", flush=True)

fig, axes = plt.subplots(1, 2, figsize=(12, 4.5), sharey=False)
for ax, mode in zip(axes, MODES):
    for gi, gw in enumerate(GW_RANGE):
        xs, ys = [], []
        for mesh in MESH_RANGE:
            vals = agg_sent.get((gw, mesh, mode), [])
            if vals:
                xs.append(mesh)
                ys.append(safe_mean(vals))
        if xs:
            ax.plot(xs, ys, marker='o', linewidth=1.8, markersize=5,
                    color=gw_colors[gi], label=f"GW={gw}")
    ax.set_title(f"Mode = {mode}  (hop: {'1 km' if mode=='MIN' else '6 km'})",
                 fontweight='bold')
    ax.set_xlabel("Mesh Node Sayısı")
    ax.set_ylabel("Ortalama numSent (paket)")
    ax.set_xticks(MESH_RANGE)
    ax.legend(fontsize=8, ncol=2, loc='upper left', framealpha=0.8)
    ax.grid(True, alpha=0.25, linestyle=':')
fig.suptitle("Simülasyonda Gönderilen Toplam Paket Sayısı (Topoloji Yükü)",
             fontweight='bold', y=1.02)
plt.tight_layout()
sent_path = os.path.join(PLOTS_DIR, "sent_vs_scale.png")
fig.savefig(sent_path, dpi=DPI_SAVE, bbox_inches='tight')
plt.close(fig)
print(f"     Kaydedildi: {sent_path}")


# ─────────────────────────────────────────────────────────────────────────────
# TEŞHİS: DER=0 kontrolü
# ─────────────────────────────────────────────────────────────────────────────
all_der_vals    = [v for lst in agg_der.values() for v in lst]
nonzero_der_cnt = sum(1 for v in all_der_vals if v > 0)
all_der_zero    = (nonzero_der_cnt == 0)

mean_coll_all = safe_mean(all_coll_vals) if all_coll_vals else float('nan')
summary_rows = []
for gw in GW_RANGE:
    for mesh in MESH_RANGE:
        for mode in MODES:
            der_vals   = agg_der.get((gw, mesh, mode), [])
            drop_vals  = agg_drop.get((gw, mesh, mode), [])
            coll_vals  = agg_collision.get((gw, mesh, mode), [])
            sent_vals  = agg_sent.get((gw, mesh, mode), [])
            if not sent_vals:
                continue
            summary_rows.append({
                'gw': gw, 'mesh': mesh, 'mode': mode,
                'n_runs':       len(sent_vals),
                'mean_der':     safe_mean(der_vals) if der_vals else 0.0,
                'max_der':      float(np.nanmax(der_vals)) if der_vals else 0.0,
                'min_der':      float(np.nanmin(der_vals)) if der_vals else 0.0,
                'mean_drop':    safe_mean(drop_vals) if drop_vals else 0.0,
                'mean_coll':    safe_mean(coll_vals) if coll_vals else float('nan'),
                'mean_sent':    safe_mean(sent_vals),
            })

summary_rows.sort(key=lambda r: (r['mean_der'], -r['mean_coll']
                                  if not np.isnan(r.get('mean_coll', float('nan'))) else 0),
                  reverse=True)

W = 90
total_elapsed = time.time() - t_start

print()
print("═" * W)
print("  7×7 ANALİZ RAPORU")
print("═" * W)

# ── Teşhis bölümü
if all_der_zero:
    print()
    print("  ⚠  UYARI: TÜM KONFİGÜRASYONLAR DER=%0 — SİMÜLASYON ARTEFAKTI TESPİT EDİLDİ")
    print()
    print("  Kök Neden Analizi:")
    print("    • omnetpp.ini: **.radioMedium.pathLoss.max_sensitivity_dBm = -141.0")
    print("      Bu parametre, FLoRa'nın LoRa radyo modelinde communicationRange'i")
    print("      ~30 km'ye genişletiyor.")
    print("    • Tüm GW gruplarının sensörleri (GW0 ve GW1'in sensörleri) birbirinin")
    print("      mesafesinde kalıyor → her GW tüm ağın trafiğini 'duyuyor'.")
    print("    • FLoRa strict-collision modeli: herhangi iki LoRa sinyali aynı anda")
    print("      aktifse, her ikisi de çarpışma olarak işaretleniyor (capture yok).")
    print("    • Sonuç: Radyo katmanında %100 çarpışma → NS'ye hiç paket ulaşmıyor.")
    print()
    if not np.isnan(mean_coll_all):
        print(f"    Ortalama çarpışma yükü  : {mean_coll_all:.1f}%")
    print()
    print("  Mevcut verilerle anlamlı metrikler:")
    print("    ✓ total_sent        → sensörlerin kaç paket gönderdiğini doğruluyor")
    print("    ✓ collision_pct     → her topolojinin çarpışma yoğunluğu")
    print("    ✓ total_rcv_started → GW'nin kaç alım girişiminde bulunduğu")
    print()
    header_label = "Çarpışma Yükü Sıralaması (En Az → En Çok)"
    sort_by = "collision"
    summary_rows.sort(key=lambda r: r['mean_coll']
                      if not np.isnan(r.get('mean_coll', float('nan'))) else 999)
else:
    header_label = "En Başarılı Konfigürasyonlar (DER %)"
    sort_by = "der"
    summary_rows.sort(key=lambda r: r['mean_der'], reverse=True)

# ── Tablo
HDR = (f"{'Sıra':>4}  {'GW':>3}  {'M':>3}  {'Mod':>4}  "
       f"{'MeanDER':>8}  {'MaxDER':>7}  {'Collisn%':>9}  {'MeanSent':>9}  "
       f"{'DropAvg':>8}  {'N':>5}")
SEP = "─" * W

print(f"\n  {header_label}")
print(HDR)
print(SEP)
show_rows = summary_rows[:20] if not all_der_zero else summary_rows[:20]
for i, r in enumerate(show_rows, 1):
    coll_s = f"{r['mean_coll']:>8.1f}%" if not np.isnan(r.get('mean_coll', float('nan'))) else "       –"
    print(f"{i:>4}.  {r['gw']:>3}  {r['mesh']:>3}  {r['mode']:>4}  "
          f"{r['mean_der']:>7.1f}%  {r['max_der']:>6.1f}%  {coll_s}  "
          f"{r['mean_sent']:>9.0f}  {r['mean_drop']:>8.1f}  {r['n_runs']:>5}")

print()
all_sent_vals = [v for lst in agg_sent.values() for v in lst]
print(f"  Toplam parse edilen run  : {len(rows)}")
print(f"  Hatalar                  : {errors}")
print(f"  Genel ort. DER           : {safe_mean(all_der_vals):.2f}%")
print(f"  Genel ort. numSent       : {safe_mean(all_sent_vals):.0f} paket/run")
if not np.isnan(mean_coll_all):
    print(f"  Genel ort. çarpışma yükü : {mean_coll_all:.1f}%")
print(f"  Analiz süresi            : {total_elapsed:.1f} saniye")
print()
print(f"  Grafikler → {PLOTS_DIR}/")
print(f"     heatmap_der.png      (uygulama DER - {('DER=0' if all_der_zero else 'DER değişken')})")
print(f"     capacity_curve.png   (DER vs topoloji büyüklüğü)")
print(f"     drop_analysis.png    (routing drop sayısı)")
print(f"     collision_load.png   (radyo katmanı çarpışma yüzdeleri)")
print(f"     sent_vs_scale.png    (numSent - simülasyon gerçekliği kontrolü)")
print(f"  CSV → {CSV_OUT}")
print("═" * W)
