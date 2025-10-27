# main.py
from flask import Flask, request, jsonify, render_template, Response
from threading import Thread, Lock
from robot import movement
from robot.camera import StreamingOutput
from config import WINDOWS_SERVER, CAMERA_RES
import picamera

app = Flask(__name__)

# -----------------
# Single Camera Instance (Singleton Pattern)
# -----------------
camera_lock = Lock()
camera = None
output = None

def get_camera():
    """Get or initialize the single camera instance."""
    global camera, output
    with camera_lock:
        if camera is None:
            camera = picamera.PiCamera(resolution=CAMERA_RES, framerate=15)
            output = StreamingOutput(face_server_url=WINDOWS_SERVER)
            camera.start_recording(output, format='mjpeg')
        return camera, output

# -----------------
# Robot API
# -----------------
@app.route("/move", methods=["POST"])
def move():
    data = request.get_json()
    direction = data.get("direction")
    
    if direction == "forward":
        movement.move_forward()
    elif direction == "backward":
        movement.move_backward()
    elif direction == "left":
        movement.turn_left()
    elif direction == "right":
        movement.turn_right()
    elif direction == "stop":
        movement.stop_robot()
    
    return jsonify({"status": f"{direction} command executed"})

@app.route("/go_to_door", methods=["POST"])
def go_door():
    Thread(target=movement.go_to_door).start()
    return jsonify({"status": "Moving to door..."})

@app.route("/return_to_start", methods=["POST"])
def return_start():
    Thread(target=movement.return_to_start).start()
    return jsonify({"status": "Returning to start..."})

# -----------------
# Pages
# -----------------
@app.route("/")
def index():
    return render_template("index.html")

@app.route("/camera")
def camera_page():
    return render_template("camera.html")

# -----------------
# MJPEG streaming
# -----------------
@app.route("/video_feed")
def video_feed():
    """Video streaming route."""
    _, stream_output = get_camera()
    
    def generate():
        while True:
            with stream_output.condition:
                stream_output.condition.wait()
                frame = stream_output.frame
            yield (b"--FRAME\r\n"
                   b"Content-Type: image/jpeg\r\n\r\n" + frame + b"\r\n")
    
    return Response(generate(), mimetype='multipart/x-mixed-replace; boundary=FRAME')