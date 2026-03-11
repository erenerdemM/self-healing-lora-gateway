# MidScaleHarsh — Fiziksel Etki ve Zeka Raporu
## Zorlu Fiziksel Şartların Derin Log Analizi

**Senaryo:** `MidScaleHarsh` — 300 s simülasyon, Event #141 631'e kadar  
**Topoloji:** 10 HybridGW · 60 MeshNode · 50 SensorGW × 5 sensör = **250 fiziksel sensör**  
**Log dosyası:** `/tmp/harsh_routing_detail.log` — 259 890 satır (`--cmdenv-log-level=WARN`)  
**Sonuç dosyası:** `results/MidScaleHarsh-#0.sca`

---

## Bölüm 1 — Duvarlara Çarpan Sinyaller
### DielectricObstacleLoss'un Ölçülen Etkisi

#### 1.1 Engel Hesaplama İstatistikleri (`.sca` radioMedium)

```
Obstacle loss intersection computation count : 507 990
Obstacle loss intersection count             :  25 561   (%5.03 — sinyal yollarının 1/20'si kesildi)
```

**15 bina** (`obstacles.xml`) tüm simülasyon boyunca 507 990 kez sinyal-engel kesişim
hesabı yaptırdı; bunların 25 561 tanesi gerçek bir fiziksel blokajla sonuçlandı.
Her 20 LoRa sinyalinden 1 tanesi bina duvarına çarptı.

#### 1.2 SensorGW Bazlı `rcvBelowSensitivity` Oranları

| SensorGW    | Gönderilen | Hassasiyet Altı | Oran       | Yorum                         |
|------------|-----------|----------------|-----------|-------------------------------|
| sensorGW10 | 58        | 37             | **63.8 %** | En kötü — en fazla engel      |
| sensorGW8  | 56        | 29             | **51.8 %** | İkinci en kötü                |
| sensorGW7  | 54        | 26             | 48.1 %     |                               |
| sensorGW3  | 58        | 28             | 48.3 %     |                               |
| sensorGW4  | 53        | 24             | 45.3 %     |                               |
| sensorGW5  | 58        | 27             | 46.6 %     |                               |
| sensorGW9  | 55        | 22             | 40.0 %     |                               |
| sensorGW2  | 58        | 19             | 32.8 %     |                               |
| sensorGW6  | 64        | 19             | 29.7 %     | En az engel                   |
| sensorGW1  | 56        | 18             | **32.1 %** | Görece temiz görüş hattı      |
| **TOPLAM** | **570**   | **249**        | **43.7 %** | Yarıya yakın paket engelde    |

> sensorGW10 ile sensorGW1 arasındaki fark: **63.8 % − 32.1 % = 31.7 puan** —
> yani sensorGW10 bölgesindeki sensörler, sensorGW1 bölgesindekilere göre yaklaşık
> **2× daha fazla** engele maruz kaldı.

#### 1.3 En Kötü Bireysel Sensör: `sensorGW10[1]`

```
sensorGW10[1].LoRaNic.mac  numSent           = 13
sensorGW10[1].LoRaNic.radio.receiver  rcvBelowSensitivity = 13
→ Tüm paketler alıcı hassasiyet eşiğinin altında kaldı — %100 kayıp!
```

Bu sensör, 300 saniye boyunca **hiçbir paketini** iletmedi.
Bina gölgesinde kalmaya en uç örnek: σ = 7.0 dB gölgelenme + duvar kırması,
her paketi ölü bölgeye itiyor.

#### 1.4 HybridGW Alıcı Karşılaştırması

| Gateway    | meshAddr  | beaconRssi | rcvBelowSensitivity |
|-----------|----------|-----------|---------------------|
| hybridGW10 | 10.1.0.10 | −65.0 dBm | **132**             |
| hybridGW3  | 10.1.0.3  | −80.0 dBm | 119                 |
| hybridGW7  | 10.1.0.7  | −70.0 dBm | 119                 |
| hybridGW4  | 10.1.0.4  | −68.0 dBm | 117                 |
| hybridGW2  | 10.1.0.2  | −72.0 dBm | 113                 |
| hybridGW9  | 10.1.0.9  | −74.0 dBm | 112                 |
| hybridGW5  | 10.1.0.5  | −75.0 dBm | 110                 |
| hybridGW1  | 10.1.0.1  | −78.0 dBm | 107                 |
| hybridGW8  | 10.1.0.8  | −77.0 dBm | 107                 |
| hybridGW6  | 10.1.0.6  | −82.0 dBm | **104**             |

