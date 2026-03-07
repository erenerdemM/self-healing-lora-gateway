// =============================================================================
// MeshRouting.cc — Akıllı Mesh Röle: Next-Hop Yönlendirme + CAD Güç Makinesi
// =============================================================================
// Proje: Self-Healing Hybrid LoRa Gateway — DEÜ EEE Bitirme
//   Eren ERDEM (2020502028), Melisa KURAL (2021502041)
//
// MİMARİ SORUMLULUK:
//   - HybridGateway: interneti kopunca, en iyi hedef GW'yi seçer ve YAYINLAR.
//     (Rota HESAPLAMAz — sadece hedefi belirler)
//   - MeshNode (bu modül): Paketin "Hedef GW" adresini okur, C_i maliyet
//     fonksiyonuyla en iyi komşuyu (next-hop) hesaplar ve iletir.
//   - AjanGateway: bölgesel ağ kaybında son çare çıkış noktası.
//
// CAD DÖNGÜSÜ:
//   DEEP_SLEEP ──[cadTimer: 0.5s]──► CAD (5ms tarama)
//       kanal boş ──────────────────────► DEEP_SLEEP
//       preamble var (WoR) ─────────────► ACTIVE_RX  ──[timeout: 2s]──► DEEP_SLEEP
//                                              │ paket alındı
//                                              ▼
//                                         PROCESSING  ← C_i hesapla, next-hop seç
//                                              │ karar verildi
//                                              ▼
//                                         ACTIVE_TX ──► DEEP_SLEEP
//
// MALIYET FONKSİYONU:
//   C_i = α·(P_tx/|RSSI_i|) + β·(Q_i/Q_max) + γ·H_i
//   Fallback: Q_i >= %80 → 2. en iyi komşuya geç
// =============================================================================

#include "MeshRouting.h"
#include <algorithm>
#include <limits>

Define_Module(MeshRouting);

// =============================================================================
// Statik sinyal tanımları — sınıf başına bir kez
// =============================================================================
simsignal_t MeshRouting::powerStateSignal_      = cComponent::registerSignal("powerState");
simsignal_t MeshRouting::routingCostSignal_     = cComponent::registerSignal("routingCost");
simsignal_t MeshRouting::congestionEventSignal_ = cComponent::registerSignal("congestionEvent");
simsignal_t MeshRouting::sleepDurationSignal_   = cComponent::registerSignal("sleepDuration");

// =============================================================================
// OMNeT++ Yaşam Döngüsü
// =============================================================================

void MeshRouting::initialize(int stage)
{
    cSimpleModule::initialize(stage);

    if (stage == inet::INITSTAGE_LOCAL) {

        // ── Maliyet fonksiyonu ağırlıkları ───────────────────────────────
        alpha_               = par("alpha");
        beta_                = par("beta");
        gamma_               = par("gamma");
        congestionThreshold_ = par("congestionThreshold");
        txPower_dBm_         = par("txPower_dBm");

        // ── CAD / güç parametreleri ───────────────────────────────────────
        // par("cadInterval") @unit(s)  → getValue() direkt saniye cinsinden
        cadInterval_s_     = par("cadInterval");
        activeRxTimeout_s_ = par("activeRxTimeout");
        neighborTimeout_s_ = par("neighborTimeout");
        // par("cadDuration") @unit(ms) → getValue() milisaniye cinsinden
        cadDuration_ms_    = par("cadDuration");

        // ── Zamanlayıcı nesnelerini oluştur ───────────────────────────────
        cadTimer_       = new cMessage("cadTimer");
        cadEndTimer_    = new cMessage("cadEndTimer");
        rxTimeoutTimer_ = new cMessage("rxTimeoutTimer");

        EV_INFO << "[MeshRouting] Parametre okuması tamamlandı."
                << "  cadInterval=" << cadInterval_s_ << "s"
                << "  CAD=" << cadDuration_ms_ << "ms"
                << "  α=" << alpha_ << " β=" << beta_ << " γ=" << gamma_ << "\n";
    }

    if (stage == inet::INITSTAGE_NETWORK_LAYER) {
        // Cihaz ilk açıldığında DEEP_SLEEP'te başlar; cadTimer kurulur
        enterDeepSleep();
    }
}

