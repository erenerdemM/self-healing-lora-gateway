// =============================================================================
// HybridGateway — Hibrit LoRaWAN + Mesh Gateway
// =============================================================================
// Donanım Mimarisi:
//
//  ┌─────────────────────────────────────────────────────────────────────────┐
//  │  Alt Sistem       │ Bileşen              │ Arayüz      │ Görev         │
//  ├─────────────────────────────────────────────────────────────────────────┤
//  │  Ana İşlemci      │ Raspberry Pi CM4      │ Taşıyıcı    │ Routing +     │
//  │                   │ (Lite, 2GB RAM)       │ Kart        │ PacketFwd     │
//  ├─────────────────────────────────────────────────────────────────────────┤
//  │  LoRaWAN Modülü   │ RAK5146 (SX1303)      │ SPI / USB   │ 8 kanal, 16  │
//  │                   │                       │             │ demodülatör  │
//  ├─────────────────────────────────────────────────────────────────────────┤
//  │  Mesh Modülü      │ Heltec HT-CT62        │ UART / USB  │ GW-arası     │
//  │                   │ (SX1262 + ESP32-C3)   │             │ acil mesh    │
//  │                   │ [Co-processor]        │             │ (şifreleme + │
//  │                   │                       │             │  kuyruk ESP  │
//  │                   │                       │             │  içinde)     │
//  ├─────────────────────────────────────────────────────────────────────────┤
//  │  Birincil Backhaul│ CM4 Built-in GbE      │ Ethernet    │ Ana internet │
//  │                   │ (Gigabit Ethernet)    │ CAT5e/6     │ bağlantısı   │
//  ├─────────────────────────────────────────────────────────────────────────┤
//  │  İkincil Backhaul │ Quectel EG25-G        │ Mini PCIe   │ LTE Cat4     │
//  │  (Yedek)          │ (LTE Cat4)            │             │ aktif yedek  │
//  ├─────────────────────────────────────────────────────────────────────────┤
//  │  Güç              │ Şebeke (220V AC)      │ —           │ Harici güç,  │
//  │                   │                       │             │ batarya yok   │
//  └─────────────────────────────────────────────────────────────────────────┘
//
// Backhaul Öncelik Sırası (Aktif Yedeklilik):
//   1. Ethernet GbE  (RTT ~1–5 ms)   → backhaulUp=true
//   2. Quectel LTE Cat4 (RTT ~30-80 ms) → lteBackhaulUp=true (Ethernet düşerse)
//   3. Mesh Failover (HybridRouting)  → her ikisi de düşerse
//
// Not — Heltec HT-CT62 Co-processor Modeli:
//   ESP32-C3, Meshtastic protokolünü (şifreleme, paket kuyruklama) kendi içinde
//   çözer; CM4 sadece UART/USB üzerinden hazır paketi alıp yayınlar.
//   Bu tasarım CM4 CPU yükünü azaltır ve mesh katmanını bağımsız kılar.
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
//   - SENARYO A: Ethernet veya LTE aktif → PacketForwarder → NetworkServer
//   - SENARYO B: Her iki backhaul da kopuk → HybridRouting → Mesh Failover
//     Maliyet: C_i = α·(P_tx/RSSI_i) + β·(Q_i/Q_max) + γ·H_i
//   - Backhaul durumunu 100 ms periyotla denetler
// =============================================================================

import flora.LoraNode.LoRaGW;

module HybridGateway extends LoRaGW
{
    parameters:
        @display("i=device/antennatower;is=n");

        // Arayüz sayısı:
        //   1 → yalnızca mesh/WAN tarafı
        //   2 → mesh + internet/WAN (NetworkServer'a doğrudan bağlı)
        numEthInterfaces = default(1);

        // ── LoRaWAN Konsantratör Parametreleri (RAK5146 / SX1303) ──────────
        // SX1303 alıcı hassasiyeti: -141 dBm @ SF12/125kHz
        // (FLoRa default -100 dBm'yi eziyor)
        LoRaGWNic.radio.receiver.sensitivity = default(-141dBm);

