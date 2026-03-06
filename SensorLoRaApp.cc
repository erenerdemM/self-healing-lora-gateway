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
    cancelAndDelete(sendTimer);
    sendTimer = nullptr;
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

        sendTimer = new omnetpp::cMessage("sendTimer");
        scheduleAt(simTime() + startTime, sendTimer);
    }
}

void SensorLoRaApp::handleMessage(omnetpp::cMessage *msg)
{
    if (msg->isSelfMessage()) {
        sendUplink();
        sentPackets++;

        if (numberOfPacketsToSend == 0 || sentPackets < numberOfPacketsToSend) {
            scheduleAt(simTime() + sendInterval, msg);
        }
        else {
            delete msg;
            sendTimer = nullptr;
        }
    }
    else {
        // For now, ignore downlink/control.
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
