#!/usr/bin/env python3
"""
İzmir LoRa Mesh Ağı — Rastgele Topoloji ve Parametre Üreteci
=============================================================
Üretilen düzensizlikler:
  1. GW konumları   : MIN_GW_DIST kısıtıyla rastgele (200×110 km alan)
  2. MeshNode konumları : k‑means ile GW kümelerinin merkezlerinde
  3. Kontrol mekanizması: Birbirine <30 km'den yakın 2 GW varsa, aralarına
     en yakın MeshNode'u fiziksel olarak kaydır ("en az 1 MN arasında" kuralı)
  4. meshNeighborList : GW → YALNIZCA MeshNode (GW‑GW doğrudan bağlantı YOK)
                        MeshNode → ilgili GW'ler + komşu MeshNode'lar (zincir)
  5. Sensör SF        : {9,10,11,12} eşit dağılım, her sensöre bağımsız
  6. sendInterval     : Gaussian(µ=200s, σ=50s) ∈ [120, 360] s, her sensöre ayrı
  7. startTime        : Uniform[5, 400] s — tamamen düzensiz başlangıç
  8. GW backhaulCutTime: %20 GW rastgele t∈[600,3000]s'de kesilir
                         (mesh failover senaryosu)
Kullanım:
  python3 generate_random_config.py            # SEED=2026
  python3 generate_random_config.py --seed 42  # farklı tohum
  python3 generate_random_config.py --dry-run  # ekrana yaz, INI'ye ekleme
"""

import math
import random
import argparse
import sys
import os

# ─────────────────────────────────────────────────────────────────────────────
# Sabitler
# ─────────────────────────────────────────────────────────────────────────────
BOX_X        = 200_000   # m  — İzmir bounding box genişlik
BOX_Y        = 110_000   # m  — İzmir bounding box yükseklik
MARGIN_X     = 13_000    # m  — GW'leri kenarlardan uzak tut
MARGIN_Y     = 11_000

N_GW             = 28
N_MESHNODE       = 7
N_SENSORS_PER_GW = 5
N_SENSORS        = N_GW * N_SENSORS_PER_GW  # 140

# LoRa menzil kısıtı: d_max(SF12, kırsal) ≈ 30 800 m
LORA_MAX_RANGE   = 30_800   # m — bu mesafede 2 GW doğrudan haberleşebilir
MIN_GW_DIST      = 24_000   # m — başlangıç yerleştirme için minimum

# Kontrol mekanizması: 2 GW < LORA_MAX_RANGE ise aralarına MN koy
CLOSE_GW_THRESH  = LORA_MAX_RANGE        # m
MN_MIDPOINT_PULL = 0.65                  # MN'yi ne kadar orta noktaya çek

# Mesh komşu arama yarıçapları
GW_TO_MN_RADIUS  = 45_000   # m — GW'nin meshNeighborList'ine girebilmek için
MN_TO_MN_RADIUS  = 55_000   # m — MeshNode'ların birbirini görebilmesi için
MN_TO_GW_RADIUS  = 45_000   # m — MeshNode'un GW listesine eklemesi için

# Sensör konumu
SENSOR_R_MIN     = 6_000    # m
SENSOR_R_MAX     = 12_000   # m

# SF ve sendInterval
SF_CHOICES       = [9, 10, 11, 12]
SEND_INTERVAL_MEAN = 200    # s
SEND_INTERVAL_STD  = 50     # s
SEND_INTERVAL_MIN  = 120    # s
SEND_INTERVAL_MAX  = 360    # s

# Başlangıç zamanı
START_TIME_MIN   = 5    # s
START_TIME_MAX   = 400  # s

# Backhaul kesme: %20 GW rastgele kesilsin
BACKHAUL_CUT_FRACTION = 0.20
BACKHAUL_CUT_T_MIN    = 600   # s
BACKHAUL_CUT_T_MAX    = 3000  # s

# Zincir topolojisi için MN sıralaması (k‑means sonrasında x konumuna göre)
# ─────────────────────────────────────────────────────────────────────────────


def dist(a, b):
    return math.hypot(a[0] - b[0], a[1] - b[1])


