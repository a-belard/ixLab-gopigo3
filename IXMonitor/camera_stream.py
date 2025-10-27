import cv2, requests, numpy as np
from picamera2 import Picamera2
from config import WINDOWS_SERVER, CAMERA_RES, CAMERA_FPS

picam2 = Picamera2()
config = picam2.create_preview_configuration(
    main={"size": CAMERA_RES, "format": "RGB888"},
    controls={"FrameRate": CAMERA_FPS}
)
picam2.configure(config)
picam2.start()

frame_count = 0
FRAME_SKIP = 3  # Send every 3rd frame to detection server

def gen_frames_remote():
    """Yield MJPEG frames processed by Windows face detection server."""
    global frame_count
    
    while True:
        frame = picam2.capture_array()
        annotated = frame  # Default to original frame
        
        # Only send every Nth frame for detection
        frame_count += 1
        if frame_count >= FRAME_SKIP:
            frame_count = 0
            _, buffer = cv2.imencode('.jpg', frame)
            files = {'image': ('frame.jpg', buffer.tobytes(), 'image/jpeg')}
            try:
                resp = requests.post(WINDOWS_SERVER, files=files, timeout=0.5)
                img_array = np.frombuffer(resp.content, np.uint8)
                annotated = cv2.imdecode(img_array, cv2.IMREAD_COLOR)
            except:
                pass  # Use original frame on failure
        
        _, jpeg = cv2.imencode('.jpg', annotated)
        yield (b'--frame\r\n'
               b'Content-Type: image/jpeg\r\n\r\n' + jpeg.tobytes() + b'\r\n')
