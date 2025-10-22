# main.py
from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, StreamingResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from threading import Thread
from robot import movement, camera as cam_module
import picamera
from time import sleep

app = FastAPI()
app.mount("/static", StaticFiles(directory="static"), name="static")

# -----------------
# Robot API
# -----------------
@app.post("/move")
async def move(req: Request):
    data = await req.json()
    direction = data.get("direction")
    if direction == "forward": movement.move_forward()
    elif direction == "backward": movement.move_backward()
    elif direction == "left": movement.turn_left()
    elif direction == "right": movement.turn_right()
    elif direction == "stop": movement.stop()
    return JSONResponse({"status": f"{direction} command executed"})

@app.post("/go_to_door")
async def go_door():
    Thread(target=movement.go_to_door).start()
    return JSONResponse({"status": "Moving to door..."})

@app.post("/return_to_start")
async def return_start():
    Thread(target=movement.return_to_start).start()
    return JSONResponse({"status": "Returning to start..."})

# -----------------
# Pages
# -----------------
@app.get("/", response_class=HTMLResponse)
async def index():
    with open("templates/index.html") as f:
        return f.read()

@app.get("/camera", response_class=HTMLResponse)
async def camera_page():
    with open("templates/camera.html") as f:
        return f.read()

# -----------------
# MJPEG streaming
# -----------------
output = cam_module.StreamingOutput(face_server_url="http://172.20.86.247:8000/process_frame")

# main.py
from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, StreamingResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from threading import Thread
from robot import movement, camera as cam_module
import picamera
from time import sleep

app = FastAPI()
app.mount("/static", StaticFiles(directory="static"), name="static")

# -----------------
# Robot API
# -----------------
@app.post("/move")
async def move(req: Request):
    data = await req.json()
    direction = data.get("direction")
    if direction == "forward": movement.move_forward()
    elif direction == "backward": movement.move_backward()
    elif direction == "left": movement.turn_left()
    elif direction == "right": movement.turn_right()
    elif direction == "stop": movement.stop()
    return JSONResponse({"status": f"{direction} command executed"})

@app.post("/go_to_door")
async def go_door():
    Thread(target=movement.go_to_door).start()
    return JSONResponse({"status": "Moving to door..."})

@app.post("/return_to_start")
async def return_start():
    Thread(target=movement.return_to_start).start()
    return JSONResponse({"status": "Returning to start..."})

# -----------------
# Pages
# -----------------
@app.get("/", response_class=HTMLResponse)
async def index():
    with open("templates/index.html") as f:
        return f.read()

@app.get("/camera", response_class=HTMLResponse)
async def camera_page():
    with open("templates/camera.html") as f:
        return f.read()

from fastapi.responses import RedirectResponse

@app.get("/video_feed")
def camera_redirect():
    return RedirectResponse("/stream.mjpg")


# -----------------
# MJPEG streaming
# -----------------
output = cam_module.StreamingOutput(face_server_url="http://172.20.86.247:8000/detect")

@app.get("/stream.mjpg")
def stream_mjpeg():
    import picamera
    camera = picamera.PiCamera(resolution=(320, 240), framerate=15)
    camera.start_recording(output, format='mjpeg')

    def generator():
        try:
            while True:
                with output.condition:
                    output.condition.wait()
                    frame = output.frame
                yield (b"--FRAME\r\n"
                       b"Content-Type: image/jpeg\r\n\r\n" + frame + b"\r\n")
        finally:
            camera.stop_recording()

    return StreamingResponse(generator(), media_type='multipart/x-mixed-replace; boundary=FRAME')