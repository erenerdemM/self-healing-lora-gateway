// =============================================================================
// MeshPacket.msg — Mesh Ağ Haberleşme Paketleri
// =============================================================================
// Proje: Self-Healing Hybrid LoRa Gateway — DEÜ EEE Bitirme
//   Eren ERDEM (2020502028), Melisa KURAL (2021502041)
//
// MESAJ HİYERARŞİSİ:
//
//   inet::FieldsChunk
//       └── MeshPacket          (temel iletim zarfı)
//               ├── SensorDataPacket   (saha sensör verisi, 11 bayt payload)
//               └── SosBeaconPacket    (acil durum imdat paketi, AjanGW uyanışı)
//
// MİMARİ NOT:
//   - MeshRouting.cc, gelen paketin `destinationGateway` alanını okur.
//     Bu adres HybridGateway tarafından broadcast edilirken doldurulur.
//   - MeshNode C_i maliyet fonksiyonuyla best next-hop'u hesaplar ve unicast iletir.
//   - SosBeaconPacket: darboğaz (Q >= %80) veya bölgesel çöküşte AjanGateway'i uyandırır.
// =============================================================================

import inet.common.INETDefs;
import inet.common.packet.chunk.Chunk;
import inet.networklayer.common.L3Address;

cplusplus {{
#include "inet/networklayer/common/L3Address.h"
using namespace inet;
}}

namespace lora_mesh;

// =============================================================================
// 1. MeshPacket — Temel taşıyıcı zarf
// =============================================================================
// Her mesh paketinde bulunması gereken minimum başlık bilgileri.
// HybridGateway, ağa çıkarken `destinationGateway` alanını doldurur.
// MeshNode bu alanı okuyarak hangi GW'ye doğru yönleneceğine karar verir.
//
// Toplam başlık boyutu: ~10 bayt (2 × L3Address/IPv4 + 2 × int alanları)
// =============================================================================
class MeshPacket extends inet::FieldsChunk
{
    // Paketi gönderen kaynak düğümün ağ adresi
    inet::L3Address sourceAddress;

    // Paketin ulaşmak istediği hedef gateway'in adresi.
    // HybridGateway bu alanı broadcast yaparken atar; MeshNode, C_i hesabında
    // bu hedefe doğru en iyi next-hop'u bulmak için kullanır.
    inet::L3Address destinationGateway;

    // Paketin geçtiği atlama (hop) sayacı — döngü önleme için
    int hopCount = 0;

    // Uçtan uca sıra numarası — yinelenen paket tespiti için
    int sequenceNumber = 0;
}

// =============================================================================
// 2. SensorDataPacket — Standart tarla sensörü verisi
// =============================================================================
// SensorLoRaApp.cc tarafından üretilen 11 baytlık little-endian payload'u
// OMNeT++ simülasyon katmanında alan alan temsil eder.
//
// Byte düzeni (SensorLoRaApp.cc ile birebir):
//   [0..1]  seqNum         int16_t   2 bayt
//   [2..3]  temperature_dC int16_t   2 bayt  (°C × 10 → 235 = 23.5 °C)
//   [4]     humidity       uint8_t   1 bayt  (% 0..100)
//   [5]     soilMoisture   uint8_t   1 bayt  (% 0..100)
//   [6]     rain           uint8_t   1 bayt  (0=yok, 1=hafif, 2=orta, 3=şiddetli)
//   [7..8]  pressure_hPa   int16_t   2 bayt  (hPa, offset +900 → 1013 hPa = 113)
//   [9]     lightLevel     uint8_t   1 bayt  (0=karanlık .. 255=tam güneş)
//             TOPLAM                11 bayt  (+ MeshPacket başlığı)
// =============================================================================
class SensorDataPacket extends MeshPacket
{
    // Sıra numarası (SensorLoRaApp.cc'deki seqNum ile aynı)
    short seqNum = 0;

