import customtkinter as ctk
import os
from PIL import Image, ImageTk
import pygame
import dalgona.squid_game.game as dalgona_game
import rlgl.game as rlgl_game
import sys
from dalgona.track_module import trackmodule as tm
import ctypes
import ctypes.wintypes
import cv2
import gc
import time

user32 = ctypes.windll.user32

SW_MINIMIZE = 6
SW_RESTORE = 9
SW_MAXIMIZE = 3

class POINT(ctypes.Structure):
    _fields_ = [("x", ctypes.c_long), ("y", ctypes.c_long)]

class RECT(ctypes.Structure):
    _fields_ = [("left", ctypes.c_long), ("top", ctypes.c_long),
                ("right", ctypes.c_long), ("bottom", ctypes.c_long)]

class WINDOWPLACEMENT(ctypes.Structure):
    _fields_ = [
        ("length", ctypes.c_uint),
        ("flags", ctypes.c_uint),
        ("showCmd", ctypes.c_uint),
        ("ptMinPosition", POINT),
        ("ptMaxPosition", POINT),
        ("rcNormalPosition", RECT),
    ]

def get_window_state(hwnd):
    wp = WINDOWPLACEMENT()
    wp.length = ctypes.sizeof(WINDOWPLACEMENT)
    user32.GetWindowPlacement(hwnd, ctypes.byref(wp))
    return wp.showCmd

def set_window_state_by_title(title, state):
    hwnd = user32.FindWindowW(None, title)
    if hwnd:
        if state == 2:  # minimized
            user32.ShowWindow(hwnd, SW_MINIMIZE)
        elif state == 3:  # maximized
            user32.ShowWindow(hwnd, SW_MAXIMIZE)
        else:
            user32.ShowWindow(hwnd, SW_RESTORE)

# ===============================
# THEME
# ===============================
ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("blue")

# ===============================
# PATHS
# ===============================
BASE = os.path.dirname(os.path.abspath(__file__))
ASSETS = os.path.join(BASE, "assets")
SOUNDS = os.path.join(BASE, "sounds")
FRAMES = os.path.join(BASE, "frames")
SOUNDS = os.path.join(BASE, "sounds")
sys.path.append(os.path.join(BASE, "dalgona", "squid_game"))

# ===============================
# APP WINDOW
# ===============================
app = ctk.CTk()
app.title("Squid Game – Red Light Green Light")
screen_w = app.winfo_screenwidth()
screen_h = app.winfo_screenheight()
# Position and size the window to the screen and prefer a maximized state
app.geometry(f"{screen_w}x{screen_h}+0+0")
try:
    app.state('zoomed')
except Exception:
    # Fallback to fullscreen if zoomed isn't supported
    app.attributes('-fullscreen', True)
# Toggle maximize/fullscreen with Escape
app.bind("<Escape>", lambda event: app.state('normal') if app.state() == 'zoomed' else app.state('zoomed'))

# ===============================
# LOAD ASSETS
# ===============================
menu_bg_src = Image.open(os.path.join(ASSETS, "menuPic.png"))
# Scale the background to cover the whole window while preserving aspect ratio
orig_w, orig_h = menu_bg_src.size
scale = max(screen_w / orig_w, screen_h / orig_h) * 1.05  # slight oversize to avoid gaps
new_w = int(orig_w * scale)
new_h = int(orig_h * scale)
menu_bg_img = menu_bg_src.resize((new_w, new_h), Image.LANCZOS)
menu_bg = ImageTk.PhotoImage(menu_bg_img)

# ===============================
# SOUND
# ===============================
pygame.mixer.init()

def play_music(path, loop=True):
    pygame.mixer.music.load(path)
    pygame.mixer.music.play(-1 if loop else 0)

def stop_music():
    pygame.mixer.music.stop()

def play_sound(path):
    sound = pygame.mixer.Sound(path)
    sound.play()
    return sound

def play_result_music_after(sound, music_path):
    def check():
        if pygame.mixer.get_busy():   # sound still playing
            app.after(100, check)
        else:
            play_music(music_path, loop=True)

    check()

