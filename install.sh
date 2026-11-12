#!/usr/bin/env bash
set -Eeuo pipefail

PROJECT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
DEFAULTS_FILE="$PROJECT_DIR/config/defaults.conf"
CONFIG_FILE="/etc/pi5-basics.conf"
LOG_FILE="/var/log/pi5-basics-install.log"

if [[ $EUID -ne 0 ]]; then
  echo "Bitte mit sudo starten: sudo bash install.sh" >&2
  exit 1
fi
if [[ ! -r /etc/os-release ]]; then echo "OS-Version nicht ermittelbar."; exit 1; fi
. /etc/os-release
if [[ "${ID:-}" != "raspbian" && "${ID:-}" != "debian" ]]; then
  echo "Nicht unterstütztes Betriebssystem: ${PRETTY_NAME:-unbekannt}"; exit 1
fi
if [[ "${VERSION_CODENAME:-}" != "trixie" ]]; then
  echo "Dieses Projekt ist für Raspberry Pi OS Trixie vorgesehen (gefunden: ${VERSION_CODENAME:-unbekannt})."
  exit 1
fi
MODEL="$(tr -d '\0' </proc/device-tree/model 2>/dev/null || true)"
if [[ "$MODEL" != *"Raspberry Pi 5"* ]]; then
  echo "Warnung: Raspberry Pi 5 nicht eindeutig erkannt (${MODEL:-unbekannt})."
  read -r -p "Trotzdem fortfahren? [j/N] " answer
  [[ "$answer" =~ ^[JjYy]$ ]] || exit 1
fi

mkdir -p /var/log
touch "$LOG_FILE"
exec > >(tee -a "$LOG_FILE") 2>&1
trap 'echo "FEHLER in Zeile $LINENO. Details: $LOG_FILE" >&2' ERR

echo "=== pi5-basics Installer ==="
echo "System: ${PRETTY_NAME:-unbekannt}"
echo "Modell: ${MODEL:-unbekannt}"
echo "Die Bootreihenfolge wird NICHT geändert. SSD-Vorbereitung erfolgt separat."

if [[ ! -f "$CONFIG_FILE" ]]; then
  install -D -m 0644 "$DEFAULTS_FILE" "$CONFIG_FILE"
fi
# shellcheck disable=SC1090
. "$CONFIG_FILE"

ask() {
  local prompt="$1" current="$2" answer
  [[ -t 0 ]] || { printf '%s' "$current"; return; }
  read -r -p "$prompt [j/N] " answer
  if [[ "$answer" =~ ^[JjYy]$ ]]; then printf '1'; else printf '0'; fi
}
echo
echo "Interaktive Konfiguration (Enter/Nein übernimmt den sicheren Standard Nein)."
if [[ -t 0 ]]; then
  INSTALL_OPTIONAL_TOOLS="$(ask "Zusätzliche Diagnosewerkzeuge installieren?" "$INSTALL_OPTIONAL_TOOLS")"
  DISABLE_WIFI="$(ask "WLAN per rfkill deaktivieren?" "$DISABLE_WIFI")"
  DISABLE_BLUETOOTH="$(ask "Bluetooth per rfkill deaktivieren?" "$DISABLE_BLUETOOTH")"
  ENABLE_ZRAM="$(ask "ZRAM aktivieren?" "$ENABLE_ZRAM")"
  ENABLE_AUTO_UPDATES="$(ask "Automatische Sicherheitsupdates aktivieren?" "$ENABLE_AUTO_UPDATES")"
  LIMIT_JOURNAL="$(ask "System-Journal begrenzen (200 MB persistent)?" "$LIMIT_JOURNAL")"
  ENABLE_WATCHDOG="$(ask "Hardware-Watchdog aktivieren, falls vorhanden?" "$ENABLE_WATCHDOG")"
fi
cat >"$CONFIG_FILE" <<EOF
INSTALL_OPTIONAL_TOOLS=$INSTALL_OPTIONAL_TOOLS
DISABLE_WIFI=$DISABLE_WIFI
DISABLE_BLUETOOTH=$DISABLE_BLUETOOTH
ENABLE_ZRAM=$ENABLE_ZRAM
ENABLE_AUTO_UPDATES=$ENABLE_AUTO_UPDATES
LIMIT_JOURNAL=$LIMIT_JOURNAL
ENABLE_WATCHDOG=$ENABLE_WATCHDOG
EOF
chmod 0644 "$CONFIG_FILE"

echo
echo "Geplante Einstellungen:"
cat "$CONFIG_FILE"
if [[ -t 0 ]]; then
  read -r -p "Installation jetzt durchführen? [j/N] " confirm
  [[ "$confirm" =~ ^[JjYy]$ ]] || { echo "Abgebrochen; Konfiguration gespeichert."; exit 0; }
