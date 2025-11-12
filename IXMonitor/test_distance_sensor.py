#!/usr/bin/env python3
"""
Test script for distance sensor
Run this on the Raspberry Pi to verify sensor is working
"""

import sys
import time

try:
    from robot.distance_sensor import get_distance_sensor, get_distance
    
    print("Testing Distance Sensor...")
    print("-" * 40)
    
    # Try to get sensor
    sensor = get_distance_sensor()
    
    if sensor is None:
        print("ERROR: Could not initialize distance sensor!")
        print("\nTroubleshooting:")
        print("1. Check sensor is connected to I2C port")
        print("2. Verify di_sensors library: pip3 install Dexter_Industries_Distance_Sensor")
        print("3. Check I2C is enabled: sudo raspi-config -> Interface Options -> I2C")
        sys.exit(1)
    
    print("✓ Sensor initialized successfully")
    print("\nReading distance every second (Ctrl+C to stop)...")
    print("-" * 40)
    
    try:
        while True:
            distance = get_distance()
            
            if distance is None:
                print("No reading (sensor error or not responding)")
            elif distance >= 300:
                print(f"Distance: {distance}cm (Out of range)")
            elif distance < 15:
                print(f"Distance: {distance}cm ⚠️ VERY CLOSE")
            elif distance < 30:
                print(f"Distance: {distance}cm ⚠️ WARNING")
            else:
                print(f"Distance: {distance}cm ✓")
            
            time.sleep(1)
            
    except KeyboardInterrupt:
        print("\n\nTest stopped by user")
        print("-" * 40)
        print("Sensor test completed!")

except ImportError as e:
    print(f"ERROR: Could not import distance sensor module: {e}")
    print("\nMake sure you're running this from the IXMonitor directory:")
    print("  cd /home/pi/ixLab-gopigo3/IXMonitor")
    print("  python3 test_distance_sensor.py")
    sys.exit(1)

except Exception as e:
    print(f"ERROR: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)
