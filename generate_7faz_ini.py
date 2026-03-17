#!/usr/bin/env python3
# =============================================================================
# generate_7faz_ini.py  —  7 Fazlı Arazi1 Kampanyası omnetpp.ini Üreticisi
# =============================================================================
#
# YAPI (168 topoloji-config = 84 topoloji × 2 senaryo):
#   Sc1: Faz1_Sc1_XXX  — sendInterval=180s  (ideal trafik)
#   Sc2: Faz1_Sc2_XXX  — sendInterval=sfInterval (BTK/ETSI %1 DC)
#
# Faz | Yeni Değişken       | ×Çarpan | Run/Config | 168×Run
# ----+---------------------+---------+------------+----------
# 1   | Base (SF×SF×2 Sc)   | -       | 36         | 6.048
# 2   | dutyCycleLimit      | ×3      | 108        | 18.144
# 3   | sigma gölge (dB)    | ×3      | 324        | 54.432
# 4   | gamma+pl0 hava      | ×3      | 972        | 163.296
# 5   | noiseFloor (sens)   | ×3      | 2.916      | 489.888
# 6   | backhaulLatency     | ×3      | 8.748      | 1.469.664
# 7   | Self-Healing (×1)   | ×1      | 8.748      | 1.469.664
# =============================================================================

import re, sys, os

SRC_INI = "omnetpp.ini"
DST_INI = "omnetpp_new.ini"

# ── Faz parametre tablosu ────────────────────────────────────────────────────
FAZ_TABLE = {
    1: {
        "iso_label": "Base_SF",
        "runs": 36,
        "iter_lines": [
            "**.sensorGW*[*].app[0].initialLoRaSF = ${sensorSF = 7, 8, 9, 10, 11, 12}",
            "**.meshNode[*].meshRouting.loraSF     = ${meshSF   = 7, 8, 9, 10, 11, 12}",
        ],
        "parallel_lines": [
            "**.LoRaGWNic.radio.receiver.sensitivity    = ${gwSens       = -124dBm, -127dBm, -130dBm, -133dBm, -135dBm, -141dBm ! sensorSF}",
            "**.meshNode[*].meshRouting.beaconInterval  = ${meshInterval = 5s, 9s, 17s, 29s, 63s, 265s ! meshSF}",
            "**.meshNode[*].meshRouting.cadDuration     = ${cadDur       = 1ms, 2ms, 4ms, 8ms, 16ms, 33ms   ! meshSF}",
        ],
        "fixed_lines": [],
    },
    2: {
        "iso_label": "Yasal_DC",
        "runs": 108,
        "iter_lines": [
            "# DC siniri: %0.5 kisitli / %1 yasal BTK-ETSI / %5 gevşek test",
            "**.sensorGW*[*].app[0].dutyCycleLimit = ${dc = 0.005, 0.01, 0.05}",
        ],
        "fixed_lines": [],
    },
    3: {
        "iso_label": "Dogal_Engel",
        "runs": 324,
        "iter_lines": [
            "# Log-normal golge: 0dB acik / 5dB kent / 10dB yogun",
            "**.radioMedium.pathLoss.sigma = ${sigmaE = 0.0, 5.0, 10.0}",
            "**.sigma                      = ${sigmaE}",
        ],
        "fixed_lines": [],
    },
    4: {
        "iso_label": "Hava_Durumu",
        "runs": 972,
        "iter_lines": [
            "# Yol kaybi: gamma acik/yagmur/firtina + pl0 ek yagmur kaybi (paralel)",
            "**.radioMedium.pathLoss.gamma    = ${wGamma = 2.75, 3.5, 4.5}",
            "**.radioMedium.pathLoss.pl_d0_db = ${wPl0   = 31.54, 34.54, 38.54 ! wGamma}",
        ],
        "fixed_lines": [],
    },
    5: {
        "iso_label": "RF_Gurultu",
        "runs": 2916,
        "iter_lines": [
            "# Gurultu tabani: standart / orta RF girisim / yuksek RF girisim",
            "**.radioMedium.pathLoss.max_sensitivity_dBm = ${nFloor = -115.0, -108.0, -100.0}",
        ],
        "fixed_lines": [],
    },
    6: {
        "iso_label": "Internet_Gecikmesi",
        "runs": 8748,
        "iter_lines": [
            "# Ethernet RTT: ideal LAN / LTE Cat4 / LTE zayif (paralel gruptaki LTE degeri)",
            "**.routingAgent.backhaulLatency    = ${ethLat = 0ms, 5ms, 20ms}",
            "**.routingAgent.lteBackhaulLatency = ${lteLat = 50ms, 100ms, 200ms ! ethLat}",
        ],
        "fixed_lines": [],
    },
    7: {
        "iso_label": "Self_Healing",
        "runs": 8748,
        "iter_lines": [],
        "fixed_lines": [
            "# Backhaul t=30s kesilir; GW mesh failover'a gecer",
            "**.routingAgent.backhaulCutTime = 30s",
            "**.routingAgent.lteBackhaulUp   = false",
        ],
    },
}

