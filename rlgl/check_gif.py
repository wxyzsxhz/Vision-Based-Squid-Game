import imageio
import cv2

gif_path = "character_assets/FourPlayers.gif"  # change if needed

# Load GIF frames
frames = imageio.mimread(gif_path)

print("Total Frames:", len(frames))

if len(frames) > 0:
    frame = frames[0]
    print("Frame Shape (H, W, C):", frame.shape)

    height, width = frame.shape[0], frame.shape[1]
    channels = frame.shape[2] if len(frame.shape) == 3 else 1

    print("Width:", width)
    print("Height:", height)
    print("Channels:", channels)

    if channels == 4:
        print("→ GIF has transparency (alpha channel)")
    else:
        print("→ GIF has no transparency")
else:
    print("No frames found.")
