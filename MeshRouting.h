#ifndef MESHROUTING_H
#define MESHROUTING_H

// =============================================================================
// MeshRouting — Akıllı Next-Hop Yönlendirme + CAD Güç Durum Makinesi
// =============================================================================
// Sadece MeshNode (pille çalışan röle) içinde kullanılır.
//
// CAD Güç Durum Makinesi (SX1262 tabanlı, 3.7 V beslemeli):
//
//   ┌─────────────────────────────────────────────────────────────────────┐
//   │  DEEP_SLEEP                                                         │
//   │  Akım: 15 µA   │ cadInterval timer tetiklenir                      │
//   └───────────────────────────┬─────────────────────────────────────────┘
//                               │ cadInterval doldu
//                               ▼
//   ┌────────────────────────────────────────────────────────────────────┐
//   │  CAD  (Channel Activity Detection)                                 │
//   │  Akım: ~10 mA, Süre: cadDuration (~5 ms)                          │
//   └───────────┬────────────────────────────┬────────────────────────────┘
//               │ Preamble YOK               │ Preamble VAR (WoR tetiklendi)
//               ▼                            ▼
//   DEEP_SLEEP'e dön            ┌──────────────────────────────────────────┐
//                               │  ACTIVE_RX                               │
//                               │  Akım: 120 mA                            │
//                               │  Paket alımı gerçekleşir veya timeout    │
//                               └────────────────┬─────────────────────────┘
//                                                │ Paket alındı
//                                                ▼
//                               ┌──────────────────────────────────────────┐
//                               │  PROCESSING                              │
//                               │  Komşu tablosu güncellenir               │
//                               │  C_i hesaplanır, next-hop seçilir        │
//                               └────────────────┬─────────────────────────┘
//                                                │ Karar verildi
//                                                ▼
//                               ┌──────────────────────────────────────────┐
//                               │  ACTIVE_TX                               │
//                               │  Akım: 120 mA                            │
//                               │  Paket next-hop'a iletilir               │
//                               └────────────────┬─────────────────────────┘
//                                                │ İletim bitti
//                                                ▼
//                                          DEEP_SLEEP
//
// Maliyet Fonksiyonu:
//   C_i = α · (P_tx / |RSSI_i|) + β · (Q_i / Q_max) + γ · H_i
//   Minimum C_i olan komşu seçilir.
//   Q_i >= congestionThreshold (0.8) → 2. en iyi komşuya geç.
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
// PowerState — SX1262 radyo güç durumları
// ─────────────────────────────────────────────────────────────────────────────
enum class PowerState {
    DEEP_SLEEP,   // Radyo tamamen kapalı.  Beklenti: ~15 µA
    CAD,          // Channel Activity Detection taraması.  ~10 mA, ~5 ms
    ACTIVE_RX,    // Preamble bulundu; tam alım modunda.  ~120 mA
    PROCESSING,   // Paket alındı; yönlendirme kararı hesaplanıyor (radyo uyku)
    ACTIVE_TX     // next-hop'a paket gönderiliyor.  ~120 mA
};

// ─────────────────────────────────────────────────────────────────────────────
// NeighborEntry — Komşu tablosunun tek satırı
// ─────────────────────────────────────────────────────────────────────────────
struct NeighborEntry {
    L3Address  address;            // Komşunun IP adresi
    double     rssi_dBm;           // Son ölçülen RSSI (dBm) — RSSI_i
    int        hopCountToGateway;  // İnternete erişen GW'ye kalan hop — H_i
    double     queueOccupancy;     // Kuyruk doluluk oranı [0.0–1.0] — Q_i/Q_max
    bool       isOnlineGateway;    // true → bu komşunun aktif internet bağlantısı var
    simtime_t  lastSeen;           // Son mesajın alındığı simülasyon zamanı
    double     cachedCost;         // En son hesaplanan C_i (önbellek)
};

