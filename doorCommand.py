import easygopigo3
from time import sleep
from picamera import PiCamera
import os

# Instantiate robot
gpg = easygopigo3.EasyGoPiGo3()
# Initialize camera once (headless safe)
camera = PiCamera()
camera.resolution = (640, 480)
sleep(2)  # allow camera to warm up

def move_forward(distance_m: float, blocking: bool = True):
    cm = distance_m * 100
    gpg.drive_cm(cm, blocking=blocking)

def move_backward(distance_m: float, blocking: bool = True):
    cm = distance_m * 100
    gpg.drive_cm(-cm, blocking=blocking)

def turn_right(angle_deg: float, blocking: bool = True):
    gpg.turn_degrees(angle_deg, blocking=blocking)

def turn_left(angle_deg: float, blocking: bool = True):
    gpg.turn_degrees(-angle_deg, blocking=blocking)

def set_speed_dps(dps: int):
    gpg.set_speed(dps)

def take_picture(filename="door_picture.jpg"):
    print("Taking picture...")
    # Capture directly (no preview needed)
    camera.capture(filename)
    print(f"Picture saved as {filename}")
    # Speak "Pic" through Kano speaker
    os.system('espeak "Pic" --stdout | aplay -D plughw:1,0 2>/dev/null')

# GO to door
def go_to_door():
    # Move forward 5.5 meters
    move_forward(5.5)
    # Turn left 90 degrees
    turn_left(90)
    # Move forward 1 meter
    move_forward(1)
    # Stop and take picture
    gpg.stop()
    #take_picture()
    # Return to starting point
    move_backward(1)
    turn_right(90)
    move_backward(5.5)
    gpg.stop()

# Example usage
if __name__ == "__main__":
    # set_speed_dps(700)
    go_to_door()
    # cleanup
    camera.close()
