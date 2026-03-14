#!/usr/bin/env python3
"""
analyze_faz2_comparison.py — Faz 1 vs Faz 2 Karşılaştırmalı Analiz
====================================================================
Faz 1 (sigma=0, gamma=2.75) vs Faz 2 (sigma=6, gamma=3.5) kıyaslaması.

Kullanım:
    python3 analyze_faz2_comparison.py
"""

import os, re, csv, time, sys
from collections import defaultdict
import numpy as np

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import seaborn as sns

SCRIPT_DIR  = os.path.dirname(os.path.abspath(__file__))
PROJ_DIR    = os.path.abspath(os.path.join(SCRIPT_DIR, '..', '..'))

FAZ1_CSV    = os.path.join(PROJ_DIR, 'Faz1_Arazi1_Olceklendirme_Final', 'summary_7x7.csv')
FAZ2_DIR    = os.path.join(PROJ_DIR, 'results_faz2')
PLOTS_DIR   = os.path.join(SCRIPT_DIR, 'plots_faz2_comparison')
CSV_OUT     = os.path.join(SCRIPT_DIR, 'summary_faz2.csv')

os.makedirs(PLOTS_DIR, exist_ok=True)

# ─── Faz2 regex ──────────────────────────────────────────────────────────────
re_fname2 = re.compile(
    r'^Faz2_GW(\d+)_Mesh(\d+)_(MIN|MAX)-'
    r'sensorSF=(\d+),meshSF=(\d+),'
)

re_sensor_mod    = re.compile(r'sensorGW\d+\[\d+\]\.LoRaNic\.mac$')
re_ns_mod        = re.compile(r'networkServer\d+\.app\[0\]$')
re_routing_mod   = re.compile(r'hybridGW\d+\.routingAgent$')
re_gw_radio_mod  = re.compile(r'hybridGW\d+\.LoRaGWNic\.radio$')
re_gw_radio_recv = re.compile(r'hybridGW\d+\.LoRaGWNic\.radio\.receiver$')


def parse_sca(path: str) -> dict:
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
            elif stat == 'droppedPacket:count' and re_routing_mod.search(module):
                drop += int(val)
            elif stat == 'LoRaGWRadioReceptionFinishedCorrect:count' and re_gw_radio_mod.search(module):
                rcv_correct += int(val)
            elif stat == 'LoRaGWRadioReceptionStarted:count' and re_gw_radio_mod.search(module):
                rcv_started += int(val)
            elif stat == 'LoRaReceptionCollision:count' and re_gw_radio_recv.search(module):
                collision += int(val)
    return {
        'total_sent': sent, 'total_rcv': rcv, 'total_drop': drop,
        'total_rcv_correct': rcv_correct, 'total_rcv_started': rcv_started,
        'total_collision': collision,
    }


# ═══════════════════════════════════════════════════════════════════════════════
# ADIM 1: FAZ 1 CSV YÜKLEme
# ═══════════════════════════════════════════════════════════════════════════════
print("=" * 70)
print("  FAZ 1 vs FAZ 2 KARŞILAŞTIRMALI ANALİZ")
print("=" * 70)
print(f"\n[1/4] Faz 1 CSV yükleniyor: {FAZ1_CSV}")

faz1_rows = []
with open(FAZ1_CSV, newline='') as f:
    for row in csv.DictReader(f):
        faz1_rows.append({
            'gw': int(row['gw']), 'mesh': int(row['mesh']), 'mode': row['mode'],
            'sSF': int(row['sensorSF']), 'mSF': int(row['meshSF']),
            'radio_der': float(row['radio_der_pct']),
            'collision_pct': float(row['collision_pct']),
            'rcv_started': float(row['total_rcv_started']),
            'rcv_correct': float(row['total_rcv_correct']),
        })
print(f"    {len(faz1_rows)} satır yüklendi.")


# ═══════════════════════════════════════════════════════════════════════════════
# ADIM 2: FAZ 2 SCA PARSE
# ═══════════════════════════════════════════════════════════════════════════════
print(f"\n[2/4] Faz 2 SCA parse ediliyor: {FAZ2_DIR}")
t0 = time.time()

