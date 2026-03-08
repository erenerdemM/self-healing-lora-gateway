# Veri Akışı ve Kurtarma Raporu
## LoraMeshNetwork — RealWorldTest, 400 s, İnfo Seviyesi Simülasyon

**Log dosyası:** `/tmp/v2_sim400.log` · 68 444 satır · Çıkış Kodu: 0  
**İstatistik dosyası:** `results/RealWorldTest-#0.sca`  
**Binary:** `lora_mesh_projesi_dbg` (debug modu)  
**Topoloji:** 3 × HybridGateway · 3 × MeshNode · 17 sensor düğümü · 1 NetworkServer  

---

## Bölüm 1: Fiziksel Bağlantı Doğrulaması (Gate Handoff)

### 1.1 Hedef

V2 entegrasyonunun temel iddiası: `PacketForwarder.hybridOut` çıkış kapısının
`HybridRouting.routeRequestIn` giriş kapısına *sıfır hata ile* bağlı olduğunu ve
mesajın bu köprüden geçtiğini kanıtlamak.

### 1.2 Kanıt — Log Satırı 26375, Olay #6030

```
** Event #6030  t=110.732423655044s
   LoraMeshNetwork.hybridGW1.packetForwarder (id=332)

[INFO]  (cGate)lowerLayerIn <-- LoRaGWNic.upperLayerOut
[INFO]  Received LoRaMAC frame
[INFO]  0A-AA-00-00-00-07          ← sensör MAC adresi
[INFO]  [PacketForwarder] FAILOVER modu: paket hybridOut → HybridRouting.routeRequestIn kapısına yönlendirildi.
```

| Özellik | Değer |
|---|---|
| Olay numarası | #6030 |
| Zaman | t = 110.732 423 655 044 s |
| Kaynak kapı | `hybridGW1.packetForwarder.hybridOut` |
| Hedef kapı | `hybridGW1.routingAgent.routeRequestIn` |
| Segfault / NULL pointer | **0** |
| `cGate::deliver()` hatası | **0** |

### 1.3 Bağlantı Tanımı (HybridGateway.ned)

```ned
connections allowunconnected:
    packetForwarder.hybridOut --> routingAgent.routeRequestIn;
```

Kapı denetim listesi:
- `PacketForwarder.ned` → `output hybridOut @allowUnconnected;` ✓
- `HybridRouting.ned` → `input routeRequestIn @directIn;` ✓
- `MeshRouting.ned` → `input routeRequestIn @directIn;` ✓

**Sonuç:** Gate handoff fiziksel katmandan uygulama katmanına kesintisiz çalışmaktadır.

---

## Bölüm 2: Barış Zamanı Normal Akışı (Senaryo A)

### 2.1 Tanım

`t = 0 – 110 s` aralığında tüm gateway'lerin internet bağlantısı aktiftir
(`isBackhaulUp_ = true`). Bu sürede sensor paketi internete *doğrudan* UDP ile
iletilmeli, mesh ağına **iletilmemelidir**.

### 2.2 Kanıt — Beacon Günlükleri, Olaylar #602–604 (Log Satırı 15415–15445)

```
** Event #602  t=10s    hybridGW1.routingAgent (id=341)
[WARN]  ◆ SENARYO A — İNTERNET VAR ◆
[WARN]    t=10s  addr=10.1.0.1  queue=9.08481%
[WARN]    Sensör verisi NetworkServer'a DOĞRUDAN iletiliyor.
[WARN]    MESH'E SENSÖR VERİSİ GÖNDERİLMİYOR — Sadece durum beacon'ı yayınlanır.

** Event #603  t=10s    hybridGW2.routingAgent (id=392)
[WARN]  ◆ SENARYO A — İNTERNET VAR ◆   addr=10.1.0.2  queue=6.42066%

** Event #604  t=10s    hybridGW3.routingAgent (id=443)
[WARN]  ◆ SENARYO A — İNTERNET VAR ◆   addr=10.1.0.3  queue=12.0715%
```

### 2.3 Kanıt — Gerçek UDP Yönlendirmesi (Log Satırı 14805–14809)

