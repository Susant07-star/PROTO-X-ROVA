import asyncio
import socket
import time
import os
import re
import traceback
import struct
import wave
import io
import pyttsx3
import numpy as np
import cv2
import aiohttp
from aiohttp import web # Added for Web Interface
import asyncio # moved up
from ultralytics import YOLO
from dotenv import load_dotenv
from openai import AsyncOpenAI
# Removed OpenAI API Key import
from faster_whisper import WhisperModel, download_model
import speech_recognition as sr
import numpy as np
import threading
import queue
import msvcrt
import sys
import io
import python_weather
import geocoder # For IP-based location
import json # Added for Vision Node JSON parsing

# If you see the DLL error again, try:
# Fix 2: Add Windows Defender Exception
# pip uninstall av
# pip install av --force-reinstall


load_dotenv()
os.environ["HF_HUB_DISABLE_SYMLINKS_WARNING"] = "1" # Suppress HF Warning



# --- GLOBAL STATE ---
ROBOT_STATE = {
    "connected": True,  # Server is running
    "esp32_connected": False,
    "arm_connected": False, # Track arm ESP separately
    "vision_connected": False,
    "temp_legs": None,  # Temperature from Legs/Main ESP
    "temp_arms": None,  # Temperature from Arms ESP
    "obstacle_type": "None",
    "obstacle_dist": 0,
    "last_voice_cmd": ""
}

latest_frame = None # Global variable to store latest JPEG frame

client_socket = None # Global reference for Web API

client_socket = None # Global reference for Web API
current_interaction_id = 0 # Counter to track latest user interaction for TTS cancellation
whisper_model_ref = None # Reference to the loaded model for Web API

# --- REMINDER MANAGER ---
class ReminderManager:
    def __init__(self, filepath="reminders.json"):
        self.filepath = filepath
        self.reminders = self.load_reminders()
        self.lock = asyncio.Lock()

    def load_reminders(self):
        if os.path.exists(self.filepath):
            try:
                with open(self.filepath, "r") as f:
                    return json.load(f)
            except Exception as e:
                print(f"⚠️ Failed to load reminders: {e}")
        return []

    def save_reminders(self):
        try:
            with open(self.filepath, "w") as f:
                json.dump(self.reminders, f, indent=2)
        except Exception as e:
            print(f"⚠️ Failed to save reminders: {e}")

    async def add_reminder(self, time_str, message):
        """
        time_str: HH:MM (24h format)
        message: text
        """
        async with self.lock:
            # Parse HH:MM to get next occurrence
            now = time.localtime()
            try:
                hour, minute = map(int, time_str.split(":"))
                
                # Create timestamp for today at HH:MM
                target_today = time.mktime((now.tm_year, now.tm_mon, now.tm_mday, hour, minute, 0, now.tm_wday, now.tm_yday, now.tm_isdst))
                
                # If target is in past, move to tomorrow
                if target_today <= time.time():
                    target_ts = target_today + 86400
                else:
                    target_ts = target_today
                
                new_reminder = {
                    "id": str(int(time.time()*1000)), # Simple ID
                    "time_ts": target_ts,
                    "time_str": time_str,
                    "message": message,
                    "status": "PENDING" # PENDING, TRIGGERED, DISMISSED
                }
                self.reminders.append(new_reminder)
                self.save_reminders()
                print(f"⏰ Reminder Added: {message} at {time_str}")
                return True
            except Exception as e:
                print(f"❌ Date Parse Error: {e}")
                return False

    async def get_active_reminders(self):
        return [r for r in self.reminders if r["status"] != "DISMISSED"]

    async def dismiss_reminder(self, r_id):
        async with self.lock:
            for r in self.reminders:
                if r["id"] == r_id:
                    r["status"] = "DISMISSED"
                    self.save_reminders()
                    return True
            return False
            
    async def check_due(self):
        """Called periodically to check for due reminders"""
        now_ts = time.time()
        triggered = []
        async with self.lock:
            dirty = False
            for r in self.reminders:
                if r["status"] == "PENDING" and r["time_ts"] <= now_ts:
                    r["status"] = "TRIGGERED"
                    triggered.append(r)
                    dirty = True
            if dirty:
                self.save_reminders()
        return triggered

reminder_manager = ReminderManager()

# --- AUDIO STREAM HANDLERS ---
import functools

async def handle_audio_stream(request):
    """
    WebSocket endpoint for real-time audio partial transcription.
    """
    ws = web.WebSocketResponse()
    await ws.prepare(request)
    
    print("🎙️ Web Audio Stream Connected")
    
    # We will accumulate audio and run transcription periodically
    # Format: float32 PCM @ 16000Hz expected from client
    
    audio_buffer = np.array([], dtype=np.float32)
    last_transcribe_time = time.time()
    
    try:
        async for msg in ws:
            if msg.type == aiohttp.WSMsgType.BINARY:
                data = msg.data
                # Convert bytes (int16) to float32
                # Client sends Int16 (2 bytes per sample)
                chunk = np.frombuffer(data, dtype=np.int16).astype(np.float32) / 32768.0
                audio_buffer = np.concatenate((audio_buffer, chunk))
                
                # Check for silence/processing every 1s worth of data (16000 samples)
                # Or based on time
                now = time.time()
                if (now - last_transcribe_time) > 0.8: # Partial update every 800ms
                    last_transcribe_time = now
                    
                    if len(audio_buffer) > 4000: # Min 0.25s to transcribe
                        # Run Partial Transcription
                        # Beam size 1 for speed
                        try:
                            segments, _ = whisper_model_ref.transcribe(audio_buffer, beam_size=1, language="en")
                            text = "".join([s.text for s in segments]).strip()
                            if text:
                                await ws.send_json({"type": "partial", "text": text})
                        except Exception as e:
                            print(f"Partial Error: {e}")

            elif msg.type == aiohttp.WSMsgType.TEXT:
                # Client sends {"action": "stop"} or similar when they release the button
                cmd = json.loads(msg.data)
                if cmd.get("action") == "stop":
                    # FINAL RECOGNITION
                    print("🛑 Stream Ended. Finalizing...")
                    if len(audio_buffer) > 0:
                        try:
                            segments, _ = whisper_model_ref.transcribe(audio_buffer, beam_size=5, language="en") # Higher accuracy
                            text = "".join([s.text for s in segments]).strip()
                            await ws.send_json({"type": "final", "text": text})
                        except Exception as e:
                            print(f"Final Error: {e}")
                    # Clear buffer
                    audio_buffer = np.array([], dtype=np.float32)

            elif msg.type == aiohttp.WSMsgType.ERROR:
                print('ws connection closed with exception %s', ws.exception())

    except Exception as e:
        print(f"WebSocket Error: {e}")
    finally:
        print("🎙️ Web Audio Stream Closed")
    
    return ws




