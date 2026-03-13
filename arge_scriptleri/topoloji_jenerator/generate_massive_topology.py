#!/usr/bin/env python3
"""
generate_massive_topology.py — Devasa Ölçeklenebilirlik Topoloji Fabrikası
===========================================================================
Amaç : GW sayısı (2..10) × MeshPerGap (1..10) × Mod (MIN|MAX) üçlü
       Kartezyen çarpımı için NED + INI config + run_massive.sh üretir.
       Her topoloji → 36 run (sensorSF 7..12 × meshSF 7..12).
       Toplam: 9 × 10 × 2 × 36 = 6 480 simülasyon.

Kullanım:
  python3 generate_massive_topology.py             # Tüm 180 topolojiyi üret
  python3 generate_massive_topology.py --test      # Sadece GW=2, Mesh=1 (test)
  python3 generate_massive_topology.py --gw 3 --mesh 2 --mode MIN  # Tek kombo
  python3 generate_massive_topology.py --dry-run   # Üret ama dosyaya yazma

Üretilen dosyalar:
  lora_mesh_projesi/LoraMesh_GW{N}_Mesh{M}_{MODE}.ned  — NED topoloji (x180)
  lora_mesh_projesi/omnetpp.ini                         — config blokları eklenir
  lora_mesh_projesi/run_massive.sh                      — toplu batch runner

Topoloji Mantığı (lineer zincir):
  GW0 — MN[0..M-1] — GW1 — MN[M..2M-1] — GW2 — ... — GW{N-1}
  Her GW'nin yanına 10 sensör (Y-ekseninde dağılmış, X=GW.x)

Mod:
  MIN → hop_distance = 1 000 m (yoğun, kentsel stres testi)
  MAX → hop_distance = 6 000 m (Arazi1ile kanıtlanmış maks. mesafe)
"""

import os
import re
import sys
import stat
import argparse
from pathlib import Path
from typing import Tuple

# ─────────────────────────────────────────────────────────────────────────────
# Sabitler
# ─────────────────────────────────────────────────────────────────────────────
PROJ_DIR    = Path(__file__).resolve().parent.parent.parent  # arge_scriptleri/topoloji_jenerator/ → lora_mesh_projesi/
INI_FILE    = PROJ_DIR / "omnetpp.ini"
RUN_SCRIPT  = PROJ_DIR / "run_massive.sh"

OMNETPP_DIR = "/home/eren/Desktop/bitirme_lora_kod/omnetpp-6.0-linux-x86_64/omnetpp-6.0"
FLORA_DIR   = "/home/eren/Desktop/bitirme_lora_kod/workspace/flora"
INET_DIR    = "/home/eren/Desktop/bitirme_lora_kod/workspace/inet4.4"

NUM_GW_RANGE       = range(2, 11)   # 2 .. 10
MESH_PER_GAP_RANGE = range(1, 11)   # 1 .. 10
MODES              = ["MIN", "MAX"]
SENSORS_PER_GW     = 10

# Hop mesafesi (iki komşu düğüm arası)
HOP_M = {"MIN": 1_000, "MAX": 6_000}  # metre

# SF → paralel parametre listeleri (sıra: SF7, SF8, SF9, SF10, SF11, SF12)
SF_INTERVAL    = ["6.2s",    "11.3s",   "20.6s",  "41s",    "82s",    "147s" ]
GW_SENSITIVITY = ["-124dBm", "-127dBm", "-130dBm", "-133dBm", "-135dBm", "-141dBm"]
MESH_INTERVAL  = ["5s",      "9s",      "17s",     "29s",    "63s",    "265s" ]
CAD_DUR        = ["1ms",     "2ms",     "4ms",     "8ms",    "16ms",   "33ms" ]

# Sensör Y-ofsetleri (GW merkezi etrafında, ±çift yönde)
SENSOR_Y_OFFSETS = [500, 1000, 1500, 2000, 2500, -500, -1000, -1500, -2000, -2500]

# ─────────────────────────────────────────────────────────────────────────────
# Yardımcı: Config/NED adı üretimi
# ─────────────────────────────────────────────────────────────────────────────
def net_name(num_gw: int, mper: int, mode: str) -> str:
    return f"LoraMesh_GW{num_gw}_Mesh{mper}_{mode}"

def config_name(num_gw: int, mper: int, mode: str) -> str:
    return f"Scalable_GW{num_gw}_Mesh{mper}_{mode}"

