// =============================================================================
// LoraMeshNetworkArazi1  —  Arazi Sahası 1: Hava Koşulları ve Darboğaz Testi
// =============================================================================
// Proje : Kendi Kendini İyileştiren Hibrit LoRa Gateway Mimarisi
//   Eren ERDEM (2020502028) — Melisa KURAL (2021502041)
//   DEÜ EEE — Danışman: Prof. Dr. Damla GÜRKAN KUNTALP
//
//  AMAÇ: GW1 backhaul kesintisinde 5 MeshNode zincirinin veriyi GW2'ye
//        ulaştırmasını kanıtlamak. weatherSigma parametrik çalıştırılır.
//
//  TOPOLOJİ — Lineer Zincir (doğu-batı 30 km):
//
//    GW1          MN0   S0   MN1   S1   MN2   S2   MN3   S3   MN4   S4   GW2
//    x=0         6km        12km      18km       24km       27km       30km
//
//    HybridGateway  ←—— 5 MeshNode zinciri ——→  HybridGateway
//       ↕                                            ↕
//    gwRouter1                                   gwRouter2
//       ↕                                            ↕
//    networkServer1                             networkServer2
//
//  SENARYO:
//    t=0   : GW1 ve GW2 internete bağlı (SENARYO A — direct forwarding)
//    t=30s : GW1 backhaul KESİLİR (SENARYO B)
//    t=30s~: GW1 veriyi MeshNode zincirine iter → MN zinciri → GW2 → NS2
//
//  SF / MENZIL HESABI (BW=125kHz, TX=14dBm, sensitivity=-141dBm @ SF12):
//    SF12 d_max ≈ 35km (MeshNode'lar arası 6km → tüm hop'lar kapsama içinde)
//    Sensörler aynı subgrid'deki MeshNode'a ~3km mesafede (daima kapsama içinde)
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

network LoraMeshNetworkArazi1
{
    parameters:
        @display("bgb=35000,4000;bgi=maps/terrain,s");

    submodules:

        // ── RF Ortam Motorları ─────────────────────────────────────────────
        radioMedium: LoRaMedium {
            @display("p=500,300;i=misc/sun;is=s");
        }
        wlanMedium: Ieee80211ScalarRadioMedium {
            @display("p=1500,300;i=misc/sun;is=s");
        }

        // ── IP Yapılandırıcı ───────────────────────────────────────────────
        configurator: Ipv4NetworkConfigurator {
            parameters:
                assignDisjunctSubnetAddresses = true;
                @display("p=2500,300;is=vs");
        }

        // ── GW1 — Batı uç (x=0m) — t=30s'de backhaul kesiliyor ────────────
        hybridGW1: HybridGateway {
            parameters:
                numEthInterfaces = 1;
                @display("p=500,2000;i=device/accesspoint");
        }

        // ── 5 MeshNode — lineer zincir, 6km aralıklı ──────────────────────
        // meshNode[0]: x=6000m
        // meshNode[1]: x=12000m
        // meshNode[2]: x=18000m
        // meshNode[3]: x=24000m
        // meshNode[4]: x=27000m
        meshNode[5]: MeshNode {
            parameters:
                @display("p=4000,2000");
        }

        // ── 5 Sensör — her MeshNode aralığının ortasına yakın ─────────────
        // sensor[0]: x=3000m  (GW1 ile MN0 arası)
        // sensor[1]: x=9000m  (MN0 ile MN1 arası)
        // sensor[2]: x=15000m (MN1 ile MN2 arası)
        // sensor[3]: x=21000m (MN2 ile MN3 arası)
        // sensor[4]: x=25500m (MN3 ile MN4 arası)
        sensor[5]: EndNode {
            @display("p=2500,3000");
        }

        // ── GW2 — Doğu uç (x=30000m) — internete daima bağlı ─────────────
        hybridGW2: HybridGateway {
            parameters:
                numEthInterfaces = 1;
                @display("p=30500,2000;i=device/accesspoint");
        }

        // ── Kablolu Altyapı — GW1 tarafı ──────────────────────────────────
        gwRouter1: Router {
            @display("p=200,2000");
        }
        networkServer1: NetworkServer {
            parameters:
                numEthInterfaces = 1;
                numApps = 1;
                @display("p=100,2000");
        }

        // ── Kablolu Altyapı — GW2 tarafı ──────────────────────────────────
        gwRouter2: Router {
            @display("p=31000,2000");
        }
        networkServer2: NetworkServer {
            parameters:
                numEthInterfaces = 1;
                numApps = 1;
                @display("p=31500,2000");
        }

    connections allowunconnected:
        hybridGW1.ethg++ <--> Eth1G <--> gwRouter1.ethg++;
        gwRouter1.ethg++ <--> Eth1G <--> networkServer1.ethg++;

        hybridGW2.ethg++ <--> Eth1G <--> gwRouter2.ethg++;
        gwRouter2.ethg++ <--> Eth1G <--> networkServer2.ethg++;
}
