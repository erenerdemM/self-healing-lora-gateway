// =============================================================================
// LoraMeshNetworkCity — Şehir Ölçekli (City-Scale) Kaotik Mesh Topolojisi
// =============================================================================
// Proje: Kendi Kendini İyileştiren Hibrit LoRa Gateway Mimarisi
//   Eren ERDEM (2020502028) — Melisa KURAL (2021502041)
//   DEU EEE — Danışman: Prof. Dr. Damla GURKAN KUNTALP
//
// TOPOLOJİ:
//   10 × HybridGateway (GW1..GW10)  —  Playground: 3200×3200 m
//   60 × MeshNode (MN1..MN60)       —  400m ızgara sürüsü (swarm)
//   50 × Sensor   (sensorGW1[5] .. sensorGW10[5])
//   1  × gwRouter1  + 1 × NetworkServer (kablolu omurga)
//
// KURAL:
//   - GW ↔ MeshNode: KESİNLİKLE kablo yok. Sadece sendDirect() beacon.
//   - Backhaul (GW → gwRouter1 → NS): kablolu Eth1G.
//   - İnternet VARSA:  GW sensör paketini UDP ile NS'e iletir.
//   - İnternet GİDERSE: GW paketi mesh'e aktarır (C_i metriği ile hedef seçer).
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

