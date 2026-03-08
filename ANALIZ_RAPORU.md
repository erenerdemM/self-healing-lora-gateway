# LoRa Mesh Ağı Simülasyon Analiz Raporu
## Bitirme Projesi — HybridRouting + MeshRouting Senaryo Doğrulaması

---

## 1. Topoloji

### Ağ Düğümleri
| Tip | İsim | Adet |
|-----|------|------|
| Hibrit Ağ Geçidi (GW) | hybridGW1, hybridGW2, hybridGW3 | 3 |
| Mesh Röle Düğümü | meshNode1, meshNode2, meshNode3, meshNode4 | 4 |
| Vektör Sensör (GW1 bölgesi) | sensorGW1[0..4] | 5 |
| Vektör Sensör (GW2 bölgesi) | sensorGW2[0..3] | 4 |
| Vektör Sensör (GW3 bölgesi) | sensorGW3[0..7] | 8 |
| **Toplam Sensör** | | **17** |

### Mesh Komşuluk Tablosu (Topoloji Kısıtı)
```
hybridGW1  ←→  meshNode1
hybridGW2  ←→  meshNode2
hybridGW3  ←→  meshNode4
meshNode1  ←→  meshNode2, meshNode3
meshNode2  ←→  meshNode1
meshNode3  ←→  meshNode1, meshNode4
meshNode4  ←→  meshNode3
```
Mesh üzerinden GW-arası yol: `GW1 ↔ meshNode1 ↔ meshNode3 ↔ meshNode4 ↔ GW3`

### Fiziksel Konumlar
| Düğüm | X | Y |
|-------|---|---|
| hybridGW1 | 200 | 200 |
| hybridGW2 | 800 | 200 |
| hybridGW3 | 500 | 850 |
| meshNode1 | 350 | 350 |
| meshNode2 | 650 | 350 |
| meshNode3 | 350 | 600 |
| meshNode4 | 650 | 700 |

---

## 2. Senaryo Tanımları

### Senaryo A — İnternet VAR (Normal Mod)
- GW, internet bağlantısı aktif olduğu sürece sensör verilerini doğrudan NetworkServer'a iletir.
- Mesh ağına sensör verisi GÖNDERİLMEZ — yalnızca durum beaconı yayınlanır.
- Her 10 saniyede bir beacon ile komşulara `isBackhaulUp_=true` bildirimi yapılır.

### Senaryo B — İnternet KESİK (FAILOVER Modu)
- Backhaul bağlantısı kesilen GW, en düşük maliyetli komşu GW'yi seçer.
- Maliyet fonksiyonu: $C_i = w_1 \cdot q_i + w_2 \cdot h_i + w_3 \cdot (1 - r_i)$
  - $q_i$: kuyruk doluluk oranı
  - $h_i$: internete uzaklık (hop sayısı)
  - $r_i$: normalize RSSI
- Seçilen GW (veya mesh next-hop) `FAILOVER HEDEFİ` olarak log'a yazılır.
- Mesh ağı üzerinden pakete yönlendirme aktive edilir.

---

## 3. Simülasyon Parametreleri

```
Simülasyon süresi : 400 saniye
Log seviyesi      : WARN
Beacon aralığı    : 10 saniye (beaconInterval = 10s)
Sensör gönderim   : startTime=uniform(5s,35s), sendInterval=uniform(40s,90s)
```

