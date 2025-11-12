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
from .movement import move_forward, move_backward, turn_left, turn_right, stop_robot

# Autonomous control state
autonomous_thread = None
autonomous_stop_event = Event()

def capture_frame_from_camera(camera_instance):
    """Capture a single frame from the camera as bytes"""
    stream = io.BytesIO()
    camera_instance.capture(stream, format='jpeg', use_video_port=True)
    stream.seek(0)
    return stream.read()

def execute_action(action: str):
    """Execute robot movement action"""
    action = action.lower().strip()
    
    if action == "forward":
        print("Moving forward")
        move_forward(distance_m=0.3, blocking=True)  # 30cm forward
    elif action == "backward":
        print("Moving backward")
        move_backward(distance_m=0.2, blocking=True)  # 20cm backward
    elif action == "left":
        print("Turning left")
        turn_left(angle_deg=30, blocking=True)  # 30 degrees
    elif action == "right":
        print("Turning right")
        turn_right(angle_deg=30, blocking=True)  # 30 degrees
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
        print(f"❌ Error getting decision: {e}")
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
    """Main autonomous navigation loop"""
    print(f"\nStarting autonomous navigation")
    print(f"Goal: {goal}")
    print(f"Max actions: {max_actions}\n")
    
    action_history = []
    action_count = 0
    
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
            # Capture current frame
            print(f"\n[Action {action_count + 1}/{max_actions}]")
            print("Capturing frame...")
            frame_bytes = capture_frame_from_camera(camera_instance)
            
            # Get decision from AI
            print("Analyzing scene and making decision...")
            result = get_autonomous_decision(frame_bytes, goal, action_history)
            
            if not result.get("success"):
                print(f"Decision failed: {result.get('error')}")
                break
            
            decision = result.get("decision", {})
            
            # Display AI's analysis
            print(f"\nObservation: {decision.get('observation', 'N/A')}")
            print(f"Reasoning: {decision.get('reasoning', 'N/A')}")
            print(f"Progress: {decision.get('progress', 'N/A')}")
            print(f"Action: {decision.get('action', 'stop')}")
            
            # Execute action
            action = decision.get('action', 'stop')
            action_history.append(action)
            action_count += 1
            
            completed = execute_action(action)
            
            if completed or action == "complete":
                print("\nGoal achieved! Stopping autonomous mode.")
                break
            
            # Small delay between actions for safety
            time.sleep(0.5)
            
        except KeyboardInterrupt:
            print("\nAutonomous mode interrupted by user")
            break
        except Exception as e:
            print(f"\nError in autonomous loop: {e}")
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