# ─────────────────────────────────────────────────────────────────────────────
# Pozisyon hesaplama
# ─────────────────────────────────────────────────────────────────────────────
def compute_positions(num_gw: int, mper: int, mode: str) -> dict:
    """
    Döndürür: {
      'hybridGW{i}':       (x, y, z),
      'meshNode_{j}':      (x, y, z),   # global mesh index j
      'sensorGW{i}_{k}':  (x, y, z),   # GW i, sensor k
      'gwRouter{i}':       (x, y, z),
      'networkServer{i}':  (x, y, z),
    }
    """
    hop  = HOP_M[mode]
    gap  = (mper + 1) * hop          # GW-to-GW mesafesi

    pos = {}

    # GW'ler — x ekseninde eşit aralıklı
    for i in range(num_gw):
        pos[f"hybridGW{i}"] = (i * gap, 0, 10)

    # MeshNode'lar — her gap içinde mper adet
    mn_idx = 0
    for seg in range(num_gw - 1):
        gw_left_x = seg * gap
        for j in range(1, mper + 1):
            pos[f"meshNode_{mn_idx}"] = (gw_left_x + j * hop, 0, 5)
            mn_idx += 1

    # Sensörler — her GW için SENSORS_PER_GW adet, Y'de yayılmış
    for i in range(num_gw):
        gw_x = i * gap
        for k, y_off in enumerate(SENSOR_Y_OFFSETS):
            pos[f"sensorGW{i}_{k}"] = (gw_x, y_off, 1)

    # Backhaul altyapısı — her GW için gwRouter + networkServer
    for i in range(num_gw):
        gw_x = i * gap
        pos[f"gwRouter{i}"]      = (gw_x, -3000, 0)
        pos[f"networkServer{i}"] = (gw_x, -5000, 0)

    return pos


# ─────────────────────────────────────────────────────────────────────────────
# NED dosyası üretimi
# ─────────────────────────────────────────────────────────────────────────────
def generate_ned(num_gw: int, mper: int, mode: str, pos: dict) -> str:
    nn         = net_name(num_gw, mper, mode)
    hop        = HOP_M[mode]
    gap        = (mper + 1) * hop
    total_len  = (num_gw - 1) * gap
    total_mesh = (num_gw - 1) * mper
    total_sens = num_gw * SENSORS_PER_GW

    # Display canvas
    canvas_w = max(total_len + 5_000, 8_000)
    canvas_h = 12_000

    # Ölçek: display pikseli ≈ metre / scale_f
    scale_f = max(total_len / 6_000, 1.0)

    def dpx(x: int) -> int:
        return int(x / scale_f) + 500

    L = [
        f"// Auto-generated by generate_massive_topology.py",
        f"// ─────────────────────────────────────────────────────────────────",
        f"// Network   : {nn}",
        f"// Parameters: GW={num_gw}  MeshPerGap={mper}  Mode={mode}",
        f"// Distances : HopDist={hop}m  GapDist={gap}m  TotalLen={total_len}m",
        f"// Nodes     : {total_mesh} MeshNode, {total_sens} sensor ({SENSORS_PER_GW}/GW)",
        f"// Runs      : 36 (sensorSF 7..12 × meshSF 7..12)",
        f"// ─────────────────────────────────────────────────────────────────",
        f"",
        f"import flora.LoRaPhy.LoRaMedium;",
        f"import inet.networklayer.configurator.ipv4.Ipv4NetworkConfigurator;",
        f"import inet.node.ethernet.Eth1G;",
        f"import inet.node.inet.Router;",
        f"import inet.physicallayer.wireless.ieee80211.packetlevel.Ieee80211ScalarRadioMedium;",
        f"import EndNode;",
        f"import HybridGateway;",
        f"import MeshNode;",
        f"import NetworkServer;",
        f"",
        f"network {nn}",
        f"{{",
        f"    parameters:",
        f'        @display("bgb={canvas_w},{canvas_h}");',
        f"",
        f"    submodules:",
        f"",
        f"        // ── RF Ortam Motorları ───────────────────────────────────────",
        f'        radioMedium: LoRaMedium {{',
        f'            @display("p=500,200;i=misc/sun;is=s");',
        f'        }}',
        f'        wlanMedium: Ieee80211ScalarRadioMedium {{',
        f'            @display("p=1500,200;i=misc/sun;is=s");',
        f'        }}',
        f'        configurator: Ipv4NetworkConfigurator {{',
        f'            parameters:',
        f'                assignDisjunctSubnetAddresses = true;',
        f'                @display("p=2500,200;is=vs");',
        f'        }}',
        f"",
        f"        // ── HybridGateway'ler ({'daima çevrimiçi, backhaulCutTime=-1s'}) ──",
    ]

    for i in range(num_gw):
        x = pos[f"hybridGW{i}"][0]
        L += [
            f"        hybridGW{i}: HybridGateway {{",
            f"            parameters:",
            f"                numEthInterfaces = 1;",
            f'                @display("p={dpx(x)},800;i=device/accesspoint");',
            f"        }}",
        ]

    L.append("")

    if total_mesh > 0:
        L += [
            f"        // ── MeshNode zinciri ({total_mesh} düğüm, lineer) ─────────────────",
            f"        meshNode[{total_mesh}]: MeshNode {{",
            f'            parameters: @display("p=500,1200");',
            f"        }}",
            f"",
        ]

    L.append(f"        // ── Sensörler ({SENSORS_PER_GW}/GW, Y-ekseninde yayılmış) ──────────────")
    for i in range(num_gw):
        x = pos[f"hybridGW{i}"][0]
        L += [
            f"        sensorGW{i}[{SENSORS_PER_GW}]: EndNode {{",
            f'            @display("p={dpx(x)},2500");',
            f"        }}",
        ]

    L.append("")
    L.append(f"        // ── Kablolu Altyapı: gwRouter + networkServer (her GW bağımsız) ──")
    for i in range(num_gw):
        x = pos[f"hybridGW{i}"][0]
        L += [
            f"        gwRouter{i}: Router {{",
            f'            @display("p={dpx(x)},3500");',
            f"        }}",
            f"        networkServer{i}: NetworkServer {{",
            f"            parameters:",
            f"                numEthInterfaces = 1;",
            f"                numApps = 1;",
            f'                @display("p={dpx(x)},4500");',
            f"        }}",
        ]

    L += [
        f"",
        f"    connections allowunconnected:",
        f"",
        f"        // === BACKHAUL (kablolu): GW → gwRouter → networkServer ===",
    ]
    for i in range(num_gw):
        L += [
            f"        hybridGW{i}.ethg++ <--> Eth1G <--> gwRouter{i}.ethg++;",
            f"        gwRouter{i}.ethg++ <--> Eth1G <--> networkServer{i}.ethg++;",
        ]

    L += [
        f"",
        f"        // === MeshNode'lar ve sensörler kablosuz (sendDirect beacon) ===",
        f"}}",
    ]

    return "\n".join(L) + "\n"


