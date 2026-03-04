# PROTO-X-ROVA
ROVA is an advanced, voice-controlled 4-wheel robot developed as part of the PROTO-X project. It combines heavy-duty hardware with a modern AI software stack to provide a responsive and intelligent robotic assistant.

👥 The Team
Created by: 6 Students from Takshashila Academy, Kathmandu, Nepal

Team Leader: Sushant Bhandari
Members: Neema Sherpa, Uttam Shrestha, Nishant Bhandari, Prithivi Raiymajhi, Subash Shrestha
Principal: Mrs. Netra Neupane

🛠️ Hardware Specifications
Component	specification
Microcontroller -	ESP32 Dev Board
Motors	-4x GH37-385 (12V DC, 100 RPM, Geared)
Motor Drivers -	2x BTS7960 (43A High-Current Bridge)
Power	12V LiPo/Lead-acid Battery with LM2596 Buck Converter (5V Logic)
Audio	I2S Microphone (INMP441) & I2S Speaker (MAX98357A)
Vision	- ESP32-CAM or PC-hosted Camera Node (YOLOv8 support)

💻 Software Architecture
The system is split into two main layers:

1. Firmware (ESP32 / Arduino C++)
Real-time motor control using LEDC PWM.
I2S Audio streaming (full-duplex) for voice interactions.
Low-latency TCP connection to the central server.
On-board telemetry (e.g., Temperature monitoring).
2. AI Server (Python / PC Hosted)
Voice Recognition: faster-whisper for high-accuracy local speech-to-text.
Natural Language Processing: Local LLM integration (Ollama - Qwen2.5) for intelligent reasoning and command parsing.
Vision: Ultralytics YOLOv8 for real-time obstacle detection and object recognition.
Web Interface: Aiohttp-based dashboard for remote control, video streaming, and status monitoring.
TTS: Local text-to-speech for robot responses.

🚀 Key Features
Natural Voice Interaction: Communicate with simple English commands.
Autonomous Avoidance: Real-time vision-based path correction.
Omnidirectional Potential: 4-wheel drive for high torque and stability.
Remote Dashboard: Live video feed and control interface from any browser.
Local-First: Designed to run entirely on local hardware for privacy and speed.
