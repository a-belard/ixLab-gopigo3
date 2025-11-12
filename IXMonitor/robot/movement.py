from easygopigo3 import EasyGoPiGo3
from .distance_sensor import is_obstacle_detected, get_distance

gpg = EasyGoPiGo3()

# Speed configurations (default is 300)
NORMAL_SPEED = 300
FAST_SPEED = 500
SLOW_SPEED = 150

def set_speed(speed):
    """Set robot speed (100-500)"""
    gpg.set_speed(speed)

def move_forward(distance_m=0.1, blocking=False, check_obstacles=True, speed=NORMAL_SPEED):
    """Move forward with optional obstacle detection and speed control."""
    if check_obstacles and is_obstacle_detected(threshold_cm=25):
        print("Obstacle detected! Stopping.")
        gpg.stop()
        return False
    
    # Use faster speed for longer distances
    if distance_m > 0.5:
        speed = FAST_SPEED
    
    gpg.set_speed(speed)
    gpg.drive_cm(distance_m * 100, blocking=blocking)
    gpg.set_speed(NORMAL_SPEED)  # Reset to normal
    return True

def move_backward(distance_m=0.1, blocking=False, speed=NORMAL_SPEED):
    gpg.set_speed(speed)
    gpg.drive_cm(-distance_m * 100, blocking=blocking)
    gpg.set_speed(NORMAL_SPEED)

def turn_right(angle_deg=10, blocking=False, speed=NORMAL_SPEED):
    gpg.set_speed(speed)
    gpg.turn_degrees(angle_deg, blocking=blocking)
    gpg.set_speed(NORMAL_SPEED)

def turn_left(angle_deg=10, blocking=False, speed=NORMAL_SPEED):
    gpg.set_speed(speed)
    gpg.turn_degrees(-angle_deg, blocking=blocking)
    gpg.set_speed(NORMAL_SPEED)

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
