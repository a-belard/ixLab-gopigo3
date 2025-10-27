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
                raw_frame = self.buffer.getvalue()
                
                # Send to face detection server and get annotated frame back
                if self.face_server_url:
                    self.frame_count += 1
                    if self.frame_count >= self.frame_skip:
                        self.frame_count = 0
                        try:
                            response = requests.post(
                                self.face_server_url, 
                                files={'image': ('frame.jpg', raw_frame, 'image/jpeg')}, 
                                timeout=self.timeout
                            )
                            if response.status_code == 200:
                                # Use annotated frame from server
                                self.frame = response.content
                            else:
                                # Fallback to raw frame if server error
                                self.frame = raw_frame
                        except:
                            # Fallback to raw frame on network error
                            self.frame = raw_frame
                    else:
                        # Use raw frame for skipped frames
                        self.frame = raw_frame
                else:
                    # No face detection server, use raw frame
                    self.frame = raw_frame
                
                self.condition.notify_all()
            self.buffer.seek(0)
        return self.buffer.write(buf)


def take_picture(camera_instance, filename="door_picture.jpg"):
    """Takes a photo using the existing camera instance."""
    import os
    
    print("Taking picture...")
    try:
        # Use the existing camera's capture method with still port
        camera_instance.capture(filename, use_video_port=False, resize=(1024, 768))
        print(f"Saved {filename}")
        
        # Play audio confirmation
        try:
            os.system('espeak "Picture taken" --stdout | aplay -D plughw:1,0 2>/dev/null')
        except:
            pass
        
        return filename
    except Exception as e:
        print(f"Error taking picture: {e}")
        return None
