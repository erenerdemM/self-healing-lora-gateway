// =============================================================================
// HybridRouting.cc — Hibrit Ağ Geçidinin Kendi-Kendini İyileştirme Zekası
// =============================================================================
// Proje: Self-Healing Hybrid LoRa Gateway — DEÜ EEE Bitirme
//   Eren ERDEM (2020502028), Melisa KURAL (2021502041)
//
// MİMARİ SORUMLULUK (Gateway Rota Hesaplamaz, Sadece Hedef Belirler):
//   HybridGateway interneti izler; kopunca en iyi hedef GW'yi seçer ve
//   SensorDataPacket'i o hedefe doğru mesh ağına yayınlar.
//   MeshNode'lar (MeshRouting.cc) next-hop kararını kendi verir.
//   Bölgesel çöküşte SosBeaconPacket ile AjanGateway'leri uyandırır.
//
// BACKHAUL DÖNGÜSÜ:
//   backhaulCheckTimer (100 ms) ──► checkBackhaulStatus()
//       İnternet VAR  → paket Ethernet arayüzüne (Network Server)
//       İnternet YOK  → selectBestNeighborGateway() → SensorDataPacket
//                         + hiç Online-GW yoksa veya tüm kuyruklar doluysa
//                           → SosBeaconPacket (hint: REGIONAL_FAILURE / CONGESTION)
//
// REASONCODE KODU ŞEMASI (SosBeaconPacket):
//   0 = CONGESTION       → tüm komşular Q >= congestionThreshold
//   1 = REGIONAL_FAILURE → tablo boş veya tüm komşular stale
//   2 = GATEWAY_DOWN     → en az bir Online-GW vardı; şimdi hiç yok
//   3 = LINK_DEGRADED    → (rezerve, gelecek sürüm)
// =============================================================================

#include "HybridRouting.h"
#include "MeshPacket_m.h"

#include "inet/common/packet/Packet.h"

#include <algorithm>
#include <limits>
#include <numeric>
#include <sstream>

using namespace lora_mesh;

Define_Module(HybridRouting);

// =============================================================================
// OMNeT++ Yaşam Döngüsü
// =============================================================================

void HybridRouting::initialize(int stage)
{
    cSimpleModule::initialize(stage);

    if (stage == inet::INITSTAGE_LOCAL) {

        // ── Maliyet fonksiyonu ağırlıkları ───────────────────────────────────
        alpha_               = par("alpha");
        beta_                = par("beta");
        gamma_               = par("gamma");
        congestionThreshold_ = par("congestionThreshold");
        txPower_dBm_         = par("txPower_dBm");

        // ── Backhaul / CAD parametreler ───────────────────────────────────────
        backhaulCheckInterval_s_ = par("backhaulCheckInterval");
        cadInterval_s_           = par("cadInterval");
        cadDuration_ms_          = par("cadDuration");
        activeRxTimeout_s_       = par("activeRxTimeout");
        neighborTimeout_s_       = par("neighborTimeout");

        // ── LoRaWAN Gateway downlink TX parametreleri (BTK KET / ETSI EN 300 220-2) ─
        bandMTxPower_dBm_ = par("bandMTxPower_dBm");
        bandMDutyCycle_   = par("bandMDutyCycle");
        rx2TxPower_dBm_   = par("rx2TxPower_dBm");
        rx2DutyCycle_     = par("rx2DutyCycle");
        rx2Frequency_Hz_  = par("rx2Frequency");
        txQuotaWindow_s_  = par("txQuotaWindow");
        antennaGain_dBi_  = par("antennaGain_dBi");
        numDemodulators_  = par("numDemodulators");

        // ── Beacon / kuyruk parametreleri ──────────────────────────────
        beaconInterval_s_ = par("beaconInterval");
        beaconRssi_       = par("beaconRssi");
        maxQueueSize_     = par("maxQueueSize");
        sensorPacketRate_ = par("sensorPacketRate");
        backhaulCutTime_s_= par("backhaulCutTime");
        currentQueueOcc_  = 0.05 + uniform(0.0, 0.08);  // rastgele başlangıç
        failoverLogCounter_ = 0;

        // Topoloji kısıt listesini parse et
        std::string listStr = par("meshNeighborList").stringValue();
        if (!listStr.empty()) {
            std::istringstream iss(listStr);
            std::string token;
            while (iss >> token) meshNeighborList_.push_back(token);
            EV_INFO << "[HybridRouting] meshNeighborList parse edildi: "
                    << meshNeighborList_.size() << " komşu — " << listStr << "\n";
        } else {
            EV_INFO << "[HybridRouting] meshNeighborList boş — tüm ağa broadcast mod.\n";
        }

        // omnetpp.ini örnek:
        //   [V2-Failover]
        //   **.hybridGW1.routingAgent.backhaulUp = false   # baştan kesilmiş
        //   # veya t=200s'de dinamik: scheduleAt ile setBackhaulUp(false) çağrısı
        isBackhaulUp_ = par("backhaulUp");
        // backhaulRuntimeUp başlangıç değerini senkronize et (PacketForwarder okur)
        par("backhaulRuntimeUp").setBoolValue(isBackhaulUp_);
        EV_INFO << "[HybridRouting] backhaulUp=" << (isBackhaulUp_ ? "true (ONLINE)" : "false (FAILOVER)") << "\n";

        // ── Güç durum makinesi başlangıcı ─────────────────────────────────────
        currentPowerState_ = PowerState::DEEP_SLEEP;

        // ── İşlemci gecikmesi (STM32 SPI+DMA+ISR modeli) ─────────────────────
        processingDelay_ms_ = par("processingDelay");
        EV_INFO << "[HybridRouting] processingDelay=" << processingDelay_ms_
                << "ms (0=sıfır-gecikme, >0=STM32 gerçekçi model)\n";

        // ── İstatistik sinyallerini kaydet ────────────────────────────────────
        powerStateSignal_      = registerSignal("powerState");
        routingCostSignal_     = registerSignal("routingCost");
        congestionEventSignal_ = registerSignal("congestionEvent");
        droppedPacketSignal_   = registerSignal("droppedPacket");

        // ── Zamanlayıcıları oluştur ───────────────────────────────────────────
        backhaulTimer_ = new cMessage("backhaulCheckTimer");
        cadTimer_      = new cMessage("cadTimer");
        sleepTimer_    = new cMessage("rxTimeoutTimer");

        // ── LoRaWAN GW BTK/ETSI profil başlangıç logu ─────────────────────
        {
            const double effTx      = bandMTxPower_dBm_ - antennaGain_dBi_;
            const double bandM_quot = txQuotaWindow_s_ * bandMDutyCycle_;
            const double rx2_quot   = txQuotaWindow_s_ * rx2DutyCycle_;
            EV_INFO << "[HybridRouting] LoRaWAN GW BTK/ETSI Profil:\n"
                    << "  SX1303+SX1250: -141dBm hassasiyet,  "
                    << numDemodulators_ << " demodülatör (8ch×2)\n"
                    << "  Band M (868.0-868.6MHz): TX=" << effTx << "dBm ERP"
                    << "  DC=" << bandMDutyCycle_ * 100.0 << "%"
                    << "  kota=" << bandM_quot << "s/saat\n"
                    << "  Band P RX2 (" << rx2Frequency_Hz_ / 1e6 << "MHz): TX="
                    << rx2TxPower_dBm_ << "dBm"
                    << "  DC=" << rx2DutyCycle_ * 100.0 << "%"
                    << "  kota=" << rx2_quot << "s/saat\n"
                    << "  Anten kazancı=" << antennaGain_dBi_
                    << "dBi → EIRP düzeltmesi uygulandı\n";
        }

        EV_INFO << "[HybridRouting] initialize tamamlandı."
                << "  backhaulInterval=" << backhaulCheckInterval_s_ << "s"
                << "  α=" << alpha_ << " β=" << beta_ << " γ=" << gamma_
                << "  congThreshold=" << congestionThreshold_ * 100.0 << "%\n";
    }

    if (stage == inet::INITSTAGE_NETWORK_LAYER) {
        // Backhaul izleme döngüsünü başlat
        scheduleAt(simTime() + backhaulCheckInterval_s_, backhaulTimer_);
        EV_INFO << "[HybridRouting] Backhaul timer kuruldu: t+"
                << backhaulCheckInterval_s_ << "s\n";

        // Beacon zamanlayıcısı: komşu tablolarını gerçek verilerle doldurmak için
        beaconTimer_ = new cMessage("beaconTimer");
        scheduleAt(simTime() + beaconInterval_s_, beaconTimer_);
        EV_INFO << "[HybridRouting] Beacon timer kuruldu: t+" << beaconInterval_s_
                << "s  meshAddress=" << par("meshAddress").stringValue() << "\n";

        // İşlemci gecikmesi zamanlayıcısı (geciktirilmiş routing kararı için)
        if (processingDelay_ms_ > 0.0) {
            processTimer_ = new cMessage("processingDelayTimer");
            EV_INFO << "[HybridRouting] ProcessTimer hazır — STM32 ISR gecikmesi="
                    << processingDelay_ms_ << "ms\n";
        }

        // Tek seferlik backhaul kesme zamanlayıcısı
        if (backhaulCutTime_s_ > 0) {
            backhaulCutTimer_ = new cMessage("backhaulCutTimer");
            scheduleAt(backhaulCutTime_s_, backhaulCutTimer_);
            EV_INFO << "[HybridRouting] Backhaul kesme zamanlandı: t="
                    << backhaulCutTime_s_ << "s\n";
        }
    }
}

