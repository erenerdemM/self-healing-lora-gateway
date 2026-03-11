// =============================================================================
// HybridGateway — Hibrit LoRaWAN + Mesh Gateway
// =============================================================================
// Donanım (PDF Bölüm 5.1-5.2):
//   Raspberry Pi CM4 (Lite, 2GB RAM)
//   + RAK5146 (SX1303 + SX1250 RF ön-uç)  — LoRaWAN konsantratör
//       SX1303 özellikleri:
//         - 8 kanal, 16 bağımsız LoRa demodülatör (SF7-SF12 aynı frekansta çakışma yok)
//         - SX1250 RF ön-uç ile alıcı hassasiyeti: -141 dBm (SF12/125kHz)
//         - Fine Timestamping (TDOA jeölokasyon, GPS'siz üçgenleme)
//         - Pratik kapasite: ~10 000 uç düğüm (10 msg/gün, ALOHA çarpışma payı)
//   + Heltec HT-CT62 (SX1262+ESP32-C3) — Mesh radyo modülü (Band P: 869.525 MHz)
//   + Quectel EG25-G (LTE Cat4) — hücresel yedek backhaul
//   Batarya: 3.7 V × 3500 mAh = 46 620 J (Li-ion)
//
// Yasal Spektrum Sınırları (BTK KET Yönetmeliği / ETSI EN 300 220-2):
//   Alt Bant M (868.0–868.6 MHz): max 14 dBm ERP / +16 dBm EIRP, %1 DC
//     → ACK, Join-Accept, MAC komutları standart kanalda bu bandı kullanır
//   Alt Bant P (869.4–869.65 MHz): max +27 dBm (500 mW), %10 DC
//     → RX2 penceresi; GW'ye %1 dar kotadan 10× daha geniş TX hakkı verir
//
// Anten EIRP Kuralı:
//   Yasal limit TX kartındaki güç değil; antenin ucundan yayılan EIRP'dir.
//   Örn: 8 dBi dış mekan anten → cihaz TX gücü 16-8 = 8 dBm'a indirilmeli.
//   antennaGain_dBi parametresi bu hesabı otomatik yapar.
//
// Sorumluluklar:
//   - EndNode'lardan gelen LoRaWAN paketlerini alır (16 demodülatör paralel)
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

        // ── LoRaWAN Konsantratör Parametreleri (RAK5146 / SX1303 + SX1250) ─
        // SX1303+SX1250 alıcı hassasiyeti: -141 dBm (FLoRa default -100 dBm'yi eziyor)
        // SF12/125kHz için; SF7'de ~-126 dBm
        LoRaGWNic.radio.receiver.sensitivity = default(-141dBm);

        // Demodülatör sayısı: 8 kanal × 2 = 16 bağımsız demodülatör
        // Aynı frekansta aynı anda farklı SF'lerden gelen paketler çakışmaz (ortogonal)
        int numDemodulators = default(16);

        // Pratik maksimum uç düğüm kapasitesi (10 msg/gün, ALOHA)
        int maxNodesPerGW   = default(10000);

        // ── Downlink TX Güç Parametreleri (BTK KET / ETSI EN 300 220-2) ──
        // Bant M (868.0–868.6 MHz): Join-Accept, ACK, MAC komutları
        //   Max: 14 dBm ERP (= +16 dBm EIRP isotropik anten ile)
        //   Duty Cycle: %1 → kayan 1-saatlik pencere: 36 s/saat kota
        double bandMTxPower_dBm   = default(14.0);
        double bandMDutyCycle     = default(0.01);

        // Bant P (869.4–869.65 MHz): RX2 penceresi (LoRaWAN downlink)
        //   Max: +27 dBm (500 mW) — günlük 10× geniş kota
        //   Duty Cycle: %10 → kayan 1-saatlik pencere: 360 s/saat kota
        //   Merkez frekans: (869.4 + 869.65) / 2 = 869.525 MHz
        double rx2TxPower_dBm     = default(27.0);
        double rx2DutyCycle       = default(0.10);
        double rx2Frequency @unit(Hz) = default(869.525MHz);

        // Anten kazancı EIRP düzeltmesi:
        //   Gerçek TX gücü = bandMTxPower_dBm - antennaGain_dBi ≤ 14 dBm ERP
        //   Örn: 8 dBi anten → EIRP düzeltmesi = 8 dB → TX = 14-8 = 6 dBm
        double antennaGain_dBi    = default(0.0);  // İzotropik anten (varsayılan)

        // Parametreleri routingAgent'e ilet
        routingAgent.bandMTxPower_dBm  = default(this.bandMTxPower_dBm);
        routingAgent.bandMDutyCycle    = default(this.bandMDutyCycle);
        routingAgent.rx2TxPower_dBm    = default(this.rx2TxPower_dBm);
        routingAgent.rx2DutyCycle      = default(this.rx2DutyCycle);
        routingAgent.rx2Frequency      = default(this.rx2Frequency);
        routingAgent.antennaGain_dBi   = default(this.antennaGain_dBi);
        routingAgent.numDemodulators   = default(this.numDemodulators);

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
