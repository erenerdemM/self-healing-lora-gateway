#ifndef HYBRIDROUTING_H
#define HYBRIDROUTING_H

// =============================================================================
// HybridRouting — Akıllı Next-Hop Yönlendirme + CAD Güç Yönetimi
// =============================================================================
// Maliyet fonksiyonu: C_i = α·(P_tx/RSSI_i) + β·(Q_i/Q_max) + γ·H_i
//
// Güç durum makinesi (MeshNode):
//   DEEP_SLEEP (15 µA) ──CAD timer──► CAD ──preamble yok──► DEEP_SLEEP
//                                       │ preamble bulundu (WoR)
//                                       ▼
//                                   ACTIVE_RX (120 mA)
//                                       │ paket alındı / timeout
//                                       ▼
//                                   PROCESSING (routing kararı)
//                                       │ yönlendirme tamamlandı
//                                       ▼
//                                   ACTIVE_TX ──► DEEP_SLEEP
//
// =============================================================================

#include <map>
#include <vector>
#include <deque>
#include <string>
#include <utility>

#include <omnetpp.h>

#include "inet/common/INETDefs.h"
#include "inet/networklayer/common/L3Address.h"

using namespace omnetpp;
using namespace inet;

// ─────────────────────────────────────────────────────────────────────────────
// PowerState — MeshNode (pille çalışan röle) güç durumları
// ─────────────────────────────────────────────────────────────────────────────
enum class PowerState {
    DEEP_SLEEP,   // Radyo kapalı.  Beklenti: ~15 µA  (SX1262 datasheet)
    CAD,          // Channel Activity Detection taraması.  ~5 ms, ~10 mA
    ACTIVE_RX,    // Paket alım modu.  ~120 mA
    ACTIVE_TX,    // Paket gönderim modu.  ~120 mA (14 dBm @ SX1262)
    PROCESSING    // Yönlendirme kararı hesaplama (CPU aktif, radyo uyku)
};

// ─────────────────────────────────────────────────────────────────────────────
// NeighborEntry — Komşu tablosunun tek bir satırı
// ─────────────────────────────────────────────────────────────────────────────
struct NeighborEntry {
    L3Address  address;            // Komşunun IP adresi
    double     rssi_dBm;           // Son ölçülen RSSI (dBm)  — RSSI_i
    int        hopCountToGateway;  // İnternete erişen GW'ye kalan hop sayısı — H_i
    double     queueOccupancy;     // Kuyruğun doluluk oranı [0.0 – 1.0] — Q_i/Q_max
    simtime_t  lastSeen;           // Bu komşudan son mesaj alınma zamanı
    bool       isOnlineGateway;    // true → bu komşunun aktif internet bağlantısı var
    double     cachedCost;         // En son hesaplanan C_i (önbellek)
};

// ─────────────────────────────────────────────────────────────────────────────
// HybridRouting — cSimpleModule
//
// OMNeT++ modülü: hem HybridGateway hem MeshNode içinde submodule olarak çalışır.
// Yönlendirme kararı: maliyet fonksiyonunu minimize eden next-hop seçimi.
// Güç yönetimi: CAD periyodik zamanlayıcısı ile durum makinesi.
// ─────────────────────────────────────────────────────────────────────────────
class HybridRouting : public cSimpleModule
{
  // ─── Public API ────────────────────────────────────────────────────────────
  public:
    /**
     * En düşük maliyetli next-hop'u seç ve adresini döndür.
     * @param txPower_dBm  Gönderim gücü (dBm) — maliyet payı
     * @return Seçilen komşunun L3 adresi; komşu yoksa UNSPECIFIED_ADDRESS
     */
    L3Address selectNextHop(double txPower_dBm);

