# Self-Healing Hybrid LoRa Gateway — OMNeT++ Simülasyonu

> **DEÜ Elektrik-Elektronik Mühendisliği Bitirme Projesi**  
> Eren ERDEM (2020502028) · Melisa KURAL (2021502041)  
> Danışman: Prof. Dr. Damla GÜRKAN KUNTALP

---

## Proje Hakkında

LoRaWAN altyapısında internet bağlantısı kesildiğinde **Meshtastic Gateway-to-Gateway (G2G)** protokolü üzerinden yedek yol oluşturan, bağlantı geri gelince otomatik olarak birincil yola dönen **kendi kendini iyileştiren (self-healing) hibrit gateway mimarisi**nin OMNeT++ ile simülasyonu.

### Hedef Mimari (PDF)

```
EndNode (STM32 + E77-900M)
    │  LoRaWAN  SF12 / 868 MHz
    ▼
HybridGateway-1  ─── NORMAL mod: doğrudan internet → NetworkServer
  (RPi CM4 + RAK5146 + HT-CT62)
    │  FAILOVER: Meshtastic G2G
    ▼
MeshNode  (SX1262 relay)
    │
    ▼
HybridGateway-2  (internet çıkışlı)
    │  WAN/LTE
    ▼
NetworkServer  (ChirpStack / TTN / Azure IoT Hub)
```

### 3 Senaryo

| Senaryo | Durum | Açıklama |
|---------|-------|----------|
| **Normal** | GW1 → internet | Standart LoRaWAN |
| **Failover** | GW1 → Mesh → GW2 → internet | İnternet kesildi, Meshtastic devreye girdi |
| **Self-Healing** | Mesh → internet | Bağlantı geri geldi, ONLINE moda dönüş |

---

## Simülasyon Ortamı

| Araç | Sürüm |
|------|-------|
| OMNeT++ | 6.0 |
| INET Framework | 4.4.x |
| FLoRa | 1.1.0 |

---

## Proje Yapısı

```
lora_mesh_projesi/
├── EndNode.ned           # LoRaWAN sensör nodu (STM32 + E77-900M)
├── HybridGateway.ned     # Hibrit GW (LoRaWAN + Meshtastic, RPi CM4)
├── MeshNode.ned          # Meshtastic relay düğümü (SX1262)
├── NetworkServer.ned     # Bulut LNS (ChirpStack/TTN)
├── LoraMeshNetwork.ned   # Ana topoloji
├── SensorLoRaApp.cc/h    # Sensör uygulama katmanı (11B payload)
├── SensorLoRaApp.ned     # Uygulama modülü tanımı
├── omnetpp.ini           # Simülasyon konfigürasyonu
└── Makefile              # opp_makemake ile oluşturuldu
```

---

## Sensör Payload Formatı (11 Byte, Little-Endian)

| Byte | Alan | Tip | Aralık |
|------|------|-----|--------|
| `[0..1]` | Sıra no | u16 | 0–65535 |
| `[2..3]` | Sıcaklık × 10 | i16 | −50..500 (−5.0°C..50.0°C) |
| `[4]` | Bağıl nem | u8 | 20–95 % |
| `[5]` | Toprak nemi | u8 | 0–100 % |
| `[6]` | Yağış | u8 | 0–50 mm/h |
| `[7..8]` | Basınç | u16 | 950–1050 hPa |
| `[9..10]` | Işık | u16 | 0–60000 lux |

---

## LoRa PHY Parametreleri (V1)

| Parametre | Değer |
|-----------|-------|
| Merkez Frekans | 868 MHz (EU868) |
| Spreading Factor | SF12 |
| Bant Genişliği | 125 kHz |
| Coding Rate | 4/4 |
| TX Gücü | 14 dBm |
| RX Sensitivitesi | −137 dBm |
| Path Loss Modeli | Log-Normal Shadowing (γ=2.08, σ=3.57 dB) |

---

## Derleme & Çalıştırma

### Gereksinimler

- OMNeT++ 6.0 (`omnetpp-6.0-linux-x86_64/omnetpp-6.0/`)
- INET 4.4 (`workspace/inet4.4/`)
- FLoRa (`workspace/flora/`)

### Derleme

```bash
# OMNeT++ ortamını aktive et
source /path/to/omnetpp-6.0/setenv

# Projeyi derle
cd lora_mesh_projesi
make -j$(nproc) MODE=debug
```

### Çalıştırma (Cmdenv)

```bash
cd lora_mesh_projesi
LD_LIBRARY_PATH="$LD_LIBRARY_PATH:../workspace/flora/src:../workspace/inet4.4/src" \
./lora_mesh_projesi_dbg -m -u Cmdenv \
  -n ".:../workspace/flora/src:../workspace/inet4.4/src" \
  omnetpp.ini
```

### Beklenen Çıktı

```
LoRa_ServerPacketReceived:count = 10
packetDropNoRouteFound:count    = 0   (tüm düğümlerde)
```

---

## Versiyon Yol Haritası

| Versiyon | Durum | İçerik |
|----------|-------|--------|
| **V1** | ✅ Tamamlandı | Temel topoloji, LoRaWAN → Mesh (Ethernet) → NS |
| **V2** | 🔄 Devam ediyor | Meshtastic G2G (SX1262 radyo), Failover Agent, Rlink izleme |
| **V3** | 📋 Planlandı | Çoklu GW, WRR yük dengeleme, QoS, self-healing döngüsü |