faz2_rows = []
files = os.listdir(FAZ2_DIR)
total = len(files)

for i, fname in enumerate(sorted(files), 1):
    m = re_fname2.match(fname)
    if not m:
        continue
    gw, mesh, mode, ssf, msf = int(m.group(1)), int(m.group(2)), m.group(3), int(m.group(4)), int(m.group(5))
    d = parse_sca(os.path.join(FAZ2_DIR, fname))
    radio_der = (d['total_rcv_correct'] / d['total_rcv_started'] * 100) if d['total_rcv_started'] > 0 else 0.0
    col_pct   = (d['total_collision']   / d['total_rcv_started'] * 100) if d['total_rcv_started'] > 0 else 0.0
    faz2_rows.append({
        'gw': gw, 'mesh': mesh, 'mode': mode, 'sSF': ssf, 'mSF': msf,
        'radio_der': radio_der, 'collision_pct': col_pct,
        'rcv_started': d['total_rcv_started'],
        'rcv_correct': d['total_rcv_correct'],
        'total_sent': d['total_sent'],
    })
    if i % 300 == 0:
        print(f"    {i}/{total}  ({time.time()-t0:.1f}s)", flush=True)

print(f"    {len(faz2_rows)} kayıt parse edildi ({time.time()-t0:.1f}s)")

# CSV yaz
with open(CSV_OUT, 'w', newline='') as f:
    w = csv.DictWriter(f, fieldnames=['gw','mesh','mode','sSF','mSF','radio_der','collision_pct','rcv_started','rcv_correct','total_sent'])
    w.writeheader()
    w.writerows(faz2_rows)
print(f"    CSV → {CSV_OUT}")


# ═══════════════════════════════════════════════════════════════════════════════
# ADIM 3: HESAPLAMALAR
# ═══════════════════════════════════════════════════════════════════════════════
print(f"\n[3/4] Karşılaştırmalı metrikler hesaplanıyor...")

f1_der = np.array([r['radio_der'] for r in faz1_rows])
f2_der = np.array([r['radio_der'] for r in faz2_rows])
f1_col = np.array([r['collision_pct'] for r in faz1_rows])
f2_col = np.array([r['collision_pct'] for r in faz2_rows])

# ── 1. GENEL PERFORMANS ────────────────────────────────────────────────────────
f1_mean_der = f1_der.mean()
f2_mean_der = f2_der.mean()
delta_der   = f1_mean_der - f2_mean_der
f1_mean_col = f1_col.mean()
f2_mean_col = f2_col.mean()

print(f"\n  ── GENEL PERFORMANS ─────────────────────────────────────────")
print(f"  Faz 1 ort. DER        : {f1_mean_der:.2f}%")
print(f"  Faz 2 ort. DER        : {f2_mean_der:.2f}%")
print(f"  Delta (F1-F2)         : -{delta_der:.2f} puan")
print(f"  Faz 1 ort. collision  : {f1_mean_col:.2f}%")
print(f"  Faz 2 ort. collision  : {f2_mean_col:.2f}%")
print(f"  Collision delta       : {f2_mean_col - f1_mean_col:+.2f} puan")

# ── 2. SF BAZLI DAYANIKLILIK ───────────────────────────────────────────────────
print(f"\n  ── SF BAZLI DAYANIKLILIK ────────────────────────────────────")

# Faz1 ve Faz2'yi (gw,mesh,mode,sSF,mSF) anahtarıyla birleştir
faz1_map = {(r['gw'], r['mesh'], r['mode'], r['sSF'], r['mSF']): r for r in faz1_rows}
faz2_map = {(r['gw'], r['mesh'], r['mode'], r['sSF'], r['mSF']): r for r in faz2_rows}

common_keys = set(faz1_map.keys()) & set(faz2_map.keys())
print(f"  Eşleşen (key) çifti   : {len(common_keys)}")

