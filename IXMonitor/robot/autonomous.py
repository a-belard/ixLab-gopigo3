# robot/autonomous.py
"""
Autonomous navigation module using vision-guided decision making
"""
import requests
import io
import json
import time
from threading import Thread, Event
from config import WINDOWS_SERVER_BASE
from .movement import move_forward, move_backward, turn_left, turn_right, stop_robot, get_obstacle_distance

# Autonomous control state
autonomous_thread = None
autonomous_stop_event = Event()

def capture_frame_from_camera(camera_instance):
    """Capture a single frame from the camera as bytes"""
    stream = io.BytesIO()
    camera_instance.capture(stream, format='jpeg', use_video_port=True)
    stream.seek(0)
    return stream.read()

def execute_action(action: str, speed_mode: str = "normal"):
    """
    Execute robot movement action with obstacle avoidance and speed control.
    
    :param action: Movement action (forward, backward, left, right, stop, complete)
    :param speed_mode: Speed setting - "slow", "normal", or "fast"
    """
    action = action.lower().strip()
    
    # Map speed mode to actual speed values
    from .movement import NORMAL_SPEED, FAST_SPEED, SLOW_SPEED
    speed_map = {
        "slow": SLOW_SPEED,
        "normal": NORMAL_SPEED,
        "fast": FAST_SPEED
    }
    speed = speed_map.get(speed_mode, NORMAL_SPEED)
    
    if action == "forward":
        print(f"Moving forward ({speed_mode} speed)")
        # Check for obstacles before moving forward
        distance = get_obstacle_distance()
        if distance is not None and distance < 25:
            print(f"Obstacle detected at {distance}cm - stopping")
            stop_robot()
            return False
        
        # Use longer distance for continuous forward movement
        result = move_forward(distance_m=0.5, blocking=True, check_obstacles=True, speed=speed)
        if not result:
            print("Obstacle encountered during movement")
        return False
    elif action == "backward":
        print(f"Moving backward ({speed_mode} speed)")
        move_backward(distance_m=0.3, blocking=True, speed=speed)
    elif action == "left":
        print(f"Turning left ({speed_mode} speed)")
        turn_left(angle_deg=30, blocking=True, speed=speed)
    elif action == "right":
        print(f"Turning right ({speed_mode} speed)")
        turn_right(angle_deg=30, blocking=True, speed=speed)
    elif action == "stop":
        print("Stopping")
        stop_robot()
    elif action == "complete":
        print("Goal completed!")
        stop_robot()
        return True  # Signal completion
    else:
        print(f"Unknown action: {action}")
        stop_robot()
    
    return False  # Not completed

def get_autonomous_decision(image_bytes: bytes, goal: str, previous_actions: list) -> dict:
    """Request decision from Windows server"""
    try:
        url = f"{WINDOWS_SERVER_BASE}/autonomous/decide"
        
        files = {'image': ('frame.jpg', image_bytes, 'image/jpeg')}
        data = {
            'goal': goal,
            'previous_actions': json.dumps(previous_actions)
        }
        
        response = requests.post(url, files=files, data=data, timeout=15)
        response.raise_for_status()
        
        return response.json()
        
    except requests.exceptions.RequestException as e:
        print(f"Error getting decision: {e}")
        return {
            "success": False,
            "error": str(e),
            "decision": {
                "action": "stop",
                "reasoning": f"Network error: {str(e)}",
                "observation": "Cannot connect to server",
                "progress": "0%"
            }
        }