    /**
     * Komşu tablosunu güncelle (beacon veya gelen paket başlığından tetiklenir).
     * Giriş yoksa yeni satır açılır; varsa rssi/hop/queue bilgisi güncellenir.
     */
    void updateNeighbor(const L3Address& addr,
                        double rssi_dBm,
                        int    hopCount,
                        double queueOccupancy,
                        bool   isOnlineGateway);

    /**
     * neighborTimeout süresi geçmiş girişleri tablodan sil.
     * Periyodik olarak (backhaulCheckInterval) çağrılır.
     */
    void purgeStaleNeighbors();

    /** Mevcut güç durumunu döndür (enerji tüketimi kaydı için). */
    PowerState getPowerState() const { return currentPowerState_; }

  // ─── OMNeT++ yaşam döngüsü ─────────────────────────────────────────────────
  protected:
    virtual void initialize(int stage) override;
    virtual int  numInitStages() const override { return inet::NUM_INIT_STAGES; }
    virtual void handleMessage(cMessage *msg) override;
    virtual void finish() override;

  // ─── Parametreler ──────────────────────────────────────────────────────────
  private:
    // Maliyet fonksiyonu ağırlıkları
    double alpha_;               // RSSI bileşeni ağırlığı
    double beta_;                // Kuyruk doluluk ağırlığı
    double gamma_;               // Hop count ağırlığı
    double congestionThreshold_; // Bu oranın üzerindeyse "darboğaz" → 2. komşu
    double backhaulCheckInterval_s_;

    // CAD / düşük güç parametreleri
    double cadInterval_s_;       // CAD tetikleme periyodu
    double cadDuration_ms_;      // Tekil CAD tarama süresi
    double activeRxTimeout_s_;   // Bu süre geçerse Active Rx → Deep Sleep
    double neighborTimeout_s_;   // Bu kadar süredir görülmeyen komşu silindi

    double txPower_dBm_;         // Varsayılan gönderim gücü

    // ── LoRaWAN Gateway downlink parametreleri (BTK KET / ETSI EN 300 220-2) ──
    double bandMTxPower_dBm_;    // Band M: 14 dBm ERP (ACK/Join-Accept/MAC)
    double bandMDutyCycle_;      // Band M: %1 DC → 36 s/saat
    double rx2TxPower_dBm_;      // Band P RX2: 27 dBm max
    double rx2DutyCycle_;        // Band P: %10 DC → 360 s/saat
    double rx2Frequency_Hz_;     // 869.525 MHz (Band P merkezi)
    double txQuotaWindow_s_;     // Kayan pencere: 3600 s
    double antennaGain_dBi_;     // Anten kazancı (EIRP düzeltmesi)
    int    numDemodulators_;     // 16 bağımsız demodülatör (8 kanal × 2)
    // Kayan 1-saatlik TX logları: (zaman, toa_s)
    std::deque<std::pair<simtime_t, double>> txLogBandM_;  // Band M downlink log
    std::deque<std::pair<simtime_t, double>> txLogRx2_;    // RX2 downlink log

    // Beacon / kuyruk parametreleri
    double beaconInterval_s_;    // Beacon yayın periyodu (s)
    double beaconRssi_;          // Simüle edilmiş mesh RSSI (dBm)
    double sensorPacketRate_;    // Sensör paket varış hızı (pkt/s)
    int    maxQueueSize_;        // Kuyruk kapasitesi (pkt)
    double backhaulCutTime_s_;   // Bu zamanda Ethernet backhaul kesilir (< 0 = yok)
    double backhaulLatency_ms_;  // Ethernet RTT gecikme eki (ms, 0=yok)

    // ── İkincil Backhaul: Quectel EG25-G (LTE Cat4, Mini PCIe) ──────────────
    // Ethernet düşünce otomatik devreye girer (aktif yedeklilik)
    // backhaulLatency_ms_ sıfırken LTE gecikmesi devreye girer (~30-80 ms)
    bool   isLteBackhaulUp_ = true;  // initialize()'da par() ile ezilir
    double lteBackhaulLatency_ms_;   // LTE Cat4 RTT gecikme (ms)

