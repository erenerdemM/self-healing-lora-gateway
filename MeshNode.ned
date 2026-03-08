// =============================================================================
// MeshNode — Akıllı Mesh Rölesi (Next-Hop Routing + CAD Uyku Modu)
// =============================================================================
// Donanım (PDF Bölüm 5.1.2):
//   Heltec HT-CT62: SX1262 (LoRa) + ESP32-C3 (MCU)
//   Batarya: 3.7 V × 3500 mAh = 46 620 J (Li-ion)
//   Anten: 868 MHz PCB/SMA
//
// Görev:
//   - HybridGateway'ler arasında paketleri iletir (store-and-forward)
//   - Flooding YOK — her paket için C_i maliyet fonksiyonu ile next-hop seçilir
//       C_i = α·(P_tx/|RSSI_i|) + β·(Q_i/Q_max) + γ·H_i
//   - Darboğaz koruması: Q_i >= 0.8 → 2. komşuya yönlendir
//   - Güç durum makinesi (SX1262 datasheet değerleri):
//       DEEP_SLEEP (15 µA) → CAD (10 mA, ~5 ms) → ACTIVE_RX (120 mA) → DEEP_SLEEP
//
// Temel sınıf:
//   AdhocHost → IP forwarding, mobil düğüm, gelişmiş routing altyapısı
//   WirelessHost → IEEE 802.11 (V2'de LoRa PHY ile değiştirilecek)
//   NodeBase    → energyStorage / energyManagement submodule desteği
// =============================================================================

import inet.node.inet.AdhocHost;
import inet.power.storage.IdealEpEnergyStorage;
import inet.physicallayer.wireless.common.energyconsumer.StateBasedEpEnergyConsumer;

module MeshNode extends AdhocHost
{
    parameters:
        @display("i=device/accesspoint;is=n");

        // IP forwarding AdhocHost'ta zaten true; açıkça belirtiyoruz
        forwarding = default(true);

        // V2: SX1262 LoRa radyo eklenecek, IEEE 802.11 PHY kaldırılacak.
        // V1 → V2 geçişi: numWlanInterfaces = 1 (enerji tüketimi ölçülebilir)
        // CAD simüle eden StateBasedEpEnergyConsumer wlan[0] üzerinde çalışır.
        // LoRaMedium çakışması önlem: MeshNode Ethernet ile bağlı, WLAN fiziksel
        // ortum LoRaMedium'dan ayrı tutulacak (V2: meshtasticMedium eklenecek).
        numWlanInterfaces = default(1);

        // ── Enerji deposu ──────────────────────────────────────────────────
        // NodeBase'deki energyStorage slotunu IdealEpEnergyStorage ile doldur
        // (IdealEpEnergyStorage sonsuz kapasiteli; gerçekçi değerler omnetpp.ini'de
        //  daha sonra SimpleEpEnergyStorage ile değiştirilebilir)
        energyStorage.typename = default("IdealEpEnergyStorage");

        // ── Radyo enerji tüketim modeli (SX1262 datasheet, 3.7 V referans) ─
        // StateBasedEpEnergyConsumer: radyo state → güç tüketimi eşlemesi
        wlan[*].radio.energyConsumer.typename = default("StateBasedEpEnergyConsumer");

        //   DEEP_SLEEP : 15 µA × 3.7 V = 0.0000555 W
        wlan[*].radio.energyConsumer.sleepPowerConsumption          = default(0.0000555W);
        //   CAD (receiverIdle olarak modellenir): 10 mA × 3.7 V = 0.037 W
        wlan[*].radio.energyConsumer.receiverIdlePowerConsumption   = default(0.037W);
        //   ACTIVE_RX : 120 mA × 3.7 V = 0.444 W
        wlan[*].radio.energyConsumer.receiverReceivingPowerConsumption = default(0.444W);
        //   ACTIVE_TX (14 dBm, SX1262): 120 mA × 3.7 V = 0.444 W
        wlan[*].radio.energyConsumer.transmitterTransmittingPowerConsumption = default(0.444W);

        // ── MeshRouting parametre geçişi ───────────────────────────────────
        // Maliyet fonksiyonu: C_i = α·(P_tx/|RSSI|) + β·(Q/Q_max) + γ·H
        meshRouting.alpha               = default(0.4);
        meshRouting.beta                = default(0.3);
        meshRouting.gamma               = default(0.3);
        meshRouting.congestionThreshold = default(0.8);   // %80 eşiği

        // CAD durum makinesi
        meshRouting.cadInterval         = default(0.5s);  // Ne sıklıkta uyan
        meshRouting.cadDuration         = default(5ms);   // Tekil CAD tarama
        meshRouting.activeRxTimeout     = default(2.0s);  // Max alım süresi
        meshRouting.txPower_dBm         = default(14.0);  // SX1262 TX gücü

        // Komşu zaman aşımı
        meshRouting.neighborTimeout     = default(30.0s);

    submodules:
        // Akıllı yönlendirme ve CAD güç yönetimi ajanı
        meshRouting: MeshRouting {
            @display("p=160,350");
        }
}