network LoraMeshNetworkCity
{
    parameters:
        @display("bgb=3350,3350;bgi=maps/terrain,s");

    submodules:

        // ----- RF Ortam Motorları -----
        radioMedium: LoRaMedium {
            @display("p=80,60;i=misc/sun;is=s");
        }
        wlanMedium: Ieee80211ScalarRadioMedium {
            @display("p=260,60;i=misc/sun;is=s");
        }

        // ──────────────────────────────────────────────────────────────────────
        // 50 ADET SENSOR — 10 grup × 5 sensör
        // ──────────────────────────────────────────────────────────────────────
        sensorGW1[5]:  EndNode { @display("p=400,300"); }
        sensorGW2[5]:  EndNode { @display("p=1100,200"); }
        sensorGW3[5]:  EndNode { @display("p=2000,350"); }
        sensorGW4[5]:  EndNode { @display("p=2700,700"); }
        sensorGW5[5]:  EndNode { @display("p=200,1400"); }
        sensorGW6[5]:  EndNode { @display("p=1000,1500"); }
        sensorGW7[5]:  EndNode { @display("p=1900,1300"); }
        sensorGW8[5]:  EndNode { @display("p=2700,1800"); }
        sensorGW9[5]:  EndNode { @display("p=600,2500"); }
        sensorGW10[5]: EndNode { @display("p=2100,2600"); }

        // ──────────────────────────────────────────────────────────────────────
        // 10 ADET HYBRİD GATEWAY — kablolu backhaul, LoRa alıcı, mesh agent
        // ──────────────────────────────────────────────────────────────────────
        hybridGW1: HybridGateway {
            parameters:
                numEthInterfaces = 1;
                @display("p=400,300;i=device/accesspoint");
        }
        hybridGW2: HybridGateway {
            parameters:
                numEthInterfaces = 1;
                @display("p=1100,200;i=device/accesspoint");
        }
        hybridGW3: HybridGateway {
            parameters:
                numEthInterfaces = 1;
                @display("p=2000,350;i=device/accesspoint");
        }
        hybridGW4: HybridGateway {
            parameters:
                numEthInterfaces = 1;
                @display("p=2700,700;i=device/accesspoint");
        }
        hybridGW5: HybridGateway {
            parameters:
                numEthInterfaces = 1;
                @display("p=200,1400;i=device/accesspoint");
        }
        hybridGW6: HybridGateway {
            parameters:
                numEthInterfaces = 1;
                @display("p=1000,1500;i=device/accesspoint");
        }
        hybridGW7: HybridGateway {
            parameters:
                numEthInterfaces = 1;
                @display("p=1900,1300;i=device/accesspoint");
        }
        hybridGW8: HybridGateway {
            parameters:
                numEthInterfaces = 1;
                @display("p=2700,1800;i=device/accesspoint");
        }
        hybridGW9: HybridGateway {
            parameters:
                numEthInterfaces = 1;
                @display("p=600,2500;i=device/accesspoint");
        }
        hybridGW10: HybridGateway {
            parameters:
                numEthInterfaces = 1;
                @display("p=2100,2600;i=device/accesspoint");
        }

        // ──────────────────────────────────────────────────────────────────────
        // 60 ADET MESH NODE — 8×8 ızgara, 400m aralık, sadece sendDirect beacon
        // Row 0 (y≈100): MN1-8   Row 1 (y≈500): MN9-16   Row 2 (y≈900): MN17-24
        // Row 3 (y≈1300): MN25-32  Row 4 (y≈1700): MN33-40  Row 5 (y≈2100): MN41-48
        // Row 6 (y≈2500): MN49-56  Row 7 (y≈2900): MN57-60 (yalnızca col 0-3)
        // ──────────────────────────────────────────────────────────────────────
        meshNode1:  MeshNode { parameters: @display("p=100,100"); }
        meshNode2:  MeshNode { parameters: @display("p=500,100"); }
        meshNode3:  MeshNode { parameters: @display("p=900,100"); }
        meshNode4:  MeshNode { parameters: @display("p=1300,100"); }
        meshNode5:  MeshNode { parameters: @display("p=1700,100"); }
        meshNode6:  MeshNode { parameters: @display("p=2100,100"); }
        meshNode7:  MeshNode { parameters: @display("p=2500,100"); }
        meshNode8:  MeshNode { parameters: @display("p=2900,100"); }
        meshNode9:  MeshNode { parameters: @display("p=100,500"); }
        meshNode10: MeshNode { parameters: @display("p=500,500"); }
        meshNode11: MeshNode { parameters: @display("p=900,500"); }
        meshNode12: MeshNode { parameters: @display("p=1300,500"); }
        meshNode13: MeshNode { parameters: @display("p=1700,500"); }
        meshNode14: MeshNode { parameters: @display("p=2100,500"); }
        meshNode15: MeshNode { parameters: @display("p=2500,500"); }
        meshNode16: MeshNode { parameters: @display("p=2900,500"); }
        meshNode17: MeshNode { parameters: @display("p=100,900"); }
        meshNode18: MeshNode { parameters: @display("p=500,900"); }
        meshNode19: MeshNode { parameters: @display("p=900,900"); }
        meshNode20: MeshNode { parameters: @display("p=1300,900"); }
        meshNode21: MeshNode { parameters: @display("p=1700,900"); }
        meshNode22: MeshNode { parameters: @display("p=2100,900"); }
        meshNode23: MeshNode { parameters: @display("p=2500,900"); }
        meshNode24: MeshNode { parameters: @display("p=2900,900"); }
        meshNode25: MeshNode { parameters: @display("p=100,1300"); }
        meshNode26: MeshNode { parameters: @display("p=500,1300"); }
        meshNode27: MeshNode { parameters: @display("p=900,1300"); }
        meshNode28: MeshNode { parameters: @display("p=1300,1300"); }
        meshNode29: MeshNode { parameters: @display("p=1700,1300"); }
        meshNode30: MeshNode { parameters: @display("p=2100,1300"); }
        meshNode31: MeshNode { parameters: @display("p=2500,1300"); }
        meshNode32: MeshNode { parameters: @display("p=2900,1300"); }
        meshNode33: MeshNode { parameters: @display("p=100,1700"); }
        meshNode34: MeshNode { parameters: @display("p=500,1700"); }
        meshNode35: MeshNode { parameters: @display("p=900,1700"); }
        meshNode36: MeshNode { parameters: @display("p=1300,1700"); }
        meshNode37: MeshNode { parameters: @display("p=1700,1700"); }
        meshNode38: MeshNode { parameters: @display("p=2100,1700"); }
        meshNode39: MeshNode { parameters: @display("p=2500,1700"); }
        meshNode40: MeshNode { parameters: @display("p=2900,1700"); }
        meshNode41: MeshNode { parameters: @display("p=100,2100"); }
        meshNode42: MeshNode { parameters: @display("p=500,2100"); }
        meshNode43: MeshNode { parameters: @display("p=900,2100"); }
        meshNode44: MeshNode { parameters: @display("p=1300,2100"); }
        meshNode45: MeshNode { parameters: @display("p=1700,2100"); }
        meshNode46: MeshNode { parameters: @display("p=2100,2100"); }
        meshNode47: MeshNode { parameters: @display("p=2500,2100"); }
        meshNode48: MeshNode { parameters: @display("p=2900,2100"); }
        meshNode49: MeshNode { parameters: @display("p=100,2500"); }
        meshNode50: MeshNode { parameters: @display("p=500,2500"); }
        meshNode51: MeshNode { parameters: @display("p=900,2500"); }
        meshNode52: MeshNode { parameters: @display("p=1300,2500"); }
        meshNode53: MeshNode { parameters: @display("p=1700,2500"); }
        meshNode54: MeshNode { parameters: @display("p=2100,2500"); }
        meshNode55: MeshNode { parameters: @display("p=2500,2500"); }
        meshNode56: MeshNode { parameters: @display("p=2900,2500"); }
        meshNode57: MeshNode { parameters: @display("p=100,2900"); }
        meshNode58: MeshNode { parameters: @display("p=500,2900"); }
        meshNode59: MeshNode { parameters: @display("p=900,2900"); }
        meshNode60: MeshNode { parameters: @display("p=1300,2900"); }

        // ──────────────────────────────────────────────────────────────────────
        // Ağ Altyapısı (kablolu omurga)
        // ──────────────────────────────────────────────────────────────────────
        gwRouter1: Router {
            @display("p=3100,1600");
        }
        networkServer: NetworkServer {
            parameters:
                numEthInterfaces = 1;
                numApps = 1;
                @display("p=3280,1600");
        }
        configurator: Ipv4NetworkConfigurator {
            parameters:
                assignDisjunctSubnetAddresses = true;
                @display("p=80,3200;is=vs");
        }

    connections allowunconnected:

        // === BACKHAUL (Kablolu) — 10 GW → gwRouter1 → NetworkServer ===
        hybridGW1.ethg++  <--> Eth1G <--> gwRouter1.ethg++;
        hybridGW2.ethg++  <--> Eth1G <--> gwRouter1.ethg++;
        hybridGW3.ethg++  <--> Eth1G <--> gwRouter1.ethg++;
        hybridGW4.ethg++  <--> Eth1G <--> gwRouter1.ethg++;
        hybridGW5.ethg++  <--> Eth1G <--> gwRouter1.ethg++;
        hybridGW6.ethg++  <--> Eth1G <--> gwRouter1.ethg++;
        hybridGW7.ethg++  <--> Eth1G <--> gwRouter1.ethg++;
        hybridGW8.ethg++  <--> Eth1G <--> gwRouter1.ethg++;
        hybridGW9.ethg++  <--> Eth1G <--> gwRouter1.ethg++;
        hybridGW10.ethg++ <--> Eth1G <--> gwRouter1.ethg++;
        gwRouter1.ethg++  <--> Eth1G <--> networkServer.ethg++;

        // === MeshNode'lar KABLOSUZ SADECE — fiziksel kablo YOK ===
        // Tüm GW ↔ MeshNode haberleşmesi sendDirect() beacon üzerinden gerçekleşir.
}