# --- AUDIO INPUT WORKER (FASTER-WHISPER + SR VAD) ---
mic_active_event = threading.Event()

def listen_local_mic_worker(loop, input_queue, model):
    """
    Background thread that:
    1. Uses SpeechRecognition for VAD (Listening until silence).
    2. Uses Faster-Whisper for Transcription (High Accuracy).
    """

    # 2. Init VAD (SpeechRecognition)
    r = sr.Recognizer()
    r.dynamic_energy_threshold = True
    r.pause_threshold = 1.0 # 1.0s silence = end of speech

    print("🎙️ Hybrid Listener (SR+Whisper) initialized (Paused)...")
    
    while True: # Hardware Reconnection Loop
        try:
            with sr.Microphone(sample_rate=16000) as source:
                print("✅ Mic Connected.")
                try:
                    # Short calibration
                    r.adjust_for_ambient_noise(source, duration=0.5) 
                except Exception as e:
                    print(f"⚠️ Calibration skipped: {e}")

                print("✅ Ready to Listen.")
                
                while True:
                    # CHECK FLAG: If not active, sleep
                    if not mic_active_event.is_set():
                        time.sleep(0.1)
                        continue
                    
                    try:
                        # 3. Capture Audio (VAD)
                        # Listen returns AudioData
                        audio_data = r.listen(source, timeout=1.5, phrase_time_limit=5.0)
                        
                        # 4. Transcribe (Whisper)
                        # Convert raw bytes (int16) to float32 numpy array
                        raw_data = audio_data.get_raw_data(convert_rate=16000, convert_width=2)
                        
                        # Convert to numpy float32, normalized to [-1, 1]
                        audio_np = np.frombuffer(raw_data, dtype=np.int16).astype(np.float32) / 32768.0
                        
                        segments, info = model.transcribe(audio_np, beam_size=5)
                        
                        text = ""
                        for segment in segments:
                            text += segment.text
                        
                        if text.strip():
                            print(f"\n🗣️ Whisper Heard: '{text}'")
                            loop.call_soon_threadsafe(input_queue.put_nowait, text)
                            
                    except sr.WaitTimeoutError:
                        pass # No speech, loop check flag
                    except Exception as e:
                        print(f"⚠️ Listener Error: {e}")
                        break # Break inner loop to re-initialize mic if needed
        
        except Exception as e:
            print(f"⚠️ Mic Init Fail: {sys.exc_info()[0]}. Retrying in 2s...")
            time.sleep(2.0)



# Removed wait_for_confirmation function as we want natural flow



# CONFIGURATION
SERVER_PORT = 4000
ARM_PORT = 4001  # New Port for Arms

# DEEPGRAM & OPENAI KEYS REMOVED - FULL LOCAL MODE
# If you need them back, check previous versions.

# Secondary API (Ollama on other PC) - UPDATE THIS IP
OLLAMA_IP = "192.168.137.205"
OLLAMA_BASE_URL = f"http://{OLLAMA_IP}:11434/v1"
# SWITCHING TO 1.5B MODEL (Emergency CPU Fix)
# The 7B model is choking your CPU (100% usage). 
# This 1.5B model is 5x faster and will work even without GPU.
# OLLAMA_MODEL = "qwen2.5:1.5b" 
OLLAMA_MODEL = "qwen2.5:7b-instruct"
# OLLAMA_MODEL = "qwen2.5:3b-instruct"
# ROBOT CALIBRATION
ROTATION_360_MS = 3200 
TURN_90_MS = ROTATION_360_MS // 4 

# GLOBAL CONNECTIONS
main_robot_socket = None
arm_robot_socket = None
command_queue_ref = None # Global reference for API access

# --- WEB SERVER HANDLERS ---
async def handle_index(request):
    return web.FileResponse('./static/index.html')

async def handle_status(request):
    return web.json_response(ROBOT_STATE)

async def handle_video_feed(request):
    """Streams MJPEG from latest_frame"""
    boundary = "frame"
    response = web.StreamResponse(
        status=200,
        reason='OK',
        headers={
            'Content-Type': f'multipart/x-mixed-replace;boundary={boundary}'
        }
    )
    await response.prepare(request)

    try:
        while True:
            if latest_frame:
                # Write boundary
                await response.write(f'--{boundary}\r\n'.encode('utf-8'))
                # Write headers
                await response.write(b'Content-Type: image/jpeg\r\n')
                await response.write(f'Content-Length: {len(latest_frame)}\r\n\r\n'.encode('utf-8'))
                # Write frame data
                await response.write(latest_frame)
                await response.write(b'\r\n')
                
                # Cap FPS roughly 20fps
                await asyncio.sleep(0.05)
            else:
                # No frame yet, wait
                await asyncio.sleep(0.1)
    except Exception as e:
        print(f"Video Stream Closed: {e}")
    
    return response

async def handle_move(request):
    global command_queue_ref, main_robot_socket
    try:
        data = await request.json()
        cmd = data.get('cmd')
        duration = int(data.get('duration', 0))
        
        print(f"\n🌐 WEB MOVE REQUEST RECEIVED:")
        print(f"   Command: {cmd}")
        print(f"   Duration: {duration}ms")
        print(f"   Queue exists: {command_queue_ref is not None}")
        print(f"   Socket exists: {main_robot_socket is not None}")
        
        if cmd and command_queue_ref:
            print(f"✅ Enqueueing command: {cmd} ({duration}ms)")
            await command_queue_ref.put((cmd, duration))
            print(f"✅ Command queued successfully!")
            return web.json_response({'status': 'ok'})
        else:
            error_msg = []
            if not cmd:
                error_msg.append("No command provided")
            if not command_queue_ref:
                error_msg.append("Command queue not initialized")
            print(f"❌ ERROR: {', '.join(error_msg)}")
            return web.json_response({'status': 'error', 'msg': ' | '.join(error_msg)}, status=400)
    except Exception as e:
        print(f"❌ EXCEPTION in handle_move: {e}")
        import traceback
        traceback.print_exc()
        return web.json_response({'status': 'error', 'msg': str(e)}, status=500)

