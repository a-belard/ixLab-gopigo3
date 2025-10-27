# Config variables
WINDOWS_SERVER = "http://172.20.86.247:8000/detect"
ROBOT_STEP = 0.1          # meters per step
TURN_ANGLE = 10           # degrees per step
CAMERA_RES = (320, 240)
CAMERA_FPS = 10           # frames per second for camera
DETECTION_FRAME_SKIP = 2  # send every Nth frame to face detection (10fps / 2 = 5fps)
DETECTION_TIMEOUT = 0.5   # timeout for face detection server (seconds)
