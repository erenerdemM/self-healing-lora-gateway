# VS Code + OMNeT++ hızlı kullanım

Bu klasördeki ayarlar, OMNeT++ projesini VS Code üzerinden derlemek/çalıştırmak için hazırlandı.

## Tasks
- `Terminal -> Run Task` menüsünden:
  - **OMNeT++: Build (debug)** / **Build (release)**
  - **OMNeT++: Run (Cmdenv, debug exe)**
  - **OMNeT++: Run (Qtenv, debug exe)**

Tasks, OMNeT++ ortamını `setenv` ile kurup sonra `make` veya simülasyon çalıştırır.

## Debug
`Run and Debug` panelindeki **OMNeT++: Debug (lora_mesh_projesi_dbg)** konfigi C++ debug içindir.

Gereksinim: VS Code içinde **C/C++** uzantısı (ms-vscode.cpptools).

Not: Debug sırasında OMNeT++ ortamı için en sağlıklısı `setenv` ile başlatılmış bir terminalden çalıştırmaktır. Eğer debug açılışında GUI/Qt sorunları görürsen, önce task ile çalıştırıp sonra gerektiğinde attach yaklaşımına geçebiliriz.
