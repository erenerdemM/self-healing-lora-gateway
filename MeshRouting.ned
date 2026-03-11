// =============================================================================
// MeshRouting — Akıllı Next-Hop Yönlendirme + CAD Güç Durum Makinesi
// =============================================================================
// MeshNode içinde submodule olarak çalışır.
//
// Görevler:
//   1. CAD periyodik zamanlayıcısı ile güç durumu yönetimi:
//        DEEP_SLEEP → CAD → ACTIVE_RX → PROCESSING → ACTIVE_TX → DEEP_SLEEP
//   2. Komşu Tablosu tutma (RSSI, hop sayısı, kuyruk doluluk oranı)
//   3. Maliyet fonksiyonu hesaplama:
//        C_i = α·(P_tx/|RSSI_i|) + β·(Q_i/Q_max) + γ·H_i
//   4. Darboğaz tespiti: Q_i >= congestionThreshold → 2. en iyi komşuya geç
//   5. Kuyrukt önceliği: mesh/relay paketi > sensör paketi
//
// @see MeshRouting.h / MeshRouting.cc
// =============================================================================

simple MeshRouting
{
    parameters:
        // ── Maliyet Fonksiyonu Ağırlıkları ───────────────────────────────
        // C_i = α·(P_tx/|RSSI_i|) + β·(Q_i/Q_max) + γ·H_i  (α+β+γ = 1.0)
        double alpha = default(0.4);                 // RSSI bileşeni ağırlığı
        double beta  = default(0.3);                 // Kuyruk doluluk ağırlığı
        double gamma = default(0.3);                 // Hop count ağırlığı

        // Darboğaz eşiği — aşılırsa 2. en iyi komşu seçilir
        double congestionThreshold = default(0.8);   // 0.8 = %80

        // TX gücü (SX1262 hw üst sınır 22 dBm — Band P yasal: 27 dBm ERP)
        double txPower_dBm = default(22.0);

        // ── Meshtastic LoRa Radyo Parametreleri (EU_868 Bant P) ──────────
        // Meshtastic EU_868: Bant P (869.4-869.65 MHz) = %10 DC, 27 dBm max
        // (Bant M/L = %1 DC; Bant P = %10 DC → 10× daha geniş TX kotası)
        // Kanal merkezi: (869.4 + 869.65) / 2 = 869.525 MHz
        double loraCarrierFrequency @unit(Hz) = default(869.525MHz);

        // LongFast (varsayılan preset): SF11 / BW=250kHz / LDRO=ON
        // ShortFast: SF7/250kHz | MediumFast: SF9/250kHz | LongSlow: SF12/125kHz
        double loraBandwidth        @unit(Hz) = default(250kHz);
        int    loraSF                          = default(11);

        // Meshtastic 16-sembol preambül (LoRa standardı 8'den farklı):
        //   t_preamble = (16 + 4.25) × Tsym(SF11/250kHz)
        //              = 20.25 × 8.192ms = 165.9ms
        //   LPL (SX1262 periyodik uyanış): cadInterval < t_preamble → tetikleme garantili
        int    loraPreambleLength              = default(16);

        // Meshtastic özel senkronizasyon kelimesi
        // Standart LoRa: 0x12 (public/TTN) veya 0x34 (private)
        // Meshtastic: 0x2B (= decimal 43) — ağ izolasyonu sağlar
        int    loraSyncWord                    = default(0x2B);

        // ── Çok-Atlama (Hop) Sınırları ────────────────────────────────────
        // Meshtastic 2.6+: Next-Hop Routing devreye girdi (Flooding yerine)
        //   hopLimit=3: paket en fazla 3 atlama yapabilir
        //   maxHopLimit=7: operatör tarafından ayarlanabilecek mutlak üst sınır
        int    hopLimit                        = default(3);
        int    maxHopLimit                     = default(7);

        // ── Görev Döngüsü (Duty Cycle) & TX Kotası ─────────────────────────
        // Bant P (869.4-869.65 MHz) = %10 DC → 360 saniye/saat TX kotası
        // Kayan 1-saatlik pencere (rolling time window):
        //   Son 3600s içindeki toplam ToA toplamı ≤ 360s → TX izinli
        //   Kota dolunca: TX Suspend (gönderim iptal) — eski paketler
        //   pencereden çıkana dek beklenir.
        // Uyarı: override_duty_cycle=true yalnızca DMO/lab için!
        double dutyCycleLimit                  = default(0.10);
        double txQuotaWindow        @unit(s)   = default(3600s);

        // ── Otomatik Ölçeklendirme (Meshtastic v2.4.0+) ────────────────────
        // Son 2 saatte duyulan aktif düğüm sayısı > autoScaleThreshold ise:
        //   Scaled_Interval = Default_Interval × (1.0 + ((N - threshold) × coeff))
        // Örnek: 62 düğüm, beaconInterval=10s:
        //   Scaled = 10 × (1.0 + (22 × 0.075)) = 10 × 2.65 = 26.5s
        // Amaç: LongFast (624ms ToA) → 50+ düğümde ~576 pkt/saat limit aşılmadan
        //       beacon/telemetri aralıklarını organik olarak seyrelterek koruma sağlar.
        int    autoScaleThreshold              = default(40);
        double autoScaleCoeff                  = default(0.075);

        // ── CAD / Düşük Güç Parametreleri ────────────────────────────────
        // DEEP_SLEEP → cadInterval aşımı → CAD scan → preamble yoksa DEEP_SLEEP
        //                                            → preamble varsa  ACTIVE_RX
        double cadInterval    @unit(s)  = default(0.5s);   // Periyodik CAD tetik
        double cadDuration    @unit(ms) = default(16ms);   // LongFast SF11/250kHz: 2×Tsym=16ms
        double activeRxTimeout @unit(s) = default(2.0s);   // Max alım süresi

        // ── Komşu Tablosu ─────────────────────────────────────────────────
        // Bu süreden eski giriş "stale" sayılıp silinir
        double neighborTimeout @unit(s) = default(30.0s);

        // ── Mesh Ağ Kimliği & Beacon ──────────────────────────────────────
        // Bu MeshNode'un mesh ağındaki adresi (beacon'da kullanılır)
        string meshAddress = default("0.0.0.0");
        // Periyodik beacon yayın aralığı
        double beaconInterval @unit(s) = default(10.0s);
        // Simüle edilmiş beacon RSSI değeri (dBm)
        double beaconRssi = default(-75.0);
        // Sabit kuyruk doluluk oranı: MeshNode'un taşıdığı yük simülasyonu
        double meshQueueOccupancy = default(0.1);
        // Topoloji zorlaması: Beacon sadece bu listedeki modüllere gönderilir.
        // Boşlukla ayrılmış modül adları (NED submodule isimleri).
        // Örn: "hybridGW1 meshNode2 meshNode3"
        string meshNeighborList = default("");
        @display("i=block/routing");
        @class(MeshRouting);

        // ── OMNeT++ istatistik sinyalleri ─────────────────────────────────
        // Qtenv ve opp_scavetool ile grafiklenebilir.
        //
        //   powerState : 0=DEEP_SLEEP 1=CAD 2=ACTIVE_RX 3=PROCESSING 4=ACTIVE_TX
        @signal[powerState](type=long);
        @statistic[powerState](title="Güç Durumu"; source=powerState;
            record=vector; interpolationmode=sample-hold);

        //   routingCost : seçilen next-hop için hesaplanan C_i değeri
        @signal[routingCost](type=double);
        @statistic[routingCost](title="Yönlendirme Maliyeti C_i"; source=routingCost;
            record=vector,stats,histogram);

        //   congestionEvent : darboğaz tespiti → 2. komşuya geçiş sayısı
        @signal[congestionEvent](type=long);
        @statistic[congestionEvent](title="Darboğaz Olayı"; source=congestionEvent;
            record=count,vector);

        //   sleepDuration : her DEEP_SLEEP periyodunun saniye cinsinden süresi
        @signal[sleepDuration](type=double);
        @statistic[sleepDuration](title="Uyku Süresi (s)"; source=sleepDuration;
            record=vector,mean,max);

    gates:
        // Üst katmandan veya HybridGateway'den (sendDirect ile) yönlendirme talebi
        input  routeRequestIn @directIn;
        // Seçilen next-hop adresi üst katmana
        output routeDecisionOut;
        // MAC katmanından veya beacon'dan (sendDirect ile) komşu RSSI/beacon bildirimleri
        input  neighborUpdateIn @directIn;
}
