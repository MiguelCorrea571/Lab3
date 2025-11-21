import socket
import threading
import tkinter as tk
import json
from tkinter import messagebox

AVAILABLE_COLORS = [
    "#FF0059", "#00C8FF", "#5DFF00", "#FFB300",
    "#9D00FF", "#FF6A00", "#00FFB2", "#FFD7F0",
    "#A3FF00", "#0095FF"
]

player_colors = {}


from tkinter import simpledialog

SERVER_PORT = 5000

SERVER_HOST = simpledialog.askstring(
    "Conectar al servidor",
    "Ingresa la IP del servidor:\n\n"
    "- Usa 'localhost' si juegas solo\n"
    "- Usa IP LAN si están en la misma red (ej: 192.168.x.x)\n"
    "- Usa IP pública para jugar online"
)

client = socket.socket()
client.connect((SERVER_HOST, SERVER_PORT))


player_id = None
room_id = None
state = {"players": {}, "projectiles": []}
last_dir = "up"
username = ""

# ---------------- COLORES ÚNICOS ----------------


# ---------------- TKINTER ROOT ----------------
root = tk.Tk()
root.title("Grid Battle Arena")
root.geometry("500x500")

BTN_STYLE = {"font": ("Arial", 14), "width": 15, "bg": "#333", "fg": "white"}
TITLE_STYLE = {"font": ("Arial", 22), "fg": "white", "bg": "black"}

frame_name = tk.Frame(root, bg="black")
frame_menu = tk.Frame(root, bg="black")
frame_join = tk.Frame(root, bg="black")
frame_wait = tk.Frame(root, bg="black")
frame_game = tk.Frame(root, bg="black")


def show(frame):
    for f in (frame_name, frame_menu, frame_join, frame_wait, frame_game):
        f.pack_forget()
    frame.pack(fill="both", expand=True)


# ---------------- NAME INPUT ----------------
tk.Label(frame_name, text="Ingresa tu nombre:", **TITLE_STYLE).pack(pady=20)

name_entry = tk.Entry(frame_name, font=("Arial", 18))
name_entry.pack(pady=20)


def confirm_name():
    global username
    username = name_entry.get().strip()
    if username == "":
        return
    show(frame_menu)


tk.Button(frame_name, text="Confirmar", command=confirm_name, **BTN_STYLE).pack(pady=30)


# ---------------- MENU ----------------
tk.Label(frame_menu, text="GRID BATTLE ARENA", **TITLE_STYLE).pack(pady=40)


def send_create():
    client.send(json.dumps({"name": username, "action": "create"}).encode())
    show(frame_wait)
    lbl_wait.config(text="Creando sala...")


def send_join():
    rid = entry_room.get().strip()
    if rid:
        client.send(json.dumps({"name": username, "action": "join", "room": rid}).encode())
        lbl_join_status.config(text="Conectando...")


tk.Button(frame_menu, text="Crear Sala", command=send_create, **BTN_STYLE).pack(pady=10)
tk.Button(frame_menu, text="Unirse a Sala", command=lambda: show(frame_join), **BTN_STYLE).pack(pady=10)
tk.Button(frame_menu, text="Salir", command=root.destroy, **BTN_STYLE).pack(pady=10)


# ---------------- JOIN FRAME ----------------
tk.Label(frame_join, text="Código de Sala:", **TITLE_STYLE).pack(pady=30)

entry_room = tk.Entry(frame_join, font=("Arial", 18))
entry_room.pack(pady=20)

lbl_join_status = tk.Label(frame_join, text="", fg="white", bg="black")
lbl_join_status.pack()

tk.Button(frame_join, text="Unirse", command=send_join, **BTN_STYLE).pack(pady=10)
tk.Button(frame_join, text="Volver", command=lambda: show(frame_menu), **BTN_STYLE).pack(pady=10)


# ---------------- WAITING FRAME ----------------
lbl_wait = tk.Label(frame_wait, text="", **TITLE_STYLE)
lbl_wait.pack(pady=40)