// =============================================================================
// handleMessage — tüm zamanlayıcı ve dış mesaj akışının merkezi
// =============================================================================
void HybridRouting::handleMessage(cMessage *msg)
{
    // =========================================================================
    // 1. ÖZ-MESAJLAR (zamanlayıcılar)
    // =========================================================================
    if (msg->isSelfMessage()) {

        // ── Beacon yayın zamanlayıcısı ────────────────────────────────────────
        if (msg == beaconTimer_) {
            broadcastBeaconToMeshNeighbors();
            scheduleAt(simTime() + beaconInterval_s_, beaconTimer_);
            return;
        }

        // ── Tek seferlik backhaul kesme zamanlayıcısı ─────────────────────────
        if (backhaulCutTimer_ && msg == backhaulCutTimer_) {
            isBackhaulUp_ = false;
            par("backhaulRuntimeUp").setBoolValue(false);  // PacketForwarder'a bildir
            EV_WARN << "\n[HybridRouting] ████ BACKHAUL KESİNTİSİ ████\n"
                    << "  Zaman: t=" << simTime() << "s\n"
                    << "  Durum: isBackhaulUp_ = false  (FAILOVER modu aktif)\n"
                    << "  Komşu tablosunda " << neighborTable_.size() << " giriş mevcut.\n";
            auto sorted = getSortedNeighbors(txPower_dBm_);
            if (sorted.empty()) {
                EV_WARN << "[HybridRouting] Komşu tablosu BOŞ — failover hedefi belirlenemiyor!\n";
            } else {
                EV_INFO << "[HybridRouting] C_i tablosu (failover anı, α="
                        << alpha_ << " β=" << beta_ << " γ=" << gamma_ << "):\n";
                for (size_t i = 0; i < sorted.size() && i < 5; ++i) {
                    const auto& e = sorted[i].second;
                    double cSig = alpha_ * (txPower_dBm_ / (-e.rssi_dBm));
                    double cQ   = beta_  * e.queueOccupancy;
                    double cH   = gamma_ * (e.isOnlineGateway ? 0 : e.hopCountToGateway);
                    EV_INFO << "    [" << i << "] " << sorted[i].first
                            << "  RSSI=" << e.rssi_dBm << "dBm"
                            << "  Q=" << e.queueOccupancy * 100.0 << "%"
                            << "  H=" << e.hopCountToGateway
                            << (e.isOnlineGateway ? "  [ONLINE-GW]" : "  [relay]")
                            << "  C_i=" << sorted[i].second.cachedCost
                            << "  (α·" << cSig << " + β·" << cQ
                            << " + γ·" << cH << ")\n";
                }
                L3Address best = selectBestNeighborGateway();
                EV_WARN << "[HybridRouting] ★ FAILOVER HEDEFİ: "
                        << (best.isUnspecified() ? "YOK (tablo boş)" : best.str())
                        << "  (en düşük C_i ile seçildi)\n";
            }
            delete msg;
            backhaulCutTimer_ = nullptr;
            return;
        }

        // ── processingDelayTimer: STM32 ISR gecikmesi bitti, routing kararı ver
        if (processTimer_ && msg == processTimer_) {
            cMessage *pm = pendingMsg_;
            pendingMsg_  = nullptr;
            if (pm) processRouteRequest(pm);
            return;
        }

        if (msg == backhaulTimer_) {
            checkBackhaulStatus();
            // Bir sonraki kontrol döngüsünü planla
            scheduleAt(simTime() + backhaulCheckInterval_s_, backhaulTimer_);
            return;
        }

        if (msg == cadTimer_) {
            enterCAD();
            return;
        }

        if (msg == sleepTimer_) {
            // ACTIVE_RX timeout → derin uykuya geç
            EV_INFO << "[HybridRouting] RX timeout → DEEP_SLEEP\n";
            enterDeepSleep();
            return;
        }

        EV_WARN << "[HybridRouting] Bilinmeyen öz-mesaj: "
                << msg->getName() << " — silindi.\n";
        delete msg;
        return;
    }

    // =========================================================================
    // 2. DIŞ MESAJLAR: gate üzerinden gelen paketler
    // =========================================================================
    const int arrGate = msg->getArrivalGateId();

    // ── routeRequestIn: Sensör verisini yönlendir ─────────────────────────────
    //
    // Üst katman (SensorLoRaApp veya ağ katmanı) bir veri paketi iletmek istiyor.
    // Gateway internet durumuna göre paketin nereye gideceğine karar verilir.
    //
    if (arrGate == findGate("routeRequestIn")) {

        EV_INFO << "[HybridRouting] routeRequestIn: yönlendirme talebi alındı.\n";

        // ── STM32 İşlemci Gecikmesi Modeli ───────────────────────────────────
        // Gerçek donanımda SX1303 LoRa MAC → SPI → DMA → ISR → RAM kopyalama
        // ~5-15ms sürer. processingDelay_ms_ > 0 ise mesajı geciktirerek
        // processTimer_ ile doğru zamanda işle.
        if (processingDelay_ms_ > 0.0 && processTimer_) {
            if (pendingMsg_) {
                // Kuyrukta zaten bekleyen mesaj var — Drop-Tail (STM32 single buffer)
                EV_WARN << "[HybridRouting] İşlemci meşgul — Drop-Tail (1 paket düşürüldü)\n";
                emit(droppedPacketSignal_, (long)1);
                delete msg;
            } else {
                pendingMsg_ = msg;
                scheduleAt(simTime() + processingDelay_ms_ / 1000.0, processTimer_);
                EV_INFO << "[HybridRouting] STM32 ISR gecikmesi: " << processingDelay_ms_
                        << "ms sonra routing kararı verilecek.\n";
            }
            return;
        }
        // processingDelay == 0: eski sıfır-gecikme davranışı
        processRouteRequest(msg);
        return;
    }

    // ── neighborUpdateIn: Komşudan RSSI / beacon bilgisi ─────────────────────
    if (arrGate == findGate("neighborUpdateIn")) {
        // Komşu GW veya MeshNode'dan beacon mesajı alindi—güncelle
        if (msg->hasPar("senderAddr")) {
            std::string senderAddr = msg->par("senderAddr").stringValue();
            double rssi_dBm  = msg->par("rssi").doubleValue();
            double queueOcc  = msg->par("queue").doubleValue();
            bool   isOnline  = msg->par("online").boolValue();
            int    hopToGw   = (int)msg->par("hopToGw").longValue();
            L3Address addr(senderAddr.c_str());
            if (!addr.isUnspecified())
                updateNeighbor(addr, rssi_dBm, hopToGw, queueOcc, isOnline);
            else
                EV_WARN << "[HybridRouting] Beacon: geçersiz adres '" << senderAddr << "'\n";
        }
        delete msg;
        return;
    }

    EV_WARN << "[HybridRouting] Bilinmeyen gate mesajı (gateId="
            << arrGate << ") — silindi.\n";
    delete msg;
}

