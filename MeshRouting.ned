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

        // TX gücü (SX1262, 14 dBm — maliyet formülünde pay)
        double txPower_dBm = default(14.0);

        // ── CAD / Düşük Güç Parametreleri ────────────────────────────────
        // DEEP_SLEEP → cadInterval aşımı → CAD scan → preamble yoksa DEEP_SLEEP
        //                                            → preamble varsa  ACTIVE_RX
        double cadInterval    @unit(s)  = default(0.5s);   // Periyodik CAD tetik
        double cadDuration    @unit(ms) = default(5ms);    // Tekil tarama süresi
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
