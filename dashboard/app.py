#!/usr/bin/env python3
"""Small, authenticated LAN dashboard for pi5-basics. Standard library only."""
import html
import http.cookies
import ipaddress
import os
import secrets
import socket
import shutil
import subprocess
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs

TOKEN_FILE = Path("/etc/pi5-basics-dashboard.token")
PORT = 8080
SESSIONS = {}
try:
    DASHBOARD_PASSWORD = TOKEN_FILE.read_text().strip()
except OSError:
    DASHBOARD_PASSWORD = ""

def run_readonly(command, timeout=20):
    try:
        p = subprocess.run(command, text=True, stdout=subprocess.PIPE,
                           stderr=subprocess.STDOUT, timeout=timeout, check=False)
        return p.stdout[-12000:]
    except Exception as exc:
        return f"Fehler: {exc}"

def system_data():
    model = Path("/proc/device-tree/model").read_bytes().decode(errors="replace").strip("\0") if Path("/proc/device-tree/model").exists() else "Unbekannt"
    try:
        temp = float(Path("/sys/class/thermal/thermal_zone0/temp").read_text().strip()) / 1000
        temperature = f"{temp:.1f} °C"
    except Exception:
        temperature = "Nicht verfügbar"
    try:
        mem = {}
        for line in Path("/proc/meminfo").read_text().splitlines():
            key, value = line.split(":", 1)
            mem[key] = int(value.strip().split()[0])
        used = mem["MemTotal"] - mem.get("MemAvailable", 0)
        ram = f"{used/1024:.0f} / {mem['MemTotal']/1024:.0f} MiB ({used/mem['MemTotal']*100:.0f} %)"
    except Exception:
        ram = "Nicht verfügbar"
    uptime = run_readonly(["uptime", "-p"], 5).strip()
    os_name = "Unbekannt"
    try:
        for line in Path("/etc/os-release").read_text().splitlines():
            if line.startswith("PRETTY_NAME="):
                os_name = line.split("=",1)[1].strip().strip('"')
    except Exception:
        pass
    return model, temperature, ram, uptime, os_name

def network_data():
    """Return interface and IPv4 information only; IPv6 addresses are intentionally hidden."""
    output = run_readonly(["/usr/sbin/ip", "-brief", "address"], 5)
    if output and not output.startswith("Fehler:") and output.strip():
        lines = []
        for line in output.splitlines():
            parts = line.split()
            if not parts or parts[0] == "lo":
                continue
            ipv4 = []
            for item in parts[2:]:
                try:
                    if ipaddress.ip_interface(item).version == 4:
                        ipv4.append(item)
                except ValueError:
                    continue
            if ipv4:
                lines.append(" ".join(parts[:2] + ipv4))
        if lines:
            return "\n".join(lines)
    fallback = run_readonly(["/usr/bin/hostname", "-I"], 5).strip()
    ipv4 = []
    for item in fallback.split():
        try:
            if ipaddress.ip_address(item).version == 4:
                ipv4.append(item)
        except ValueError:
            pass
    return "IPv4: " + " ".join(ipv4) if ipv4 else "Keine IPv4-Netzwerkadresse ermittelbar."

def mounted_targets():
    found = []
    for root in (Path("/mnt"), Path("/media")):
        if root.exists():
            # Cover /mnt/disk and common desktop automounts such as /media/user/disk.
            for pattern in ("*", "*/*"):
                for p in root.glob(pattern):
                    try:
                        if p.is_dir() and os.path.ismount(p):
                            found.append(str(p))
                    except OSError:
                        pass
    return sorted(set(found))

