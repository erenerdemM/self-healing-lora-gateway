#!/usr/bin/env python3
# =============================================================================
# analiz_faz.py  —  Faz Sonu Grafik Üreticisi v2
# =============================================================================
# Kullanım: python3 analiz_faz.py --faz N [--out graphs/]
#
# Üretilen 4 grafik (gerçek SCA metriklerine göre):
#   1. DER (Data Extraction Rate) — config bazında bar chart
#   2. Çarpışma sayısı (numCollisions) — config bazında bar chart
#   3. GW Duty Cycle drop — GW_droppedDC toplam, config bazında
#   4. numSent dağılımı — histogram (kaç paket gönderildi)
# =============================================================================
import argparse, os, glob, re, collections, statistics

# ── SCA Parser (quoted + unquoted field names) ────────────────────────────────
_QUOTED   = re.compile(r'^scalar\s+\S+\s+"([^"]+)"\s+([0-9eE.+\-]+)\s*$')
_UNQUOTED = re.compile(r'^scalar\s+\S+\s+(\S+)\s+([0-9eE.+\-]+)\s*$')

# Count-type fields → sum across modules; rate-type → mean
_SUM_KEYWORDS = ('count', 'sent', 'received', 'drop', 'collision',
                 'forwarded', 'created', 'started', 'finished')

def parse_sca_file(path):
    """SCA dosyasından scalar değerleri çıkar.
    Aynı isimli alanlar (farklı modüller) toplanır veya ortalaması alınır."""
    acc = collections.defaultdict(list)
    try:
        with open(path, encoding='utf-8', errors='ignore') as f:
            for line in f:
                m = _QUOTED.match(line) or _UNQUOTED.match(line)
                if not m:
                    continue
                key, val_str = m.group(1), m.group(2)
                try:
                    val = float(val_str)
                    if val == val:          # nan kontrolü
                        acc[key].append(val)
                except ValueError:
                    pass
    except Exception:
        pass

    result = {}
    for k, vals in acc.items():
        if not vals:
            continue
        kl = k.lower()
        if any(x in kl for x in _SUM_KEYWORDS):
            result[k] = sum(vals)
        else:
            result[k] = statistics.mean(vals)
    return result


def collect_faz(faz_n, results_dir):
    """Faz için tüm SCA dosyalarını oku → liste[dict]."""
    pattern = os.path.join(results_dir, "*.sca")
    files = sorted(glob.glob(pattern))
    if not files:
        print(f"[WARN] {results_dir} içinde SCA yok.")
        return []
    rows = []
    for f in files:
        # Faz1_Sc1_GW2_Mesh1_MAX-0.sca → config=Sc1_GW2_Mesh1_MAX, rep=0
        bn = os.path.basename(f)
        cfg_m = re.match(r'Faz\d+_(.+?)-(\d+)\.sca', bn, re.IGNORECASE)
        d = parse_sca_file(f)
        d['_cfg'] = cfg_m.group(1) if cfg_m else bn
        d['_rep'] = int(cfg_m.group(2)) if cfg_m else 0
        rows.append(d)
    print(f"[*] {len(rows)} SCA okundu.")
    return rows


def group_by_config(rows):
    """Config bazında tekrarları ortala → {config_name: {metric: mean_val}}"""
    groups = collections.defaultdict(list)
    for r in rows:
        groups[r['_cfg']].append(r)

    summary = {}
    for cfg, reps in groups.items():
        agg = {}
        all_keys = set(k for r in reps for k in r if not k.startswith('_'))
        for k in all_keys:
            vals = [r[k] for r in reps if k in r]
            if vals:
                agg[k] = statistics.mean(vals)
        summary[cfg] = agg
    return summary


