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
auto_greet_active = False  # Global flag for auto-greet mode

def get_camera():
    """Get or initialize the single camera instance."""
    global camera, output, raw_output
    with camera_lock:
        if camera is None:
            camera = picamera.PiCamera(resolution=CAMERA_RES, framerate=CAMERA_FPS)
            # Output with face detection (only when requested)
            output = StreamingOutput(
                face_server_url=WINDOWS_SERVER,
                frame_skip=DETECTION_FRAME_SKIP,
                timeout=DETECTION_TIMEOUT
            )
            # Raw output without face detection for main page
            raw_output = StreamingOutput(face_server_url=None)
            # Start ONLY raw output by default (no detection)
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

@app.route("/distance", methods=["GET"])
def get_distance():
    """Get current distance sensor reading"""
    from robot.movement import get_obstacle_distance
    distance = get_obstacle_distance()
    return jsonify({
        "distance_cm": distance,
        "obstacle_detected": distance is not None and distance < 30
    })

@app.route("/greet_person", methods=["POST"])
def greet_person():
    """
    Greeting behavior: Move forward 5 steps when person detected,
    say greeting, then move back 5 steps.
    """
    from robot.audio import play_audio_message
    import time
    
    def greeting_sequence():
        try:
            # Move forward 5 steps
            print("Person detected! Moving forward...")
            for step in range(5):
                movement.move_forward(distance_m=0.1, blocking=True, check_obstacles=False)
                time.sleep(0.2)
            
            # Stop and greet
            movement.stop_robot()
            time.sleep(0.5)
            
            print("Playing greeting message...")
            play_audio_message("Hello Stranger, Welcome to IX Lab", voice="en-us+f3")
            
            time.sleep(1)
            
            # Move backward 5 steps
            print("Moving back to original position...")
            for step in range(5):
                movement.move_backward(distance_m=0.1, blocking=True)
                time.sleep(0.2)
            
            movement.stop_robot()
            print("Greeting sequence completed!")
            
        except Exception as e:
            print(f"Error in greeting sequence: {e}")
            movement.stop_robot()
    
    # Run in background thread
    Thread(target=greeting_sequence).start()
    
    return jsonify({
        "status": "Greeting sequence started",
        "message": "Robot will move forward, greet, and return"
    })


@app.route("/auto_greet/start", methods=["POST"])
def start_auto_greet():
    """
    Start automatic greeting mode: continuously monitor for people
    and trigger greeting sequence when detected.
    """
    from robot.autonomous import capture_frame_from_camera
    import requests
    from config import WINDOWS_SERVER_BASE
    import time
    
    global auto_greet_active
    auto_greet_active = True
    
    def auto_greet_loop():
        global auto_greet_active
        print("Starting auto-greet monitoring...")
        last_greet_time = 0
        cooldown_period = 30  # 30 seconds between greetings
        
        try:
            cam, _, _ = get_camera()
            
            while auto_greet_active:
                try:
                    # Capture frame
                    frame_bytes = capture_frame_from_camera(cam)
                    
                    # Check for person via Windows server
                    files = {'image': ('frame.jpg', frame_bytes, 'image/jpeg')}
                    response = requests.post(
                        f"{WINDOWS_SERVER_BASE}/detect/check_person",
                        files=files,
                        timeout=5
                    )
                    
                    if response.status_code == 200:
                        result = response.json()
                        person_detected = result.get("person_detected", False)
                        
                        if person_detected:
                            current_time = time.time()
                            if current_time - last_greet_time >= cooldown_period:
                                print(f"Person detected! Triggering greeting...")
                                # Trigger greeting sequence
                                greeting_sequence()
                                last_greet_time = current_time
                            else:
                                print("Person detected but in cooldown period")
                    
                    time.sleep(2)  # Check every 2 seconds
                    
                except Exception as e:
                    print(f"Error in auto-greet loop: {e}")
                    time.sleep(2)
                    
        except Exception as e:
            print(f"Fatal error in auto-greet: {e}")
        finally:
            auto_greet_active = False
            print("Auto-greet monitoring stopped")
    
    def greeting_sequence():
        """Internal greeting sequence for auto-greet"""
        from robot.audio import play_audio_message
        import time
        
        try:
            # Move forward 5 steps
            print("Moving forward...")
            for step in range(5):
                movement.move_forward(distance_m=0.1, blocking=True, check_obstacles=False)
                time.sleep(0.2)
            
            movement.stop_robot()
            time.sleep(0.5)
            
            # Greet
            print("Playing greeting...")
            play_audio_message("Hello Stranger, Welcome to IX Lab", voice="en-us+f3")
            time.sleep(1)
            
            # Move backward 5 steps
            print("Moving back...")
            for step in range(5):
                movement.move_backward(distance_m=0.1, blocking=True)
                time.sleep(0.2)
            
            movement.stop_robot()
            print("Greeting completed!")
            
        except Exception as e:
            print(f"Error in greeting sequence: {e}")
            movement.stop_robot()
    
    # Start monitoring in background
    Thread(target=auto_greet_loop, daemon=True).start()
    
    return jsonify({
        "status": "Auto-greet mode started",
        "message": "Monitoring for people to greet"
    })


@app.route("/auto_greet/stop", methods=["POST"])
def stop_auto_greet():
    """Stop automatic greeting mode."""
    global auto_greet_active
    auto_greet_active = False
    
    return jsonify({
        "status": "Auto-greet mode stopped"
    })


@app.route("/auto_greet/status", methods=["GET"])
def auto_greet_status():
    """Get auto-greet mode status."""
    global auto_greet_active
    
    return jsonify({
        "active": auto_greet_active,
        "message": "Auto-greet is active" if auto_greet_active else "Auto-greet is inactive"
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
    """Video streaming route with face detection."""
    cam, stream_output, _ = get_camera()
    
    # Start face detection recording if not already started on port 1
    with camera_lock:
        # Check if detection recording is already running
        # We can't directly check the port, so use a flag or try-except
        try:
            # Try to start detection recording on splitter port 1
            cam.start_recording(stream_output, format='mjpeg', splitter_port=1)
        except picamera.exc.PiCameraAlreadyRecording:
            # Already recording on port 1, which is fine
            pass
        except Exception as e:
            # Log other errors but continue
            print(f"Detection recording start error: {e}")
    
    def generate():
        while True:
            with stream_output.condition:
                stream_output.condition.wait()
                frame = stream_output.frame
            yield (b"--FRAME\r\n"
                   b"Content-Type: image/jpeg\r\n\r\n" + frame + b"\r\n")
    
    return Response(generate(), mimetype='multipart/x-mixed-replace; boundary=FRAME')