def page(title, body, csrf="", header_right="", header_label="Raspberry Pi 5"):
    return """<!doctype html><html lang="de"><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>pi5-basics · """ + html.escape(title) + """</title>
<style>
:root{color-scheme:dark;--bg:#101820;--panel:#1b2935;--line:#304353;--txt:#edf4f8;--muted:#a9bac7;--accent:#79c0ff}
*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--txt);font:16px system-ui,sans-serif}
header,main{max-width:1600px;margin:auto;padding:20px}header{display:flex;justify-content:space-between;align-items:center;border-bottom:1px solid var(--line);background:#172633}
h1{font-size:1.3rem;margin:0}h2{font-size:1.1rem;margin-top:0}.muted{color:var(--muted);font-size:.9rem}
.grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(220px,1fr));gap:12px}.value{font-size:1.35rem}.card{box-shadow:0 3px 12px #0002}.metricbar{height:9px;background:#344958;border-radius:99px;overflow:hidden;margin-top:10px}.metricbar span{display:block;height:100%;background:#48c6d8;border-radius:99px}.metricbar.good span{background:#55d6a0}.metricbar.warn span{background:#e8b75b}.metricbar.bad span{background:#ed766b}.alertbox{border:1px solid #a65c42;background:#422c29;border-radius:12px;padding:14px;margin-bottom:14px;color:#ffd1c6}@media(max-width:760px){header,main{padding:14px}}
.card{background:var(--panel);border:1px solid var(--line);border-radius:14px;padding:16px;margin-bottom:14px}.maintenance-card,.maintenance-card *{font-weight:400}
.value{font-size:1.2rem;font-weight:650;overflow-wrap:anywhere}.actions{display:grid;grid-template-columns:repeat(auto-fit,minmax(220px,1fr));gap:12px}
button,.button,select,input{font:inherit;border-radius:9px;padding:11px 14px;border:1px solid var(--line);background:#263b4c;color:var(--txt)}
button{cursor:pointer;background:#174d76;border-color:#347eb3}button:hover{background:#206493}
input[type=password]{width:100%;margin:10px 0}select{width:100%;margin:8px 0}
pre{white-space:pre-wrap;overflow-wrap:anywhere;background:#0b1218;padding:14px;border-radius:10px;max-height:420px;overflow:auto}
form{margin:0}label{display:block;margin:8px 0}.header-actions{display:flex;align-items:center;gap:12px}.password-row{display:grid;grid-template-columns:minmax(0,1fr) auto;gap:12px;align-items:end}.password-fields{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:12px}.password-fields input{width:100%;margin:6px 0}.password-row button{margin-bottom:6px}@media(max-width:760px){.password-row{grid-template-columns:1fr}.password-row button{justify-self:start}}@media(max-width:600px){.password-fields{grid-template-columns:1fr}}.danger{background:#54302c;border-color:#9b554b}
a{color:var(--accent)}footer{max-width:1050px;margin:auto;padding:10px 20px 30px;color:var(--muted);font-size:.85rem}
</style>
<header><div><h1>🍓 pi5-basics</h1><span class="muted">""" + html.escape(header_label) + """</span></div>""" + header_right + """</header>
<main>""" + body + """</main><footer>Nur im vertrauenswürdigen Heimnetz verwenden. Keine Portweiterleitung aus dem Internet einrichten.</footer></html>"""

