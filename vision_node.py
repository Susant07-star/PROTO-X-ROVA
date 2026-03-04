# =========================================================
# VISION NODE - USER'S LAPTOP
# Processes mobile camera feed and streams to Control Node
# =========================================================

import os
import cv2
import time
import numpy as np
import threading
import socket
import struct
import json
import torch
from ultralytics import YOLO

# =========================================================
# NETWORK CONFIGURATION - [IMPORTANT: UPDATE THESE!]
# =========================================================
# 1. CONTROL_NODE_IP: The WiFi IP of the Laptop running esp_voice_server.py
#    - Open cmd on that laptop, type 'ipconfig', look for IPv4 Address.
CONTROL_NODE_IP = "192.168.137.1"  

CONTROL_NODE_PORT = 5000

# =========================================================
# CAMERA CONFIGURATION - [IMPORTANT: UPDATE THIS!]
# =========================================================
# 2. PHONE_CAM_URL: The URL from your 'IP Webcam' app on the phone
#    - Format: http://<PHONE_IP>:8080/video
PHONE_CAM_URL = "http://192.168.0.113:8080/video" # [FIXED IP] Do not change unless phone IP changes 

# =========================================================
# FORCE OPENVINO -> NPU (Fallbacks handled by OpenVINO)
# =========================================================
os.environ["OPENVINO_DEVICE"] = "NPU"
torch.set_grad_enabled(False)

# Optimization for Intel GPUs/iGPUs/NPUs which support OpenCL
cv2.setNumThreads(0)
cv2.ocl.setUseOpenCL(True)

# =========================================================
# DISTANCE & CALIBRATION (CRITICAL)
# =========================================================
# To fix distance:
# 1. Place an object (e.g., A4 Paper, Width 21cm) at exactly 50cm away.
# 2. Read the "Pixel Width" printed in the console.
# 3. Calculate: FOCAL_LENGTH = (Pixel_Width * 50) / 21
# 4. Update the value below.
FOCAL_LENGTH = 600.0  # Default estimate for typical webcam/phone

# REAL WORLD WIDTHS (in cm) - This fixes the "Bottle vs Person" size issue
CLASS_WIDTHS = {
    "person": 50.0,   # Shoulder width approx
    "bottle": 10.0,   # Water bottle width
    "cup": 8.0,
    "chair": 50.0,    # Seat width
    "couch": 180.0,
    "tv": 100.0,
    "laptop": 35.0,
    "cell phone": 7.5,
    "book": 15.0,
    "door": 90.0
}
DEFAULT_WIDTH = 20.0  # Fallback for unknown objects

# =========================================================
# PERFORMANCE SETTINGS
# =========================================================
RESIZE_WIDTH = 640  # Increased for better small object detection (was 320)
YOLO_INTERVAL = 3   # Run inference every 3 frames (smoother)
VIDEO_STREAM_INTERVAL = 2
OBSTACLE_THRESHOLD_CM = 55
MESSAGE_COOLDOWN_FRAMES = 15

