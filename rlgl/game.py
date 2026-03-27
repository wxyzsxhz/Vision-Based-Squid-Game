import customtkinter as ctk
import cv2
import os
import numpy as np
import time
import random
from PIL import Image, ImageTk
import pygame

# Suppress TensorFlow warnings
os.environ['TF_CPP_MIN_LOG_LEVEL'] = '3'

import mediapipe as mp
from mediapipe.tasks import python
from mediapipe.tasks.python import vision

# ===============================
# GAME STATE
# ===============================
cap = None
game_running = False
isgreen = True
light_time = 0
prev_time = 0
timer = 45
win_flag = False

# Progress tracking
progress = 0  # 0 to 100
GOAL_PROGRESS = 100
last_update_time = 0

# Hand tracking - NOW SUPPORTS 2 HANDS
hand_detector = None
hand_landmarker_result = None

# Gesture state
current_gesture_left = "IDLE"
current_gesture_right = "IDLE"
frozen_hand_positions = {}  # Store multiple hand positions

# Movement state
is_jumping = False
jump_velocity = 0
jump_height = 0
auto_run_speed = 3.5  # % per second
jump_forward_speed = 8.0  # % per second during jump (faster forward movement)

# Jump physics - LOW and WIDE
JUMP_INITIAL_VELOCITY = 12  # Much lower jump
GRAVITY = 1.2
MAX_JUMP_HEIGHT = 60  # Short hop

# Character animation
character_frame = 0
animation_speed = 0.2
character_x = 0

# Red light detection - Track character VISUAL position on screen
frozen_character_state = None  # Store {progress, jump_height, canvas_x} when red light starts

# Obstacles
obstacles = []

# Timing
GREEN_DUR = 5
RED_DUR = 3.5

# Hand landmark connections
HAND_CONNECTIONS = [
    (0, 1), (1, 2), (2, 3), (3, 4),  # Thumb
    (0, 5), (5, 6), (6, 7), (7, 8),  # Index
    (0, 9), (9, 10), (10, 11), (11, 12),  # Middle
    (0, 13), (13, 14), (14, 15), (15, 16),  # Ring
    (0, 17), (17, 18), (18, 19), (19, 20),  # Pinky
    (5, 9), (9, 13), (13, 17)  # Palm
]

# ===============================
# SELECTION STATE
# ===============================
selected_character = None
selected_background = None