def leave_room():
    global room_id, state

    try:
        # avisar al server
        client.send(json.dumps({"action": "leave"}).encode())
    except:
        pass

    try:
        client.shutdown(socket.SHUT_RDWR)
    except:
        pass

    try:
        client.close()
    except:
        pass

    # crear un nuevo socket para evitar reconectar con el viejo
    rebuild_connection()

    room_id = None
    state = {"players": {}, "projectiles": []}

    show(frame_menu)
    
def rebuild_connection():
    global client
    client = socket.socket()
    client.connect((SERVER_HOST, SERVER_PORT))
    threading.Thread(target=listen, daemon=True).start()




# ---------------- GAME FRAME ----------------
lbl_room = tk.Label(frame_game, font=("Arial", 14), fg="white", bg="black")
lbl_room.pack()
btn_back = tk.Button(frame_game, text="Volver al menú", command=leave_room, **BTN_STYLE)
btn_back.pack(pady=5)

canvas = tk.Canvas(frame_game, width=420, height=420, bg="black")
canvas.pack()


# ---------------- DRAW FUNCTION ----------------
def draw():
    canvas.delete("all")

    for pid, p in state["players"].items():
        # color único del jugador
        color = player_colors.get(pid, "white")

        x, y = p["x"] * 20, p["y"] * 20

        # player
        canvas.create_rectangle(x, y, x + 20, y + 20, fill=color)
        canvas.create_text(x + 10, y - 10, text=f"{pid}", fill="white", font=("Arial", 8))

        # HP bar
        hp = p["hp"]
        bar_width = int(20 * (hp / 100))
        canvas.create_rectangle(x, y + 22, x + 20, y + 28, fill="darkred")
        canvas.create_rectangle(x, y + 22, x + bar_width, y + 28, fill="lime")
        canvas.create_text(x + 10, y + 35, text=f"{hp} HP", fill="yellow", font=("Arial", 7))

    # proyectiles
    for proj in state["projectiles"]:
        x, y = proj["x"] * 20, proj["y"] * 20
        canvas.create_oval(x, y, x + 20, y + 20, fill="red")


# ---------------- KEY INPUT ----------------
def on_key(event):
    global last_dir

    if event.keysym in ("Up", "Down", "Left", "Right"):
        last_dir = event.keysym.lower()
        client.send(json.dumps({"type": "move", "dir": last_dir}).encode())

    elif event.keysym == "space":
        client.send(json.dumps({"type": "shoot", "dir": last_dir}).encode())


# ---------------- LISTEN THREAD ----------------
def listen():
    global player_id, room_id, state

    while True:
        try:
            data = client.recv(4096)
            if not data:
                break  # socket cerrado → salir del hilo
            msg = json.loads(data.decode())
        except:
            break  # socket inválido → salir del hilo

        # ---- resto de tu código sin tocar ----
        if msg["type"] == "assign_id":
            player_id = msg["id"]
        
        elif msg["type"] == "room_created":
            room_id = msg["room"]
            lbl_wait.config(text=f"Sala creada: {room_id}\nEsperando jugador...")

        elif msg["type"] == "joined":
            room_id = msg["room"]
            lbl_wait.config(text=f"Unido a sala: {room_id}\nEsperando jugador...")
        
        elif msg["type"] == "state":
            state = msg
            if not frame_game.winfo_ismapped():
                lbl_room.config(text=f"Sala {room_id} | Tú: {player_id}")
                show(frame_game)
                root.bind("<Key>", on_key)
            draw()
        elif msg["type"] == "winner":
            if msg["id"] == player_id:
                messagebox.showinfo("Victoria", "¡Ganaste la partida!")
            else:
                messagebox.showinfo("Derrota", f"{msg['id']} ganó la partida.")

        


threading.Thread(target=listen, daemon=True).start()

show(frame_name)
root.mainloop()