// =============================================================================
// processRouteRequest — routeRequestIn gelen paketi işle
//   processingDelay_ > 0 ise processTimer_ sonrasında çağrılır.
//   processingDelay_ = 0 ise doğrudan handleMessage'dan senkron çağrılır.
// =============================================================================
void HybridRouting::processRouteRequest(cMessage *msg)
{
    purgeStaleNeighbors();

    if (checkBackhaulAlive()) {
        EV_WARN << "[HybridRouting] ◆ SENARYO A — İNTERNET VAR ◆\n"
                << "  t=" << simTime() << "s  addr=" << par("meshAddress").stringValue() << "\n"
                << "  Sensör verisi doğrudan NetworkServer'a iletiliyor.\n"
                << "  MESH'E SENSÖR VERİSİ GÖNDERİLMİYOR — Sadece beacon yayınlanır.\n";

        cMessage *decision = new cMessage("routeDecision_direct");
        decision->setKind(0);
        if (gate("routeDecisionOut")->isConnected())
            send(decision, "routeDecisionOut");
        else {
            EV_WARN << "[HybridRouting] routeDecisionOut bağlı değil — karar düşürüldü (V1).\n";
            delete decision;
        }
        delete msg;
    } else {
        EV_WARN << "[HybridRouting] ◆ SENARYO B — İNTERNET KESİNTİSİ ◆\n"
                << "  t=" << simTime() << "s  addr=" << par("meshAddress").stringValue() << "\n"
                << "  Sensör verisi MESH ağına aktarılıyor!\n"
                << "  En düşük C_i'ye sahip ONLINE-GW hedef seçiliyor...\n";
        forwardToMesh(msg);
    }
}

