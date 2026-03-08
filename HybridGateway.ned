// =============================================================================
// HybridGateway — Hibrit LoRaWAN + Mesh Gateway
// =============================================================================
// Donanım (PDF Bölüm 5.1-5.2):
//   Raspberry Pi CM4 (Lite, 2GB RAM)
//   + RAK5146 (SX1303) mPCIe  — LoRaWAN konsantratör
//   + Heltec HT-CT62 (SX1262+ESP32-C3) — Mesh radyo modülü
//   + Quectel EG25-G (LTE Cat4) — hücresel yedek backhaul
//   Batarya: 3.7 V × 3500 mAh = 46 620 J (Li-ion)
//
// Sorumluluklar:
//   - EndNode'lardan gelen LoRaWAN paketlerini alır
//   - ONLINE: PacketForwarder → NetworkServer (doğrudan WAN)
//   - FAILOVER: HybridRouting → en düşük maliyetli komşu → NetworkServer
//     Maliyet: C_i = α·(P_tx/RSSI_i) + β·(Q_i/Q_max) + γ·H_i
//   - Backhaul durumunu 100 ms periyotla denetler
//   - Mesh paketi önceliği > sensör paketi (öncelik kuyruğu)
// =============================================================================

import flora.LoraNode.LoRaGW;
import inet.power.storage.IdealEpEnergyStorage;

module HybridGateway extends LoRaGW
{
    parameters:
        @display("i=device/antennatower;is=n");

        // Arayüz sayısı:
        //   1 → yalnızca mesh/WAN tarafı (backhaul yok, yönlendirme yapılır)
        //   2 → mesh + internet/WAN (NetworkServer'a doğrudan bağlı)
        numEthInterfaces = default(1);

        // Batarya kapasitesi (IdealEpEnergyStorage: sonsuz kapasite, NodeStatus sorunu yok)
        // TODO V2: Gerçek batarya için SimpleEpEnergyStorage + NodeStatus
        energyStorage.nominalCapacity = default(46620J);
        energyStorage.initialCapacity = default(46620J);

        // ── Akıllı Yönlendirme Maliyet Fonksiyonu ────────────────────────
        // C_i = α·(P_tx/RSSI_i) + β·(Q_i/Q_max) + γ·H_i   (α+β+γ = 1.0)
        double alpha = default(0.4);   // Sinyal kalitesi ağırlığı  (RSSI)
        double beta  = default(0.3);   // Kuyruk doluluk oranı ağırlığı
        double gamma = default(0.3);   // Hop sayısı ağırlığı

        // Darboğaz eşiği: Q_i >= congestionThreshold → 2. en iyi komşuya geç
        double congestionThreshold = default(0.8);

        // Backhaul kontrol periyodu
        double backhaulCheckInterval @unit(s) = default(0.1s);

        // Backhaul başlangıç durumu (omnetpp.ini'den override edilebilir)
        //   [General] → true  : ONLINE mod
        //   [V2-Failover] bölümünde → false : t=0'dan itibaren failover testi
        //   Dinamik kesinti: t=200s'de event üzerinden setBackhaulUp(false)
        bool backhaulUp = default(true);

        // Ajanına parametre iletimi
        routingAgent.alpha                 = default(this.alpha);
        routingAgent.beta                  = default(this.beta);
        routingAgent.gamma                 = default(this.gamma);
        routingAgent.congestionThreshold   = default(this.congestionThreshold);
        routingAgent.backhaulCheckInterval = default(this.backhaulCheckInterval);
        routingAgent.backhaulUp            = default(this.backhaulUp);

    submodules:
        // Enerji deposu — simülasyon boyunca tüketimi izler
        energyStorage: IdealEpEnergyStorage {
            @display("p=50,350");
        }
        // Akıllı yönlendirme ve komşu tablo ajanı
        routingAgent: HybridRouting {
            @display("p=160,350");
        }

    connections allowunconnected:
        // Veri düzlemi entegrasyonu: backhaul DOWN iken PacketForwarder,
        // sensör paketlerini doğrudan bu bağlantı üzerinden HybridRouting'e iletir.
        // HybridRouting → SENARYO B → forwardToMesh() → sendDirect → hedef MeshNode
        packetForwarder.hybridOut --> routingAgent.routeRequestIn;
}
