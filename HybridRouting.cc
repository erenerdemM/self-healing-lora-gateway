// =============================================================================
// HybridRouting.cc — Stub (iskelet)
// =============================================================================
// HybridRouting.h / HybridRouting.ned ile eşleşen minimum C++ kaydı.
// Simülasyonun derlenip bağlanabilmesi için Define_Module gereklidir.
//
// TODO (sonraki aşama): Broadcast mantığı implemente edilecek —
//   - Internet bağlantısı koparsa en iyi hedef GW'yi seç ve yayınla
//   - MeshNode'lardan gelen SosBeaconPacket'i yakala ve AjanGW'yi uyandır
// =============================================================================

#include "HybridRouting.h"

Define_Module(HybridRouting);

// ─── Yaşam döngüsü ──────────────────────────────────────────────────────────

void HybridRouting::initialize(int stage)
{
    cSimpleModule::initialize(stage);

    if (stage == 0) {
        EV_INFO << "[HybridRouting] initialize — stub modu aktif\n";
    }
}

void HybridRouting::handleMessage(cMessage *msg)
{
    EV_WARN << "[HybridRouting] handleMessage stub — mesaj silindi: "
            << msg->getName() << "\n";
    delete msg;
}

// ─── Public API stubs ───────────────────────────────────────────────────────

L3Address HybridRouting::selectNextHop(double /*txPower_dBm*/)
{
    return L3Address();   // Unspecified — V2'de implemente edilecek
}

void HybridRouting::updateNeighbor(const L3Address& /*addr*/,
                                    double           /*rssi_dBm*/,
                                    int              /*hopCount*/,
                                    double           /*queueOccupancy*/,
                                    bool             /*isOnlineGateway*/)
{
    // V2'de implemente edilecek
}

void HybridRouting::purgeStaleNeighbors()
{
    // V2'de implemente edilecek
}

void HybridRouting::finish()
{
    // V2'de timer temizliği yapılacak
}