# ─────────────────────────────────────────────────────────────────────────────
# INI config bloku üretimi
# ─────────────────────────────────────────────────────────────────────────────
def generate_ini_block(num_gw: int, mper: int, mode: str, pos: dict) -> str:
    nn         = net_name(num_gw, mper, mode)
    cn         = config_name(num_gw, mper, mode)
    hop        = HOP_M[mode]
    gap        = (mper + 1) * hop
    total_len  = (num_gw - 1) * gap
    total_mesh = (num_gw - 1) * mper
    total_sens = num_gw * SENSORS_PER_GW

    # Tüm GW isimlerini boşlukla ayır (meshNeighborList için)
    all_gw_names = " ".join(f"hybridGW{i}" for i in range(num_gw))

    # SF paralel parametre stringleri
    sf_int_str  = ", ".join(SF_INTERVAL)
    gw_sens_str = ", ".join(GW_SENSITIVITY)
    mi_str      = ", ".join(MESH_INTERVAL)
    cd_str      = ", ".join(CAD_DUR)

    # Komşu önbellek menzili: topoloji uzunluğu + 10km tampon (min 35km)
    nb_range = max(5_000, total_len + 3_000)  # commRange ~3500m → cache range 5-8 km yeterli

    # Kısıt alanı
    max_x = total_len + 2_000
    max_y = 3_500
    min_y = -6_000

    L = [
        f"",
        f"# {'='*77}",
        f"# Config   : {cn}",
        f"# GW={num_gw}  MeshPerGap={mper}  Mod={mode}",
        f"# Hop={hop}m  Gap={gap}m  ToplamUzunluk={total_len}m",
        f"# MeshNode={total_mesh}  Sensör={total_sens} ({SENSORS_PER_GW}/GW)",
        f"# Run=36  (sensorSF 7..12 × meshSF 7..12), sigma=0.0",
        f"# {'='*77}",
        f"",
        f"[Config {cn}]",
        f"network        = {nn}",
        f"sim-time-limit = 1200s",
        f'description    = "Scalable GW={num_gw} Mesh={mper} {mode}: '
        f'{total_sens} sensör, {total_mesh} MeshNode, sigma=0, backhaulCutTime=-1s"',
        f"",
        f"**.scalar-recording = true",
        f"**.vector-recording = false",
        f"",
        f"# ── Kartezyen çarpım: sensorSF × meshSF = 36 run ──────────────────────────",
        f"**.sensorGW*[*].app[0].initialLoRaSF       = ${{sensorSF    = 7, 8, 9, 10, 11, 12}}",
        f"**.meshNode[*].meshRouting.loraSF           = ${{meshSF      = 7, 8, 9, 10, 11, 12}}",
        f"**.radioMedium.pathLoss.sigma               = 0.0",
        f"**.sigma                                    = 0.0",
        f"",
        f"# ── sensorSF paralel (!): sendInterval + gwSensitivity ────────────────────",
        f"**.sensorGW*[*].app[0].dataSize      = 20B",
        f"**.sensorGW*[*].app[0].sendInterval  = ${{sfInterval   = {sf_int_str} ! sensorSF}}",
        f"**.LoRaGWNic.radio.receiver.sensitivity = ${{gwSensitivity = {gw_sens_str} ! sensorSF}}",
        f"",
        f"# ── meshSF paralel (!): beaconInterval + cadDuration ──────────────────────",
        f"**.meshNode[*].meshRouting.beaconInterval = ${{meshInterval = {mi_str} ! meshSF}}",
        f"**.meshNode[*].meshRouting.cadDuration    = ${{cadDur       = {cd_str} ! meshSF}}",
        f"",
        f"# ── LoRaWAN Fiziksel Ortam ─────────────────────────────────────────────────",
        f"**.radioMedium.pathLoss.d0          = 1m",
        f"**.radioMedium.pathLoss.gamma       = 2.75",
        f"**.radioMedium.pathLoss.pl_d0_db    = 31.54",
        f"**.radioMedium.pathLoss.max_sensitivity_dBm = -115.0",  # -141→-115: commRange 30km→3.5km (spatial reuse)
        f"**.radioMedium.mediumLimitCache.maxTransmissionDuration = 5s",
        f"**.radioMedium.mediumLimitCache.maxTransmissionPower = 0.025118W",  # fix NaN → enables commRange rangeFilter
        f'**.radioMedium.pathLossType         = "LoRaLogNormalShadowing"',
        f"**.minInterferenceTime              = 0s",
        f'**.radioMedium.mediumLimitCacheType = "LoRaMediumCache"',
        f'**.radioMedium.rangeFilter          = "communicationRange"',
        f'**.radioMedium.neighborCacheType    = "LoRaNeighborCache"',
        f"**.radioMedium.neighborCache.range  = {nb_range}m",
        f"**.radioMedium.neighborCache.refillPeriod = 1200s",
        f"{nn}.**.radio.separateTransmissionParts = false",
        f"{nn}.**.radio.separateReceptionParts    = false",
        f"",
        f"# ── Global ARP & IP yönlendirme ────────────────────────────────────────────",
        f'**.arp.typename = "GlobalArp"',
    ]

    for i in range(num_gw):
        L.append(f"**.gwRouter{i}.ipv4.forwarding     = true")
        L.append(f"**.hybridGW{i}.ipv4.forwarding     = true")

    L += [
        f"",
        f"# ── Global GW parametreleri (backhaulCutTime=-1s → daima çevrimiçi) ────────",
        f"**.LoRaGWNic.radio.iAmGateway              = true",
        f"**.packetForwarder.localPort               = 2000",
        f"**.packetForwarder.destPort                = 1000",
        f"**.routingAgent.backhaulCutTime            = -1s",
        f"**.routingAgent.maxQueueSize               = 200",
        f"**.routingAgent.neighborTimeout            = 120s",
        f"**.routingAgent.bandMTxPower_dBm           = 14.0",
        f"**.routingAgent.bandMDutyCycle             = 0.01",
        f"**.routingAgent.rx2TxPower_dBm             = 14.0",  # 27→14 dBm: standart LoRa txPower
        f"**.routingAgent.rx2DutyCycle               = 0.10",
        f"**.routingAgent.rx2Frequency               = 869.525MHz",
        f"**.routingAgent.antennaGain_dBi            = 0.0",
        f"**.routingAgent.numDemodulators            = 16",
        f"**.routingAgent.txQuotaWindow              = 3600s",
        f"**.routingAgent.beaconRssi                 = -72.0",
        f"**.routingAgent.sensorPacketRate           = 5.0",
        f"",
        f"# ── Per-GW: destAddresses, meshAddress, meshNeighborList ───────────────────",
    ]

    for i in range(num_gw):
        L += [
            f'**.hybridGW{i}.packetForwarder.destAddresses = "networkServer{i}"',
            f'**.hybridGW{i}.routingAgent.meshAddress       = "10.1.0.{i+1}"',
            f'**.hybridGW{i}.routingAgent.meshNeighborList  = "{all_gw_names} meshNode"',
        ]

    L += [
        f"",
        f"# ── MeshNode parametreleri ─────────────────────────────────────────────────",
        f'**.meshNode[*].wlan[*].radio.radioMediumModule = "wlanMedium"',
        f"**.meshNode[*].meshRouting.loraBandwidth       = 250000Hz",
        f"**.meshNode[*].meshRouting.neighborTimeout     = 120s",
        f'**.meshNode[*].meshRouting.meshNeighborList    = "{all_gw_names} meshNode"',
    ]

    # Per-meshNode meshAddress (global linear index)
    mn_idx = 0
    for seg in range(num_gw - 1):
        for j in range(mper):
            L.append(f'**.meshNode[{mn_idx}].meshRouting.meshAddress = "10.20.0.{mn_idx+1}"')
            mn_idx += 1

    L += [
        f"",
        f"# ── Sensör Uygulama Katmanı (wildcard: tüm sensorGW* dizileri) ─────────────",
        f"**.sensorGW*[*].numApps                      = 1",
        f'**.sensorGW*[*].app[0].typename              = "SensorLoRaApp"',
        f"**.sensorGW*[*].app[0].numberOfPacketsToSend = 0",
        f"**.sensorGW*[*].app[0].initialLoRaTP         = 14dBm",
        f"**.sensorGW*[*].app[0].initialLoRaCF         = 868.1MHz",
        f"**.sensorGW*[*].app[0].initialLoRaBW         = 125kHz",
        f"**.sensorGW*[*].app[0].initialLoRaCR         = 4",
        f"**.sensorGW*[*].app[0].initialUseHeader      = true",
        f"",
        f"# ── Staggered start: SF12 ToA=1.97s → 3.5s aralık (tüm SF için güvenli) ──",
    ]

    for i in range(num_gw):
        for k in range(SENSORS_PER_GW):
            t = 2.0 + (i * SENSORS_PER_GW + k) * 3.5
            L.append(f"**.sensorGW{i}[{k}].app[0].startTime = {t:.1f}s")

    L += [
        f"",
        f"# ── Per-NS konfigürasyonu ─────────────────────────────────────────────────",
    ]
    for i in range(num_gw):
        L += [
            f"**.networkServer{i}.numApps              = 1",
            f'**.networkServer{i}.app[0].typename      = "NetworkServerApp"',
            f"**.networkServer{i}.app[0].localPort     = 1000",
            f"**.networkServer{i}.app[0].destPort      = 2000",
            f'**.networkServer{i}.app[0].destAddresses = "hybridGW{i}"',
        ]

    L += [
        f"",
        f"# ── Mobility başlangıç konumları ──────────────────────────────────────────",
        f"**.mobility.initFromDisplayString = false",
        f"",
    ]

    # GW konumları
    for i in range(num_gw):
        x, y, z = pos[f"hybridGW{i}"]
        L += [
            f"**.hybridGW{i}.mobility.initialX = {x}m",
            f"**.hybridGW{i}.mobility.initialY = {y}m",
            f"**.hybridGW{i}.mobility.initialZ = {z}m",
        ]

    L.append("")

    # MeshNode konumları
    mn_idx = 0
    for seg in range(num_gw - 1):
        for j in range(mper):
            x, y, z = pos[f"meshNode_{mn_idx}"]
            L += [
                f"**.meshNode[{mn_idx}].mobility.initialX = {x}m",
                f"**.meshNode[{mn_idx}].mobility.initialY = {y}m",
                f"**.meshNode[{mn_idx}].mobility.initialZ = {z}m",
            ]
            mn_idx += 1

    L.append("")

    # Sensör konumları
    for i in range(num_gw):
        for k in range(SENSORS_PER_GW):
            x, y, z = pos[f"sensorGW{i}_{k}"]
            L += [
                f"**.sensorGW{i}[{k}].mobility.initialX = {x}m",
                f"**.sensorGW{i}[{k}].mobility.initialY = {y}m",
                f"**.sensorGW{i}[{k}].mobility.initialZ = {z}m",
            ]

    L.append("")

    # gwRouter + networkServer konumları
    for i in range(num_gw):
        rx, ry, rz = pos[f"gwRouter{i}"]
        nx, ny, nz = pos[f"networkServer{i}"]
        L += [
            f"**.gwRouter{i}.mobility.initialX      = {rx}m",
            f"**.gwRouter{i}.mobility.initialY      = {ry}m",
            f"**.gwRouter{i}.mobility.initialZ      = {rz}m",
            f"**.networkServer{i}.mobility.initialX = {nx}m",
            f"**.networkServer{i}.mobility.initialY = {ny}m",
            f"**.networkServer{i}.mobility.initialZ = {nz}m",
        ]

    L += [
        f"",
        f"**.constraintAreaMinX = -1000m",
        f"**.constraintAreaMinY = {min_y}m",
        f"**.constraintAreaMaxX = {max_x}m",
        f"**.constraintAreaMaxY = {max_y}m",
        f"**.constraintAreaMinZ = 0m",
        f"**.constraintAreaMaxZ = 20m",
    ]

    return "\n".join(L) + "\n"


