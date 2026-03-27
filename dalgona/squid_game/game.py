import cv2
import random
import time
import math
import numpy as np
import pygame
import os
import ctypes
import gc

from dalgona.track_module.trackmodule import HandDetector

os.environ["OPENCV_UI"] = "1"

pygame.mixer.init()

# -------------------------------------------------
# COLORS
# -------------------------------------------------
RED = (0, 0, 255)
GREEN = (0, 255, 0)
BLUE = (255, 0, 0)
YELLOW = (0, 255, 255)        # Bright yellow for dashes
WHITE = (255, 255, 255)
PURPLE = (255, 0, 255)
ORANGE = (0, 165, 255)
BLACK = (0, 0, 0)
CYAN = (255, 255, 0)

FILLED = -1

# -------------------------------------------------
# GAME SETTINGS
# -------------------------------------------------
START_RADIUS = 30          # How close to start to begin
PATH_WIDTH = 25            # Width of the valid path (yellow zone)
OUTSIDE_TOLERANCE = 15     # How far outside the path you can go before losing
DASH_LENGTH = 12           # Length of each dash
DASH_GAP = 8               # Gap between dashes
DASH_WIDTH = 3             # Thin dash width
CUT_WIDTH = 4              # Width of the cut in the cookie outline
TIME_LIMIT = 30            # 30 seconds time limit

FRAME_WIDTH = 1280
FRAME_HEIGHT = 720

BASE = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(os.path.dirname(BASE))

win_sound = pygame.mixer.Sound(os.path.join(PROJECT_ROOT, "sounds", "win.mp3"))
lose_sound = pygame.mixer.Sound(os.path.join(PROJECT_ROOT, "sounds", "kill.mp3"))

# -------------------------------------------------
# SHAPES
# -------------------------------------------------
SHAPES = {
    "triangle": {
        "image": os.path.join(BASE, "images", "triangle_biscuit.jpg"),
        "broken": os.path.join(BASE, "images", "triangle_biscuit_broken.jpg"),
    },
    "circle": {
        "image": os.path.join(BASE, "images", "circle_biscuit.png"),
        "broken": os.path.join(BASE, "images", "circle_biscuit_broken.png"),
    },
    "star": {
        "image": os.path.join(BASE, "images", "star_biscuit.png"),
        "broken": os.path.join(BASE, "images", "star_biscuit_broken.png"),
    },
    "umbrella": {
        "image": os.path.join(BASE, "images", "umbrella_biscuit.png"),
        "broken": os.path.join(BASE, "images", "umbrella_biscuit_broken.png"),
    },
}

WIN_NAME = "Dalgona Game"
game_counter = 0


# -------------------------------------------------
# HELPER FUNCTIONS
# -------------------------------------------------
def prepare_target_image(path: str) -> np.ndarray:
    """Load and prepare the shape image"""
    img = cv2.imread(path)
    if img is None:
        print(f"Error: Could not load image from {path}")
        return np.ones((1080, 1440, 3), dtype=np.uint8) * 255

    img = cv2.resize(img, (512, 512))

    # Place in center of white canvas
    canvas = np.ones((1080, 1440, 3), dtype=np.uint8) * 255
    cy, cx = 1080 // 2, 1440 // 2
    canvas[cy-256:cy+256, cx-256:cx+256] = img
    return canvas


def extract_shape_outline(img: np.ndarray):
    """Find the outline of the shape"""
    hsv = cv2.cvtColor(img, cv2.COLOR_BGR2HSV)

    # Detect red/brown colors (the dalgona)
    lower1 = np.array([0, 70, 50])
    upper1 = np.array([10, 255, 255])
    lower2 = np.array([170, 70, 50])
    upper2 = np.array([180, 255, 255])

    mask = cv2.inRange(hsv, lower1, upper1) + cv2.inRange(hsv, lower2, upper2)
    mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, np.ones((5,5), np.uint8))

    contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    return max(contours, key=cv2.contourArea) if contours else None


def get_shape_points(contour):
    """Get points along the shape outline"""
    epsilon = 0.01 * cv2.arcLength(contour, True)
    approx = cv2.approxPolyDP(contour, epsilon, True)
    return approx.reshape(-1, 2).tolist()


