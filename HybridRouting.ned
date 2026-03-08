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
        // Backhaul (internet) başlangıç durumu
        //   true  → ONLINE: paketler doğrudan NetworkServer'a
        //   false → FAILOVER: en iyi komşu GW'ye mesh üzerińden
        // omnetpp.ini'den override: **.routingAgent.backhaulUp = false
        bool backhaulUp = default(true);
        // ── CAD / Düşük Güç Parametreleri (MeshNode için) ────────────────
        // DEEP_SLEEP → CAD scan → (preamble bulunursa) → ACTIVE_RX → DEEP_SLEEP
        double cadInterval    @unit(s)  = default(0.5s);    // CAD tetikleme periyodu
        double cadDuration    @unit(ms) = default(5ms);     // Tekil CAD tarama süresi
        double activeRxTimeout @unit(s) = default(2.0s);    // Max Active Rx süresi

        // ── Komşu Tablosu ─────────────────────────────────────────────────
        // Belirtilen süreden eski giriş "stale" sayılıp silinir
        double neighborTimeout @unit(s) = default(30.0s);

// ── Beacon & Gerçek Komşu Keşfi ──────────────────────────────────────
        // Periyodik beacon yayını: Komşu tablolarını gerçek verilerle doldurur.
        double beaconInterval @unit(s) = default(10.0s);  // Beacon periyodu
        double beaconRssi    = default(-75.0);  // Simüle edilmiş mesh RSSI (dBm)
        double sensorPacketRate = default(1.0); // Sensörden gelen pkt/saniye (kuyruk modeli)
        int    maxQueueSize  = default(50);     // Maksimum kuyruk kapasitesi (pkt)

        // Tek seferlik backhaul kesme zamanı (> 0 ise o anda isBackhaulUp_=false)
        // omnetpp.ini: **.hybridGW1.routingAgent.backhaulCutTime = 200s
        double backhaulCutTime @unit(s) = default(-1s);

        // Runtime backhaul bayrağı — PacketForwarder bu parametreyi okuyarak
        // mesh failover kararı verir. HybridRouting.cc tarafından dinamik olarak
        // güncellenir: backhaulCutTimer tetiklendiğinde false yapılır.
        // Doğrudan omnetpp.ini'den EZİLMEMELİ (runtime-only).
        bool backhaulRuntimeUp @mutable = default(true);  // OMNeT++ 6: C++ setBoolValue() için @mutable

        // Mesh kimliği: Beacon'da kullanılan sabitlenmiş IP benzeri adres
        // omnetpp.ini: **.hybridGW1.routingAgent.meshAddress = "10.1.0.1"
        string meshAddress = default("0.0.0.0");

        // Topoloji zorlaması: Beacon sadece bu listedeki modüllere gönderilir.
        // Boslukla ayrılmış modül adları (NED submodule isimleri).
        // Boş bırakılırsa tüm ağa broadcast yapılır (eski davranış).
        // Örn: "meshNode1" veya "meshNode1 meshNode2"
        string meshNeighborList = default("");

        // ── Sinyaller (istatistik kaydı için) ────────────────────────────
        //   powerState     : 0=NORMAL 1=FAILOVER 2=MESH_ONLY 3=RECOVERY 4=ERROR
        @signal[powerState](type=long);
        @statistic[powerState](title="Guc Durumu"; source=powerState; record=vector; interpolationmode=sample-hold);
        //   routingCost    : Secilen next-hop icin hesaplanan C_i degeri
        @signal[routingCost](type=double);
        @statistic[routingCost](title="Yonlendirme Maliyeti Ci"; source=routingCost; record=vector,mean,min,max);
        //   congestionEvent: Darboğaz tespiti → 2. komşuya geçis sayisi
        @signal[congestionEvent](type=long);
        @statistic[congestionEvent](title="Darboğaz Olayi"; source=congestionEvent; record=count,vector);

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