# =========================================================
# NETWORK SENDER CLASS
# =========================================================
class NetworkSender:
    """Handles connection and data transmission to Control Node"""
    def __init__(self, ip, port):
        self.ip = ip
        self.port = port
        self.sock = None
        self.connected = False
        self.lock = threading.Lock()
        self.reconnect_thread = None
        self.should_reconnect = True
        
    def connect(self):
        """Establish connection to Control Node"""
        try:
            if self.sock:
                try:
                    self.sock.close()
                except:
                    pass
                    
            self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.sock.settimeout(5.0)
            print(f"📡 Connecting to Control Node at {self.ip}:{self.port}...")
            self.sock.connect((self.ip, self.port))
            self.sock.settimeout(None)  # Set to blocking mode after connection
            self.connected = True
            print(f"✅ Connected to Control Node!")
            return True
        except Exception as e:
            print(f"⚠️ Connection Failed: {e}")
            self.connected = False
            return False
    
    def send_frame(self, frame):
        """Send compressed video frame to Control Node"""
        if not self.connected:
            return
            
        try:
            with self.lock:
                # Compress frame to JPEG (quality 50 for speed/bandwidth)
                _, buffer = cv2.imencode('.jpg', frame, [int(cv2.IMWRITE_JPEG_QUALITY), 50])
                data = buffer.tobytes()
                size = len(data)
                
                # Packet Format: [MAGIC:2][TYPE:1][SIZE:4][PAYLOAD]
                # Type 1 = Video Frame
                header = struct.pack(">2sBI", b'RV', 1, size)
                self.sock.sendall(header + data)
        except Exception as e:
            print(f"❌ Network Error (Frame): {e}")
            self.connected = False
            self._schedule_reconnect()
    
    def send_signal(self, signal_type, data_dict):
        """Send JSON control signal to Control Node"""
        if not self.connected:
            return
            
        try:
            with self.lock:
                # Type 2 = Control Signal (JSON)
                payload = json.dumps({"type": signal_type, "data": data_dict}).encode('utf-8')
                size = len(payload)
                
                header = struct.pack(">2sBI", b'RV', 2, size)
                self.sock.sendall(header + payload)
        except Exception as e:
            print(f"❌ Network Error (Signal): {e}")
            self.connected = False
            self._schedule_reconnect()
    
    def _schedule_reconnect(self):
        """Schedule automatic reconnection in background"""
        if self.reconnect_thread is None or not self.reconnect_thread.is_alive():
            self.reconnect_thread = threading.Thread(target=self._reconnect_loop, daemon=True)
            self.reconnect_thread.start()
    
    def _reconnect_loop(self):
        """Background reconnection loop"""
        while self.should_reconnect and not self.connected:
            print("🔄 Attempting to reconnect in 3 seconds...")
            time.sleep(3)
            self.connect()
    
    def close(self):
        """Close connection"""
        self.should_reconnect = False
        self.connected = False
        if self.sock:
            try:
                self.sock.close()
            except:
                pass

# =========================================================
# WALL DETECTION (FAST OPTICAL)
# =========================================================
def detect_wall_boundary(frame):
    """Detect floor/wall boundary using edge detection"""
    gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
    h, w = gray.shape

    # Focus on the bottom 60% of the screen
    roi_top = int(h * 0.4)
    roi = gray[roi_top:h, :]

    blurred = cv2.GaussianBlur(roi, (7, 7), 0)
    edges = cv2.Canny(blurred, 30, 100)

    lines = cv2.HoughLinesP(
        edges,
        1,
        np.pi / 180,
        threshold=60,
        minLineLength=int(w * 0.6),
        maxLineGap=50
    )

    best_y = None
    if lines is not None:
        candidates = []
        for line in lines:
            x1, y1, x2, y2 = line[0]
            if x2 == x1:
                continue
            if abs((y2 - y1) / (x2 - x1)) < 0.1:  # Only horizontal-ish lines
                candidates.append((y1 + y2) // 2 + roi_top)

        if candidates:
            # SAFETY CHECK: Ignore lines at the very bottom (robot chassis/frame edge)
            candidates = [y for y in candidates if y < (h - 5)]
            
            if candidates:
                best_y = max(candidates)

    return best_y

# =========================================================
# THREADED VIDEO STREAM (NO LAG)
# =========================================================
class VideoStream:
    """Continuously reads frames from camera in background thread with Auto-Reconnect"""
    def __init__(self, url):
        self.url = url
        self.cap = cv2.VideoCapture(self.url)
        self.cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)
        self.frame = None
        self.lock = threading.Lock()
        self.stopped = False
        self.connected = self.cap.isOpened()

    def start(self):
        threading.Thread(target=self.update, daemon=True).start()
        return self

    def update(self):
        while not self.stopped:
            if self.connected and self.cap.isOpened():
                grabbed = self.cap.grab()
                if grabbed:
                    _, frame = self.cap.retrieve()
                    with self.lock:
                        self.frame = frame
                else:
                    # Frame grab failed, might have lost connection
                    print("⚠️ Lost Camera Frame... Reconnecting...")
                    self.connected = False
                    self.cap.release()
            else:
                # Attempt to reconnect
                # print(f"🔄 Reconnecting to Camera {self.url}...")
                try:
                    self.cap = cv2.VideoCapture(self.url)
                    self.cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)
                    if self.cap.isOpened():
                        print("✅ Camera Reconnected!")
                        self.connected = True
                except:
                    pass
                time.sleep(1) # Wait before retry

    def read(self):
        with self.lock:
            return self.frame.copy() if self.frame is not None else None

    def stop(self):
        self.stopped = True
        if self.cap: self.cap.release()

