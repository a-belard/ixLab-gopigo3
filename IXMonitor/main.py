# main.py
from flask import Flask, request, jsonify, render_template, Response
from threading import Thread, Lock
from robot import movement
from robot.camera import StreamingOutput
from robot import autonomous
from config import WINDOWS_SERVER, CAMERA_RES, CAMERA_FPS, DETECTION_FRAME_SKIP, DETECTION_TIMEOUT
import picamera

app = Flask(__name__)

# -----------------
# Single Camera Instance (Singleton Pattern)
# -----------------
camera_lock = Lock()
camera = None
output = None
raw_output = None

def get_camera():
    """Get or initialize the single camera instance."""
    global camera, output, raw_output
    with camera_lock:
        if camera is None:
            camera = picamera.PiCamera(resolution=CAMERA_RES, framerate=CAMERA_FPS)
            # Output with face detection for /camera page
            output = StreamingOutput(
                face_server_url=WINDOWS_SERVER,
                frame_skip=DETECTION_FRAME_SKIP,
                timeout=DETECTION_TIMEOUT
            )
            # Raw output without face detection for main page
            raw_output = StreamingOutput(face_server_url=None)
            camera.start_recording(output, format='mjpeg', splitter_port=1)
            camera.start_recording(raw_output, format='mjpeg', splitter_port=2)
        return camera, output, raw_output

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
        # Get the existing camera instance
        cam, _, _ = get_camera()
        filename = capture_photo(cam)
        
        if filename is None:
            return jsonify({"status": "Error", "error": "Failed to capture image"}), 500
        
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

@app.route("/battery", methods=["GET"])
def get_battery():
    """Get the current battery voltage and percentage."""
    try:
        voltage = movement.gpg.get_voltage_battery()
        # GoPiGo3 battery range: ~7V (empty) to ~12V (full)
        # Calculate percentage based on typical Li-ion range
        min_voltage = 7.0
        max_voltage = 12.0
        percentage = max(0, min(100, ((voltage - min_voltage) / (max_voltage - min_voltage)) * 100))
        
        return jsonify({
            "voltage": round(voltage, 2),
            "percentage": round(percentage, 1)
        })
    except Exception as e:
        return jsonify({"voltage": 0, "percentage": 0, "error": str(e)}), 500

# -----------------
# Chat/Audio API
# -----------------
@app.route("/chat/text", methods=["POST"])
def chat_text():
    """Send text message to AI server and get response."""
    from robot.audio import send_text_to_server, play_audio_message
    
    data = request.get_json()
    text = data.get("text", "").strip()
    speak = data.get("speak", True)
    
    if not text:
        return jsonify({"success": False, "error": "Text cannot be empty"}), 400
    
    try:
        # Send to server
        result = send_text_to_server(text)
        
        if result["success"] and speak:
            # Play the response
            ai_response = result.get("ai_response", "")
            Thread(target=play_audio_message, args=(ai_response,)).start()
        
        return jsonify(result)
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500

@app.route("/chat/record", methods=["POST"])
def chat_record():
    """Receive audio from client browser, send to server, and play response."""
    from robot.audio import send_audio_to_server, play_audio_message
    import os
    import tempfile
    
    # Check if audio file is in the request
    if 'audio' not in request.files:
        return jsonify({"success": False, "error": "No audio file received"}), 400
    
    audio_file = request.files['audio']
    
    if audio_file.filename == '':
        return jsonify({"success": False, "error": "Empty audio file"}), 400
    
    # Save audio to temporary file
    temp_file = tempfile.NamedTemporaryFile(delete=False, suffix='.wav')
    temp_path = temp_file.name
    temp_file.close()
    
    try:
        audio_file.save(temp_path)
        
        # Send to Windows server
        result = send_audio_to_server(temp_path)
        
        # Clean up temp file
        if os.path.exists(temp_path):
            os.remove(temp_path)
        
        # Play the AI response on robot speaker
        if result["success"]:
            ai_response = result.get("ai_response", "")
            Thread(target=play_audio_message, args=(ai_response,)).start()
        
        return jsonify(result)
    except Exception as e:
        # Clean up temp file on error
        if os.path.exists(temp_path):
            os.remove(temp_path)
        return jsonify({"success": False, "error": str(e)}), 500

@app.route("/chat/reset", methods=["POST"])
def chat_reset():
    """Reset conversation history."""
    from robot.audio import reset_conversation
    result = reset_conversation()
    return jsonify(result)

# -----------------
# Autonomous Navigation API
# -----------------
@app.route("/autonomous/start", methods=["POST"])
def start_autonomous():
    """Start vision-guided autonomous navigation"""
    data = request.get_json()
    goal = data.get("goal", "Explore the environment")
    max_actions = data.get("max_actions", 20)
    
    # Get camera instance
    cam, _, _ = get_camera()
    
    # Start autonomous mode
    result = autonomous.start_autonomous_mode(cam, goal, max_actions)
    return jsonify(result)

@app.route("/autonomous/stop", methods=["POST"])
def stop_autonomous():
    """Stop autonomous navigation"""
    result = autonomous.stop_autonomous_mode()
    return jsonify(result)

@app.route("/autonomous/status", methods=["GET"])
def autonomous_status():
    """Get autonomous mode status"""
    is_active = autonomous.is_autonomous_active()
    return jsonify({
        "active": is_active,
        "message": "Autonomous mode is active" if is_active else "Autonomous mode is inactive"
    })

# -----------------
# Vision Analysis API
# -----------------
@app.route("/vision/analyze", methods=["POST"])
def vision_analyze():
    """Analyze current camera view"""
    from robot.autonomous import capture_frame_from_camera
    import requests
    from config import WINDOWS_SERVER_BASE
    
    data = request.get_json() or {}
    prompt = data.get("prompt", "Describe what you see in detail")
    
    try:
        # Get camera and capture frame
        cam, _, _ = get_camera()
        frame_bytes = capture_frame_from_camera(cam)
        
        # Send to Windows server for analysis
        files = {'image': ('frame.jpg', frame_bytes, 'image/jpeg')}
        form_data = {'prompt': prompt}
        
        response = requests.post(
            f"{WINDOWS_SERVER_BASE}/vision/analyze",
            files=files,
            data=form_data,
            timeout=15
        )
        response.raise_for_status()
        
        return jsonify(response.json())
        
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500

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
    """Raw video streaming route (no face detection) for main page."""
    _, _, raw_stream = get_camera()
    
    def generate():
        while True:
            with raw_stream.condition:
                raw_stream.condition.wait()
                frame = raw_stream.frame
            yield (b"--FRAME\r\n"
                   b"Content-Type: image/jpeg\r\n\r\n" + frame + b"\r\n")
    
    return Response(generate(), mimetype='multipart/x-mixed-replace; boundary=FRAME')

@app.route("/video_feed_detection")
def video_feed_detection():
    """Video streaming route with face detection for /camera page."""
    _, stream_output, _ = get_camera()
    
    def generate():
        while True:
            with stream_output.condition:
                stream_output.condition.wait()
                frame = stream_output.frame
            yield (b"--FRAME\r\n"
                   b"Content-Type: image/jpeg\r\n\r\n" + frame + b"\r\n")
    
    return Response(generate(), mimetype='multipart/x-mixed-replace; boundary=FRAME')