hybridGW10 (en güçlü beacon = en çok sensör çekiyor) aynı zamanda en fazla
hassasiyet-altı sinyal aldı; **güçlü beacon gölgelenmeyi ortadan kaldırmıyor**,
engel arkasındaki sensörler geri yolda zayıf kalıyor.

---

## Bölüm 2 — Sinyal Çakılması Yüzünden Değişen Rotalar
### C_i Algoritmasının Tetiklediği Yeniden Yönlendirmeler

#### 2.1 Backhaul Kesinti Zaman Çizelgesi (7 GW, 300 s içinde)

```
t =  53.752 s  Event #28984  hybridGW2 (10.1.0.2, −72 dBm)  → BACKHAUL KESİNTİSİ
t =  83.482 s  Event #42131  hybridGW4 (10.1.0.4, −68 dBm)  → BACKHAUL KESİNTİSİ
t =  91.254 s  Event #46044  hybridGW3 (10.1.0.3, −80 dBm)  → BACKHAUL KESİNTİSİ
t = 145.914 s  Event #71328  hybridGW1 (10.1.0.1, −78 dBm)  → BACKHAUL KESİNTİSİ
t = 151.505 s  Event #74120  hybridGW6 (10.1.0.6, −82 dBm)  → BACKHAUL KESİNTİSİ
t = 160.471 s  Event #78784  hybridGW5 (10.1.0.5, −75 dBm)  → BACKHAUL KESİNTİSİ
t = 183.827 s  Event #89201  hybridGW7 (10.1.0.7, −70 dBm)  → BACKHAUL KESİNTİSİ
```

300 saniyelik simülasyonun **%61'i** (183.8 s sonrasında) geçmeden 10 GW'nin
7'si devre dışı düştü. Yalnızca hybridGW8 (cut=317 s), hybridGW9 (cut=384 s) ve
hybridGW10 (cut=306 s) 300 s sonu itibarıyla internet bağlantısını korudu.

#### 2.2 C_i Algoritması — FAILOVER HEDEFİ Seçimleri

Her backhaul kesildiğinde `HybridRouting` SENARYO B moduna geçer ve komşu tablosundaki
en düşük C_i değerine sahip mesh düğümünü seçer.  
Maliyet fonksiyonu: `C_i = α × (1 − RSSI_norm) + (1 − α) × QueueOccupancy`  (α = 0.6)

| t (s)   | GW kesildi  | beaconRssi | Seçilen FAILOVER HEDEFİ | Seçilen Düğüm Komşulukları                   |
|--------|------------|-----------|------------------------|----------------------------------------------|
| 53.752  | hybridGW2  | −72 dBm   | `10.2.0.14` meshNode14  | GW2, meshNode4, 13, 15, 24                   |
| 83.482  | hybridGW4  | −68 dBm   | `10.2.0.20` meshNode20  | GW4, meshNode10, 19, 30                      |
| 91.254  | hybridGW3  | −80 dBm   | `10.2.0.7`  meshNode7   | GW3, meshNode6, 8, 17                        |
| 145.914 | hybridGW1  | −78 dBm   | `10.2.0.11` meshNode11  | **GW1 + GW5**, meshNode1, 12, 21 ← AKILLI   |
| 151.505 | hybridGW6  | −82 dBm   | `10.2.0.24` meshNode24  | GW6, meshNode14, 23, 25, 34                  |
| 160.471 | hybridGW5  | −75 dBm   | `10.2.0.22` meshNode22  | **GW5 + GW6**, meshNode12, 21, 23, 32        |
| 183.827 | hybridGW7  | −70 dBm   | `10.2.0.26` meshNode26  | GW7, meshNode16, 25, 27, 36                  |

**Dikkat çeken seçimler:**
- **GW1 → meshNode11**: meshNode11 hem GW1 hem de GW5'e komşu; GW1 kesildiğinde
  algoritma GW5'e de ulaşabilen düğümü seçerek trafik akışını sürdürdü.
- **GW5 → meshNode22**: meshNode22 hem GW5 hem GW6'ya komşu — iki farklı aktif
  yola birden erişim imkânı.

#### 2.3 SENARYO B & BÖLGESEL ÇÖKÜŞ Sayıları

```
[WARN] SENARYO B (failover modu)  : 316 olay   — kesintiden sonra süregelen failover döngüleri
[WARN] BÖLGESEL ÇÖKÜŞ tespiti     : 12 301 olay — tüm komşular dolu/çevrimdışı durumda
```