# ─────────────────────────────────────────────────────────────────────────────
# run_massive.sh üretimi
# ─────────────────────────────────────────────────────────────────────────────
def generate_run_script(all_configs: list) -> str:
    total = len(all_configs) * 36  # 36 run/config
    cfg_lines = "\n".join(f'    "{c}"' for c in all_configs)

    return f"""#!/bin/bash
# =============================================================================
# run_massive.sh — Auto-generated by generate_massive_topology.py
# =============================================================================
# Toplam config : {len(all_configs)}
# Run/config    : 36  (sensorSF 7..12 × meshSF 7..12)
# Toplam run    : {total}
#
# Kullanım:
#   bash run_massive.sh [--jobs N] [--from-config IDX] [--to-config IDX]
#   bash run_massive.sh --config Scalable_GW2_Mesh1_MIN        # tek config
#   bash run_massive.sh --jobs 4 --from-config 0 --to-config 9  # ilk 10 config
#
# Resume: .done flag'leri sayesinde kaldığı yerden devam eder.
#   Silmek için: rm -rf logs_massive/<ConfigName>
# =============================================================================

set -euo pipefail

PROJ_DIR="$(cd "$(dirname "${{BASH_SOURCE[0]}}")" && pwd)"
BIN="${{PROJ_DIR}}/lora_mesh_projesi_dbg"
OMNETPP_DIR="{OMNETPP_DIR}"
FLORA="{FLORA_DIR}"
INET="{INET_DIR}"
RUNS_PER_CONFIG=36
LOG_BASE="${{PROJ_DIR}}/logs_massive"

export LD_LIBRARY_PATH="${{OMNETPP_DIR}}/lib:${{FLORA}}/src:${{INET}}/src${{LD_LIBRARY_PATH:+:$LD_LIBRARY_PATH}}"

# ── Config listesi (auto-generated) ──────────────────────────────────────────
CONFIGS=(
{cfg_lines}
)
TOTAL_CONFIGS=${{#CONFIGS[@]}}

# ── Argüman parse ─────────────────────────────────────────────────────────────
JOBS=1
FROM_CFG=0
TO_CFG=$(( TOTAL_CONFIGS - 1 ))

while [[ $# -gt 0 ]]; do
    case $1 in
        --jobs)         JOBS="$2";     shift 2 ;;
        --from-config)  FROM_CFG="$2"; shift 2 ;;
        --to-config)    TO_CFG="$2";   shift 2 ;;
        --config)
            CFG_NAME="$2"
            for idx in "${{!CONFIGS[@]}}"; do
                if [[ "${{CONFIGS[$idx]}}" == "$CFG_NAME" ]]; then
                    FROM_CFG=$idx; TO_CFG=$idx; break
                fi
            done
            shift 2 ;;
        *) echo "Bilinmeyen argüman: $1"; exit 1 ;;
    esac
done

mkdir -p "${{LOG_BASE}}"
cd "${{PROJ_DIR}}"

# ── Tek bir run'ı çalıştıran fonksiyon ───────────────────────────────────────
run_one() {{
    local config="$1"
    local run="$2"
    local log_dir="${{LOG_BASE}}/${{config}}"
    local log="${{log_dir}}/run_${{run}}.log"
    local done_flag="${{log_dir}}/run_${{run}}.done"

    mkdir -p "${{log_dir}}"

    # Resume: tamamlanmış run'ı atla
    if [[ -f "${{done_flag}}" ]]; then
        return 0
    fi

    "${{BIN}}" -m -c "${{config}}" -r "${{run}}" -u Cmdenv \\
        -n ".:{FLORA_DIR}/src:{INET_DIR}/src" \\
        > "${{log}}" 2>&1

    local exit_code=$?
    if [[ ${{exit_code}} -eq 0 ]]; then
        touch "${{done_flag}}"
        (
            flock -x 200
            DONE_COUNT=$(find "${{LOG_BASE}}" -name "*.done" 2>/dev/null | wc -l)
            echo "[DONE] ${{config}} run=${{run}}  (${{DONE_COUNT}}/{total} toplam)"
        ) 200>"${{LOG_BASE}}/.lock"
    else
        echo "[FAIL] ${{config}} run=${{run}}  exit=${{exit_code}}  log=${{log}}"
        return ${{exit_code}}
    fi
}}

export -f run_one
export BIN FLORA INET LOG_BASE PROJ_DIR

# ── Özet ──────────────────────────────────────────────────────────────────────
echo "=== run_massive.sh ==="
echo "Toplam config : ${{TOTAL_CONFIGS}}"
echo "Seçilen range : ${{FROM_CFG}} .. ${{TO_CFG}} ($(( TO_CFG - FROM_CFG + 1 )) config)"
echo "Run/config    : ${{RUNS_PER_CONFIG}}"
echo "Paralel       : ${{JOBS}} iş"
echo "Logs          : ${{LOG_BASE}}/"
echo ""

WALL_START=$(date +%s)
TOTAL_FAILED=0

# ── Ana döngü ─────────────────────────────────────────────────────────────────
for cfg_idx in $(seq "${{FROM_CFG}}" "${{TO_CFG}}"); do
    config="${{CONFIGS[$cfg_idx]}}"
    log_dir="${{LOG_BASE}}/${{config}}"

    echo "─── Config [${{cfg_idx}}/${{TOTAL_CONFIGS}}]: ${{config}}"

    if [[ ${{JOBS}} -gt 1 ]] && command -v parallel &>/dev/null; then
        seq 0 $(( RUNS_PER_CONFIG - 1 )) | \\
            parallel -j "${{JOBS}}" --line-buffer run_one "${{config}}" {{}}
    else
        if [[ ${{JOBS}} -gt 1 && ${{cfg_idx}} -eq ${{FROM_CFG}} ]]; then
            echo "  UYARI: GNU Parallel bulunamadı, sıralı mod."
        fi
        for run in $(seq 0 $(( RUNS_PER_CONFIG - 1 ))); do
            run_one "${{config}}" "${{run}}" || (( TOTAL_FAILED++ ))
        done
    fi

    # Config özet satırı
    DONE_FOR_CFG=$(find "${{log_dir}}" -name "*.done" 2>/dev/null | wc -l)
    echo "    → ${{DONE_FOR_CFG}}/${{RUNS_PER_CONFIG}} tamamlandı"
done

WALL_END=$(date +%s)
ELAPSED=$(( WALL_END - WALL_START ))

echo ""
echo "=== Batch tamamlandı ==="
echo "Geçen süre   : $(( ELAPSED / 3600 ))s $(( (ELAPSED % 3600) / 60 ))dk $(( ELAPSED % 60 ))sn"
echo "Başarısız    : ${{TOTAL_FAILED}}"
echo "SCA dosyaları: ${{PROJ_DIR}}/results/Scalable_*.sca"
"""


