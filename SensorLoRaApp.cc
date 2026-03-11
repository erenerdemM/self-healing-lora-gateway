#include "SensorLoRaApp.h"

#include "inet/common/ModuleAccess.h"
#include "inet/common/INETMath.h"
#include "inet/common/packet/Packet.h"
#include "inet/common/packet/chunk/BytesChunk.h"

#include "LoRa/LoRaRadio.h"
#include "LoRa/LoRaTagInfo_m.h"

namespace flora {

Define_Module(SensorLoRaApp);

SensorLoRaApp::SensorLoRaApp() {}

SensorLoRaApp::~SensorLoRaApp()
{
    cancelAndDelete(sendTimer);  sendTimer = nullptr;
    cancelAndDelete(rx1Timer_);  rx1Timer_ = nullptr;
    cancelAndDelete(rx2Timer_);  rx2Timer_ = nullptr;
}

void SensorLoRaApp::initialize(int stage)
{
    omnetpp::cSimpleModule::initialize(stage);

    if (stage == INITSTAGE_APPLICATION_LAYER) {
        numberOfPacketsToSend = par("numberOfPacketsToSend");
        startTime = par("startTime");
        sendInterval = par("sendInterval");
        dataSize = par("dataSize");

        // App assumes the parent module contains a submodule named "LoRaNic" with a "radio".
        auto *parent = getParentModule();
        auto *nic = parent->getSubmodule("LoRaNic");
        if (!nic)
            throw omnetpp::cRuntimeError("SensorLoRaApp expects parent to contain submodule 'LoRaNic'");

        loRaRadio = omnetpp::check_and_cast<LoRaRadio *>(nic->getSubmodule("radio"));

        configureRadioFromParameters();

        // ── LoRaWAN Class A RX pencere süresi (SF ve BW'den otomatik hesaplama) ──
        rxDelay1_s_              = par("rxDelay1").doubleValue();
        const int    sf          = par("initialLoRaSF").intValue();
        const double bw_hz       = par("initialLoRaBW").doubleValue();
        const int    rxSyms      = par("rxWindowSymbols").intValue();
        const double tsym_s      = std::pow(2.0, sf) / bw_hz;  // SF12: 32.768ms
        rxWindowDuration_s_      = rxSyms * tsym_s;             // SF12: 5×32.768ms = 163.8ms

        // ── BTK/ETSI Görev Döngüsü Taban Hesabı ────────────────────────────────────
        // Kaynak: "LoRaWAN Parametreleri ve Yasal Sınırlar" Raporu §Tablo (ToA)
        // min_interval = ToA / DC_limit  (1% band → 100 × ToA)
        //   SF12/BW125/11B → ToA≈1.45s → min≈145s
        //   SF10/BW125/20B → ToA≈0.41s → min≈41s
        //   SF7 /BW125/11B → ToA≈0.06s → min≈6s
        const double dc_limit   = par("dutyCycleLimit").doubleValue();  // 0.01 = %1
        const int    pl         = par("dataSize").intValue();
        const int    cr         = par("initialLoRaCR").intValue();       // 4 = 4/5
        const int    de         = (sf >= 11) ? 1 : 0;  // Low Data Rate Opt. (SF11/SF12)
        const double t_preamble = (8.0 + 4.25) * tsym_s;  // n_preamble=8 standart
        // LoRa payload sembol sayısı (H=0 başlıklı, CRC=1)
        const double inner      = (8.0*pl - 4.0*sf + 28.0 + 16.0) / (4.0*(sf - 2.0*de));
        const int    n_sym      = 8 + std::max((int)std::ceil(inner) * (cr + 4), 0);
        const double toa_s      = t_preamble + n_sym * tsym_s;
        minSendInterval_s_      = toa_s / dc_limit;  // yasal taban

        // SF10–12 maksimum uygulama yükü = 51B (ETSI dwell sınırı)
        if (sf >= 10 && pl > 51)
            throw omnetpp::cRuntimeError(
                "[BTK/ETSI] SF%d: dataSize=%dB > 51B maksimum uygulama yükü!", sf, pl);

        EV_INFO << "[SensorLoRaApp] BTK/ETSI Spektrum Analizi:"
                << "  SF=" << sf
                << "  BW=" << (bw_hz / 1e3) << "kHz"
                << "  payload=" << pl << "B"
                << "  ToA=" << toa_s * 1e3 << "ms"
                << "  DC≤" << dc_limit * 100 << "%"
                << "  min_interval=" << minSendInterval_s_ << "s"
                << "  rxWin=" << rxWindowDuration_s_ * 1e3 << "ms\n";

        rx1Timer_ = new omnetpp::cMessage("classA_rx1Timer");
        rx2Timer_ = new omnetpp::cMessage("classA_rx2Timer");

        sendTimer = new omnetpp::cMessage("sendTimer");
        scheduleAt(simTime() + startTime, sendTimer);
    }
}

void SensorLoRaApp::handleMessage(omnetpp::cMessage *msg)
{
    if (msg->isSelfMessage()) {

        // ── Class A RX1: TX+1s sonra pencere açılıyor ───────────────────────────────
        if (msg == rx1Timer_) {
            const int sf = par("initialLoRaSF").intValue();
            EV_INFO << "[ClassA-RX1] Pencere ACIK — t=" << simTime()
                    << "s  SF" << sf
                    << "  f=" << par("initialLoRaCF").doubleValue() / 1e6 << "MHz"
                    << "  sure=" << rxWindowDuration_s_ * 1e3 << "ms"
                    << "  (kapat: t=" << (simTime() + rxWindowDuration_s_) << "s)\n";
            return;   // Pencere süresi sonunda cihaz uyku + RX2 bekler
        }

        // ── Class A RX2: TX+2s sonra pencere açılıyor (SF12, 869.525 MHz) ──────
        if (msg == rx2Timer_) {
            // RX2 penceresi her zaman SF12 / 869.525 MHz (LoRaWAN spec.)
            constexpr double rx2_tsym_s = 32.768e-3;  // SF12/125kHz
            const double rx2_dur_ms = par("rxWindowSymbols").intValue() * rx2_tsym_s * 1e3;
            EV_INFO << "[ClassA-RX2] Pencere ACIK — t=" << simTime()
                    << "s  SF12  f=869.525MHz  sure=" << rx2_dur_ms << "ms"
                    << "  → Cihaz UYKU moduna giriyor.\n";
            return;   // Uygulama katmanında downlink işleme V2'de eklenecek
        }

        // ── Ana TX zamanlayici: uplink + Class A RX pencerelerini planla ───────
        sendUplink();
        sentPackets++;

        // Class A RX1 (TX+rxDelay1) ve RX2 (TX+rxDelay1+1s) zamanla
        cancelEvent(rx1Timer_);
        cancelEvent(rx2Timer_);
        scheduleAt(simTime() + rxDelay1_s_,         rx1Timer_);
        scheduleAt(simTime() + rxDelay1_s_ + 1.0,   rx2Timer_);

        if (numberOfPacketsToSend == 0 || sentPackets < numberOfPacketsToSend) {
            simtime_t nextInterval = par("sendInterval");

            // ── Floor 1: BTK/ETSI Görev Döngüsü (yasal zorunluluk) ────────────
            // Kaynak: "LoRaWAN Parametreleri ve Yasal Sınırlar" Raporu §DC Limiti
            // min = ToA/DC_limit: SF12/11B→145s, SF10/20B→41s, SF7/11B→6s
            const simtime_t dc_floor(minSendInterval_s_);

            // ── Floor 2: LoRaWAN Class A zamanlama (TS001-1.0.4 §7.2) ─────────
            // RECEIVE_DELAY2(2s) + RX2_window(163ms) ≈ 2.16s — DC floor'dan küçük
            const simtime_t classA_floor(rxDelay1_s_ + 1.0 + rxWindowDuration_s_);

            // Geçerli taban: ikisinin büyüğü (DC floor her zaman baskın)
            const simtime_t lorawan_floor =
                (dc_floor > classA_floor) ? dc_floor : classA_floor;

            if (nextInterval < lorawan_floor)
                nextInterval = lorawan_floor;

            scheduleAt(simTime() + nextInterval, msg);
        }
        else {
            delete msg;
            sendTimer = nullptr;
        }
    }
    else {
        // Downlink/control — V2'de ack ve ADR işlenecek.
        delete msg;
    }
}

void SensorLoRaApp::configureRadioFromParameters()
{
    loRaRadio->loRaTP = par("initialLoRaTP").doubleValue();
    loRaRadio->loRaCF = inet::units::values::Hz(par("initialLoRaCF").doubleValue());
    loRaRadio->loRaSF = par("initialLoRaSF");
    loRaRadio->loRaBW = inet::units::values::Hz(par("initialLoRaBW").doubleValue());
    loRaRadio->loRaCR = par("initialLoRaCR");
    loRaRadio->loRaUseHeader = par("initialUseHeader");
}

void SensorLoRaApp::writeLeU16(std::vector<uint8_t>& bytes, size_t offset, uint16_t value)
{
    bytes.at(offset + 0) = static_cast<uint8_t>(value & 0xFF);
    bytes.at(offset + 1) = static_cast<uint8_t>((value >> 8) & 0xFF);
}

void SensorLoRaApp::writeLeI16(std::vector<uint8_t>& bytes, size_t offset, int16_t value)
{
    writeLeU16(bytes, offset, static_cast<uint16_t>(value));
}

void SensorLoRaApp::sendUplink()
{
    auto *pkt = new inet::Packet("SensorUplink");

    // 11-byte payload (little-endian):
    // [0..1]  seq (u16)
    // [2..3]  temperature_dC (i16)  e.g. 235 -> 23.5C
    // [4]     humidity_pct (u8)     0..100
    // [5]     soil_pct (u8)         0..100
    // [6]     rain_mmph (u8)        0..255
    // [7..8]  pressure_hPa (u16)    300..1100
    // [9..10] light_lux (u16)       0..65535
    std::vector<uint8_t> bytes;
    bytes.resize(std::max(11, dataSize), 0);

    writeLeU16(bytes, 0, sequence++);

    // Generate plausible sensor values (can be replaced with parameters later)
    int16_t temp_dC = static_cast<int16_t>(intuniform(-50, 500)); // -5.0..50.0 C
    uint8_t hum = static_cast<uint8_t>(intuniform(20, 95));
    uint8_t soil = static_cast<uint8_t>(intuniform(0, 100));
    uint8_t rain = static_cast<uint8_t>(intuniform(0, 50));
    uint16_t pressure = static_cast<uint16_t>(intuniform(950, 1050));
    uint16_t light = static_cast<uint16_t>(intuniform(0, 60000));

    writeLeI16(bytes, 2, temp_dC);
    bytes.at(4) = hum;
    bytes.at(5) = soil;
    bytes.at(6) = rain;
    writeLeU16(bytes, 7, pressure);
    writeLeU16(bytes, 9, light);

    auto payload = inet::makeShared<inet::BytesChunk>();
    payload->setBytes(bytes);

    pkt->insertAtBack(payload);

    // Attach LoRa PHY parameters as a tag (consumed by LoRaRadio/PHY)
    auto loraTag = pkt->addTagIfAbsent<LoRaTag>();
    loraTag->setBandwidth(loRaRadio->loRaBW);
    loraTag->setCenterFrequency(loRaRadio->loRaCF);
    loraTag->setSpreadFactor(loRaRadio->loRaSF);
    loraTag->setCodeRendundance(loRaRadio->loRaCR);
    loraTag->setPower(mW(inet::math::dBmW2mW(loRaRadio->loRaTP)));

    send(pkt, "socketOut");
}

} // namespace flora
