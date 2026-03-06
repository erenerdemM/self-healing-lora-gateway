// =============================================================================
// MeshNode — Meshtastic Mesh Relay (Ara Aktarım) Düğümü
// =============================================================================
// PDF (Bölüm 1.2, 2): Meshtastic (LoRa Mesh) protokolü, gateway'ler arasında
//   Gateway-to-Gateway (G2G) iletişim katmanını oluşturur.
//   MeshNode, bu mesh ağındaki ara aktarım (relay) düğümüdür.
//   LoRaWAN protokolüyle ilgisi yoktur — sadece Meshtastic paketi yönlendirir.
//
// Görev:
//   - HybridGateway'ler arasında Meshtastic paketlerini store-and-forward ile iletir
//   - Çoklu MeshNode ile multi-hop mesh zinciri oluşturulabilir
//   - LoRaWAN medium'una kayıtlı DEĞİLDİR (sensör trafiğine karışmaz)
//
// =============================================================================
// V1 (Genel Tanım — ŞU AN AKTİF):
//   INET Router tabanlı. Meshtastic mesh, Ethernet olarak simüle edilir.
//   IP forwarding otomatik açık (Router varsayılanı).
//   numEthInterfaces: bağlandığı HybridGateway/MeshNode sayısı kadar.
//
// V2 (Gerçekçilik):
//   Ethernet arayüzleri → SX1262 tabanlı LoRa radyo ile değiştirilir.
//   Ayrı bir MeshtasticMedium (LoRaMedium'dan türeyen) eklenir.
//   Store-and-forward ile multi-hop yönlendirme (Meshtastic flooding/DSDV).
//   Mesh latency modeli: Latency_mesh = Σ(ToA_j + T_proc_j + T_prop_j) / n
//     (PDF Denklem 2.5)
//   Enerji modeli: V1'den ~n kat fazla tüketim (n = hop sayısı)
//
// V3 (Ölçeklendirme):
//   Çoklu MeshNode, dinamik topoloji, hareket (RandomWaypointMobility)
//   SNR tabanlı en iyi komşu seçimi (EWM skoru)
//   Kanal yoğunluğu ve çarpışma modeli
//
// Donanım referansı (PDF Bölüm 5.1.2):
//   Heltec HT-CT62 (SX1262 + ESP32-C3) veya benzeri SX1262 tabanlı cihaz.
//   Meshtastic firmware — CAD (Channel Activity Detection) modu, düşük güç.
//   Standby akımı: ~15µA (Phase I, PDF Bölüm 5.4.1)
// =============================================================================

import inet.node.inet.Router;

module MeshNode extends Router
{
    parameters:
        // Her topolojide tutarlı erişim noktası (relay) görünümü
        @display("i=device/accesspoint;is=n");

        // V1: Her bağlantı için 1 Ethernet arayüzü
        //   2 = iki HybridGateway arasında köprü
        //   3 = üç yönlü mesh bağlantı noktası
        // V2: Ethernet → SX1262 LoRa radyo (MeshtasticMedium üzerinden)
        numEthInterfaces = default(2);

        // V2: Meshtastic protokol parametreleri (şimdilik yorum satırı)
        // int maxHopCount = default(3);       // Meshtastic varsayılan hop limiti
        // double meshTxPower = default(14dBm); // SX1262 TX gücü (EU868)
        // double meshSF = default(11);         // Spreading Factor (G2G bağlantısı)
}