async def handle_arm(request):
    global arm_robot_socket
    try:
        data = await request.json()
        action = data.get('action') # UP, DOWN, WAVE or LS:90
        
        if not action:
            return web.json_response({'error': 'Missing action'}, status=400)

        print(f"🦾 WEB ARM ACTION: {action}")
        
        # Macro Definitions
        macros = {
            "UP": ["LS:0", "RS:180", "LE:0", "RE:180"],
            "DOWN": ["LS:90", "RS:90", "LE:90", "RE:90"],
            "WAVE": ["RS:180", "RE:150", "RE:180"] 
        }
        
        cmds = []
        if action in macros:
            cmds = macros[action]
        elif re.match(r'^[A-Z]{2}:\d+$', action):
            # Direct Servo Command (e.g. LS:90)
            cmds = [action]
        else:
             return web.json_response({'error': 'Unknown Action or Invalid Format'}, status=400)
             
        if arm_robot_socket:
            for cmd in cmds:
                packet = f"{cmd}\n".encode('ascii')
                loop = asyncio.get_running_loop()
                await loop.sock_sendall(arm_robot_socket, packet)
                await asyncio.sleep(0.01) # Small gap
            return web.json_response({'status': 'executed'})
        else:
            return web.json_response({'status': 'error', 'msg': 'Arm not connected'}, status=503)

    except Exception as e:
         return web.json_response({'status': 'error', 'msg': str(e)}, status=500)

async def handle_chat(request):
    """
    Web chat endpoint - now uses the SAME logic as terminal/voice commands.
    Streams AI response to browser AND speaks to robot simultaneously.
    """
    global client_socket, command_queue_ref
    try:
        data = await request.json()
        user_text = data.get('text')
        
        if not user_text:
            return web.json_response({'error': 'No text provided'}, status=400)
            
        print(f"💬 WEB CHAT: {user_text}")
        
        # Prepare streaming response
        response = web.StreamResponse(
            status=200,
            reason='OK',
            headers={'Content-Type': 'text/plain'}
        )
        await response.prepare(request)
        
        # Define callback to stream tokens to browser
        async def stream_to_browser(token):
            try:
                await response.write(token.encode('utf-8'))
            except Exception as e:
                print(f"⚠️ Browser stream error: {e}")
        
        # Call the SAME function used by terminal/voice commands
        # This will:
        # - Load robot knowledge (if needed)
        # - Execute commands
        # - Speak to robot (TTS)
        # - Stream to browser (via callback)
        try:
            # Wrap process_interaction to capture streaming
            # We need to pass token_callback through the chain
            # But process_interaction doesn't expose token_callback directly
            # So let's call the underlying functions ourselves
            
            # For now, let's call process_interaction and it will speak
            # We'll modify it to also stream
            await process_interaction(user_text, client_socket, command_queue_ref, web_stream_callback=stream_to_browser)
            
        except TypeError:
            # Fallback if process_interaction doesn't support web_stream_callback yet
            # We'll need to modify process_interaction to accept this parameter
            print("⚠️ Need to update process_interaction signature")
            await response.write(b"Processing...")
        
        # Close stream
        await response.write_eof()
        return response

    except Exception as e:
        print(f"❌ Chat Error: {e}")
        import traceback
        traceback.print_exc()
        return web.json_response({'status': 'error', 'msg': str(e)}, status=500)

async def handle_stop(request):
    """
    Instantly stops the robot from speaking by incrementing interaction ID.
    """
    global current_interaction_id
    current_interaction_id += 1
    print(f"🛑 STOP REQUEST RECEIVED (New ID: {current_interaction_id})")
    return web.json_response({'status': 'stopped', 'new_id': current_interaction_id})

async def handle_get_reminders(request):
    reminders = await reminder_manager.get_active_reminders()
    return web.json_response(reminders)

async def handle_dismiss_reminder(request):
    try:
        data = await request.json()
        r_id = data.get('id')
        if await reminder_manager.dismiss_reminder(r_id):
            return web.json_response({'status': 'ok'})
        return web.json_response({'status': 'error', 'msg': 'Not found'}, status=404)
    except Exception as e:
        return web.json_response({'status': 'error', 'msg': str(e)}, status=500)

async def start_web_server(loop, command_queue, model_ref):
    global command_queue_ref, whisper_model_ref
    command_queue_ref = command_queue
    whisper_model_ref = model_ref
    
    app = web.Application()
    app.router.add_get('/', handle_index)
    app.router.add_get('/video_feed', handle_video_feed)
    app.router.add_get('/api/status', handle_status)
    app.router.add_post('/api/move', handle_move)
    app.router.add_post('/api/arm', handle_arm)
    app.router.add_post('/api/chat', handle_chat)
    app.router.add_post('/api/stop', handle_stop)
    app.router.add_get('/api/reminders', handle_get_reminders)
    app.router.add_post('/api/reminders/dismiss', handle_dismiss_reminder)
    app.router.add_get('/api/audio_stream', handle_audio_stream) # NEW WebSocket
    
    # Serve static files (css, js) explicitly
    app.router.add_static('/static', './static')

    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, '0.0.0.0', 8080)
    await site.start()
    print("🌐 Web Interface Started: http://localhost:8080")

# INIT TTS ENGINE (One time)
# Note: pyttsx3 is not async friendly so we run it in executor/thread
def init_tts_engine():
    engine = pyttsx3.init()
    voices = engine.getProperty('voices')
    # Set to Zira (usually index 1)
    for voice in voices:
        if "zira" in voice.name.lower():
            engine.setProperty('voice', voice.id)
            break
    engine.setProperty('rate', 170) # Slightly faster
    return engine

    return engine

# =========================================================
# VISION NODE INTEGRATION (Receiver Classes)
# =========================================================
class PacketReceiver:
    """Handles receiving and parsing network packets from Vision Node"""
    def __init__(self, sock):
        self.sock = sock
        self.buffer = b""

    def recv_exact(self, size):
        """Receive exact number of bytes"""
        data = b""
        while len(data) < size:
            chunk = self.sock.recv(size - len(data))
            if not chunk:
                raise ConnectionError("Connection closed")
            data += chunk
        return data

    def recv_packet(self):
        """Receive and parse one packet"""
        # Read header: [MAGIC:2][TYPE:1][SIZE:4]
        try:
            header = self.recv_exact(7)
        except ConnectionError:
            return None, None
            
        magic, pkt_type, size = struct.unpack(">2sBI", header)

        if magic != b'RV':
            raise ValueError(f"Invalid magic bytes: {magic}")

        # Read payload
        payload = self.recv_exact(size)
        return pkt_type, payload