def place_with_min_dist(n, x_range, y_range, min_d, rng, max_attempts=120_000):
    """
    Rejection sampling ile minimum mesafe kısıtlı rastgele nokta yerleştirme.
    max_attempts aşılırsa kısıt kademeli gevşetilir.
    """
    points = []
    attempts = 0
    current_min = min_d
    while len(points) < n:
        if attempts > max_attempts:
            current_min *= 0.95   # kısıtı %5 gevşet
            attempts = 0
            if current_min < min_d * 0.6:
                raise RuntimeError(
                    f"Sadece {len(points)}/{n} nokta yerleştirilebildi. "
                    "MIN_GW_DIST çok büyük veya alan çok küçük.")
        x = rng.uniform(*x_range)
        y = rng.uniform(*y_range)
        if all(dist((x, y), p) >= current_min for p in points):
            points.append((x, y))
        attempts += 1
    return points


def kmeans(points, k, rng, max_iter=300):
    """
    k‑means kümeleme. Başlangıç merkezleri k‑means++ ile seçilir.
    """
    # k‑means++ başlangıcı
    centers = [rng.choice(points)]
    while len(centers) < k:
        dists2 = [min(dist(p, c) ** 2 for c in centers) for p in points]
        total = sum(dists2)
        r = rng.uniform(0, total)
        cum = 0.0
        for i, d2 in enumerate(dists2):
            cum += d2
            if cum >= r:
                centers.append(points[i])
                break
        else:
            centers.append(points[-1])

    for _ in range(max_iter):
        clusters = [[] for _ in range(k)]
        for p in points:
            nearest = min(range(k), key=lambda i: dist(p, centers[i]))
            clusters[nearest].append(p)

        new_centers = []
        for i, cluster in enumerate(clusters):
            if cluster:
                cx = sum(p[0] for p in cluster) / len(cluster)
                cy = sum(p[1] for p in cluster) / len(cluster)
                new_centers.append((cx, cy))
            else:
                new_centers.append(centers[i])

        if new_centers == centers:
            break
        centers = new_centers

    # cluster ataması
    assignments = [min(range(k), key=lambda i: dist(p, centers[i])) for p in points]
    return centers, assignments


def clamp_to_box(x, y):
    return (
        max(MARGIN_X / 2, min(BOX_X - MARGIN_X / 2, x)),
        max(MARGIN_Y / 2, min(BOX_Y - MARGIN_Y / 2, y)),
    )


def midpoint(a, b):
    return ((a[0] + b[0]) / 2, (a[1] + b[1]) / 2)