fi

export DEBIAN_FRONTEND=noninteractive
apt-get update
BASE_PACKAGES=(mc htop ncdu git curl wget nano vim-tiny unzip rsync smartmontools lm-sensors lsof dnsutils usbutils pciutils ethtool jq rfkill)
OPTIONAL_PACKAGES=(btop tree iotop)
apt-get install -y "${BASE_PACKAGES[@]}"
if [[ "$INSTALL_OPTIONAL_TOOLS" == "1" ]]; then apt-get install -y "${OPTIONAL_PACKAGES[@]}"; fi
if [[ "$ENABLE_ZRAM" == "1" ]]; then apt-get install -y zram-tools; fi
if [[ "$ENABLE_AUTO_UPDATES" == "1" ]]; then apt-get install -y unattended-upgrades; fi

if [[ "$ENABLE_ZRAM" == "1" && -f /etc/default/zramswap ]]; then
  cp -a /etc/default/zramswap "/etc/default/zramswap.pi5-basics.bak"
  sed -i -E 's/^#?PERCENT=.*/PERCENT=25/; s/^#?ALGO=.*/ALGO=zstd/' /etc/default/zramswap
  systemctl enable --now zramswap.service || systemctl restart zramswap.service || true
fi

if [[ "$LIMIT_JOURNAL" == "1" ]]; then
  install -d -m 0755 /etc/systemd/journald.conf.d
  cat >/etc/systemd/journald.conf.d/60-pi5-basics.conf <<'EOF'
[Journal]
SystemMaxUse=200M
RuntimeMaxUse=100M
EOF
  systemctl restart systemd-journald.service
fi

if [[ "$ENABLE_AUTO_UPDATES" == "1" ]]; then
  cat >/etc/apt/apt.conf.d/20auto-upgrades <<'EOF'
APT::Periodic::Update-Package-Lists "1";
APT::Periodic::Unattended-Upgrade "1";
EOF
  systemctl enable --now apt-daily.timer apt-daily-upgrade.timer
fi

# Use rfkill through a small oneshot service; do not remove NetworkManager or networking packages.
if [[ "$DISABLE_WIFI" == "1" || "$DISABLE_BLUETOOTH" == "1" ]]; then
  install -d -m 0755 /usr/local/sbin
  cat >/usr/local/sbin/pi5-basics-block-radios <<'EOF'
#!/bin/sh
set -eu
if command -v rfkill >/dev/null 2>&1; then
  rfkill block wifi || true
  rfkill block bluetooth || true
fi
EOF
  chmod 0755 /usr/local/sbin/pi5-basics-block-radios
  # Restore any radio not selected by configuration.
  if [[ "$DISABLE_WIFI" != "1" ]]; then sed -i '/rfkill block wifi/d' /usr/local/sbin/pi5-basics-block-radios; fi
  if [[ "$DISABLE_BLUETOOTH" != "1" ]]; then sed -i '/rfkill block bluetooth/d' /usr/local/sbin/pi5-basics-block-radios; fi
  cat >/etc/systemd/system/pi5-basics-block-radios.service <<'EOF'
[Unit]
Description=Block radios disabled by pi5-basics
After=systemd-udev-settle.service
Wants=systemd-udev-settle.service

[Service]
Type=oneshot
ExecStart=/usr/local/sbin/pi5-basics-block-radios
RemainAfterExit=yes

[Install]
WantedBy=multi-user.target
EOF
  systemctl daemon-reload
  systemctl enable --now pi5-basics-block-radios.service
fi

# Install helper commands from the checked-out project.
install -m 0755 "$PROJECT_DIR/commands/pi-status" /usr/local/bin/pi-status
install -m 0755 "$PROJECT_DIR/commands/pi-maintenance" /usr/local/bin/pi-maintenance
install -m 0755 "$PROJECT_DIR/commands/pi-backup" /usr/local/bin/pi-backup
install -m 0755 "$PROJECT_DIR/commands/pi-ssd-prepare" /usr/local/bin/pi-ssd-prepare

if [[ "$ENABLE_WATCHDOG" == "1" && -e /dev/watchdog ]]; then
  apt-get install -y watchdog
  systemctl enable --now watchdog.service || echo "Watchdog konnte nicht automatisch aktiviert werden; bitte manuell prüfen."
elif [[ "$ENABLE_WATCHDOG" == "1" ]]; then
  echo "Kein /dev/watchdog gefunden; Watchdog wurde nicht aktiviert."
fi

echo
echo "Installation abgeschlossen."
echo "Prüfen: pi-status"
echo "SSD-Vorbereitung: pi-ssd-prepare"
echo "Protokoll: $LOG_FILE"
echo "Hinweis: Die Bootreihenfolge wurde nicht verändert."