def plot_faz(faz_n, rows, out_dir):
    try:
        import matplotlib
        matplotlib.use('Agg')
        import matplotlib.pyplot as plt
    except ImportError:
        print("[WARN] matplotlib yok — metin özeti üretiliyor.")
        text_summary(faz_n, rows, out_dir)
        return

    os.makedirs(out_dir, exist_ok=True)
    summary = group_by_config(rows)
    cfgs = sorted(summary.keys())
    n = len(cfgs)
    step = max(1, n // 25)         # x ekseninde max ~25 etiket

    def bar_chart(title, ylabel, values, fname, color):
        fig, ax = plt.subplots(figsize=(14, 5))
        ax.bar(range(n), values, color=color, width=0.8)
        ax.set_xticks(range(0, n, step))
        ax.set_xticklabels([cfgs[i][:22] for i in range(0, n, step)],
                           rotation=45, ha='right', fontsize=7)
        ax.set_title(f'Faz{faz_n} — {title}')
        ax.set_ylabel(ylabel)
        ax.set_xlabel('Config')
        fig.tight_layout()
        path = os.path.join(out_dir, fname)
        fig.savefig(path, dpi=150)
        plt.close()
        print(f"[OK] {path}")

    # ── Grafik 1: DER ─────────────────────────────────────────────────────────
    der_key = 'DER - Data Extraction Rate'
    der_vals = [summary[c].get(der_key, 0.0) for c in cfgs]
    if any(v > 0 for v in der_vals):
        bar_chart('DER (Data Extraction Rate)', 'DER [0–1]',
                  der_vals, f'faz{faz_n}_der.png', 'steelblue')

    # ── Grafik 2: Çarpışma sayısı ─────────────────────────────────────────────
    col_key = next((k for k in (summary[cfgs[0]] if cfgs else {})
                    if 'collision' in k.lower()), None)
    if col_key:
        col_vals = [summary[c].get(col_key, 0.0) for c in cfgs]
        if any(v > 0 for v in col_vals):
            bar_chart(f'Çarpışma Sayısı ({col_key})', 'Toplam Çarpışma',
                      col_vals, f'faz{faz_n}_collision.png', 'tomato')

    # ── Grafik 3: GW Duty Cycle Drop ──────────────────────────────────────────
    dc_key = 'GW_droppedDC'
    dc_vals = [summary[c].get(dc_key, 0.0) for c in cfgs]
    if any(v > 0 for v in dc_vals):
        bar_chart('GW Duty Cycle Drop (GW_droppedDC)', 'Drop Sayısı',
                  dc_vals, f'faz{faz_n}_dc_drop.png', 'darkorange')
    else:
        # DC drop yoksa: paket gönderim dağılımı göster
        sent_key = next((k for k in (summary[cfgs[0]] if cfgs else {})
                         if k.lower() == 'numsent'), None)
        if sent_key:
            sent_vals = [summary[c].get(sent_key, 0.0) for c in cfgs]
            bar_chart('Gönderilen Paket Sayısı (numSent)', 'Toplam Paket',
                      sent_vals, f'faz{faz_n}_sent.png', 'mediumseagreen')

    # ── Grafik 4: DER dağılımı histogram ──────────────────────────────────────
    all_der = [r.get(der_key, None) for r in rows]
    all_der = [v for v in all_der if v is not None and v > 0]
    if all_der:
        fig, ax = plt.subplots(figsize=(8, 5))
        ax.hist(all_der, bins=20, color='mediumslateblue', edgecolor='black',
                rwidth=0.85)
        ax.set_title(f'Faz{faz_n} — DER Dağılımı (tüm tekrarlar)')
        ax.set_xlabel('DER [0–1]')
        ax.set_ylabel('Frekans')
        fig.tight_layout()
        path = os.path.join(out_dir, f'faz{faz_n}_der_hist.png')
        fig.savefig(path, dpi=150)
        plt.close()
        print(f"[OK] {path}")

    print(f"[OK] Faz{faz_n} grafikleri tamamlandı → {out_dir}")


def text_summary(faz_n, rows, out_dir):
    os.makedirs(out_dir, exist_ok=True)
    out = os.path.join(out_dir, f'faz{faz_n}_ozet.txt')
    summary = group_by_config(rows)
    with open(out, 'w', encoding='utf-8') as f:
        f.write(f"Faz{faz_n} Metin Özeti — {len(rows)} SCA, "
                f"{len(summary)} config\n{'='*60}\n")
        for cfg in sorted(summary.keys()):
            agg = summary[cfg]
            der  = agg.get('DER - Data Extraction Rate', float('nan'))
            col  = agg.get('numCollisions', agg.get('LoRaReceptionCollision:count', 0))
            sent = agg.get('numSent', 0)
            dc   = agg.get('GW_droppedDC', 0)
            f.write(f"{cfg:45s}  DER={der:.3f}  col={col:.0f}  "
                    f"sent={sent:.0f}  DC_drop={dc:.0f}\n")
    print(f"[OK] Metin özeti: {out}")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument('--faz', type=int, required=True, choices=range(1, 8))
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