# ── Parser yardımcıları ───────────────────────────────────────────────────────

REGEN_STARTS = (
    "**.sensorGW*[*].app[0].initialLoRaSF",
    "**.meshNode[*].meshRouting.loraSF",
    "**.LoRaGWNic.radio.receiver.sensitivity",
    "**.meshNode[*].meshRouting.beaconInterval",
    "**.meshNode[*].meshRouting.cadDuration",
    "**.radioMedium.pathLoss.sigma",
    "**.sigma",
    "**.sensorGW*[*].app[0].sendInterval",
    "${sensorSF", "${meshSF", "${gwSensitivity", "${meshInterval",
    "${cadDur", "${sfInterval",
)

HEADER_STARTS = (
    "output-scalar-file", "network", "sim-time-limit",
    "description", "**.scalar-recording", "**.vector-recording",
    "# ===", "# Config", "# GW=", "# Hop=", "# MeshNode=", "# Run=",
    "# ── Kartezyen", "# ── sensorSF", "# ── meshSF", "# NOTE:",
)


def parse_blocks(path):
    with open(path, encoding="utf-8") as f:
        content = f.read()

    hdr_re = re.compile(r'^\[Config ([A-Za-z0-9_]+)\]', re.MULTILINE)
    all_m  = list(hdr_re.finditer(content))

    faz1_blocks = {}   # topo → dict(network, body_lines)
    faz2_sfline = {}   # topo → sendInterval expression string

    for i, m in enumerate(all_m):
        cfg  = m.group(1)
        topo = None
        kind = None
        if cfg.startswith("Faz1_"):
            topo = cfg[5:]
            kind = 1
        elif cfg.startswith("Faz2_"):
            topo = cfg[5:]
            kind = 2
        else:
            continue

        start = m.end()
        end   = all_m[i+1].start() if i+1 < len(all_m) else len(content)
        raw   = content[start:end]

        if kind == 1:
            net  = None
            body = []
            for line in raw.split("\n"):
                s = line.strip()
                nm = re.match(r'^network\s*=\s*(\S+)', s)
                if nm:
                    net = nm.group(1)
                    continue
                if any(s.startswith(p) for p in HEADER_STARTS + REGEN_STARTS):
                    continue
                body.append(line)
            # trailing blanks
            while body and not body[-1].strip():
                body.pop()
            faz1_blocks[topo] = {"network": net or f"LoraMesh_{topo}", "body": body}

        elif kind == 2:
            for line in raw.split("\n"):
                s = line.strip()
                if "sendInterval" in s and ("sfInterval" in s or "!" in s):
                    val = s.split("=", 1)[1].strip() if "=" in s else s
                    faz2_sfline[topo] = val
                    break

    return faz1_blocks, faz2_sfline


def faz1_cfg(topo, sc, network, body, sendinterval_val):
    cfg  = f"Faz1_{sc}_{topo}"
    runs = FAZ_TABLE[1]["runs"]
    out  = []
    out.append(f"# {'─'*72}")
    out.append(f"# {cfg}  ({runs} run)")
    out.append(f"[Config {cfg}]")
    out.append(f"network        = {network}")
    out.append(f"sim-time-limit = 1200s")
    sc_desc = "Sc1-Ideal:sendInterval=180s" if sc == "Sc1" else "Sc2-DC:sendInterval=SF-bazli"
    out.append(f'description    = "Faz1 {sc_desc}"')
    out.append(f"output-scalar-file = results_faz1/${{configname}}-${{runnumber}}.sca")
    out.append(f"**.scalar-recording = true")
    out.append(f"**.vector-recording = false")
    out.append(f"")
    for l in FAZ_TABLE[1]["iter_lines"]:
        out.append(l)
    for l in FAZ_TABLE[1]["parallel_lines"]:
        out.append(l)
    out.append(f"")
    if sc == "Sc1":
        out.append(f"**.sensorGW*[*].app[0].sendInterval = 180s")
    else:
        out.append(f"**.sensorGW*[*].app[0].sendInterval = {sendinterval_val}")
    out.append(f"")
    out.extend(body)
    out.append(f"")
    return out