class ObstacleHandler:
    """Processes obstacle signals and triggers motor commands"""
    def __init__(self, command_queue, loop):
        self.command_queue = command_queue
        self.loop = loop
        self.last_obstacle_time = 0

    def handle_obstacle(self, data):
        zone = data.get("zone", "UNKNOWN")
        distance = data.get("distance", 0)
        
        # Log
        print(f"🚨 OBSTACLE: {zone} ({distance}cm)")
        
        # Decide Action
        command = None
        if distance < 30:
            command = "CMD:S" # Emergency Stop
        elif distance < 55:
            if zone == "CENTER":
                all_zones = data.get("all_zones", {})
                left = all_zones.get("left", 9999)
                right = all_zones.get("right", 9999)
                command = "CMD:L:500" if left > right else "CMD:R:500"
            elif zone == "LEFT":
                 command = "CMD:R:400"
            elif zone == "RIGHT":
                 command = "CMD:L:400"
        
        if command:
            print(f"🤖 AVOIDANCE ACION: {command}")
            # Inject into command queue (High Priority)
            # define tuple (cmd_char, duration_ms)
            # But wait, our queue expects (char, duration).
            # We need to parse "CMD:L:500" -> ('L', 500)
            
            parts = command.split(":") 
            # CMD:S -> parts[1]=S
            # CMD:L:500 -> parts[1]=L, parts[2]=500
            
            if len(parts) >= 2:
                char = parts[1]
                dur = int(parts[2]) if len(parts) > 2 else 0
                self.loop.call_soon_threadsafe(self.command_queue.put_nowait, (char, dur))

# We can't keep engine open in global scope easily with threading rules sometimes
# But generally okay. 

# llm_client removed (was for OpenAI)

# CONVERSATION MEMORY (DISABLED FOR SPEED - Robot commands don't need context)
conversation_history = []
MAX_HISTORY_TURNS = 0  # Disabled for minimal latency

# KNOWLEDGE BASE DISABLED FOR MAXIMUM SPEED
# Robot will not know who created it, but will respond INSTANTLY
ROBOT_KNOWLEDGE_GLOBAL = ""
# Commented out for speed:
# try:
#     with open("robot_knowledge.txt", "r", encoding="utf-8") as f:
#         ROBOT_KNOWLEDGE_GLOBAL = f.read()
#     print("📚 Robot Knowledge Pre-loaded Successfully!")
# except Exception as e:
#     print(f"⚠️ Could not load robot_knowledge.txt: {e}")
#     ROBOT_KNOWLEDGE_GLOBAL = ""
print("⚡ Knowledge Base DISABLED - Maximum Speed Mode!")

async def get_ollama_stream(messages):
    print(f"🔄 Switching to Local Ollama ({OLLAMA_IP}) [STREAMING]...")
    try:
        
        ollama_client = AsyncOpenAI(
            base_url=OLLAMA_BASE_URL,
            api_key="ollama",
            timeout=60.0  # CLIENT-LEVEL timeout (prevents 10s default disconnect)
        )
        
        stream = await ollama_client.chat.completions.create(
            model=OLLAMA_MODEL,
            messages=messages,
            stream=True,
            timeout=60.0,  # Request-level timeout
            extra_body={
                "num_predict": 15,  # ULTRA SHORT - max 15 tokens (~10 words)
                "temperature": 0.4,  # Moderate creativity for arm reasoning
                "top_p": 0.7,  # Allow some exploration for angles
                "repeat_penalty": 1.3  # Punish long explanations
            }
        )
        return stream
        
    except Exception as e:
        print(f"❌ Ollama Conn Fail: {e}")
        return None

async def speak_text(text, client_socket, interaction_id):
    """Generates Local TTS (pyttsx3) and streams it to the ESP32."""
    if not text.strip(): return
    
    # Filter out junk (like ">", ":", " ", punctuation only)
    if not re.search(r'[a-zA-Z0-9]', text):
        return

    try:
        # Run synchronous pyttsx3 in a thread to avoid blocking asyncio loop
        def generate_audio():
            engine = pyttsx3.init() # Init strictly inside thread for safety
            voices = engine.getProperty('voices')
            for voice in voices:
                if "zira" in voice.name.lower():
                    engine.setProperty('voice', voice.id)
                    break
            engine.setProperty('rate', 170)
            
            # Use unique filename to prevent permission conflicts
            import uuid
            temp_file = f"temp_tts_{uuid.uuid4().hex[:8]}.wav"
            engine.save_to_file(text, temp_file)
            engine.runAndWait() # Process
            return temp_file

        temp_file = await asyncio.to_thread(generate_audio)
        
        # Open and process audio
        with wave.open(temp_file, 'rb') as wf:
            params = wf.getparams()
            channels = params.nchannels
            rate = params.framerate
            width = params.sampwidth
            frames = wf.readframes(params.nframes)
            
        # Resample to 16000Hz if needed
            
        # Resample to 16000Hz if needed using NumPy
        if rate != 16000:
            # Convert bytes to numpy array (int16)
            audio_data = np.frombuffer(frames, dtype=np.int16)
            
            # If stereo, process each channel or mix down first
            if channels == 2:
                # Reshape to (frames, 2)
                audio_data = audio_data.reshape(-1, 2)
                # Mix to mono for simplicity (avg)
                audio_data = audio_data.mean(axis=1).astype(np.int16)
                channels = 1
                
            # Calculate new length
            duration = len(audio_data) / rate
            new_length = int(duration * 16000)
            
            if new_length == 0: return # Prevent crash on empty audio
            
            # Simple Linear Interpolation
            x_old = np.linspace(0, len(audio_data), len(audio_data))
            x_new = np.linspace(0, len(audio_data), new_length)
            
            resampled_data = np.interp(x_new, x_old, audio_data).astype(np.int16)
            bytes_buffer = resampled_data.tobytes()
        else:
            bytes_buffer = frames

        # Convert Stereo to Mono for simple transmission if needed (or keep stereo)
        # ESP32 expects whatever we send. Our sketch handles stereo/mono mixing 
        # But wait, audioop.ratecv returns raw bytes.
        # If origin is stereo, it resamples stereo.
        
        # Stream the buffer directly
        # Convert bytes_buffer to IO stream for compatibility with existing function logic?
        # No, existing function expects stream.read().
        # Let's just create a BytesIO
        
        byte_stream = io.BytesIO(bytes_buffer)
        await stream_audio_to_esp32(byte_stream, client_socket, interaction_id)
        
        # Cleanup
        try:
            os.remove(temp_file)
        except:
            pass
        
    except Exception as e:
        print(f"  ⚠️ TTS Error: {e}")
        traceback.print_exc()