def create_dashed_outline(points, dash_length=DASH_LENGTH, gap_length=DASH_GAP):
    """Create a dashed outline from the shape points - YELLOW dashes"""
    dashes = []

    for i in range(len(points)):
        p1 = points[i]
        p2 = points[(i + 1) % len(points)]

        dist = math.hypot(p2[0] - p1[0], p2[1] - p1[1])
        dx = p2[0] - p1[0]
        dy = p2[1] - p1[1]

        if dist > 0:
            dx /= dist
            dy /= dist

        current_dist = 0

        while current_dist < dist:
            dash_end = min(current_dist + dash_length, dist)

            start_x = int(p1[0] + dx * current_dist)
            start_y = int(p1[1] + dy * current_dist)
            end_x = int(p1[0] + dx * dash_end)
            end_y = int(p1[1] + dy * dash_end)

            dashes.append(((start_x, start_y), (end_x, end_y)))
            current_dist = dash_end + gap_length

    return dashes


def create_cut_cookie(shape_img, cut_dashes, cut_width=CUT_WIDTH):
    """Create a version of the cookie with the red outline cut where dashes were erased"""
    result = shape_img.copy()

    for (start_x, start_y), (end_x, end_y) in cut_dashes:
        cv2.line(result, (start_x, start_y), (end_x, end_y), (255, 255, 255), cut_width)

    return result


def point_to_line_distance(px, py, x1, y1, x2, y2):
    """Calculate distance from point to line segment"""
    dx, dy = x2 - x1, y2 - y1

    if dx == 0 and dy == 0:
        return math.hypot(px - x1, py - y1)

    t = ((px - x1) * dx + (py - y1) * dy) / (dx * dx + dy * dy)
    t = max(0, min(1, t))

    closest_x = x1 + t * dx
    closest_y = y1 + t * dy

    return math.hypot(px - closest_x, py - closest_y)


def _apply_window_state():
    """Set window state (maximized/minimized/normal)"""
    start_state = os.environ.get("DALGONA_START_STATE", "normal")
    if start_state == "withdrawn":
        start_state = "zoomed"

    cv2.waitKey(1)

    try:
        user32 = ctypes.windll.user32
        hwnd = user32.FindWindowW(None, WIN_NAME)
        if hwnd:
            if start_state == "zoomed":
                user32.ShowWindow(hwnd, 3)  # Maximize
            elif start_state == "iconic":
                user32.ShowWindow(hwnd, 6)  # Minimize
            else:
                user32.ShowWindow(hwnd, 9)  # Restore
    except:
        pass