// =============================================================================
// finish — simülasyon sonu temizlik
// =============================================================================
void HybridRouting::finish()
{
    cancelAndDelete(backhaulTimer_);   backhaulTimer_     = nullptr;
    cancelAndDelete(cadTimer_);        cadTimer_          = nullptr;
    cancelAndDelete(sleepTimer_);      sleepTimer_        = nullptr;
    cancelAndDelete(beaconTimer_);     beaconTimer_       = nullptr;
    cancelAndDelete(backhaulCutTimer_); backhaulCutTimer_ = nullptr;
    cancelAndDelete(processTimer_);    processTimer_      = nullptr;
    if (pendingMsg_) { delete pendingMsg_; pendingMsg_ = nullptr; }

    EV_INFO << "[HybridRouting] finish: zamanlayıcılar temizlendi. "
            << "Komşu tablosu boyutu: " << neighborTable_.size() << "\n";
}

// =============================================================================
// Backhaul İzleme
// =============================================================================

// -----------------------------------------------------------------------------
// checkBackhaulStatus — periyodik kontrol (100 ms)
//
// Simülasyonda "internet kesintisi" omnetpp.ini'deki bir parametre ya da
// dış sinyal aracılığıyla modellenebilir. Şu aşamada deterministik simülasyon
// için isBackhaulUp_ boolean'ı kullanıyoruz.
// Gerçek uygulamada: NIC'e ICMP ping / TCP probe sonucu buraya yazılır.
// -----------------------------------------------------------------------------
void HybridRouting::checkBackhaulStatus()
{
    purgeStaleNeighbors();

    // ── Kuyruk doluluk dinamiği ───────────────────────────────────────────────
    // Backhaul UP: WAN kanal boşaltır, kuyruk küçük kalır
    // Backhaul DOWN: sensör paketleri birikir, kuyruk dolar
    //
    // Gerçek STM32 kapasitesi: maxQueueSize_ × ~50B ≈ 50 × 50B = 2.5 KB
    // Bu modelde "occ = 1.0" → maxQueueSize_ pakede eşdeğer doluluk.
    // Drop-Tail: occ zaten >= 1.0 iken yeni paketler düşürülür.
    if (isBackhaulUp_) {
        currentQueueOcc_ = 0.985 * currentQueueOcc_
                         + 0.0005 * sensorPacketRate_;
    } else {
        const double incoming = 0.0003 * sensorPacketRate_;
        const double projected = currentQueueOcc_ + incoming;

        // Drop-Tail: kuyruk zaten %100 doluysa gelen paketleri say ve düşür
        if (currentQueueOcc_ >= 1.0) {
            // Her 100ms kontrol aralığında sensorPacketRate_*0.1 paket gelmiştir;
            // hepsi düşürülmüştür → Drop-Tail sinyali gönder
            const long droppedNow = static_cast<long>(sensorPacketRate_ * backhaulCheckInterval_s_);
            if (droppedNow > 0) {
                emit(droppedPacketSignal_, droppedNow);
                EV_WARN << "[HybridRouting] DROP-TAIL: kuyruk DOLU (%"
                        << currentQueueOcc_ * 100.0 << ") — " << droppedNow
                        << " paket düşürüldü (STM32 SRAM: maxQueueSize="
                        << maxQueueSize_ << " pkt)\n";
            }
        }
        currentQueueOcc_ = std::min(1.0, projected);
    }
    currentQueueOcc_ = std::max(0.0, currentQueueOcc_);

    if (!checkBackhaulAlive()) {

        // Her 5s'de bir (50 * 0.1s = 5s) komşu tablosunu logla
        ++failoverLogCounter_;
        if (failoverLogCounter_ % 50 == 1) {
            auto sorted = getSortedNeighbors(txPower_dBm_);
            if (!sorted.empty()) {
                EV_INFO << "[HybridRouting] ─── FAILOVER C_i Tablosu — t="
                        << simTime() << "s ───\n";
                for (size_t i = 0; i < sorted.size() && i < 5; ++i) {
                    const auto& e = sorted[i].second;
                    EV_INFO << "  [" << i << "] " << sorted[i].first
                            << "  RSSI=" << e.rssi_dBm << "dBm"
                            << "  Q=" << e.queueOccupancy * 100.0 << "%"
                            << (e.isOnlineGateway ? "  [ONLINE-GW]" : "  [relay]")
                            << "  C_i=" << e.cachedCost << "\n";
                }
                EV_INFO << "[HybridRouting] → Seçilen hedef: "
                        << selectBestNeighborGateway() << "\n";
            } else {
                EV_WARN << "[HybridRouting] !! Backhaul KOPUK — komşu tablosu boş!\n";
            }
        }

        // Online komşu sayısını hesapla
        int onlineCount = countOnlineGateways();

        if (onlineCount == 0) {
            // Tüm komşular offline ya da tablo boş → Bölgesel Çöküş
            EV_WARN << "[HybridRouting] ⚠ BÖLGESEL ÇÖKÜŞ tespiti — komşu tablosu boş veya tümü offline!\n"
                    << "  → İnternet GİTTİ, mesh yolu YOK. Paket kuyrukta beklemede.\n";
            // SOS beacon sadece routeDecisionOut bağlıysa gönderilir (V2+)
            if (gate("routeDecisionOut")->isConnected())
                broadcastSosBeacon(/*reasonCode=*/1);

        } else {
            // Komşular var ama hepsi darboğazda mı?
            bool allCongested = areAllNeighborsCongested();
            if (allCongested) {
                EV_WARN << "[HybridRouting] TÜM KOMŞULAR DARBOĞAZDA\n";
                if (gate("routeDecisionOut")->isConnected())
                    broadcastSosBeacon(/*reasonCode=*/0);
            }
        }
    }
}

// -----------------------------------------------------------------------------
// checkBackhaulAlive — internet bağlantısı sağlıklı mı?
//
// Simülasyonda: isBackhaulUp_ bayrağı harici bir event veya omnetpp.ini
// parametresiyle değiştirilebilir (örn. t=200s'de false yapılır).
// HybridGateway.ned içinde `backhaulUp` parametresi göz önüne alınabilir.
// -----------------------------------------------------------------------------
bool HybridRouting::checkBackhaulAlive() const
{
    return isBackhaulUp_;
}

