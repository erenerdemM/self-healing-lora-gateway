import inet.applications.contract.IApp;

// Periodic LoRa sensor application that generates a fixed-size (11B) payload.
// The payload is packed little-endian and carried as raw bytes.
//
// This module is intended for LoRaWAN-style uplinks in our hybrid gateway project.
// (A full LoRaWAN MAC/join is handled elsewhere; here we model the uplink payload + PHY params.)
//
simple SensorLoRaApp like IApp
{
    parameters:
        @class(flora::SensorLoRaApp);
        int numberOfPacketsToSend = default(0); // 0 = infinite
        volatile double startTime @unit(s) = default(10s);
        volatile double sendInterval @unit(s) = default(60s);

        // LoRa PHY settings (EU868 defaults)
        double initialLoRaTP @unit(dBm) = default(14dBm);
        double initialLoRaCF @unit(Hz) = default(868MHz);
        int initialLoRaSF = default(7);
        double initialLoRaBW @unit(Hz) = default(125kHz);
        int initialLoRaCR = default(4);
        bool initialUseHeader = default(true);

        int dataSize @unit(B) = default(11B);
    gates:
        input socketIn;
        output socketOut;
}
