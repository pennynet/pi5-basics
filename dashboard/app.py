#!/usr/bin/env python3
"""Small, authenticated LAN dashboard for pi5-basics. Standard library only."""
import html
import http.cookies
import ipaddress
import os
import secrets
import socket
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
    """Return useful interface/IP information even when the ip command is unavailable."""
    output = run_readonly(["ip", "-brief", "address"], 5)
    if output and not output.startswith("Fehler:") and output.strip():
        lines = [line for line in output.splitlines() if not line.lstrip().startswith("lo ")]
        if lines:
            return "\\n".join(lines)
    fallback = run_readonly(["hostname", "-I"], 5).strip()
    if fallback and not fallback.startswith("Fehler:"):
        return "IP-Adresse(n): " + fallback
    return "Keine Netzwerkadresse ermittelbar (iproute2/Netzwerkverbindung prüfen)."

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

def page(title, body, csrf=""):
    return """<!doctype html><html lang="de"><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>pi5-basics · """ + html.escape(title) + """</title>
<style>
:root{color-scheme:dark;--bg:#101820;--panel:#1b2935;--line:#304353;--txt:#edf4f8;--muted:#a9bac7;--accent:#79c0ff}
*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--txt);font:16px system-ui,sans-serif}
header,main{max-width:1050px;margin:auto;padding:20px}header{display:flex;justify-content:space-between;align-items:center;border-bottom:1px solid var(--line)}
h1{font-size:1.3rem;margin:0}h2{font-size:1.1rem;margin-top:0}.muted{color:var(--muted);font-size:.9rem}
.grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(190px,1fr));gap:12px}
.card{background:var(--panel);border:1px solid var(--line);border-radius:14px;padding:16px;margin-bottom:14px}
.value{font-size:1.2rem;font-weight:650;overflow-wrap:anywhere}.actions{display:grid;grid-template-columns:repeat(auto-fit,minmax(220px,1fr));gap:12px}
button,.button,select,input{font:inherit;border-radius:9px;padding:11px 14px;border:1px solid var(--line);background:#263b4c;color:var(--txt)}
button{cursor:pointer;background:#174d76;border-color:#347eb3}button:hover{background:#206493}
input[type=password]{width:100%;margin:10px 0}select{width:100%;margin:8px 0}
pre{white-space:pre-wrap;overflow-wrap:anywhere;background:#0b1218;padding:14px;border-radius:10px;max-height:420px;overflow:auto}
form{margin:0}label{display:block;margin:8px 0}.danger{background:#54302c;border-color:#9b554b}
a{color:var(--accent)}footer{max-width:1050px;margin:auto;padding:10px 20px 30px;color:var(--muted);font-size:.85rem}
</style>
<header><h1>🍓 pi5-basics · """ + html.escape(title) + """</h1><span class="muted">Raspberry Pi 5</span></header>
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
        self.send_header("Content-Security-Policy", "default-src 'self'; style-src 'unsafe-inline'; form-action 'self'; frame-ancestors 'none'")
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
        targets = mounted_targets()
        target_options = "".join(f'<option value="{html.escape(p, quote=True)}">{html.escape(p)}</option>' for p in targets)
        backup_form = (f'<form method="post" action="/action"><input type="hidden" name="csrf" value="{csrf}"><input type="hidden" name="action" value="backup"><label>Gemountetes Backup-Ziel</label><select name="target" required>{target_options}</select><label><input type="checkbox" name="confirm" value="yes" required> Ich bestätige, dass das ausgewählte Laufwerk mein Backup-Ziel ist.</label><button {"disabled" if not targets else ""}>Backup starten</button></form>' if targets else '<p class="muted">Kein eigenes Laufwerk unter /mnt oder /media eingehängt. Backup ist deshalb deaktiviert.</p>')
        body = f"""