// -----------------------------------------------------------------------------
// handleMessage — tüm mesaj ve timer akışının merkezi
// -----------------------------------------------------------------------------
void MeshRouting::handleMessage(cMessage *msg)
{
    // =========================================================================
    // 1. ÖZ-MESAJLAR: Zamanlayıcı olayları (güç durum makinesi)
    // =========================================================================
    if (msg->isSelfMessage()) {

        if (msg == cadTimer_) {
            // cadInterval doldu → kanal aktivitesi tara
            enterCAD();
        }
        else if (msg == cadEndTimer_) {
            // CAD tarama penceresi kapandı → preamble var mı?
            //
            // Gerçek SX1262'de hardware interrupt tetikler (DIO1/DIO2).
            // Simülasyonda: neighborTimeout içinde herhangi bir komşudan
            // güncelleme aldıysak havada aktif trafik kabul ediyoruz.
            bool preambleDetected = false;
            simtime_t recentThreshold = simTime() - neighborTimeout_s_;
            for (const auto& kv : neighborTable_) {
                if (kv.second.lastSeen >= recentThreshold) {
                    preambleDetected = true;
                    break;
                }
            }
            onCADComplete(preambleDetected);
        }
        else if (msg == rxTimeoutTimer_) {
            // ACTIVE_RX içinde paket gelmedi → uyu
            onRxTimeout();
        }
        else {
            EV_WARN << "[MeshRouting] Bilinmeyen öz-mesaj: "
                    << msg->getName() << " — silindi.\n";
            delete msg;
        }
        return;
    }

    // =========================================================================
    // 2. HARİCİ MESAJLAR: Katmanlar arası iletişim
    // =========================================================================
    const int gateId = msg->getArrivalGateId();

    // ── routeRequestIn: Ağ katmanı bir paketi iletmek istiyor ────────────────
    //
    // MİMARİ: HybridGateway interneti kopunca ve en iyi hedef GW adresini
    // seçip mesh'e YAYINAR. Bu paket MeshNode'a ulaştığında:
    //   1. MeshNode ACTIVE_RX ile paketi alır.
    //   2. Paketin Hedef GW adresini okur (V2: MeshPacket header'ından).
    //   3. Komşu tablosunda C_i en düşük olan next-hop'u hesaplar.
    //   4. Paketi o next-hop'a iletir (ACTIVE_TX).
    //
    if (gateId == findGate("routeRequestIn")) {

        EV_INFO << "[MeshRouting] Yönlendirme talebi alındı"
                << "  (mevcut durum=" << static_cast<int>(currentState_) << ")\n";

        // Radyo uyku/CAD döngüsündeyse kesintisiz geçiş yap
        if (currentState_ == PowerState::DEEP_SLEEP ||
            currentState_ == PowerState::CAD) {
            cancelEvent(cadTimer_);
            cancelEvent(cadEndTimer_);
        }
        cancelEvent(rxTimeoutTimer_);

        // ── PROCESSING: Hedef GW'ye next-hop hesapla ─────────────────────
        enterProcessing();

        // V2: Paketin Hedef GW adresini çıkar ve hedefe özel komşu seç.
        //     Şimdilik global minimum maliyet seçimi yapılıyor.
        //
        //   auto *meshPkt = check_and_cast<MeshPacket *>(msg);
        //   pendingDestination_ = meshPkt->getDestinationGateway();
        //   L3Address nextHop = selectNextHopToward(pendingDestination_, txPower_dBm_);

        L3Address nextHop = selectNextHop(txPower_dBm_);

        if (nextHop.isUnspecified()) {
            EV_WARN << "[MeshRouting] Next-hop bulunamadı — paket düşürüldü.\n";
            // V2: packetDropSignal emit edilecek
        }
        else {
            EV_INFO << "[MeshRouting] Seçilen next-hop: " << nextHop
                    << "  → ACTIVE_TX başlıyor.\n";

            // V2: routeDecisionOut gate'ine nextHop adresi gönderilecek.
            //   auto *reply = new RouteReplyMsg("routeReply");
            //   reply->setNextHop(nextHop);
            //   send(reply, "routeDecisionOut");

            enterActiveTx();
        }

        delete msg;
        return;
    }

    // ── neighborUpdateIn: MAC katmanından RSSI / komşu beacon bilgisi ────────
    //
    // V2: Bu gate'e MeshNode'un LoRa radyosu komşulardan aldığı beacon
    //     paketlerini iletecek. Buradan updateNeighbor() çağrılacak.
    //
    //   auto *beaconMsg = check_and_cast<NeighborBeaconMsg *>(msg);
    //   updateNeighbor(beaconMsg->getSenderAddress(),
    //                  beaconMsg->getRssi(),
    //                  beaconMsg->getHopCountToGateway(),
    //                  beaconMsg->getQueueOccupancy(),
    //                  beaconMsg->getIsOnlineGateway());
    //
    if (gateId == findGate("neighborUpdateIn")) {
        EV_INFO << "[MeshRouting] Komşu güncelleme mesajı alındı (V2'de işlenecek).\n";
        delete msg;
        return;
    }

    EV_WARN << "[MeshRouting] Beklenmedik gate mesajı (gateId="
            << gateId << ") — silindi.\n";
    delete msg;
}