class Handler(BaseHTTPRequestHandler):
    server_version = "pi5-basics-dashboard/1.0"

    def private_client(self):
        try:
            ip = ipaddress.ip_address(self.client_address[0].split("%")[0])
            return ip.is_private or ip.is_loopback or ip.is_link_local
        except ValueError:
            return False

    def session(self):
        cookie = http.cookies.SimpleCookie(self.headers.get("Cookie", ""))
        morsel = cookie.get("pi5session")
        return SESSIONS.get(morsel.value) if morsel else None

    def send(self, status, content, cookie=None):
        data = content.encode()
        self.send_response(status)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("X-Frame-Options", "DENY")
        self.send_header("Referrer-Policy", "no-referrer")
        self.send_header("Content-Security-Policy", "default-src 'self'; style-src 'unsafe-inline'; form-action 'self'; frame-src http://*:7681; frame-ancestors 'none'")
        if cookie:
            self.send_header("Set-Cookie", cookie)
        self.end_headers()
        self.wfile.write(data)

    def read_form(self):
        length = min(int(self.headers.get("Content-Length", "0")), 8192)
        return parse_qs(self.rfile.read(length).decode(errors="replace"))

    def do_GET(self):
        if not self.private_client():
            return self.send(403, "Zugriff nur aus privaten/lokalen Netzen erlaubt.")
        if not DASHBOARD_PASSWORD:
            return self.send(503, "Dashboard-Passwort fehlt. Installer erneut ausführen.")
        sess = self.session()
        if not sess:
            body = '<section class="card" style="max-width:420px;margin:50px auto"><h2>Anmeldung</h2><p class="muted">Das Dashboard-Passwort steht in der Installationsausgabe.</p><form method="post" action="/login"><input type="password" name="password" placeholder="Dashboard-Passwort" required autofocus><button>Anmelden</button></form></section>'
            return self.send(200, page("Anmeldung", body))
        csrf = sess["csrf"]
        if self.path == "/logout":
            return self.send(200, page("Abmelden", '<p>Zum Abmelden bitte die Schaltfläche verwenden.</p>'))
        model, temp, ram, uptime, os_name = system_data()
        network = network_data()
        maintenance_status = run_readonly(["sudo", "-n", "/usr/local/sbin/pi5-dashboard-action", "maintenance-status"], 5).strip()
        maintenance_enabled = maintenance_status.startswith("Automatische Wartung: aktiviert")
        host = self.connection.getsockname()[0].split("%", 1)[0]
        terminal_host = f"[{host}]" if ":" in host else host
        terminal_url = f"http://{terminal_host}:7681/"
        targets = mounted_targets()
        target_options = "".join(f'<option value="{html.escape(p, quote=True)}">{html.escape(p)}</option>' for p in targets)
        backup_form = (f'<form method="post" action="/action"><input type="hidden" name="csrf" value="{csrf}"><input type="hidden" name="action" value="backup"><label>Gemountetes Backup-Ziel</label><select name="target" required>{target_options}</select><label><input type="checkbox" name="confirm" value="yes" required> Ich bestätige, dass das ausgewählte Laufwerk mein Backup-Ziel ist.</label><button {"disabled" if not targets else ""}>Backup starten</button></form>' if targets else '<p class="muted">Kein eigenes Laufwerk unter /mnt oder /media eingehängt. Backup ist deshalb deaktiviert.</p>')
        alerts = []
        try:
            tval = float(temp.replace(" °C", ""))
            if tval >= 75:
                alerts.append(f"Hohe CPU-Temperatur: {temp}")
        except ValueError:
            pass
        try:
            meminfo = {}
            for line in Path("/proc/meminfo").read_text().splitlines():
                key, value = line.split(":", 1)
                meminfo[key] = int(value.strip().split()[0])
            ram_pct = round((meminfo["MemTotal"] - meminfo.get("MemAvailable", 0)) / meminfo["MemTotal"] * 100)
            if ram_pct >= 90:
                alerts.append(f"RAM-Auslastung hoch: {ram_pct} %")
        except Exception:
            ram_pct = 0
        try:
            usage = shutil.disk_usage("/")
            disk_pct = round(usage.used / usage.total * 100)
            if disk_pct >= 90:
                alerts.append(f"Root-Dateisystem fast voll: {disk_pct} %")
            disk_info = f"{usage.used / 2**30:.1f} / {usage.total / 2**30:.1f} GiB"
        except Exception:
            disk_pct, disk_info = 0, "Nicht verfügbar"
        for unit in ("pi5-dashboard.service", "pi5-terminal.service", "nginx.service"):
            state = run_readonly(["/usr/bin/systemctl", "is-active", unit], 5).strip()
            if state != "active":
                alerts.append(f"{unit}: {state or 'unbekannt'}")
        alert_html = ('<div class="alertbox"><strong>⚠ Probleme erkannt</strong><ul>' + ''.join('<li>' + html.escape(item) + '</li>' for item in alerts) + '</ul></div>') if alerts else ""
        body = f"""
{alert_html}
<div class="actions">
<section class="card storage-card"><h2>Backup &amp; SSD</h2><p class="muted">Datei-Backup von /etc, /home, /root und /boot/firmware auf ein separates, eingehängtes Laufwerk.</p>{backup_form}<hr style="border:0;border-top:1px solid var(--line);margin:16px 0"><p class="muted">Rein lesende Bestandsaufnahme von Datenträgern, NVMe und Bootloader.</p><form method="post" action="/action"><input type="hidden" name="csrf" value="{csrf}"><input type="hidden" name="action" value="ssd"><button>SSD-Status anzeigen</button></form></section>
<section class="card maintenance-card"><h2>Wartung</h2><p class="muted">Manuelle Systemwartung: Paketlisten und Pakete aktualisieren, verwaiste Pakete entfernen und Journal aufräumen.</p><form method="post" action="/action"><input type="hidden" name="csrf" value="{csrf}"><input type="hidden" name="action" value="maintenance"><label><input type="checkbox" name="confirm" value="yes" required> Ich möchte die Systemwartung jetzt ausführen.</label><button class="danger">Wartung starten</button></form><hr style="border:0;border-top:1px solid var(--line);margin:16px 0"><p class="muted">Automatische Wartung: wöchentlich sonntags um 04:00 Uhr. Kein automatischer Neustart. Protokoll: /var/log/pi5-basics-maintenance.log</p><form method="post" action="/action"><input type="hidden" name="csrf" value="{csrf}"><input type="hidden" name="action" value="{ "maintenance-disable" if maintenance_enabled else "maintenance-enable" }"><button class="{ "danger" if maintenance_enabled else "" }">{ "Automatische Wartung deaktivieren" if maintenance_enabled else "Automatische Wartung aktivieren" }</button></form></section>
<section class="card"><h2>Systemdetails</h2><p class="muted">Ausgabe der vorhandenen pi-status-Funktion.</p><form method="post" action="/action"><input type="hidden" name="csrf" value="{csrf}"><input type="hidden" name="action" value="status"><button>Statusdetails anzeigen</button></form></section>
</div>
<div class="grid">
<div class="card"><div class="muted">CPU-Temperatur</div><div class="value">{html.escape(temp)}</div><div class="metricbar { "bad" if "tval" in locals() and tval >= 75 else "warn" if "tval" in locals() and tval >= 60 else "" }"><span style="width:{min(100, max(0, tval if "tval" in locals() else 0)):.0f}%"></span></div><p class="muted">Warnschwelle 75 °C</p></div>
<div class="card"><div class="muted">RAM-Auslastung</div><div class="value">{html.escape(ram)}</div><div class="metricbar { "bad" if ram_pct >= 90 else "warn" if ram_pct >= 75 else "good" }"><span style="width:{ram_pct}%"></span></div></div>
<div class="card"><div class="muted">Root-Speicher</div><div class="value">{disk_pct} %</div><div class="metricbar { "bad" if disk_pct >= 90 else "warn" if disk_pct >= 75 else "good" }"><span style="width:{disk_pct}%"></span></div><p class="muted">{html.escape(disk_info)}</p></div>

</div>

<section class="card"><h2>Linux-Terminal</h2><p class="muted">Interaktive Bash-Sitzung als Administrator pi5terminal mit vollständigen sudo-Rechten. Ein gleichzeitiger Browser-Client.</p><iframe title="Linux-Terminal" src="{html.escape(terminal_url, quote=True)}" style="display:block;width:100%;height:520px;border:1px solid var(--line);border-radius:10px;background:#0b1218" referrerpolicy="no-referrer"></iframe><p class="muted">Beim ersten Öffnen fragt der Browser nach den separaten Terminal-Zugangsdaten. Es ist absichtlich nur eine gleichzeitige Terminalsitzung zugelassen.</p></section>
<section class="card"><h2>Dashboard-Passwort ändern</h2><p class="muted">Mindestens 12 Zeichen. Nach der Änderung wirst du abgemeldet und musst dich mit dem neuen Passwort erneut anmelden.</p><form method="post" action="/password"><input type="hidden" name="csrf" value="{csrf}"><div class="password-row"><div class="password-fields"><div><label>Neues Passwort</label><input type="password" name="new_password" minlength="12" maxlength="256" autocomplete="new-password" required></div><div><label>Neues Passwort bestätigen</label><input type="password" name="confirm_password" minlength="12" maxlength="256" autocomplete="new-password" required></div></div><button>Passwort ändern</button></div></form></section>

"""
        body += '<script>setTimeout(function(){location.reload()},5000);</script>'
        header_right = f'<div class="header-actions"><form method="post" action="/action"><input type="hidden" name="csrf" value="{csrf}"><input type="hidden" name="action" value="shutdown"><button class="danger" type="submit" onclick="return confirm(&quot;Soll der Raspberry Pi wirklich heruntergefahren werden?&quot;)">Shutdown</button></form><form method="post" action="/action"><input type="hidden" name="csrf" value="{csrf}"><input type="hidden" name="action" value="reboot"><button type="submit" onclick="return confirm(&quot;Soll der Raspberry Pi wirklich neu gestartet werden?&quot;)">Reboot</button></form><form method="post" action="/logout"><input type="hidden" name="csrf" value="{csrf}"><button class="danger">Abmelden</button></form></div>'
        header_info = f"{model} · {os_name} · IPv4: {network.replace(chr(10), ' | ')} · Laufzeit: {uptime}"
        self.send(200, page("Dashboard", body, header_right=header_right, header_label=header_info))

    def do_POST(self):
        global DASHBOARD_PASSWORD
        if not self.private_client():
            return self.send(403, "Zugriff verweigert.")
        form = self.read_form()
        if self.path == "/login":
            supplied = form.get("password", [""])[0]
            if secrets.compare_digest(supplied, DASHBOARD_PASSWORD):
                sid = secrets.token_urlsafe(32)
                SESSIONS[sid] = {"csrf": secrets.token_urlsafe(24)}
                self.send_response(303)
                self.send_header("Location", "/")
                self.send_header("Set-Cookie", f"pi5session={sid}; HttpOnly; SameSite=Strict; Path=/; Max-Age=28800")
                self.send_header("Cache-Control", "no-store")
                self.send_header("Content-Length", "0")
                self.end_headers()
                return
            time.sleep(1)
            return self.send(401, page("Anmeldung", '<p>Anmeldung fehlgeschlagen.</p><a href="/">Erneut versuchen</a>'))
        sess = self.session()
        if not sess:
            return self.send(401, page("Anmeldung", '<p>Bitte erneut anmelden. <a href="/">Anmelden</a></p>'))
        if not secrets.compare_digest(form.get("csrf", [""])[0], sess["csrf"]):
            return self.send(403, page("Fehler", "<p>Ungültige Anfrage (CSRF-Prüfung).</p>"))
        if self.path == "/password":
            new_password = form.get("new_password", [""])[0]
            confirm_password = form.get("confirm_password", [""])[0]
            if len(new_password) < 12 or len(new_password) > 256 or "\n" in new_password or "\r" in new_password:
                return self.send(400, page("Passwort ändern", '<p>Das Passwort muss 12 bis 256 Zeichen lang sein und darf keinen Zeilenumbruch enthalten.</p><a href="/">Zurück</a>'))
            if not secrets.compare_digest(new_password, confirm_password):
                return self.send(400, page("Passwort ändern", '<p>Die Passwörter stimmen nicht überein.</p><a href="/">Zurück</a>'))
            try:
                result = subprocess.run(
                    ["sudo", "-n", "/usr/local/sbin/pi5-dashboard-action", "set-password"],
                    input=new_password + "\n", text=True, stdout=subprocess.PIPE,
                    stderr=subprocess.STDOUT, timeout=15, check=False
                )
            except Exception as exc:
                return self.send(500, page("Passwort ändern", f"<p>Passwortänderung fehlgeschlagen: {html.escape(str(exc))}</p><a href='/'>Zurück</a>"))
            if result.returncode != 0:
                return self.send(500, page("Passwort ändern", f"<p>{html.escape(result.stdout.strip() or 'Passwortänderung fehlgeschlagen.')}</p><a href='/'>Zurück</a>"))
            DASHBOARD_PASSWORD = new_password
            SESSIONS.clear()
            return self.send(200, page("Passwort geändert", '<p>Das Dashboard-Passwort wurde geändert. Bitte melde dich jetzt mit dem neuen Passwort an.</p><a href="/">Zur Anmeldung</a>'),
                             "pi5session=; HttpOnly; SameSite=Strict; Path=/; Max-Age=0")
        if self.path == "/logout":
            cookie = http.cookies.SimpleCookie(self.headers.get("Cookie", ""))
            sid = cookie.get("pi5session")
            if sid:
                SESSIONS.pop(sid.value, None)
            return self.send(200, page("Abgemeldet", '<p>Du bist abgemeldet. <a href="/">Anmelden</a></p>'),
                             "pi5session=; HttpOnly; SameSite=Strict; Path=/; Max-Age=0")
        action = form.get("action", [""])[0]
        if action not in ("status", "ssd", "maintenance", "backup", "maintenance-enable", "maintenance-disable", "shutdown", "reboot"):
            return self.send(400, page("Fehler", "<p>Unbekannte Aktion.</p>"))
        if action in ("maintenance", "backup") and form.get("confirm", [""])[0] != "yes":
            return self.send(400, page("Bestätigung fehlt", '<p>Aktion wurde nicht gestartet. <a href="/">Zurück</a></p>'))
        if action in ("shutdown", "reboot"):
            output = run_readonly(["sudo", "-n", "/usr/local/sbin/pi5-dashboard-action", action], timeout=10)
        elif action in ("maintenance-enable", "maintenance-disable"):
            output = run_readonly(["sudo", "-n", "/usr/local/sbin/pi5-dashboard-action", action], timeout=30)
        elif action == "status":
            output = run_readonly(["/usr/local/bin/pi-status"])
        elif action == "ssd":
            output = run_readonly(["/usr/local/bin/pi-ssd-prepare"])
        elif action == "maintenance":
            output = run_readonly(["sudo", "-n", "/usr/local/sbin/pi5-dashboard-action", "maintenance"], timeout=1800)
        else:
            target = form.get("target", [""])[0]
            if target not in mounted_targets():
                output = "Abbruch: Ziel ist kein aktuell eingehängter Datenträger unter /mnt oder /media."
            else:
                output = run_readonly(["sudo", "-n", "/usr/local/sbin/pi5-dashboard-action", "backup", target], timeout=7200)
        body = f'<section class="card"><h2>Ergebnis: {html.escape(action)}</h2><pre>{html.escape(output)}</pre><a href="/">Zurück zum Dashboard</a></section>'
        self.send(200, page("Aktionsergebnis", body, sess["csrf"]))

    def log_message(self, fmt, *args):
        print("%s - %s" % (self.address_string(), fmt % args), flush=True)

if __name__ == "__main__":
    if not DASHBOARD_PASSWORD:
        raise SystemExit("Missing dashboard token file")
    server = ThreadingHTTPServer(("0.0.0.0", PORT), Handler)
    server.daemon_threads = True
    print(f"pi5-basics dashboard listening on port {PORT}", flush=True)
    server.serve_forever()
