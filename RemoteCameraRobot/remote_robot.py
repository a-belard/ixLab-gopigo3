# Dexter Industries GoPiGo3 Remote Camera robot with Optimized Person Detection
# Run with: python3 flask_server.py

import signal
import sys
import logging
from time import sleep

# check if it's ran with Python3
assert sys.version_info[0:1] == (3,)

from flask import Flask, jsonify, render_template, request, Response, send_from_directory, url_for
from werkzeug.serving import make_server
from gopigo3 import FirmwareVersionError
from easygopigo3 import EasyGoPiGo3

import io
import picamera
import socketserver
from threading import Condition, Thread, Event, Lock
from http import server
import cv2
import numpy as np
import tflite_runtime.interpreter as tflite

logging.basicConfig(level=logging.DEBUG)

# -----------------------------
# Globals
# -----------------------------
keyboard_trigger = Event()
frame_lock = Lock()  # protects access to latest_frame
latest_frame = None  # annotated frame for streaming
DETECTION_INTERVAL = 5  # detect every N frames

def signal_handler(signal, frame):
    logging.info('Signal detected. Stopping threads.')
    keyboard_trigger.set()

# -----------------------------
# Robot Initialization
# -----------------------------
MAX_FORCE = 5.0
MIN_SPEED = 100
MAX_SPEED = 300
try:
    gopigo3_robot = EasyGoPiGo3()
except IOError:
    logging.critical('GoPiGo3 is not detected.')
    sys.exit(1)
except FirmwareVersionError:
    logging.critical('GoPiGo3 firmware needs to be updated')
    sys.exit(2)
except Exception:
    logging.critical("Unexpected error when initializing GoPiGo3 object")
    sys.exit(3)

# -----------------------------
# Flask Web Server
# -----------------------------
HOST = "0.0.0.0"
WEB_PORT = 5000
app = Flask(__name__, static_url_path='')

class WebServerThread(Thread):
    def __init__(self, app, host, port):
        Thread.__init__(self)
        self.srv = make_server(host, port, app)
        self.ctx = app.app_context()
        self.ctx.push()

    def run(self):
        logging.info('Starting Flask server')
        self.srv.serve_forever()

    def shutdown(self):
        logging.info('Stopping Flask server')
        self.srv.shutdown()

@app.route("/robot", methods=["POST"])
def robot_commands():
    args = request.args
    state = args['state']
    angle_degrees = int(float(args['angle_degrees']))
    angle_dir = args['angle_dir']
    force = float(args['force'])
    determined_speed = MIN_SPEED + force * (MAX_SPEED - MIN_SPEED) / MAX_FORCE
    if determined_speed > MAX_SPEED:
        determined_speed = MAX_SPEED

    if state == 'move':
        if angle_degrees >= 260 and angle_degrees <= 280:
            gopigo3_robot.set_speed(determined_speed)
            gopigo3_robot.backward()
        elif angle_degrees > 90 and angle_degrees < 260:
            gopigo3_robot.set_motor_dps(gopigo3_robot.MOTOR_RIGHT, determined_speed)
            left_motor_percentage = abs((angle_degrees - 170) / 90)
            sign = -1 if angle_degrees >= 180 else 1
            gopigo3_robot.set_motor_dps(gopigo3_robot.MOTOR_LEFT, determined_speed * left_motor_percentage * sign)
        elif angle_degrees < 90 and angle_degrees >= 0:
            gopigo3_robot.set_motor_dps(gopigo3_robot.MOTOR_LEFT, determined_speed)
            right_motor_percentage = angle_degrees / 90
            gopigo3_robot.set_motor_dps(gopigo3_robot.MOTOR_RIGHT, determined_speed * right_motor_percentage)
        elif angle_degrees <= 360 and angle_degrees > 280:
            gopigo3_robot.set_motor_dps(gopigo3_robot.MOTOR_LEFT, determined_speed)
            right_motor_percentage = (angle_degrees - 280) / 80 - 1
            gopigo3_robot.set_motor_dps(gopigo3_robot.MOTOR_RIGHT, determined_speed * right_motor_percentage)
    elif state == 'stop':
        gopigo3_robot.stop()
    else:
        app.logging.warning('unknown state sent')

    resp = Response()
    resp.mimetype = "application/json"
    resp.status = "OK"
    resp.status_code = 200
    return resp

@app.route("/")
def index():
    return page("index.html")

@app.route("/<string:page_name>")
def page(page_name):
    return render_template("{}".format(page_name))

@app.route("/static/<path:path>")
def send_static(path):
    return send_from_directory('/home/pi/Dexter/GoPiGo3/Projects/RemoteCameraRobot/static', path)