    // ── Mesh Röle Teslimat Metadata (PacketForwarder.meshRelayIn için) ──────
    // LoRa Spreading Factor (7..12). forwardToMesh() orijinal LoRaMacFrame'den
    // kopyalar; PacketForwarder NS2'ye teslim ederken LoRaMacFrame içine yazar.
    int loRaSF = 9;

    // Orijinal sensör MAC adresi (string olarak; MacAddress.str() çıktısı).
    // Ör: "0a:aa:00:00:00:01". PacketForwarder bunu MacAddress(str)'a dönüştürür.
    string transmitterMacStr = "0a:aa:00:00:00:01";

    // Sinyal kalitesi (orijinal GW-Sensor ölçümü, NS2 istatistikleri için)
    double rssi = -100.0;
    double snir = 10.0;

    // Sıcaklık — ondalık hassasiyeti korumak için ×10 tamsayı olarak
    // Örnek: 23.5 °C → 235, -5.0 °C → -50
    short temperature_dC = 0;

    // Bağıl nem [0..100] %
    int humidity = 0;

    // Toprak nemi [0..100] %
    int soilMoisture = 0;

    // Yağış kodu: 0=yok, 1=hafif, 2=orta, 3=şiddetli
    int rain = 0;

    // Atmosfer basıncı [hPa], offset +900 uygulanmış
    // Örnek: 1013 hPa → 113 olarak saklanır
    short pressure_hPa = 0;

    // Işık seviyesi [0..255] (0=tam karanlık, 255=tam güneş)
    int lightLevel = 0;
}

// =============================================================================
// 3. SosBeaconPacket — Acil durum imdat sinyali (AjanGateway uyanışı)
// =============================================================================
// MeshRouting.cc, aşağıdaki tetikleyicilerden birini algıladığında bu paketi
// mesh'e yayınlar:
//   a) Darboğaz: Q_i >= congestionThreshold (varsayılan %80) VE fallback komşu yok
//   b) Bölgesel çöküş: tüm komşular stale / neighbor tablosu boş
//   c) Ana gateway erişilemez: isOnlineGateway=true olan komşu kalmadı
//
// AjanGateway, bu paketi dinler ve kendi uplink bağlantısını (4G/satellit)
// aktive ederek bölgesel yedek çıkış noktası olarak devreye alır.
//
// `isUrgent = true` alan bu paket, MeshNode'larda normal veri paketlerine
// göre öncelikli işlenir (kuyrukta ön tarafa alınır).
// =============================================================================
class SosBeaconPacket extends MeshPacket
{
    // Her zaman true — normal veri paketlerinden ayırt etmek için
    // MeshNode yönlendirici, bu bayrakla SOS trafiğini önceliklendirir
    bool isUrgent = true;

    // Alarm nedeni kodu
    //   0 = CONGESTION       — yerel kuyruk darboğazı (Q >= eşik)
    //   1 = REGIONAL_FAILURE — birden fazla komşu erişilemez
    //   2 = GATEWAY_DOWN     — tüm online-GW komşuları kayboldu
    //   3 = LINK_DEGRADED    — ortalama RSSI dramatik düşüş tespit etti
    int reasonCode = 0;

    // SOS'u üreten düğümün kimlik dizgesi (Qtenv'de okunabilirlik için)
    // Örnek: "meshNode[2]"
    string senderNodeId = "";

    // Alarm anındaki kuyruk doluluk oranı [0.0 .. 1.0]
    // computeCost() içindeki Q_i/Q_max değeri buraya kopyalanır
    double congestionLevel = 0.0;

    // Alarm anındaki neighbor tablosunda online GW sayısı
    // 0 ise tam yalıtım (total isolation) senaryosu
    int onlineGatewayCount = 0;

    // SOS üretildiği andaki ortalama komşu RSSI [dBm]
    // Sinyal kalitesi izleme ve post-mortem analiz için
    double averageRssi_dBm = 0.0;
}