# ─────────────────────────────────────────────────────────────────────────────
# Dosya yazma (idempotent)
# ─────────────────────────────────────────────────────────────────────────────
def write_ned(num_gw: int, mper: int, mode: str, ned_text: str,
              dry_run: bool = False) -> bool:
    """NED dosyasını yazar. Zaten varsa üzerine yazar (regenerate)."""
    path = PROJ_DIR / f"{net_name(num_gw, mper, mode)}.ned"
    if dry_run:
        print(f"  [DRY] NED → {path.name}  ({len(ned_text)} karakter)")
        return True
    path.write_text(ned_text, encoding="utf-8")
    return True


def append_ini_block(num_gw: int, mper: int, mode: str, block: str,
                     dry_run: bool = False) -> bool:
    """
    INI bloğunu omnetpp.ini sonuna ekler.
    Config zaten varsa atlar (idempotent).
    """
    cn = config_name(num_gw, mper, mode)
    header = f"[Config {cn}]"

    current = INI_FILE.read_text(encoding="utf-8") if INI_FILE.exists() else ""
    # Satır başında tam eşleşme ara (comment satırlarını atla)
    if re.search(r'^\[Config ' + re.escape(cn) + r'\]', current, re.MULTILINE):
        print(f"  [SKIP] INI config '{cn}' zaten mevcut.")
        return False

    if dry_run:
        print(f"  [DRY] INI ← '{cn}'  ({len(block)} karakter)")
        return True

    with INI_FILE.open("a", encoding="utf-8") as f:
        f.write(block)
    return True