# ===============================
# SCREENS
# ===============================
menu = ctk.CTkFrame(app)
instruction = ctk.CTkFrame(app)
start_screen = ctk.CTkFrame(app)
game = ctk.CTkFrame(app)
result = ctk.CTkFrame(app)
dalgona = ctk.CTkFrame(app)

for f in (menu, instruction, start_screen, game, result, dalgona):
    f.place(relx=0, rely=0, relwidth=1, relheight=1)

def show(frame):
    frame.tkraise()

# ===============================
# MENU SCREEN
# ===============================
bg_label = ctk.CTkLabel(menu, image=menu_bg, text="", width=new_w, height=new_h)
# Center the (possibly oversized) background image in the window
bg_label.place(relx=0.5, rely=0.5, anchor='center')
bg_label.image = menu_bg

menu_box = ctk.CTkFrame(menu, fg_color="transparent")
menu_box.place(relx=0.28, rely=0.65, anchor="center")

def start_rlgl():
    rlgl_game.run_rlgl(app, go_menu, BASE, show)

def start_dalgona():
    # Aggressive cleanup before starting
    cv2.destroyAllWindows()
    for _ in range(3):
        cv2.waitKey(500)

    gc.collect()
    gc.collect()  # Double garbage collection
    time.sleep(0.5)

    stop_music()
    show(start_screen)
    pygame.mixer.music.load(os.path.join(SOUNDS, "start.mp3"))
    pygame.mixer.music.play()
    check_dalgona_start_music()

def go_menu():
    stop_music()
    play_music(os.path.join(SOUNDS, "menu.mp3"))
    show(menu)

ctk.CTkButton(
    menu_box, text="▶ RLGL", width=200, height=46,
    font=ctk.CTkFont(size=18, weight="bold"),
    fg_color="#C60660", hover_color="#A90552",
    command=start_rlgl
).pack()

ctk.CTkButton(
    menu_box, text="🍪 Dalgona", width=200, height=46,
    font=ctk.CTkFont(size=18),
    fg_color="#F4A261", hover_color="#E76F51",
    command=start_dalgona
).pack(pady=(10, 0))

ctk.CTkButton(
    menu_box, text="⭕ GUIDE", width=200, height=46,
    font=ctk.CTkFont(size=18),
    fg_color="#059696", hover_color="#046b6b",
    command=lambda: show(instruction)
).pack(pady=10)

ctk.CTkButton(
    menu_box, text="🟥 QUIT", width=200, height=46,
    font=ctk.CTkFont(size=18),
    command=app.destroy
).pack()

# ===============================
# INSTRUCTION SCREEN
# ===============================

# Main container
guide_container = ctk.CTkFrame(instruction, fg_color="transparent")
guide_container.pack(pady=40, padx=40, fill="both", expand=True)

# Create 2 columns
guide_container.grid_columnconfigure(0, weight=1)
guide_container.grid_columnconfigure(1, weight=1)

# ===============================
# LEFT SIDE — RLGL
# ===============================

rlgl_frame = ctk.CTkFrame(guide_container, corner_radius=15)
rlgl_frame.grid(row=0, column=0, padx=20, sticky="nsew")

ctk.CTkLabel(
    rlgl_frame,
    text="🚦 RED LIGHT GREEN LIGHT",
    font=ctk.CTkFont(size=20, weight="bold")
).pack(pady=10)

# RLGL Image
rlgl_img = ctk.CTkImage(
    light_image=Image.open("assets/RLGL.jpg"),
    size=(300, 180)
)

ctk.CTkLabel(rlgl_frame, image=rlgl_img, text="").pack(pady=10)

# RLGL Instructions
ctk.CTkLabel(
    rlgl_frame,
    text="1.  GREEN LIGHT: Move using hand gestures.\n"
    "   • ✌️ Peace Sign: Walk\n"
    "   • 👍 Thumbs Up: Jump over obstacles\n"
    "   • ✌️+👍 Both Hands: Forward Power Jump\n\n"
    "2.  RED LIGHT: Stop all movement immediately!\n"
    "3.  OBSTACLES: These will block your path. \n"
    "   You must JUMP to clear them; walking into them \n"
    "   will stop your progress.\n"
    "4.  GOAL: Reach the finish line before the 16s timer ends.",
    font=ctk.CTkFont(size=18),
    justify="left"
).pack(pady=10)