    // Dinamik kuyruk doluluk oranı [0..1] — her backhaulTimer'da güncellenir
    double currentQueueOcc_;

    // Failover loglama sayacı (her 5s'de bir detaylı log)
    int    failoverLogCounter_;

    // ── İşlemci Gecikmesi Modeli (STM32 gerçekliği) ───────────────────────────
    // SX1303 SPI okuma + DMA kopyalama + CPU interrupt servisi → ~5-15ms
    // 0.0 ise eski sıfır-gecikme davranışı korunur.
    double  processingDelay_ms_;      // par("processingDelay")
    cMessage *processTimer_ = nullptr; // Geciktirilmiş routing kararı zamanlayıcısı
    cMessage *pendingMsg_   = nullptr; // İşlem bekleyen tek paket (basit model)

  // ─── Durum ─────────────────────────────────────────────────────────────────
    PowerState currentPowerState_;

    // Backhaul (internet) bağlantı durumu.
    // Başlangıç değeri initialize()'da par("backhaulUp") ile okunur.
    // omnetpp.ini'den: **.routingAgent.backhaulUp = false  (bölümsel failover)
    // Simülasyon içi event: setBackhaulUp(false) — örn. t=200s'de
    bool isBackhaulUp_ = true;  // Ethernet GbE durumu — par() ile ezilir

    /** omnetpp.ini veya harici C++ event'inden çağrılabilir */
    void setBackhaulUp(bool up)    { isBackhaulUp_     = up; }
    void setLteBackhaulUp(bool up) { isLteBackhaulUp_  = up; }

    /** Aktif backhaul gecikmesini ms cinsinden döndür.
     *  Ethernet UP → backhaulLatency_ms_
     *  Sadece LTE UP → lteBackhaulLatency_ms_
     *  Her ikisi de DOWN → 0 (mesh failover, gecikme anlamsız) */
    double activeBackhaulLatency_ms() const {
        if (isBackhaulUp_)    return backhaulLatency_ms_;
        if (isLteBackhaulUp_) return lteBackhaulLatency_ms_;
        return 0.0;
    }

    // Paket sıra numarası sayacı (her encapsulation'da artar)
    int seqCounter_ = 0;

    // Topoloji kısıtı: sadece bu modül adlarına beacon gönderilir
    // Boşsa → tüm ağa broadcast (geriye dönük uyumlu)
    std::vector<std::string> meshNeighborList_;

    // Komşu tablosu: IP adresi → NeighborEntry
    std::map<L3Address, NeighborEntry> neighborTable_;

  // ─── Dahili zamanlayıcılar ─────────────────────────────────────────────────
    cMessage *cadTimer_              = nullptr;  // Periyodik CAD tetikleyici
    cMessage *sleepTimer_            = nullptr;  // Active Rx timeout → Deep Sleep
    cMessage *backhaulTimer_         = nullptr;  // Backhaul durumu kontrol döngüsü
    cMessage *beaconTimer_           = nullptr;  // Periyodik beacon yayını
    cMessage *backhaulCutTimer_      = nullptr;  // Tek seferlik backhaul kesme
    cMessage *backhaulLatencyTimer_  = nullptr;  // Backhaul RTT gecikme modeli
    cMessage *pendingLatencyMsg_     = nullptr;  // Gecikme bekleyen orijinal paket

    /** Tüm ağdaki MeshRouting ve HybridRouting modüllerine beacon gönder. */
    void broadcastBeaconToMeshNeighbors();


  // ─── İstatistik sinyalleri ─────────────────────────────────────────────────
    simsignal_t powerStateSignal_;       // Güç durumu geçişlerini kaydet
    simsignal_t routingCostSignal_;      // Seçilen next-hop maliyetini kaydet
    simsignal_t congestionEventSignal_;  // Darboğaz / SOS olaylarını say
    simsignal_t droppedPacketSignal_;    // Drop-Tail: kuyruk dolu → paket düşürüldü

