import cv2, requests, numpy as np
from picamera2 import Picamera2
from config import WINDOWS_SERVER, CAMERA_RES

picam2 = Picamera2()
picam2.configure(picam2.create_preview_configuration(main={"size": CAMERA_RES}))
picam2.start()

def gen_frames_remote():
    """Yield MJPEG frames processed by Windows face detection server."""
    while True:
        frame = picam2.capture_array()
        _, buffer = cv2.imencode('.jpg', frame)
        files = {'file': ('frame.jpg', buffer.tobytes(), 'image/jpeg')}
        try:
            resp = requests.post(WINDOWS_SERVER, files=files, timeout=1.5)
            img_array = np.frombuffer(resp.content, np.uint8)
            annotated = cv2.imdecode(img_array, cv2.IMREAD_COLOR)
        except:
            annotated = frame  # fallback

        _, jpeg = cv2.imencode('.jpg', annotated)
        yield (b'--frame\r\n'
               b'Content-Type: image/jpeg\r\n\r\n' + jpeg.tobytes() + b'\r\n')