# ===============================
# RIGHT SIDE — DALGONA
# ===============================

dalgona_frame = ctk.CTkFrame(guide_container, corner_radius=15)
dalgona_frame.grid(row=0, column=1, padx=20, sticky="nsew")

ctk.CTkLabel(
    dalgona_frame,
    text="🍪 DALGONA GAME",
    font=ctk.CTkFont(size=20, weight="bold")
).pack(pady=10)

# Dalgona Image
dalgona_img = ctk.CTkImage(
    light_image=Image.open("assets/Dalgona.jpg"),
    size=(300, 180)
)

ctk.CTkLabel(dalgona_frame, image=dalgona_img, text="").pack(pady=10)

# Dalgona Instructions
# Dalgona Instructions
ctk.CTkLabel(
    dalgona_frame,
    text="1. Place your finger on the RED START circle.\n"
         "2. When the game starts, slowly trace along the shape.\n"
         "3. Cut the CYAN dashed lines by touching them.\n"  # The dashes to cut
         "4. Stay within the YELLOW border while tracing.\n"  # The path to follow
         "5. Return near the starting point after tracing enough\n"
         "   of the shape.",
    font=ctk.CTkFont(size=18),
    justify="left"
).pack(pady=10)
# ===============================
# BACK BUTTON
# ===============================

ctk.CTkButton(
    instruction,
    text="⬅ GO BACK TO MENU",
    width=220,
    height=50,
    command=lambda: show(menu)
).pack(pady=(10, 30))

# ===============================
# Dalgona
# ===============================

# ===============================
# CONTINUE GAME
# ===============================
def continue_game():
    stop_music()
    show(game)

    # Force UI refresh
    app.update_idletasks()

# ===============================
# RESULT SCREEN
# ===============================

kill_bg = ImageTk.PhotoImage(
    Image.open(os.path.join(ASSETS, "kill.png"))
         .resize((screen_w, screen_h), Image.LANCZOS)
)

win_bg = ImageTk.PhotoImage(
    Image.open(os.path.join(ASSETS, "winner.png"))
         .resize((screen_w, screen_h), Image.LANCZOS)
)

result_label = ctk.CTkLabel(
    result, text="", font=ctk.CTkFont(size=30, weight="bold")
)
result_label.pack(pady=30)

result_bg = ctk.CTkLabel(result, text="")
result_bg.place(relx=0, rely=0, relwidth=1, relheight=1)

result_label.lift()
#result_image.lift()   # if you keep it

#result_image = ctk.CTkLabel(result, text="")
#result_image.pack(pady=50)

result_btn_box = ctk.CTkFrame(
    result,
    fg_color="transparent"
)
result_btn_box.place(relx=0.5, rely=0.73, anchor="center")

# Keep references so we can swap behavior for RLGL vs Dalgona
btn_menu = ctk.CTkButton(
    result_btn_box, text="⬅ GO TO MENU", width=180, height=46,
    font=ctk.CTkFont(size=18),
    fg_color="#C60660", hover_color="#A90552",
    command=lambda: go_menu()
)
btn_menu.pack(side="left")

def continue_from_result():
    global current_result_mode
    if current_result_mode == "dalgona":
        print("Starting new Dalgona game...")

        # CRITICAL: Aggressive cleanup before starting
        cv2.destroyAllWindows()
        for _ in range(3):
            cv2.waitKey(500)

        gc.collect()
        gc.collect()  # Double garbage collection
        time.sleep(1.0)  # Give system time to clean up

        # Start new game
        app.after(100, lambda: start_dalgona())
    else:
        continue_game()

