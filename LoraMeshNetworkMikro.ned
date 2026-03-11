// =============================================================================
// LoraMeshNetworkMikro  —  Mesh Hop Teyit Topolojisi (Faz 1 Teşhis)
// =============================================================================
// Proje : Kendi Kendini İyileştiren Hibrit LoRa Gateway Mimarisi
//   Eren ERDEM (2020502028) — Melisa KURAL (2021502041)
//   DEÜ EEE — Danışman: Prof. Dr. Damla GÜRKAN KUNTALP
//
//  AMAÇ: Tek sensörün MeshNode üzerinden sekme (hop) yaparak GW'ye ulaştığını
//        kanıtlayan minimum topoloji.
//
//  MENZIL TEKNİĞİ (SF7, sigma=0):
//   SF7 d_max ≈ 7.4 km (sensitivity=-124 dBm, TX=14 dBm, gamma=2.75)
//
//   sensor[0]  @  x=10000m  (GW'ye 10km — ULAŞAMAZ, d_max aşıldı)
//        │
//        │ LoRa (5km, SF7 kapsama içinde ✓)
//        ▼
//   meshNode[0] @ x=5000m   (GW'ye 5km — LoRa kapsama içinde ✓)
//        │
//        │ WLAN/IP Mesh (sendDirect beacon)
//        ▼
//   hybridGW1 @ x=0m
//        │
//        │ Ethernet
//        ▼
//   gwRouter1 → networkServer
//
//  KANIT ZİNCİRİ (log çıktısında izlenecek):
//   1. sensor[0]  → LoRa yayını (SensorLoRaApp sendUplink)
//   2. hybridGW1  → rcvBelowSensitivity (10km > 7.4km, -124dBm sınırı)
//   3. meshNode[0]→ CAD preamble algılandı → ACTIVE_RX → paket alındı
//   4. meshNode[0]→ Yönlendirme talebi → next-hop: hybridGW1
//   5. networkServer → paket teslim alındı
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

network LoraMeshNetworkMikro
{
    parameters:
        @display("bgb=12000,3000;bgi=maps/terrain,s");

    submodules:

        // ── RF Ortam Motorları ─────────────────────────────────────────────
        radioMedium: LoRaMedium {
            @display("p=300,200;i=misc/sun;is=s");
        }
        wlanMedium: Ieee80211ScalarRadioMedium {
            @display("p=800,200;i=misc/sun;is=s");
        }

        // ── IP Yapılandırıcı ───────────────────────────────────────────────
        configurator: Ipv4NetworkConfigurator {
            parameters:
                assignDisjunctSubnetAddresses = true;
                @display("p=1400,200;is=vs");
        }

        // ── 1 HybridGateway (x=0m, orijin) ────────────────────────────────
        hybridGW1: HybridGateway {
            parameters:
                numEthInterfaces = 1;
                @display("p=500,1500;i=device/accesspoint");
        }

        // ── 1 MeshNode (x=5000m) — sensör ile GW arasında röle ────────────
        meshNode[1]: MeshNode {
            parameters:
                @display("p=3500,1500");
        }

        // ── 1 EndNode (LoRaWAN Sensör) x=10000m ───────────────────────────
        // GW'ye uzaklık: 10km > SF7 d_max(7.4km) → doğrudan ulaşAMAZ
        // MeshNode'a uzaklık: 5km < SF7 d_max(7.4km) → ULAŞIR
        sensor[1]: EndNode {
            @display("p=6500,1500");
        }

        // ── Kablolu Altyapı ────────────────────────────────────────────────
        gwRouter1: Router {
            @display("p=200,1500");
        }
        networkServer: NetworkServer {
            parameters:
                numEthInterfaces = 1;
                numApps = 1;
                @display("p=100,1500");
        }

    connections allowunconnected:

        hybridGW1.ethg++ <--> Eth1G <--> gwRouter1.ethg++;
        gwRouter1.ethg++ <--> Eth1G <--> networkServer.ethg++;
}
