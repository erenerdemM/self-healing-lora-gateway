// =============================================================================
// EndNode — LoRaWAN IoT Uç Nokta Cihazı (Saha Sensörü)
// =============================================================================
// PDF: "End Node" — sensörlerden veri toplayıp LoRa ile StandardGateway'e gönderir.
//
// Mimari konumu:
//   EndNode --[LoRa PHY, SF12, 868MHz]--> StandardGateway
//
// Versiyon Yol Haritası:
//   V1 (Genel Tanım): LoRa PHY/NIC + SensorLoRaApp + enerji deposu + sabit konum
//   V2 (Gerçekçilik) : Uyku/uyanma döngüsü (Class A), ADR (Adaptive Data Rate),
//                      gerçek 11B payload (sıcaklık, nem, batarya seviyesi)
//   V3 (Ölçeklendirme): Çoklu EndNode, farklı SF/TP konfigürasyonları,
//                        mobilite (random waypoint), batarya tüketim modellemesi
//
// Donanım referansı (PDF Bölüm 3.2): STM32L476RG + E77-900M LoRaWAN Modülü
//   - 11B payload, little-endian: sıcaklık(2B) + nem(2B) + basınç(2B) +
//     hız(2B) + batarya(2B) + sıra no(1B)
// =============================================================================

import inet.applications.contract.IApp;
import inet.mobility.static.StationaryMobility;
import inet.networklayer.common.InterfaceTable;
import inet.common.lifecycle.NodeStatus;
import inet.power.storage.IdealEpEnergyStorage;
import flora.LoRa.LoRaNic;

module EndNode
{
    parameters:
        @networkNode();
        // Her topolojide tutarlı sensör görünümü
        @display("i=misc/sensor2;is=n");

        // Uygulama sayısı (V1: 1 adet SensorLoRaApp)
        int numApps = default(1);

        // FLoRa uyumlu parametreler (V2'de kaldırılacak)
        string deploymentType = default("");
        double maxGatewayDistance = default(320.0);
        double gatewayX = default(320.0);
        double gatewayY = default(320.0);

        *.interfaceTableModule = default(absPath(".interfaceTable"));

        // V2: hasStatus=true → Class A uyku/uyanma döngüsü modellenecek
        bool hasStatus = default(false);

    submodules:
        // NodeStatus: uyku/uyanma ve lifecycle yönetimi (V2'de aktif olacak)
        status: NodeStatus if hasStatus {
            @display("p=30,20;is=s");
        }

        // Enerji deposu: ideal model (V2'de Li-ion 3500mAh 18650 → PDF Bölüm 5.4)
        energyStorage: IdealEpEnergyStorage {
            @display("p=30,60;is=s");
        }

        // Arayüz tablosu
        interfaceTable: InterfaceTable {
            @display("p=30,100;is=s");
        }

        // Sabit konum (V3: RandomWaypointMobility ile değiştirilecek)
        mobility: StationaryMobility {
            @display("p=30,140;is=s");
        }

        // LoRa fiziksel arayüz — FLoRa LoRaNic (SX1262 benzeri)
        // V1: SF12, 868MHz, 14dBm (EU868 uyumlu, ETSI EN 300 220)
        // V2: ADR aktif, SF/TP otomatik ayarlama
        LoRaNic: LoRaNic {
            @display("p=170,100");
            interfaceTableModule = absPath("^.interfaceTable");
            energySourceModule = absPath("^.energyStorage");
        }

        // Uygulama katmanı (V1: SensorLoRaApp, V2: gerçek payload formatlı app)
        app[numApps]: <> like IApp {
            @display("p=320,100,row,120");
        }

    connections allowunconnected:
        for i=0..numApps-1 {
            app[i].socketOut --> LoRaNic.upperLayerIn;
            LoRaNic.upperLayerOut --> app[i].socketIn;
        }
}
