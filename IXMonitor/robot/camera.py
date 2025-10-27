# robot/camera.py
import io
import os
import requests
from threading import Condition

class StreamingOutput:
    """
    Handles MJPEG stream and sends frames to Windows face detection server.
    """
    def __init__(self, face_server_url=None):
        self.frame = None
        self.buffer = io.BytesIO()
        self.condition = Condition()
        self.face_server_url = face_server_url

    def write(self, buf):
        if buf.startswith(b'\xff\xd8'):
            self.buffer.truncate()
            with self.condition:
                self.frame = self.buffer.getvalue()
                if self.face_server_url:
                    try:
                        requests.post(self.face_server_url, files={'frame': self.frame}, timeout=0.05)
                    except:
                        pass
                self.condition.notify_all()
            self.buffer.seek(0)
        return self.buffer.write(buf)


def take_picture(filename="door_picture.jpg"):
    """Takes a photo using the existing camera instance."""
    import picamera
    from time import sleep
    
    print("Taking picture...")
    # Create temporary camera instance for photo capture
    with picamera.PiCamera() as cam:
        cam.resolution = (1024, 768)
        sleep(1)  # Allow camera to warm up
        cam.capture(filename)
    
    print(f"Saved {filename}")
    # Play audio confirmation if available
    try:
        os.system('espeak "Picture taken" --stdout | aplay -D plughw:1,0 2>/dev/null')
    except:
        pass
    
    return filename