async def command_execution_worker(client_socket, command_queue):
    """
    Background worker that executes commands sequentially.
    Crucially, it waits for the duration of each command before processing the next,
    ensuring the robot finishes the movement.
    """
    print("🤖 Command Execution Worker Started")
    while True:
        try:
            # Get command from queue
            cmd_char, duration = await command_queue.get()
            
            # Construct Packet
            if duration > 0:
                cmd_packet = f"CMD:{cmd_char}:{duration}\n".encode('ascii')
            else:
                cmd_packet = f"CMD:{cmd_char}\n".encode('ascii')

            # Send to Robot
            loop = asyncio.get_event_loop()
            try:
                if client_socket:
                    await loop.sock_sendall(client_socket, cmd_packet)
                else:
                    print("⚠️ Robot not connected, command skipped.")

                if duration > 0:
                    print(f"🤖 Executing: {cmd_char} for {duration}ms (Waiting...)")
                    # Wait for physical execution + small buffer
                    await asyncio.sleep(duration / 1000.0) 
                else:
                    print(f"🤖 Executing: {cmd_char} (Instant)")
            except Exception as e:
                print(f"⚠️ Command Send Error: {e}")

            command_queue.task_done()
            
        except asyncio.CancelledError:
            break
        except Exception as e:
            print(f"⚠️ Command Worker Error: {e}")
            await asyncio.sleep(1.0)

async def stream_audio_to_esp32(audio_stream, client_socket, interaction_id):
    """Reads audio stream and writes to TCP socket with chunking and gain."""
    audio_data = audio_stream.read() 
    if not audio_data: return

    # Optimized chunk size for WiFi - Tuned to 1024 to balance throughput and latency (reduce jitter)
    CHUNK_SIZE = 1024
    for i in range(0, len(audio_data), CHUNK_SIZE):
        chunk = audio_data[i:i+CHUNK_SIZE]
        
        # Apply Digital Gain (1.5x for moderate volume)
        if len(chunk) % 2 == 0:
            count = len(chunk) // 2
            shorts = struct.unpack(f'<{count}h', chunk)
            # Clamp to 16-bit range
            amplified = [max(-32768, min(32767, int(s * 3))) for s in shorts]
            chunk = struct.pack(f'<{len(amplified)}h', *amplified)
        
        try:
            # Check for Interruption
            if interaction_id != current_interaction_id:
                print(f"🚫 Stream Interrupted (ID: {interaction_id} vs {current_interaction_id})")
                break

            if client_socket:
                await asyncio.get_event_loop().sock_sendall(client_socket, chunk)
            else:
                 # Robot offline, just simulate delay
                 pass
            # Minimal sleep to yield control, but fast enough to keep buffer full
            await asyncio.sleep(0.001)  
        except Exception as e:
            print(f"  ⚠️ Send Error: {e}")
            break

async def process_llm_stream(stream, client_socket, request_start_time, command_queue, interaction_id, token_callback=None):
    """Consumes the LLM stream, buffers sentences, and speaks them."""
    full_text = ""
    sentence_buffer = ""
    print("▶️ Starting Stream Output...")
    
    first_token_received = False
    start_play_time = None
    command_finish_time = 0 # Timestamp when the current/last physical movement will finish

    async for chunk in stream:
        # Check Interruption
        if interaction_id != current_interaction_id:
            print("🚫 LLM Stream Cancelled (New Interaction)")
            return full_text

        content = chunk.choices[0].delta.content
        if content:
            if not first_token_received:
                ttft = time.time() - request_start_time
                print(f"⚡ Time to First Char: {ttft:.2f}s")
                first_token_received = True

            # Call callback if provided (for Web Streaming)
            if token_callback:
                await token_callback(content)

            sentence_buffer += content
            full_text += content
            
            # DEBUG: Print raw content to see if tags exist
            print(f"Raw: {content!r}") 

            while True:
                # --- IMMEDIATE COMMAND CHECK ---
                # Regex matches: <cmd:F:1000> OR <cmd:R:360deg> OR <cmd:ARM:LS:90>
                # Unified Regex: Listen for TWO types: 
                # 1. WHEEL: cmd:F:1000
                # 2. ARM:   cmd:LS:90
                
                cmd_match = re.search(
                    r'(?:<|\(|^)cmd:\s*([A-Z]{1,2})(?:[: ]((\d+)(deg|degrees)?|(\d+)ms))?(?:>|\))', 
                    sentence_buffer, 
                    re.IGNORECASE
                )
                
                if not cmd_match:
                    break # No more commands in buffer

                cmd_part = cmd_match.group(1).upper() # F, B, LS, RS...
                full_tag = cmd_match.group(0)
                val_str = cmd_match.group(2)
                
                # Check if it is an ARM command (2 letters like LS, RS, LE, RE, LW, RW, LG, RG)
                is_arm = len(cmd_part) == 2 and cmd_part in ["LS", "RS", "LE", "RE", "LW", "RW", "LG", "RG"]
                
                # Parse value
                value = 0
                if val_str:
                     num_match = re.search(r'(\d+)', val_str)
                     if num_match: value = int(num_match.group(1))

                if is_arm:
                    print(f"🦾 ARM COMMAND: {cmd_part} -> {value}")
                    # Send directly to Arm Socket
                    if arm_robot_socket:
                        try:
                            # Format expected by ESP32: "LS:90\n"
                            packet = f"{cmd_part}:{value}\n".encode('ascii')
                            # Ensure we don't break async (sock_sendall is async in loop)
                            loop = asyncio.get_running_loop()
                            loop.call_soon_threadsafe(lambda: arm_robot_socket.sendall(packet))
                            # OR better: await loop.sock_sendall(arm_robot_socket, packet)
                            # But we are in async parsing loop, so we can await?
                            # Actually, process_llm_stream is async.
                            await loop.sock_sendall(arm_robot_socket, packet)
                        except Exception as e:
                            print(f"⚠️ Arm Send Failed: {e}")
                    else:
                        print("⚠️ Arm Not Connected!")
                
                else:
                    # EXISTING WHEEL LOGIC
                    cmd_char = cmd_part # F, B, L, R, S
                    duration = value
                    
                    # Degree conversion for wheels
                    if val_str and 'deg' in val_str.lower() and cmd_char in ['L', 'R']:
                         duration = int((value / 360.0) * ROTATION_360_MS)
                    
                    print(f"🤖 COMMAND FOUND: {cmd_char} Time:{duration}ms")
                    await command_queue.put((cmd_char, duration))
                
                # Remove the tag from the buffer
                sentence_buffer = sentence_buffer.replace(full_tag, "", 1)
            
            # --- REMINDER CHECK ---
            # Parses <remind:17:00:Drink water>
            remind_match = re.search(r'(?:<|\(|^)remind:(\d{1,2}:\d{2}):([^>]+)(?:>|\))', sentence_buffer, re.IGNORECASE)
            if remind_match:
                r_time = remind_match.group(1)
                r_msg = remind_match.group(2).strip()
                full_tag_r = remind_match.group(0)
                
                print(f"⏰ REMINDER DETECTED: {r_msg} at {r_time}")
                await reminder_manager.add_reminder(r_time, r_msg)
                
                sentence_buffer = sentence_buffer.replace(full_tag_r, "", 1)

            while True:
                # Check for first sentence delimiter
                match = re.search(r'([.!?\n]+)(?:\s|$)', sentence_buffer)
                if match:
                    parts = re.split(r'([.!?\n]+(?:\s|$))', sentence_buffer, maxsplit=1)
                    if len(parts) >= 3:
                        sentence_chunk = parts[0] + parts[1]
                        remainder = parts[2]
                        
                        # Process text (speak)
                        # We don't need process_text_chunk for commands anymore, just TTS
                        # But we still need to clean markdown
                        
                        spoken_text = re.sub(r'[*_#]', '', sentence_chunk).strip()
                        
                        if spoken_text:
                            if not start_play_time: start_play_time = time.time()
                            print(f"🗣️: {spoken_text}")
                            await speak_text(spoken_text, client_socket, interaction_id)
                        
                        sentence_buffer = remainder 
                        continue 
                break 

    # Flush remainder
    if sentence_buffer.strip():
        spoken_text = re.sub(r'[*_#]', '', sentence_buffer).strip()
        if spoken_text:
            print(f"🗣️: {spoken_text}")
            await speak_text(spoken_text, client_socket, interaction_id)
        
    return full_text