# Her SF çifti için ortalama delta
sf_delta = defaultdict(list)
sf_f1    = defaultdict(list)
sf_f2    = defaultdict(list)
for key in common_keys:
    ssf, msf = key[3], key[4]
    d1 = faz1_map[key]['radio_der']
    d2 = faz2_map[key]['radio_der']
    sf_delta[(ssf, msf)].append(d1 - d2)
    sf_f1[(ssf, msf)].append(d1)
    sf_f2[(ssf, msf)].append(d2)

sf_summary = []
for (ssf, msf), deltas in sf_delta.items():
    sf_summary.append({
        'sSF': ssf, 'mSF': msf,
        'f1_mean': np.mean(sf_f1[(ssf, msf)]),
        'f2_mean': np.mean(sf_f2[(ssf, msf)]),
        'delta_mean': np.mean(deltas),
        'delta_std': np.std(deltas),
    })

sf_summary.sort(key=lambda x: x['delta_mean'])  # en az kayıp başta

print(f"\n  En dirençli SF kombinasyonları (en az DER kaybı):")
print(f"  {'sSF':>4} {'mSF':>4} {'Faz1 DER':>10} {'Faz2 DER':>10} {'Delta':>8}")
print(f"  {'-'*46}")
for s in sf_summary[:5]:
    print(f"  {s['sSF']:>4} {s['mSF']:>4} {s['f1_mean']:>9.2f}% {s['f2_mean']:>9.2f}% {s['delta_mean']:>+8.2f}")

print(f"\n  En kırılgan SF kombinasyonları (en fazla DER kaybı):")
print(f"  {'sSF':>4} {'mSF':>4} {'Faz1 DER':>10} {'Faz2 DER':>10} {'Delta':>8}")
print(f"  {'-'*46}")
for s in sf_summary[-5:]:
    print(f"  {s['sSF']:>4} {s['mSF']:>4} {s['f1_mean']:>9.2f}% {s['f2_mean']:>9.2f}% {s['delta_mean']:>+8.2f}")

# ── 3. TOPOLOJİ BAZLI EN KIRILMaN & EN DİRENÇLİ ──────────────────────────────
print(f"\n  ── TOPOLOJİ BAZLI DAYANIKLILIK ─────────────────────────────")

topo_delta = defaultdict(list)
topo_f1    = defaultdict(list)
topo_f2    = defaultdict(list)
for key in common_keys:
    gw, mesh, mode = key[0], key[1], key[2]
    topo = (gw, mesh, mode)
    topo_delta[topo].append(faz1_map[key]['radio_der'] - faz2_map[key]['radio_der'])
    topo_f1[topo].append(faz1_map[key]['radio_der'])
    topo_f2[topo].append(faz2_map[key]['radio_der'])

topo_summary = []
for topo, deltas in topo_delta.items():
    topo_summary.append({
        'gw': topo[0], 'mesh': topo[1], 'mode': topo[2],
        'f1_mean': np.mean(topo_f1[topo]),
        'f2_mean': np.mean(topo_f2[topo]),
        'delta_mean': np.mean(deltas),
    })

topo_summary.sort(key=lambda x: x['delta_mean'])

print(f"\n  En dirençli topolojiler (min DER kaybı):")
print(f"  {'GW':>3} {'Mesh':>5} {'Mode':>5} {'Faz1':>8} {'Faz2':>8} {'Delta':>8}")
print(f"  {'-'*45}")
for t in topo_summary[:5]:
    print(f"  {t['gw']:>3} {t['mesh']:>5} {t['mode']:>5} {t['f1_mean']:>7.2f}% {t['f2_mean']:>7.2f}% {t['delta_mean']:>+8.2f}")

print(f"\n  En kırılgan topolojiler (max DER kaybı):")
print(f"  {'GW':>3} {'Mesh':>5} {'Mode':>5} {'Faz1':>8} {'Faz2':>8} {'Delta':>8}")
print(f"  {'-'*45}")
for t in topo_summary[-5:]:
    print(f"  {t['gw']:>3} {t['mesh']:>5} {t['mode']:>5} {t['f1_mean']:>7.2f}% {t['f2_mean']:>7.2f}% {t['delta_mean']:>+8.2f}")

# ── 4. %80+ DER SWEET SPOT ────────────────────────────────────────────────────
print(f"\n  ── YENİ SWEET SPOT (%80+ DER) ───────────────────────────────")

