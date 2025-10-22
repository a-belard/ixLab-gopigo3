# monitor.py
# Flask server to control GoPiGo3 robot for manual and automatic movement

import os
import signal
import sys
from time import sleep
from threading import Thread, Event
from flask import Flask, jsonify, render_template, request
from easygopigo3 import EasyGoPiGo3
from picamera import PiCamera

# -----------------------------
# Initialization
# -----------------------------
app = Flask(__name__, template_folder='templates', static_folder='static')
shutdown_event = Event()

try:
    gpg = EasyGoPiGo3()
except Exception as e:
    print(f"Error initializing GoPiGo3: {e}")
    sys.exit(1)

camera = PiCamera()
camera.resolution = (640, 480)
sleep(2)  # allow warm-up

# -----------------------------
# Robot Command Functions
# -----------------------------
def move_forward(distance_m=0.1, blocking=False):
    print("Moving forward")
    gpg.drive_cm(distance_m * 100, blocking=blocking)

def move_backward(distance_m=0.1, blocking=False):
    print("Moving backward")
    gpg.drive_cm(-distance_m * 100, blocking=blocking)

def turn_right(angle_deg=10, blocking=False):
    print("Turning right")
    gpg.turn_degrees(angle_deg, blocking=blocking)

def turn_left(angle_deg=10, blocking=False):
    print("Turning left")
    gpg.turn_degrees(-angle_deg, blocking=blocking)

def stop_robot():
    print("Stopping robot")
    gpg.stop()

def take_picture(filename="door_picture.jpg"):
    """Takes a photo and plays a short sound confirmation."""
    print("Taking picture...")
    camera.capture(filename)
    print(f"Saved {filename}")
    os.system('espeak "Picture taken" --stdout | aplay -D plughw:1,0 2>/dev/null')
    return filename

def go_to_door():
    """Sequence to move to door and take a picture."""
    print("Driving to door...")
    # gpg.set_speed(700)  # commented
    move_forward(5.5)
    turn_left(90)
    move_forward(1)
    gpg.stop()
    take_picture()
    print("At door.")

def return_to_start():
    """Return the robot to its starting point."""
    print("Returning to start...")
    move_backward(1)
    turn_right(90)
    move_backward(5.5)
    gpg.stop()
    print("Returned to start.")

# -----------------------------
# Flask Routes
# -----------------------------
@app.route("/")
def index():
    return render_template("index.html")

@app.route("/move", methods=["POST"])
def move():
    data = request.get_json()
    direction = data.get("direction")

    if direction == "forward":
        move_forward()
    elif direction == "backward":
        move_backward()
    elif direction == "left":
        turn_left()
    elif direction == "right":
        turn_right()
    elif direction == "stop":
        stop_robot()

    return jsonify({"status": f"{direction} command executed"})

@app.route("/go_to_door", methods=["POST"])
def handle_go_to_door():
    t = Thread(target=go_to_door)
    t.start()
    return jsonify({"status": "Moving to door..."})

@app.route("/return_to_start", methods=["POST"])
def handle_return_to_start():
    t = Thread(target=return_to_start)
    t.start()
    return jsonify({"status": "Returning to start..."})

@app.route("/take_picture", methods=["POST"])
def handle_take_picture():
    filename = take_picture()
    return jsonify({"status": f"Picture taken: {filename}"})

# -----------------------------
# Graceful Shutdown
# -----------------------------
def signal_handler(sig, frame):
    print("Shutting down...")
    shutdown_event.set()

# -----------------------------
# Main Entry
# -----------------------------
if __name__ == "__main__":
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    print("Starting Flask server on port 5000...")
    web_thread = Thread(target=lambda: app.run(host="0.0.0.0", port=5000, debug=False, use_reloader=False))
    web_thread.start()

    while not shutdown_event.is_set():
        sleep(0.5)

    print("Stopping camera and cleaning up...")
    camera.close()
    gpg.stop()
    sys.exit(0)