def autonomous_navigation_loop(camera_instance, goal: str, max_actions: int = 20):
    """Main autonomous navigation loop with speed optimization"""
    print(f"\nStarting autonomous navigation (FAST mode)")
    print(f"Goal: {goal}")
    print(f"Max actions: {max_actions}\n")
    
    action_history = []
    action_count = 0
    consecutive_forward = 0  # Track consecutive forward moves for speed boost
    
    try:
        # Notify server to start autonomous mode
        requests.post(
            f"{WINDOWS_SERVER_BASE}/autonomous/start",
            json={"goal": goal, "max_actions": max_actions},
            timeout=5
        )
    except:
        pass
    
    while not autonomous_stop_event.is_set() and action_count < max_actions:
        try:
            loop_start = time.time()
            
            # Quick distance check
            distance = get_obstacle_distance()
            if distance is not None and distance < 20:
                print(f"WARNING: Close obstacle: {distance}cm")
            
            # Capture frame
            print(f"\n[Action {action_count + 1}/{max_actions}]")
            frame_bytes = capture_frame_from_camera(camera_instance)
            
            # Get decision from AI (optimized prompts for speed)
            decision_start = time.time()
            result = get_autonomous_decision(frame_bytes, goal, action_history)
            decision_time = time.time() - decision_start
            print(f"AI decision: {decision_time:.2f}s")
            
            if not result.get("success"):
                print(f"Decision failed: {result.get('error')}")
                break
            
            decision = result.get("decision", {})
            
            # Compact output
            print(f"Observation: {decision.get('observation', 'N/A')[:60]}...")
            print(f"Reasoning: {decision.get('reasoning', 'N/A')[:60]}...")
            print(f"Progress: {decision.get('progress', 'N/A')}")
            
            # Execute action with speed control
            action = decision.get('action', 'stop')
            action_history.append(action)
            action_count += 1
            
            # Determine speed based on consecutive forward moves
            if action == "forward":
                consecutive_forward += 1
                speed_mode = "fast" if consecutive_forward >= 2 else "normal"
            else:
                consecutive_forward = 0
                speed_mode = "normal"
            
            print(f"Action: {action.upper()} ({speed_mode})")
            completed = execute_action(action, speed_mode)
            
            if completed or action == "complete":
                print("\nGoal achieved!")
                break
            
            loop_time = time.time() - loop_start
            print(f"Loop time: {loop_time:.2f}s")
            
            # Minimal delay for fast navigation
            time.sleep(0.2)
            
        except KeyboardInterrupt:
            print("\nStopped by user")
            break
        except Exception as e:
            print(f"\nError: {e}")
            break
    
    # Final stop
    stop_robot()
    autonomous_stop_event.clear()
    
    # Notify server to stop
    try:
        requests.post(f"{WINDOWS_SERVER_BASE}/autonomous/stop", timeout=5)
    except:
        pass
    
    print(f"\nAutonomous navigation completed")
    print(f"Total actions: {action_count}")
    print(f"Action sequence: {' -> '.join(action_history)}\n")
    
    return {
        "success": True,
        "action_count": action_count,
        "action_history": action_history,
        "completed": action_count < max_actions
    }

def start_autonomous_mode(camera_instance, goal: str, max_actions: int = 20):
    """Start autonomous navigation in a separate thread"""
    global autonomous_thread, autonomous_stop_event
    
    # Stop any existing autonomous mode
    if autonomous_thread and autonomous_thread.is_alive():
        print("Stopping existing autonomous mode...")
        stop_autonomous_mode()
        time.sleep(1)
    
    # Reset stop event
    autonomous_stop_event.clear()
    
    # Start new thread
    autonomous_thread = Thread(
        target=autonomous_navigation_loop,
        args=(camera_instance, goal, max_actions)
    )
    autonomous_thread.start()
    
    return {
        "success": True,
        "message": f"Autonomous mode started with goal: {goal}"
    }

def stop_autonomous_mode():
    """Stop autonomous navigation"""
    global autonomous_stop_event
    
    print("Stopping autonomous mode...")
    autonomous_stop_event.set()
    stop_robot()
    
    # Wait for thread to finish
    if autonomous_thread and autonomous_thread.is_alive():
        autonomous_thread.join(timeout=5)
    
    return {
        "success": True,
        "message": "Autonomous mode stopped"
    }

def is_autonomous_active():
    """Check if autonomous mode is active"""
    return autonomous_thread is not None and autonomous_thread.is_alive()
