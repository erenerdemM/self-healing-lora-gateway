// =============================================================================
// HybridRouting — Akıllı Yönlendirme ve Güç Yönetimi Simple Modülü
// =============================================================================
// Hem HybridGateway hem de MeshNode içinde submodule olarak kullanılır.
//
// Görevler:
//   1. Komşu Tablosu yönetimi (beacon/paket güncellemeleri ile dinamik)
//   2. Maliyet fonksiyonu hesaplama:
//        C_i = α·(P_tx/RSSI_i) + β·(Q_i/Q_max) + γ·H_i
//   3. Darboğaz koruması: Q_i >= 0.8 → 2. en iyi komşuya yönlendir
//   4. Güç durum makinesi (MeshNode için):
//        DEEP_SLEEP (15 µA) → CAD → ACTIVE_RX (120 mA) → DEEP_SLEEP
//   5. Backhaul izleme: 100 ms periyotla internet bağlantısını denetler
//
// @see HybridRouting.h için C++ tanımları
// =============================================================================

simple HybridRouting
{
    parameters:
        // ── Maliyet Fonksiyonu Ağırlıkları ───────────────────────────────
        // C_i = α·(P_tx/RSSI_i) + β·(Q_i/Q_max) + γ·H_i  (α+β+γ = 1.0)
        double alpha = default(0.4);                // RSSI ağırlığı
        double beta  = default(0.3);                // Kuyruk doluluk ağırlığı
        double gamma = default(0.3);                // Hop count ağırlığı

        // Darboğaz eşiği — aşılırsa 2. en iyi komşu seçilir
        double congestionThreshold = default(0.8);

        // Backhaul kontrol periyodu (HybridGateway için)
        double backhaulCheckInterval @unit(s) = default(0.1s);

        // TX gücü (maliyet hesabında pay olarak kullanılır)
        double txPower_dBm = default(14.0);         // dBm

        // ── CAD / Düşük Güç Parametreleri (MeshNode için) ────────────────
        // DEEP_SLEEP → CAD scan → (preamble bulunursa) → ACTIVE_RX → DEEP_SLEEP
        double cadInterval    @unit(s)  = default(0.5s);    // CAD tetikleme periyodu
        double cadDuration    @unit(ms) = default(5ms);     // Tekil CAD tarama süresi
        double activeRxTimeout @unit(s) = default(2.0s);    // Max Active Rx süresi

        // ── Komşu Tablosu ─────────────────────────────────────────────────
        // Belirtilen süreden eski giriş "stale" sayılıp silinir
        double neighborTimeout @unit(s) = default(30.0s);

        @display("i=block/routing");
        @class(HybridRouting);

    gates:
        // Üst katmandan gelen yönlendirme kararı istekleri
        input  routeRequestIn;
        // Seçilen next-hop bilgisi üst katmana
        output routeDecisionOut;

        // Komşu beacon / RSSI bildirimleri (MAC katmanından)
        input  neighborUpdateIn;
}
