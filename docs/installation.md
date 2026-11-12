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
# Git wird nur für den Download benötigt; der Installer installiert es nicht erneut.
git clone https://github.com/pennynet/pi5-basics.git
cd pi5-basics
sudo bash install.sh
~~~

Alle Rückfragen und die abschließende Bestätigung lassen sich überspringen:

~~~bash
sudo bash install.sh --non-interactive
~~~

Dabei werden die vorhandenen Einstellungen aus `/etc/pi5-basics.conf` verwendet. Bei der ersten Installation gelten die Werte aus `config/defaults.conf`.

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


## Web-Dashboard

Der Installer richtet einen Webdienst auf Port 8080 ein. Im Heimnetz ist er üblicherweise unter `http://raspberrypi.local:8080` oder über die IP-Adresse des Pi erreichbar.

Das zufällig erzeugte Kennwort wird bei der Installation ausgegeben und liegt in `/etc/pi5-basics-dashboard.token`. Es kann nach der Anmeldung direkt im Dashboard im Abschnitt „Dashboard-Passwort ändern“ geändert werden. Das neue Passwort muss mindestens 12 Zeichen lang sein; nach der Änderung ist eine erneute Anmeldung erforderlich.

Der Dienst läuft als unprivilegierter Benutzer `pi5dashboard`. Nur ein fest begrenzter Root-Helfer darf Wartung oder Backup ausführen. Beide Aktionen verlangen eine Bestätigung im Browser. Für Backups werden nur aktuell eingehängte Dateisysteme direkt unter `/mnt` oder `/media` angeboten. SSD Prepare und Status sind lesende Aktionen.

**Sicherheit:** Das Dashboard ist für ein vertrauenswürdiges privates Heimnetz gedacht. HTTP verschlüsselt die Verbindung nicht. Port 8080 keinesfalls ins Internet weiterleiten. Für Fernzugriff VPN (z. B. Tailscale) oder einen korrekt eingerichteten HTTPS-Reverse-Proxy verwenden.

Dienst prüfen:

~~~bash
sudo systemctl status pi5-dashboard
sudo journalctl -u pi5-dashboard -n 50 --no-pager
~~~


## Interaktives Linux-Terminal

Der Installer installiert `ttyd` und richtet einen eigenen Dienst auf Port 7681 ein. Das Dashboard bettet das Terminal ein; alternativ kann es separat unter `http://<pi-ip>:7681` geöffnet werden.

- Linux-Benutzer: `pi5terminal`, Shell: Bash, Home: `/home/pi5terminal`.
- Eine gleichzeitige Browserverbindung (`--max-clients 1`).
- Separate HTTP-Basic-Authentication-Zugangsdaten; das Passwort wird bei der ersten Installation zufällig erzeugt und bei erneuter Installation beibehalten.
- Zugangsdaten liegen in `/etc/pi5-basics-terminal.env`, Eigentümer root, Modus 0600. Später anzeigen: `sudo cat /etc/pi5-basics-terminal.env`.
- Der Terminalbenutzer ist nicht Mitglied der sudo-Gruppe und erhält keine sudo-Regel. Für Root-Aufgaben weiterhin SSH oder lokale Konsole mit einem administrativen Benutzer verwenden.
- systemd begrenzt den Netzwerkzugriff auf private IPv4-Netze sowie IPv6 ULA-/Link-Local-Bereiche. Der Dienst lauscht auf Port 7681; die IP-Filter werden durch systemd/cgroup-BPF durchgesetzt.
- Der Dienst läuft mit gehärteten systemd-Einstellungen und ohne Linux-Capabilities.

**Wichtige Transportgrenze:** ttyd verwendet hier HTTP/WebSocket ohne TLS. Basic Authentication verschlüsselt das Passwort nicht. Deshalb ausschließlich in einem vertrauenswürdigen Heimnetz betreiben, niemals Port 7681 oder 8080 ins Internet weiterleiten. Für Fernzugriff VPN verwenden; für verschlüsselten Browserzugriff im LAN beide Dienste hinter einen korrekt konfigurierten HTTPS-Reverse-Proxy stellen.

Dienst prüfen:

~~~bash
sudo systemctl status pi5-terminal
sudo journalctl -u pi5-terminal -n 50 --no-pager
sudo ss -ltnp | grep ':7681'
~~~

Terminaldienst stoppen/deaktivieren:

~~~bash
sudo systemctl disable --now pi5-terminal
~~~

Bei erneutem Installerlauf wird der Dienst wieder aktiviert. Das Terminalpasswort kann nicht über das Dashboard geändert werden; eine Rotation erfordert eine kontrollierte Änderung von `/etc/pi5-basics-terminal.env` und einen Neustart des Dienstes.