// ─────────────────────────────────────────────────────────────────────────────
// MeshRouting — cSimpleModule
//
// MeshNode içinde submodule olarak çalışır.
// CAD timer → güç durum geçişleri → maliyet fonksiyonu → next-hop seçimi.
// ─────────────────────────────────────────────────────────────────────────────
class MeshRouting : public cSimpleModule
{
  // ─── Public API ────────────────────────────────────────────────────────────
  public:
    /**
     * Paket yönlendirme talebi: en düşük maliyetli next-hop adresini döndür.
     * Darboğaz koruması otomatik uygulanır.
     * @param txPower_dBm Gönderim gücü (dBm) — maliyet payı
     * @return Seçilen komşunun L3 adresi; komşu yoksa UNSPECIFIED_ADDRESS
     */
    L3Address selectNextHop(double txPower_dBm);

    /**
     * Komşu tablosunu güncelle.
     * Yeni komşuysa yeni satır açılır; varsa RSSI/hop/queue güncellenir.
     */
    void updateNeighbor(const L3Address& addr,
                        double           rssi_dBm,
                        int              hopCount,
                        double           queueOccupancy,
                        bool             isOnlineGateway);

    /**
     * neighborTimeout süresi geçmiş komşuları tablodan sil.
     */
    void purgeStaleNeighbors();

    /** Mevcut güç durumunu döndür. */
    PowerState getPowerState() const { return currentState_; }

  // ─── OMNeT++ yaşam döngüsü ─────────────────────────────────────────────────
  protected:
    virtual void initialize(int stage) override;
    virtual int  numInitStages() const override { return inet::NUM_INIT_STAGES; }
    virtual void handleMessage(cMessage *msg) override;
    virtual void finish() override;

  // ─── Parametreler ──────────────────────────────────────────────────────────
  private:
    // Maliyet fonksiyonu ağırlıkları (α+β+γ = 1.0)
    double alpha_;               // RSSI bileşeni ağırlığı
    double beta_;                // Kuyruk doluluk ağırlığı
    double gamma_;               // Hop count ağırlığı
    double congestionThreshold_; // Bu oran üzerindeyse darboğaz → 2. komşu
    double txPower_dBm_;         // Varsayılan TX gücü (dBm)

    // CAD / uyku parametreleri
    double cadInterval_s_;       // Periyodik CAD tetikleme aralığı
    double cadDuration_ms_;      // Tekil CAD tarama süresi
    double activeRxTimeout_s_;   // Bu süre geçince ACTIVE_RX → DEEP_SLEEP
    double neighborTimeout_s_;   // Bu süre geçince komşu silindi

    // Meshtastic radyo parametreleri (Band P / LongFast)
    double loraCarrierFrequency_Hz_;  // 869.525 MHz — Band P merkez
    double loraBandwidth_Hz_;         // 250 kHz (LongFast default)
    int    loraSF_;                   // 11 (LongFast) — SF7..SF12
    int    loraPreambleLength_;       // 16 sembol (Meshtastic std, LoRa default=8)
    int    loraSyncWord_;             // 0x2B = 43 (Meshtastic özel)
    int    hopLimit_;                 // Varsayılan maks hop: 3
    int    maxHopLimit_;              // Mutlak üst sınır: 7

    // Görev döngüsü (Duty Cycle) — Bant P %10 → 360s/saat
    double dutyCycleLimit_;           // 0.10
    double txQuotaWindow_s_;          // 3600s kayan pencere
    // Kayan pencere TX log: (gönderim_zamanı, toa_saniye)
    std::deque<std::pair<simtime_t, double>> txLog_;

    // Otomatik ölçeklendirme (v2.4.0+)
    int    autoScaleThreshold_;       // 40 düğüm üzerinde ölçekleme başlar
    double autoScaleCoeff_;           // 0.075 / düğüm

    // Beacon parametreleri
    double beaconInterval_s_;    // Periyodik beacon yayın aralığı
    double beaconRssi_;          // Simüle edilmiş beacon RSSI (dBm)
    double meshQueueOccupancy_;  // Sabit kuyruk doluluk oranı

    // Topoloji kısıt listesi: sadece bu modül adlarına beacon gönderilir
    std::vector<std::string> meshNeighborList_;

  // ─── Durum ─────────────────────────────────────────────────────────────────
    PowerState currentState_ { PowerState::DEEP_SLEEP };

    // Komşu tablosu: IP adresi → NeighborEntry
    std::map<L3Address, NeighborEntry> neighborTable_;