// =============================================================================
// Mesh Failover — Paket Kapsülleme ve İletimi
// =============================================================================

// -----------------------------------------------------------------------------
// forwardToMesh — SensorDataPacket oluştur, en iyi komşu GW'ye ilet
// -----------------------------------------------------------------------------
void HybridRouting::forwardToMesh(cMessage *originalMsg)
{
    // ── En iyi komşu Gateway adresini bul ─────────────────────────────────────
    L3Address bestGW = selectBestNeighborGateway();

    if (bestGW.isUnspecified()) {
        EV_WARN << "[HybridRouting] forwardToMesh: hedef GW bulunamadı — "
                << "SOS Beacon yayınlanıyor.\n";
        broadcastSosBeacon(/*reasonCode=*/2);  // GATEWAY_DOWN
        delete originalMsg;
        return;
    }

    // ── SensorDataPacket oluştur ve inet::Packet sarmala ─────────────────────
    // FieldsChunk türevleri (MeshPacket, SensorDataPacket) cMessage değil;
    // INET standardına göre inet::Packet sarmalayıcı içine konur.
    auto chunk = makeShared<SensorDataPacket>();
    chunk->setSeqNum(static_cast<short>(seqCounter_));
    chunk->setDestinationGateway(bestGW);
    chunk->setHopCount(0);
    chunk->setSequenceNumber(seqCounter_++);
    chunk->setChunkLength(inet::B(20));  // SensorDataPacket sabit boyutu
    chunk->markImmutable();

    auto pkt = new inet::Packet("sensorData_mesh");
    pkt->insertAtBack(chunk);

    EV_INFO << "[HybridRouting] SensorDataPacket → Hedef GW: " << bestGW
            << "  seqNum=" << (seqCounter_ - 1) << "\n";

    emit(routingCostSignal_, computeCostForAddress(bestGW));

    // ── sendDirect ile hedef MeshNode'un routeRequestIn kapısına ilet ─────────
    // bestGW → MeshNode'un meshAddress parametresiyle eşleştir;
    // eşleşen modülün meshRouting submodülüne sendDirect gönder.
    // Bu pattern, beacon'ların neighborUpdateIn'e gönderilmesiyle aynıdır.
    bool sent = false;
    cModule *network = getSimulation()->getSystemModule();
    for (cModule::SubmoduleIterator it(network); !it.end(); ++it) {
        cModule *node = *it;
        if (!node) continue;
        cModule *mr = node->getSubmodule("meshRouting");
        if (!mr || mr->findGate("routeRequestIn") < 0) continue;
        L3Address nodeAddr(mr->par("meshAddress").stringValue());
        if (!nodeAddr.isUnspecified() && nodeAddr == bestGW) {
            EV_INFO << "[HybridRouting] sendDirect → " << node->getName()
                    << ".meshRouting.routeRequestIn  (destGW=" << bestGW << ")\n";
            sendDirect(pkt, mr, "routeRequestIn");
            sent = true;
            break;
        }
    }
    if (!sent) {
        EV_WARN << "[HybridRouting] forwardToMesh: hedef MeshNode ('" << bestGW
                << "') bulunamadı — SensorDataPacket düşürüldü.\n";
        delete pkt;
    }

    delete originalMsg;
}

// -----------------------------------------------------------------------------
// selectBestNeighborGateway
//   Komşu tablosunu C_i ile sırala; Online olan ve kuyruğu boş olan en iyi GW'yi seç.
//   Darboğaz koruması: Q_i >= congestionThreshold → 2. komşuya fallback.
// -----------------------------------------------------------------------------
L3Address HybridRouting::selectBestNeighborGateway()
{
    purgeStaleNeighbors();

    auto sorted = getSortedNeighbors(txPower_dBm_);

    if (sorted.empty()) {
        EV_WARN << "[HybridRouting] selectBestNeighborGateway: komşu tablosu boş.\n";
        return L3Address();
    }

    EV_INFO << "[HybridRouting] Komşu sıralaması (" << sorted.size() << " giriş):\n";
    for (size_t i = 0; i < sorted.size() && i < 4; ++i) {
        const auto& e = sorted[i].second;
        EV_INFO << "  [" << i << "] " << sorted[i].first
                << "  C=" << e.cachedCost
                << "  RSSI=" << e.rssi_dBm << "dBm"
                << "  Q=" << e.queueOccupancy * 100.0 << "%"
                << "  H=" << e.hopCountToGateway
                << (e.isOnlineGateway ? "  [ONLINE-GW]" : "") << "\n";
    }

    const NeighborEntry& best = sorted[0].second;
    emit(routingCostSignal_, best.cachedCost);

    // Darboğaz koruması
    if (best.queueOccupancy >= congestionThreshold_) {
        emit(congestionEventSignal_, (long)1);
        EV_WARN << "[HybridRouting] DARBOĞAZ: 1. komşu Q="
                << best.queueOccupancy * 100.0 << "% ≥ eşik %"
                << congestionThreshold_ * 100.0 << "\n";

        if (sorted.size() >= 2) {
            EV_INFO << "[HybridRouting] Fallback seçildi: " << sorted[1].first
                    << "  C=" << sorted[1].second.cachedCost << "\n";
            return sorted[1].first;
        }

        EV_WARN << "[HybridRouting] Fallback komşu yok — darboğazlı 1. komşu kullanılıyor.\n";
    }

    return sorted[0].first;
}

// =============================================================================
// SOS Beacon
// =============================================================================

