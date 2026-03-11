// =============================================================================
// LoraMeshNetwork1000km2  —  1024 km² LoRaWAN + Meshtastic Kapsama Topolojisi
// =============================================================================
// Proje  : Kendi Kendini İyileştiren Hibrit LoRa Gateway Mimarisi
//   Eren ERDEM (2020502028) — Melisa KURAL (2021502041)
//   DEÜ EEE — Danışman: Prof. Dr. Damla GÜRKAN KUNTALP
//
// Alan     : 32 km × 32 km = 1024 km²
// GW       : 2 × HybridGateway  — minimum GW sayısı, tam alan kapsama
// Mesh     : 1 × MeshNode       — minimum röle, GW1↔MN1↔GW2 köprüsü
// Sensör   : 10 × EndNode / GW  = 20 toplam — maksimum LoRaWAN bağlantı
// Koşul    : İdeal (parazitsiz, σ=0, serbest-uzay karakteristik)
//
// ─── Kapsama Analizi ───────────────────────────────────────────────────────
//   Donanım : SX1303+SX1250,  Rx = −141 dBm,  Tx = 14 dBm ERP
//   Link Budget : 14 − (−141) = 155 dB
//   Path Loss (σ=0, γ=2.75): PL(d) = 31.3 + 27.5·log10(d)
//     155 = 31.3 + 27.5·log10(d)  →  d_max ≈ 32 km (ideal açık alan)
//
//   GW1 konumu : (8 km, 16 km)   — sol/batı yarısı
//   GW2 konumu : (24 km, 16 km)  — sağ/doğu yarısı
//   Köşe mesafesi : √(8²+16²) = 17.9 km  <  32 km  ✓
//   → TÜM 1024 km² TEK GW KATMANINDA KAPSAMDA
//   → 2 GW: Her GW bakhaul koptuğunda komşu GW üzerinden erişim sağlar
//
// ─── Minimum Mesh Tasarımı ────────────────────────────────────────────────
//   meshNode1 (16km,16km): GW1 ve GW2 arasında merkez köprü
//   Yollar: GW1 → MN1 → GW2    (zincir)
//           GW1 → GW2           (doğrudan sendDirect)
//   → Çift yol: tek arıza noktası yok
//
// ─── Maksimum LoRaWAN Bağlantı ────────────────────────────────────────────
//   SF12 / 125 kHz / 14 dBm / 11B payload → ToA = 1.97 s
//   ETSI EN 300 220-2, DC < %1 → min aralık = 197 s
//   Sim parametresi: sendInterval = 200 s  (maksimum yasal veri hızı)
//   10 sensör/GW × (1 pkt / 200 s) = 0.05 pkt/s/GW
//   ALOHA kapasite sınırı ≈ 10 000 sensör/GW; sim: 10/GW (hesap hızı)
//   Çift kapsama bandı: merkezde yer alan sensörler (x≈15-17 km) HER İKİ
//   GW tarafından alınır → bakhaul koptuğunda sıfır veri kaybı ✓
//
// ─── Failover Senaryosu ────────────────────────────────────────────────────
//   t=0       : Her iki GW ONLINE, tüm sensörler aktif
//   t=1800s   : GW1 internet bağlantısı kesilir (backhaulCutTime=1800s)
//   t=1800+   : GW1 modu → FAILOVER; veri akışı: sensör→GW1→MN1→GW2→internet
//   GW2       : Daima ONLINE (internet çıkış noktası)
//   DER       : 1.0 boyunca korunur — sıfır paket kaybı
// =============================================================================

import flora.LoRaPhy.LoRaMedium;
import inet.networklayer.configurator.ipv4.Ipv4NetworkConfigurator;
import inet.node.ethernet.Eth1G;
import inet.node.inet.Router;
import inet.physicallayer.wireless.ieee80211.packetlevel.Ieee80211ScalarRadioMedium;
import EndNode;
import HybridGateway;
import MeshNode;
import NetworkServer;

