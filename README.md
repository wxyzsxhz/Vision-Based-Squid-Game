# 🎮 Vision-Based Squid Game

An interactive **computer vision-based gaming system** inspired by the popular series *Squid Game*.
This project allows players to control and interact with games using **real-time body movement and hand gestures** through a webcam.

---

## 📌 Overview

This system recreates two iconic Squid Game challenges:

* 🚦 **Red Light, Green Light**
* 🍬 **Dalgona Cookie Cutter Game**

Using computer vision techniques, the system detects **motion and hand gestures** to enable natural human–computer interaction without traditional input devices.

---

## ✨ Features

* 🎥 Real-time webcam-based interaction
* 🧍 Motion detection for gameplay control
* ✋ Hand gesture recognition using landmark tracking
* 🍬 Shape tracing system for Dalgona game
* 🎮 Physics-based character movement
* 💥 Collision detection with obstacles
* 🔊 Sound effects and background music
* 🖥️ User-friendly GUI with multiple screens

---

## 🧠 Game Modes

### 🚦 Red Light, Green Light

* Player movement is controlled using gestures
* Movement allowed during **Green Light**
* Movement during **Red Light** → ❌ Eliminated
* Reach finish line within **60 seconds** to win

---

### 🍬 Dalgona Cookie Cutter Game

* Trace shapes like **circle, triangle, star, umbrella**
* Controlled using **index finger tracking**
* Stay within boundary while tracing
* Exceed boundary → ❌ Game Over
* Complete within **30 seconds** to win

---

## ⚙️ Technologies Used

* **Python**
* **OpenCV** – image processing & motion detection
* **MediaPipe** – hand landmark detection & gesture recognition
* **NumPy** – numerical operations
* **Pygame** – sound and animation
* **CustomTkinter** – graphical user interface

---

## 🚀 Installation

### 1. Clone the repository

```bash
git clone https://github.com/wxyzsxhz/vision-based-squid-game.git
```

### 2. Install dependencies

```bash
pip install -r requirements.txt
```

### 3. Run the project

```bash
python main.py
```

---

## ▶️ Usage

1. Open the application
2. Select a game mode
3. Allow webcam access
4. Play using gestures and movement

---

## 📄 License

This project is for academic purposes.
MIT License can be applied if published publicly.

---