// -----------------------------------------------------------------------------
// finish — simülasyon sonu bellek temizliği
// -----------------------------------------------------------------------------
void MeshRouting::finish()
{
    cancelAndDelete(cadTimer_);       cadTimer_       = nullptr;
    cancelAndDelete(cadEndTimer_);    cadEndTimer_    = nullptr;
    cancelAndDelete(rxTimeoutTimer_); rxTimeoutTimer_ = nullptr;
}

// =============================================================================
// Public API — Yönlendirme
// =============================================================================

// -----------------------------------------------------------------------------
// selectNextHop
//   Komşu tablosunu C_i ile sırala; darboğaz varsa 2. komşuya geç.
// -----------------------------------------------------------------------------
L3Address MeshRouting::selectNextHop(double txPower_dBm)
{
    purgeStaleNeighbors();

    auto sorted = getSortedNeighbors(txPower_dBm);

    if (sorted.empty()) {
        EV_WARN << "[MeshRouting] Komşu tablosu boş — yönlendirme yapılamıyor.\n";
        return L3Address();   // Unspecified
    }

    const NeighborEntry& best = sorted[0].second;
    emit(routingCostSignal_, best.cachedCost);

    EV_INFO << "[MeshRouting] Komşu sıralaması:\n";
    for (size_t i = 0; i < sorted.size() && i < 3; ++i) {
        const auto& e = sorted[i].second;
        EV_INFO << "  [" << i << "] " << sorted[i].first
                << "  C=" << e.cachedCost
                << "  RSSI=" << e.rssi_dBm << "dBm"
                << "  Q=" << e.queueOccupancy * 100.0 << "%"
                << "  H=" << e.hopCountToGateway
                << (e.isOnlineGateway ? "  [ONLINE-GW]" : "") << "\n";
    }

    // ── Darboğaz koruması ─────────────────────────────────────────────────────
    // 1. komşunun kuyruğu congestionThreshold'u (varsayılan %80) aşıyorsa,
    // listedeki 2. komşu (fallback) kullanılır.
    if (best.queueOccupancy >= congestionThreshold_) {
        emit(congestionEventSignal_, (long)1);

        EV_WARN << "[MeshRouting] DARBOĞAZ tespit edildi → 1. komşu "
                << sorted[0].first
                << "  Q=" << best.queueOccupancy * 100.0 << "%"
                << " >= eşik %" << congestionThreshold_ * 100.0 << "\n";

        if (sorted.size() >= 2) {
            const NeighborEntry& fallback = sorted[1].second;
            EV_INFO << "[MeshRouting] Fallback seçildi: " << sorted[1].first
                    << "  C=" << fallback.cachedCost << "\n";
            emit(routingCostSignal_, fallback.cachedCost);
            return sorted[1].first;
        }

        // Fallback komşu yok; darboğazlı 1. komşuyla devam et
        EV_WARN << "[MeshRouting] Fallback komşu bulunamadı — "
                   "1. komşu kullanılıyor (darboğaz riski mevcut).\n";
    }

    return sorted[0].first;
}