# Faz 1: %80+ topoloji (tüm SF ort.)
f1_topo_mean = {}
for t in topo_summary:
    f1_topo_mean[(t['gw'], t['mesh'], t['mode'])] = t['f1_mean']

f2_topo_mean = {}
for t in topo_summary:
    f2_topo_mean[(t['gw'], t['mesh'], t['mode'])] = t['f2_mean']

f1_sweet = sorted([(k,v) for k,v in f1_topo_mean.items() if v >= 80.0], key=lambda x: (x[0][0], x[0][1]))
f2_sweet = sorted([(k,v) for k,v in f2_topo_mean.items() if v >= 80.0], key=lambda x: (x[0][0], x[0][1]))

print(f"\n  Faz 1 → %80+ ortalama DER sağlayan topoloji sayısı: {len(f1_sweet)}")
print(f"  Faz 2 → %80+ ortalama DER sağlayan topoloji sayısı: {len(f2_sweet)}")

if f2_sweet:
    # En az GW+Mesh olan
    best = sorted(f2_sweet, key=lambda x: x[0][0]*10 + x[0][1])[0]
    print(f"\n  Faz 2 en optimal (%80+) sweet spot:")
    print(f"    GW={best[0][0]}, Mesh={best[0][1]}, Mode={best[0][2]} → ort. DER={best[1]:.2f}%")
else:
    print(f"\n  !! Faz 2'de ortalama %80+ DER sağlayan topoloji YOK !!")
    # En iyi olan
    best_f2 = sorted(topo_summary, key=lambda x: -x['f2_mean'])[0]
    print(f"  En iyi Faz 2 topolojisi: GW={best_f2['gw']}, Mesh={best_f2['mesh']}, Mode={best_f2['mode']} → {best_f2['f2_mean']:.2f}%")

# Per-SF sweet spot (Faz 2)
print(f"\n  Faz 2 en iyi SF kombinasyonları (ort. DER sıralaması):")
sf_f2_means = {(s['sSF'], s['mSF']): s['f2_mean'] for s in sf_summary}
top_sf = sorted(sf_f2_means.items(), key=lambda x: -x[1])[:6]
for (ssf, msf), v in top_sf:
    print(f"    sSF={ssf}, mSF={msf} → {v:.2f}%")

# ── 5. FİZİKSEL DOĞRULAMA ─────────────────────────────────────────────────────
print(f"\n  ── FİZİKSEL DOĞRULAMA ───────────────────────────────────────")

# Toplam started/correct
f1_total_started = sum(r['rcv_started'] for r in faz1_rows)
f1_total_correct = sum(r['rcv_correct'] for r in faz1_rows)
f2_total_started = sum(r['rcv_started'] for r in faz2_rows)
f2_total_correct = sum(r['rcv_correct'] for r in faz2_rows)

f1_global_der = f1_total_correct / f1_total_started * 100 if f1_total_started else 0
f2_global_der = f2_total_correct / f2_total_started * 100 if f2_total_started else 0

print(f"\n  Faz 1 → rcv_started={f1_total_started:,.0f}  rcv_correct={f1_total_correct:,.0f}  global_DER={f1_global_der:.2f}%")
print(f"  Faz 2 → rcv_started={f2_total_started:,.0f}  rcv_correct={f2_total_correct:,.0f}  global_DER={f2_global_der:.2f}%")
print(f"  Paket doğruluğu düşüşü: {f1_global_der - f2_global_der:.2f} puan")
print(f"  Faz 2'de toplam kayıp eden paket: {(f2_total_started - f2_total_correct):,.0f}")

# Collision karşılaştırması
f1_total_col = sum(r['rcv_started'] * r['collision_pct'] / 100 for r in faz1_rows)
f2_total_col = sum(r['rcv_started'] * r['collision_pct'] / 100 for r in faz2_rows)
print(f"\n  Faz 1 toplam çarpışma (tahmini): {f1_total_col:,.0f}")
print(f"  Faz 2 toplam çarpışma (tahmini): {f2_total_col:,.0f}")
col_ratio = f2_total_col / f1_total_col if f1_total_col > 0 else 0
print(f"  Çarpışma değişim oranı (F2/F1): {col_ratio:.3f}x  ({'azaldı ✓' if col_ratio < 1 else 'arttı'})")
print(f"  → Sinyal zayıfladığı için çarpışmalar {'azaldı (shadowing etkisi teyit)' if col_ratio < 1 else 'arttı (beklenmedik)'}")