def build_config(seed):
    rng = random.Random(seed)

    # ── 1. GW konumları ──────────────────────────────────────────────────────
    gw_pos = place_with_min_dist(
        N_GW,
        (MARGIN_X, BOX_X - MARGIN_X),
        (MARGIN_Y, BOX_Y - MARGIN_Y),
        MIN_GW_DIST,
        rng,
    )

    # ── 2. MeshNode konumları (k‑means merkezleri) ───────────────────────────
    raw_centers, gw_cluster = kmeans(gw_pos, N_MESHNODE, rng)
    # Alan sınırında tut
    mn_pos = [clamp_to_box(*c) for c in raw_centers]
    # MeshNode'ları x'e göre sırala → zincir topolojisi için tutarlı index
    mn_order = sorted(range(N_MESHNODE), key=lambda i: mn_pos[i][0])
    mn_pos = [mn_pos[mn_order[i]] for i in range(N_MESHNODE)]
    # GW küme atamasını yeni MN sıralamasına göre güncelle
    old_to_new = {mn_order[i]: i for i in range(N_MESHNODE)}
    gw_cluster = [old_to_new[c] for c in gw_cluster]

    # ── 3. Kontrol mekanizması: yakın GW çiftleri ────────────────────────────
    # Eğer 2 GW arasındaki mesafe < LORA_MAX_RANGE ise aralarında MN olmalı.
    # Değilse, en ilgili MN'yi orta noktaya doğru kaydır.
    control_log = []

    # Hangi GW çiftleri LORA_MAX_RANGE içinde?
    close_pairs = []
    for i in range(N_GW):
        for j in range(i + 1, N_GW):
            if dist(gw_pos[i], gw_pos[j]) < CLOSE_GW_THRESH:
                close_pairs.append((i, j))

    for gi, gj in close_pairs:
        mid = midpoint(gw_pos[gi], gw_pos[gj])
        # Bu çift için bir MN arasında mı?
        mn_dists = [dist(mid, mn_pos[m]) for m in range(N_MESHNODE)]
        nearest_mn = min(range(N_MESHNODE), key=lambda m: mn_dists[m])
        coverage_dist = min(dist(mn_pos[m], gw_pos[gi]) for m in range(N_MESHNODE)
                            if m != nearest_mn or True)  # any MN covering both
        # MN her 2 GW'yi de kapsayabiliyor mu? (yarı-mesafe içinde)
        mn_ok = any(
            dist(mn_pos[m], gw_pos[gi]) < LORA_MAX_RANGE and
            dist(mn_pos[m], gw_pos[gj]) < LORA_MAX_RANGE
            for m in range(N_MESHNODE)
        )
        if not mn_ok:
            # En yakın MN'yi orta noktaya çek
            old = mn_pos[nearest_mn]
            nx = old[0] + MN_MIDPOINT_PULL * (mid[0] - old[0])
            ny = old[1] + MN_MIDPOINT_PULL * (mid[1] - old[1])
            mn_pos[nearest_mn] = clamp_to_box(nx, ny)
            control_log.append(
                f"  GW[{gi}]↔GW[{gj}] mesafe={dist(gw_pos[gi],gw_pos[gj])/1000:.1f}km "
                f"< {CLOSE_GW_THRESH/1000}km → MN[{nearest_mn}] "
                f"({old[0]/1000:.1f},{old[1]/1000:.1f})km'den "
                f"({mn_pos[nearest_mn][0]/1000:.1f},{mn_pos[nearest_mn][1]/1000:.1f})km'ye kaydırıldı"
            )

    # ── 4. Sensör konumları + SF + sendInterval + startTime ─────────────────
    sensor_pos      = []
    sensor_sf       = []
    sensor_interval = []
    sensor_start    = []

    for gi in range(N_GW):
        for j in range(N_SENSORS_PER_GW):
            angle  = rng.uniform(0, 2 * math.pi)
            radius = rng.uniform(SENSOR_R_MIN, SENSOR_R_MAX)
            sx = gw_pos[gi][0] + radius * math.cos(angle)
            sy = gw_pos[gi][1] + radius * math.sin(angle)
            sx = max(1000, min(BOX_X - 1000, sx))
            sy = max(1000, min(BOX_Y - 1000, sy))
            sensor_pos.append((sx, sy))

            sf = rng.choice(SF_CHOICES)
            sensor_sf.append(sf)

            interval = rng.gauss(SEND_INTERVAL_MEAN, SEND_INTERVAL_STD)
            interval = max(SEND_INTERVAL_MIN, min(SEND_INTERVAL_MAX, interval))
            sensor_interval.append(round(interval))

            start = rng.uniform(START_TIME_MIN, START_TIME_MAX)
            sensor_start.append(round(start))

    # ── 5. GW meshNeighborList : YALNIZCA MeshNode (GW→GW bağlantı YOK) ─────
    gw_mesh_neighbors = []
    for gi, gp in enumerate(gw_pos):
        # Mesafeye göre sıralanmış MN'ler
        sorted_mn = sorted(range(N_MESHNODE), key=lambda m: dist(gp, mn_pos[m]))
        neighbors = [
            f"meshNode[{m}]"
            for m in sorted_mn
            if dist(gp, mn_pos[m]) <= GW_TO_MN_RADIUS
        ]
        if not neighbors:
            neighbors = [f"meshNode[{sorted_mn[0]}]"]   # en az biri mutlaka
        gw_mesh_neighbors.append(" ".join(neighbors))

    # ── 6. MeshNode meshNeighborList ─────────────────────────────────────────
    mn_mesh_neighbors = []
    for mi, mp in enumerate(mn_pos):
        neighbors = []
        # İlgili GW'ler
        for gi, gp in enumerate(gw_pos):
            if dist(mp, gp) <= MN_TO_GW_RADIUS:
                neighbors.append(f"hybridGW[{gi}]")
        # Komşu MeshNode'lar (zincir: sadece sol ve sağ komşu)
        if mi > 0:
            neighbors.append(f"meshNode[{mi - 1}]")
        if mi < N_MESHNODE - 1:
            neighbors.append(f"meshNode[{mi + 1}]")
        # Yakın ama zincir dışı MN'ler de ekle
        for mj in range(N_MESHNODE):
            if mj != mi and abs(mj - mi) > 1:
                if dist(mp, mn_pos[mj]) <= MN_TO_MN_RADIUS:
                    tag = f"meshNode[{mj}]"
                    if tag not in neighbors:
                        neighbors.append(tag)
        if not neighbors:
            neighbors.append(f"meshNode[{(mi + 1) % N_MESHNODE}]")
        mn_mesh_neighbors.append(" ".join(neighbors))

    # ── 7. GW backhaulCutTime : %20 rastgele kesilir ─────────────────────────
    n_cut = max(1, round(N_GW * BACKHAUL_CUT_FRACTION))
    cut_gws = set(rng.sample(range(N_GW), n_cut))
    gw_backhaul_cut = {}
    for gi in cut_gws:
        t = round(rng.uniform(BACKHAUL_CUT_T_MIN, BACKHAUL_CUT_T_MAX))
        gw_backhaul_cut[gi] = t

    return {
        "gw_pos"           : gw_pos,
        "mn_pos"           : mn_pos,
        "gw_cluster"       : gw_cluster,
        "sensor_pos"       : sensor_pos,
        "sensor_sf"        : sensor_sf,
        "sensor_interval"  : sensor_interval,
        "sensor_start"     : sensor_start,
        "gw_mesh_neighbors": gw_mesh_neighbors,
        "mn_mesh_neighbors": mn_mesh_neighbors,
        "gw_backhaul_cut"  : gw_backhaul_cut,
        "control_log"      : control_log,
        "close_pairs"      : close_pairs,
    }


