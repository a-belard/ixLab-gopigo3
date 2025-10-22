from easygopigo3 import EasyGoPiGo3

gpg = EasyGoPiGo3()

def move_forward(distance_m=0.1, blocking=False):
    gpg.drive_cm(distance_m * 100, blocking=blocking)

def move_backward(distance_m=0.1, blocking=False):
    gpg.drive_cm(-distance_m * 100, blocking=blocking)

def turn_right(angle_deg=10, blocking=False):
    gpg.turn_degrees(angle_deg, blocking=blocking)

def turn_left(angle_deg=10, blocking=False):
    gpg.turn_degrees(-angle_deg, blocking=blocking)

def stop_robot():
    gpg.stop()
