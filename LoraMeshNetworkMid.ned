// =============================================================================
// LoraMeshNetworkMid  —  Orta-Metropol Ölçekli LoRa Mesh Topolojisi (5000×5000 m)
// =============================================================================
// 10 × HybridGateway   |  60 × MeshNode   |  50 × EndNode (5×10 grup)
// Alan: 5000 × 5000 m  |  Mesh menzil: 900 m  |  LoRa menzil: 1500 m
// Kablo YOK (allowunconnected)  —  Backhaul: GW → gwRouter1 → NetworkServer
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

network LoraMeshNetworkMid
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
            @display("p=480,60;i=block/cogwheel;is=s");
        }

        // ── Sensörler ──────────────────────────────────────────────
        sensorGW1[5]: EndNode { @display("p=625,469"); }
        sensorGW2[5]: EndNode { @display("p=1719,313"); }
        sensorGW3[5]: EndNode { @display("p=3125,547"); }
        sensorGW4[5]: EndNode { @display("p=4219,1094"); }
        sensorGW5[5]: EndNode { @display("p=313,2188"); }
        sensorGW6[5]: EndNode { @display("p=1563,2344"); }
        sensorGW7[5]: EndNode { @display("p=2969,2031"); }
        sensorGW8[5]: EndNode { @display("p=4219,2813"); }
        sensorGW9[5]: EndNode { @display("p=938,3906"); }
        sensorGW10[5]: EndNode { @display("p=3281,4063"); }

        // ── HybridGateway'ler (kablolu backhaul, LoRa alıcı, mesh) ──
        hybridGW1: HybridGateway {
            parameters:
                numEthInterfaces = 1;
                @display("p=625,469;i=device/accesspoint");
        }
        hybridGW2: HybridGateway {
            parameters:
                numEthInterfaces = 1;
                @display("p=1719,313;i=device/accesspoint");
        }
        hybridGW3: HybridGateway {
            parameters:
                numEthInterfaces = 1;
                @display("p=3125,547;i=device/accesspoint");
        }
        hybridGW4: HybridGateway {
            parameters:
                numEthInterfaces = 1;
                @display("p=4219,1094;i=device/accesspoint");
        }
        hybridGW5: HybridGateway {
            parameters:
                numEthInterfaces = 1;
                @display("p=313,2188;i=device/accesspoint");
        }
        hybridGW6: HybridGateway {
            parameters:
                numEthInterfaces = 1;
                @display("p=1563,2344;i=device/accesspoint");
        }
        hybridGW7: HybridGateway {
            parameters:
                numEthInterfaces = 1;
                @display("p=2969,2031;i=device/accesspoint");
        }
        hybridGW8: HybridGateway {
            parameters:
                numEthInterfaces = 1;
                @display("p=4219,2813;i=device/accesspoint");
        }
        hybridGW9: HybridGateway {
            parameters:
                numEthInterfaces = 1;
                @display("p=938,3906;i=device/accesspoint");
        }
        hybridGW10: HybridGateway {
            parameters:
                numEthInterfaces = 1;
                @display("p=3281,4063;i=device/accesspoint");
        }

        gwRouter1: Router {
            parameters:
                numEthInterfaces = 11;
                @display("p=2600,5100;i=abstract/router");
        }
        networkServer: NetworkServer {
            @display("p=2600,5050;i=device/server");
        }

        // ── MeshNode'lar (10×6 grid, 500m/800m aralık) ────────────
        meshNode1: MeshNode { @display("p=250,400;i=device/wifilaptop;is=s"); }
        meshNode2: MeshNode { @display("p=750,400;i=device/wifilaptop;is=s"); }
        meshNode3: MeshNode { @display("p=1250,400;i=device/wifilaptop;is=s"); }
        meshNode4: MeshNode { @display("p=1750,400;i=device/wifilaptop;is=s"); }
        meshNode5: MeshNode { @display("p=2250,400;i=device/wifilaptop;is=s"); }
        meshNode6: MeshNode { @display("p=2750,400;i=device/wifilaptop;is=s"); }
        meshNode7: MeshNode { @display("p=3250,400;i=device/wifilaptop;is=s"); }
        meshNode8: MeshNode { @display("p=3750,400;i=device/wifilaptop;is=s"); }
        meshNode9: MeshNode { @display("p=4250,400;i=device/wifilaptop;is=s"); }
        meshNode10: MeshNode { @display("p=4750,400;i=device/wifilaptop;is=s"); }
        meshNode11: MeshNode { @display("p=250,1200;i=device/wifilaptop;is=s"); }
        meshNode12: MeshNode { @display("p=750,1200;i=device/wifilaptop;is=s"); }
        meshNode13: MeshNode { @display("p=1250,1200;i=device/wifilaptop;is=s"); }
        meshNode14: MeshNode { @display("p=1750,1200;i=device/wifilaptop;is=s"); }
        meshNode15: MeshNode { @display("p=2250,1200;i=device/wifilaptop;is=s"); }
        meshNode16: MeshNode { @display("p=2750,1200;i=device/wifilaptop;is=s"); }
        meshNode17: MeshNode { @display("p=3250,1200;i=device/wifilaptop;is=s"); }
        meshNode18: MeshNode { @display("p=3750,1200;i=device/wifilaptop;is=s"); }
        meshNode19: MeshNode { @display("p=4250,1200;i=device/wifilaptop;is=s"); }
        meshNode20: MeshNode { @display("p=4750,1200;i=device/wifilaptop;is=s"); }
        meshNode21: MeshNode { @display("p=250,2000;i=device/wifilaptop;is=s"); }
        meshNode22: MeshNode { @display("p=750,2000;i=device/wifilaptop;is=s"); }
        meshNode23: MeshNode { @display("p=1250,2000;i=device/wifilaptop;is=s"); }
        meshNode24: MeshNode { @display("p=1750,2000;i=device/wifilaptop;is=s"); }
        meshNode25: MeshNode { @display("p=2250,2000;i=device/wifilaptop;is=s"); }
        meshNode26: MeshNode { @display("p=2750,2000;i=device/wifilaptop;is=s"); }
        meshNode27: MeshNode { @display("p=3250,2000;i=device/wifilaptop;is=s"); }
        meshNode28: MeshNode { @display("p=3750,2000;i=device/wifilaptop;is=s"); }
        meshNode29: MeshNode { @display("p=4250,2000;i=device/wifilaptop;is=s"); }
        meshNode30: MeshNode { @display("p=4750,2000;i=device/wifilaptop;is=s"); }
        meshNode31: MeshNode { @display("p=250,2800;i=device/wifilaptop;is=s"); }
        meshNode32: MeshNode { @display("p=750,2800;i=device/wifilaptop;is=s"); }
        meshNode33: MeshNode { @display("p=1250,2800;i=device/wifilaptop;is=s"); }
        meshNode34: MeshNode { @display("p=1750,2800;i=device/wifilaptop;is=s"); }
        meshNode35: MeshNode { @display("p=2250,2800;i=device/wifilaptop;is=s"); }
        meshNode36: MeshNode { @display("p=2750,2800;i=device/wifilaptop;is=s"); }
        meshNode37: MeshNode { @display("p=3250,2800;i=device/wifilaptop;is=s"); }
        meshNode38: MeshNode { @display("p=3750,2800;i=device/wifilaptop;is=s"); }
        meshNode39: MeshNode { @display("p=4250,2800;i=device/wifilaptop;is=s"); }
        meshNode40: MeshNode { @display("p=4750,2800;i=device/wifilaptop;is=s"); }
        meshNode41: MeshNode { @display("p=250,3600;i=device/wifilaptop;is=s"); }
        meshNode42: MeshNode { @display("p=750,3600;i=device/wifilaptop;is=s"); }
        meshNode43: MeshNode { @display("p=1250,3600;i=device/wifilaptop;is=s"); }
        meshNode44: MeshNode { @display("p=1750,3600;i=device/wifilaptop;is=s"); }
        meshNode45: MeshNode { @display("p=2250,3600;i=device/wifilaptop;is=s"); }
        meshNode46: MeshNode { @display("p=2750,3600;i=device/wifilaptop;is=s"); }
        meshNode47: MeshNode { @display("p=3250,3600;i=device/wifilaptop;is=s"); }
        meshNode48: MeshNode { @display("p=3750,3600;i=device/wifilaptop;is=s"); }
        meshNode49: MeshNode { @display("p=4250,3600;i=device/wifilaptop;is=s"); }
        meshNode50: MeshNode { @display("p=4750,3600;i=device/wifilaptop;is=s"); }
        meshNode51: MeshNode { @display("p=250,4400;i=device/wifilaptop;is=s"); }
        meshNode52: MeshNode { @display("p=750,4400;i=device/wifilaptop;is=s"); }
        meshNode53: MeshNode { @display("p=1250,4400;i=device/wifilaptop;is=s"); }
        meshNode54: MeshNode { @display("p=1750,4400;i=device/wifilaptop;is=s"); }
        meshNode55: MeshNode { @display("p=2250,4400;i=device/wifilaptop;is=s"); }
        meshNode56: MeshNode { @display("p=2750,4400;i=device/wifilaptop;is=s"); }
        meshNode57: MeshNode { @display("p=3250,4400;i=device/wifilaptop;is=s"); }
        meshNode58: MeshNode { @display("p=3750,4400;i=device/wifilaptop;is=s"); }
        meshNode59: MeshNode { @display("p=4250,4400;i=device/wifilaptop;is=s"); }
        meshNode60: MeshNode { @display("p=4750,4400;i=device/wifilaptop;is=s"); }

    connections allowunconnected:
        // ── GW → Router kablolu backhaul ──────────────────────────
        hybridGW1.ethg++ <--> Eth1G <--> gwRouter1.ethg++;
        hybridGW2.ethg++ <--> Eth1G <--> gwRouter1.ethg++;
        hybridGW3.ethg++ <--> Eth1G <--> gwRouter1.ethg++;
        hybridGW4.ethg++ <--> Eth1G <--> gwRouter1.ethg++;
        hybridGW5.ethg++ <--> Eth1G <--> gwRouter1.ethg++;
        hybridGW6.ethg++ <--> Eth1G <--> gwRouter1.ethg++;
        hybridGW7.ethg++ <--> Eth1G <--> gwRouter1.ethg++;
        hybridGW8.ethg++ <--> Eth1G <--> gwRouter1.ethg++;
        hybridGW9.ethg++ <--> Eth1G <--> gwRouter1.ethg++;
        hybridGW10.ethg++ <--> Eth1G <--> gwRouter1.ethg++;
        // ── Router → NetworkServer ────────────────────────────────
        gwRouter1.ethg++ <--> Eth1G <--> networkServer.ethg++;
}