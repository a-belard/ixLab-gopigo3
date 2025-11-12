# robot/distance_sensor.py
from di_sensors.easy_mutex import ifMutexAcquire, ifMutexRelease
import time
from di_sensors import distance_sensor


class EasyDistanceSensor(distance_sensor.DistanceSensor):
    """
    Class for the Distance Sensor device.
    Uses mutexes for thread-safe access.
    """
    def __init__(self, port="I2C", use_mutex=False):
        """
        Creates an EasyDistanceSensor object.

        :param string port: the bus for the sensor. Options: "I2C", "AD1", "AD2"
        :param bool use_mutex: Enable for multi-threaded access
        """
        self.descriptor = "Distance Sensor"
        self.use_mutex = use_mutex
        self.readings = []  # Store last 3 readings for averaging

        # Port mapping
        possible_ports = {
            "I2C": "RPI_1SW",
            "AD1": "GPG3_AD1",
            "AD2": "GPG3_AD2",
            "RPI_1SW": "RPI_1SW",
            "RPI_1": "RPI_1",
            "RPI_1HW": "RPI_1",
            "GPG3_AD1": "GPG3_AD1",
            "GPG3_AD2": "GPG3_AD2"
        }

        port = port.upper()
        bus = possible_ports.get(port, "RPI_1SW")

        ifMutexAcquire(self.use_mutex)
        try:
            distance_sensor.DistanceSensor.__init__(self, bus=bus)
        except Exception as e:
            raise
        finally:
            ifMutexRelease(self.use_mutex)

    def read_mm(self):
        """
        Reads distance in millimeters.
        Range: 5-2300mm, returns 3000 if out of range.
        """
        mm = 8190
        attempt = 0

        # Try 3 times to get a valid reading
        while (mm > 8000 or mm < 5) and attempt < 3:
            ifMutexAcquire(self.use_mutex)
            try:
                mm = self.read_range_single()
            except Exception as e:
                print(f"Distance sensor read error: {e}")
                mm = 0
            finally:
                ifMutexRelease(self.use_mutex)
            attempt += 1
            time.sleep(0.001)

        # Add valid reading to history for averaging
        if mm < 8000 and mm > 5:
            self.readings.append(mm)
            if len(self.readings) > 3:
                self.readings.pop(0)
        
        # If we have readings, use average; otherwise use current reading
        if len(self.readings) > 0:
            mm = round(sum(self.readings) / float(len(self.readings)))
        
        # Cap at 3000mm (300cm)
        if mm > 3000:
            mm = 3000

        return mm

    def read(self):
        """
        Reads distance in centimeters.
        Range: 0-230cm, returns 300 if out of range.
        """
        cm = self.read_mm() // 10
        return cm

    def read_inches(self):
        """
        Reads distance in inches.
        Range: 0-90 inches.
        """
        cm = self.read()
        return round(cm / 2.54, 1)


# Singleton instance for easy access
_distance_sensor_instance = None

def get_distance_sensor():
    """Get or create the distance sensor singleton."""
    global _distance_sensor_instance
    if _distance_sensor_instance is None:
        try:
            print("Initializing distance sensor on I2C...")
            _distance_sensor_instance = EasyDistanceSensor(port="I2C", use_mutex=True)
            # Test read to verify it's working
            test_reading = _distance_sensor_instance.read()
            print(f"Distance sensor initialized successfully - test reading: {test_reading}cm")
        except Exception as e:
            print(f"Warning: Could not initialize distance sensor: {e}")
            print("Sensor will be disabled. Check connections and try again.")
            _distance_sensor_instance = None
    return _distance_sensor_instance


def is_obstacle_detected(threshold_cm=30):
    """
    Check if an obstacle is detected within threshold distance.
    
    :param threshold_cm: Distance threshold in centimeters (default 30cm)
    :returns: True if obstacle detected, False otherwise
    """
    sensor = get_distance_sensor()
    if sensor is None:
        return False
    
    try:
        distance = sensor.read()
        return distance < threshold_cm and distance > 0
    except Exception as e:
        print(f"Error reading distance sensor: {e}")
        return False


def get_distance():
    """
    Get current distance reading in centimeters.
    Returns None if sensor not available or reading failed.
    """
    sensor = get_distance_sensor()
    if sensor is None:
        return None
    
    try:
        distance = sensor.read()
        # If distance is 0, it usually means sensor error - return None
        if distance == 0:
            return None
        return distance
    except Exception as e:
        print(f"Error reading distance: {e}")
        return None
