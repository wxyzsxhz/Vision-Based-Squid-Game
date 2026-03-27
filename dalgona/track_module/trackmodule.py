import cv2
import mediapipe as mp
import numpy as np
from mediapipe.tasks import python
from mediapipe.tasks.python import vision
import math

# Hardcoded hand connections (same as old MediaPipe)
HAND_CONNECTIONS = [
    (0, 1), (1, 2), (2, 3), (3, 4),        # Thumb
    (0, 5), (5, 6), (6, 7), (7, 8),        # Index
    (0, 9), (9, 10), (10, 11), (11, 12),   # Middle
    (0, 13), (13, 14), (14, 15), (15, 16), # Ring
    (0, 17), (17, 18), (18, 19), (19, 20), # Pinky
    (5, 9), (9, 13), (13, 17)              # Palm connections
]

def to_pixel(x_norm: float, y_norm: float, w: int, h: int) -> tuple[int, int]:
    """Convert normalized landmark to pixel coordinates"""
    x = min(max(x_norm, 0.0), 1.0)
    y = min(max(y_norm, 0.0), 1.0)
    return int(x * w), int(y * h)

class HandDetector:
    def __init__(self, model_path="hand_landmarker.task", num_hands=2, min_detection_confidence=0.5):
        # Ensure the task file exists
        import os
        if not os.path.exists(model_path):
            raise FileNotFoundError(f"Task file not found at {model_path}")

        # Create the hand landmarker
        options = vision.HandLandmarkerOptions(
            base_options=python.BaseOptions(model_asset_path=model_path),  # <-- use the argument!
            num_hands=num_hands,
            min_hand_detection_confidence=min_detection_confidence,
            running_mode=vision.RunningMode.IMAGE  # IMAGE mode, no callback needed
        )

        self.landmarker = vision.HandLandmarker.create_from_options(options)
        self.results = None
        self.finger_tip_ids = [4, 8, 12, 16, 20]  # Thumb, Index, Middle, Ring, Pinky
        self.lmlist = []


    def findHands(self, img, draw=True):
        """Detect hands and optionally draw landmarks on the image"""
        h, w, _ = img.shape
        rgb_image = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
        mp_image = mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb_image)

        self.results = self.landmarker.detect(mp_image)
        self.lmlist = []  # <-- clear previous list

        if self.results.hand_landmarks:
            for hand_landmarks in self.results.hand_landmarks:
                pts = [to_pixel(lm.x, lm.y, w, h) for lm in hand_landmarks]
                if draw:
                    for a, b in HAND_CONNECTIONS:
                        cv2.line(img, pts[a], pts[b], (0, 255, 0), 2)
                    for (x, y) in pts:
                        cv2.circle(img, (x, y), 3, (0, 0, 255), -1)
                self.lmlist.append(pts)  # <-- save landmarks for finger tracking

        return img

    def findPosition(self, img, handNo=0, draw=False):
        """Return list of landmarks of the first detected hand"""
        if len(self.lmlist) > 0:
            return self.lmlist[handNo]
        else:
            return []

    # def fingersUp(self):
    #     """Return which fingers are up (1) or down (0)"""
    #     fingers = []
    #     if len(self.lmlist) == 0:
    #         return [0, 0, 0, 0, 0]

    #     # Thumb (check x relative to previous point)
    #     if self.lmlist[self.finger_tip_ids[0]][1] < self.lmlist[self.finger_tip_ids[0] - 1][1]:
    #         fingers.append(1)
    #     else:
    #         fingers.append(0)

    #     # Other 4 fingers (check y)
    #     for id in range(1, 5):
    #         if self.lmlist[self.finger_tip_ids[id]][2] < self.lmlist[self.finger_tip_ids[id] - 2][2]:
    #             fingers.append(1)
    #         else:
    #             fingers.append(0)
    #     return fingers

    # fingersUp

    def fingersUp(self):
        fingers = []
        # Check if at least one hand was detected
        if len(self.lmlist) != 0:
            # Get the landmarks for the FIRST hand detected
            myHandLms = self.lmlist[0]

            # Thumb logic - Use myHandLms instead of self.lmlist
            if myHandLms[self.finger_tip_ids[0]][0] < myHandLms[self.finger_tip_ids[0] - 1][0]:
                fingers.append(1)
            else:
                fingers.append(0)

            # 4 Fingers logic
            for id in range(1, 5):
                if myHandLms[self.finger_tip_ids[id]][1] < myHandLms[self.finger_tip_ids[id] - 2][1]:
                    fingers.append(1)
                else:
                    fingers.append(0)
        else:
            fingers = [0, 0, 0, 0, 0]

        return fingers
    fingersUp