// -----------------------------------------------------------------------------
// updateNeighbor — komşu tablosuna ekle veya güncelle
// -----------------------------------------------------------------------------
void MeshRouting::updateNeighbor(const L3Address& addr,
                                  double           rssi_dBm,
                                  int              hopCount,
                                  double           queueOccupancy,
                                  bool             isOnlineGateway)
{
    auto it = neighborTable_.find(addr);

    if (it == neighborTable_.end()) {
        NeighborEntry e;
        e.address           = addr;
        e.rssi_dBm          = rssi_dBm;
        e.hopCountToGateway = hopCount;
        e.queueOccupancy    = queueOccupancy;
        e.isOnlineGateway   = isOnlineGateway;
        e.lastSeen          = simTime();
        e.cachedCost        = computeCost(e, txPower_dBm_);
        neighborTable_[addr] = e;

        EV_INFO << "[MeshRouting] Yeni komşu: " << addr
                << "  RSSI=" << rssi_dBm << "dBm"
                << "  H=" << hopCount
                << "  C=" << e.cachedCost
                << (isOnlineGateway ? "  [ONLINE-GW]" : "") << "\n";
    }
    else {
        NeighborEntry& e    = it->second;
        e.rssi_dBm          = rssi_dBm;
        e.hopCountToGateway = hopCount;
        e.queueOccupancy    = queueOccupancy;
        e.isOnlineGateway   = isOnlineGateway;
        e.lastSeen          = simTime();
        e.cachedCost        = computeCost(e, txPower_dBm_);

        EV_DETAIL << "[MeshRouting] Komşu güncellendi: " << addr
                  << "  RSSI=" << rssi_dBm << "dBm  C=" << e.cachedCost << "\n";
    }
}

// -----------------------------------------------------------------------------
// purgeStaleNeighbors — neighborTimeout süresi dolan girişleri sil
// -----------------------------------------------------------------------------
void MeshRouting::purgeStaleNeighbors()
{
    const simtime_t threshold = simTime() - neighborTimeout_s_;

    for (auto it = neighborTable_.begin(); it != neighborTable_.end(); ) {
        if (it->second.lastSeen < threshold) {
            EV_INFO << "[MeshRouting] Stale komşu silindi: " << it->first
                    << "  (son=" << it->second.lastSeen << "s, şimdi="
                    << simTime() << "s)\n";
            it = neighborTable_.erase(it);
        }
        else {
            ++it;
        }
    }
}

// =============================================================================
// Maliyet Fonksiyonu
// =============================================================================

// -----------------------------------------------------------------------------
// computeCost  →  C_i = α·(P_tx/|RSSI_i|) + β·(Q_i/Q_max) + γ·H_i
// -----------------------------------------------------------------------------
double MeshRouting::computeCost(const NeighborEntry& n, double txPower_dBm) const
{
    // Geçersiz RSSI koruması: RSSI ≥ 0 fiziksel olarak anlamsız
    if (n.rssi_dBm >= 0.0) {
        EV_WARN << "[MeshRouting] computeCost: geçersiz RSSI="
                << n.rssi_dBm << " — maliyet=INF\n";
        return std::numeric_limits<double>::max();
    }

    // α terimi: sinyal kalitesi maliyeti
    //   |RSSI| büyük (sinyal zayıf) → P_tx/|RSSI| küçük → düşük α maliyeti
    //   Bu PDF formülasyonuna birebir sadıktır.
    //   Not: Sinyal ne kadar zayıfsa enerji harcaması o kadar çok olduğu için
    //   V2'de bu terimi tersine çevirmek (rssiAbs/P_tx) tartışılabilir.
    const double rssiAbs    = -n.rssi_dBm;
    const double signalTerm = txPower_dBm / rssiAbs;

    // β terimi: kuyruk doluluk oranı [0.0..1.0]
    const double queueTerm  = n.queueOccupancy;

    // γ terimi: internete erişen gateway'e kalan hop sayısı
    //   İnterneti olan komşu (isOnlineGateway=true) → hopCount=0 → γ·0=0 → düşük maliyet
    const double hopTerm    = static_cast<double>(
                                  n.isOnlineGateway ? 0 : n.hopCountToGateway);

    return alpha_ * signalTerm + beta_ * queueTerm + gamma_ * hopTerm;
}

// -----------------------------------------------------------------------------
// getSortedNeighbors — C_i'ye göre artan sırada (index 0 = en iyi)
// -----------------------------------------------------------------------------
std::vector<std::pair<L3Address, NeighborEntry>>
MeshRouting::getSortedNeighbors(double txPower_dBm) const
{
    std::vector<std::pair<L3Address, NeighborEntry>> result;
    result.reserve(neighborTable_.size());

    for (const auto& kv : neighborTable_) {
        NeighborEntry e = kv.second;
        e.cachedCost    = computeCost(e, txPower_dBm);
        result.emplace_back(kv.first, e);
    }

    // Artan C_i sırası: [0] en iyi (minimum maliyet)
    std::sort(result.begin(), result.end(),
        [](const std::pair<L3Address, NeighborEntry>& a,
           const std::pair<L3Address, NeighborEntry>& b) {
            return a.second.cachedCost < b.second.cachedCost;
        });

    return result;
}

