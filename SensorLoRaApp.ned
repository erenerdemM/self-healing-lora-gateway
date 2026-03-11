import inet.applications.contract.IApp;

// Periodic LoRa sensor application that generates a fixed-size (11B) payload.
// The payload is packed little-endian and carried as raw bytes.
//
// This module is intended for LoRaWAN-style uplinks in our hybrid gateway project.
// (A full LoRaWAN MAC/join is handled elsewhere; here we model the uplink payload + PHY params.)
//
simple SensorLoRaApp like IApp
{
    parameters:
        @class(flora::SensorLoRaApp);
        int numberOfPacketsToSend = default(0); // 0 = infinite
        volatile double startTime @unit(s) = default(10s);
        volatile double sendInterval @unit(s) = default(60s);

        // LoRa PHY ayarları — BTK KET Yönetmeliği + ETSI EN 300 220 kapsamı
        // Maksimum ERP: +14 dBm (25 mW)  |  Bant: 868 MHz ISM
        // Ana LoRaWAN kanalları (Sub-band M): 868.1 / 868.3 / 868.5 MHz
        double initialLoRaTP @unit(dBm) = default(14dBm);    // Yasal max: +14 dBm ERP
        double initialLoRaCF @unit(Hz) = default(868.1MHz);  // Sub-band M birincil kanal
        int initialLoRaSF = default(7);
        double initialLoRaBW @unit(Hz) = default(125kHz);
        int initialLoRaCR = default(4);                       // 4/5 hata düzeltme
        bool initialUseHeader = default(true);

        // Maksimum uygulama yükü (ETSI dwell limiti):
        //   SF7–SF9  → 222 Bayt max  |  SF10–SF12 → 51 Bayt max
        int dataSize @unit(B) = default(11B);

        // BTK/ETSI Görev Döngüsü (Duty Cycle) limiti
        // Sub-band M/L/Q (868–870 MHz): %1  |  Sub-band P (869.4–869.65 MHz RX2): %10
        // min_sendInterval = ToA / dutyCycleLimit
        //   SF12/11B: 1.45s/0.01 = 145s  |  SF10/20B: 0.41s/0.01 = 41s
        double dutyCycleLimit = default(0.01);  // %1 — BTK KET / ETSI EN 300 220

        // ── LoRaWAN Class A Downlink Pencereleri (TS001-1.0.4 §7.2) ──────────────
        // TX bittikten sonra:
        //   t + RECEIVE_DELAY1 (1s) → RX1 penceresi açılır (aynı kanal/SF/BW)
        //   t + RECEIVE_DELAY2 (2s) → RX2 penceresi açılır (869.525 MHz, SF12)
        // Pencere genişliği = rxWindowSymbols × Tsym  (Tsym = 2^SF / BW)
        //   SF12/125kHz: 5 × 32.768ms = 163.8ms
        //   SF10/125kHz: 5 × 8.192ms  = 40.96ms
        double rxDelay1 @unit(s) = default(1.0s);  // RECEIVE_DELAY1 (LoRaWAN sabit)
        int rxWindowSymbols      = default(5);      // Min pencere genişliği (5×Tsym)
    gates:
        input socketIn;
        output socketOut;
}
