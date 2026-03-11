// =============================================================================
// LoraMeshNetworkUrban25km  —  Kentsel 25 km² LoRa Mesh Topolojisi
// =============================================================================
// Alan   : 5000 × 5000 m  (25 km²)
// Donanım: 4 × HybridGateway  |  8 × MeshNode  |  20 × SensorNode (4×5)
// RF     : SF10 / BW125kHz / EU868  |  γ=4.0 (kentsel), σ=6.0 dB
//
// Link Budget (SF10/14dBm/−133dBm):
//   PL_max = 149 dB,  σ=6dB margin → pratik menzil ≈ 2.45 km
//   4 GW quadrant merkezi: (1250,1250) (3750,1250) (1250,3750) (3750,3750)
//   Max sensör → GW uzaklığı = √(1250²+1250²) = 1768 m < 2450 m  ✓
//
// ETSI EN 300 220-2 §5.4, DC < 1%:
//   ToA(SF10/125/20B) = 0.43s,  sendInterval=exp(300s)
//   DC = 0.43/300 = 0.14%  ✓
//
// CAD (SX1262 SF10, CadSymbolNum=2):
//   cadDuration = 16ms,  cadInterval = 40ms
//   P_avg = (16/56)×10mA×3.7V + (40/56)×15µA×3.7V = 10.6 mW
//   Pil ömrü: 46620J / 0.01057W ≈ 51 gün  → güneş paneli gerekli  ✓
// =============================================================================

import flora.LoRaPhy.LoRaMedium;
import inet.environment.common.PhysicalEnvironment;
import inet.networklayer.configurator.ipv4.Ipv4NetworkConfigurator;
import inet.node.ethernet.Eth1G;
import inet.node.inet.Router;
import inet.physicallayer.wireless.ieee80211.packetlevel.Ieee80211ScalarRadioMedium;
import EndNode;
import HybridGateway;
import MeshNode;
import NetworkServer;

network LoraMeshNetworkUrban25km
{
    parameters:
        @display("bgb=5200,5200;bgi=maps/terrain,s");

    submodules:
        radioMedium: LoRaMedium {
            @display("p=80,60;i=misc/sun;is=s");
        }
        wlanMedium: Ieee80211ScalarRadioMedium {
            @display("p=280,60;i=misc/sun;is=s");
        }
        configurator: Ipv4NetworkConfigurator {
            config = xmldoc("network-config-urban25km.xml");
            @display("p=480,60;i=block/cogwheel;is=s");
        }
        physicalEnvironment: PhysicalEnvironment {
            @display("p=680,60;i=misc/city;is=s");
        }

        // ── Sensörler — 5 sensör × 4 GW bölgesi = 20 sensör ───────────────
        // Bölge 1 (GW1 çevresi, SW quadrant)
        sensorGW1[5]: EndNode { @display("p=900,900"); }
        // Bölge 2 (GW2 çevresi, SE quadrant)
        sensorGW2[5]: EndNode { @display("p=3400,900"); }
        // Bölge 3 (GW3 çevresi, NW quadrant)
        sensorGW3[5]: EndNode { @display("p=900,3400"); }
        // Bölge 4 (GW4 çevresi, NE quadrant)
        sensorGW4[5]: EndNode { @display("p=3400,3400"); }

        // ── HybridGateway — quadrant merkezleri ───────────────────────────
        // Link budget: max PL=143dB → menzil 2.45km; yarıçap 1768m < 2450m ✓
        hybridGW1: HybridGateway {
            parameters:
                numEthInterfaces = 1;
                @display("p=1250,1250;i=device/accesspoint");
        }
        hybridGW2: HybridGateway {
            parameters:
                numEthInterfaces = 1;
                @display("p=3750,1250;i=device/accesspoint");
        }
        hybridGW3: HybridGateway {
            parameters:
                numEthInterfaces = 1;
                @display("p=1250,3750;i=device/accesspoint");
        }
        hybridGW4: HybridGateway {
            parameters:
                numEthInterfaces = 1;
                @display("p=3750,3750;i=device/accesspoint");
        }

        gwRouter1: Router {
            parameters:
                numEthInterfaces = 5;   // eth0-3: 4 GW, eth4: NetworkServer
                @display("p=2600,5100;i=abstract/router");
        }
        networkServer: NetworkServer {
            @display("p=2600,5050;i=device/server");
        }

        // ── MeshNode'lar — kenar köprüler + GW-arası röleler ─────────────
        // Kenar köprüler (kör noktaları eliminate eder):
        //   N1 (kuzey): (2500,200)   N2 (batı): (200,2500)
        //   N3 (doğu): (4800,2500)   N4 (güney): (2500,4800)
        // GW-arası röleler (4 GW arasındaki zincirler):
        //   N5 (GW1-GW3 dikey): (1250,2500)   N6 (GW1-GW2 yatay): (2500,1250)
        //   N7 (GW2-GW4 dikey): (3750,2500)   N8 (GW3-GW4 yatay): (2500,3750)
        meshNode1: MeshNode { @display("p=2500,200;i=device/wifilaptop;is=s"); }
        meshNode2: MeshNode { @display("p=200,2500;i=device/wifilaptop;is=s"); }
        meshNode3: MeshNode { @display("p=4800,2500;i=device/wifilaptop;is=s"); }
        meshNode4: MeshNode { @display("p=2500,4800;i=device/wifilaptop;is=s"); }
        meshNode5: MeshNode { @display("p=1250,2500;i=device/wifilaptop;is=s"); }
        meshNode6: MeshNode { @display("p=2500,1250;i=device/wifilaptop;is=s"); }
        meshNode7: MeshNode { @display("p=3750,2500;i=device/wifilaptop;is=s"); }
        meshNode8: MeshNode { @display("p=2500,3750;i=device/wifilaptop;is=s"); }

    connections allowunconnected:
        // ── GW → Router kablolu backhaul (7/24 fiber senkron) ─────────────
        hybridGW1.ethg++ <--> Eth1G <--> gwRouter1.ethg++;
        hybridGW2.ethg++ <--> Eth1G <--> gwRouter1.ethg++;
        hybridGW3.ethg++ <--> Eth1G <--> gwRouter1.ethg++;
        hybridGW4.ethg++ <--> Eth1G <--> gwRouter1.ethg++;
        // ── Router → NetworkServer ─────────────────────────────────────────
        gwRouter1.ethg++ <--> Eth1G <--> networkServer.ethg++;
}
