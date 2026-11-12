# Installation und Konfiguration

## Voraussetzungen

- Raspberry Pi 5; Zielplattform ist das Modell mit 8 GB RAM.
- Raspberry Pi OS Trixie, vorzugsweise 64-bit.
- Internetverbindung während der Paketinstallation.
- Administrativer Zugriff (sudo).
- Für die Erstinstallation genügt die vorhandene SD-Karte; eine SSD ist nicht nötig.

## Installation

~~~bash
sudo apt update
sudo apt install -y git
git clone https://github.com/pennynet/pi5-basics.git
cd pi5-basics
sudo bash install.sh
~~~

Der Installer bricht bei einer nicht unterstützten Debian-/Raspberry-Pi-OS-Version ab. Bei nicht eindeutig erkanntem Pi-5-Modell fragt er vor dem Fortfahren nach.

## Interaktive Einrichtung

Die Fragen betreffen optionale Diagnosewerkzeuge, WLAN, Bluetooth, ZRAM, automatische Updates, Journalbegrenzung und Watchdog. Zusätzlich fragt der Installer, ob ein Lüfter am dedizierten 4-Pin-FAN-Anschluss des Pi 5 angeschlossen ist. Bei Nein wird die Lüfterkonfiguration übersprungen. Bei Ja kann ein Profil (Normal, Leise, Kühl) oder eine benutzerdefinierte Kurve gewählt werden. Die Auswahl wird vor der Ausführung angezeigt und muss bestätigt werden.

Die lokale Konfiguration liegt in /etc/pi5-basics.conf. Sie enthält einfache Ein/Aus-Werte. Nach einer Änderung kann der Installer erneut gestartet werden.

## Funkmodule

Wi-Fi und Bluetooth werden über rfkill blockiert, nicht durch Entfernen von Kernelmodulen oder Netzwerkpaketen. Ethernet bleibt unberührt. Falls Du später WLAN benötigst:

~~~bash
sudo rfkill unblock wifi
sudo systemctl disable --now pi5-basics-block-radios.service
~~~

Danach die Datei /etc/pi5-basics.conf anpassen und den Installer erneut ausführen, damit die gewünschte Konfiguration konsistent bleibt.

## Automatische Updates

Bei Aktivierung wird unattended-upgrades installiert und der tägliche Paketlisten- und Upgrade-Lauf aktiviert. Das ersetzt keine regelmäßige Prüfung des Systems. Größere Distributions-Upgrades und EEPROM-Firmware-Upgrades erfolgen nicht automatisch durch dieses Projekt.

## ZRAM und Journal

ZRAM ergänzt den Arbeitsspeicher durch komprimierten Swap. Die Konfiguration verwendet einen moderaten Anteil; die tatsächliche Wirkung hängt von der Last ab.

Die Journalbegrenzung verhindert unbegrenztes Wachstum der persistenten und flüchtigen Logs. Für Fehleranalysen kann das Journal weiterhin mit journalctl gelesen werden.

## Deinstallation

Es gibt derzeit keinen automatischen Deinstaller, da Paketbesitz und bereits vorhandene Systemkonfigurationen nicht zuverlässig genug unterschieden werden können. Entferne Änderungen gezielt und prüfe vorher die Sicherungskopien. Für Funkmodule kann der Dienst deaktiviert werden; Journal-Drop-in und APT-Konfiguration können nach Prüfung entfernt werden.

## Protokoll

/var/log/pi5-basics-install.log

Bei Problemen bitte die letzten relevanten Zeilen zusammen mit cat /etc/os-release und pi-status prüfen.


## Lüfter am FAN-Anschluss

Die Lüftersteuerung des Raspberry Pi 5 erfolgt über die Firmware und den dedizierten 4-Pin-FAN-Anschluss. Die Abfrage im Installer bezieht sich ausdrücklich auf diesen Anschluss, nicht auf einen Lüfter an GPIO oder USB.

- **Normal:** 50 / 60 / 67,5 / 75 °C mit 30 / 49 / 69 / 100 % PWM (Firmwarewerte 75 / 125 / 175 / 255).
- **Leise:** spätere Anlaufstufen für weniger Geräusch, volle Leistung spätestens bei 75 °C.
- **Kühl:** frühere Anlaufstufen für niedrigere Temperaturen.
- **Benutzerdefiniert:** vier aufsteigende Temperaturschwellen (35–78 °C), vier aufsteigende PWM-Werte (0–255) und Hysterese (1–15 °C).

Vor der Änderung wird `/boot/firmware/config.txt` mit Zeitstempel gesichert. Der Installer ersetzt nur seinen eigenen markierten Abschnitt und lässt andere Konfigurationseinträge stehen. Änderungen werden nach einem Neustart aktiv. Wenn kein Lüfter bestätigt wird, wird die Datei nicht angefasst.

Ein 3-Pin-Lüfter oder ein Lüfter an GPIO/USB wird von dieser Abfrage nicht als kompatibler FAN-Header-Lüfter behandelt; dafür ist eine andere Steuerung nötig.
