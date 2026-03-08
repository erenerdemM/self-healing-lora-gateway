// =============================================================================
// LoraMeshNetworkMetro — Metropol Ölçekli Kaotik Mesh Topolojisi
// =============================================================================
// 5000×5000 m  |  20 HybridGW  |  150 MeshNode  |  100 LoRa Sensör
// Kural: Fiziksel Ethernet YOLU YOK. Tüm mesh haberleşmesi sendDirect()
//        ile (beacon tabanlı komşu tablosu). NetworkServer yalnızca IP
//        çözümlemesi için NED'de bulunur; UDP ulaşımı beklenmez.
// =============================================================================

import flora.LoRaPhy.LoRaMedium;
import inet.networklayer.configurator.ipv4.Ipv4NetworkConfigurator;
import inet.physicallayer.wireless.ieee80211.packetlevel.Ieee80211ScalarRadioMedium;
import EndNode;
import HybridGateway;
import MeshNode;
import NetworkServer;

network LoraMeshNetworkMetro
{
    parameters:
        @display("bgb=5100,5100;bgi=maps/terrain,s");

    submodules:

        // ── RF Ortamlar ───────────────────────────────────────────────────────
        radioMedium: LoRaMedium {
            @display("p=80,60;i=misc/sun;is=s");
        }
        wlanMedium: Ieee80211ScalarRadioMedium {
            @display("p=260,60;i=misc/sun;is=s");
        }
        configurator: Ipv4NetworkConfigurator {
            @display("p=80,180;i=block/cogwheel;is=s");
        }
        // NetworkServer: IP çözümlemesi için (Ethernet bağlantısı yok — sadece stub)
        networkServer: NetworkServer {
            @display("p=2550,2550;i=device/server;is=l");
        }

        // ── 20 Hibrit Gateway ────────────────────────────────────────────────
        hybridGW1: HybridGateway { @display("p=300,280;i=device/antennatower;is=n"); }
        hybridGW2: HybridGateway { @display("p=1100,350;i=device/antennatower;is=n"); }
        hybridGW3: HybridGateway { @display("p=2100,280;i=device/antennatower;is=n"); }
        hybridGW4: HybridGateway { @display("p=3000,350;i=device/antennatower;is=n"); }
        hybridGW5: HybridGateway { @display("p=4100,280;i=device/antennatower;is=n"); }
        hybridGW6: HybridGateway { @display("p=280,1450;i=device/antennatower;is=n"); }
        hybridGW7: HybridGateway { @display("p=1200,1600;i=device/antennatower;is=n"); }
        hybridGW8: HybridGateway { @display("p=2200,1400;i=device/antennatower;is=n"); }
        hybridGW9: HybridGateway { @display("p=3100,1600;i=device/antennatower;is=n"); }
        hybridGW10: HybridGateway { @display("p=4200,1450;i=device/antennatower;is=n"); }
        hybridGW11: HybridGateway { @display("p=350,2650;i=device/antennatower;is=n"); }
        hybridGW12: HybridGateway { @display("p=1300,2800;i=device/antennatower;is=n"); }
        hybridGW13: HybridGateway { @display("p=2300,2650;i=device/antennatower;is=n"); }
        hybridGW14: HybridGateway { @display("p=3200,2800;i=device/antennatower;is=n"); }
        hybridGW15: HybridGateway { @display("p=4300,2650;i=device/antennatower;is=n"); }
        hybridGW16: HybridGateway { @display("p=250,3900;i=device/antennatower;is=n"); }
        hybridGW17: HybridGateway { @display("p=1400,4100;i=device/antennatower;is=n"); }
        hybridGW18: HybridGateway { @display("p=2400,3800;i=device/antennatower;is=n"); }
        hybridGW19: HybridGateway { @display("p=3300,4100;i=device/antennatower;is=n"); }
        hybridGW20: HybridGateway { @display("p=4400,3900;i=device/antennatower;is=n"); }

        // ── 150 Mesh Röle Düğümü ──────────────────────────────────────────────
        meshNode1: MeshNode { @display("p=81,109;i=device/accesspoint;is=s"); }
        meshNode2: MeshNode { @display("p=411,127;i=device/accesspoint;is=s"); }
        meshNode3: MeshNode { @display("p=759,88;i=device/accesspoint;is=s"); }
        meshNode4: MeshNode { @display("p=1054,123;i=device/accesspoint;is=s"); }
        meshNode5: MeshNode { @display("p=1443,146;i=device/accesspoint;is=s"); }
        meshNode6: MeshNode { @display("p=1742,118;i=device/accesspoint;is=s"); }
        meshNode7: MeshNode { @display("p=2031,95;i=device/accesspoint;is=s"); }
        meshNode8: MeshNode { @display("p=2367,118;i=device/accesspoint;is=s"); }
        meshNode9: MeshNode { @display("p=2746,117;i=device/accesspoint;is=s"); }
        meshNode10: MeshNode { @display("p=3089,106;i=device/accesspoint;is=s"); }
        meshNode11: MeshNode { @display("p=3345,80;i=device/accesspoint;is=s"); }
        meshNode12: MeshNode { @display("p=3705,86;i=device/accesspoint;is=s"); }
        meshNode13: MeshNode { @display("p=4051,123;i=device/accesspoint;is=s"); }
        meshNode14: MeshNode { @display("p=4308,80;i=device/accesspoint;is=s"); }
        meshNode15: MeshNode { @display("p=4665,132;i=device/accesspoint;is=s"); }
        meshNode16: MeshNode { @display("p=88,555;i=device/accesspoint;is=s"); }
        meshNode17: MeshNode { @display("p=411,635;i=device/accesspoint;is=s"); }
        meshNode18: MeshNode { @display("p=743,566;i=device/accesspoint;is=s"); }
        meshNode19: MeshNode { @display("p=1052,587;i=device/accesspoint;is=s"); }
        meshNode20: MeshNode { @display("p=1430,623;i=device/accesspoint;is=s"); }
        meshNode21: MeshNode { @display("p=1761,583;i=device/accesspoint;is=s"); }
        meshNode22: MeshNode { @display("p=2085,554;i=device/accesspoint;is=s"); }
        meshNode23: MeshNode { @display("p=2389,593;i=device/accesspoint;is=s"); }
        meshNode24: MeshNode { @display("p=2741,611;i=device/accesspoint;is=s"); }
        meshNode25: MeshNode { @display("p=3026,627;i=device/accesspoint;is=s"); }
        meshNode26: MeshNode { @display("p=3406,617;i=device/accesspoint;is=s"); }
        meshNode27: MeshNode { @display("p=3722,590;i=device/accesspoint;is=s"); }
        meshNode28: MeshNode { @display("p=3976,600;i=device/accesspoint;is=s"); }
        meshNode29: MeshNode { @display("p=4382,615;i=device/accesspoint;is=s"); }
        meshNode30: MeshNode { @display("p=4680,637;i=device/accesspoint;is=s"); }
        meshNode31: MeshNode { @display("p=143,1106;i=device/accesspoint;is=s"); }
        meshNode32: MeshNode { @display("p=485,1101;i=device/accesspoint;is=s"); }
        meshNode33: MeshNode { @display("p=787,1091;i=device/accesspoint;is=s"); }
        meshNode34: MeshNode { @display("p=1135,1078;i=device/accesspoint;is=s"); }
        meshNode35: MeshNode { @display("p=1422,1090;i=device/accesspoint;is=s"); }
        meshNode36: MeshNode { @display("p=1704,1107;i=device/accesspoint;is=s"); }
        meshNode37: MeshNode { @display("p=2048,1035;i=device/accesspoint;is=s"); }
        meshNode38: MeshNode { @display("p=2412,1109;i=device/accesspoint;is=s"); }
        meshNode39: MeshNode { @display("p=2708,1046;i=device/accesspoint;is=s"); }
        meshNode40: MeshNode { @display("p=3042,1068;i=device/accesspoint;is=s"); }
        meshNode41: MeshNode { @display("p=3395,1075;i=device/accesspoint;is=s"); }
        meshNode42: MeshNode { @display("p=3659,1083;i=device/accesspoint;is=s"); }
        meshNode43: MeshNode { @display("p=4024,1098;i=device/accesspoint;is=s"); }
        meshNode44: MeshNode { @display("p=4343,1027;i=device/accesspoint;is=s"); }
        meshNode45: MeshNode { @display("p=4649,1100;i=device/accesspoint;is=s"); }
        meshNode46: MeshNode { @display("p=86,1580;i=device/accesspoint;is=s"); }
        meshNode47: MeshNode { @display("p=446,1501;i=device/accesspoint;is=s"); }
        meshNode48: MeshNode { @display("p=770,1529;i=device/accesspoint;is=s"); }
        meshNode49: MeshNode { @display("p=1101,1568;i=device/accesspoint;is=s"); }
        meshNode50: MeshNode { @display("p=1439,1507;i=device/accesspoint;is=s"); }
        meshNode51: MeshNode { @display("p=1781,1536;i=device/accesspoint;is=s"); }
        meshNode52: MeshNode { @display("p=2088,1580;i=device/accesspoint;is=s"); }
        meshNode53: MeshNode { @display("p=2379,1569;i=device/accesspoint;is=s"); }
        meshNode54: MeshNode { @display("p=2736,1522;i=device/accesspoint;is=s"); }
        meshNode55: MeshNode { @display("p=3019,1568;i=device/accesspoint;is=s"); }
        meshNode56: MeshNode { @display("p=3381,1548;i=device/accesspoint;is=s"); }
        meshNode57: MeshNode { @display("p=3709,1505;i=device/accesspoint;is=s"); }
        meshNode58: MeshNode { @display("p=3976,1517;i=device/accesspoint;is=s"); }
        meshNode59: MeshNode { @display("p=4358,1524;i=device/accesspoint;is=s"); }
        meshNode60: MeshNode { @display("p=4627,1532;i=device/accesspoint;is=s"); }
        meshNode61: MeshNode { @display("p=120,2062;i=device/accesspoint;is=s"); }
        meshNode62: MeshNode { @display("p=434,2030;i=device/accesspoint;is=s"); }
        meshNode63: MeshNode { @display("p=806,2028;i=device/accesspoint;is=s"); }
        meshNode64: MeshNode { @display("p=1050,1988;i=device/accesspoint;is=s"); }
        meshNode65: MeshNode { @display("p=1454,1983;i=device/accesspoint;is=s"); }
        meshNode66: MeshNode { @display("p=1765,2020;i=device/accesspoint;is=s"); }
        meshNode67: MeshNode { @display("p=2115,1986;i=device/accesspoint;is=s"); }
        meshNode68: MeshNode { @display("p=2360,2030;i=device/accesspoint;is=s"); }
        meshNode69: MeshNode { @display("p=2676,2043;i=device/accesspoint;is=s"); }
        meshNode70: MeshNode { @display("p=3048,1984;i=device/accesspoint;is=s"); }
        meshNode71: MeshNode { @display("p=3394,2063;i=device/accesspoint;is=s"); }
        meshNode72: MeshNode { @display("p=3731,2026;i=device/accesspoint;is=s"); }
        meshNode73: MeshNode { @display("p=3978,2016;i=device/accesspoint;is=s"); }
        meshNode74: MeshNode { @display("p=4333,2035;i=device/accesspoint;is=s"); }
        meshNode75: MeshNode { @display("p=4629,2046;i=device/accesspoint;is=s"); }
        meshNode76: MeshNode { @display("p=117,2503;i=device/accesspoint;is=s"); }
        meshNode77: MeshNode { @display("p=444,2453;i=device/accesspoint;is=s"); }
        meshNode78: MeshNode { @display("p=806,2531;i=device/accesspoint;is=s"); }
        meshNode79: MeshNode { @display("p=1070,2503;i=device/accesspoint;is=s"); }
        meshNode80: MeshNode { @display("p=1383,2536;i=device/accesspoint;is=s"); }
        meshNode81: MeshNode { @display("p=1718,2497;i=device/accesspoint;is=s"); }
        meshNode82: MeshNode { @display("p=2110,2480;i=device/accesspoint;is=s"); }
        meshNode83: MeshNode { @display("p=2360,2530;i=device/accesspoint;is=s"); }
        meshNode84: MeshNode { @display("p=2682,2516;i=device/accesspoint;is=s"); }
        meshNode85: MeshNode { @display("p=3049,2518;i=device/accesspoint;is=s"); }
        meshNode86: MeshNode { @display("p=3364,2468;i=device/accesspoint;is=s"); }
        meshNode87: MeshNode { @display("p=3733,2487;i=device/accesspoint;is=s"); }
        meshNode88: MeshNode { @display("p=4024,2497;i=device/accesspoint;is=s"); }
        meshNode89: MeshNode { @display("p=4316,2518;i=device/accesspoint;is=s"); }
        meshNode90: MeshNode { @display("p=4668,2516;i=device/accesspoint;is=s"); }
        meshNode91: MeshNode { @display("p=90,3005;i=device/accesspoint;is=s"); }
        meshNode92: MeshNode { @display("p=421,3000;i=device/accesspoint;is=s"); }
        meshNode93: MeshNode { @display("p=774,2980;i=device/accesspoint;is=s"); }
        meshNode94: MeshNode { @display("p=1057,2942;i=device/accesspoint;is=s"); }
        meshNode95: MeshNode { @display("p=1433,3010;i=device/accesspoint;is=s"); }
        meshNode96: MeshNode { @display("p=1702,2969;i=device/accesspoint;is=s"); }
        meshNode97: MeshNode { @display("p=2082,3010;i=device/accesspoint;is=s"); }
        meshNode98: MeshNode { @display("p=2407,2963;i=device/accesspoint;is=s"); }
        meshNode99: MeshNode { @display("p=2729,2928;i=device/accesspoint;is=s"); }
        meshNode100: MeshNode { @display("p=3020,2991;i=device/accesspoint;is=s"); }
        meshNode101: MeshNode { @display("p=3366,2991;i=device/accesspoint;is=s"); }
        meshNode102: MeshNode { @display("p=3715,2996;i=device/accesspoint;is=s"); }
        meshNode103: MeshNode { @display("p=3992,2968;i=device/accesspoint;is=s"); }
        meshNode104: MeshNode { @display("p=4364,2938;i=device/accesspoint;is=s"); }
        meshNode105: MeshNode { @display("p=4694,2972;i=device/accesspoint;is=s"); }
        meshNode106: MeshNode { @display("p=103,3472;i=device/accesspoint;is=s"); }
        meshNode107: MeshNode { @display("p=443,3411;i=device/accesspoint;is=s"); }
        meshNode108: MeshNode { @display("p=759,3464;i=device/accesspoint;is=s"); }
        meshNode109: MeshNode { @display("p=1081,3426;i=device/accesspoint;is=s"); }
        meshNode110: MeshNode { @display("p=1416,3433;i=device/accesspoint;is=s"); }
        meshNode111: MeshNode { @display("p=1750,3405;i=device/accesspoint;is=s"); }
        meshNode112: MeshNode { @display("p=2089,3410;i=device/accesspoint;is=s"); }
        meshNode113: MeshNode { @display("p=2375,3464;i=device/accesspoint;is=s"); }
        meshNode114: MeshNode { @display("p=2700,3402;i=device/accesspoint;is=s"); }
        meshNode115: MeshNode { @display("p=3024,3434;i=device/accesspoint;is=s"); }
        meshNode116: MeshNode { @display("p=3397,3429;i=device/accesspoint;is=s"); }
        meshNode117: MeshNode { @display("p=3660,3476;i=device/accesspoint;is=s"); }
        meshNode118: MeshNode { @display("p=4015,3410;i=device/accesspoint;is=s"); }
        meshNode119: MeshNode { @display("p=4343,3470;i=device/accesspoint;is=s"); }
        meshNode120: MeshNode { @display("p=4693,3417;i=device/accesspoint;is=s"); }
        meshNode121: MeshNode { @display("p=143,3892;i=device/accesspoint;is=s"); }
        meshNode122: MeshNode { @display("p=461,3938;i=device/accesspoint;is=s"); }
        meshNode123: MeshNode { @display("p=775,3878;i=device/accesspoint;is=s"); }
        meshNode124: MeshNode { @display("p=1082,3948;i=device/accesspoint;is=s"); }
        meshNode125: MeshNode { @display("p=1437,3918;i=device/accesspoint;is=s"); }
        meshNode126: MeshNode { @display("p=1750,3903;i=device/accesspoint;is=s"); }
        meshNode127: MeshNode { @display("p=2089,3891;i=device/accesspoint;is=s"); }
        meshNode128: MeshNode { @display("p=2428,3956;i=device/accesspoint;is=s"); }
        meshNode129: MeshNode { @display("p=2675,3951;i=device/accesspoint;is=s"); }
        meshNode130: MeshNode { @display("p=3077,3938;i=device/accesspoint;is=s"); }
        meshNode131: MeshNode { @display("p=3368,3964;i=device/accesspoint;is=s"); }
        meshNode132: MeshNode { @display("p=3724,3890;i=device/accesspoint;is=s"); }
        meshNode133: MeshNode { @display("p=4063,3881;i=device/accesspoint;is=s"); }
        meshNode134: MeshNode { @display("p=4346,3933;i=device/accesspoint;is=s"); }
        meshNode135: MeshNode { @display("p=4671,3960;i=device/accesspoint;is=s"); }
        meshNode136: MeshNode { @display("p=128,4390;i=device/accesspoint;is=s"); }
        meshNode137: MeshNode { @display("p=445,4377;i=device/accesspoint;is=s"); }
        meshNode138: MeshNode { @display("p=782,4393;i=device/accesspoint;is=s"); }
        meshNode139: MeshNode { @display("p=1074,4373;i=device/accesspoint;is=s"); }
        meshNode140: MeshNode { @display("p=1423,4357;i=device/accesspoint;is=s"); }
        meshNode141: MeshNode { @display("p=1753,4398;i=device/accesspoint;is=s"); }
        meshNode142: MeshNode { @display("p=2089,4383;i=device/accesspoint;is=s"); }
        meshNode143: MeshNode { @display("p=2372,4421;i=device/accesspoint;is=s"); }
        meshNode144: MeshNode { @display("p=2723,4397;i=device/accesspoint;is=s"); }
        meshNode145: MeshNode { @display("p=3008,4387;i=device/accesspoint;is=s"); }
        meshNode146: MeshNode { @display("p=3340,4383;i=device/accesspoint;is=s"); }
        meshNode147: MeshNode { @display("p=3714,4427;i=device/accesspoint;is=s"); }
        meshNode148: MeshNode { @display("p=4016,4357;i=device/accesspoint;is=s"); }
        meshNode149: MeshNode { @display("p=4348,4356;i=device/accesspoint;is=s"); }
        meshNode150: MeshNode { @display("p=4700,4399;i=device/accesspoint;is=s"); }

        // ── 100 LoRa Sensör (5/GW) ───────────────────────────────────────────
        sensorGW1[5]: EndNode { @display("i=device/sensor02;is=s"); }
        sensorGW2[5]: EndNode { @display("i=device/sensor02;is=s"); }
        sensorGW3[5]: EndNode { @display("i=device/sensor02;is=s"); }
        sensorGW4[5]: EndNode { @display("i=device/sensor02;is=s"); }
        sensorGW5[5]: EndNode { @display("i=device/sensor02;is=s"); }
        sensorGW6[5]: EndNode { @display("i=device/sensor02;is=s"); }
        sensorGW7[5]: EndNode { @display("i=device/sensor02;is=s"); }
        sensorGW8[5]: EndNode { @display("i=device/sensor02;is=s"); }
        sensorGW9[5]: EndNode { @display("i=device/sensor02;is=s"); }
        sensorGW10[5]: EndNode { @display("i=device/sensor02;is=s"); }
        sensorGW11[5]: EndNode { @display("i=device/sensor02;is=s"); }
        sensorGW12[5]: EndNode { @display("i=device/sensor02;is=s"); }
        sensorGW13[5]: EndNode { @display("i=device/sensor02;is=s"); }
        sensorGW14[5]: EndNode { @display("i=device/sensor02;is=s"); }
        sensorGW15[5]: EndNode { @display("i=device/sensor02;is=s"); }
        sensorGW16[5]: EndNode { @display("i=device/sensor02;is=s"); }
        sensorGW17[5]: EndNode { @display("i=device/sensor02;is=s"); }
        sensorGW18[5]: EndNode { @display("i=device/sensor02;is=s"); }
        sensorGW19[5]: EndNode { @display("i=device/sensor02;is=s"); }
        sensorGW20[5]: EndNode { @display("i=device/sensor02;is=s"); }

    connections allowunconnected:
        // Tüm haberleşme sendDirect() — fiziksel kablo YOK
}