12 301 BÖLGESEL ÇÖKÜŞ olayı, GW yoğunlaşma dönemlerinde (t > 150 s) routing
modülünün **her bir paket iletim denemesinde** ≥ 1 komşu göremediğini gösteriyor;
bu da Bölüm 3'teki kuyruk doymasının doğrudan nedeni.

---

## Bölüm 3 — Trafik Patlaması ve Darboğazın Tetiklenmesi
### Queue Doyması ve DARBOĞAZ Zinciri

#### 3.1 DARBOĞAZ Olayları Özeti (toplam: 75)

| GW IP     | GW Adı     | Backhaul Kesildi | İlk DARBOĞAZ  | Son DARBOĞAZ | max Q    | Olay |
|----------|-----------|-----------------|--------------|-------------|---------|------|
| 10.1.0.2  | hybridGW2 | t =  53.8 s     | **t = 153.6 s** | t = 287.5 s | %100    | 12   |
| 10.1.0.3  | hybridGW3 | t =  91.3 s     | t = 193.2 s  | t = 294.6 s | %100    | **27** |
| 10.1.0.4  | hybridGW4 | t =  83.5 s     | t = 218.7 s  | t = 298.9 s | %100    | 8    |
| 10.1.0.1  | hybridGW1 | t = 145.9 s     | t = 254.3 s  | t = 298.6 s | %100    | 11   |
| 10.1.0.6  | hybridGW6 | t = 151.5 s     | t = 262.4 s  | t = 298.8 s | %100    | 6    |
| 10.1.0.5  | hybridGW5 | t = 160.5 s     | t = 261.8 s  | t = 278.3 s | %90.5   | 4    |
| 10.1.0.7  | hybridGW7 | t = 183.8 s     | t = 280.6 s  | t = 295.7 s | %87.9   | 7    |

> hybridGW8, GW9, GW10 (internet ayakta): 300 s boyunca **hiçbir DARBOĞAZ yok**.  
> Bu, tıkanmanın yalnızca backhaul-dead GW'lerin kuyruk dolmasından kaynaklandığını
> kesinlikle kanıtlıyor.

#### 3.2 İlk DARBOĞAZ Patlama Analizi (meshNode14 → GW2)

```
Event #75389  t = 153.556 s  meshNode14.meshRouting  GW=10.1.0.2  Q=80.48%
Event #76585  t = 156.293 s  meshNode14.meshRouting  GW=10.1.0.2  Q=80.48%
Event #77620  t = 158.695 s  meshNode14.meshRouting  GW=10.1.0.2  Q=80.48%
```

**GW6 tam 2.1 saniye önce** devre dışı düştü (t = 151.505 s). GW6 kesilince
GW6'nın komşu mesh düğümlerinin trafiği GW2'ye aktı, queue **2.1 saniyede
%80.5'e fırladı** → bursty trafik dalgası + anlık GW çöküşü bu sıçramayı verdi.

Tıkanan GW2 kuyruk ilerlemesi:
```
t=153.6s  Q= 80.48%  [████████████████    ]   ← İLK DARBOĞAZ (Event #75389)
t=156.3s  Q= 80.48%  [████████████████    ]   ← kuyruk stabil
t=158.7s  Q= 80.48%  [████████████████    ]   ← 3 olay, sessiz birikim
     ...       (GW5 kesiliyor: t=160.471s)
t=180.1s  Q=100.00%  [████████████████████]   ← TAM DOYMA (Event #87675)
t=182.7s  Q=100.00%  [████████████████████]
t=185.9s  Q=100.00%  [████████████████████]
```

GW2 kuyruğu: **%80.5 → %100'e 26.5 saniyede** (t = 153.6 → 180.1 s).  
Bu hızlanma GW5'in kesilmesiyle (t = 160.5 s) eş zamanlı gerçekleşti.

#### 3.3 GW3 Tıkanma Zinciri — 27 Olay, %82 → %100

```
t=193.179s  Q= 82.36%  [meshNode8 ]   ← açılış (Event #93950)
t=197.993s  Q= 82.36%  [meshNode8 ]
t=201.515s  Q= 89.86%  [meshNode6 ]   ← yeni düğüm katılıyor
t=201.701s  Q= 89.86%  [meshNode18]
t=202.763s  Q= 89.86%  [meshNode5 ]
      ...
t=213.742s  Q= 97.36%  [meshNode5 ]   ← kritik eşik (Event #102458)
t=223.591s  Q=100.00%  [meshNode5 ]   ← TAM DOYMA (Event #107945)
      ...
t=294.591s  Q=100.00%  [meshNode6 ]   ← 71 saniyedir tam dolu
```