async def process_interaction(text, client_socket, command_queue, web_stream_callback=None):
    global conversation_history, current_interaction_id
    
    # 1. New Interaction Started -> Increment ID
    current_interaction_id += 1
    my_interaction_id = current_interaction_id
    print(f"🆔 Interaction ID: {my_interaction_id} Started")

    if not text.strip(): return
    
    start_time = time.time()
    print(f"\n🤔 Thinking... [Input: {text}]")
    ai_text = ""
    
    # Knowledge base DISABLED for speed - robot_knowledge always empty
    robot_knowledge = ""
    print("⚡ Knowledge Disabled (Speed Mode)")

    # --- SMART WEATHER: CITY DETECTION ---
    lower_text = text.lower()
    weather_keywords = ["weather", "temperature", "forecast", "hot", "cold", "rain", "sunny", "location", "where am i", "which city"]
    
    # Use regex to match WHOLE WORDS only (avoids "hot" in "photosynthesis")
    # \b matches word boundaries
    pattern = r"\b(" + "|".join(re.escape(k) for k in weather_keywords) + r")\b"
    
    if re.search(pattern, lower_text):
        print("🌤️ Weather Intent Detected...")
        try:
            g = geocoder.ip('me')
            detected_current_city = g.city if g.city else "Kathmandu"
        except:
            detected_current_city = "Kathmandu"
            
        target_city = detected_current_city
        city_match = re.search(r'\b(in|at|for|of)\s+([a-zA-Z]+)', text, re.IGNORECASE)
        forced_city = None
        
        if city_match:
            detected = city_match.group(2)
            if detected.lower() not in ["the", "a", "my", "your", "today", "now", "here", "this"]:
                forced_city = detected
                target_city = forced_city
        
        try:
            # CASE A: User asks about LOCATION
            if not forced_city and any(k in lower_text for k in ["location", "where am i", "which city", "where are you"]):
                response_text = f"I am currently located in {detected_current_city}."
                await speak_text(response_text, client_socket, my_interaction_id)
                return

            # CASE B: User asks about WEATHER
            async def get_weather(city_name):
                async with python_weather.Client(unit=python_weather.METRIC) as client:
                    weather = await client.get(city_name) 
                    temp = getattr(weather, 'temperature', 'N/A')
                    desc = getattr(weather, 'description', getattr(weather, 'kind', 'Unknown'))
                    return f"{temp} degrees Celsius and {desc}"
            
            weather_report = await get_weather(target_city)
            city_display = target_city if target_city else detected_current_city
            response_text = f"The current weather in {city_display} is {weather_report}."
            await speak_text(response_text, client_socket, my_interaction_id)
            return
            
        except Exception as e:
            print(f"⚠️ Weather Fetch Failed: {e}")

    # REASONING-BASED PROMPT - LLM chooses angles based on understanding
    current_time_str = time.strftime("%H:%M")
    system_prompt = {
        "role": "system", 
        "content": (
            f"Current Time: {current_time_str}. "
            "ROVA robot with mic+speaker. Built by 6 students (Sushant Bhandari, Neema Sherpa, Uttam Shrestha, Nishant Bhandari, Prithivi Raiymajhi, Subash Shrestha) at Takshashila Academy, Kathmandu. Principal: Mrs. Netra Neupane.\n"
            "Commands: brief+tag. Questions: 1 sentence.\n\n"
            
            "MOVEMENT: <cmd:F:1000>=fwd 1s | <cmd:L:90deg>=left 90° | <cmd:S>=stop\n\n"
            
            "ARMS - Understand the physics and choose angles:\n"
            "• LS/RS (shoulder): 0°=raised/front, 90°=neutral side, 180°=raised/front(opposite)\n"
            "• LE/RE (elbow): 0°=straight/extended, 90°=bent 90°, 180°=fully bent\n"
            "• LW/RW (wrist): rotates outward (0°) or inward (180°)\n"
            "• LG/RG (gripper): 0°=closed tight, 40°=OPEN (Do not exceed 40°)\n\n"
            
            "Physical Defaults: Shoulders=90, Elbows(L=0, R=180), Grippers=0.\n"
            "Think about what makes sense:\n"
            "- 'hands off/down' = return to defaults\n"
            "- 'hands up/raised' = shoulders up(0° left, 180° right), elbows straight(0° left, 180° right)\n"
            "- 'wave' = shoulder stable, elbow alternating\n"
            "- 'grab/close' = gripper closes to 0°\n"
            "- 'release/open' = gripper opens to 40°\n\n"

            "REMINDERS: Output <remind:HH:MM:Message> (24h format) for requests like 'Remind me to X at 5pm'.\n"
            "Example: 'Remind me to drink water at 5 PM' -> <remind:17:00:Drink water> Okay, set.\n"
            "If user says 'in 10 minutes', calculate FUTURE time based on Current Time.\n"
            
            "REASON about the motion, don't just copy patterns. Be creative!"
        )
    }

    examples = [
        {"role": "user", "content": "Move forward"},
        {"role": "assistant", "content": "<cmd:F:2000> On it."},
        {"role": "user", "content": "Hands down"},
        {"role": "assistant", "content": "<cmd:LS:90><cmd:RS:90><cmd:LE:45><cmd:RE:45> Lowered."},
    ]
    
    # Build message context (EXCLUDE history if disabled for speed)
    if MAX_HISTORY_TURNS > 0:
        current_messages = [system_prompt] + examples + conversation_history + [{"role": "user", "content": text}]
    else:
        # ZERO HISTORY MODE - Only send system, examples, and current question (fast!)
        current_messages = [system_prompt] + examples + [{"role": "user", "content": text}]
    
    print(f"🧠 Context Size: {len(current_messages)} messages")
    print(f"🚀 Using Local Ollama ({OLLAMA_MODEL})...")
    llm_start = time.time()
    
    # CALL OLLAMA DIRECTLY
    try:
        stream = await get_ollama_stream(current_messages)
        if stream:
            # Immediate Terminal Feedback + Web Stream (if from browser)
            async def on_terminal_token(token):
                print(token, end='', flush=True)
                # Also stream to web browser if callback provided
                if web_stream_callback:
                    await web_stream_callback(token)

            print("🤖 AI: ", end='', flush=True) 
            ai_text = await process_llm_stream(stream, client_socket, llm_start, command_queue, my_interaction_id, token_callback=on_terminal_token)
            print("") # Newline

    except Exception as e:
        print(f"❌ LLM Error: {e}")

    duration = time.time() - llm_start
    print(f"⏱️ Total Interaction: {duration:.2f}s")
    
    # Update memory
    conversation_history.append({"role": "user", "content": text})
    if ai_text:
        conversation_history.append({"role": "assistant", "content": ai_text})
    
    # Keep only last N turns
    if len(conversation_history) > (MAX_HISTORY_TURNS * 2):
        conversation_history = conversation_history[-(MAX_HISTORY_TURNS * 2):]