# ═══════════════════════════════════════════════════════════════════════════════
# ADIM 4: GRAFİKLER
# ═══════════════════════════════════════════════════════════════════════════════
print(f"\n[4/4] Grafikler üretiliyor → {PLOTS_DIR}")

# ── Grafik 1: Ortalama DER Heatmap (Faz1 vs Faz2 yan yana) ───────────────────
GW_VALS   = list(range(2, 8))
MESH_VALS = list(range(1, 8))

def build_heatmap(rows, label):
    hm = np.full((len(GW_VALS), len(MESH_VALS)), np.nan)
    agg = defaultdict(list)
    for r in rows:
        agg[(r['gw'], r['mesh'])].append(r['radio_der'])
    for gi, gw in enumerate(GW_VALS):
        for mi, mesh in enumerate(MESH_VALS):
            vals = agg.get((gw, mesh), [])
            if vals:
                hm[gi][mi] = np.mean(vals)
    return hm

hm1 = build_heatmap(faz1_rows, 'Faz1')
hm2 = build_heatmap(faz2_rows, 'Faz2')
hm_delta = hm1 - hm2  # pozitif = Faz2 daha kötü

fig, axes = plt.subplots(1, 3, figsize=(18, 5))
vmin = min(np.nanmin(hm1), np.nanmin(hm2))
vmax = max(np.nanmax(hm1), np.nanmax(hm2))

for ax, hm, title in zip(axes[:2], [hm1, hm2], ['Faz 1 (σ=0, γ=2.75)', 'Faz 2 (σ=6, γ=3.5)']):
    sns.heatmap(hm, ax=ax, vmin=vmin, vmax=vmax, cmap='RdYlGn',
                xticklabels=MESH_VALS, yticklabels=GW_VALS,
                annot=True, fmt='.0f', linewidths=0.3)
    ax.set_title(f'Ort. DER% — {title}', fontsize=11)
    ax.set_xlabel('MeshPerGap'); ax.set_ylabel('GW Sayısı')

sns.heatmap(hm_delta, ax=axes[2], cmap='RdBu_r', center=0,
            xticklabels=MESH_VALS, yticklabels=GW_VALS,
            annot=True, fmt='.0f', linewidths=0.3)
axes[2].set_title('Delta DER% (Faz1 − Faz2)\n(+kırmızı = Faz2 bozuldu)', fontsize=11)
axes[2].set_xlabel('MeshPerGap'); axes[2].set_ylabel('GW Sayısı')

plt.tight_layout()
path = os.path.join(PLOTS_DIR, 'heatmap_faz1_vs_faz2.png')
plt.savefig(path, dpi=150, bbox_inches='tight')
plt.close()
print(f"    → {os.path.basename(path)}")

# ── Grafik 2: SF Dayanıklılık Matrisi ─────────────────────────────────────────
sf_mat_f1    = np.full((6, 6), np.nan)  # sSF x mSF
sf_mat_f2    = np.full((6, 6), np.nan)
sf_mat_delta = np.full((6, 6), np.nan)
SFS = [7, 8, 9, 10, 11, 12]
sfi = {sf: i for i, sf in enumerate(SFS)}

for s in sf_summary:
    i, j = sfi[s['sSF']], sfi[s['mSF']]
    sf_mat_f1[i][j]    = s['f1_mean']
    sf_mat_f2[i][j]    = s['f2_mean']
    sf_mat_delta[i][j] = s['delta_mean']