// -----------------------------------------------------------------------------
// broadcastSosBeacon — Bölgesel çöküşte / darboğazda derin uyku GW'leri uyandır
// reasonCode:
//   0 = CONGESTION       (tüm komşular Q >= eşik)
//   1 = REGIONAL_FAILURE (komşu tablosu boş / stale)
//   2 = GATEWAY_DOWN     (online-GW komşu kalmadı)
//   3 = LINK_DEGRADED    (rezerve)
// -----------------------------------------------------------------------------
void HybridRouting::broadcastSosBeacon(int reasonCode)
{
    // Anlık kuyruk doluluk ve RSSI istatistiklerini hesapla
    double avgQ    = 0.0;
    double avgRssi = 0.0;
    if (!neighborTable_.empty()) {
        for (const auto& kv : neighborTable_) {
            avgQ    += kv.second.queueOccupancy;
            avgRssi += kv.second.rssi_dBm;
        }
        avgQ    /= static_cast<double>(neighborTable_.size());
        avgRssi /= static_cast<double>(neighborTable_.size());
    }
    int onlineGW = countOnlineGateways();

    // FieldsChunk türevi → makeShared + inet::Packet sarmala
    auto chunk = makeShared<SosBeaconPacket>();
    chunk->setIsUrgent(true);
    chunk->setReasonCode(reasonCode);
    chunk->setSenderNodeId(getParentModule()->getFullName());
    chunk->setOnlineGatewayCount(onlineGW);
    chunk->setCongestionLevel(avgQ);
    chunk->setAverageRssi_dBm(avgRssi);
    chunk->setDestinationGateway(L3Address("255.255.255.255"));
    chunk->setHopCount(0);
    chunk->setSequenceNumber(seqCounter_++);
    chunk->setChunkLength(inet::B(48));  // SosBeaconPacket sabit boyutu
    chunk->markImmutable();

    auto pkt = new inet::Packet("sosBeacon");
    pkt->insertAtBack(chunk);

    const char* codeNames[] = {"CONGESTION", "REGIONAL_FAILURE", "GATEWAY_DOWN", "LINK_DEGRADED"};
    EV_ERROR << "[HybridRouting] SOS BEACON YAYINLANDI → "
             << codeNames[reasonCode < 4 ? reasonCode : 0]
             << "  onlineGW=" << onlineGW
             << "  avgQ=" << avgQ * 100.0 << "%"
             << "  avgRSSI=" << avgRssi << "dBm\n";

    emit(congestionEventSignal_, (long)reasonCode);

    if (gate("routeDecisionOut")->isConnected())
        send(pkt, "routeDecisionOut");
    else {
        EV_WARN << "[HybridRouting] routeDecisionOut bağlı değil — SOS beacon düşürüldü (V1).\n";
        delete pkt;
    }
}

// =============================================================================
// Public API
// =============================================================================

// -----------------------------------------------------------------------------
// selectNextHop — Genel amaçlı next-hop seçimi (MeshRouting API uyumlu)
// -----------------------------------------------------------------------------
L3Address HybridRouting::selectNextHop(double txPower_dBm)
{
    purgeStaleNeighbors();
    auto sorted = getSortedNeighbors(txPower_dBm);

    if (sorted.empty())
        return L3Address();

    const NeighborEntry& best = sorted[0].second;
    if (best.queueOccupancy >= congestionThreshold_ && sorted.size() >= 2) {
        emit(congestionEventSignal_, (long)1);
        return sorted[1].first;
    }
    return sorted[0].first;
}

// -----------------------------------------------------------------------------
// updateNeighbor — Komşu tablosuna ekle veya güncelle
// -----------------------------------------------------------------------------
void HybridRouting::updateNeighbor(const L3Address& addr,
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

        EV_INFO << "[HybridRouting] Yeni komşu: " << addr
                << "  RSSI=" << rssi_dBm << "dBm"
                << "  H=" << hopCount
                << "  C=" << e.cachedCost
                << (isOnlineGateway ? "  [ONLINE-GW]" : "") << "\n";
    } else {
        NeighborEntry& e    = it->second;
        e.rssi_dBm          = rssi_dBm;
        e.hopCountToGateway = hopCount;
        e.queueOccupancy    = queueOccupancy;
        e.isOnlineGateway   = isOnlineGateway;
        e.lastSeen          = simTime();
        e.cachedCost        = computeCost(e, txPower_dBm_);

        EV_DETAIL << "[HybridRouting] Komşu güncellendi: " << addr
                  << "  RSSI=" << rssi_dBm << "dBm  C=" << e.cachedCost << "\n";
    }
}

// -----------------------------------------------------------------------------
// purgeStaleNeighbors — neighborTimeout_s_ dolan girişleri sil
// -----------------------------------------------------------------------------
void HybridRouting::purgeStaleNeighbors()
{
    const simtime_t threshold = simTime() - neighborTimeout_s_;

    for (auto it = neighborTable_.begin(); it != neighborTable_.end(); ) {
        if (it->second.lastSeen < threshold) {
            EV_INFO << "[HybridRouting] Stale komşu silindi: " << it->first
                    << "  (lastSeen=" << it->second.lastSeen
                    << "s, şimdi=" << simTime() << "s)\n";
            it = neighborTable_.erase(it);
        } else {
            ++it;
        }
    }
}

// =============================================================================
// Maliyet Fonksiyonu
// =============================================================================

// -----------------------------------------------------------------------------
// computeCost — C_i = α·(P_tx/|RSSI_i|) + β·Q_i + γ·H_i
// -----------------------------------------------------------------------------
double HybridRouting::computeCost(const NeighborEntry& n, double txPower_dBm) const
{
    if (n.rssi_dBm >= 0.0) {
        EV_WARN << "[HybridRouting] computeCost: geçersiz RSSI="
                << n.rssi_dBm << " — maliyet=INF\n";
        return std::numeric_limits<double>::max();
    }

    const double rssiAbs    = -n.rssi_dBm;
    const double signalTerm = txPower_dBm / rssiAbs;
    const double queueTerm  = n.queueOccupancy;
    const double hopTerm    = static_cast<double>(
                                  n.isOnlineGateway ? 0 : n.hopCountToGateway);

    return alpha_ * signalTerm + beta_ * queueTerm + gamma_ * hopTerm;
}

// -----------------------------------------------------------------------------
// computeCostForAddress — Adrese göre maliyet (emit için)
// -----------------------------------------------------------------------------
double HybridRouting::computeCostForAddress(const L3Address& addr) const
{
    auto it = neighborTable_.find(addr);
    if (it == neighborTable_.end())
        return std::numeric_limits<double>::max();
    return computeCost(it->second, txPower_dBm_);
}

