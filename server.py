import socket
import threading
import json
import time
import random

SERVER_HOST = "0.0.0.0"
SERVER_PORT = 5000

rooms = {}
conn_to_room = {}
conn_to_pid = {}
lock = threading.Lock()


def safe_send(conn, data):
    try:
        conn.send(json.dumps(data).encode())
    except:
        pass


def broadcast(room_id, data):
    msg = json.dumps(data).encode()
    for c in rooms[room_id]["clients"]:
        try:
            c.send(msg)
        except:
            pass


def room_loop(room_id):
    while True:
        time.sleep(0.1)

        with lock:
            if room_id not in rooms:
                break

            room = rooms[room_id]
            players = room["players"]
            projectiles = room["projectiles"]

            # Mover proyectiles
            for proj in list(projectiles):
                if proj["dir"] == "up":
                    proj["y"] -= 1
                elif proj["dir"] == "down":
                    proj["y"] += 1
                elif proj["dir"] == "left":
                    proj["x"] -= 1
                elif proj["dir"] == "right":
                    proj["x"] += 1

                # Colisión con jugadores
                for pid, p in list(players.items()):
                    if proj["owner"] != pid and (p["x"], p["y"]) == (proj["x"], proj["y"]):
                        p["hp"] -= 25
                        projectiles.remove(proj)

                        if p["hp"] <= 0:
                            del players[pid]
                            broadcast(room_id, {"type": "eliminated", "id": pid})
                        break

                # Eliminar proyectiles fuera del mapa
                if proj in projectiles and not (0 <= proj["x"] <= 20 and 0 <= proj["y"] <= 20):
                    projectiles.remove(proj)

            # Iniciar juego cuando haya 2 jugadores
            if len(players) >= 2 and not room["started"]:
                room["started"] = True
                broadcast(room_id, {"type": "status", "msg": "⚔ Juego iniciado!"})

            # Ganador
            if room["started"] and len(players) == 1:
                winner = list(players.keys())[0]
                broadcast(room_id, {"type": "winner", "id": winner})
                break

            # Actualizar estado
            broadcast(room_id, {"type": "state", "players": players, "projectiles": projectiles})

def get_random_position(players, max_x=20, max_y=20):
    """Devuelve coordenadas (x,y) libres evitando superposición con jugadores existentes."""
    while True:
        x = random.randint(0, max_x)
        y = random.randint(0, max_y)
        if all((x, y) != (p["x"], p["y"]) for p in players.values()):
            return x, y

def handle_client(conn, addr):
    username = None

    try:
        first_msg = json.loads(conn.recv(1024).decode())
        username = first_msg["name"]

        # Validar nombre repetido
        for r in rooms.values():
            if username in r["players"]:
                safe_send(conn, {"type": "error", "msg": "Nombre en uso. Usa otro."})
                conn.close()
                return

        conn_to_pid[conn] = username

        # Crear sala
        if first_msg["action"] == "create":
            room_id = str(random.randint(1000, 9999))
            while room_id in rooms:
                room_id = str(random.randint(1000, 9999))

            # Definir "walls" (líneas blancas con colisión).
