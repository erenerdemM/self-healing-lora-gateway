#pragma once

#include <omnetpp.h>
#include "inet/common/InitStages.h"

namespace flora {

class LoRaRadio;

class SensorLoRaApp : public omnetpp::cSimpleModule
{
  public:
    SensorLoRaApp();
    ~SensorLoRaApp() override;

  protected:
    void initialize(int stage) override;
    int numInitStages() const override { return inet::NUM_INIT_STAGES; }
    void handleMessage(omnetpp::cMessage *msg) override;

  private:
    void configureRadioFromParameters();
    void sendUplink();

    static void writeLeU16(std::vector<uint8_t>& bytes, size_t offset, uint16_t value);
    static void writeLeI16(std::vector<uint8_t>& bytes, size_t offset, int16_t value);

  private:
    omnetpp::cMessage *sendTimer = nullptr;
    LoRaRadio *loRaRadio = nullptr;

    int sentPackets = 0;
    int numberOfPacketsToSend = 0;

    omnetpp::simtime_t startTime;
    omnetpp::simtime_t sendInterval;
    int dataSize = 11;

    uint16_t sequence = 0;
};

} // namespace flora
