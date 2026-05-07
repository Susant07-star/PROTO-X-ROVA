# 🤖 PROTO-X ROVA: Advanced Voice-Controlled AI Robot
> **A high-performance, autonomous 4-wheel robotic assistant powered by ESP32 and Real-Time Computer Vision.**

---

![License](https://img.shields.io/badge/License-MIT-blue.svg?style=for-the-badge)
![Python](https://img.shields.io/badge/Python-3.10+-3776AB?style=for-the-badge&logo=python&logoColor=white)
![C++](https://img.shields.io/badge/C++-ESP32-00599C?style=for-the-badge&logo=c%2B%2B&logoColor=white)
![AI](https://img.shields.io/badge/AI-YOLOv8%20|%20Whisper-FF6F00?style=for-the-badge&logo=google-ai&logoColor=white)

**PROTO-X ROVA** (Robotic Omnidirectional Voice Assistant) is an advanced engineering project developed at Takshashila Academy. It represents the perfect synergy between heavy-duty hardware and a modern AI software stack, featuring real-time natural language processing and autonomous computer vision.

---

## 🚀 Key Features

*   🎙️ **Natural Voice Interaction:** Local STT (Faster-Whisper) for seamless voice commands.
*   🧠 **Intelligent Reasoning:** Integrated with **Ollama (Qwen2.5)** for high-level logic and command parsing.
*   👁️ **Computer Vision:** Powered by **YOLOv8** for real-time object recognition and obstacle avoidance.
*   🛰️ **Distributed Architecture:** Dual-layer system separating real-time firmware from heavy-duty AI processing.
*   ⚡ **Local-First:** Designed for speed and privacy—all AI processing happens on local hardware.

---

## 🛠️ Hardware Specifications

| Component | Specification | Description |
| :--- | :--- | :--- |
| **Microcontroller** | ESP32 Dev Board | Dual-core 240MHz logic control |
| **Motors** | 4x GH37-385 Geared | 12V DC, 100 RPM high-torque drive |
| **Motor Drivers** | 2x BTS7960 (43A) | Heavy-duty H-Bridge for high current |
| **Power System** | 12V LiPo/Lead-Acid | LM2596 Buck Converters for stable 5V logic |
| **Audio Input** | INMP441 I2S Mic | High-fidelity digital MEMS microphone |
| **Audio Output** | MAX98357A I2S Amp | Digital audio to 3W speaker output |
| **Vision** | ESP32-CAM / PC Node | Live telemetry and vision processing |

---

## 💻 Software Stack & Architecture

The ROVA system is built on a high-speed TCP/IP communication bridge between the robot and the AI Server.

### 1. Firmware (ESP32 / Arduino C++)
*   **Motor Control:** Precision PWM-based speed and direction control.
*   **Audio Streaming:** Full-duplex I2S audio pipeline for real-time voice capture.
*   **Telemetry:** On-board monitoring of battery health and system temperature.

### 2. AI Server (Python 3.10+)
*   **STT:** `faster-whisper` for sub-second speech-to-text conversion.
*   **NLP:** Local LLM integration via `Ollama` for semantic understanding.
*   **Vision:** `ultralytics` YOLOv8 for spatial awareness and object detection.
*   **Dashboard:** `aiohttp` web server providing a live remote-control interface and video stream.

---

## 👥 The Team
**Developed by the Takshashila Engineering Group (Kathmandu, Nepal):**
*   **Team Leader:** Sushant Bhandari
*   **Engineering Team:** Neema Sherpa, Uttam Shrestha, Nishant Bhandari, Prithivi Raiymajhi, Subash Shrestha
*   **Supervision:** Mrs. Netra Neupane (Principal)

---

## 📄 License
This project is licensed under the **MIT License**. See the `LICENSE` file for details.

---

<div align="center">
  <sub>Built with ❤️ by the Takshashila Engineering Team</sub>
</div>