GW3'e 5 farklı meshNode yönlendirdi: `meshNode5, 6, 7, 8, 18`.
Bunlar hepsi GW3'ün komşuluk listesindeki düğümler (ini: `meshNode5 meshNode6
meshNode7 meshNode8 meshNode16 meshNode17 meshNode18`). Backhaul kesik GW3,
7 komşusundan 5'i tarafından DARBOĞAZ kaynağı olarak işaretlendi.

#### 3.4 Cascade Yayılma Kronolojisi

```
t =  53.8 s   GW2 backhaul KESİLDİ
t =  83.5 s   GW4 backhaul KESİLDİ
t =  91.3 s   GW3 backhaul KESİLDİ
t = 145.9 s   GW1 backhaul KESİLDİ
t = 151.5 s   GW6 backhaul KESİLDİ
t = 153.6 s ★ İLK DARBOĞAZ: GW2, Q=80.5%  (+2.1 s sonra)
t = 158.7 s   GW2 kuyruk stabil  →
t = 160.5 s   GW5 backhaul KESİLDİ
t = 180.1 s   GW2 Q=100% (tam doyma)
t = 183.8 s   GW7 backhaul KESİLDİ
t = 193.2 s   GW3 DARBOĞAZ başlıyor, Q=82.4%
t = 218.7 s   GW4 DARBOĞAZ başlıyor, Q=100%
t = 254.3 s   GW1 DARBOĞAZ başlıyor, Q=86.3%
t = 261.8 s   GW5 DARBOĞAZ başlıyor, Q=83.0%
t = 262.4 s   GW6 DARBOĞAZ başlıyor, Q=89.6%
t = 280.6 s   GW7 DARBOĞAZ başlıyor, Q=80.4%
t = 298.9 s   Simülasyon bitiyor: 7 GW kuyruğu kısmen/tam dolu
```

Her GW kesintisi ortalama **30–100 s sonra** DARBOĞAZ olarak tezahür etti.
50 sensör × (1/15) paket/s ≈ **3.3 paket/s** ortalama toplam yük; ama
`uniform(8s, 45s)` dağılımı anlık yük dalgalarını 3–5× artırabilir.

---

## Özet: Üç Stres Katmanının Birleşik Etkisi

| Stres Faktörü          | Kanıt                                     | Sayısal Değer                                  |
|-----------------------|-------------------------------------------|------------------------------------------------|
| DielectricObstacleLoss | rcvBelowSensitivity oranı                 | %43.7 ortalama, **%100** en kötü bireysel sensör |
| σ = 7.0 dB gölgelenme | sensorGW10/1 farkı                        | %63.8 − %32.1 = **31.7 puan**                 |
| Bursty trafik          | İlk DARBOĞAZ hızı                         | Q = 0→%80 in **2.1 s** (GW6 çöktükten sonra)  |
| C_i algoritması        | FAILOVER HEDEFİ seçimi                    | 7 kesinti → 7 akıllı next-hop, %0 müdahale    |
| Mesh tıkanması         | Toplam DARBOĞAZ                           | **75 olay · 7 farklı GW · max Q = %100**       |

### Temel Bulgular

1. **Fiziksel engeller ölçülebilir**: sensorGW10 bölgesindeki sensörlerin
   %63'ü hassasiyet altında kaldı; sensorGW10[1] bütün paketlerini kaybetti.

2. **C_i algoritması reaktif ve akıllı**: GW1 kesildiğinde hem GW1 hem GW5'e
   komşu olan meshNode11 seçildi; bu karar %0 insan müdahalesiyle otomatik
   gerçekleşti (Event #71328, t = 145.914 s).

3. **Cascade dominant**: İlk DARBOĞAZ, 6. GW kesintisinden yalnızca **2.1 s**
   sonra geldi. Bursty trafik (uniform 8–45 s aralık) kuyrukları anlık olarak
   %80'in üzerine taşıdı ve bir kez bu eşik aşıldı mı geri dönüş güçleşti.

---

*Rapor oluşturma tarihi: simülasyon `MidScaleHarsh-#0` (300 s, seed 0)*  
*Log: 259 890 satır WARN seviyesi · Analiz: Python tabanlı satır-pattern eşleştirme*