# -------------------------------------------------
# MAIN GAME - Single Game
# -------------------------------------------------
def run_dalgona() -> bool:
    # CRITICAL: Force destroy any existing OpenCV windows before starting
    cv2.destroyAllWindows()
    cv2.waitKey(500)
    gc.collect()

    """Run a single dalgona game and return True for win, False for lose"""
    global game_counter
    game_counter += 1

    print(f"\n{'='*60}")
    print(f"STARTING GAME #{game_counter}")
    print(f"{'='*60}")

    # 1. Pick random shape
    shape_name = random.choice(list(SHAPES.keys()))
    print(f"Selected shape: {shape_name}")

    # 2. Load images
    base_img = prepare_target_image(SHAPES[shape_name]["image"])
    broken_img = prepare_target_image(SHAPES[shape_name]["broken"])

    # 3. Get shape outline
    contour = extract_shape_outline(base_img)
    if contour is None:
        print("Error: Could not extract shape outline")
        return False

    # 4. Get points along shape
    points = get_shape_points(contour)

    # 5. Scale points to screen size
    scale_x = FRAME_WIDTH / 1440
    scale_y = FRAME_HEIGHT / 1080
    scaled_points = [(int(x * scale_x), int(y * scale_y)) for x, y in points]

    # 6. Create dashed outline
    all_dashes = create_dashed_outline(scaled_points, DASH_LENGTH, DASH_GAP)
    print(f"Created {len(all_dashes)} CYAN dashes")

    # 7. Find start point (topmost)
    start_point = min(scaled_points, key=lambda p: p[1])

    # 8. Initialize camera
    cap = None
    backends = [cv2.CAP_DSHOW, cv2.CAP_MSMF, cv2.CAP_ANY]

    for backend in backends:
        try:
            print(f"Attempting to open camera with backend {backend}")
            cap = cv2.VideoCapture(0, backend)

            if cap.isOpened():
                cap.set(cv2.CAP_PROP_FRAME_WIDTH, FRAME_WIDTH)
                cap.set(cv2.CAP_PROP_FRAME_HEIGHT, FRAME_HEIGHT)
                cap.set(cv2.CAP_PROP_FPS, 30)
                cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)

                # Test read
                success, test_frame = cap.read()
                if success and test_frame is not None:
                    print(f"Camera opened successfully with backend {backend}")
                    break
                else:
                    cap.release()
                    cap = None
            else:
                if cap:
                    cap.release()
                cap = None
        except Exception as e:
            print(f"Error opening camera: {e}")
            if cap:
                cap.release()
            cap = None

    # 9. Initialize hand detector
    detector = None
    if cap and cap.isOpened():
        try:
            detector = HandDetector(model_path=os.path.join(BASE, "hand_landmarker.task"))
        except Exception as e:
            print(f"Error loading hand detector: {e}")

    # 10. Setup window
    cv2.namedWindow(WIN_NAME, cv2.WINDOW_NORMAL)
    cv2.resizeWindow(WIN_NAME, FRAME_WIDTH, FRAME_HEIGHT)
    _apply_window_state()

    # 11. Game state variables
    game_state = "waiting"
    erased_dashes = set()
    cut_dashes = []
    start_time = 0
    warning_message = ""
    game_ended = False
    final_result = False

    print("\n=== DALGONA GAME ===")
    print("1. Place your finger on the RED START dot")
    print("2. Trace the shape to cut the red cookie outline")
    print("3. When you touch a YELLOW dash, it disappears")
    print("4. Stay within the yellow path while tracing")
    print(f"5. You have {TIME_LIMIT} seconds")
    print("6. Cut ALL YELLOW dashes to win!\n")

    # Show the new cookie immediately
    shape_bg = cv2.resize(base_img, (FRAME_WIDTH, FRAME_HEIGHT))
    cv2.imshow(WIN_NAME, shape_bg)
    cv2.waitKey(100)

    try:
        while True:
            # Read camera frame if available
            frame = None
            if cap and cap.isOpened():
                success, frame = cap.read()
                if success and frame is not None:
                    frame = cv2.flip(frame, 1)
                    frame = cv2.resize(frame, (FRAME_WIDTH, FRAME_HEIGHT))

            # Prepare backgrounds
            shape_bg = cv2.resize(base_img, (FRAME_WIDTH, FRAME_HEIGHT))
            broken_bg = cv2.resize(broken_img, (FRAME_WIDTH, FRAME_HEIGHT))

            # Create cookie with cut red outline
            if cut_dashes:
                display = create_cut_cookie(shape_bg, cut_dashes, cut_width=CUT_WIDTH)
            else:
                display = shape_bg.copy()

            # Draw the valid path area
            overlay = display.copy()
            for i in range(len(scaled_points)):
                p1 = scaled_points[i]
                p2 = scaled_points[(i + 1) % len(scaled_points)]
                cv2.line(overlay, p1, p2, YELLOW, PATH_WIDTH * 2)
            cv2.addWeighted(overlay, 0.3, display, 0.7, 0, display)

            # Draw start point
            cv2.circle(display, start_point, START_RADIUS, RED, FILLED)
            cv2.putText(display, "START HERE",
                       (start_point[0] - 60, start_point[1] - 30),
                       cv2.FONT_HERSHEY_SIMPLEX, 0.7, RED, 2)

            # Draw dashed outline
            for i, (dash_start, dash_end) in enumerate(all_dashes):
                if i not in erased_dashes:
                    cv2.line(display, dash_start, dash_end, CYAN, DASH_WIDTH)

            # Get hand position if detector is available
            finger_x, finger_y = None, None
            if detector and frame is not None:
                frame = detector.findHands(frame)
                lmlist = detector.findPosition(frame, draw=False)
                if lmlist and len(lmlist) > 8:
                    finger_x, finger_y = lmlist[8][0], lmlist[8][1]

            # Game logic
            if finger_x is not None and finger_y is not None and not game_ended:
                # Show finger position
                cv2.circle(display, (finger_x, finger_y), 8, PURPLE, 2)
                cv2.circle(display, (finger_x, finger_y), 3, PURPLE, FILLED)

                # Check distance to shape
                min_dist = float('inf')
                for i in range(len(scaled_points)):
                    p1 = scaled_points[i]
                    p2 = scaled_points[(i + 1) % len(scaled_points)]
                    dist = point_to_line_distance(finger_x, finger_y, p1[0], p1[1], p2[0], p2[1])
                    min_dist = min(min_dist, dist)

                # Game state machine
                if game_state == "waiting":
                    dist_to_start = math.hypot(finger_x - start_point[0],
                                              finger_y - start_point[1])
                    if dist_to_start < START_RADIUS:
                        game_state = "playing"
                        start_time = time.time()
                        erased_dashes = set()
                        cut_dashes = []
                        print("Game started!")

                elif game_state == "playing":
                    elapsed = time.time() - start_time
                    time_remaining = max(0, TIME_LIMIT - int(elapsed))

                    if time_remaining <= 0:
                        game_state = "lost"
                        lose_sound.play()
                        game_ended = True
                        final_result = False

                    # Check if outside the valid zone
                    if min_dist > PATH_WIDTH:
                        if min_dist > PATH_WIDTH + OUTSIDE_TOLERANCE:
                            game_state = "lost"
                            lose_sound.play()
                            print("Game Over! Too far outside the line!")
                            game_ended = True
                            final_result = False
                        else:
                            warning_message = "Stay inside the yellow zone!"
                            cv2.circle(display, (finger_x, finger_y), 15, ORANGE, 2)
                    else:
                        warning_message = ""

                    # Check for dashes to cut
                    for i, (dash_start, dash_end) in enumerate(all_dashes):
                        if i not in erased_dashes:
                            dist_to_dash = point_to_line_distance(finger_x, finger_y,
                                                                 dash_start[0], dash_start[1],
                                                                 dash_end[0], dash_end[1])
                            if dist_to_dash < DASH_WIDTH * 4:
                                erased_dashes.add(i)
                                cut_dashes.append((dash_start, dash_end))
                                print(f"Dash {i} cut!")

                    # Check win condition
                    if len(erased_dashes) == len(all_dashes):
                        game_state = "won"
                        win_sound.play()
                        print(f"Victory! Time: {int(elapsed)} seconds")
                        game_ended = True
                        final_result = True

            # Prepare final display - NO TEXT
            if game_state == "lost":
                final = broken_bg.copy()
            elif game_state == "won":
                final = create_cut_cookie(shape_bg, cut_dashes, cut_width=CUT_WIDTH)
            else:
                final = display.copy()
                if frame is not None:
                    final = cv2.addWeighted(frame, 0.3, display, 0.7, 0)

            # Draw HUD
            if game_state == "playing" and not game_ended:
                elapsed = int(time.time() - start_time)
                time_remaining = max(0, TIME_LIMIT - elapsed)
                progress_percent = (len(erased_dashes) / len(all_dashes)) * 100 if all_dashes else 0

                cv2.putText(final, f"Time: {time_remaining}s", (30, 40),
                           cv2.FONT_HERSHEY_SIMPLEX, 1.0,
                           RED if time_remaining < 10 else WHITE, 2)
                cv2.putText(final, f"Progress: {progress_percent:.1f}%", (30, 80),
                           cv2.FONT_HERSHEY_SIMPLEX, 0.9, YELLOW, 2)

                if warning_message:
                    cv2.putText(final, warning_message, (400, 100),
                               cv2.FONT_HERSHEY_SIMPLEX, 1, ORANGE, 3)

            if game_state == "waiting":
                cv2.putText(final, "Place finger on RED dot to start", (300, 100),
                           cv2.FONT_HERSHEY_SIMPLEX, 1, YELLOW, 3)

            # Display
            cv2.imshow(WIN_NAME, final)
            key = cv2.waitKey(1) & 0xFF

            # Key controls
            if key == ord('q'):
                game_ended = True
                final_result = False
                break

            # Exit after game ends
            if game_ended:
                print(f"Game ended: {game_state}. Showing result for 3 seconds...")

                # Show final screen for 3 seconds
                start_display = time.time()
                while time.time() - start_display < 3:
                    cv2.imshow(WIN_NAME, final)
                    key = cv2.waitKey(100) & 0xFF
                    if key == ord('q'):
                        break

                break

    except Exception as e:
        print(f"Error during game: {e}")
    finally:
        # Clean up this game's resources
        if cap:
            cap.release()

        # CRITICAL: Always destroy windows, especially after a win
        cv2.destroyAllWindows()
        for _ in range(3):
            cv2.waitKey(500)

        time.sleep(0.5)  # Give system time to clean up

    print(f"Game #{game_counter} resources released")
    return final_result


# -------------------------------------------------
# MAIN LOOP - For standalone testing
# -------------------------------------------------
if __name__ == "__main__":
    print("="*60)
    print("DALGONA GAME - Press Ctrl+C to exit")
    print("="*60)

    try:
        while True:
            # Run the game
            result = run_dalgona()
            print(f"\nGame {game_counter} result: {'WIN' if result else 'LOSE'}")

            # Ask if player wants to continue
            print("\n" + "="*60)
            print("Press ENTER to play again, or 'q' to quit")
            print("="*60)

            # Wait for user input
            user_input = input().strip().lower()
            if user_input == 'q':
                break

            # CRITICAL: Completely destroy everything and start fresh
            print("Preparing new game...")
            cv2.destroyAllWindows()
            cv2.waitKey(1000)  # Wait a full second for cleanup

            # Force garbage collection
            gc.collect()

            # Clear console
            os.system('cls' if os.name == 'nt' else 'clear')

    except KeyboardInterrupt:
        print("\n\nGame terminated by user")
    finally:
        # Final cleanup
        cv2.destroyAllWindows()
        print("Cleanup complete. Goodbye!")
