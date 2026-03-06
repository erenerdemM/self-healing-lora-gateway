// =============================================================================
// HybridGateway — Hibrit LoRaWAN + Meshtastic Gateway
// =============================================================================
// PDF (Bölüm 5.1, 2): "Standard Gateway" — LoRaWAN konsantratör (RAK5146/SX1303)
//   VE Meshtastic mesh modülü (Heltec HT-CT62/SX1262) aynı donanım üzerinde.
//
// Görev:
//   - EndNode'lardan LoRa paketleri alır (LoRaWAN PHY/MAC)
//   - ONLINE modda : PacketForwarder → NetworkServer (doğrudan internet/WAN)
//   - FAILOVER modda: PacketForwarder → MeshNode üzerinden → diğer HybridGateway
//     → NetworkServer (Meshtastic G2G, Gateway-to-Gateway)
//
// Tüm gateway'ler bu aynı tiptedir. Fark sadece:
//   - İnternet bağlantısı olup olmadığı (ini'de Ethernet bağlantısıyla modellenir)
//   - Failover Agent'ın ONLINE/FAILOVER durum bilgisi (V2'de aktif)
//
// =============================================================================
// V1 (Genel Tanım — ŞU AN AKTİF):
//   FLoRa LoRaGW tabanlı. LoRa paketi alır, UDP/IP ile hedef adrese gönderir.
//   Meshtastic mesh, V1'de Ethernet linki olarak simüle edilir.
//   numEthInterfaces:
//     1 → sadece mesh/WAN tarafı (internet yok, mesh üzerinden yönlendirme)
//     2 → mesh tarafı + WAN/internet tarafı (internet var, NetworkServer'a bağlı)
//
// V2 (Gerçekçilik):
//   - Local LNS (ChirpStack) entegrasyonu — AES-CMAC MIC, AES-CTR decrypt
//   - Failover Agent state machine: ONLINE / FAILOVER / SELF_HEALING
//   - Rlink(t) = α·(1-PLR) + β·RTT⁻¹  izleme (PDF Denklem 2.8)
//   - τ_failover eşiği aşılınca mod geçişi
//   - Meshtastic için ayrı SX1262 LoRa radyo + MeshtasticMedium eklenir
//   - Ethernet mesh linki → Meshtastic radyo linki ile değiştirilir
//
// V3 (Ölçeklendirme):
//   - Çoklu HybridGateway, WRR yük dengeleme
//   - EWM ağırlık hesaplama: SCORE = w1·SNR - w2·HopCount + w3·Energy
//   - Bottleneck tespiti: Q_size > Q_max → komşu GW uyandırma
//   - QoS tag (2-bit): 00=Standart, 11=Kritik/Acil (PDF Denklem 2.9)
//   - AES session key ile re-encryption (Ksession)
//
// Donanım (PDF Bölüm 5.1-5.2):
//   Raspberry Pi CM4 (Lite, 2GB RAM)
//   + RAK5146 (SX1303) mPCIe — LoRaWAN konsantratör
//   + Heltec HT-CT62 (SX1262+ESP32-C3) — Meshtastic mesh modülü
//   + Quectel EG25-G (LTE Cat4) — hücresel yedek backhaul
//   + Özel 2-katmanlı PCB, IP67 muhafaza
// =============================================================================

import flora.LoraNode.LoRaGW;

module HybridGateway extends LoRaGW
{
    parameters:
        // Her topolojide tutarlı anten kulesi görünümü
        @display("i=device/antennatower;is=n");

        // V1: 1 arayüz = sadece mesh/WAN (internet yok, Meshtastic mesh ile bağlı)
        //     2 arayüz = mesh + internet/WAN (NetworkServer'a doğrudan bağlı)
        // V2: +1 arayüz = Meshtastic SX1262 (ayrı LoRa medium üzerinden G2G)
        // V3: +1 arayüz = LTE Cat4 (Quectel EG25-G, acil durum backhaul)
        numEthInterfaces = default(1);

        // V2: Failover Agent parametreleri (şimdilik yorum satırı)
        // double failoverThreshold = default(0.6);  // τ_failover (PDF Denklem 2.8)
        // double alpha = default(0.7);               // PLR ağırlığı
        // double beta  = default(0.3);               // RTT⁻¹ ağırlığı

        // V3: EWM yük dengeleme ağırlıkları
        // double w1 = default(0.5);  // HopCount ağırlığı (PDF Tablo 2.2)
        // double w2 = default(0.5);  // SNR ağırlığı
}