# =========================================================
# LOAD YOLO (OPENVINO NPU - INTEL CORE ULTRA SPECIALIZED)
# =========================================================
try:
    from openvino.runtime import Core
    core = Core()
    devices = core.available_devices
    print(f"🔍 OpenVINO Devices Found: {devices}")
    if "NPU" in devices:
        print("✅ Intel AI Boost NPU detected!")
    else:
        print("⚠️ NPU not listed. Using available devices.")
except Exception as e:
    print(f"⚠️ Could not list OpenVINO devices: {e}")


# =========================================================
# LOAD YOLO-WORLD (SMARTER VISION)
# =========================================================
# We use 'yolov8s-worldv2' -> Slightly bigger (Small) but understands ANY word.
# 'yolov8n' (Nano) is faster but dumb (only 80 fixed objects).
model_name = "yolov8s-worldv2" 
pt_model = f"{model_name}.pt"
openvino_model_dir = f"{model_name}_openvino_model"

print(f"🚀 Loading Intelligent Vision ({model_name})...")

# Check/Export Logic
if not os.path.exists(openvino_model_dir):
    print(f"⚠️ Model not found. downloading/exporting {pt_model}...")
    try:
        temp_model = YOLO(pt_model)
        # Export for NPU (Half Precision for speed)
        # temp_model.export(format="openvino", half=True) 
        # Note: YOLO-World sometimes has issues exporting to OpenVINO directly with dynamic classes.
        # For safety, we will run it in PyTorch mode first to ensure it works.
        # If speed is okay, we keep it. If not, we try export.
        pass
    except Exception as e:
        print(f"❌ Export skipped: {e}")

try:
    # Load Model
    model = YOLO(pt_model) 
    
    # 🌟 MAGIC STEP: TELL IT WHAT TO SEE! 🌟
    # We can list ANYTHING here.
    search_for = ["person", "door", "wall", "chair", "table", "bottle", "book", "cell phone"]
    model.set_classes(search_for)
    
    print(f"✅ Vision Ready! Looking for: {search_for}")
    print("   (Note: First run might be slow as it downloads the model)")
    
except Exception as e:
    print(f"❌ Error loading YOLO-World: {e}")
    print("   Falling back to standard 'yolov8n' (Nano).")
    model = YOLO("yolov8n.pt")

