// =============================================================================
// NetworkServer — Bulut / Yerel Ağ Sunucusu (LNS)
// =============================================================================
// PDF: "Network Server (LNS)" — LoRaWAN paketlerini işleyen merkezi sunucu.
//   Normalde bulutta (TTN, ChirpStack Cloud) veya yerel (Local LNS) çalışır.
//   EndNode verilerini StandardGateway veya AgentGateway üzerinden alır.
//
// Mimari konumu:
//   StandardGateway --[normal: internet]--> NetworkServer
//   AgentGateway    --[failover path]  --> NetworkServer
//
// Versiyon Yol Haritası:
//   V1 (Genel Tanım): INET StandardHost wrapper. FLoRa NetworkServerApp çalıştırır.
//                     GW'den gelen UDP paketleri alır, ACK gönderir (downlink).
//                     localPort=1000, destPort=2000 (FLoRa standardı).
//
//   V2 (Gerçekçilik): ChirpStack LNS davranışı modellenir:
//                       - AES-CMAC MIC doğrulama (PDF Denklem LocalLNS kısmı)
//                       - Duplicate frame detection (çoklu GW'den aynı paket)
//                       - Downlink scheduling (Class A RX1/RX2 window)
//                       - PostgreSQL veri tabanı yazımı (PDF Bölüm 3.4.3)
//                     Azure IoT Hub → Azure Functions → PostgreSQL pipeline modeli
//
//   V3 (Ölçeklendirme): Çoklu NetworkServer (geo-dağıtık), yük dengeleme,
//                        PDR/latency istatistikleri, QoS etiket istatistikleri
//                        (00=Standart, 11=Kritik paket oranı analizi)
//
// Yazılım referansı (PDF Bölüm 3.3-3.4, Appendix B):
//   ChirpStack v4, TTN integration, Azure IoT Hub forwarding,
//   Azure Functions ingest pipeline, PostgreSQL schema
// =============================================================================

import inet.node.inet.StandardHost;

module NetworkServer extends StandardHost
{
    parameters:
        // Her topolojide tutarlı sunucu görünümü
        @display("i=device/server2;is=n");

        // V1: 1 Ethernet arayüzü — AgentGateway tarafı
        // V2: +1 arayüz: WAN/internet backhaul
        numEthInterfaces = default(1);

        // V1: 1 uygulama — FLoRa NetworkServerApp
        // V2: +1 uygulama: ChirpStack LNS simülatörü
        // V3: +1 uygulama: Azure IoT Hub forwarder
        numApps = default(1);

        // V2: MIC doğrulama ve duplicate detection parametreleri
        // string lnsType = default("simple");  // "simple" | "chirpstack"
        // bool enableMicVerification = default(false);
        // bool enableDuplicateDetection = default(false);
}
