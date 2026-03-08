// =============================================================================
// MultiNodeNetwork — Çok Düğümlü Performans ve Karar Doğrulama Topolojisi
// =============================================================================
// Config: [Config MultiNodeTest] in omnetpp.ini
//
// AMAÇ:
//   C_i maliyet algoritmasını, darboğaz koruma mekanizmasını ve CAD güç
//   durum makinesini çok düğümlü (4 sensör, 3 GW, 3 MeshNode) senaryoda
//   matematiksel olarak doğrula. Mock komşu enjeksiyonu ile sinyal tablolarını
//   manuel kontrol altında test et.
//
// TOPOLOJİ (Y şekli):
//
//   sensor1..4 ──[LoRa]──► hybridGW1 (backhaulUp=false, failover aktif)
//                                │[Eth]
//                           meshNode1  (2 eth, zincir başı)
//                                │[Eth]
//                           meshNode2  (3 eth, yıldız merkezi)
//                          ╱[Eth]         ╲[Eth]
//                    gwRouter1              meshNode3  (2 eth)
//                  (GW2 rolü,                   │[Eth]
//                   sabit int.)            gwRouter2
//                       │[Eth]           (GW3 rolü, "unstable")
//                  networkServer               │[Eth]
//                    (2 eth)  ◄─────────────────────
//
// NOT: hybridGW2/GW3 rolleri gwRouter1/gwRouter2 (INET Router) ile temsil
//      edilir. Bu V1 ile aynı mimari kısıt: LoRaGW'nin EthernetEncapsulation
//      modülü INET lp-dispatcher zincirini tam desteklemez (HybridGateway
//      bunu aşıyor ama sadece LoRa RX tarafında). İnternet-tarafı relay rolü
//      için INET Router en güvenli seçim.
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

network MultiNodeNetwork
{
    parameters:
        @display("bgb=1100,650");

    submodules:

        // ── RF Ortamları ──────────────────────────────────────────────────────

        // LoRaWAN fiziksel ortam: EndNode ↔ HybridGateway (868 MHz, SF12)
        radioMedium: LoRaMedium {
            @display("p=50,50;i=misc/sun;is=s");
        }

        // WLAN fiziksel ortam: MeshNode'ların IEEE 802.11 enerji tüketicisi için
        // (numWlanInterfaces=1 → StateBasedEpEnergyConsumer bu medium üzerinde çalışır)
        wlanMedium: Ieee80211ScalarRadioMedium {
            @display("p=180,50;i=misc/sun;is=s");
        }

        // ── Altyapı ───────────────────────────────────────────────────────────
        configurator: Ipv4NetworkConfigurator {
            parameters:
                assignDisjunctSubnetAddresses = true;
                @display("p=50,150;is=vs");
        }

        // ── 4× Sensör Düğümü ──────────────────────────────────────────────────
        // Staggered startTime: darboğaz ve interleaved paket akışı simüle eder.
        sensor1: EndNode {
            @display("p=80,330");
        }
        sensor2: EndNode {
            @display("p=140,410");
        }
        sensor3: EndNode {
            @display("p=80,480");
        }
        sensor4: EndNode {
            @display("p=170,290");
        }

        // ── HybridGateway ─────────────────────────────────────────────────────
        // hybridGW1: LoRaWAN alıcı + HybridRouting modülü
        //   backhaulUp=false → baştan failover modunda (mock timer ile dinamik)
        hybridGW1: HybridGateway {
            parameters:
                numEthInterfaces = 1;  // tek çıkış: meshNode1
                @display("p=310,390");
        }

        // ── 3× Mesh Röle Düğümü ───────────────────────────────────────────────
        // meshNode1: zincir girişi (hybridGW1 → meshNode2 köprüsü)
        meshNode1: MeshNode {
            parameters:
                numEthInterfaces = 2;  // [0]: hybridGW1, [1]: meshNode2
                @display("p=460,390");
        }

        // meshNode2: yıldız merkezi (3 çıkış: meshNode1, gwRouter1, meshNode3)
        meshNode2: MeshNode {
            parameters:
                numEthInterfaces = 3;
                @display("p=610,280");
        }

        // meshNode3: alt kol (meshNode2 → gwRouter2 köprüsü)
        meshNode3: MeshNode {
            parameters:
                numEthInterfaces = 2;  // [0]: meshNode2, [1]: gwRouter2
                @display("p=610,510");
        }

        // ── İnternet Gateway Röleleri (Router tabanlı) ────────────────────────
        // gwRouter1: GW2 rolü — sabit internet (stable backhaul)
        gwRouter1: Router {
            @display("p=760,200");
        }

        // gwRouter2: GW3 rolü — "unstable" internet
        //   (Gerçek hayatta: zayıf 4G sinyali veya intermittent fiber)
        gwRouter2: Router {
            @display("p=760,510");
        }

        // ── NetworkServer ──────────────────────────────────────────────────────
        // numEthInterfaces=2: gwRouter1 + gwRouter2'den ayrı portlar
        networkServer: NetworkServer {
            parameters:
                numEthInterfaces = 2;
                numApps = 1;
                @display("p=920,355");
        }

    connections allowunconnected:

        // ── Zincir: hybridGW1 → meshNode1 → meshNode2 ─────────────────────────
        hybridGW1.ethg++ <--> Eth1G <--> meshNode1.ethg++;
        meshNode1.ethg++ <--> Eth1G <--> meshNode2.ethg++;

        // ── Kol A: meshNode2 → gwRouter1 → networkServer ──────────────────────
        meshNode2.ethg++ <--> Eth1G <--> gwRouter1.ethg++;
        gwRouter1.ethg++ <--> Eth1G <--> networkServer.ethg++;

        // ── Kol B: meshNode2 → meshNode3 → gwRouter2 → networkServer ──────────
        meshNode2.ethg++ <--> Eth1G <--> meshNode3.ethg++;
        meshNode3.ethg++ <--> Eth1G <--> gwRouter2.ethg++;
        gwRouter2.ethg++ <--> Eth1G <--> networkServer.ethg++;
}