# =========================================================
# MAIN EXECUTION
# =========================================================
def main():
    # Start camera stream
    print(f"📡 Connecting to camera {PHONE_CAM_URL}")
    stream = VideoStream(PHONE_CAM_URL).start()
    time.sleep(1)

    if stream.read() is None:
        print("❌ Camera not detected")
        time.sleep(2)
        if stream.read() is None:
            print("❌ Retrying connection failed. Exiting.")
            stream.stop()
            return

    print("✅ Camera connected")

    # Initialize Network Sender
    print(f"\n📡 Initializing network connection to Control Node...")
    net = NetworkSender(CONTROL_NODE_IP, CONTROL_NODE_PORT)
    net.connect()  # Initial connection attempt

    # Main loop variables
    frame_count = 0
    prev_time = time.time()
    last_boxes = []
    last_wall_y = None
    message_cooldown = 0
    last_obstacle_zone = None

    print("\n✅ Vision Node Running!")
    print("=" * 50)

    try:
        while True:
            frame = stream.read()
            if frame is None:
                continue

            # Rotate if needed (uncomment if phone is horizontal)
            # frame = cv2.rotate(frame, cv2.ROTATE_90_CLOCKWISE)

            h0, w0, _ = frame.shape
            frame = cv2.resize(
                frame,
                (RESIZE_WIDTH, int(h0 * RESIZE_WIDTH / w0)),
                interpolation=cv2.INTER_LINEAR
            )

            h, w, _ = frame.shape
            left_zone = w // 3
            right_zone = 2 * w // 3

            frame_count += 1

            # =====================================================
            # YOLO + WALL (INTERVAL)
            # =====================================================
            if frame_count % YOLO_INTERVAL == 0:
                results = model(frame, conf=0.45, verbose=False)[0]
                last_boxes = results.boxes
                last_wall_y = detect_wall_boundary(frame)

            # =====================================================
            # ZONE DISTANCES & OBSTACLE DETECTION
            # =====================================================
            closest = {"LEFT": 9999, "CENTER": 9999, "RIGHT": 9999}
            
            blocked_zone = None
            min_dist = 9999


            for box in last_boxes:
                x1, y1, x2, y2 = map(int, box.xyxy[0])
                cls = int(box.cls[0])
                label = model.names[cls] if model.names else "unknown"
                
                bw = x2 - x1
                if bw <= 0: continue

                # Get real world width for this object type
                real_width = CLASS_WIDTHS.get(label, DEFAULT_WIDTH)
                
                # Distance Formula: D = (Real_Width * Focal_Length) / Pixel_Width
                distance = (real_width * FOCAL_LENGTH) / bw
                cx = (x1 + x2) // 2

                if cx < left_zone:
                    zone = "LEFT"
                elif cx > right_zone:
                    zone = "RIGHT"
                else:
                    zone = "CENTER"

                closest[zone] = min(closest[zone], distance)
                
                # Check for obstacles below threshold
                if distance < OBSTACLE_THRESHOLD_CM:
                    if distance < min_dist:
                        min_dist = distance
                        blocked_zone = zone

                # Visuals
                color = (0, 0, 255) if distance < OBSTACLE_THRESHOLD_CM else (0, 255, 0)
                cv2.rectangle(frame, (x1, y1), (x2, y2), color, 2)
                cv2.putText(frame, f"{label} {int(distance)}cm",
                            (x1, y1 - 5),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.5,
                            color, 1)

            # =====================================================
            # SEND OBSTACLE SIGNALS TO CONTROL NODE
            # =====================================================
            if blocked_zone and message_cooldown == 0:
                # Send obstacle signal
                signal_data = {
                    "zone": blocked_zone,
                    "distance": round(min_dist, 1),
                    "timestamp": time.time(),
                    "all_zones": {
                        "left": round(closest["LEFT"], 1),
                        "center": round(closest["CENTER"], 1),
                        "right": round(closest["RIGHT"], 1)
                    }
                }
                net.send_signal("OBSTACLE", signal_data)
                print(f"⚠️ OBSTACLE DETECTED: {blocked_zone} at {min_dist:.1f}cm")
                
                message_cooldown = MESSAGE_COOLDOWN_FRAMES
                last_obstacle_zone = blocked_zone
            
            if message_cooldown > 0:
                message_cooldown -= 1

            # =====================================================
            # SEND VIDEO FRAME TO CONTROL NODE
            # =====================================================
            if frame_count % VIDEO_STREAM_INTERVAL == 0:
                net.send_frame(frame)

            # =====================================================
            # VISUALS (LOCAL DISPLAY)
            # =====================================================
            # Draw zone lines
            cv2.line(frame, (left_zone, 0), (left_zone, h), (120, 120, 120), 1)
            cv2.line(frame, (right_zone, 0), (right_zone, h), (120, 120, 120), 1)

            # Draw wall boundary if detected
            if last_wall_y:
                cv2.line(frame, (0, last_wall_y), (w, last_wall_y), (255, 255, 0), 2)

            # =====================================================
            # FPS COUNTER
            # =====================================================
            now = time.time()
            fps = 1 / (now - prev_time)
            prev_time = now
            cv2.putText(frame, f"FPS: {int(fps)}",
                        (10, 20),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.6,
                        (0, 255, 255), 2)

            # Network status indicator
            status_color = (0, 255, 0) if net.connected else (0, 0, 255)
            status_text = "CONNECTED" if net.connected else "DISCONNECTED"
            cv2.putText(frame, f"Network: {status_text}",
                        (10, 40),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.5,
                        status_color, 2)

            # =====================================================
            # DISPLAY
            # =====================================================
            cv2.imshow("Vision Node (Intel NPU/GPU)", frame)

            if cv2.waitKey(1) & 0xFF == ord('q'):
                print("\n👋 Shutting down Vision Node...")
                break

    except KeyboardInterrupt:
        print("\n👋 Interrupted by user")
    finally:
        # Cleanup
        stream.stop()
        net.close()
        cv2.destroyAllWindows()
        print("✅ Vision Node stopped cleanly")

if __name__ == "__main__":
    main()
