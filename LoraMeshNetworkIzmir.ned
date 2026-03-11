// =============================================================================
// LoraMeshNetworkIzmir  —  İzmir İli LoRaWAN + Meshtastic Kapsama Topolojisi
// =============================================================================
// Proje  : Kendi Kendini İyileştiren Hibrit LoRa Gateway Mimarisi
//   Eren ERDEM (2020502028) — Melisa KURAL (2021502041)
//   DEÜ EEF — Danışman: Prof. Dr. Damla GÜRKAN KUNTALP
//
// ─── Coğrafi Alan ─────────────────────────────────────────────────────────────
//   İzmir İli bounding box: 200 km × 110 km ≈ 22,000 km² (gerçek il: ~12,012 km²)
//   Koordinatlar: (0,0) = SW köşe (Seferihisar S), (200km, 110km) = NE köşe (Gediz N)
//   Referans noktaları:
//     İzmir Merkez (Konak) : (80km,  50km)
//     Aliağa               : (67km,  90km)
//     Selçuk               : (120km, 15km)
//     Bergama              : (55km, 100km)
//     Ödemiş               : (145km, 60km)
//     Torbalı              : (95km,  35km)
//     Dikili               : (42km,  95km)
//     Çeşme                : (20km,  40km)
//     Foça                 : (58km,  75km)
//
// ─── GW Izgarası (7 sütun × 4 satır = 28 HybridGateway) ─────────────────────
//   Yatay adım: 28 km  (her GW ~15km yarıçap → üst üste binen kapsama)
//   Dikey adım: 28 km
//   İlk GW: (14km, 14km)
//
//   Sütun indeksi : col=0..6  → x = 14 + col*28  (km)
//   Satır indeksi : row=0..3  → y = 14 + row*28  (km)
//
//   GW adı: hybridGW[col*4 + row]  (28 toplam)
//   Yani:
//     col=0: x=14  → hybridGW[0..3]   (Çeşme–Karaburun batı kolu)
//     col=1: x=42  → hybridGW[4..7]   (Foça–Dikili batı şeridi)
//     col=2: x=70  → hybridGW[8..11]  (Aliağa–Bornova merkez ekseni)
//     col=3: x=98  → hybridGW[12..15] (Kemalpaşa–Torbalı–Selçuk)
//     col=4: x=126 → hybridGW[16..19] (Kiraz–Ödemiş)
//     col=5: x=154 → hybridGW[20..23] (iç Ege doğu şeridi)
//     col=6: x=182 → hybridGW[24..27] (Kütahya sınırı doğu)
//
// ─── İnternet Bağlantılı "Çıkış GW" Listesi ─────────────────────────────────
//   Gerçek fiber/5G backhaul noktaları:
//     hybridGW[10]  → İzmir merkez veri merkezi (x=70, y=42)
//     hybridGW[11]  → Aliağa endüstriyel (x=70, y=70)   [yedek]
//     hybridGW[13]  → Kemalpaşa OSB      (x=98, y=14)
//     hybridGW[18]  → Ödemiş kırsal      (x=126, y=70)  [yedek]
//   Geri kalan 24 GW: backhaulCutTime=-1 değil, rastgele kesilme senaryosu için
//   Bu simülasyon: backhaulCutTime=1800s (GW[10] t=30dk kesilir)
//
// ─── Mesh Topolojisi (omurga zinciri) ─────────────────────────────────────────
//   7 MeshNode: Her sütunun iki GW'si arasına yerleştirilmiş
//   meshNode[0..6]: x=14,42,70,98,126,154,182 → y=55 (yatay merkez ekseni)
//   Zincir: GW[0]─MN[0]─GW[4]─MN[1]─GW[8]─...─GW[24]
//   + her MeshNode komşu MeshNode'lar ile da bağlı → mesh ağ
//
// ─── Sensör Dağılımı ─────────────────────────────────────────────────────────
//   5 sensör / GW  ×  28 GW  =  140 sensör toplam
//   sensor[gwIdx*5 + 0..4]: her GW etrafinda 5 farklı yönde sensör
//   Mesafe: 2–12 km arası (her GW'nin LoRaWAN hücresini temsil eder)
//
// ─── RF Parametreler ─────────────────────────────────────────────────────────
//   LoRaWAN : SF12/125kHz/14dBm/868.1MHz/11B → ToA=1.97s → DC=0.985% < %1 ✓
//   Mesh    : SF11/250kHz/22dBm/869.525MHz (Band P, Meshtastic LongFast)
//   GW alıcı: SX1303+SX1250, -141dBm @ SF12/125kHz (LoRaReceiver.cc güncellendi)
//   Path loss: PL(d) = 31.54 + 27.5·log₁₀(d)  [dB], σ=0, kırsal açık alan
//   Menzil  : 14-(−141) = 155 dB bütçe → d_max ≈ 15.2 km ✓ (28km/2=14km < 15.2km)
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