    // Yönlendirme bekleyen paketin hedef adresi (PROCESSING süresince tutulur)
    L3Address pendingDestination_;

    // V2 iletim tamponu: ACTIVE_TX'e taşınan paket ve seçilen next-hop adresi
    cMessage  *pendingPkt_  = nullptr;  // sahiplik enterActiveTx'e geçer

  // ─ Dahili zamanlayıcılar ────────────────────────────────────────────────
    cMessage *cadTimer_         = nullptr;  // Periyodik CAD uyanma zamanlayıcısı
    cMessage *cadEndTimer_      = nullptr;  // CAD tarama bitiş zamanlayıcısı
    cMessage *rxTimeoutTimer_   = nullptr;  // ACTIVE_RX zaman aşımı
    cMessage *beaconTimer_      = nullptr;  // Periyodik mesh beacon zamanlayıcısı


  // ─── İstatistik sinyalleri ─────────────────────────────────────────────────
    static simsignal_t powerStateSignal_;        // Güç durum geçişlerini kaydet
    static simsignal_t routingCostSignal_;       // Seçilen next-hop C_i değerini kaydet
    static simsignal_t congestionEventSignal_;   // Darboğaz → 2. komşu seçimi sayısı
    static simsignal_t sleepDurationSignal_;     // Her DEEP_SLEEP periyodunun süresini kaydet

    // Uyku moduna girilen simülasyon zamanı (sleepDuration hesabı için)
    simtime_t sleepEntryTime_ { 0 };

  // ─── Maliyet hesaplama ─────────────────────────────────────────────────────
    /**
     * Tek komşu için C_i hesapla.
     * C_i = α·(P_tx/|RSSI_i|) + β·Q_i + γ·H_i
     * RSSI negatif olduğundan mutlak değer alınır.
     */
    double computeCost(const NeighborEntry& n, double txPower_dBm) const;

    /**
     * Komşu tablosunu artan C_i sırasına göre sırala.
     * Darboğaz tespitinde bu liste kullanılır.
     */
    std::vector<std::pair<L3Address, NeighborEntry>>
        getSortedNeighbors(double txPower_dBm) const;

    /**
     * Band P TX kotası kontrolü (kayan 1-saatlik pencere).
     * toaSeconds: göndermek istenen paketin hava süresi (s)
     * Dönüş: true → TX izinli (log'a eklendi); false → TX Suspend
     */
    bool checkDutyCycle(double toaSeconds);

    /**
     * Son 2 saatteki aktif komşu sayısına göre ölçeklendirilmiş aralık (s).
     * N <= threshold → baseInterval değişmeden döner.
     * N > threshold  → baseInterval × (1 + (N−threshold) × coeff)
     */
    double computeScaledInterval(double baseInterval) const;

  // ─── CAD güç durum makinesi ─────────────────────────────────────────────────
    void enterDeepSleep();     // Radyo kapat, cadTimer başlat (15 µA)
    void enterCAD();           // CAD taraması başlat (~5 ms, cadEndTimer başlat)
    void enterActiveRx();      // Preamble tespit → tam alım moduna geç, rxTimeout başlat
    void enterProcessing();    // Paket alındı → yönlendirme karar aşaması
    void enterActiveTx();      // next-hop seçildi → iletim başlat

    /**
     * CAD tarama sonucu: havada preamble var mı?
     */
    void onCADComplete(bool preambleDetected);

    /**
     * ACTIVE_RX zaman aşımı: paket gelmedi, DEEP_SLEEP'e dön.
     */
    void onRxTimeout();

    /**
     * Komşulara periyodik beacon yayını (topoloji listesine göre filtrelenir).
     * Beacon içeriği: meshAddress, RSSI, kuyruk doluluk, online=false, hopToGw.
     */
    void broadcastBeaconToMeshNeighbors();

    /**
     * Komşu tablosundan en yakın ONLINE-GW'ye kaç hop gerektiğini hesapla.
     * Doğrudan komşu ONLINE-GW varsa 1; onun komşusundaysa 2; vb.
     * Tablo boşsa 10 (çok uzak) döner.
     */
    int computeHopToGw() const;
};

#endif // MESHROUTING_H
