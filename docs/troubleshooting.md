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


## Dashboard-Terminal ist nicht erreichbar

Status und Logs prüfen:

~~~bash
sudo systemctl status pi5-terminal
sudo journalctl -u pi5-terminal -n 100 --no-pager
sudo ss -ltnp | grep ':7681'
sudo systemd-analyze security pi5-terminal.service
~~~

- Terminal läuft auf Port 7681; Dashboard auf Port 8080.
- Im Browser müssen die separaten Zugangsdaten aus `sudo cat /etc/pi5-basics-terminal.env` verwendet werden.
- Nur ein Browser-Client kann gleichzeitig verbunden sein. Einen zweiten Tab schließen und erneut versuchen.
- Der nftables-Filter erlaubt nur private IPv4-Netze sowie IPv6 ULA-/Link-Local-Adressen und Loopback. Bei Zugriff aus einem ungewöhnlichen VPN-/Subnetz kann die Verbindung blockiert werden. Prüfen: `sudo nft list table inet pi5_terminal`.
- Prüfen, ob `ttyd` installiert ist: `command -v ttyd`.
- Bei Problemen nach einem Paket- oder Systemupdate: `sudo systemctl restart pi5-terminal`.

Das Terminalkonto `pi5terminal` besitzt absichtlich keine sudo-Rechte. Root-Aufgaben müssen über einen separaten administrativen Zugang erfolgen.
