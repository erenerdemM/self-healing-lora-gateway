// =============================================================================
// LoraMeshNetwork — Self-Healing Hybrid LoRa Gateway Simülasyon Topolojisi
// =============================================================================
// Proje: Kendi Kendini İyileştiren Hibrit LoRa Gateway Mimarisi
//   Eren ERDEM (2020502028) — Melisa KURAL (2021502041)
//   DEÜ EEE — Danışman: Prof. Dr. Damla GÜRKAN KUNTALP
//
// =============================================================================
// ELEMANLAR (PDF mimarisinden):
//   EndNode      : LoRaWAN IoT saha sensörü
//   HybridGateway: LoRaWAN + Meshtastic kapasiteli gateway (tüm GW'ler aynı tip)
//   MeshNode     : Meshtastic mesh relay düğümü (sadece G2G aktarma)
//   NetworkServer: Bulut / yerel LNS (ChirpStack)
//
// =============================================================================
// V1 Topolojisi — Temel Mimari Doğrulaması (ŞU AN AKTİF):
//
//   sensorNode1  --[LoRa, SF12]-->  hybridGW1  (internet YOK)
//                                       |
//                              [Mesh V1=Eth, 1Gbps]
//                                       |
//                                   meshNode1  (relay)
//                                       |
//                              [Mesh V1=Eth, 1Gbps]
//                                       |
//                                   hybridGW2  (internet VAR)
//                                       |
//                              [Ethernet WAN, 1Gbps]
//                                       |
//                                   networkServer  (LNS)
//
// Hedef: DER=1.0, packetDropNoRouteFound=0, LoRa_ServerPacketReceived=10
//
// =============================================================================
// V2 Topolojisi — Failover + Self-Healing:
//
//   NORMAL mod: hybridGW1 → [WAN] → networkServer (doğrudan)
//   FAILOVER mod (Rlink < τ): hybridGW1 → [Meshtastic G2G] → meshNode1
//                               → hybridGW2 → [WAN] → networkServer
//   SELF-HEALING: bağlantı geri gelince NORMAL moda dönüş
//   Yeni: meshtasticMedium + Failover Agent C++ state machine
//
// =============================================================================
// V3 Topolojisi — Çok Düğümlü Mesh Ağı:
//
//   N×EndNode → M×HybridGateway → [Meshtastic mesh] → networkServer
//   K×MeshNode (multi-hop relay zinciri), WRR + EWM yük dengeleme
//   Bottleneck senaryosu, QoS tag istatistikleri
// =============================================================================

import flora.LoRaPhy.LoRaMedium;
import inet.networklayer.configurator.ipv4.Ipv4NetworkConfigurator;
import inet.node.ethernet.Eth1G;
import inet.node.inet.Router;
import EndNode;
import HybridGateway;
import MeshNode;
import NetworkServer;

network LoraMeshNetwork
{
    parameters:
        @display("bgb=950,600");

    submodules:

        // ----- RF Ortam Motorları -----

        // LoRaWAN fiziksel ortam: EndNode ↔ HybridGateway arası (868MHz, SF12)
        // V2: meshtasticMedium eklenecek (HybridGateway ↔ MeshNode, ayrı frekans bandı)
        radioMedium: LoRaMedium {
            @display("p=50,50;i=misc/sun;is=s");
        }

        // ----- Ağ Elemanları -----

        // LoRaWAN IoT saha sensörü
        // Donanım: STM32L476RG + E77-900M — 11B payload, SF12, 14dBm
        sensorNode1: EndNode {
            @display("p=100,380");
        }

        // GW1: LoRaWAN birincil hibrit gateway — internet BAĞLANTISI YOK
        //   EndNode'dan LoRa paketi alır.
        //   V1: meshNode1 üzerinden hybridGW2'ye IP routing yapar.
        //   V2: Failover Agent devreye girer, Meshtastic G2G aktif.
        hybridGW1: HybridGateway {
            parameters:
                numEthInterfaces = 1;  // sadece mesh tarafı
                @display("p=300,220");
        }

        // Meshtastic relay düğümü
        //   V1: IP router (Ethernet bağlantılarıyla)
        //   V2: SX1262 LoRa radyo + MeshtasticMedium ile gerçek mesh relay
        meshNode1: MeshNode {
            parameters:
                numEthInterfaces = 2;  // [0]: hybridGW1, [1]: hybridGW2
                @display("p=500,220");
        }

        // GW2: İnternet BAĞLANTISI OLAN hibrit gateway
        //   V1: meshNode1'den gelen paketi networkServer'a yönlendirir.
        //   NOT: LoRaGW tabanlı modüllerde INET 4.4 EthernetEncapsulation,
        //        handleRegisterInterface zincirini lp-dispatcher'a iletmez.
        //        Bu nedenle V1'de hybridGW2 IP relay rolü için INET Router
        //        tabanlı gwRouter2 ile temsil edilir. HybridGateway rolü V2'de
        //        tam olarak aktive edilecek (LoRa RX + Meshtastic alıcı).
        //   V2: Meshtastic alıcı + LNS transmitter + QoS queue.
        gwRouter2: Router {
            @display("p=700,220");
        }

        // Bulut / yerel LNS — NetworkServerApp (FLoRa) çalıştırır
        //   V2: ChirpStack LNS simülatörü + duplicate detection
        networkServer: NetworkServer {
            parameters:
                numEthInterfaces = 1;
                numApps = 1;
                @display("p=870,220");
        }

        // ----- Altyapı -----

        // Otomatik IP adresleme + statik routing
        //   Her Ethernet linki ayrı /30 subnet alır.
        //   hybridGW1 → meshNode1 → hybridGW2 → networkServer route zinciri otomatik
        configurator: Ipv4NetworkConfigurator {
            parameters:
                assignDisjunctSubnetAddresses = true;
                @display("p=50,150;is=vs");
        }

    connections:

        // hybridGW1 → meshNode1  (Meshtastic G2G, V1'de Ethernet ile simüle)
        hybridGW1.ethg++ <--> Eth1G <--> meshNode1.ethg++;

        // meshNode1 → gwRouter2  (Meshtastic G2G, V1'de Ethernet ile simüle)
        // gwRouter2 = HybridGW2 IP rolü (INET Router, EthernetEncapsulation sorunu yok)
        meshNode1.ethg++ <--> Eth1G <--> gwRouter2.ethg++;

        // gwRouter2 → networkServer  (internet/WAN backhaul)
        gwRouter2.ethg++ <--> Eth1G <--> networkServer.ethg++;
}