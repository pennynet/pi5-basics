# SSD-Boot und SD-Fallback

## Grundsatz

Die Erstinstallation von pi5-basics verändert die Bootreihenfolge nicht. Der Raspberry Pi startet weiter von der vorhandenen SD-Karte. Erst wenn die konkrete SSD angeschlossen und geprüft wurde, sollte eine Migration oder Bootloader-Änderung erfolgen.

## SSD-Anschlussarten

### NVMe über PCIe

Bei einer NVMe-SSD am PCIe-Anschluss des Pi 5 müssen Hardwareadapter, PCIe-Konfiguration und EEPROM-Firmware zusammenpassen. Bei manchen Nicht-HAT+-Lösungen kann eine PCIe-Erkennungseinstellung wie PCIE_PROBE erforderlich sein. Nicht blind übernehmen: Adapter- und Firmware-Dokumentation prüfen.

### SSD über USB

Eine SATA- oder NVMe-SSD in einem USB-Gehäuse wird als USB-Massenspeicher behandelt. Die Kompatibilität hängt auch vom USB-Gehäuse und dessen Bridge-Chip ab.

## Vorbereitungscheck

Wenn die SSD angeschlossen ist:

~~~bash
sudo pi-ssd-prepare
lsblk -o NAME,PATH,SIZE,TRAN,FSTYPE,UUID,MODEL,MOUNTPOINTS
sudo smartctl --scan
~~~

Vor jeder Migration Modell, Kapazität und Gerätepfad eindeutig feststellen. Gerätebezeichnungen wie /dev/sda können sich ändern. Nicht allein anhand eines Gerätenamens entscheiden, welche Platte gelöscht oder überschrieben wird.

## Bootreihenfolge

Die Raspberry-Pi-EEPROM-Bootreihenfolge wird als Folge von Hex-Ziffern angegeben und von rechts nach links ausgewertet. Häufig relevante Codes sind:

- 6: NVMe
- 4: USB-Massenspeicher
- 1: SD-Karte
- f: Bootsequenz neu starten

Die konkrete Kombination muss zur gewünschten Reihenfolge und zur angeschlossenen Hardware passen. NVMe-first und USB-first sind unterschiedliche Konfigurationen. Prüfe vor Änderungen die aktuelle offizielle Raspberry-Pi-Dokumentation und die Ausgabe von rpi-eeprom-config.

## Sicherer Ablauf für die spätere Aktivierung

1. Vollständiges, geprüftes Backup der SD-Karte erstellen.
2. SSD anschließen und mit pi-ssd-prepare identifizieren.
3. SMART-/Gesundheitsstatus und Kapazität prüfen.
4. Klären, ob das bestehende System geklont oder frisch installiert werden soll.
5. SSD vorbereiten und Daten übertragen; dabei sicherstellen, dass PARTUUID/UUID und Boot-Konfiguration konsistent sind.
6. Ersten SSD-Start mit erreichbarer lokaler Konsole testen.
7. Erst nach erfolgreichem Test die EEPROM-Bootreihenfolge auf SSD zuerst und SD danach setzen.
8. SD-Karte unverändert als Rettungsmedium aufbewahren und den Fallback separat testen.

## Grenzen des Fallbacks

Der EEPROM-Bootloader kann zum nächsten Medium wechseln, wenn er auf dem ersten Medium keinen startfähigen Bootpfad findet. Das ist kein vollständiges Hochverfügbarkeits- oder Recovery-System. Wenn Linux vom SSD-Bootmedium startet, aber später das Root-Dateisystem nicht mounten kann, kann der Bootloader-Fallback bereits vorbei sein.

Für echte Ausfallsicherheit sind zusätzlich ein aktuelles Backup und ein getesteter Wiederherstellungsweg erforderlich.

## Firmware und offizielle Dokumentation

Vor dem Umschalten die aktuelle Dokumentation konsultieren:

- Raspberry Pi EEPROM configuration: https://www.raspberrypi.com/documentation/computers/raspberry-pi.html#raspi-config
- Raspberry Pi bootloader configuration: https://www.raspberrypi.com/documentation/computers/raspberry-pi.html#bootloader_configuration

Dieses Projekt setzt EEPROM-Parameter absichtlich nicht automatisch.