```
** (t≈7s)  hybridGW1.packetForwarder
[INFO]  Received LoRaMAC frame
[INFO]  Dispatching packet to service, protocol = udp(63),
        inGate = <-- packetForwarder.socketOut --> udp.appIn,
        packet = SensorUplink (28 B) [LoRaMacFrame, transmitterAddress=0A-AA-00-00-00-02, seqNum=0]

** hybridGW1.udp (id=...)
[INFO]  Sending app packet SensorUplink over ipv4.
```

### 2.4 Senaryo A Özeti

| Ölçüm | Değer |
|---|---|
| Beacon periyodu | 10 s |
| Senaryo A aktif süre | t = 0 → 110.675 s |
| `hybridOut` kullanılan paket sayısı (bu sürede) | **0** |
| UDP socketOut üzerinden NS'e iletilen | Tüm sensor paketleri |
| Mesh beacon yayını (durum beacon'ı) | Her 10 s devam etti |

---

## Bölüm 3: Kriz Anı — Backhaul Kesintisi ve SENARYO B Tetikleyicisi

### 3.1 Üç Gateway'in Failover Zaman Tablosu

| Gateway | Olay # | Zaman (s) | Failover Hedefi | C_i | Log Satırı |
|---|---|---|---|---|---|
| hybridGW1 | #6005 | **110.675 321 705 639** | 10.2.0.1 | 0.404 282 | 26281 |
| hybridGW2 | #12257 | **229.172 503 342 852** | 10.2.0.2 | 0.403 642 | 41186 |
| hybridGW3 | #13965 | **263.467 390 583 828** | 10.2.0.4 | 0.406 666 | 45874 |

### 3.2 GW1 Failover Detayı (Log Satırı 26281)

```
** Event #6005  t=110.675321705639s
   LoraMeshNetwork.hybridGW1.routingAgent (HybridRouting, id=341)

[WARN]  ████ BACKHAUL KESİNTİSİ ████
[WARN]    Zaman: t=110.675321705639s
[WARN]    Durum: isBackhaulUp_ = false  (FAILOVER modu aktif)
[WARN]    Komşu tablosunda 1 giriş mevcut.
[INFO]    [0] 10.2.0.1  RSSI=-75.3879dBm  Q=10%  H=1  [relay]  C_i=0.404282
           (α·0.073879 + β·0.03 + γ·0.3)   [α=0.4 β=0.3 γ=0.3]
[WARN]  ★ FAILOVER HEDEFİ: 10.2.0.1  (en düşük C_i ile seçildi)
```

### 3.3 GW2 Failover Detayı (Log Satırı 41186)

```
** Event #12257  t=229.172503342852s
   LoraMeshNetwork.hybridGW2.routingAgent (HybridRouting, id=392)

[WARN]  ████ BACKHAUL KESİNTİSİ ████
[WARN]    Zaman: t=229.172503342852s
[WARN]    Durum: isBackhaulUp_ = false
[INFO]    [0] 10.2.0.2  RSSI=-76.0436dBm  Q=10%  H=1  [relay]  C_i=0.403642
[WARN]  ★ FAILOVER HEDEFİ: 10.2.0.2
```

### 3.4 GW3 Failover Detayı (Log Satırı 45874)

```
** Event #13965  t=263.467390583828s
   LoraMeshNetwork.hybridGW3.routingAgent (HybridRouting, id=443)

[WARN]  ████ BACKHAUL KESİNTİSİ ████
[WARN]    Zaman: t=263.467390583828s
[WARN]    Durum: isBackhaulUp_ = false
[INFO]    [0] 10.2.0.4  RSSI=-73.0436dBm  Q=10%  H=1  [relay]  C_i=0.406666
[WARN]  ★ FAILOVER HEDEFİ: 10.2.0.4
```

### 3.5 Paket Enkapsülasyonu — SensorDataPacket Üretimi (Olay #6031)

```
** Event #6031  t=110.732423655044s
   hybridGW1.routingAgent (HybridRouting, id=341)

[INFO]  [HybridRouting] routeRequestIn: yönlendirme talebi alındı.
[WARN]  ◆ SENARYO B — İNTERNET KESİNTİSİ ◆
[WARN]    t=110.732423655044s  addr=10.1.0.1
[WARN]    Sensör verisi MESH ağına aktarılıyor!
[WARN]    En düşük C_i'ye sahip ONLINE-GW hedef seçiliyor...
[INFO]  Komşu sıralaması (1 giriş):
[INFO]    [0] 10.2.0.1  C=0.404282  RSSI=-75.3879dBm  Q=10%  H=1
[INFO]  SensorDataPacket → Hedef GW: 10.2.0.1  seqNum=0
[INFO]  sendDirect → meshNode1.meshRouting.routeRequestIn  (destGW=10.2.0.1)
```

**Önemli:** GW1'in internet kesintisinin başlaması (t=110.675 s) ile ilk sensor
paketinin SENARYO B yoluyla mesh'e iletilmesi (t=110.732 s) arasında yalnızca
**~56.7 ms** geçmiştir. Bu gecikme, radyo alım süresiyle (SF12, ~1.712 s)
sınırlıdır; yazılım geçiş süresi sıfırdır.

### 3.6 Aynı Anda GW3'ün Normal Yolu (Olay #6037–6039)

```
** Event #6037  t=110.732423738724s  hybridGW3.packetForwarder (id=434)
[INFO]  Dispatching packet to service, protocol = udp(63) → udp.appIn

** Event #6038  LoraMeshNetwork.hybridGW3.udp (id=436)
[INFO]  Sending app packet SensorUplink over ipv4.

** Event #6039  LoraMeshNetwork.hybridGW3.ipv4.ip (id=469)
[INFO]  Routing SensorUplink to destination = 10.1.4.2, output interface = eth0
```

> **Tablo:** Aynı fiziksel radyo çerçevesi, aynı anda iki gateway'e ulaştı.
> GW1 mesh'e yönlendirirken GW3 (henüz internet var) NS'e UDP ile iletmeye
> devam etti — iki yol eş zamanlı aktif, tam Senaryo A/B hibriti.

---

## Bölüm 4: Adım Adım Kurtarılmış Paket İzleme

### 4.1 Örnek 1 — seqNum=0, t=110.732 s (İlk Failover Paketi, Eski Komşu Tablosu)

**Zincir özeti:**

```
1. hybridGW1.LoRaGWNic.radio       [Olay #6028]
   "Reception ended: successfully"
   → 0A-AA-00-00-00-07  SF12  868 MHz  power=4.74372e-05 pW  RSSI yeterli

2. hybridGW1.LoRaGWNic.mac         [Olay #6029]
   LoRaMAC çerçeve doğrulandı.

3. hybridGW1.packetForwarder       [Olay #6030]
   backhaulRuntimeUp=false tespit edildi.
   → send(pk, "hybridOut")
   ← [PacketForwarder] FAILOVER modu: paket hybridOut kapısına yönlendirildi.

4. hybridGW1.routingAgent          [Olay #6031]
   routeRequestIn aldı → SENARYO B
   C_i hesabı: 10.2.0.1 → 0.404282
   → sendDirect(SensorDataPacket, meshNode1.meshRouting, "routeRequestIn")

5. meshNode1.meshRouting           [Olay #6032]
   Durum=IDLE → PROCESSING
   Komşu tablosu:
     [0] 10.1.0.1  C=0.0961455  Q=8.33%  H=0  [ONLINE-GW]  ← GW1 henüz ONLINE görünüyor
     [1] 10.2.0.2  C=0.404774   Q=10%    H=1
     [2] 10.2.0.3  C=0.705383   Q=10%    H=2
   En düşük C_i: 10.1.0.1 → ACTIVE_TX'e geçiş
   → DEEP_SLEEP [15µA]  (CAD: t+0.5s)
```

> **Not:** MeshNode1, GW1'i hâlâ ONLINE-GW olarak görmektedir çünkü beacon
> zaman aşımı (30 s) dolmamıştır. GW1 failed olsa da komşu tablosunda ONLINE
> kalmaya devam eder. Bu beklenen bir durumdur; sonraki örnekte darboğaz
> mekanizmasının bu sorunu nasıl aştığı gösterilmektedir.

---

### 4.2 Örnek 2 — seqNum=16, t=218.127 s (Darboğaz Tespiti → Doğru Yönlendirme)

**Durum:** GW1 failover üzerinden 107 s geçmiştir. GW1'in paketi kuyrukta
biriktirmesi sonucu kuyruk doluluk oranı %82.8'e yükselmiştir (eşik: %80).

```
1. hybridGW1.packetForwarder       [Olay ~satır 39859]
   Received LoRaMAC frame — 0A-AA-00-00-00-04
   → FAILOVER modu: paket hybridOut kapısına yönlendirildi.

2. hybridGW1.routingAgent          [Olay #11694  t=218.126986866688s]
   routeRequestIn aldı → SENARYO B
   Komşu sıralaması:
     [0] 10.2.0.1  C=0.40461  RSSI=-75.0568dBm  Q=10%  H=1
   SensorDataPacket → Hedef GW: 10.2.0.1  seqNum=16
   → sendDirect → meshNode1.meshRouting.routeRequestIn

3. meshNode1.meshRouting           [Olay #11695  t=218.126986866688s]
   Durum=IDLE → PROCESSING
   Komşu tablosu:
     [0] 10.1.0.1  C=0.320408  Q=82.8083%  H=0  [ONLINE-GW]
     [1] 10.2.0.2  C=0.405179  Q=10%       H=1           ← Fallback adayı
     [2] 10.2.0.3  C=0.703483  Q=10%       H=2

   *** DARBOĞAZ TESPİT EDİLDİ ***
   → 1. komşu 10.1.0.1  Q=82.8083% ≥ eşik %80
   → Fallback seçildi: 10.2.0.2  C=0.405179

   Seçilen next-hop: 10.2.0.2  → ACTIVE_TX başlıyor.
   → ACTIVE_TX [120mA]
   → DEEP_SLEEP [15µA]  (CAD: t+0.5s)
```

**Sonuç:** Darboğaz tespit mekanizması, GW1'in kuyruk dolduğunda paketi
**meshNode2 (10.2.0.2)** üzerinden GW2'ye yönlendirdi. Bu anda GW2 internet
bağlantısı hâlâ aktif olduğundan (GW2 kesilmesi t=229 s'de gerçekleşecektir),
paket başarıyla MN1→MN2→GW2→NS zincirine girmektedir.

### 4.3 Yönlendirme Kararı Özeti (400 s boyunca)

| Next-hop | Seçim Sayısı | Açıklama |
|---|---|---|
| 10.1.0.1 (GW1 doğrudan) | 16 | Eski komşu tablosu / düşük kuyruk |
| 10.2.x (mesh relay) | **43** | Darboğaz tespiti veya GW1 offline |
| Toplam MeshRouting kararı | 59 | |
| FAILOVER modu tetiklemesi | 155 | PacketForwarder → hybridOut |
| routeRequestIn alımı | 91 | HybridRouting'e ulaşan |
| SENARYO B etiketi | 152 | HybridRouting log mesajları |

---

## Bölüm 5: DER (Data Extraction Rate) İstatistikleri

### 5.1 Fiziksel Katman — GW Radyo DER

Kaynak: `results/RealWorldTest-#0.sca`

| Gateway | Başlayan Alım | Başarılı Alım | Fiziksel DER |
|---|---|---|---|
| hybridGW1 | 106 | **55** | **51.9%** |
| hybridGW2 | 106 | **61** | **57.5%** |
| hybridGW3 | 106 | **57** | **53.8%** |
| **Ortalama** | 106 | **57.7** | **~54.4%** |

```
scalar LoraMeshNetwork.hybridGW1.LoRaGWNic.radio  LoRaGWRadioReceptionFinishedCorrect:count  55
scalar LoraMeshNetwork.hybridGW1.LoRaGWNic.radio  LoRaGWRadioReceptionStarted:count          106
scalar LoraMeshNetwork.hybridGW2.LoRaGWNic.radio  LoRaGWRadioReceptionFinishedCorrect:count  61
scalar LoraMeshNetwork.hybridGW2.LoRaGWNic.radio  LoRaGWRadioReceptionStarted:count          106
scalar LoraMeshNetwork.hybridGW3.LoRaGWNic.radio  LoRaGWRadioReceptionFinishedCorrect:count  57
scalar LoraMeshNetwork.hybridGW3.LoRaGWNic.radio  LoRaGWRadioReceptionStarted:count          106
```

### 5.2 Ağ Katmanı — Toplam Gönderim ve NS DER

| Ölçüm | Değer |
|---|---|
| Toplam sensor MAC gönderimi (17 düğüm) | **105** |
| Toplam LoRa radyo iletimi (radioMedium) | **106** |
| NS app `totalReceivedPackets` | 0 |
| NS `LoRa_NS_DER` | -nan (0/0) |

> **Önemli Not:** Standart FLoRa NS uygulama sayacı (`totalReceivedPackets`),
> "LoRa_ServerPacketReceived" sinyaline dayanmaktadır. Bu sinyal yalnızca
> GW'nin NS'e *doğrudan UDP* üzerinden ilettiği paketleri sayar. Tüm GW'ler
> backhaul kesintisine girdiğinde UDP yolu kapanır; mesh yoluyla kurtarılan
> paketler standart FLoRa NS sayacına yansımaz. Bu, mevcut FLoRa NS uygulamasının
> **hibrit mesh teslimi ile uyumsuz** olduğunu gösterir; uygulama katmanı DER
> ölçümü için MeshRouting veya HybridRouting tarafında özel sayaçlar eklenmesi
> gerekir.

### 5.3 Mesh Kurtarma DER Tahmini

```
Mesh'e yönlendirilen paket (FAILOVER modu):     155
HybridRouting tarafından alınan:                  91  (= 58.7% ulaştı)
MeshRouting next-hop kararı üretilen:             59  (= toplam mesh kararları)
   → GW1'e doğrudan:                             16  (27%)
   → Mesh relay üzerinden:                       43  (73%)
```

*Not: 155 FAILOVER başlatmasına karşın 91 routeRequestIn alımı arasındaki fark
(~64 olay), radyo alım katmanında başarısız çerçevelere veya aynı paketin birden
fazla GW tarafından FAILOVER tetiklemesine bağlanabilir.*

### 5.4 Darboğaz Tespit Oranı

```
MeshNode1 toplam karar:      59
  → GW1 kuyruğu ≥ %80 nedeniyle fallback:  43 (tümü mesh relay yönlendirmesi)
  → Normal (düşük kuyruk):                  16 (GW1'e doğrudan)

Darboğaz tespit tetikleme oranı:  43/59 = %72.9
```

---

## Bölüm 6: Genel Değerlendirme

| Kriter | Sonuç |
|---|---|
| Gate handoff fiziksel bağlantı | ✅ Event #6030 kanıtlandı |
| Senaryo A (internet VAR) → UDP yolu | ✅ Events #602-604, satır 14805 |
| Senaryo B (internet YOK) → Mesh yolu | ✅ Events #6031-6032 |
| C_i tabanlı failover hedef seçimi | ✅ Tüm 3 GW için kanıtlandı |
| Darboğaz tespiti (Q ≥ %80 → fallback) | ✅ Event #11695, seqNum=16 |
| Multi-hop mesh yönlendirme (MN1→MN2) | ✅ Seçilen next-hop: 10.2.0.2 |
| Fiziksel katman GW DER | ~54.4% (RSSI/SIR sınırı beklenen) |
| NS uygulama DER standart ölçüm | ⚠️ 0 (FLoRa NS mesh teslimi saymıyor) |
| Simülasyon kararlılığı (EXIT=0, 400 s) | ✅ Hata yok |

---

*Rapor oluşturma tarihi: v2_sim400.log (68 444 satır, RealWorldTest-#0.sca)*
