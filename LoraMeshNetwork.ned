// =============================================================================
// LoraMeshNetwork — Self-Healing Hybrid LoRa Gateway Simülasyon Topolojisi
// =============================================================================
// Proje: Kendi Kendini İyileştiren Hibrit LoRa Gateway Mimarisi
//   Eren ERDEM (2020502028) — Melisa KURAL (2021502041)
//   DEU EEE — Danışman: Prof. Dr. Damla GURKAN KUNTALP
//
// KESİN TOPOLOJİ:
//
//   sensorGW1[0..4]  --[LoRa]--> hybridGW1 --[Eth]--> gwRouter1 --[Eth]--> networkServer
//   sensorGW2[0..3]  --[LoRa]--> hybridGW2 --[Eth]--> gwRouter1
//   sensorGW3[0..7]  --[LoRa]--> hybridGW3 --[Eth]--> gwRouter1
//
//   Mesh zinciri (sendDirect beacon, kablo YOK):
//     hybridGW1 <~beacon~> meshNode1 <~beacon~> meshNode2 <~beacon~> hybridGW2
//                          meshNode1 <~beacon~> meshNode3 <~beacon~> meshNode4 <~beacon~> hybridGW3
//
//   KURAL:
//     - GW <-> MeshNode: KESİNLİKLE kablo yok. Sadece sendDirect() beacon.
//     - Backhaul (GW->gwRouter1->networkServer) kablolu.
//     - Internet VARSA: GW sadece beacon gönderir, mesh'e sensör verisi yollamaz.
//     - Internet GİDERSE: GW mesajı alır, en iyi GW'yi hedef gösterir, mesh'e aktarır.
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

network LoraMeshNetwork
{
    parameters:
        @display("bgb=2200,2400");

    submodules:

        // ----- RF Ortam Motorları -----
        radioMedium: LoRaMedium {
            @display("p=60,50;i=misc/sun;is=s");
        }
        wlanMedium: Ieee80211ScalarRadioMedium {
            @display("p=220,50;i=misc/sun;is=s");
        }

        // ----- Sensör Grubu 1: hybridGW1'e bağlı 5 adet LoRaWAN sensör -----
        // [0] max kuzey 400m  [1] max KD ~440m  [2] orta KB ~220m  [3] min doğu ~60m  [4] min güney ~65m
        sensorGW1[5]: EndNode {
            @display("p=200,400");
        }

        // ----- Sensör Grubu 2: hybridGW2'ye bağlı 4 adet LoRaWAN sensör -----
        // [0] max doğu 400m  [1] max kuzey 400m  [2] orta KBat ~280m  [3] min ~70m
        sensorGW2[4]: EndNode {
            @display("p=1400,400");
        }

        // ----- Sensör Grubu 3: hybridGW3'e bağlı 8 adet LoRaWAN sensör -----
        // [0] max güney 400m  [1] max batı 400m  [2] max GB ~390m
        // [3] orta doğu ~206m  [4] orta KB ~241m  [7] orta KD ~270m
        // [5] min ~61m  [6] min ~64m
        sensorGW3[8]: EndNode {
            @display("p=600,1600");
        }

        // ----- Hibrit Gateway'ler (backhaul Ethernet'i var) -----
        // Yatay zincir: GW1(200,600)─400m─MN1(600,600)─400m─MN2(1000,600)─400m─GW2(1400,600)
        hybridGW1: HybridGateway {
            parameters:
                numEthInterfaces = 1;
                @display("p=200,600;i=device/accesspoint");
        }
        hybridGW2: HybridGateway {
            parameters:
                numEthInterfaces = 1;
                @display("p=1400,600;i=device/accesspoint");
        }
        // Düşey zincir: MN1(600,600)─400m─MN3(600,1000)─400m─MN4(600,1400)─400m─GW3(600,1800)
        hybridGW3: HybridGateway {
            parameters:
                numEthInterfaces = 1;
                @display("p=600,1800;i=device/accesspoint");
        }

        // ----- Mesh Düğümleri (KABLOSUZ SADECE - kablo bağlantısı yok) -----
        // meshNode1: yatay zincir (GW1↔MN2) ve düşey zincir (MN3) kavşak noktası
        // meshNode2: meshNode1 ↔ hybridGW2  (yatay, +400m)
        // meshNode3: meshNode1 ↔ meshNode4  (düşey, +400m)
        // meshNode4: meshNode3 ↔ hybridGW3  (düşey, +400m)
        meshNode1: MeshNode {
            parameters:
                @display("p=600,600");
        }
        meshNode2: MeshNode {
            parameters:
                @display("p=1000,600");
        }
        meshNode3: MeshNode {
            parameters:
                @display("p=600,1000");
        }
        meshNode4: MeshNode {
            parameters:
                @display("p=600,1400");
        }

        // ----- Ağ Altyapısı (kablolu omurga) -----
        gwRouter1: Router {
            @display("p=1700,600");
        }
        networkServer: NetworkServer {
            parameters:
                numEthInterfaces = 1;
                numApps = 1;
                @display("p=1900,600");
        }
        configurator: Ipv4NetworkConfigurator {
            parameters:
                assignDisjunctSubnetAddresses = true;
                @display("p=60,980;is=vs");
        }

    connections allowunconnected:

        // === BACKHAUL (Kablolu) ===
        // Her HybridGateway doğrudan gwRouter1'e bağlı
        hybridGW1.ethg++ <--> Eth1G <--> gwRouter1.ethg++;   // GW1 -> router eth[0]
        hybridGW2.ethg++ <--> Eth1G <--> gwRouter1.ethg++;   // GW2 -> router eth[1]
        hybridGW3.ethg++ <--> Eth1G <--> gwRouter1.ethg++;   // GW3 -> router eth[2]
        gwRouter1.ethg++ <--> Eth1G <--> networkServer.ethg++;  // router eth[3] -> server

        // === MeshNode'lar KABLOSUZ SADECE ===
        // meshNode1/2/3/4 sadece sendDirect() beacon ile haberleşir.
        // Fiziksel kablo bağlantısı YOK.
}
