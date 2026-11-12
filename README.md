# pi5-basics

**Automated setup and maintenance toolkit for Raspberry Pi 5 running Raspberry Pi OS Trixie.** Interactive configuration, essential system tools, security hardening, Ethernet-focused setup, and preparation for SSD boot with SD-card fallback.

- Hardware: Raspberry Pi 5 (8 GB target)
- OS: Raspberry Pi OS Trixie (64-bit recommended)
- Language: Bash
- License: MIT

> **Status:** Initial setup release. The installer configures the base system, installs helper commands, and deploys the authenticated LAN dashboard. SSD detection is currently read-only. It deliberately does not partition, format, clone, or change EEPROM boot order. SSD migration and boot activation are a separate, explicit step once the actual SSD and connection type are known.

## Goals

- Straightforward, repeatable setup for a Raspberry Pi 5.
- Interactive configuration with safe defaults and final confirmation.
- Keep the current SD-card installation bootable.
- Prepare for later SSD installation without requiring the SSD now.
- Avoid aggressive debloating or disabling services whose role is unclear.
- Make changes auditable, logged, and reversible where practical.

## Features

### Included packages

Midnight Commander (mc) is installed by default, plus htop, ncdu, curl, wget, nano, vim-tiny, unzip, rsync, smartmontools, lm-sensors, lsof, dnsutils, usbutils, pciutils, ethtool, jq and rfkill. Git is a prerequisite for cloning the repository and is installed before the project is downloaded; the installer therefore does not install it again.

Optional tools selected during setup: btop, tree and iotop.

### System configuration

- ZRAM with a conservative 25% setting, when enabled.
- Persistent journal limited to 200 MB; runtime journal limited to 100 MB.
- Optional unattended package upgrades.
- Optional radio blocking via rfkill (Wi-Fi and Bluetooth separately configurable).
- Optional watchdog installation only when requested and a watchdog device exists.
- Optional native Raspberry Pi 5 fan curve for a fan confirmed on the dedicated 4-pin FAN header; presets Normal, Quiet and Cool plus custom thresholds/PWM values. Existing `config.txt` is backed up before the managed section is updated.
- No blanket removal of services, no disabling of systemd-random-seed, and no disabling of fstrim.

The installer does not disable Ethernet, NetworkManager, SSH, Avahi, or other services indiscriminately. Fan control uses the Pi 5 firmware; it does not install a polling daemon. The fan question defaults to No. If no fan is confirmed, fan settings are left alone. It does not change SSH authentication. For the terminal only, it adds a separate nftables input chain for TCP port 7681; other ports and existing firewall chains are left untouched.

### Web dashboard

The installer also deploys an authenticated dashboard at `http://raspberrypi.local:8080` (or `http://<pi-address>:8080`). It provides live-on-refresh system cards, detailed status, backup, maintenance, read-only SSD preparation and an embedded interactive Linux terminal. Backup and maintenance require an explicit confirmation. Backup targets are restricted to mounted filesystems found under `/mnt` or `/media`.

The dashboard service runs as an unprivileged `pi5dashboard` user; a narrowly scoped root helper performs privileged maintenance, backup and password-file updates. The separate terminal uses `ttyd` on port 7681 and runs a Bash shell as the dedicated, unprivileged `pi5terminal` user. It allows one connected browser client, requires separate HTTP Basic Authentication credentials, and is protected by a dedicated nftables input chain that accepts connections to port 7681 only from the subnet(s) assigned to the default-route interface (IPv4 and IPv6). Outbound network access from the shell remains available. The terminal account has no sudo rights and is not used by the dashboard helper. The terminal password is generated once and stored in `/etc/pi5-basics-terminal.env` (root-only, mode 0600); the installer prints it at setup. To retrieve it later, use `sudo cat /etc/pi5-basics-terminal.env`. The initial random dashboard password is stored in `/etc/pi5-basics-dashboard.token`; it can be changed in the authenticated dashboard under “Dashboard-Passwort ändern”. The dashboard accepts connections only from private/local IP ranges. **Use it only on a trusted home network; do not forward port 8080 from the internet. HTTP and the ttyd Basic Authentication exchange are not encrypted on the LAN**, so use only a trusted home network. Do not forward ports 8080 or 7681 from the internet. Remote VPN access is not enabled in this LAN-only configuration; it would require explicitly adding the VPN subnet to the terminal allowlist. For encrypted browser access on the LAN, put both services behind a correctly configured HTTPS reverse proxy.

### Helper commands

| Command | Purpose |
|---|---|
| pi-status | Overview of hardware, OS, memory, storage, temperature, network and radios |
| pi-maintenance | Interactive apt update/upgrade, cleanup and journal vacuum |
| pi-backup /mount/point | File-level backup of key system directories |
| pi-ssd-prepare | Read-only inventory of storage and bootloader settings |

## Quick start

Clone the repository and run the installer:

