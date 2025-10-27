# main.py
from flask import Flask, request, jsonify, render_template, Response
from threading import Thread, Lock
from robot import movement
from robot.camera import StreamingOutput
from config import WINDOWS_SERVER, CAMERA_RES, CAMERA_FPS, DETECTION_FRAME_SKIP, DETECTION_TIMEOUT
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
            camera = picamera.PiCamera(resolution=CAMERA_RES, framerate=CAMERA_FPS)
            output = StreamingOutput(
                face_server_url=WINDOWS_SERVER,
                frame_skip=DETECTION_FRAME_SKIP,
                timeout=DETECTION_TIMEOUT
            )
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

@app.route("/take_picture", methods=["POST"])
def take_picture():
    """Capture a high-res photo and return it as base64."""
    from robot.camera import take_picture as capture_photo
    try:
        filename = capture_photo()
        # Read the image and encode as base64
        import base64
        with open(filename, 'rb') as f:
            img_data = base64.b64encode(f.read()).decode('utf-8')
        return jsonify({
            "status": "Picture taken",
            "image": f"data:image/jpeg;base64,{img_data}",
            "filename": filename
        })
    except Exception as e:
        return jsonify({"status": "Error", "error": str(e)}), 500

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