network LoraMeshNetworkIzmir
{
    parameters:
        @display("bgb=960,600;bgi=maps/terrain,s");

    submodules:

        // ── RF Ortam Motorları ─────────────────────────────────────────────
        radioMedium: LoRaMedium {
            @display("p=40,20;i=misc/sun;is=s");
        }
        wlanMedium: Ieee80211ScalarRadioMedium {
            @display("p=140,20;i=misc/sun;is=s");
        }
        configurator: Ipv4NetworkConfigurator {
            parameters:
                assignDisjunctSubnetAddresses = true;
                @display("p=40,580;is=vs");
        }

        // ── 28 HybridGateway (7 sütun × 4 satır, 28km adım) ──────────────
        // İsimlendirme: hybridGW[col*4 + row], col=0..6, row=0..3
        hybridGW[28]: HybridGateway {
            parameters:
                numEthInterfaces = 1;
                @display("p=200,300;i=device/accesspoint");
        }

        // ── 7 MeshNode (yatay merkez ekseni, her sütunun ortasında) ────────
        // meshNode[0..6]: x=14,42,70,98,126,154,182 km; y=55km
        meshNode[7]: MeshNode {
            parameters:
                @display("p=400,300");
        }

        // ── 140 EndNode (5 sensör × 28 GW) ────────────────────────────────
        sensor[140]: EndNode {
            @display("p=300,400");
        }

        // ── Kablolu Altyapı ────────────────────────────────────────────────
        // 4 internet omurga yönlendiricisi (bölgesel)
        gwRouter1: Router {   // Batı: servisi kümesi GW[0..7]
            @display("p=150,520");
        }
        gwRouter2: Router {   // Merkez: GW[8..15]
            @display("p=400,520");
        }
        gwRouter3: Router {   // Doğu: GW[16..27]
            @display("p=650,520");
        }
        coreRouter: Router {  // Omurga: 3 bölge yönlendiricisini birleştirir
            @display("p=400,560");
        }
        networkServer: NetworkServer {
            parameters:
                numEthInterfaces = 1;
                numApps = 1;
                @display("p=850,560");
        }

    connections allowunconnected:

        // === BACKHAUL — Bölgesel yönlendiriciler ===
        // Batı GW kümesi (col=0: GW[0..3], col=1: GW[4..7])
        hybridGW[0].ethg++  <--> Eth1G <--> gwRouter1.ethg++;
        hybridGW[1].ethg++  <--> Eth1G <--> gwRouter1.ethg++;
        hybridGW[2].ethg++  <--> Eth1G <--> gwRouter1.ethg++;
        hybridGW[3].ethg++  <--> Eth1G <--> gwRouter1.ethg++;
        hybridGW[4].ethg++  <--> Eth1G <--> gwRouter1.ethg++;
        hybridGW[5].ethg++  <--> Eth1G <--> gwRouter1.ethg++;
        hybridGW[6].ethg++  <--> Eth1G <--> gwRouter1.ethg++;
        hybridGW[7].ethg++  <--> Eth1G <--> gwRouter1.ethg++;

        // Merkez GW kümesi (col=2: GW[8..11], col=3: GW[12..15])
        hybridGW[8].ethg++  <--> Eth1G <--> gwRouter2.ethg++;
        hybridGW[9].ethg++  <--> Eth1G <--> gwRouter2.ethg++;
        hybridGW[10].ethg++ <--> Eth1G <--> gwRouter2.ethg++;
        hybridGW[11].ethg++ <--> Eth1G <--> gwRouter2.ethg++;
        hybridGW[12].ethg++ <--> Eth1G <--> gwRouter2.ethg++;
        hybridGW[13].ethg++ <--> Eth1G <--> gwRouter2.ethg++;
        hybridGW[14].ethg++ <--> Eth1G <--> gwRouter2.ethg++;
        hybridGW[15].ethg++ <--> Eth1G <--> gwRouter2.ethg++;

        // Doğu GW kümesi (col=4: GW[16..19], col=5: GW[20..23], col=6: GW[24..27])
        hybridGW[16].ethg++ <--> Eth1G <--> gwRouter3.ethg++;
        hybridGW[17].ethg++ <--> Eth1G <--> gwRouter3.ethg++;
        hybridGW[18].ethg++ <--> Eth1G <--> gwRouter3.ethg++;
        hybridGW[19].ethg++ <--> Eth1G <--> gwRouter3.ethg++;
        hybridGW[20].ethg++ <--> Eth1G <--> gwRouter3.ethg++;
        hybridGW[21].ethg++ <--> Eth1G <--> gwRouter3.ethg++;
        hybridGW[22].ethg++ <--> Eth1G <--> gwRouter3.ethg++;
        hybridGW[23].ethg++ <--> Eth1G <--> gwRouter3.ethg++;
        hybridGW[24].ethg++ <--> Eth1G <--> gwRouter3.ethg++;
        hybridGW[25].ethg++ <--> Eth1G <--> gwRouter3.ethg++;
        hybridGW[26].ethg++ <--> Eth1G <--> gwRouter3.ethg++;
        hybridGW[27].ethg++ <--> Eth1G <--> gwRouter3.ethg++;

        // Bölge yönlendiricileri → omurga
        gwRouter1.ethg++ <--> Eth1G <--> coreRouter.ethg++;
        gwRouter2.ethg++ <--> Eth1G <--> coreRouter.ethg++;
        gwRouter3.ethg++ <--> Eth1G <--> coreRouter.ethg++;
        coreRouter.ethg++ <--> Eth1G <--> networkServer.ethg++;

        // === MESH (sendDirect — fiziksel kablo yok) ===
        // MeshNode'lar RF beacon ile haberleşir
}