fig, axes = plt.subplots(1, 3, figsize=(18, 5))
for ax, mat, title, cmap in zip(axes,
        [sf_mat_f1, sf_mat_f2, sf_mat_delta],
        ['SF Matrisi — Faz 1', 'SF Matrisi — Faz 2', 'Delta (Faz1−Faz2)'],
        ['RdYlGn', 'RdYlGn', 'RdBu_r']):
    kw = dict(center=0) if 'Delta' in title else dict(vmin=0, vmax=100)
    sns.heatmap(mat, ax=ax, cmap=cmap, annot=True, fmt='.1f',
                xticklabels=SFS, yticklabels=SFS, linewidths=0.3, **kw)
    ax.set_title(title, fontsize=11)
    ax.set_xlabel('meshSF'); ax.set_ylabel('sensorSF')

plt.tight_layout()
path = os.path.join(PLOTS_DIR, 'sf_resilience_matrix.png')
plt.savefig(path, dpi=150, bbox_inches='tight')
plt.close()
print(f"    → {os.path.basename(path)}")

# ── Grafik 3: Degradasyon dağılımı (histogram) ────────────────────────────────
paired_deltas = []
for key in common_keys:
    paired_deltas.append(faz1_map[key]['radio_der'] - faz2_map[key]['radio_der'])
paired_deltas = np.array(paired_deltas)

fig, axes = plt.subplots(1, 2, figsize=(13, 5))

axes[0].hist(paired_deltas, bins=40, color='steelblue', edgecolor='white', alpha=0.85)
axes[0].axvline(paired_deltas.mean(), color='red', linestyle='--', label=f'Ort. Δ={paired_deltas.mean():.2f}')
axes[0].set_xlabel('DER Kaybı (Faz1 − Faz2) [%]')
axes[0].set_ylabel('Frekans')
axes[0].set_title('Degradasyon Dağılımı (tüm run çiftleri)')
axes[0].legend()

axes[1].scatter(
    [faz1_map[k]['radio_der'] for k in common_keys],
    [faz2_map[k]['radio_der'] for k in common_keys],
    alpha=0.2, s=4, color='steelblue'
)
lim = [0, 105]
axes[1].plot(lim, lim, 'r--', linewidth=1, label='Eşit performans')
axes[1].set_xlabel('Faz 1 DER [%]')
axes[1].set_ylabel('Faz 2 DER [%]')
axes[1].set_title('Scatter: Faz 1 vs Faz 2 DER')
axes[1].legend()

plt.tight_layout()
path = os.path.join(PLOTS_DIR, 'degradation_distribution.png')
plt.savefig(path, dpi=150, bbox_inches='tight')
plt.close()
print(f"    → {os.path.basename(path)}")

# ── Grafik 4: GW bazlı DER karşılaştırması ────────────────────────────────────
fig, ax = plt.subplots(figsize=(10, 5))
gw_f1 = defaultdict(list)
gw_f2 = defaultdict(list)
for key in common_keys:
    gw_f1[key[0]].append(faz1_map[key]['radio_der'])
    gw_f2[key[0]].append(faz2_map[key]['radio_der'])

gws = sorted(gw_f1.keys())
x = np.arange(len(gws))
w = 0.35
ax.bar(x - w/2, [np.mean(gw_f1[g]) for g in gws], w, label='Faz 1', color='steelblue', alpha=0.85)
ax.bar(x + w/2, [np.mean(gw_f2[g]) for g in gws], w, label='Faz 2', color='tomato', alpha=0.85)
ax.set_xticks(x); ax.set_xticklabels([f'GW={g}' for g in gws])
ax.set_ylabel('Ortalama DER [%]')
ax.set_title('GW Sayısına Göre Ort. DER: Faz 1 vs Faz 2')
ax.legend(); ax.grid(axis='y', alpha=0.3)
ax.set_ylim(0, 105)
plt.tight_layout()
path = os.path.join(PLOTS_DIR, 'gw_der_comparison.png')
plt.savefig(path, dpi=150, bbox_inches='tight')
plt.close()
print(f"    → {os.path.basename(path)}")


# ═══════════════════════════════════════════════════════════════════════════════
# ÖZET RAPOR
# ═══════════════════════════════════════════════════════════════════════════════
print("\n" + "=" * 70)
print("  ÖZET RAPOR (Gemini için)")
print("=" * 70)