def render_ini(cfg, seed):
    """omnetpp.ini formatında [Config IzmirRandom] bölümünü üret."""
    lines = []
    gw = cfg["gw_pos"]
    mn = cfg["mn_pos"]
    sp = cfg["sensor_pos"]
    sf = cfg["sensor_sf"]
    si = cfg["sensor_interval"]
    st = cfg["sensor_start"]
    gn = cfg["gw_mesh_neighbors"]
    mn_neigh = cfg["mn_mesh_neighbors"]
    bc = cfg["gw_backhaul_cut"]

    # SF dağılım özeti (yorum satırı)
    from collections import Counter
    sf_count = Counter(sf)
    sf_summary = "  ".join(f"SF{s}={sf_count[s]}" for s in sorted(sf_count))

    close_str = f"{len(cfg['close_pairs'])} çift GW <{CLOSE_GW_THRESH/1000:.0f}km"

    lines.append("")
    lines.append("# " + "=" * 78)
    lines.append("# [Config IzmirRandom]  —  Rastgele topoloji ve parametre dağılımı")
    lines.append("# " + "=" * 78)
    lines.append(f"# Tohum (seed): {seed}")
    lines.append(f"# GW sayısı   : {N_GW}  (MIN_GW_DIST={MIN_GW_DIST/1000}km)")
    lines.append(f"# MeshNode    : {N_MESHNODE}  (k-means + kontrol mekanizması)")
    lines.append(f"# Yakın GW çifti tespiti: {close_str}")
    lines.append(f"# SF dağılımı : {sf_summary}")
    lines.append(f"# sendInterval: Gaussian(µ={SEND_INTERVAL_MEAN}s,σ={SEND_INTERVAL_STD}s)"
                 f" ∈ [{SEND_INTERVAL_MIN},{SEND_INTERVAL_MAX}]s")
    lines.append(f"# startTime   : Uniform[{START_TIME_MIN},{START_TIME_MAX}]s")
    lines.append(f"# Backhaul kesme: {len(bc)} GW rastgele t∈[{BACKHAUL_CUT_T_MIN},{BACKHAUL_CUT_T_MAX}]s → {sorted(bc.keys())}")
    if cfg["control_log"]:
        lines.append("# Kontrol mekanizması tetiklendi:")
        for msg in cfg["control_log"]:
            lines.append(f"# {msg}")
    else:
        lines.append("# Kontrol mekanizması: Tüm yakın GW çiftleri zaten MN kapsamında ✓")
    lines.append("# meshNeighborList : GW → YALNIZCA meshNode (GW-GW doğrudan bağlantı YOK)")
    lines.append("# " + "=" * 78)
    lines.append("")
    lines.append("[Config IzmirRandom]")
    lines.append("extends = Izmir")
    lines.append(f'description = "Izmir Rastgele: seed={seed}, {sf_summary}, sendInterval~Gauss(200,50)"')
    lines.append("")

    # ── GW koordinatları ve mesh ayarları ────────────────────────────────────
    lines.append("# ── GW Konumları ve Mesh Komşu Listeleri ──────────────────────────────────")
    for i, (x, y) in enumerate(gw):
        cut = bc.get(i, -1)
        lines.append(f"**.hybridGW[{i}].mobility.initialX = {round(x)}m")
        lines.append(f"**.hybridGW[{i}].mobility.initialY = {round(y)}m")
        lines.append(f"**.hybridGW[{i}].mobility.initialZ = 10m")
        lines.append(f"**.hybridGW[{i}].routingAgent.backhaulCutTime = {cut}s")
        lines.append(f'**.hybridGW[{i}].routingAgent.meshNeighborList = "{gn[i]}"')

    lines.append("")
    lines.append("# ── MeshNode Konumları ve Komşu Listeleri ─────────────────────────────────")
    for i, (x, y) in enumerate(mn):
        lines.append(f"**.meshNode[{i}].mobility.initialX = {round(x)}m")
        lines.append(f"**.meshNode[{i}].mobility.initialY = {round(y)}m")
        lines.append(f"**.meshNode[{i}].mobility.initialZ = 20m")
        lines.append(f"**.meshNode[{i}].meshRouting.meshAddress = \"10.20.{i}.1\"")
        lines.append(f"**.meshNode[{i}].meshRouting.neighborTimeout = 60s")
        lines.append(f'**.meshNode[{i}].meshRouting.meshNeighborList = "{mn_neigh[i]}"')

    lines.append("")
    lines.append("# ── Sensör Konumları + SF + sendInterval + startTime ──────────────────────")
    for i in range(N_SENSORS):
        x, y = sp[i]
        lines.append(f"**.sensor[{i}].mobility.initialX       = {round(x)}m")
        lines.append(f"**.sensor[{i}].mobility.initialY       = {round(y)}m")
        lines.append(f"**.sensor[{i}].mobility.initialZ       = 1m")
        lines.append(f"**.sensor[{i}].app[0].initialLoRaSF    = {sf[i]}")
        lines.append(f"**.sensor[{i}].app[0].sendInterval     = {si[i]}s")
        lines.append(f"**.sensor[{i}].app[0].startTime        = {st[i]}s")

    return "\n".join(lines) + "\n"


