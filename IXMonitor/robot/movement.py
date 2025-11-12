from easygopigo3 import EasyGoPiGo3
from .distance_sensor import is_obstacle_detected, get_distance

gpg = EasyGoPiGo3()

def move_forward(distance_m=0.1, blocking=False, check_obstacles=True):
    """Move forward with optional obstacle detection."""
    if check_obstacles and is_obstacle_detected(threshold_cm=25):
        print("Obstacle detected! Stopping.")
        gpg.stop()
        return False
    gpg.drive_cm(distance_m * 100, blocking=blocking)
    return True

def move_backward(distance_m=0.1, blocking=False):
    gpg.drive_cm(-distance_m * 100, blocking=blocking)

def turn_right(angle_deg=10, blocking=False):
    gpg.turn_degrees(angle_deg, blocking=blocking)

def turn_left(angle_deg=10, blocking=False):
    gpg.turn_degrees(-angle_deg, blocking=blocking)

def stop_robot():
    gpg.stop()

def get_obstacle_distance():
    """Get current obstacle distance in cm. Returns None if sensor unavailable."""
    return get_distance()

def go_to_door():
    """Automated sequence to move to door and take a picture."""
    from .camera import take_picture
    print("Driving to door...")
    move_forward(5.5)
    turn_left(90)
    move_forward(1)
    stop_robot()
    take_picture()
    print("At door.")

def return_to_start():
    """Return the robot to its starting point."""
    print("Returning to start...")
    move_backward(1)
    turn_right(90)
    move_backward(5.5)
    stop_robot()
    print("Returned to start.")