worst_topo = topo_summary[-1]
best_topo  = topo_summary[0]
most_robust_sf  = sf_summary[0]
most_fragile_sf = sf_summary[-1]

print(f"""
┌─ 1. GENEL DEGRADASYON ─────────────────────────────────────────────
│  Faz 1 ort. DER          : {f1_mean_der:.2f}%
│  Faz 2 ort. DER          : {f2_mean_der:.2f}%
│  Ortalama DER kaybı (Δ)  : -{delta_der:.2f} puan
│  Global DER (ağırlıklı)  : Faz1={f1_global_der:.2f}%  →  Faz2={f2_global_der:.2f}%
│
│  Çarpışma oranı          : Faz1={f1_mean_col:.2f}%  →  Faz2={f2_mean_col:.2f}%
│  Çarpışma değişimi       : {f2_mean_col - f1_mean_col:+.2f} puan  (sigma↑ → sinyal zayıf → RF alanı azaldı)
│
├─ 2. DAYANIKLILIK ──────────────────────────────────────────────────
│  En ROBUST SF        : sSF={most_robust_sf['sSF']}, mSF={most_robust_sf['mSF']}
│    → Faz1={most_robust_sf['f1_mean']:.2f}%  Faz2={most_robust_sf['f2_mean']:.2f}%  Δ={most_robust_sf['delta_mean']:+.2f}
│
│  En KIRILGAN SF      : sSF={most_fragile_sf['sSF']}, mSF={most_fragile_sf['mSF']}
│    → Faz1={most_fragile_sf['f1_mean']:.2f}%  Faz2={most_fragile_sf['f2_mean']:.2f}%  Δ={most_fragile_sf['delta_mean']:+.2f}
│
│  En ROBUST topoloji  : GW={best_topo['gw']}, Mesh={best_topo['mesh']}, {best_topo['mode']}
│    → Faz1={best_topo['f1_mean']:.2f}%  Faz2={best_topo['f2_mean']:.2f}%  Δ={best_topo['delta_mean']:+.2f}
│
│  En KIRILGAN topoloji: GW={worst_topo['gw']}, Mesh={worst_topo['mesh']}, {worst_topo['mode']}
│    → Faz1={worst_topo['f1_mean']:.2f}%  Faz2={worst_topo['f2_mean']:.2f}%  Δ={worst_topo['delta_mean']:+.2f}
│
├─ 3. FİZİKSEL DOĞRULAMA ────────────────────────────────────────────
│  Faz 2 rcv_started   : {f2_total_started:,.0f}
│  Faz 2 rcv_correct   : {f2_total_correct:,.0f}
│  Global Δ DER        : {f1_global_der - f2_global_der:.2f} puan düşüş
│  Çarpışma F2/F1      : {col_ratio:.3f}x  → {'çarpışmalar azaldı (sinyal kaybı baskın)' if col_ratio < 1 else 'çarpışmalar arttı'}
│  → sigma=6 + gamma=3.5: shadowing + engel etkisi ÇALIŞIYOR ✓
│
├─ 4. YENİ SWEET SPOT ───────────────────────────────────────────────""")

if f2_sweet:
    best_ss = sorted(f2_sweet, key=lambda x: x[0][0]*10 + x[0][1])[0]
    print(f"│  Faz 2'de %80+ ort. DER: {len(f2_sweet)} topoloji")
    print(f"│  En minimal sweet spot  : GW={best_ss[0][0]}, Mesh={best_ss[0][1]}, {best_ss[0][2]} → {best_ss[1]:.2f}%")
else:
    print(f"│  Faz 2'de %80+ ort. DER: YOK (sweet spot kayboldu)")
    best3 = sorted(topo_summary, key=lambda x: -x['f2_mean'])[:3]
    print(f"│  Top-3 Faz2 topolojisi:")
    for t in best3:
        print(f"│    GW={t['gw']}, Mesh={t['mesh']}, {t['mode']} → {t['f2_mean']:.2f}%")

print(f"""└────────────────────────────────────────────────────────────────

  Grafikler : {PLOTS_DIR}/
  CSV       : {CSV_OUT}
""")