def fazN_cfg(faz_n, sc, topo):
    fd   = FAZ_TABLE[faz_n]
    cfg  = f"Faz{faz_n}_{sc}_{topo}"
    par  = f"Faz{faz_n-1}_{sc}_{topo}"
    out  = []
    out.append(f"[Config {cfg}]")
    out.append(f"extends        = {par}")
    out.append(f"output-scalar-file = results_faz{faz_n}/${{configname}}-${{runnumber}}.sca")
    lbl = fd["iso_label"]
    rns = fd["runs"]
    out.append(f'description    = "Faz{faz_n} {lbl}: {rns} run ({sc})"')
    for l in fd["iter_lines"]:
        out.append(l)
    for l in fd["fixed_lines"]:
        out.append(l)
    out.append(f"")
    return out


def generate(src, dst):
    print(f"[*] Kaynak: {src}")
    faz1_blocks, faz2_sfline = parse_blocks(src)
    print(f"[*] {len(faz1_blocks)} topoloji parse edildi.")

    lines = []
    lines.append("# =============================================================================")
    lines.append("# Arazi1 — 7 Fazli Kumülatif Kampanya  (Otomatik Üretildi)")
    lines.append("# Faz | Run/Config | 168 Config × Run")
    lines.append("# ----+------------+-----------")
    for n in range(1,8):
        r = FAZ_TABLE[n]["runs"]
        lines.append(f"# {n}   | {r:>10,} | {168*r:>11,}")
    lines.append("# =============================================================================")
    lines.append("")
    lines.append("[General]")
    lines.append("network = LoraMesh_GW2_Mesh1_MIN")
    lines.append("sim-time-limit = 1200s")
    lines.append("")

    totals = {n:0 for n in range(1,8)}

    # Sıralı topoloji: GW 2-7, Mesh 1-7, MIN/MAX
    topos = []
    for gw in range(2, 8):
        for mesh in range(1, 8):
            for mode in ("MIN", "MAX"):
                t = f"GW{gw}_Mesh{mesh}_{mode}"
                if t in faz1_blocks:
                    topos.append(t)

    print(f"[*] Sıralı topoloji sayısı: {len(topos)}")

    for topo in topos:
        blk    = faz1_blocks[topo]
        sfval  = faz2_sfline.get(topo,
                 "${sfInterval = 10s, 20s, 40s, 65s, 130s, 180s ! sensorSF}")
        for sc in ("Sc1", "Sc2"):
            lines.extend(faz1_cfg(topo, sc, blk["network"], blk["body"], sfval))
            totals[1] += FAZ_TABLE[1]["runs"]
            for n in range(2, 8):
                lines.extend(fazN_cfg(n, sc, topo))
                totals[n] += FAZ_TABLE[n]["runs"]

    with open(dst, "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")

    n_cfgs = sum(1 for l in lines if l.startswith("[Config "))
    n_lines = len(lines)
    print(f"\n{'─'*58}")
    print(f"  {dst}  ({n_cfgs} config, {n_lines:,} satır)")
    print(f"{'─'*58}")
    print(f"  Faz | Run/Config | Toplam Run")
    grand = 0
    for n in range(1,8):
        r = FAZ_TABLE[n]["runs"]
        t = totals[n]
        grand += t
        print(f"  {n}   | {r:>10,} | {t:>11,}")
    print(f"  {'─'*38}")
    print(f"  Kampanya Toplam: {grand:,} run")
    print(f"{'─'*58}\n")


if __name__ == "__main__":
    if not os.path.exists(SRC_INI):
        print(f"HATA: {SRC_INI} bulunamadi!"); sys.exit(1)
    generate(SRC_INI, DST_INI)