// -----------------------------------------------------------------------------
// getSortedNeighbors — artan C_i sırasıyla komşu listesi
// -----------------------------------------------------------------------------
std::vector<std::pair<L3Address, NeighborEntry>>
HybridRouting::getSortedNeighbors(double txPower_dBm) const
{
    std::vector<std::pair<L3Address, NeighborEntry>> result;
    result.reserve(neighborTable_.size());

    for (const auto& kv : neighborTable_) {
        NeighborEntry e  = kv.second;
        e.cachedCost     = computeCost(e, txPower_dBm);
        result.emplace_back(kv.first, e);
    }

    std::sort(result.begin(), result.end(),
        [](const std::pair<L3Address, NeighborEntry>& a,
           const std::pair<L3Address, NeighborEntry>& b) {
            return a.second.cachedCost < b.second.cachedCost;
        });

    return result;
}

// =============================================================================
// Yardımcı: Komşu Tablosu İstatistikleri
// =============================================================================

int HybridRouting::countOnlineGateways() const
{
    int count = 0;
    for (const auto& kv : neighborTable_) {
        if (kv.second.isOnlineGateway)
            ++count;
    }
    return count;
}

bool HybridRouting::areAllNeighborsCongested() const
{
    if (neighborTable_.empty())
        return false;

    for (const auto& kv : neighborTable_) {
        if (kv.second.queueOccupancy < congestionThreshold_)
            return false;   // En az bir komşu sağlıklı
    }
    return true;   // Hep si congestionThreshold üzerinde
}

// =============================================================================
// Güç Durum Makinesi (HybridGateway için basitleştirilmiş CAD döngüsü)
// =============================================================================

void HybridRouting::enterDeepSleep()
{
    currentPowerState_ = PowerState::DEEP_SLEEP;
    emit(powerStateSignal_, static_cast<long>(0));
    EV_INFO << "[HybridRouting] → DEEP_SLEEP\n";
    cancelEvent(cadTimer_);
    scheduleAt(simTime() + cadInterval_s_, cadTimer_);
}

void HybridRouting::enterCAD()
{
    currentPowerState_ = PowerState::CAD;
    emit(powerStateSignal_, static_cast<long>(1));
    EV_INFO << "[HybridRouting] → CAD  (" << cadDuration_ms_ << "ms)\n";
    // CAD süre sonunda uyku döngüsüne dön (WoR simülasyonda pasif)
    scheduleAt(simTime() + cadDuration_ms_ / 1000.0, sleepTimer_);
}

void HybridRouting::enterActiveRx()
{
    currentPowerState_ = PowerState::ACTIVE_RX;
    emit(powerStateSignal_, static_cast<long>(2));
    EV_INFO << "[HybridRouting] → ACTIVE_RX  (timeout=" << activeRxTimeout_s_ << "s)\n";
    cancelEvent(sleepTimer_);
    scheduleAt(simTime() + activeRxTimeout_s_, sleepTimer_);
}

void HybridRouting::enterActiveTx()
{
    currentPowerState_ = PowerState::ACTIVE_TX;
    emit(powerStateSignal_, static_cast<long>(4));
    EV_INFO << "[HybridRouting] → ACTIVE_TX\n";
    enterDeepSleep();
}

void HybridRouting::enterProcessing()
{
    currentPowerState_ = PowerState::PROCESSING;
    emit(powerStateSignal_, static_cast<long>(3));
    EV_INFO << "[HybridRouting] → PROCESSING\n";
}

void HybridRouting::onPreambleDetected()
{
    EV_INFO << "[HybridRouting] CAD → preamble ALGILANDI\n";
    cancelEvent(sleepTimer_);
    enterActiveRx();
}

// =============================================================================
// Beacon Yayını — Gerçek Komşu Keşfi
// =============================================================================