  // ─── Dahili yardımcı fonksiyonlar ─────────────────────────────────────────
    /** Backhaul sağlıklı mı? (simülasyonda isBackhaulUp_ bayrağına bakar) */
    bool checkBackhaulAlive() const;

    /** Mesh failover: SensorDataPacket oluştur ve en iyi komşu GW'ye ilet */
    void forwardToMesh(cMessage *originalMsg);

    /**
     * Komşu tablosunu tarayarak en iyi hedef Gateway adresini seç.
     * Darboğaz koruması: Q_i >= congestionThreshold → 2. komşuya fallback.
     */
    L3Address selectBestNeighborGateway();

    /**
     * Bölgesel çöküş veya tam darboğaz durumunda SosBeaconPacket yayınla.
     * @param reasonCode  0=CONGESTION 1=REGIONAL_FAILURE 2=GATEWAY_DOWN 3=LINK_DEGRADED
     */
    void broadcastSosBeacon(int reasonCode);

    /**
     * routeRequestIn üzerinden gelen mesajı işle (processingDelay sonrası).
     * Backhaul durumuna göre SENARYO A (doğrudan) veya SENARYO B (mesh) karar verilir.
     */
    void processRouteRequest(cMessage *msg);
    void processMeshDelivery(cMessage *msg);   // meshDeliveryIn → LoRaMacFrame wrap → nsForwardOut

    /** Online Gateway sayısını döndür (tablo taze girişler için) */
    int  countOnlineGateways() const;

    /** Tüm komşular darboğazda mı? */
    bool areAllNeighborsCongested() const;

    /**
     * Band M downlink için DC kota kontrolü (kayan 1-saatlik pencere).
     * toaSeconds: gönderilecek downlink paketin hava süresi (s)
     * Dönüş: true → TX izinli; false → DC kota doldu (TX Suspend)
     */
    bool checkBandMDutyCycle(double toaSeconds);

    /**
     * RX2 (Band P) downlink için DC kota kontrolü.
     * Dönüş: true → TX izinli; false → TX Suspend
     */
    bool checkRx2DutyCycle(double toaSeconds);

    /**
     * Anten kazancını EIRP limitine göre düzelt.
     * Dönüş: gerçek TX gücü (dBm) = txPower_dBm - antennaGain_dBi
     * EIRP = cihaz TX + anten kazancı ≤ yasal limit
     */
    double effectiveTxPower(double txPower_dBm) const;

    /**
     * Tek bir komşu için C_i maliyet değerini hesapla.
     * C_i = α·(P_tx/|RSSI_i|) + β·Q_i + γ·H_i
     */
    double computeCost(const NeighborEntry& n, double txPower_dBm) const;

    /** Verilen adrese göre maliyet hesapla (emit için) */
    double computeCostForAddress(const L3Address& addr) const;

    /**
     * Komşu tablosunu artan maliyet sırasına göre sırala.
     */
    std::vector<std::pair<L3Address, NeighborEntry>>
        getSortedNeighbors(double txPower_dBm) const;

  // ─── Güç durum makinesi geçişleri ──────────────────────────────────────────
    void enterDeepSleep();   // Radyo kapat, 15 µA moduna gir
    void enterCAD();         // Kısa süreli kanal taraması başlat
    void enterActiveRx();    // Preamble tespit → tam alım moduna geç (WoR)
    void enterActiveTx();    // Gönderim moduna geç
    void enterProcessing();  // Yönlendirme kararı hesaplama aşaması

    /** CAD taraması bir preamble tespit ederse çağrılır (Wake-on-Radio). */
    void onPreambleDetected();

    /** 100 ms periyotla backhaul durumunu kontrol et (HybridGateway rolü). */
    void checkBackhaulStatus();
};

#endif // HYBRIDROUTING_H