# -----------------------------
# TFLite Person Detection Setup
# -----------------------------
MODEL_PATH = "/home/pi/detect.tflite"  # download here
LABELS_PATH = "/home/pi/labelmap.txt"

with open(LABELS_PATH, 'r') as f:
    labels = [line.strip() for line in f.readlines()]

interpreter = tflite.Interpreter(model_path=MODEL_PATH)
interpreter.allocate_tensors()
input_details = interpreter.get_input_details()
output_details = interpreter.get_output_details()

# -----------------------------
# Detection function
# -----------------------------
def detect_person(frame):
    h, w, _ = frame.shape
    input_shape = input_details[0]['shape']
    input_tensor = cv2.resize(frame, (input_shape[2], input_shape[1]))
    input_tensor = np.expand_dims(input_tensor, axis=0)
    input_tensor = np.uint8(input_tensor)

    interpreter.set_tensor(input_details[0]['index'], input_tensor)
    interpreter.invoke()

    boxes = interpreter.get_tensor(output_details[0]['index'])[0]
    classes = interpreter.get_tensor(output_details[1]['index'])[0]
    scores = interpreter.get_tensor(output_details[2]['index'])[0]

    for i in range(len(scores)):
        if scores[i] > 0.5 and int(classes[i]) == 0:
            ymin, xmin, ymax, xmax = boxes[i]
            left, top, right, bottom = int(xmin*w), int(ymin*h), int(xmax*w), int(ymax*h)
            cv2.rectangle(frame, (left, top), (right, bottom), (0, 255, 0), 2)
            cv2.putText(frame, f"Person {int(scores[i]*100)}%", (left, top-10),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0,255,0), 1)
    return frame

# -----------------------------
# Streaming Output Class
# -----------------------------
class StreamingOutput(object):
    def __init__(self):
        self.frame = None
        self.buffer = io.BytesIO()
        self.condition = Condition()
        self.frame_count = 0

    def write(self, buf):
        if buf.startswith(b'\xff\xd8'):
            self.buffer.truncate()
            with self.condition:
                frame_data = np.frombuffer(self.buffer.getvalue(), dtype=np.uint8)
                img = cv2.imdecode(frame_data, cv2.IMREAD_COLOR)

                self.frame_count += 1
                if self.frame_count % DETECTION_INTERVAL == 0 and img is not None:
                    annotated = detect_person(img)
                    with frame_lock:
                        global latest_frame
                        latest_frame = annotated
                else:
                    with frame_lock:
                        if latest_frame is not None:
                            annotated = latest_frame
                        else:
                            annotated = img

                _, jpeg = cv2.imencode('.jpg', annotated)
                self.frame = jpeg.tobytes()
                self.condition.notify_all()
            self.buffer.seek(0)
        return self.buffer.write(buf)

# -----------------------------
# Streaming Server
# -----------------------------
class StreamingHandler(server.BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path == '/stream.mjpg':
            self.send_response(200)
            self.send_header('Age', 0)
            self.send_header('Cache-Control', 'no-cache, private')
            self.send_header('Pragma', 'no-cache')
            self.send_header('Content-Type', 'multipart/x-mixed-replace; boundary=FRAME')
            self.end_headers()
            try:
                while True:
                    with output.condition:
                        output.condition.wait()
                        frame = output.frame
                    self.wfile.write(b'--FRAME\r\n')
                    self.send_header('Content-Type', 'image/jpeg')
                    self.send_header('Content-Length', len(frame))
                    self.end_headers()
                    self.wfile.write(frame)
                    self.wfile.write(b'\r\n')
            except Exception as e:
                logging.warning('Removed streaming client %s: %s', self.client_address, str(e))
        else:
            self.send_error(404)
            self.end_headers()

class StreamingServer(socketserver.ThreadingMixIn, server.HTTPServer):
    allow_reuse_address = True
    daemon_threads = True

# -----------------------------
# Main
# -----------------------------
if __name__ == "__main__":
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    camera = picamera.PiCamera(resolution='320x240', framerate=15)
    output = StreamingOutput()
    camera.start_recording(output, format='mjpeg')
    logging.info("Started recording with picamera")

    STREAM_PORT = 5001
    stream = StreamingServer((HOST, STREAM_PORT), StreamingHandler)
    streamserver = Thread(target=stream.serve_forever)
    streamserver.start()
    logging.info("Started stream server for picamera")

    webserver = WebServerThread(app, HOST, WEB_PORT)
    webserver.start()
    logging.info("Started Flask web server")

    while not keyboard_trigger.is_set():
        sleep(0.5)

    logging.info("Keyboard event detected")
    webserver.shutdown()
    camera.stop_recording()
    stream.shutdown()
    webserver.join()
    streamserver.join()
    logging.info("Stopped all threads")
    sys.exit(0)