async def main():
    global arm_robot_socket, ROBOT_STATE, client_socket
    try:
        # --- 0. PRE-CHECK MODEL & KNOWLEDGE ---
        # Load robot knowledge base FIRST (Needed for warmup)
        robot_knowledge = ""
        # try:
        #     with open("robot_knowledge.txt", "r", encoding="utf-8") as f:
        #         robot_knowledge = f.read()
        #     print("✅ Knowledge Base Loaded")
        # except:
        #     print("⚠️ Knowledge Base NOT Found (Using empty)")
        #     pass

        local_model_path = r"e:\music\tiny_model"
        model_file = os.path.join(local_model_path, "model.bin")
        
        if os.path.exists(model_file):
            print(f"✅ Found Local Manual Download at: {local_model_path}")
            model_path = local_model_path
        else:
            # Fallback to library download if manual failed/missing
            print("\n⏳ Checking AI Brain (tiny.en)...")
            try:
                model_path = download_model("tiny.en")
                print(f"✅ AI Brain found at: {model_path}")
            except Exception as e:
                print(f"❌ Critical Download Error: {e}")
                print("Try running 'manual_download.py' manually!")
                return

        # Create TCP Server
        server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        server_socket.bind(('0.0.0.0', SERVER_PORT))
        server_socket.listen(1)
        server_socket.setblocking(False)
        
        print(f"📡 TCP Server Started on Port {SERVER_PORT}")
        print("will auto-reconnect if ESP32 drops.")

        # --- ARM SERVER SETUP ---
        arm_server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        arm_server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        arm_server.bind(('0.0.0.0', ARM_PORT))
        arm_server.listen(1)
        arm_server.setblocking(False)
        print(f"💪 Arm Server Started on Port {ARM_PORT}")

        # Worker to accept Arm connections
        async def arm_acceptor():
            global arm_robot_socket
            loop = asyncio.get_running_loop()
            while True:
                try:
                    conn, addr = await loop.sock_accept(arm_server)
                    print(f"✅ ARM CONNECTED: {addr}")
                    print(f"✅ ARM CONNECTED: {addr}")
                    arm_robot_socket = conn
                    ROBOT_STATE["arm_connected"] = True
                    
                    # Spawn listener for this arm connection
                    async def listen_arm(s):
                        buf = b""
                        try:
                            while True:
                                data = await loop.sock_recv(s, 1024)
                                if not data: break
                                buf += data
                                try:
                                    decoded = buf.decode('utf-8', errors='ignore')
                                    if "TEMP:" in decoded:
                                        parts = decoded.split("TEMP:")
                                        if len(parts) > 1:
                                            val_str = parts[1].split("\n")[0].strip()
                                            try: ROBOT_STATE["temp_arms"] = float(val_str)
                                            except: pass
                                        buf = b""
                                except: pass
                        except: pass
                        print(f"❌ ARM DISCONNECTED")
                        ROBOT_STATE["arm_connected"] = False
                    
                    asyncio.create_task(listen_arm(conn))
                except Exception as e:
                    print(f"Arm Accept Error: {e}")
                    await asyncio.sleep(1)

        asyncio.create_task(arm_acceptor())

        # --- COMMAND QUEUE ---
        command_queue = asyncio.Queue()

        # --- 1. Load Whisper Model (ONCE at Startup) ---
        print("⏳ Initializing Whisper Model in Memory...")
        try:
            # Use the path we verified/downloaded above
            whisper_model = await asyncio.to_thread(WhisperModel, model_path, device="cpu", compute_type="int8")
            print("✅ Whisper Model Ready!")
        except Exception as e:
            print(f"❌ Memory Load Fail: {e}")
            sys.exit(1) # Fail fast if no brain

        # --- START WEB SERVER ---
        # Pass whisper_model to the server starter
        await start_web_server(asyncio.get_running_loop(), command_queue, whisper_model)

        
        while True: # --- RECONNECTION LOOP ---
            print("\n⏳ Waiting for ESP32 to connect...")
            
            try:
                # Accept connection
                loop = asyncio.get_event_loop()
                client_socket, addr = await loop.sock_accept(server_socket)
                
                # Set socket options
                client_socket.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
                client_socket.setsockopt(socket.SOL_SOCKET, socket.SO_KEEPALIVE, 1)
                print(f"✅ ESP32 Connected from {addr}")
                ROBOT_STATE["esp32_connected"] = True
            
                # Background task to listen for ESP32 messages (like BLOCKED or TEMP)
                async def listen_for_esp32_messages():
                    buffer = b""
                    try:
                        while True:
                            data = await loop.sock_recv(client_socket, 1024)
                            if not data:
                                print("\n⚠️ ESP32 Disconnected (EOF)")
                                ROBOT_STATE["esp32_connected"] = False
                                break
                            
                            buffer += data
                            
                            # Handle BLOCKED
                            if b"BLOCKED:" in buffer:
                                print("\n⚠️ ROBOT BLOCKED BY OBSTACLE!")
                                await speak_text("Obstacle detected, cannot move forward.", client_socket)
                                buffer = buffer.replace(b"BLOCKED:", b"") # Consume
                                
                            # Handle TEMP (Format: TEMP:45.2\n)
                            # Simple regex or split could work, but let's try direct parsing if frame is clean
                            try:
                                decoded = buffer.decode('utf-8', errors='ignore')
                                if "TEMP:" in decoded:
                                    parts = decoded.split("TEMP:")
                                    if len(parts) > 1:
                                        # Take the part after TEMP:
                                        val_str = parts[1].split("\n")[0].strip()
                                        try:
                                            ROBOT_STATE["temp_legs"] = float(val_str)
                                            # print(f"Legs Temp: {val_str}")
                                        except: pass
                                    buffer = b"" # Clear buffer after successful parse
                            except: pass
                                
                    except Exception as e:
                        print(f"\n⚠️ ESP32 Listener Error: {e}")
                        ROBOT_STATE["esp32_connected"] = False
                        # Note: We rely on the main loop to catch the socket error and close everything

                listener_task = asyncio.create_task(listen_for_esp32_messages())

                # --- VISION SERVER (LISTENER) ---
                # Listens for the separate vision_node.py connection
                def vision_server_worker(loop, cmd_queue):
                    VISION_PORT = 5000
                    v_server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                    v_server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
                    try:
                        v_server.bind(('0.0.0.0', VISION_PORT))
                        v_server.listen(1)
                        print(f"👁️ Vision Server Listening on Port {VISION_PORT}...")
                    except Exception as e:
                        print(f"❌ Vision Server Bind Failed: {e}")
                        return

                    while True:
                        try:
                            client_sock, addr = v_server.accept()
                            print(f"✅ Vision Node Connected from {addr}")
                            ROBOT_STATE["vision_connected"] = True
                        except Exception as e:
                            print(f"Vision Accept Error: {e}")
                            break
                        
                        receiver = PacketReceiver(client_sock)
                        handler = ObstacleHandler(cmd_queue, loop)
                        
                        while True:
                            try:
                                pkt_type, payload = receiver.recv_packet()
                                if pkt_type is None: break # Closed
                                
                                if pkt_type == 1: # Video Frame
                                    global latest_frame
                                    latest_frame = payload
                                    # DEBUG: Print dot every 60 frames to confirm receipt
                                    # if int(time.time()) % 5 == 0: print(".", end="", flush=True) 
                                    
                                elif pkt_type == 2: # JSON Signal
                                    signal = json.loads(payload.decode('utf-8'))
                                    if signal.get("type") == "OBSTACLE":
                                        data = signal.get("data", {})
                                        handler.handle_obstacle(data)
                                        # Update State
                                        ROBOT_STATE["obstacle_type"] = data.get("label", "None")
                                        ROBOT_STATE["obstacle_dist"] = data.get("distance", 0)
                                        
                            except Exception as e:
                                print(f"Vision Data Error: {e}")
                                break
                                
                        print(f"⚠️ Vision Node Disconnected")
                        ROBOT_STATE["vision_connected"] = False
                        client_sock.close()
                            

                # START VISION SERVER THREAD (after function is defined)
                import threading
                vision_thread = threading.Thread(
                    target=vision_server_worker,
                    args=(loop, command_queue),
                    daemon=True
                )
                vision_thread.start()
                print("👁️ Vision Server Thread Started - Listening on port 5000...")

                # --- REMINDER CHECKER TASK ---
                async def reminder_worker():
                    print("⏰ Reminder Worker Started")
                    while True:
                        try:
                            bg_triggered = await reminder_manager.check_due()
                            if bg_triggered:
                                for r in bg_triggered:
                                    msg = f"Reminder: {r['message']}"
                                    print(f"🔔 ALARM: {msg}")
                                    # Speak using the captured client_socket
                                    asyncio.create_task(speak_text(msg, client_socket, 999))
                        except Exception as e:
                            print(f"Reminder Error: {e}")
                        await asyncio.sleep(1) # Check every second

                reminder_task = asyncio.create_task(reminder_worker())

                try: # --- CHAT LOOP ---
                    # Restart Worker Task with new socket
                    cmd_worker_task = asyncio.create_task(command_execution_worker(client_socket, command_queue))
                    print("\n💬 INTERACTION MODE ACTIVE")
                    
                    input_queue = asyncio.Queue()
                    
                    mic_thread = threading.Thread(
                        target=listen_local_mic_worker, 
                        args=(loop, input_queue, whisper_model), 
                        daemon=True
                    )
                    mic_thread.start()
                    
                    while True:
                        # 1. Ask User for Mode
                        print("\n----------------------------------")
                        print("Choose Input Method:")
                        print("  [T] Type")
                        print("  [M] Microphone")
                        print("----------------------------------")
                        
                        mode_str = await asyncio.to_thread(input, "Selection (t/m): ")
                        mode = mode_str.strip().lower()
                        
                        text_to_process = ""
                        
                        if mode == 'q' or mode == 'quit':
                            break
                        
                        if mode == 'm':
                            print("🎤 Listening... (Speak now)")
                            # Enable Mic
                            mic_active_event.set()
                            
                            # Wait for ONE input from queue (from Mic)
                            # We might accept multiple? No, user implied one turn.
                            text_to_process = await input_queue.get()
                            
                            # Disable Mic immediately after hearing
                            mic_active_event.clear()
                            
                        else: # Default to Typing
                            text_to_process = await asyncio.to_thread(input, "⌨️ You: ")
                        
                        if not text_to_process.strip():
                            continue

                        # 2. Process Immediately (Natural Flow)
                        print(f"✅ Processing: '{text_to_process}'")
                        await process_interaction(text_to_process, client_socket, command_queue)


                        
                except (ConnectionResetError, BrokenPipeError, ConnectionAbortedError) as conn_e:
                    print(f"⚠️ Connection Lost: {conn_e}")
                except Exception as e:
                    print(f"⚠️ Error in session: {e}")
                    traceback.print_exc()
                finally:
                    current_esp32_socket = None
                    # Clean up this session
                    print("Cleaning up session...")
                    listener_task.cancel()
                    try: cmd_worker_task.cancel()
                    except: pass
                    try: reminder_task.cancel()
                    except: pass
                    client_socket.close()
                    
            except KeyboardInterrupt:
                print("\nStopping Server...")
                break
            except Exception as accept_e:
                print(f"Critcal Accept Error: {accept_e}")
                await asyncio.sleep(1.0)
                
    except Exception as e:
        print(f"\nCRITICAL SERVER FAILURE: {e}")
        traceback.print_exc()
    finally:
        try:
            server_socket.close()
        except:
            pass

if __name__ == "__main__":
    asyncio.run(main())