def print_summary(cfg, seed):
    gw = cfg["gw_pos"]
    mn = cfg["mn_pos"]

    print(f"\n{'='*65}")
    print(f"  IzmirRandom — Topoloji Özeti (seed={seed})")
    print(f"{'='*65}")
    print(f"  {N_GW} GW  |  {N_MESHNODE} MeshNode  |  {N_SENSORS} Sensör")
    print()

    # GW konumları
    print("  GW Konumları (km):")
    for i, (x, y) in enumerate(gw):
        cl = cfg["gw_cluster"][i]
        cut = cfg["gw_backhaul_cut"].get(i, -1)
        cut_s = f"  ★ BACKHAUL_KESME t={cut}s" if cut > 0 else ""
        print(f"    GW[{i:2}]  ({x/1000:6.1f}, {y/1000:5.1f}) km  →  MN_küme={cl}{cut_s}")

    print()
    print("  MeshNode Konumları (km):")
    for i, (x, y) in enumerate(mn):
        # Bu MN'ye atanmış GW'ler
        gws_in_cluster = [gi for gi, cl in enumerate(cfg["gw_cluster"]) if cl == i]
        print(f"    MN[{i}]  ({x/1000:6.1f}, {y/1000:5.1f}) km  ←→  GW{gws_in_cluster}")

    print()
    from collections import Counter
    sf_count = Counter(cfg["sensor_sf"])
    print("  Sensör SF Dağılımı:")
    for s in sorted(sf_count):
        bar = "█" * sf_count[s]
        print(f"    SF{s}: {bar} ({sf_count[s]})")

    print()
    intervals = cfg["sensor_interval"]
    starts    = cfg["sensor_start"]
    print(f"  sendInterval  : min={min(intervals)}s  max={max(intervals)}s  µ={sum(intervals)/len(intervals):.0f}s")
    print(f"  startTime     : min={min(starts)}s  max={max(starts)}s  µ={sum(starts)/len(starts):.0f}s")

    print()
    print(f"  Yakın GW çiftleri (<{CLOSE_GW_THRESH/1000:.0f}km): {len(cfg['close_pairs'])}")
    if cfg["control_log"]:
        print("  Kontrol mekanizması → kaydırılan MN'ler:")
        for msg in cfg["control_log"]:
            print(f"   {msg}")
    else:
        print("  Kontrol mekanizması: Tüm yakın GW çiftleri MN kapsamında ✓")

    print()
    print(f"  Backhaul kesme ({len(cfg['gw_backhaul_cut'])} GW):")
    for gi, t in sorted(cfg["gw_backhaul_cut"].items()):
        print(f"    GW[{gi}] → t={t}s  |  MeshNeighbors: {cfg['gw_mesh_neighbors'][gi]}")
    print(f"{'='*65}\n")


