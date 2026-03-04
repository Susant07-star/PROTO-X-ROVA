# NOTE: This script sends commands to the ESP32 via WiFi.
# It works unchanged with the new PCA9685 code because the Protocol (LS:90) is identical!
import socket
import time

# CONFIG
HOST = '0.0.0.0' # Listen on all interfaces
PORT = 4001      # Dedicated Arm Port (Must match arm_controller.ino 'port')

def start_server():
    print(f"🔧 ARM CALIBRATION SERVER")
    
    # Print Debug Info
    hostname = socket.gethostname()
    local_ip = socket.gethostbyname(hostname)
    print(f"Server Hostname: {hostname}")
    print(f"Server Local IP: {local_ip}")
    print(f"Listening on Port {PORT}...")
    
    # Help user check IP
    print(f"\n[DEBUG] If ESP32 fails to connect, ensure 'const char *host' in Arduino code matches: {local_ip}")
    print(f"        (If connected via Hotspot, it might be 192.168.137.1)\n")
    
    server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server.bind((HOST, PORT))
    server.listen(1)
    
    print("Waiting for ESP32-CAM (Arm) to connect...")
    conn, addr = server.accept()
    print(f"✅ Connected by {addr}")
    
    print("\nINSTRUCTIONS:")
    print("Type command in format: [PART]:[ANGLE]")
    print("Parts: LS/RS (Shoulders), LE/RE (Elbows), LW/RW (Wrists), LG/RG (Grippers)")
    print("Angles: 0 to 180")
    print("NOTE: Shoulders (LS/RS) are software-limited to 180 max.")
    print("Example: 'LS:100' -> Moves Left Shoulder to 100")
    print("Type 'exit' to quit.\n")

    try:
        while True:
            cmd = input("Command > ").strip().upper()
            
            if cmd == "EXIT":
                break
            
            if ":" not in cmd:
                print("❌ Invalid format. Use PART:ANGLE (e.g., LE:45)")
                continue
                
            # Send to ESP32
            conn.sendall(f"{cmd}\n".encode())
            print(f"Sent: {cmd}")
            
    except Exception as e:
        print(f"Error: {e}")
    finally:
        conn.close()
        server.close()

if __name__ == "__main__":
    start_server()
