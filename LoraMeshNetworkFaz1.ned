// =============================================================================
// LoraMeshNetworkFaz1  —  Doğrusal Kalibrasyon Topolojisi (Faz 1)
// =============================================================================
// Proje : Kendi Kendini İyileştiren Hibrit LoRa Gateway Mimarisi
//   Eren ERDEM (2020502028) — Melisa KURAL (2021502041)
//   DEÜ EEE — Danışman: Prof. Dr. Damla GÜRKAN KUNTALP
//
//  AMAÇ:
//   Hiçbir rastgelelik (sigma=0), engel veya hava koşulu olmaksızın açık arazi
//   (serbest uzay / log-distance) path loss modeliyle SF7..SF12 menzil sınırlarını
//   ve maksimum payload kapasitesini ölçen REFERANS (baseline) topolojisi.
//
//  TOPOLOJI (X ekseni boyunca düz çizgi):
//
//   NS ─ gwRouter1 ─ [Eth] ─ hybridGW1(0m) ─[LoRa]─ sensor[0](2km)
//                                           ─[LoRa]─ sensor[1](5km)
//                                           ─[LoRa]─ sensor[2](10km)
//                                           ─[LoRa]─ sensor[3](15km)
//                                           ─[LoRa]─ sensor[4](25km)
//
//   meshNode[0..4]: lineer zincir (GW'nin backhaul kesilince aktifleşir)
//     hybridGW1 <~beacon~> meshNode[0] <~beacon~> ... <~beacon~> meshNode[4]
//
//  RF PARAMETRELER:
//   LoRaWAN : Sweep SF7..SF12 / 125kHz / 14dBm / 868.1MHz
//   Path loss: PL(d) = 31.54 + 27.5·log10(d) dB  [kırsal açık alan, sigma=0]
//   Sensör hassasiyet @ TX=14dBm:
//     SF7 (-124 dBm) → d_max ≈ 7.4 km
//     SF8 (-127 dBm) → d_max ≈ 9.6 km
//     SF9 (-130 dBm) → d_max ≈ 12.3 km
//     SF10 (-133 dBm) → d_max ≈ 15.8 km
//     SF11 (-135 dBm) → d_max ≈ 18.7 km
//     SF12 (-141 dBm) → d_max ≈ 30.9 km
//
//  BEKLENEN REFERANS MATRISI:
//     SF7 / SF8  → sadece 2km+5km sensörler ✓ ; 10km+ ✗ (rcvBelowSensitivity)
//     SF9        → 2km+5km+10km ✓            ; 15km+ ✗
//     SF10       → 2km..15km ✓               ; 25km  ✗
//     SF11       → 2km..15km ✓               ; 25km  ✗
//     SF12       → tüm sensörler (2..25km)   ✓
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

network LoraMeshNetworkFaz1
{
    parameters:
        // Görsel: 30km × 6km canvas (1px ≈ 3m @ bgb=10000,2000)
        @display("bgb=10000,2000;bgi=maps/terrain,s");

    submodules:

        // ── RF Ortam Motorları ─────────────────────────────────────────────
        radioMedium: LoRaMedium {
            @display("p=200,100;i=misc/sun;is=s");
        }
        wlanMedium: Ieee80211ScalarRadioMedium {
            @display("p=600,100;i=misc/sun;is=s");
        }

        // ── IP Yapılandırıcı ───────────────────────────────────────────────
        configurator: Ipv4NetworkConfigurator {
            parameters:
                assignDisjunctSubnetAddresses = true;
                @display("p=1000,100;is=vs");
        }

        // ── 1 adet HybridGateway (X=0, orijin) ────────────────────────────
        hybridGW1: HybridGateway {
            parameters:
                numEthInterfaces = 1;
                @display("p=500,1000;i=device/accesspoint");
        }

        // ── 5 MeshNode — lineer zincir, artan mesafede ────────────────────
        // meshNode[0]:  2km  meshNode[1]:  5km  meshNode[2]: 10km
        // meshNode[3]: 15km  meshNode[4]: 25km
        meshNode[5]: MeshNode {
            parameters:
                @display("p=2500,1200");
        }

        // ── 5 EndNode (LoRaWAN Sensör) — her MeshNode konumuna yakın ──────
        // sensor[0]:  2km  sensor[1]:  5km  sensor[2]: 10km
        // sensor[3]: 15km  sensor[4]: 25km
        sensor[5]: EndNode {
            @display("p=2500,800");
        }

        // ── Kablolu Altyapı ────────────────────────────────────────────────
        gwRouter1: Router {
            @display("p=200,1000");
        }
        networkServer: NetworkServer {
            parameters:
                numEthInterfaces = 1;
                numApps = 1;
                @display("p=100,1000");
        }

    connections allowunconnected:

        // === BACKHAUL (Kablolu, her zaman aktif) ===
        hybridGW1.ethg++ <--> Eth1G <--> gwRouter1.ethg++;
        gwRouter1.ethg++ <--> Eth1G <--> networkServer.ethg++;

        // === MeshNode'lar sadece sendDirect() beacon ile haberleşir ===
        // Fiziksel kablo bağlantısı YOK (allowunconnected).
}