# ─────────────────────────────────────────────────────────────────────────────
# Ana giriş noktası
# ─────────────────────────────────────────────────────────────────────────────
def main():
    parser = argparse.ArgumentParser(description="İzmir LoRa Mesh Rastgele Config Üreteci")
    parser.add_argument("--seed",    type=int, default=2026, help="Rastgelelik tohumu")
    parser.add_argument("--dry-run", action="store_true",    help="INI'ye ekleme, ekrana yaz")
    parser.add_argument("--ini",     default=os.path.join(os.path.dirname(__file__), "omnetpp.ini"),
                        help="Hedef omnetpp.ini yolu")
    args = parser.parse_args()

    print(f"[*] Seed={args.seed} ile rastgele topoloji üretiliyor...")
    cfg = build_config(args.seed)
    ini_text = render_ini(cfg, args.seed)
    print_summary(cfg, args.seed)

    if args.dry_run:
        print("─── DRY-RUN: INI içeriği (ilk 80 satır) ───")
        for line in ini_text.splitlines()[:80]:
            print(line)
        print("...")
        return

    # Mevcut config var mı?
    with open(args.ini) as f:
        content = f.read()
    if "[Config IzmirRandom]" in content:
        print("[!] [Config IzmirRandom] zaten mevcut.")
        overwrite = input("    Üzerine yazılsın mı? (e/h): ").strip().lower()
        if overwrite != "e":
            print("    İptal edildi.")
            sys.exit(0)
        # Eski bölümü kaldır
        start_idx = content.find("\n[Config IzmirRandom]")
        if start_idx == -1:
            start_idx = content.find("[Config IzmirRandom]")
        # Bir sonraki bölümü bul
        next_idx = content.find("\n[Config ", start_idx + 1)
        if next_idx == -1:
            content = content[:start_idx]
        else:
            content = content[:start_idx] + content[next_idx:]
        with open(args.ini, "w") as f:
            f.write(content)
        print("    Eski bölüm silindi.")

    with open(args.ini, "a") as f:
        f.write(ini_text)

    line_count = ini_text.count("\n")
    total = content.count("\n") + line_count
    print(f"[✓] {line_count} satır eklendi → omnetpp.ini toplam ~{total} satır")
    print("[✓] Çalıştırmak için:")
    print("    cd lora_mesh_projesi && \\")
    print("    LD_LIBRARY_PATH=.../flora/src:.../inet4.4/src:$LD_LIBRARY_PATH \\")
    print("    ./lora_mesh_projesi_dbg -m -u Cmdenv -c IzmirRandom -n .../flora/src:.../inet4.4/src:.")


if __name__ == "__main__":
    main()
