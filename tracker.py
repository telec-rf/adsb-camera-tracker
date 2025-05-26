# =============================================================================
# Project: ADS-B Tracking and Control System
# Author: Israel Brunini Oliveira
# GitHub: https://github.com/telec-rf
# License: GNU General Public License v3.0
# Version: 0.2
# 
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
# 
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
# GNU General Public License for more details.
# 
# You should have received a copy of the GNU General Public License
# along with this program. If not, see <https://www.gnu.org/licenses/>.
# =============================================================================



import json
import time
import math
import serial
import requests
import threading
import os
import logging
from flask import Flask, jsonify, render_template_string

# =========================
# Settings
# Configure with our precise latitude, longitude and altitude of camera (sea level to the camera)
# =========================
MY_LAT = 0.0
MY_LON = 0.0
MY_ALT = 30  # meters of camera above sea

DIST_MAX_KM = 9 # Target max distance to capture
ALT_MAX = 9000  # Max altitude to tracking in feets

LISTA_DIST_MAX_KM = 50   # Max distance of html overlay
LISTA_ALT_MAX = 30000    # Max altitide of html overlay


ADSB_IP = "192.168.100.2"
ADSB_PORT = 8080


SERIAL_PORT = 'COM3'
# ------ END Settings ------- #


SEND_INTERVAL = 0.8

BAUDRATE = 115200
CAMERA_PAN_MAX = 340.0
CAMERA_TILT_MAX = 90.0

JSON_URL = f"http://{ADSB_IP}:{ADSB_PORT}/aircraft.json"

# =========================
# VARIÁVEIS GLOBAIS
# =========================
status_data = {"az": 0, "el": 0, "dist": 0, "alvo": "N/A"}
voos_proximos = []

# =========================
# FUNÇÕES AUXILIARES
# =========================
logging.getLogger('werkzeug').setLevel(logging.ERROR)

def haversine(lat1, lon1, lat2, lon2):
    R = 6371  # km
    phi1 = math.radians(lat1)
    phi2 = math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlambda = math.radians(lon2 - lon1)
    a = math.sin(dphi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlambda / 2) ** 2
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    return R * c

def calc_az_el(lat, lon, alt):
    dist_km = haversine(MY_LAT, MY_LON, lat, lon)
    dist_m = dist_km * 1000
    delta_alt = alt - MY_ALT
    az = math.degrees(math.atan2(math.radians(lon - MY_LON), math.radians(lat - MY_LAT)))
    az = (az + 360) % 360
    el = math.degrees(math.atan2(delta_alt, dist_m))
    el = max(0.0, min(el, CAMERA_TILT_MAX))
    return az, el, dist_km

def format_command(pan, tilt):
    pan = min(pan, CAMERA_PAN_MAX)
    tilt = min(tilt, CAMERA_TILT_MAX)
    return f"p:{pan:.1f},t:{tilt:.1f}"

def escolher_alvo(dados):
    aeronaves = dados.get("aircraft", [])
    melhores = []
    lista_info = []

    for ac in aeronaves:
        if "lat" in ac and "lon" in ac and "altitude" in ac:
            seen = ac.get("seen_pos", 9999)
            alt = ac.get("altitude", 0)
            lat = ac["lat"]
            lon = ac["lon"]
            dist_km = haversine(MY_LAT, MY_LON, lat, lon)

            # Preenche lista informativa
            if seen < 60 and alt <= LISTA_ALT_MAX and dist_km <= LISTA_DIST_MAX_KM:
                lista_info.append({
                    "flight": ac.get("flight", ac.get("hex")),
                    "dist": round(dist_km, 1),
                    "alt": alt,
                    "seen": seen
                })

            # Preenche candidatos para rastreamento
            if seen < 10 and alt <= ALT_MAX and dist_km <= DIST_MAX_KM:
                melhores.append((dist_km, ac))

    lista_info.sort(key=lambda x: x["dist"])
    global voos_proximos
    voos_proximos = lista_info[:10]

    return melhores[0][1] if melhores else None

# =========================
# FLASK APP
# =========================

app = Flask(__name__)