~~~bash
sudo apt update
sudo apt install -y git
git clone https://github.com/pennynet/pi5-basics.git
cd pi5-basics
sudo bash install.sh
~~~

To skip all installer questions and use the saved `/etc/pi5-basics.conf` (or first-run defaults):

~~~bash
sudo bash install.sh --non-interactive
~~~

The installer checks the OS release and hardware, presents configuration options, saves choices to /etc/pi5-basics.conf, shows planned settings and asks for confirmation.

Install log: /var/log/pi5-basics-install.log

### Non-interactive execution

Use `sudo bash install.sh --non-interactive` to skip all questions and the final confirmation. The installer uses the saved `/etc/pi5-basics.conf`, or copies `config/defaults.conf` on first run. Without the option, interactive questions remain enabled when run in a terminal.

## Interactive options

| Option | Default | Effect |
|---|---:|---|
| Optional diagnostic tools | On | Installs btop, tree and iotop |
| Disable Wi-Fi | On | Blocks Wi-Fi with rfkill at boot |
| Disable Bluetooth | On | Blocks Bluetooth with rfkill at boot |
| Enable ZRAM | On | Installs/configures zram-tools |
| Automatic security updates | On | Enables unattended-upgrades timers |
| Limit system journal | On | Applies journal size limits above |
| Hardware watchdog | Off | Installs/enables watchdog only if /dev/watchdog exists |
| Fan connected to Pi 5 FAN header | Off / ask during interactive setup | Configures firmware fan thresholds only after explicit confirmation; offers presets and custom values |

Edit /etc/pi5-basics.conf and rerun sudo bash install.sh to apply changed settings. The installer is designed to be repeatable, but review changes before confirming.

## SSD and SD fallback plan

The SSD is not required for initial setup. The Pi continues to boot from its current SD card.

When the SSD is available, first identify whether it is:
- NVMe over PCIe (for example, an M.2 HAT or PCIe adapter).
- USB SSD (SATA or NVMe enclosure/adapter).

Run the read-only inventory:

~~~bash
sudo pi-ssd-prepare
~~~

This reports block devices, transport type, model, NVMe controller presence and relevant EEPROM settings. It makes no changes.

The later migration/activation procedure must be selected for the actual connection type. It should include a verified backup, SSD health and capacity checks, a controlled system clone or fresh installation, a boot test, and only then a boot-order change. Keep the SD card unchanged until the SSD has booted successfully.

**Important:** EEPROM fallback is a bootloader-level fallback. It can help when the bootloader cannot find a usable boot partition/kernel on the first device. It does not guarantee recovery if Linux starts from the SSD and subsequently fails to mount its root filesystem or crashes later. See docs/boot-recovery.md.

Do not copy an EEPROM BOOT_ORDER value blindly. Raspberry Pi boot-order nibbles are evaluated from right to left, and NVMe and USB mass-storage use different codes. The exact setting depends on hardware and firmware.

## Backups

Example:

~~~bash
lsblk -f
sudo mkdir -p /mnt/backup
# Mount your separate backup disk at /mnt/backup first.
sudo pi-backup /mnt/backup
~~~

The helper backs up /etc, /home, /root and /boot/firmware using rsync. This is a **file-level backup**, not a bootable image and not a substitute for a tested full-system recovery plan. The destination should be a separate, mounted disk or network filesystem.

## Maintenance and status

~~~bash
pi-status
sudo pi-maintenance
sudo pi-ssd-prepare
~~~

## Safety and design decisions

- No automatic partitioning or formatting.
- No automatic SSD cloning.
- No automatic EEPROM or boot-order modification.
- No removal of packages/services based on broad assumptions.
- No changes to SSH keys or SSH policy; only a dedicated nftables input chain for terminal TCP port 7681 is added.
- Configuration is stored in /etc/pi5-basics.conf.
- Installer logs actions to /var/log/pi5-basics-install.log.

Before using on a production or remote system, ensure you have a working backup and local console access.

## Troubleshooting

See docs/troubleshooting.md, docs/installation.md, and docs/boot-recovery.md.

## Project layout

~~~text
pi5-basics/
├── install.sh
├── README.md
├── LICENSE
├── .gitignore
├── config/
│   └── defaults.conf
├── dashboard/
│   ├── app.py
│   └── action
├── systemd/
│   ├── pi5-dashboard.service
│   ├── pi5-terminal.service\n│   └── pi5-terminal-firewall
├── commands/
│   ├── pi-status
│   ├── pi-maintenance
│   ├── pi-backup
│   └── pi-ssd-prepare
└── docs/
    ├── installation.md
    ├── boot-recovery.md
    └── troubleshooting.md
~~~

## Contributing

Issues and pull requests are welcome. Please include the Raspberry Pi model, OS release, relevant command output and installer log excerpts. Remove passwords, tokens, public IPs and other sensitive data before posting.

## License

MIT. See LICENSE.