        // 8 kanal × 2 = 16 bağımsız demodülatör
        // Aynı frekansta farklı SF'ler çakışmaz (ortogonal)
        int numDemodulators = default(16);

        // Pratik maksimum uç düğüm kapasitesi (10 msg/gün, ALOHA)
        int maxNodesPerGW   = default(10000);

        // ── Downlink TX Güç Parametreleri (BTK KET / ETSI EN 300 220-2) ──
        // Bant M (868.0–868.6 MHz): Join-Accept, ACK, MAC komutları
        //   Max: 14 dBm ERP  |  Duty Cycle: %1 → 36 s/saat kota
        double bandMTxPower_dBm   = default(14.0);
        double bandMDutyCycle     = default(0.01);

        // Bant P (869.4–869.65 MHz): RX2 penceresi (LoRaWAN downlink)
        //   Max: +27 dBm (500 mW)  |  Duty Cycle: %10 → 360 s/saat kota
        //   Merkez frekans: (869.4 + 869.65) / 2 = 869.525 MHz
        double rx2TxPower_dBm     = default(27.0);
        double rx2DutyCycle       = default(0.10);
        double rx2Frequency @unit(Hz) = default(869.525MHz);

        // Anten kazancı EIRP düzeltmesi:
        //   Gerçek TX gücü = bandMTxPower_dBm - antennaGain_dBi ≤ 14 dBm ERP
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

        // ── Birincil Backhaul: Ethernet GbE (CM4 built-in) ───────────────
        // omnetpp.ini'den [Faz-Failover] bölümünde false yapılır
        bool backhaulUp = default(true);

        // Ethernet RTT gecikme modeli (ms): 0=ideal, 1-5=gerçekçi LAN
        double backhaulLatency @unit(ms) = default(0ms);

        // ── İkincil Backhaul: Quectel EG25-G (LTE Cat4, Mini PCIe) ──────
        // Ethernet düşünce otomatik devreye girer (aktif yedeklilik)
        // omnetpp.ini: **.routingAgent.lteBackhaulUp = false  → LTE de kopuk testi
        bool lteBackhaulUp = default(true);

        // LTE Cat4 RTT gecikme modeli (ms): 30=iyi sinyal, 80=orta, 200=zayıf
        double lteBackhaulLatency @unit(ms) = default(50ms);

        // Parametreleri routingAgent'e ilet
        routingAgent.alpha                 = default(this.alpha);
        routingAgent.beta                  = default(this.beta);
        routingAgent.gamma                 = default(this.gamma);
        routingAgent.congestionThreshold   = default(this.congestionThreshold);
        routingAgent.backhaulCheckInterval = default(this.backhaulCheckInterval);
        routingAgent.backhaulUp            = default(this.backhaulUp);
        routingAgent.backhaulLatency       = default(this.backhaulLatency);
        routingAgent.lteBackhaulUp         = default(this.lteBackhaulUp);
        routingAgent.lteBackhaulLatency    = default(this.lteBackhaulLatency);

    submodules:
        // Akıllı yönlendirme ve komşu tablo ajanı
        routingAgent: HybridRouting {
            @display("p=160,350");
        }

    connections allowunconnected:
        // Veri düzlemi entegrasyonu: her iki backhaul da DOWN iken PacketForwarder,
        // sensör paketlerini bu bağlantı üzerinden HybridRouting'e iletir.
        // HybridRouting → SENARYO B → forwardToMesh() → sendDirect → hedef MeshNode
        packetForwarder.hybridOut --> routingAgent.routeRequestIn;

        // Mesh Röle Geri Dönüş: hedef GW'de HybridRouting, mesh'ten gelen paketi
        // LoRaMacFrame ile sarar ve PacketForwarder aracılığıyla NS2'ye iletir.
        routingAgent.nsForwardOut --> packetForwarder.meshRelayIn;
}