@app.route("/")
def index():
    return render_template_string("""
    <html>
    <head>
        <meta charset="utf-8">
        <title>Status Ao Vivo</title>
      <style>
    body {
        background: black;
        color: lime;
        font-family: monospace;
        text-shadow: 2px 2px 4px black;
    }

    h1, .big, table, th, td {
        background-color: rgba(0, 0, 0, 0.3); /* Fundo preto com 50% de opacidade */
    }

    h1 {

    text-align: right;
    margin-right: 10px;
        font-size: 2em;
        padding: 10px;
        border-radius: 8px;
        text-shadow: 2px 2px 4px black;
    }

    .big {
        font-size: 3em;
        padding: 10px;
        border-radius: 8px;
        text-shadow: 2px 2px 4px black;
    }

    table {
        border-collapse: collapse;
        width: 100%;
        color: lime;
        margin-top: 20px;
        text-shadow: 1px 1px 3px black;
        border-radius: 8px;
        overflow: hidden;
    }

    th, td {
        border: 1px solid lime;
        padding: 5px;
        text-align: left;
        text-shadow: 1px 1px 3px black;
    }
</style>

    </head>
    <body>
        <h1>IRF Aircraft Tracker</h1>
        <div class="big" id="status">Carregando...</div>

        <h2>Voos próximos:</h2>
        <table>
            <thead>
                <tr><th>Flight ID</th><th>Distance (km)</th><th>Altitude (ft)</th></tr>
            </thead>
            <tbody id="lista">
                <tr><td colspan="4">Carregando...</td></tr>
            </tbody>
        </table>

        <script>
        function atualizar() {
            fetch("/status")
                .then(res => res.json())
                .then(data => {
                    document.getElementById("status").innerText = 
                        `Az: ${data.az}°, El: ${data.el}°, Dist: ${data.dist} km       Tracking: ${data.alvo}`;
                });

            fetch("/alvos")
                .then(res => res.json())
                .then(data => {
                    const tbody = document.getElementById("lista");
                    tbody.innerHTML = "";
                    for (let ac of data) {
                        tbody.innerHTML += `<tr>
                            <td>${ac.flight}</td>
                            <td>${ac.dist}</td>
                            <td>${ac.alt}</td>
                            
                        </tr>`;
                    }
                });
        }
        setInterval(atualizar, 500);
        atualizar();
        </script>
    </body>
    </html>
    """)

@app.route("/status")
def status():
    return jsonify(status_data)

@app.route("/alvos")
def alvos():
    return jsonify(voos_proximos)

# =========================
# LOOP PRINCIPAL EM THREAD
# =========================

def tracking_loop():
    ser = None
    try:
        ser = serial.Serial(SERIAL_PORT, BAUDRATE, timeout=1)
        print(f"[INFO] Conectado à porta {SERIAL_PORT}")
    except Exception as e:
        print(f"[ERRO] Porta serial: {e}")
        return
    time.sleep(10)
    ser.write(('p:200,t:0' + '\n').encode())
    
    time.sleep(5)
    ultima_execucao = 0
    alvo_atual = None

    while True:
        try:
            response = requests.get(JSON_URL)
            print("req eq")
            if response.status_code != 200:
                print(f"[WARN] Erro ao obter JSON: {response.status_code}")
                time.sleep(1)
                continue

            data = response.json()
            aeronaves = data.get("aircraft", [])

            def encontrar_por_hex(hexid):
                for ac in aeronaves:
                    if ac.get("hex") == hexid:
                        return ac
                return None

            valido = False
            if alvo_atual:
                ac = encontrar_por_hex(alvo_atual.get("hex"))
                if ac and "lat" in ac and "lon" in ac and "altitude" in ac:
                    if ac.get("seen_pos", 9999) <= 10 and ac["altitude"] <= ALT_MAX:
                        dist_km = haversine(MY_LAT, MY_LON, ac["lat"], ac["lon"])
                        if dist_km <= DIST_MAX_KM:
                            alvo_atual = ac
                            valido = True

            if not valido:
                alvo_atual = escolher_alvo(data)
                if alvo_atual:
                    with open("track.txt", "w") as f:
                      f.write("1234")  # Substitua "1234" pelo número real do voo
                    print(f"[INFO] Novo alvo: {alvo_atual.get('hex')}")
                else:
                    if os.path.exists("track.txt"):
                        os.remove("track.txt")
                    print("[INFO] Nenhuma aeronave válida.")
                    time.sleep(1)
                    continue

            az, el, dist = calc_az_el(
                alvo_atual["lat"],
                alvo_atual["lon"],
                alvo_atual["altitude"] * 0.3048
            )

            agora = time.time()
            if agora - ultima_execucao >= SEND_INTERVAL:
                cmd = format_command(az, el)
                ser.write((cmd + "\n").encode())
                status_data.update({
                    "az": round(az, 1),
                    "el": round(el, 1),
                    "dist": round(dist, 1),
                    "alvo": alvo_atual.get("flight", alvo_atual.get("hex"))
                })
                print(f"[>>] {cmd} (Dist: {dist:.1f} km) (Alvo: {status_data['alvo']} )")
                ultima_execucao = agora

            time.sleep(0.2)

        except Exception as e:
            print(f"[ERRO] {e}")
            time.sleep(1)

if __name__ == "__main__":
    threading.Thread(target=tracking_loop, daemon=True).start()
    app.run(host="0.0.0.0", port=5000)