// -----------------------------------------------------------------------------
// broadcastBeaconToMeshNeighbors
//
// Ağdaki tüm MeshRouting ve HybridRouting modüllerine kendimizi tanıtan bir
// beacon mesajı gönderir. Bu, gerçek dünyada Meshtastic radyo yayınını simüle
// eder. Her alıcı kendi komşu tablosunu günceller.
//
// Beacon içeriği:
//   senderAddr  : meshAddress parametresinden (omnetpp.ini'de per-GW tanımlı)
//   rssi        : beaconRssi_ + küçük rastgele sapma (radyo değişimi simülasyonu)
//   queue       : currentQueueOcc_ (dinamik — backhaul durumuna göre değişir)
//   online      : isBackhaulUp_ (internet bağlantısı var mı?)
//   hopToGw     : 0  (bu modül zaten bir GW, internet varsa hop=0)
// -----------------------------------------------------------------------------
void HybridRouting::broadcastBeaconToMeshNeighbors()
{
    const char *myAddr = par("meshAddress").stringValue();
    double queueOcc    = currentQueueOcc_;

    EV_INFO << "[HybridRouting] ─── GW BEACON t=" << simTime() << "s"
            << "  addr=" << myAddr
            << "  queue=" << queueOcc * 100.0 << "%"
            << "  backhaul=" << (isBackhaulUp_ ? "UP (İNTERNET VAR)" : "DOWN (İNTERNET KESİK)")
            << (meshNeighborList_.empty() ? "  [broadcast-all]" : "  [filtered-topology]")
            << "\n";

    // ─── SENARYO DURUM LOGU (her beacon döngüsünde, yani her 10s) ───────────
    if (isBackhaulUp_) {
        EV_WARN << "[HybridRouting] ◆ SENARYO A — İNTERNET VAR ◆\n"
                << "  t=" << simTime() << "s  addr=" << myAddr
                << "  queue=" << queueOcc * 100.0 << "%\n"
                << "  Sensör verisi NetworkServer'a DOĞRUDAN iletiliyor.\n"
                << "  MESH'E SENSÖR VERİSİ GÖNDERİLMİYOR — Sadece durum beacon'ı yayınlanır.\n";
    } else {
        EV_WARN << "[HybridRouting] ◆ SENARYO B — İNTERNET KESİNTİSİ ◆\n"
                << "  t=" << simTime() << "s  addr=" << myAddr
                << "  queue=" << queueOcc * 100.0 << "%\n"
                << "  Internet DOWN — FAILOVER modu aktif.\n"
                << "  Mesh ağı üzerinden en düşük C_i'li GW'ye yönlendirme devrede!\n";
    }

    // Topoloji filtresi: listedeki modül mi diye kontrol et
    auto isInNeighborList = [&](const std::string& nodeName) -> bool {
        if (meshNeighborList_.empty()) return true;  // broadcast mod
        for (const auto& n : meshNeighborList_) {
            if (nodeName == n) return true;
        }
        return false;
    };

    cModule *network = getSimulation()->getSystemModule();
    int beaconCount  = 0;

    for (cModule::SubmoduleIterator it(network); !it.end(); ++it) {
        cModule *node = *it;
        if (!node) continue;

        // Topoloji kuralı: sadece izin verilen komşulara beacon gönder
        if (!isInNeighborList(node->getName())) continue;

        // MeshNode içindeki MeshRouting submodülüne beacon gönder
        cModule *mr = node->getSubmodule("meshRouting");
        if (mr && mr != this && mr->findGate("neighborUpdateIn") >= 0) {
            cMessage *beacon = new cMessage("gwBeacon");
            beacon->addPar("senderAddr").setStringValue(myAddr);
            beacon->addPar("rssi").setDoubleValue(beaconRssi_ + uniform(-2.0, 2.0));
            beacon->addPar("queue").setDoubleValue(queueOcc);
            beacon->addPar("online").setBoolValue(isBackhaulUp_);
            beacon->addPar("hopToGw").setLongValue(0);
            sendDirect(beacon, mr, "neighborUpdateIn");
            ++beaconCount;
            EV_INFO << "[HybridRouting] └─ Beacon → " << node->getName()
                    << "  online=" << (isBackhaulUp_ ? "true" : "false") << "\n";
        }

        // Diğer HybridGateway'lere beacon gönder (mesh üzerinden)
        cModule *ra = node->getSubmodule("routingAgent");
        if (ra && ra != this && ra->findGate("neighborUpdateIn") >= 0) {
            cMessage *beacon = new cMessage("gwBeacon");
            beacon->addPar("senderAddr").setStringValue(myAddr);
            beacon->addPar("rssi").setDoubleValue(beaconRssi_ + uniform(-2.0, 2.0));
            beacon->addPar("queue").setDoubleValue(queueOcc);
            beacon->addPar("online").setBoolValue(isBackhaulUp_);
            beacon->addPar("hopToGw").setLongValue(0);
            sendDirect(beacon, ra, "neighborUpdateIn");
            ++beaconCount;
            EV_INFO << "[HybridRouting] └─ Beacon → " << node->getName()
                    << " (GW-peer)  online=" << (isBackhaulUp_ ? "true" : "false") << "\n";
        }
    }

    EV_INFO << "[HybridRouting] Beacon gönderildi: " << beaconCount << " alıcı\n";

    if (!isBackhaulUp_) {
        EV_WARN << "[HybridRouting] ⚠ BEACON internet durumunu bildiriyor: "
                << par("meshAddress").stringValue()
                << " — BACKHAUL KOPUK. Komşular failover hedefi olarak bu GW'yi seçMEYECEK.\n";
    }
}

// ─────────────────────────────────────────────────────────────────────────────
// Band M (868.0-868.6 MHz) duty-cycle kota kontrolü — kayan 1-saatlik pencere
// Parametre toaSeconds: planlanmakta olan iletimin havada kalış süresi (saniye)
// Dönüş: true → TX izinli, çağıran txLogBandM_'e kaydet; false → TX askıya al
bool HybridRouting::checkBandMDutyCycle(double toaSeconds)
{
    const simtime_t now         = simTime();
    const simtime_t windowStart = now - txQuotaWindow_s_;
    // Pencere dışına çıkan eski kayıtları temizle
    while (!txLogBandM_.empty() && txLogBandM_.front().first < windowStart)
        txLogBandM_.pop_front();
    // Penceredeki toplam TX süresini hesapla
    double used = 0.0;
    for (const auto& e : txLogBandM_) used += e.second;
    const double quota = txQuotaWindow_s_ * bandMDutyCycle_;   // saniye / pencere
    if (used + toaSeconds > quota) {
        EV_WARN << "[HybridRouting] Band M TX SUSPEND: %"
                << bandMDutyCycle_ * 100.0 << " DC doldu!"
                << "  kullanılan=" << used << "s  kota=" << quota << "s\n";
        return false;
    }
    txLogBandM_.push_back({now, toaSeconds});
    return true;
}

// ─────────────────────────────────────────────────────────────────────────────
// Band P / RX2 (869.525 MHz) duty-cycle kota kontrolü
bool HybridRouting::checkRx2DutyCycle(double toaSeconds)
{
    const simtime_t now         = simTime();
    const simtime_t windowStart = now - txQuotaWindow_s_;
    while (!txLogRx2_.empty() && txLogRx2_.front().first < windowStart)
        txLogRx2_.pop_front();
    double used = 0.0;
    for (const auto& e : txLogRx2_) used += e.second;
    const double quota = txQuotaWindow_s_ * rx2DutyCycle_;
    if (used + toaSeconds > quota) {
        EV_WARN << "[HybridRouting] RX2 TX SUSPEND: %"
                << rx2DutyCycle_ * 100.0 << " DC doldu!"
                << "  kullanılan=" << used << "s  kota=" << quota << "s\n";
        return false;
    }
    txLogRx2_.push_back({now, toaSeconds});
    return true;
}

// ─────────────────────────────────────────────────────────────────────────────
// Anten kazancı EIRP düzeltmesi:  ERP (dBm) = P_tx - G_ant (dBi)
// BTK KET: Band M maksimum 14 dBm ERP  →  P_tx ≤ 14 + antennaGain_dBi_
double HybridRouting::effectiveTxPower(double txPower_dBm) const
{
    return txPower_dBm - antennaGain_dBi_;
}