### Backhaul Kesinti Zamanları (omnetpp.ini'deki uniform dağılımlardan)
```
hybridGW1: backhaulCutTime = uniform(80s, 160s)   → t = 110.675s
hybridGW2: backhaulCutTime = uniform(150s, 250s)  → t = 229.173s
hybridGW3: backhaulCutTime = uniform(200s, 320s)  → t = 263.467s
```
> **NOT**: Bu değerler default seed (run #0) ile elde edilmiştir. Her seed'de rastgele farklı zaman üretilir.

---

## 4. Simülasyon Sonuçları

### 4.1. Tüm 3 GW Rastgele Zamanda İnternet Bağlantısını Kesti ✅

Simülasyon log'undan (`/tmp/sim_final.log`):

```
[WARN][LoraMeshNetwork.hybridGW1.routingAgent]   Zaman: t=110.675321705639s
[WARN][LoraMeshNetwork.hybridGW1.routingAgent]   Durum: isBackhaulUp_ = false (FAILOVER modu aktif)

[WARN][LoraMeshNetwork.hybridGW2.routingAgent]   Zaman: t=229.172503342852s
[WARN][LoraMeshNetwork.hybridGW2.routingAgent]   Durum: isBackhaulUp_ = false (FAILOVER modu aktif)

[WARN][LoraMeshNetwork.hybridGW3.routingAgent]   Zaman: t=263.467390583828s
[WARN][LoraMeshNetwork.hybridGW3.routingAgent]   Durum: isBackhaulUp_ = false (FAILOVER modu aktif)
```

- BACKHAUL KESİNTİSİ sayısı: **3** (her GW bir kez)
- Tüm kesintiler 400s süre içinde gerçekleşti

### 4.2. Senaryo A — İnternet Varken GW Yalnızca Beacon Yayınladı ✅

Her GW, kendi kesinti zamanına kadar her 10 saniyede bir Senaryo A logu üretti:

```
[WARN][LoraMeshNetwork.hybridGW1.routingAgent] ◆ SENARYO A — İNTERNET VAR ◆
  Sensör verisi NetworkServer'a DOĞRUDAN iletiliyor.
  MESH'E SENSÖR VERİSİ GÖNDERİLMİYOR — Sadece durum beacon'ı yayınlanır.

[WARN][LoraMeshNetwork.hybridGW2.routingAgent] ◆ SENARYO A — İNTERNET VAR ◆
  ... (t=229s'e kadar devam etti)

[WARN][LoraMeshNetwork.hybridGW3.routingAgent] ◆ SENARYO A — İNTERNET VAR ◆
  ... (t=263s'e kadar devam etti)
```

- Toplam SENARYO A logu: **59**

### 4.3. Senaryo B — İnternet Gidince FAILOVER Modu Devreye Girdi ✅

Her GW kesintisinden sonra Senaryo B logları ve FAILOVER HEDEFİ seçimi gerçekleşti:

```
[WARN][hybridGW1.routingAgent] ████ BACKHAUL KESİNTİSİ ████
[WARN][hybridGW1.routingAgent] ★ FAILOVER HEDEFİ: 10.2.0.1  (en düşük C_i ile seçildi)
[WARN][hybridGW1.routingAgent] ◆ SENARYO B — İNTERNET KESİNTİSİ ◆

[WARN][hybridGW2.routingAgent] ████ BACKHAUL KESİNTİSİ ████
[WARN][hybridGW2.routingAgent] ★ FAILOVER HEDEFİ: 10.2.0.2  (en düşük C_i ile seçildi)
[WARN][hybridGW2.routingAgent] ◆ SENARYO B — İNTERNET KESİNTİSİ ◆

[WARN][hybridGW3.routingAgent] ████ BACKHAUL KESİNTİSİ ████
[WARN][hybridGW3.routingAgent] ★ FAILOVER HEDEFİ: 10.2.0.4  (en düşük C_i ile seçildi)
[WARN][hybridGW3.routingAgent] ◆ SENARYO B — İNTERNET KESİNTİSİ ◆
```

- Toplam SENARYO B logu: **61**
- Toplam FAILOVER seçimi: **67**

### 4.4. FAILOVER Hedef Adresleri Açıklaması

| GW | FAILOVER HEDEFİ | Anlamı |
|----|----------------|--------|
| hybridGW1 | 10.2.0.1 = meshNode1 | GW1 → meshNode1 → ... → online GW |
| hybridGW2 | 10.2.0.2 = meshNode2 | GW2 → meshNode2 → meshNode1 → GW1 |
| hybridGW3 | 10.2.0.4 = meshNode4 | GW3 → meshNode4 → mesNode3 → ... |

> **NOT**: Hedef adres, nihai GW adresi değil, mesh üzerindeki **next-hop** adresidir. Bu davranış tasarım gereğidir — GW en yakın mesh düğümüne paket gönderir, mesh katmanı relay zinciriyle iletir.

---

## 5. Olay Zaman Çizelgesi

```
t=0s    → hybridGW1, GW2, GW3 başlar — hepsi Senaryo A (internet VAR)
t=10s   → İlk beacon döngüsü — üç GW: "SENARYO A — İNTERNET VAR"
t=20s   → İkinci beacon döngüsü (her 10s devam eder)
...
t=110.7s → [GW1] ████ BACKHAUL KESİNTİSİ ████ → FAILOVER: meshNode1 → SENARYO B
           [GW2, GW3] Senaryo A devam ediyor
...
t=229.2s → [GW2] ████ BACKHAUL KESİNTİSİ ████ → FAILOVER: meshNode2 → SENARYO B
           [GW3] Senaryo A devam ediyor
...
t=263.5s → [GW3] ████ BACKHAUL KESİNTİSİ ████ → FAILOVER: meshNode4 → SENARYO B
t=400s  → Simülasyon tamamlandı (temiz bitiş)
```

---

## 6. Özet

| Gereksinim | Beklenen | Elde Edilen | Durum |
|-----------|---------|-------------|-------|
| 3 GW rastgele zamanda internet keser | 3 kesinti | 3 kesinti (t≈111s, 229s, 263s) | ✅ |
| İnternet VARKEN sadece beacon yayını | SENARYO A logları | 59 SENARYO A logu | ✅ |
| İnternet GİTTİKTE FAILOVER | SENARYO B + FAILOVER HEDEFİ | 61 SENARYO B + 67 FAILOVER seçimi | ✅ |
| Simülasyon 400s'ye ulaşır | Temiz bitiş | EXIT:0, 46800 satır log | ✅ |
| Mesh topoloji kısıtı uygulanır | Yalnızca komşu GW'lere beacon | meshNeighborList filtresi aktif | ✅ |

**Tüm gereksinimler karşılandı. Simülasyon başarıyla tamamlandı.**

---

*Simülasyon ortamı: OMNeT++ 6.0, FLoRa, INET 4.4*
*Proje: `/home/eren/Desktop/bitirme_lora_kod/lora_mesh_projesi/`*