# ─────────────────────────────────────────────────────────────────────────────
# Tek kombinasyon işle
# ─────────────────────────────────────────────────────────────────────────────
def process_one(num_gw: int, mper: int, mode: str, dry_run: bool = False) -> str:
    """NED + INI üretir, diskle yazar. Config adını döndürür."""
    pos      = compute_positions(num_gw, mper, mode)
    ned_text = generate_ned(num_gw, mper, mode, pos)
    ini_blk  = generate_ini_block(num_gw, mper, mode, pos)

    write_ned(num_gw, mper, mode, ned_text, dry_run)
    append_ini_block(num_gw, mper, mode, ini_blk, dry_run)

    cn = config_name(num_gw, mper, mode)
    print(f"  OK  {cn}  "
          f"(mesh={( num_gw-1)*mper}, sens={num_gw*SENSORS_PER_GW}, "
          f"len={(num_gw-1)*(mper+1)*HOP_M[mode]//1000}km)")
    return cn


# ─────────────────────────────────────────────────────────────────────────────
# Ana giriş noktası
# ─────────────────────────────────────────────────────────────────────────────
def main() -> None:
    parser = argparse.ArgumentParser(
        description="Devasa topoloji fabrikası: NED + INI + run_massive.sh üretir"
    )
    parser.add_argument("--test",    action="store_true",
                        help="Sadece GW=2, Mesh=1 (her iki mod) üret ve çık")
    parser.add_argument("--dry-run", action="store_true",
                        help="Dosyaya yazma, sadece ne yapılacağını göster")
    parser.add_argument("--gw",    type=int, default=0,
                        help="Tek kombinasyon: GW sayısı (2..10)")
    parser.add_argument("--mesh",  type=int, default=0,
                        help="Tek kombinasyon: mesh/gap (1..10)")
    parser.add_argument("--mode",  type=str, default="",
                        choices=["MIN", "MAX", "ALL"],
                        help="Mesafe modu veya ALL (varsayılan: ALL)")
    args = parser.parse_args()

    # Üretilecek kombinasyon listesi
    if args.test:
        combos = [(2, 1, "MIN"), (2, 1, "MAX")]
        print("=== TEST MODU: Yalnızca GW=2, Mesh=1 üretiliyor ===")
    elif args.gw and args.mesh:
        modes = MODES if (not args.mode or args.mode == "ALL") else [args.mode]
        combos = [(args.gw, args.mesh, m) for m in modes]
        print(f"=== TEK KOMBİNASYON: GW={args.gw}, Mesh={args.mesh} ===")
    else:
        combos = [
            (ng, mp, mo)
            for ng in NUM_GW_RANGE
            for mp in MESH_PER_GAP_RANGE
            for mo in MODES
        ]
        print(f"=== TAM ÜRETIM: {len(combos)} kombinasyon × 36 run = "
              f"{len(combos)*36:,} simülasyon ===")

    print(f"Proje dizini : {PROJ_DIR}")
    print(f"INI dosyası  : {INI_FILE}")
    print(f"Dry-run      : {args.dry_run}")
    print("")

    generated_configs = []
    for num_gw, mper, mode in combos:
        cn = process_one(num_gw, mper, mode, dry_run=args.dry_run)
        generated_configs.append(cn)

    # run_massive.sh: --test modunda da yap (tüm olası config'leri veya üretilenler)
    if args.test or (args.gw and args.mesh):
        # Test modunda sadece üretilen config'leri run script'e koy
        run_configs = generated_configs
    else:
        # Tam modda tüm config listesini oluştur (INI'ye eklenmiş olsun ya da olmasın)
        run_configs = [
            config_name(ng, mp, mo)
            for ng in NUM_GW_RANGE
            for mp in MESH_PER_GAP_RANGE
            for mo in MODES
        ]

    run_sh_text = generate_run_script(run_configs)
    if not args.dry_run:
        RUN_SCRIPT.write_text(run_sh_text, encoding="utf-8")
        RUN_SCRIPT.chmod(RUN_SCRIPT.stat().st_mode | stat.S_IEXEC | stat.S_IXGRP | stat.S_IXOTH)
        print(f"\nrun_massive.sh → {RUN_SCRIPT}  ({len(run_configs)} config, "
              f"{len(run_configs)*36:,} run)")
    else:
        print(f"\n[DRY] run_massive.sh  ({len(run_configs)} config)")

    print("")
    print(f"=== Tamamlandı: {len(generated_configs)} topoloji üretildi ===")

    # ── Test modunda hızlı NED sözdizim önizlemesi ────────────────────────────
    if args.test:
        print("")
        print("─── NED Özeti (LoraMesh_GW2_Mesh1_MIN) ───────────────────────────────────")
        ned_path = PROJ_DIR / "LoraMesh_GW2_Mesh1_MIN.ned"
        if ned_path.exists():
            lines = ned_path.read_text().splitlines()
            # Submodule listesini göster
            in_sub = False
            for ln in lines:
                if "submodules:" in ln:
                    in_sub = True
                if in_sub:
                    print(f"  {ln}")
                if in_sub and "connections" in ln:
                    break
        print("─── INI Blok Başlangıcı (Scalable_GW2_Mesh1_MIN) ─────────────────────────")
        if not args.dry_run:
            ini_text = INI_FILE.read_text()
            start = ini_text.find("[Config Scalable_GW2_Mesh1_MIN]")
            if start >= 0:
                snippet = ini_text[start:start+800]
                print(snippet)
                print("  ... (devamı omnetpp.ini'de)")


if __name__ == "__main__":
    main()