btn_continue = ctk.CTkButton(
    result_btn_box, text="🔁 CONTINUE", width=180, height=46,
    font=ctk.CTkFont(size=18),
    fg_color="#059696", hover_color="#046b6b",
    command=continue_from_result
)
btn_continue.pack(side="left", padx=10)

btn_quit = ctk.CTkButton(
    result_btn_box, text="❌ QUIT", width=180, height=46,
    font=ctk.CTkFont(size=18),
    fg_color="red",
    command=app.destroy
)
btn_quit.pack(side="left")

def show_dalgona_result(dalgona_win: bool):
    """Reuse the same RESULT screen UI for Dalgona."""
    global current_result_mode
    current_result_mode = "dalgona"

    stop_music()
    show(result)

    if dalgona_win:
        sfx = play_sound(os.path.join(SOUNDS, "win.mp3"))
        play_result_music_after(sfx, os.path.join(SOUNDS, "menu.mp3"))
        result_label.configure(text="🐙 YOU WIN!", text_color="green")
        result_bg.configure(image=win_bg)
        result_bg.image = win_bg
    else:
        sfx = play_sound(os.path.join(SOUNDS, "kill.mp3"))
        play_result_music_after(sfx, os.path.join(SOUNDS, "menu.mp3"))
        # You asked for PLAYER 456 on Dalgona lose
        result_label.configure(text="💀 ELIMINATED", text_color="red")
        result_bg.configure(image=kill_bg)
        result_bg.image = kill_bg

def go_menu():
    stop_music()
    play_music(os.path.join(SOUNDS, "menu.mp3"))
    show(menu)

def check_dalgona_start_music():
    if pygame.mixer.music.get_busy():
        app.after(100, check_dalgona_start_music)
    else:
        launch_dalgona()

def set_hwnd_state(hwnd: int, show_cmd: int):
    if not hwnd:
        return
    if show_cmd == 2:      # minimized
        user32.ShowWindow(hwnd, 6)   # SW_MINIMIZE
    elif show_cmd == 3:    # maximized
        user32.ShowWindow(hwnd, 3)   # SW_MAXIMIZE
    else:                  # normal
        user32.ShowWindow(hwnd, 9)   # SW_RESTORE

def launch_dalgona():
    # CRITICAL: Aggressive cleanup before starting
    cv2.destroyAllWindows()
    for _ in range(3):
        cv2.waitKey(500)

    gc.collect()
    gc.collect()  # Double garbage collection
    time.sleep(1.0)  # Give system time to clean up

    # Capture menu state BEFORE withdrawing
    app.update_idletasks()
    tk_state = app.state()  # 'zoomed', 'normal', 'iconic'
    if tk_state == "iconic":
        menu_state = 2
    elif tk_state == "zoomed":
        menu_state = 3
    else:
        menu_state = 1

    # Pass the desired start state to OpenCV via env var
    os.environ["DALGONA_START_STATE"] = tk_state

    # Hide Tk window while OpenCV loop runs
    app.withdraw()

    try:
        # Run Dalgona and get True/False
        dalgona_win = bool(dalgona_game.run_dalgona())
    except Exception as e:
        print(f"Error in Dalgona game: {e}")
        dalgona_win = False
    finally:
        # CRITICAL: Aggressive cleanup after game ends
        cv2.destroyAllWindows()
        for _ in range(3):
            cv2.waitKey(500)

        time.sleep(0.5)
        gc.collect()
        gc.collect()  # Double garbage collection
        time.sleep(0.5)

    # Restore Tk window
    app.deiconify()
    if menu_state == 3:
        app.state("zoomed")
    elif menu_state == 2:
        app.iconify()
    else:
        app.state("normal")

    # Force Tkinter to update and redraw
    app.update()
    app.update_idletasks()

    # Show Dalgona result
    show_dalgona_result(dalgona_win)


ctk.CTkButton(
    dalgona,
    text="⬅ BACK TO MENU",
    width=200,
    command=lambda: go_menu()
).pack(pady=20)

# ===============================
# START
# ===============================
play_music(os.path.join(SOUNDS, "menu.mp3"))
show(menu)
app.mainloop()
