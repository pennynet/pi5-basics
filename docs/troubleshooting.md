# Fehlerbehebung

## Installer meldet falsches Betriebssystem

pi5-basics ist für Raspberry Pi OS Trixie vorgesehen. Prüfe:

~~~bash
cat /etc/os-release
uname -m
tr -d '\0' </proc/device-tree/model
~~~

Bei Bookworm oder einer anderen Distribution nicht erzwingen; zuerst muss die Unterstützung explizit ergänzt werden.

## Paketinstallation schlägt fehl

~~~bash
sudo apt update
sudo apt --fix-broken install
sudo bash install.sh
~~~

Prüfe Netzwerk, DNS und freien Speicherplatz. Logdatei: /var/log/pi5-basics-install.log

## WLAN oder Bluetooth soll wieder eingeschaltet werden

~~~bash
sudo rfkill list
sudo rfkill unblock wifi
sudo rfkill unblock bluetooth
~~~

Prüfe außerdem den Dienst pi5-basics-block-radios.service, der die gewählte Sperre bei einem Start erneut anwendet.

## ZRAM ist nicht aktiv

~~~bash
systemctl status zramswap.service
swapon --show
cat /etc/default/zramswap
~~~

Wenn die Distribution eine andere zram-Implementierung verwendet, nicht mehrere ZRAM-Dienste parallel aktivieren.

## SSD wird nicht erkannt

- Bei USB: anderes Kabel/USB-Gehäuse und ausreichende Stromversorgung prüfen.
- Bei NVMe: PCIe-Adapter, Kabel/Steckverbindung und unterstützte PCIe-Konfiguration prüfen.
- Ausgabe sammeln: lsblk, dmesg | tail -100, lspci (falls vorhanden).
- Vor Änderungen immer sicherstellen, dass das aktuelle SD-System noch bootet.

## Bootet nach einer Änderung nicht

SD-Karte und SSD nicht formatieren. Strom abschalten, die zuletzt geänderte Hardware-/EEPROM-Einstellung prüfen und nach Möglichkeit mit der bekannten funktionierenden SD-Konfiguration starten. Für EEPROM-Recovery die aktuelle offizielle Raspberry-Pi-Anleitung verwenden.