# Aquí se crean líneas verticales y horizontales en x/y = 5,10,15 (ajústalo si tus líneas están en otras posiciones)
            walls = set()
            line_positions = [-5, 25, -5, 25]
            for x in line_positions:
                for y in range(0, 21):
                    walls.add((x, y))
            for y in line_positions:
                for x in range(0, 21):
                    walls.add((x, y))

            # Crear sala vacía primero
            rooms[room_id] = {
                "clients": [conn],
                "players": {},  # vacío por ahora
                "projectiles": [],
                "started": False,
                "walls": walls
            }

            # Asignar posición aleatoria al creador
            x, y = get_random_position(rooms[room_id]["players"])
            rooms[room_id]["players"][username] = {"x": x, "y": y, "hp": 100}



            conn_to_room[conn] = room_id
            safe_send(conn, {"type": "assign_id", "id": username})
            safe_send(conn, {"type": "room_created", "room": room_id})

            threading.Thread(target=room_loop, args=(room_id,), daemon=True).start()

        # Unirse a sala existente
        elif first_msg["action"] == "join":
            room_id = first_msg["room"]
            if room_id not in rooms:
                safe_send(conn, {"type": "error", "msg": "Sala no existe"})
                conn.close()
                return

            rooms[room_id]["clients"].append(conn)
            x, y = get_random_position(rooms[room_id]["players"])
            rooms[room_id]["players"][username] = {"x": x, "y": y, "hp": 100}
            conn_to_room[conn] = room_id

            safe_send(conn, {"type": "assign_id", "id": username})
            safe_send(conn, {"type": "joined", "room": room_id})

        # Escuchar mensajes del cliente
        while True:
            raw = conn.recv(1024).decode().strip()
            if not raw:
                break

            msg = json.loads(raw)
            room_id = conn_to_room[conn]

            players = rooms[room_id]["players"]
            projectiles = rooms[room_id]["projectiles"]

            if msg["type"] == "move":
                # Coord actual
                cur_x = players[username]["x"]
                cur_y = players[username]["y"]
                # Calcular destino según dirección
                nx, ny = cur_x, cur_y
                if msg["dir"] == "up":
                    ny = cur_y - 1
                elif msg["dir"] == "down":
                    ny = cur_y + 1
                elif msg["dir"] == "left":
                    nx = cur_x - 1
                elif msg["dir"] == "right":
                    nx = cur_x + 1

                # Validar límites del mapa
                if not (0 <= nx <= 20 and 0 <= ny <= 20):
                    # fuera de límites: ignorar movimiento
                    pass
                else:
                    # Validar colisión con paredes de la sala (si existen)
                    room_walls = rooms[room_id].get("walls", set())
                    if (nx, ny) in room_walls:
                        # Hay una pared: bloquear movimiento (no hacer nada)
                        pass
                    else:
                        # Evitar pisar a otro jugador
                        occupied = any(
                            (nx, ny) == (p["x"], p["y"])
                            for pid, p in players.items()
                            if pid != username
                        )

                        if occupied:
                            # Ya hay un jugador allí → bloquear movimiento
                            pass
                        else:
                            # Movimiento válido
                            players[username]["x"] = nx
                            players[username]["y"] = ny



            elif msg["type"] == "shoot":
                x, y = players[username]["x"], players[username]["y"]
                projectiles.append({"x": x, "y": y, "dir": msg["dir"], "owner": username})

    except:
        pass
    finally:
        with lock:
            # Obtener datos del jugador antes de borrar la conexión
            pid = conn_to_pid.get(conn)
            room_id = conn_to_room.get(conn)

            # Eliminar referencias de conexión
            if conn in conn_to_pid:
                del conn_to_pid[conn]

            if conn in conn_to_room:
                del conn_to_room[conn]

            # Si estaba en una sala, eliminarlo
            if room_id in rooms and pid in rooms[room_id]["players"]:
                try:
                    del rooms[room_id]["players"][pid]
                except:
                    pass

                # Avisar a los demás que salió
                broadcast(room_id, {"type": "eliminated", "id": pid})

                # Si la sala queda vacía, eliminarla COMPLETAMENTE
                if len(rooms[room_id]["players"]) == 0:
                    del rooms[room_id]

        conn.close()



def start():
    server = socket.socket()
    server.bind((SERVER_HOST, SERVER_PORT))
    server.listen()

    print(f"SERVER RUNNING on {SERVER_HOST}:{SERVER_PORT}")

    while True:
        conn, addr = server.accept()
        threading.Thread(target=handle_client, args=(conn, addr), daemon=True).start()

import socket, requests

def show_ips():
    try:
        public_ip = requests.get("https://api.ipify.org").text
    except:
        public_ip = "No disponible (sin internet o bloqueado)"

    lan_ip = socket.gethostbyname(socket.gethostname())

    print("\n🔌 SERVIDOR LISTO")
    print(f"➡ IP LOCAL (LAN): {lan_ip}")
    print(f"🌍 IP PÚBLICA (ONLINE): {public_ip}")
    print(f"📌 Usa el puerto: {SERVER_PORT}")
    print("-" * 40)

show_ips()

start()