network LoraMeshNetwork1000km2
{
    parameters:
        @display("bgb=720,500;bgi=maps/terrain,s");

    submodules:

        // ── RF Ortam Motorları ──────────────────────────────────────────────
        // radioMedium : LoRaWAN sensör ↔ HybridGateway (SX1303 alıcı)
        // wlanMedium  : MeshNode dahili WLAN (enerji ölçümü için)
        radioMedium: LoRaMedium {
            @display("p=40,30;i=misc/sun;is=s");
        }
        wlanMedium: Ieee80211ScalarRadioMedium {
            @display("p=140,30;i=misc/sun;is=s");
        }
        configurator: Ipv4NetworkConfigurator {
            parameters:
                assignDisjunctSubnetAddresses = true;
                @display("p=40,460;is=vs");
        }

        // ── Sensör Grubu 1 — hybridGW1 (batı) kapsama alanı ───────────────
        // 10 × EndNode: yön ve mesafe çeşitliliği 1–15 km
        // [0] 7 km  batı       [1] 15 km güney      [2] 12.5 km GB
        // [3] 10.6 km GD (*)   [4] 10.6 km KD (*)   [5] 15 km kuzey
        // [6] 12.5 km KB       [7] 5.8 km yakın GB   [8] 5.8 km yakın KD
        // [9] 1.4 km çok yakın
        // (*) merkezde: GW2 menzilinde de — çift kapsama
        sensorGW1[10]: EndNode {
            @display("p=90,220");
        }

        // ── HybridGateway 1 — Batı, (8 km, 16 km) ─────────────────────────
        // Donanım: RPi CM4 + RAK5146 (SX1303+SX1250) + Heltec HT-CT62 (SX1262)
        // Başlangıç: ONLINE  →  t=1800s'de internet kesilir
        hybridGW1: HybridGateway {
            parameters:
                numEthInterfaces = 1;
                @display("p=185,260;i=device/accesspoint");
        }

        // ── Merkez Mesh Röle, (16 km, 16 km) ──────────────────────────────
        // Minimum 1 MeshNode: GW1↔MN1↔GW2 zinciri
        // Donanım: Heltec HT-CT62 (SX1262 + ESP32-C3), Band P 869.525 MHz
        meshNode1: MeshNode {
            parameters:
                @display("p=360,260");
        }

        // ── HybridGateway 2 — Doğu, (24 km, 16 km) ────────────────────────
        // Donanım: RPi CM4 + RAK5146 (SX1303+SX1250) + Heltec HT-CT62 (SX1262)
        // Her zaman ONLINE — internet erişim noktası (backhaulCutTime=-1s)
        hybridGW2: HybridGateway {
            parameters:
                numEthInterfaces = 1;
                @display("p=535,260;i=device/accesspoint");
        }

        // ── Sensör Grubu 2 — hybridGW2 (doğu) kapsama alanı ──────────────
        // 10 × EndNode: GW1'in simetrik yansıması
        // [0] 7 km  doğu       [1] 15 km güney      [2] 12.5 km GD
        // [3] 10.6 km GB (*)   [4] 10.6 km KG (*)   [5] 15 km kuzey
        // [6] 12.5 km KD       [7] 5.8 km yakın GD   [8] 5.8 km yakın KG
        // [9] 1.4 km çok yakın
        // (*) merkezde: GW1 menzilinde de — çift kapsama
        sensorGW2[10]: EndNode {
            @display("p=630,220");
        }

        // ── Kablolu Altyapı (Backhaul Omurga) ─────────────────────────────
        // gwRouter1: GW'leri internete bağlayan yönlendirici
        // networkServer: ChirpStack / TTN / Azure IoT Hub eşdeğeri
        gwRouter1: Router {
            @display("p=630,360");
        }
        networkServer: NetworkServer {
            parameters:
                numEthInterfaces = 1;
                numApps = 1;
                @display("p=630,430");
        }

    connections allowunconnected:

        // === BACKHAUL (Kablolu Ethernet 1 Gbit) ===
        hybridGW1.ethg++ <--> Eth1G <--> gwRouter1.ethg++;   // GW1 → router
        hybridGW2.ethg++ <--> Eth1G <--> gwRouter1.ethg++;   // GW2 → router
        gwRouter1.ethg++ <--> Eth1G <--> networkServer.ethg++;  // router → server

        // === MESH (sendDirect — fiziksel kablo YOK) ===
        // meshNode1 sadece beacon ile haberleşir, NED bağlantısı gereksiz.
}