// =============================================================================
// Güç Durum Makinesi
// =============================================================================

// -----------------------------------------------------------------------------
// enterDeepSleep — radyo kapalı, 15 µA, cadInterval sonra CAD taraması
// -----------------------------------------------------------------------------
void MeshRouting::enterDeepSleep()
{
    cancelEvent(cadTimer_);
    cancelEvent(cadEndTimer_);
    cancelEvent(rxTimeoutTimer_);

    sleepEntryTime_ = simTime();

    currentState_ = PowerState::DEEP_SLEEP;
    emit(powerStateSignal_, static_cast<long>(0));

    EV_INFO << "[MeshRouting] → DEEP_SLEEP  [15µA]"
            << "  (CAD: t+" << cadInterval_s_ << "s)\n";

    scheduleAt(simTime() + cadInterval_s_, cadTimer_);
}

// -----------------------------------------------------------------------------
// enterCAD — Channel Activity Detection (~5 ms, ~10 mA)
// -----------------------------------------------------------------------------
void MeshRouting::enterCAD()
{
    currentState_ = PowerState::CAD;
    emit(powerStateSignal_, static_cast<long>(1));

    EV_INFO << "[MeshRouting] → CAD  [~10mA, " << cadDuration_ms_ << "ms]\n";

    scheduleAt(simTime() + cadDuration_ms_ / 1000.0, cadEndTimer_);
}

// -----------------------------------------------------------------------------
// enterActiveRx — preamble tespit edildi, Wake-on-Radio (120 mA)
// -----------------------------------------------------------------------------
void MeshRouting::enterActiveRx()
{
    cancelEvent(rxTimeoutTimer_);

    currentState_ = PowerState::ACTIVE_RX;
    emit(powerStateSignal_, static_cast<long>(2));

    EV_INFO << "[MeshRouting] → ACTIVE_RX  [120mA, WoR]"
            << "  (timeout=" << activeRxTimeout_s_ << "s)\n";

    scheduleAt(simTime() + activeRxTimeout_s_, rxTimeoutTimer_);
}

// -----------------------------------------------------------------------------
// enterProcessing — paket alındı, C_i hesaplaması (radyo uyku, CPU aktif)
// -----------------------------------------------------------------------------
void MeshRouting::enterProcessing()
{
    cancelEvent(rxTimeoutTimer_);

    currentState_ = PowerState::PROCESSING;
    emit(powerStateSignal_, static_cast<long>(3));

    EV_INFO << "[MeshRouting] → PROCESSING  (C_i hesaplanıyor, next-hop seçiliyor)\n";
}

// -----------------------------------------------------------------------------
// enterActiveTx — next-hop'a iletim (120 mA)
// -----------------------------------------------------------------------------
void MeshRouting::enterActiveTx()
{
    currentState_ = PowerState::ACTIVE_TX;
    emit(powerStateSignal_, static_cast<long>(4));

    EV_INFO << "[MeshRouting] → ACTIVE_TX  [120mA]\n";

    // Simülasyonda TX senkron tamamlanır; gerçek donanımda TX_DONE kesmesi
    // beklenir (SX1262 DIO1). V2'de bu asenkron yapılacak.
    enterDeepSleep();
}

// -----------------------------------------------------------------------------
// onCADComplete — CAD sonucu: preamble var mı?
// -----------------------------------------------------------------------------
void MeshRouting::onCADComplete(bool preambleDetected)
{
    if (preambleDetected) {
        EV_INFO << "[MeshRouting] CAD → preamble ALGILANDI (WoR tetiklendi)\n";
        enterActiveRx();
    }
    else {
        // Uyku süresi istatistiği
        if (sleepEntryTime_ > simtime_t::ZERO) {
            const simtime_t dur = simTime() - sleepEntryTime_;
            emit(sleepDurationSignal_, dur.dbl());
        }
        EV_INFO << "[MeshRouting] CAD → kanal boş → DEEP_SLEEP\n";
        enterDeepSleep();
    }
}

// -----------------------------------------------------------------------------
// onRxTimeout — ACTIVE_RX döneminde paket gelmedi → uy
// -----------------------------------------------------------------------------
void MeshRouting::onRxTimeout()
{
    EV_WARN << "[MeshRouting] ACTIVE_RX timeout (" << activeRxTimeout_s_
            << "s) — paket alınamadı → DEEP_SLEEP\n";
    enterDeepSleep();
}