def run_rlgl(parent_app, show_menu_callback, base_path, show):
    global cap, game_running, timer, isgreen, light_time, prev_time, win_flag
    global progress, hand_detector, hand_landmarker_result
    global current_gesture_left, current_gesture_right, frozen_hand_positions
    global character_frame, character_x, last_update_time
    global is_jumping, jump_velocity, jump_height
    global obstacles, frozen_character_state, jump_forward_speed
    global selected_character, selected_background

    # ===============================
    # PATHS
    # ===============================
    ASSETS = os.path.join(base_path, "assets")
    FRAMES = os.path.join(base_path, "frames")
    SOUNDS = os.path.join(base_path, "sounds")
    
    
    screen_w = parent_app.winfo_screenwidth()
    screen_h = parent_app.winfo_screenheight()

    # ===============================
    # SCREENS
    # ===============================
    start_screen = ctk.CTkFrame(parent_app)
    game_screen = ctk.CTkFrame(parent_app)
    result_screen = ctk.CTkFrame(parent_app)  # if you also have result

    for f in (start_screen, game_screen, result_screen):
        f.place(relx=0, rely=0, relwidth=1, relheight=1)

    def show(frame):
        frame.tkraise()

    # ===============================
    # START SCREEN CONTENT
    # ===============================
    selection_container = ctk.CTkFrame(start_screen)
    selection_container.place(relx=0.5, rely=0.5, anchor="center")


    # ===============================
    # LOAD PNG SEQUENCES
    # ===============================

    char_buttons = {}
    bg_buttons = {}

    def select_character(name):
        global selected_character
        selected_character = name
        
        for btn in char_buttons.values():
            btn.configure(border_width=0)
        
        char_buttons[name].configure(border_width=4, border_color="yellow")

    def select_background(name):
        global selected_background
        selected_background = name
        
        for btn in bg_buttons.values():
            btn.configure(border_width=0)
        
        bg_buttons[name].configure(border_width=4, border_color="yellow")


    def load_png_sequence(folder):
        frames = []
        files = sorted(os.listdir(folder))
        for file in files:
            if file.endswith(".png"):
                img = cv2.imread(os.path.join(folder, file), cv2.IMREAD_UNCHANGED)
                frames.append(img)
        return frames

    '''
    player_run_frames = load_png_sequence(os.path.join(FRAMES, "player_run"))
    player_idle_frames = load_png_sequence(os.path.join(FRAMES, "player_idle"))
    player_jump_frames = load_png_sequence(os.path.join(FRAMES, "player_jump"))
    '''
    doll_green_img = cv2.imread(os.path.join(FRAMES, "doll_green.png"), cv2.IMREAD_UNCHANGED)
    doll_red_img = cv2.imread(os.path.join(FRAMES, "doll_red.png"), cv2.IMREAD_UNCHANGED)

    backgrounds = {
        "bg1": cv2.imread(os.path.join(FRAMES, "bg1.png")),
        "bg2": cv2.imread(os.path.join(FRAMES, "bg2.png")),
        "bg3": cv2.imread(os.path.join(FRAMES, "bg3.png")),
        "bg4": cv2.imread(os.path.join(FRAMES, "bg4.png")),
        "bg5": cv2.imread(os.path.join(FRAMES, "bg5.png")),
    }

    # ===============================
    # LOAD 10 CHARACTERS (idle/run/jump)
    # ===============================
    characters = {}

    for i in range(1, 11):  # player1 to player10
        name = f"player{i}"
        characters[name] = {
            "idle": load_png_sequence(os.path.join(FRAMES, f"{name}_idle")),
            "run": load_png_sequence(os.path.join(FRAMES, f"{name}_run")),
            "jump": load_png_sequence(os.path.join(FRAMES, f"{name}_jump")),
        }


    # ===============================
    # LOAD ASSETS
    # ===============================

    selection_container = ctk.CTkFrame(start_screen)
    selection_container.pack(expand=True)

    ctk.CTkLabel(selection_container, text="Choose Character",
                font=ctk.CTkFont(size=24, weight="bold")).pack(pady=(20, 0))

    char_frame = ctk.CTkFrame(selection_container)
    char_frame.pack(pady=10)

    ctk.CTkLabel(selection_container, text="Choose Background",
    font=ctk.CTkFont(size=24, weight="bold")).pack(pady=(20, 0))

    bg_frame = ctk.CTkFrame(selection_container)
    bg_frame.pack(pady=10)

    def begin_game():
        if not selected_character or not selected_background:
            print("Please select character and background first!")
            return
        
        stop_music()
        show(game)
        parent_app.after(100, start_game)


    ctk.CTkButton(
        start_screen,
        text="🎮 START GAME",
        width=250,
        height=60,
        font=ctk.CTkFont(size=22, weight="bold"),
        fg_color="#059696",
        hover_color="#046b6b",
        command=begin_game
    ).place(relx=0.5, rely=0.85, anchor="center")

    
    # ===============================
    # LOAD GAME ASSETS
    # ===============================
    green_img = cv2.imread(os.path.join(FRAMES, "green.png"))
    red_img = cv2.imread(os.path.join(FRAMES, "red.png"))

    kill_bg = ImageTk.PhotoImage(
        Image.open(os.path.join(ASSETS, "kill.png"))
            .resize((screen_w, screen_h), Image.LANCZOS)
    )

    win_bg = ImageTk.PhotoImage(
        Image.open(os.path.join(ASSETS, "winner.png"))
            .resize((screen_w, screen_h), Image.LANCZOS)
    )

        
    # ===============================
    # SOUND FUNCTIONS
    # ===============================
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
            if pygame.mixer.get_busy():
                parent_app.after(100, check)
            else:
                play_music(music_path, loop=True)
        check()
    
    
    # ===============================
    # CHARACTER & BACKGROUND SELECTION
    # ===============================

    char_buttons = {}
    bg_buttons = {}

    def select_character(name):
        global selected_character
        selected_character = name
        for b in char_buttons.values():
            b.configure(border_width=0)
        char_buttons[name].configure(border_width=1, border_color="#C60660")

    def select_background(name):
        global selected_background
        selected_background = name
        for b in bg_buttons.values():
            b.configure(border_width=0)
        bg_buttons[name].configure(border_width=1, border_color="#C60660")

    # Character Buttons
    for name in characters.keys():
        preview = characters[name]["idle"][0]
        preview = cv2.resize(preview, (80, 120))
        preview_rgb = cv2.cvtColor(preview[:, :, :3], cv2.COLOR_BGR2RGB)
        img = ImageTk.PhotoImage(Image.fromarray(preview_rgb))

        btn = ctk.CTkButton(
            char_frame,   # 👈 changed here
            image=img,
            text="",
            width=70,
            height=100,
            fg_color="black",
            hover_color="#C60660",
            command=lambda n=name: select_character(n)
        )
        btn.image = img
        btn.pack(side="left", padx=5)
        char_buttons[name] = btn

    # Background Buttons
    for name in backgrounds.keys():
        preview = cv2.resize(backgrounds[name], (250, 140))
        preview_rgb = cv2.cvtColor(preview, cv2.COLOR_BGR2RGB)
        img = ImageTk.PhotoImage(Image.fromarray(preview_rgb))

        btn = ctk.CTkButton(
            bg_frame,  # 👈 changed here
            image=img,
            text="",
            width=200,
            height=130,
            fg_color="black",
            hover_color="#C60660",
            command=lambda n=name: select_background(n)
        )
        btn.image = img
        btn.pack(side="left", padx=10)
        bg_buttons[name] = btn

    
    # ===============================
    # GAME UI
    # ===============================
    game = ctk.CTkFrame(parent_app)  # create the frame first
    game.place(relx=0, rely=0, relwidth=1, relheight=1)  # make it fill the window

    # Game world container with padding
    game_world_container = ctk.CTkFrame(game, fg_color="transparent")
    game_world_container.place(relx=0.025, rely=0.025, relwidth=0.95, relheight=0.70)
    
    game_world_label = ctk.CTkLabel(game_world_container, text="")
    game_world_label.pack(fill="both", expand=True)
    
    # Info bar at bottom
    info_bar = ctk.CTkFrame(game, fg_color="#1a1a1a")
    info_bar.place(relx=0, rely=0.75, relwidth=1, relheight=0.25)
    
    info_bar.grid_columnconfigure(0, weight=1)
    info_bar.grid_columnconfigure(1, weight=2)
    info_bar.grid_rowconfigure(0, weight=1)
    
    # Camera feed (bottom-left)
    camera_container = ctk.CTkFrame(info_bar, corner_radius=10)
    camera_container.grid(row=0, column=0, sticky="nsew", padx=15, pady=15)
    
    camera_title = ctk.CTkLabel(
        camera_container,
        text="📷 YOUR HANDS",
        font=ctk.CTkFont(size=12, weight="bold")
    )
    camera_title.pack(pady=(5, 2))
    
    video_label = ctk.CTkLabel(camera_container, text="")
    video_label.pack(fill="both", expand=True, padx=5, pady=(0, 5))
    
    # Info section (bottom-right)
    info_section = ctk.CTkFrame(info_bar, fg_color="transparent")
    info_section.grid(row=0, column=1, sticky="nsew", padx=15, pady=15)
    
    # Row 1: Status and Gesture
    status_row = ctk.CTkFrame(info_section, fg_color="transparent")
    status_row.pack(fill="x", pady=5)
    
    status_label = ctk.CTkLabel(
        status_row,
        text="🟢 GREEN LIGHT",
        font=ctk.CTkFont(size=24, weight="bold")
    )
    status_label.pack(side="left", padx=10)
    
    gesture_label = ctk.CTkLabel(
        status_row,
        text="Gestures: IDLE",
        font=ctk.CTkFont(size=20)
    )
    gesture_label.pack(side="right", padx=10)
    
    # Row 2: Progress Bar
    progress_container = ctk.CTkFrame(info_section, fg_color="transparent")
    progress_container.pack(fill="x", pady=5)
    
    progress_title = ctk.CTkLabel(
        progress_container,
        text="PROGRESS:",
        font=ctk.CTkFont(size=14, weight="bold")
    )
    progress_title.pack(side="left", padx=5)
    
    progress_bar = ctk.CTkProgressBar(progress_container, width=400, height=25)
    progress_bar.pack(side="left", padx=10)
    progress_bar.set(0)
    
    progress_text = ctk.CTkLabel(
        progress_container,
        text="0%",
        font=ctk.CTkFont(size=18, weight="bold")
    )
    progress_text.pack(side="left", padx=5)
    
    # Row 3: Timer and Guide
    bottom_row = ctk.CTkFrame(info_section, fg_color="transparent")
    bottom_row.pack(fill="x", pady=5)
    
    timer_label = ctk.CTkLabel(
        bottom_row,
        text="⏱️ Time: 45s",
        font=ctk.CTkFont(size=18, weight="bold")
    )
    timer_label.pack(side="left", padx=10)
    
    guide_label = ctk.CTkLabel(
        bottom_row,
        text="✌️ Run | 👍 Jump | ✌️+👍 Jump Forward",
        font=ctk.CTkFont(size=14)
    )
    guide_label.pack(side="right", padx=10)
    
    # ===============================
    # RESULT SCREEN
    # ===============================
    result = ctk.CTkFrame(parent_app)  # create the frame first
    result.place(relx=0, rely=0, relwidth=1, relheight=1)  # make it fill the window

    result_label = ctk.CTkLabel(
    result, text="", font=ctk.CTkFont(size=30, weight="bold")
    )
    result_label.pack(pady=30)

    result_bg_label = ctk.CTkLabel(result, text="")
    result_bg_label.place(relx=0, rely=0, relwidth=1, relheight=1)
    result_label.lift()

    result_btn_box = ctk.CTkFrame(result, fg_color="transparent")
    result_btn_box.place(relx=0.5, rely=0.73, anchor="center")

    def go_menu():
        stop_music()
        play_music(os.path.join(SOUNDS, "menu.mp3"))
        show_menu_callback()

    def continue_game():
        stop_music()
        show(game)
        parent_app.update_idletasks()
        parent_app.after(100, start_game)

    ctk.CTkButton(
        result_btn_box, text="⬅ GO TO MENU", width=180, height=46,
        font=ctk.CTkFont(size=18),
        fg_color="#C60660", hover_color="#A90552",
        command=lambda: go_menu()
    ).pack(side="left")

    ctk.CTkButton(
        result_btn_box, text="🔁 CONTINUE", width=180, height=46,
        font=ctk.CTkFont(size=18),
        fg_color="#059696", hover_color="#046b6b",
        command=continue_game
    ).pack(side="left", padx=10)

    ctk.CTkButton(
        result_btn_box, text="❌ QUIT", width=180, height=46,
        font=ctk.CTkFont(size=18),
        fg_color="red",
        command=parent_app.destroy
    ).pack(side="left")
    
    # ===============================
    # OBSTACLE SYSTEM (REFACTORED)
    # ===============================
    
    def generate_obstacles():
        """Generate random LOW obstacles only (must jump over) - COMPLETELY RANDOM"""
        obs_list = []
        num_obstacles = random.randint(3, 5)  # Random number of obstacles (3-5)
        min_spacing = 180  # Minimum space between obstacles
        
        # Start and end boundaries
        start_boundary = 200  # Don't spawn too close to start
        end_boundary = 1100   # Don't spawn too close to finish
        
        positions = []
        attempts = 0
        max_attempts = 100
        
        while len(positions) < num_obstacles and attempts < max_attempts:
            # Completely random position across entire track
            x = random.randint(start_boundary, end_boundary)
            
            # Check if this position has enough spacing from all other obstacles
            valid_position = True
            for existing_x in positions:
                if abs(x - existing_x) < min_spacing:
                    valid_position = False
                    break
            
            if valid_position:
                positions.append(x)
            
            attempts += 1
        
        # Sort positions so obstacles are in order
        positions.sort()
        
        # Create obstacles at these random positions
        for x in positions:
            obs_list.append({
                "type": "low",
                "x": x,
                "width": 30,
                "height": 28,
                "passed": False
            })
        
        return obs_list
    
    def check_collision(char_x, char_y, obs, is_jumping_now, jump_h):
        """Check if character collides with obstacle - BLOCKS FORWARD MOVEMENT"""
        CHARACTER_WIDTH = 30
        CHARACTER_HEIGHT = 70
        
        # Character bounds
        char_left = char_x - CHARACTER_WIDTH // 2
        char_right = char_x + CHARACTER_WIDTH // 2
        char_bottom = char_y
        
        # Obstacle bounds
        obs_left = obs['x'] - obs['width'] // 2
        obs_right = obs['x'] + obs['width'] // 2
        
        # Check if character is trying to pass through obstacle
        if char_right > obs_left and char_left < obs_right:
            # LOW obstacle - must jump to hop over it (even a small hop works)
            if not is_jumping_now:
                # Not jumping at all - BLOCKS movement
                return True
        
        # Mark as passed if character is beyond it
        if char_x > obs_right + 10:
            obs['passed'] = True
        
        return False
    
    def draw_obstacles(canvas, obstacles_list, char_x, y_base):
        """Draw LOW obstacles only (rocks on ground)"""
        for obs in obstacles_list:
            x = obs['x']
            w = obs['width']
            h = obs['height']
            
            # Only draw if near character
            if abs(x - char_x) > 400:
                continue
            
            # LOW OBSTACLE (rock on ground)
            y = y_base
            
            # Draw rounded rock
            color = (100, 100, 100)  # Gray
            outline_color = (50, 50, 50)
            
            # Top half circle
            cv2.ellipse(canvas, (x, y - h//2), (w//2, h//2), 
                       0, 0, 180, color, -1)
            # Bottom rectangle
            cv2.rectangle(canvas, (x - w//2, y - h), (x + w//2, y), 
                         color, -1)
            # Outline
            cv2.ellipse(canvas, (x, y - h//2), (w//2, h//2), 
                       0, 0, 180, outline_color, 2)
            cv2.line(canvas, (x - w//2, y - h), (x - w//2, y), 
                    outline_color, 2)
            cv2.line(canvas, (x + w//2, y - h), (x + w//2, y), 
                    outline_color, 2)
            
            # Jump warning
            if not obs['passed']:
                cv2.putText(canvas, "JUMP!", (x - 25, y - h - 10), 
                           cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 0, 255), 2)
                
    #Transparent Overlay Function
    def overlay_png(canvas, png, x, y):
        h, w = png.shape[:2]

        if x < 0 or y < 0:
            return

        if y + h > canvas.shape[0] or x + w > canvas.shape[1]:
            return

        if png.shape[2] == 4:
            alpha = png[:, :, 3] / 255.0
            alpha = alpha[..., None]

            foreground = png[:, :, :3]
            background = canvas[y:y+h, x:x+w]

            blended = foreground * alpha + background * (1 - alpha)
            canvas[y:y+h, x:x+w] = blended.astype(np.uint8)
        else:
            canvas[y:y+h, x:x+w] = png

    
    # ===============================
    # CHARACTER DRAWING (SIMPLIFIED)
    # ===============================
    
    def draw_squid_game_player(canvas, x, y, frame, is_running, is_jump, jump_h):
        actual_y = int(y - jump_h)

        char_data = characters[selected_character]

        # Choose correct animation set
        if is_jump and len(char_data["jump"]) > 0:
            frames = char_data["jump"]
        elif is_running and len(char_data["run"]) > 0:
            frames = char_data["run"]
        else:
            frames = char_data["idle"]

        index = int(frame) % len(frames)
        sprite = frames[index]

        sprite = cv2.resize(sprite, (80, 120))

        h, w = sprite.shape[:2]
        draw_x = int(x - w // 2)
        draw_y = int(actual_y - h)

        overlay_png(canvas, sprite, draw_x, draw_y)

    def draw_doll_character(canvas, x, y, is_looking):
        sprite = doll_red_img if is_looking else doll_green_img

        sprite = cv2.resize(sprite, (80, 140))

        h, w = sprite.shape[:2]

        draw_x = int(x - w // 2)
        draw_y = int(y - h)

        overlay_png(canvas, sprite, draw_x, draw_y)

    def draw_game_world(canvas, prog, char_x, obs_list, is_jump, jump_h):
        """Draw the complete game world"""
        h, w, _ = canvas.shape
        y_base = h - 80
        
        # Background
        bg = cv2.resize(backgrounds[selected_background], (w, h))
        canvas[:] = bg

        
        # Ground
        cv2.line(canvas, (0, y_base), (w, y_base), (100, 150, 100), 3)
        
        # Track lines
        for i in range(5):
            y_line = y_base - 10 - (i * 8)
            cv2.line(canvas, (0, y_line), (w, y_line), (150, 180, 150), 1)
        
        # Start line
        start_x = 60
        cv2.line(canvas, (start_x, y_base - 70), (start_x, y_base), 
                (0, 255, 0), 4)
        cv2.putText(canvas, "START", (start_x - 25, y_base - 75),
                   cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0), 2)
        
        # Finish line
        finish_x = w - 100
        for i in range(7):
            y_start = y_base - 70 + (i * 10)
            color = (0, 0, 0) if i % 2 == 0 else (255, 255, 255)
            cv2.rectangle(canvas, (finish_x - 5, y_start),
                         (finish_x + 5, y_start + 10), color, -1)
        cv2.putText(canvas, "FINISH", (finish_x - 30, y_base - 75),
                   cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 0, 0), 2)
        
        # Doll at finish
        doll_x = finish_x + 40
        draw_doll_character(canvas, doll_x, y_base, not isgreen)
        
        # Obstacles
        draw_obstacles(canvas, obs_list, char_x, y_base)
        
        # Player
        is_running = isgreen
        draw_squid_game_player(canvas, char_x, y_base, character_frame,
                              is_running, is_jump, jump_h)
        
        # Distance markers
        for i in range(0, 101, 25):
            x_pos = int((i / 100.0) * (w - 150)) + 100
            cv2.line(canvas, (x_pos, y_base + 5), (x_pos, y_base + 15),
                    (100, 100, 100), 2)
            cv2.putText(canvas, f"{i}%", (x_pos - 15, y_base + 30),
                       cv2.FONT_HERSHEY_SIMPLEX, 0.4, (80, 80, 80), 1)
    
    # ===============================
    # HAND TRACKING (2 HANDS SUPPORT)
    # ===============================
    
    def hand_landmarker_callback(result, output_image, timestamp_ms):
        global hand_landmarker_result
        hand_landmarker_result = result
    
    def draw_hand_landmarks(frame, hand_landmarks, hand_label):
        """Draw hand landmarks with left/right label"""
        h, w, _ = frame.shape
        
        for connection in HAND_CONNECTIONS:
            start_idx, end_idx = connection
            if start_idx < len(hand_landmarks) and end_idx < len(hand_landmarks):
                start = hand_landmarks[start_idx]
                end = hand_landmarks[end_idx]
                
                start_point = (int(start.x * w), int(start.y * h))
                end_point = (int(end.x * w), int(end.y * h))
                
                color = (0, 255, 255) if hand_label == "Left" else (255, 255, 0)
                cv2.line(frame, start_point, end_point, color, 2)
        
        for landmark in hand_landmarks:
            x = int(landmark.x * w)
            y = int(landmark.y * h)
            color = (255, 0, 255) if hand_label == "Left" else (255, 128, 0)
            cv2.circle(frame, (x, y), 5, color, -1)
        
        # Draw label
        wrist = hand_landmarks[0]
        label_x = int(wrist.x * w)
        label_y = int(wrist.y * h) - 20
        cv2.putText(frame, hand_label, (label_x, label_y),
                   cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 2)
    
    def is_finger_extended(hand_landmarks, tip_idx, pip_idx):
        tip = hand_landmarks[tip_idx]
        pip = hand_landmarks[pip_idx]
        return tip.y < pip.y
    
    def is_thumb_extended(hand_landmarks):
        thumb_tip = hand_landmarks[4]
        thumb_ip = hand_landmarks[3]
        wrist = hand_landmarks[0]
        
        thumb_distance = abs(thumb_tip.x - wrist.x)
        joint_distance = abs(thumb_ip.x - wrist.x)
        
        return thumb_distance > joint_distance
    
    def count_extended_fingers(hand_landmarks):
        count = 0
        
        if is_thumb_extended(hand_landmarks):
            count += 1
        
        if is_finger_extended(hand_landmarks, 8, 6):
            count += 1
        if is_finger_extended(hand_landmarks, 12, 10):
            count += 1
        if is_finger_extended(hand_landmarks, 16, 14):
            count += 1
        if is_finger_extended(hand_landmarks, 20, 18):
            count += 1
        
        return count
    
    def is_peace_sign(hand_landmarks):
        index_up = is_finger_extended(hand_landmarks, 8, 6)
        middle_up = is_finger_extended(hand_landmarks, 12, 10)
        ring_down = not is_finger_extended(hand_landmarks, 16, 14)
        pinky_down = not is_finger_extended(hand_landmarks, 20, 18)
        
        return index_up and middle_up and ring_down and pinky_down
    
    def is_thumbs_up(hand_landmarks):
        thumb_up = is_thumb_extended(hand_landmarks)
        index_down = not is_finger_extended(hand_landmarks, 8, 6)
        middle_down = not is_finger_extended(hand_landmarks, 12, 10)
        ring_down = not is_finger_extended(hand_landmarks, 16, 14)
        pinky_down = not is_finger_extended(hand_landmarks, 20, 18)
        
        return thumb_up and index_down and middle_down and ring_down and pinky_down
    
    def detect_gesture(hand_landmarks):
        """
        Detect gesture:
        ✌️ Peace = RUN
        👍 Thumbs up = JUMP
        """
        if is_thumbs_up(hand_landmarks):
            return "JUMP"
        
        if is_peace_sign(hand_landmarks):
            return "RUN"
        
        return "IDLE"
    
    def get_hand_center(hand_landmarks):
        """Get center position of hand for movement tracking"""
        x_sum = sum([lm.x for lm in hand_landmarks])
        y_sum = sum([lm.y for lm in hand_landmarks])
        z_sum = sum([lm.z for lm in hand_landmarks])
        
        num_landmarks = len(hand_landmarks)
        
        return (
            x_sum / num_landmarks,
            y_sum / num_landmarks,
            z_sum / num_landmarks
        )
    
    def hands_moved(current_hand, frozen_position, threshold=0.05):
        """Check if hand moved from frozen position"""
        if frozen_position is None:
            return False
        
        current_center = get_hand_center(current_hand)
        
        distance = np.sqrt(
            (current_center[0] - frozen_position[0])**2 +
            (current_center[1] - frozen_position[1])**2 +
            (current_center[2] - frozen_position[2])**2
        )
        
        return distance > threshold
    
    # ===============================
    # GAME LOGIC (REFACTORED)
    # ===============================

    def start_game():
        global cap, game_running, timer, isgreen, light_time, prev_time, win_flag
        global progress, hand_detector, frozen_hand_positions
        global hand_landmarker_result, character_frame, character_x
        global current_gesture_left, current_gesture_right, last_update_time
        global is_jumping, jump_velocity, jump_height
        global obstacles

        if cap:
            cap.release()

        parent_app.after(100, _open_camera)

    def _open_camera():
        global cap, game_running, timer, isgreen, light_time, prev_time, win_flag
        global progress, hand_detector, frozen_hand_positions
        global hand_landmarker_result, character_frame, character_x
        global current_gesture_left, current_gesture_right, last_update_time
        global is_jumping, jump_velocity, jump_height
        global obstacles, frozen_character_state

        status_label.configure(text="Loading hand tracking...")
        parent_app.update_idletasks()
        
        # Create hand detector - NOW SUPPORTS 2 HANDS
        base_options = python.BaseOptions(model_asset_path='hand_landmarker.task')
        options = vision.HandLandmarkerOptions(
            base_options=base_options,
            running_mode=vision.RunningMode.LIVE_STREAM,
            num_hands=2,  # CHANGED: Support 2 hands
            min_hand_detection_confidence=0.5,
            min_hand_presence_confidence=0.5,
            min_tracking_confidence=0.5,
            result_callback=hand_landmarker_callback
        )
        hand_detector = vision.HandLandmarker.create_from_options(options)

        cap = cv2.VideoCapture(0)
        play_music(os.path.join(SOUNDS, "song.mp3"))

        status_label.configure(text="")

        # Reset game state
        timer = 60
        isgreen = True
        light_time = time.time()
        prev_time = time.time()
        win_flag = False
        game_running = True
        progress = 0
        frozen_hand_positions = {}  # Store multiple frozen positions
        hand_landmarker_result = None
        character_frame = 0
        character_x = 0
        
        # Reset movement
        current_gesture_left = "IDLE"
        current_gesture_right = "IDLE"
        last_update_time = time.time()
        is_jumping = False
        jump_velocity = 0
        jump_height = 0
        frozen_character_state = None  # Track character visual position during red light
        
        # Generate obstacles with randomization
        obstacles = generate_obstacles()
        
        progress_bar.set(0)
        progress_text.configure(text="0%")
        gesture_label.configure(text="Gestures: IDLE")

        update_game()

    def update_game():
        global timer, prev_time, isgreen, light_time
        global progress, frozen_hand_positions, hand_landmarker_result
        global current_gesture_left, current_gesture_right, last_update_time
        global is_jumping, jump_velocity, jump_height
        global character_frame, character_x, frozen_character_state

        if not game_running:
            return

        ret, frame = cap.read()
        if not ret:
            parent_app.after(16, update_game)
            return
        
        frame = cv2.flip(frame, 1)

        # Timer
        if time.time() - prev_time >= 1:
            timer -= 1
            prev_time = time.time()

        timer_label.configure(text=f"⏱️ Time: {timer}s")
        
        # Light toggle
        elapsed = time.time() - light_time
        if isgreen and elapsed >= GREEN_DUR:
            isgreen = False
            light_time = time.time()
            # Will capture state AFTER physics update below
            
        elif not isgreen and elapsed >= RED_DUR:
            isgreen = True
            light_time = time.time()
            frozen_character_state = None

        status_label.configure(text="🟢 GREEN LIGHT" if isgreen else "🔴 RED LIGHT - FREEZE!")
        
        # Time delta
        current_time = time.time()
        time_delta = current_time - last_update_time
        last_update_time = current_time
        
        # Process hand tracking
        frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        mp_image = mp.Image(image_format=mp.ImageFormat.SRGB, data=frame_rgb)
        timestamp_ms = int(time.time() * 1000)
        hand_detector.detect_async(mp_image, timestamp_ms)
        
        gesture_left = "IDLE"
        gesture_right = "IDLE"
        
        if hand_landmarker_result and hand_landmarker_result.hand_landmarks:
            num_hands = len(hand_landmarker_result.hand_landmarks)
            
            for idx, hand_landmarks in enumerate(hand_landmarker_result.hand_landmarks):
                # Determine if left or right hand
                handedness = hand_landmarker_result.handedness[idx][0]
                hand_label = handedness.category_name  # "Left" or "Right"
                
                draw_hand_landmarks(frame, hand_landmarks, hand_label)
                
                detected_gesture = detect_gesture(hand_landmarks)
                
                # Store gestures by hand
                if hand_label == "Left":
                    gesture_left = detected_gesture
                    current_gesture_left = detected_gesture
                else:
                    gesture_right = detected_gesture
                    current_gesture_right = detected_gesture
            
            # Update gesture display
            if num_hands == 2:
                gesture_label.configure(
                    text=f"L: {current_gesture_left} | R: {current_gesture_right}"
                )
            elif num_hands == 1:
                single_gesture = gesture_left if gesture_left != "IDLE" else gesture_right
                gesture_label.configure(text=f"Gesture: {single_gesture}")
            else:
                gesture_label.configure(text="Gestures: IDLE")
        
        # Process movement - ALWAYS (both green and red light)
        has_run = gesture_left == "RUN" or gesture_right == "RUN"
        has_jump = gesture_left == "JUMP" or gesture_right == "JUMP"
        
        # COMBINED GESTURE: Run + Jump = Jump Forward (WIDER, FASTER)
        if has_run and has_jump:
            # Move forward FASTER while jumping
            progress += jump_forward_speed * time_delta  # Using faster speed!
            progress = min(progress, GOAL_PROGRESS)
            character_frame += animation_speed
            
            # Trigger jump if not already jumping
            if not is_jumping:
                is_jumping = True
                jump_velocity = JUMP_INITIAL_VELOCITY
            
            progress_bar.set(progress / 100.0)
            progress_text.configure(text=f"{int(progress)}%")
            
        # SINGLE GESTURES
        elif has_run:
            # Just run (no jump)
            progress += auto_run_speed * time_delta
            progress = min(progress, GOAL_PROGRESS)
            character_frame += animation_speed
            
            progress_bar.set(progress / 100.0)
            progress_text.configure(text=f"{int(progress)}%")
            
        elif has_jump and not is_jumping:
            # Just jump (no forward movement)
            is_jumping = True
            jump_velocity = JUMP_INITIAL_VELOCITY
        
        # Update jump physics
        if is_jumping:
            jump_height += jump_velocity
            jump_velocity -= GRAVITY
            
            if jump_height <= 0:
                is_jumping = False
                jump_height = 0
                jump_velocity = 0
        
        # Calculate character position on canvas
        GAME_W = 1200
        canvas_char_x = int((progress / 100.0) * (GAME_W - 150)) + 100
        
        # RED LIGHT - Capture and check character VISUAL position (including jump!)
        if not isgreen:
            # First time red light is on? Capture the character's state
            if frozen_character_state is None:
                frozen_character_state = {
                    'progress': progress,
                    'jump_height': jump_height,
                    'canvas_x': canvas_char_x
                }
            else:
                # Check if character moved visually on screen
                # More lenient thresholds to avoid false positives
                progress_moved = abs(progress - frozen_character_state['progress']) > 1.0  # 1% tolerance
                jump_changed = abs(jump_height - frozen_character_state['jump_height']) > 5  # 5px tolerance
                position_moved = abs(canvas_char_x - frozen_character_state['canvas_x']) > 15  # 15px tolerance
                
                # Character VISIBLY moved on screen?
                if progress_moved or jump_changed or position_moved:
                    # CHARACTER MOVED! Game over
                    end_game(False)
                    return
        
        # Check collisions - BLOCKS forward movement
        for obs in obstacles:
            if obs['passed']:
                continue
                
            if check_collision(canvas_char_x, 520, obs, is_jumping, jump_height):
                # Hit obstacle - PREVENT forward movement
                # Roll back progress slightly
                if progress > 0:
                    progress -= 0.5
                    progress_bar.set(progress / 100.0)
                    progress_text.configure(text=f"{int(progress)}%")
        
        # Win condition
        if progress >= GOAL_PROGRESS:
            end_game(True)
            return
        
        # Draw game world
        GAME_W, GAME_H = 1200, 600
        game_canvas = np.ones((GAME_H, GAME_W, 3), dtype=np.uint8) * 240
        
        draw_game_world(game_canvas, progress, canvas_char_x, obstacles,
                       is_jumping, jump_height)
        
        update_display(game_canvas, game_world_label)
        
        # Draw camera
        CAM_W, CAM_H = 320, 240
        cam_frame = cv2.resize(frame, (CAM_W, CAM_H))
        update_display(cam_frame, video_label)

        # Time out
        if timer <= 0:
            end_game(False)
            return

        parent_app.after(16, update_game)

    def update_display(frame, label_widget):
        rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        imgtk = ImageTk.PhotoImage(Image.fromarray(rgb))
        label_widget.imgtk = imgtk
        label_widget.configure(image=imgtk)

    def end_game(win):
        global game_running, cap, hand_detector
        game_running = False

        if cap:
            cap.release()
            cap = None
        
        if hand_detector:
            hand_detector.close()
            hand_detector = None

        stop_music()
        show(result)

        if win:
            stop_music()
            sfx = play_sound(os.path.join(SOUNDS, "win.mp3"))
            play_result_music_after(sfx, os.path.join(SOUNDS, "menu.mp3"))
            result_label.configure(text="🎉 YOU WIN!", text_color="green")
            result_bg_label.configure(image=win_bg)
            result_bg_label.image = win_bg
        else:
            stop_music()
            sfx = play_sound(os.path.join(SOUNDS, "kill.mp3"))
            play_result_music_after(sfx, os.path.join(SOUNDS, "menu.mp3"))
            result_label.configure(text="💀 ELIMINATED", text_color="red")
            result_bg_label.configure(image=kill_bg)
            result_bg_label.image = kill_bg
    
    # ===============================
    # START GAME
    # ===============================
    
    start_screen.tkraise()
    pygame.mixer.music.load(os.path.join(SOUNDS, "start.mp3"))
    pygame.mixer.music.play()

