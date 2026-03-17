#!/usr/bin/env python3
# =============================================================================
# analiz_faz.py  —  Faz Sonu Grafik Üreticisi (Prompt §6)
# =============================================================================
# Kullanım: python3 analiz_faz.py --faz N [--out graphs/]
#
# Üretilen 4 grafik (SCA dosyalarından):
#   1. ToA dağılımı (SF bazında kutu grafiği)
#   2. Çarpışma oranı (topoloji × senaryo)
#   3. Veri kaybı % (topoloji karşılaştırma)
#   4. SNR / CRC başarı oranı (scatter plot)
# =============================================================================
import argparse, os, sys, glob
import re

def parse_sca_file(path):
    """SCA dosyasından scalar değerleri çıkar → dict."""
    data = {}
    try:
        with open(path, encoding="utf-8", errors="ignore") as f:
            for line in f:
                m = re.match(r'^scalar\s+\S+\s+"([^"]+)"\s+([0-9eE.+\-]+)', line)
                if m:
                    data[m.group(1)] = float(m.group(2))
    except Exception:
        pass
    return data

def collect_faz(faz_n, results_dir):
    """Faz için tüm SCA dosyalarını oku → liste[dict]."""
    pattern = os.path.join(results_dir, "*.sca")
    files = sorted(glob.glob(pattern))
    if not files:
        print(f"[WARN] {results_dir} içinde SCA yok.")
        return []
    rows = []
    for f in files:
        cfg_m = re.search(r'faz\d+_(.+)-\d+\.sca', os.path.basename(f).lower())
        d = parse_sca_file(f)
        d['_cfg'] = cfg_m.group(1) if cfg_m else os.path.basename(f)
        d['_file'] = f
        rows.append(d)
    print(f"[*] {len(rows)} SCA okundu.")
    return rows

def plot_faz(faz_n, rows, out_dir):
    try:
        import matplotlib
        matplotlib.use('Agg')
        import matplotlib.pyplot as plt
        import numpy as np
    except ImportError:
        print("[WARN] matplotlib yok — metin özeti üretiliyor.")
        text_summary(faz_n, rows, out_dir)
        return

    os.makedirs(out_dir, exist_ok=True)

    # ── Grafik 1: ToA dağılımı ────────────────────────────────────────────────
    toa_vals = [r.get('loraToA:stats:mean', r.get('toa:mean', None)) for r in rows]
    toa_vals = [v for v in toa_vals if v is not None]
    if toa_vals:
        fig, ax = plt.subplots(figsize=(8,5))
        ax.hist(toa_vals, bins=30, color='steelblue', edgecolor='black')
        ax.set_title(f'Faz{faz_n} — ToA Dağılımı')
        ax.set_xlabel('Ortalama ToA (s)')
        ax.set_ylabel('Frekans')
        fig.tight_layout()
        out = os.path.join(out_dir, f'faz{faz_n}_toa.png')
        fig.savefig(out, dpi=150); plt.close()
        print(f"[OK] {out}")

    # ── Grafik 2: Çarpışma oranı ──────────────────────────────────────────────
    col_keys = [k for k in (rows[0] if rows else {}) if 'collision' in k.lower() or 'çarpışma' in k.lower()]
    if col_keys:
        vals = [r.get(col_keys[0], 0) for r in rows]
        cfgs = [r['_cfg'][:20] for r in rows]
        fig, ax = plt.subplots(figsize=(10,5))
        ax.bar(range(len(vals)), vals, color='tomato')
        ax.set_xticks(range(0, len(cfgs), max(1, len(cfgs)//20)))
        ax.set_xticklabels(cfgs[::max(1, len(cfgs)//20)], rotation=45, ha='right', fontsize=7)
        ax.set_title(f'Faz{faz_n} — Çarpışma Oranı'); ax.set_ylabel('Oran')
        fig.tight_layout()
        out = os.path.join(out_dir, f'faz{faz_n}_collision.png')
        fig.savefig(out, dpi=150); plt.close()
        print(f"[OK] {out}")

    # ── Grafik 3: Veri kaybı ──────────────────────────────────────────────────
    loss_keys = [k for k in (rows[0] if rows else {}) if 'loss' in k.lower() or 'kayip' in k.lower() or 'drop' in k.lower()]
    if loss_keys:
        vals = [r.get(loss_keys[0], 0) for r in rows]
        fig, ax = plt.subplots(figsize=(8,5))
        ax.boxplot(vals, vert=False, patch_artist=True,
                   boxprops=dict(facecolor='lightgreen'))
        ax.set_title(f'Faz{faz_n} — Veri Kaybı Dağılımı'); ax.set_xlabel('%')
        fig.tight_layout()
        out = os.path.join(out_dir, f'faz{faz_n}_dataloss.png')
        fig.savefig(out, dpi=150); plt.close()
        print(f"[OK] {out}")

    # ── Grafik 4: SNR / CRC ───────────────────────────────────────────────────
    snr_key  = next((k for k in (rows[0] if rows else {}) if 'snr' in k.lower()), None)
    crc_key  = next((k for k in (rows[0] if rows else {}) if 'crc' in k.lower() or 'success' in k.lower()), None)
    if snr_key and crc_key:
        xs = [r.get(snr_key,0) for r in rows]
        ys = [r.get(crc_key,0) for r in rows]
        fig, ax = plt.subplots(figsize=(8,5))
        ax.scatter(xs, ys, alpha=0.4, s=10, color='purple')
        ax.set_title(f'Faz{faz_n} — SNR vs CRC Başarı')
        ax.set_xlabel('SNR (dB)'); ax.set_ylabel('CRC Başarı Oranı')
        fig.tight_layout()
        out = os.path.join(out_dir, f'faz{faz_n}_snr_crc.png')
        fig.savefig(out, dpi=150); plt.close()
        print(f"[OK] {out}")

    print(f"[OK] Faz{faz_n} grafikleri: {out_dir}")

def text_summary(faz_n, rows, out_dir):
    os.makedirs(out_dir, exist_ok=True)
    out = os.path.join(out_dir, f'faz{faz_n}_ozet.txt')
    with open(out, 'w') as f:
        f.write(f"Faz{faz_n} Özet — {len(rows)} SCA\n")
        if rows:
            numeric = {k:[] for k in rows[0] if k.startswith('_') is False}
            for r in rows:
                for k,v in r.items():
                    if not k.startswith('_') and isinstance(v, float):
                        numeric.setdefault(k,[]).append(v)
            import statistics
            for k,vals in list(numeric.items())[:20]:
                if vals:
                    f.write(f"  {k}: mean={statistics.mean(vals):.4f} n={len(vals)}\n")
    print(f"[OK] Metin özeti: {out}")

if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument('--faz', type=int, required=True, choices=range(1,8))
    ap.add_argument('--out', default='graphs')
    args = ap.parse_args()

    proj = os.path.dirname(os.path.abspath(__file__))
    results_dir = os.path.join(proj, f'results_faz{args.faz}')
    out_dir = os.path.join(proj, args.out, f'faz{args.faz}')

    rows = collect_faz(args.faz, results_dir)
    if rows:
        plot_faz(args.faz, rows, out_dir)
    else:
        print(f"[SKIP] Faz{args.faz} için veri yok.")