<div class="grid">
<div class="card"><div class="muted">Temperatur</div><div class="value">{html.escape(temp)}</div></div>
<div class="card"><div class="muted">RAM belegt / gesamt</div><div class="value">{html.escape(ram)}</div></div>
<div class="card"><div class="muted">Laufzeit</div><div class="value">{html.escape(uptime)}</div></div>
<div class="card"><div class="muted">System</div><div class="value">{html.escape(os_name)}</div></div>
<div class="card"><div class="muted">Netzwerk / IP</div><div class="value" style="font-size:1rem;white-space:pre-line">{html.escape(network)}</div></div>
</div>
<div class="card"><h2>Gerät</h2><div class="value">{html.escape(model)}</div><p class="muted">Aktualisiert beim Neuladen der Seite.</p><a href="/">Status aktualisieren</a></div>
<div class="actions">
<section class="card"><h2>Backup</h2><p class="muted">Datei-Backup von /etc, /home, /root und /boot/firmware auf ein separates, eingehängtes Laufwerk.</p>{backup_form}</section>
<section class="card"><h2>Maintenance</h2><p class="muted">Paketlisten und Pakete aktualisieren, verwaiste Pakete entfernen und Journal aufräumen.</p><form method="post" action="/action"><input type="hidden" name="csrf" value="{csrf}"><input type="hidden" name="action" value="maintenance"><label><input type="checkbox" name="confirm" value="yes" required> Ich möchte die Systemwartung jetzt ausführen.</label><button class="danger">Wartung starten</button></form></section>
<section class="card"><h2>SSD Prepare</h2><p class="muted">Rein lesende Bestandsaufnahme von Datenträgern, NVMe und Bootloader.</p><form method="post" action="/action"><input type="hidden" name="csrf" value="{csrf}"><input type="hidden" name="action" value="ssd"><button>SSD-Status anzeigen</button></form></section>
<section class="card"><h2>Systemdetails</h2><p class="muted">Ausgabe der vorhandenen pi-status-Funktion.</p><form method="post" action="/action"><input type="hidden" name="csrf" value="{csrf}"><input type="hidden" name="action" value="status"><button>Statusdetails anzeigen</button></form></section>
</div>
<form method="post" action="/logout"><input type="hidden" name="csrf" value="{csrf}"><button class="danger">Abmelden</button></form>"""
        self.send(200, page("Dashboard", body))

    def do_POST(self):
        if not self.private_client():
            return self.send(403, "Zugriff verweigert.")
        form = self.read_form()
        if self.path == "/login":
            supplied = form.get("password", [""])[0]
            if secrets.compare_digest(supplied, DASHBOARD_PASSWORD):
                sid = secrets.token_urlsafe(32)
                SESSIONS[sid] = {"csrf": secrets.token_urlsafe(24)}
                return self.send(200, page("Dashboard", '<p>Anmeldung erfolgreich. <a href="/">Dashboard öffnen</a></p>'),
                                 f"pi5session={sid}; HttpOnly; SameSite=Strict; Path=/; Max-Age=28800")
            time.sleep(1)
            return self.send(401, page("Anmeldung", '<p>Anmeldung fehlgeschlagen.</p><a href="/">Erneut versuchen</a>'))
        sess = self.session()
        if not sess:
            return self.send(401, page("Anmeldung", '<p>Bitte erneut anmelden. <a href="/">Anmelden</a></p>'))
        if not secrets.compare_digest(form.get("csrf", [""])[0], sess["csrf"]):
            return self.send(403, page("Fehler", "<p>Ungültige Anfrage (CSRF-Prüfung).</p>"))
        if self.path == "/logout":
            cookie = http.cookies.SimpleCookie(self.headers.get("Cookie", ""))
            sid = cookie.get("pi5session")
            if sid:
                SESSIONS.pop(sid.value, None)
            return self.send(200, page("Abgemeldet", '<p>Du bist abgemeldet. <a href="/">Anmelden</a></p>'),
                             "pi5session=; HttpOnly; SameSite=Strict; Path=/; Max-Age=0")
        action = form.get("action", [""])[0]
        if action not in ("status", "ssd", "maintenance", "backup"):
            return self.send(400, page("Fehler", "<p>Unbekannte Aktion.</p>"))
        if action in ("maintenance", "backup") and form.get("confirm", [""])[0] != "yes":
            return self.send(400, page("Bestätigung fehlt", '<p>Aktion wurde nicht gestartet. <a href="/">Zurück</a></p>'))
        if action == "status":
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
