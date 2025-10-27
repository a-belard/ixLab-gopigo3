# robot/camera.py
import io
import os
import requests
from threading import Condition

class StreamingOutput:
    """
    Handles MJPEG stream and sends frames to Windows face detection server.
    Optimized for performance with frame skipping.
    """
    def __init__(self, face_server_url=None, frame_skip=3, timeout=0.5):
        self.frame = None
        self.buffer = io.BytesIO()
        self.condition = Condition()
        self.face_server_url = face_server_url
        self.frame_skip = frame_skip
        self.timeout = timeout
        self.frame_count = 0

    def write(self, buf):
        if buf.startswith(b'\xff\xd8'):
            self.buffer.truncate()
            with self.condition:
                self.frame = self.buffer.getvalue()
                
                # Send to face detection server (only every Nth frame)
                if self.face_server_url:
                    self.frame_count += 1
                    if self.frame_count >= self.frame_skip:
                        self.frame_count = 0
                        try:
                            requests.post(
                                self.face_server_url, 
                                files={'image': ('frame.jpg', self.frame, 'image/jpeg')},
                                timeout=self.timeout
                            )
                        except Exception as e:
                            pass  # Silently ignore failures
                
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
