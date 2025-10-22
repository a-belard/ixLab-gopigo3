from .movement import move_forward, move_backward, turn_left, turn_right, stop_robot
from .camera import take_picture

def go_to_door():
    move_forward(5.5)
    turn_left(90)
    move_forward(1)
    stop_robot()
    take_picture()

def return_to_start():
    move_backward(1)
    turn_right(90)
    move_backward(5.5)
    stop_robot()
