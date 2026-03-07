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
#include <string>

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

  // ─── Durum ─────────────────────────────────────────────────────────────────
    PowerState currentPowerState_;

    // Komşu tablosu: IP adresi → NeighborEntry
    std::map<L3Address, NeighborEntry> neighborTable_;

  // ─── Dahili zamanlayıcılar ─────────────────────────────────────────────────
    cMessage *cadTimer_      = nullptr;  // Periyodik CAD tetikleyici
    cMessage *sleepTimer_    = nullptr;  // Active Rx timeout → Deep Sleep
    cMessage *backhaulTimer_ = nullptr;  // Backhaul durumu kontrol döngüsü

  // ─── İstatistik sinyalleri ─────────────────────────────────────────────────
    simsignal_t powerStateSignal_;       // Güç durumu geçişlerini kaydet
    simsignal_t routingCostSignal_;      // Seçilen next-hop maliyetini kaydet
    simsignal_t congestionEventSignal_;  // Darboğaz nedeniyle 2. komşuya geçiş sayısı

  // ─── Dahili yardımcı fonksiyonlar ─────────────────────────────────────────
    /**
     * Tek bir komşu için C_i maliyet değerini hesapla.
     * C_i = α·(P_tx/|RSSI_i|) + β·Q_i + γ·H_i
     * Not: RSSI negatif olduğundan mutlak değer alınır.
     */
    double computeCost(const NeighborEntry& n, double txPower_dBm) const;

    /**
     * Komşu tablosunu artan maliyet sırasına göre sırala.
     * Darboğaz tespiti bu listeye göre yapılır.
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
