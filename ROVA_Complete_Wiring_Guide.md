# 🤖 ROVA — Complete Wiring Guide
## All Connections for ESP32 + BTS7960 Motors + INMP441 Mic + MAX98357A Speaker + PCA9685 Servo Arm + IR Sensor

> **IMPORTANT:** Double-check every connection before powering on. Always connect grounds first and disconnect the battery before making changes.

---

## 📦 Full Component List

| Component | Quantity | Specification |
|-----------|----------|---------------|
| **ESP32 Dev Board** | 1 | Main controller |
| **GH37-385 DC Motors** | 4 | 12V, 100 RPM, Geared |
| **BTS7960 Motor Driver** | 2 | 43A High-Current H-Bridge |
| **12V Battery** | 1 | 3S LiPo or 11.1V Lead-acid |
| **Buck Converter** | 1 | LM2596 (12V → 5V, 1A+) |
| **INMP441 Microphone** | 1 | I2S Digital Microphone |
| **MAX98357A Amplifier** | 1 | I2S Audio Amplifier + Speaker |
| **PCA9685 Servo Driver** | 1 | 16-Channel I2C PWM Driver |
| **Servo Motors** | 4 | For robot arm (Shoulder + Elbow, Left + Right) |
| **IR Sensor** | 1 | Obstacle/Line detection |
| **Capacitor** | 1 | For PCA9685 power smoothing |

---

## ⚡ SECTION 1: Power Distribution (12V Battery)

> Wire all power connections first before anything else.

| FROM | TO | TO Pin | Wire Color | Wire Gauge |
|------|----|--------|------------|------------|
| Battery **+** | BTS7960 Driver #1 | **B+** | Red | 16 AWG |
| Battery **+** | BTS7960 Driver #2 | **B+** | Red | 16 AWG |
| Battery **+** | Buck Converter | **IN+** | Red | 16 AWG |
| Battery **−** | BTS7960 Driver #1 | **B−** | Black | 16 AWG |
| Battery **−** | BTS7960 Driver #2 | **B−** | Black | 16 AWG |
| Battery **−** | Buck Converter | **IN−** | Black | 16 AWG |
| Battery **−** | ESP32 | **GND** | Black | 16 AWG |

> ⚠️ **CRITICAL:** Set Buck Converter output to exactly **5.0V** using a multimeter BEFORE connecting anything else.

---

## ⚡ SECTION 2: Buck Converter → ESP32 & Motor Drivers (5V Logic Power)

| FROM | TO | TO Pin | Wire Color | Wire Gauge |
|------|----|--------|------------|------------|
| Buck **OUT+** (5V) | BTS7960 Driver #1 | **VCC** | Red | 22 AWG |
| Buck **OUT+** (5V) | BTS7960 Driver #1 | **L_EN** | Red | 22 AWG |
| Buck **OUT+** (5V) | BTS7960 Driver #1 | **R_EN** | Red | 22 AWG |
| Buck **OUT+** (5V) | BTS7960 Driver #2 | **VCC** | Red | 22 AWG |
| Buck **OUT+** (5V) | BTS7960 Driver #2 | **L_EN** | Red | 22 AWG |
| Buck **OUT+** (5V) | BTS7960 Driver #2 | **R_EN** | Red | 22 AWG |
| Buck **OUT+** (5V) | ESP32 | **VIN / 5V** | Red | 22 AWG |
| Buck **OUT−** (GND) | BTS7960 Driver #1 | **GND** | Black | 22 AWG |
| Buck **OUT−** (GND) | BTS7960 Driver #2 | **GND** | Black | 22 AWG |

---

## 🚗 SECTION 3: ESP32 → BTS7960 Motor Drivers (PWM Control Signals)

| ESP32 GPIO | BTS7960 Driver | Driver Pin | Wire Color | Purpose |
|------------|----------------|------------|------------|---------|
| **GPIO 13** | Driver #1 (LEFT) | **L_PWM** | Yellow | Left motors FORWARD |
| **GPIO 12** | Driver #1 (LEFT) | **R_PWM** | Orange | Left motors REVERSE |
| **GPIO 14** | Driver #2 (RIGHT) | **L_PWM** | Green | Right motors FORWARD |
| **GPIO 27** | Driver #2 (RIGHT) | **R_PWM** | Blue | Right motors REVERSE |

---

## 🔌 SECTION 4: BTS7960 Drivers → Motors (Power Outputs)

### Driver #1 — LEFT SIDE MOTORS

| Driver Pin | Connects To | Wire Color | Wire Gauge |
|------------|-------------|------------|------------|
| **M+** | Front Left Motor (+) | Red | 16 AWG |
| **M+** | Rear Left Motor (+) | Red | 16 AWG |
| **M−** | Front Left Motor (−) | Black | 16 AWG |
| **M−** | Rear Left Motor (−) | Black | 16 AWG |

### Driver #2 — RIGHT SIDE MOTORS

| Driver Pin | Connects To | Wire Color | Wire Gauge |
|------------|-------------|------------|------------|
| **M+** | Front Right Motor (+) | Red | 16 AWG |
| **M+** | Rear Right Motor (+) | Red | 16 AWG |
| **M−** | Front Right Motor (−) | Black | 16 AWG |
| **M−** | Rear Right Motor (−) | Black | 16 AWG |

> **Note:** Left-side motors (Front Left + Rear Left) connect in **parallel** to Driver #1. Right-side motors connect in **parallel** to Driver #2.

---

## 🎙️ SECTION 5: INMP441 Microphone → ESP32

> The INMP441 is a digital I2S microphone. It shares the I2S bus with the amplifier.

| INMP441 Pin | ESP32 Pin | Notes |
|-------------|-----------|-------|
| **VDD** | **3.3V** | Do NOT use 5V — it will damage the mic |
| **GND** | **GND** | Separate GND from L/R pin |
| **SCK** | **GPIO 26** | I2S Bit Clock (shared with amp BCLK) |
| **WS** | **GPIO 22** | I2S Word Select (shared with amp LRC) |
| **SD** | **GPIO 34** | I2S Data OUT from mic |
| **L/R** | **GND** | Sets mic to LEFT channel |

---

## 🔊 SECTION 6: MAX98357A Amplifier → ESP32

> The amplifier shares the I2S clock lines (GPIO 26 & 22) with the INMP441 mic.

| MAX98357A Pin | ESP32 Pin | Notes |
|---------------|-----------|-------|
| **LRC (WS)** | **GPIO 22** | Connect both Mic WS and Amp LRC to this pin |
| **BCLK (SCK)** | **GPIO 26** | Connect both Mic SCK and Amp BCLK to this pin |
| **DIN** | **GPIO 25** | Audio data OUT from ESP32 to amp |
| **VIN** | **5V (VIN)** | Power from Buck Converter 5V output |
| **GND** | **GND** | Common ground |
| **SD** | **5V** | Pull SD HIGH to eliminate power-on/off jitter |

> 💡 **Pro Tip:** Twist the BCLK and LRC wires together to reduce audio jitter/noise in the speaker.

### I2S Pin Summary (Both Mic + Amp share):
```
GPIO 22  ──► INMP441 WS  +  MAX98357A LRC
GPIO 26  ──► INMP441 SCK +  MAX98357A BCLK
GPIO 34  ◄── INMP441 SD  (mic data IN to ESP32)
GPIO 25  ──► MAX98357A DIN (audio data OUT from ESP32)
```

---

## 🦾 SECTION 7: PCA9685 Servo Driver → ESP32 (Robot Arm)

### Step 1: Power the Motors via Green Terminal

| From | To | Notes |
|------|----|-------|
| Buck **OUT+** (5V) | Green Terminal **V+** | Powers servo motors |
| Buck **OUT−** (GND) | Green Terminal **GND** | Common ground |
| Capacitor (+) | Green Terminal **V+** | Red leg to V+ for power smoothing |
| Capacitor (−) | Green Terminal **GND** | Black leg to GND |

### Step 2: Power the Chip Logic (Side Pins)

| ESP32 Pin | PCA9685 Pin | Notes |
|-----------|-------------|-------|
| **3.3V** (or 5V) | **VCC** | Powers the chip logic |
| **GND** | **GND** | Common ground |
| **GPIO 15** | **SDA** | I2C Data |
| **GPIO 14** | **SCL** | I2C Clock |

### Step 3: Servo Ports (Robot Arm)

| Servo | PCA9685 Port | Notes |
|-------|-------------|-------|
| **Left Shoulder** | Port **0** | Connect black/brown wire facing OUT/DOWN |
| **Left Elbow** | Port **1** | |
| **Right Shoulder** | Port **2** | |
| **Right Elbow** | Port **3** | |

---

## 🔴 SECTION 8: IR Sensor → ESP32

| IR Sensor Pin | ESP32 Pin | Notes |
|---------------|-----------|-------|
| **VCC** | **5V / 3.3V** | Use 3.3V if sensor supports it |
| **GND** | **GND** | Common ground |
| **OUT** | **GPIO 35** | Digital signal output |

---

## 📋 Complete ESP32 GPIO Pin Map (Summary)

| GPIO | Function | Connected To |
|------|----------|-------------|
| **GPIO 12** | Motor L Reverse (PWM) | BTS7960 #1 R_PWM |
| **GPIO 13** | Motor L Forward (PWM) | BTS7960 #1 L_PWM |
| **GPIO 14** | Motor R Forward (PWM) / SCL | BTS7960 #2 L_PWM / PCA9685 SCL |
| **GPIO 15** | I2C SDA | PCA9685 SDA |
| **GPIO 22** | I2S Word Select (WS) | INMP441 WS + MAX98357A LRC |
| **GPIO 25** | I2S Data OUT (TX) | MAX98357A DIN |
| **GPIO 26** | I2S Bit Clock (BCLK) | INMP441 SCK + MAX98357A BCLK |
| **GPIO 27** | Motor R Reverse (PWM) | BTS7960 #2 R_PWM |
| **GPIO 34** | I2S Data IN (from mic) | INMP441 SD |
| **GPIO 35** | IR Sensor Signal | IR Sensor OUT |
| **3.3V** | 3.3V Power Rail | INMP441 VDD, PCA9685 VCC |
| **5V / VIN** | 5V Power (from Buck) | MAX98357A VIN, PCA9685 (optional) |
| **GND** | Common Ground | All GNDs |

> ⚠️ **Note:** GPIO 14 is shared between Right Motor Forward (BTS7960 #2 L_PWM) and PCA9685 SCL. Ensure this does not conflict during use — the arm should be driven on a separate ESP32 or the motor and arm should not be active simultaneously on the same pin.

---

## ✅ Pre-Power Checklist

- [ ] Buck Converter output set to exactly **5.0V** (tested with multimeter)
- [ ] All grounds connected together (Battery, ESP32, both BTS7960, Buck converter)
- [ ] INMP441 connected to **3.3V** (not 5V)
- [ ] MAX98357A SD pin pulled HIGH to 5V
- [ ] BCLK and LRC wires twisted together
- [ ] Motor polarity verified (M+ and M−)
- [ ] PCA9685 capacitor installed on green terminal
- [ ] Servo brown/black wire faces outward on PCA9685 ports
- [ ] IR Sensor OUT connected to GPIO 35
- [ ] No exposed/short circuit wires

---

## 🐛 Quick Troubleshooting

| Problem | Likely Cause | Fix |
|---------|-------------|-----|
| Motors don't spin | L_EN/R_EN not tied to 5V | Connect both enable pins to Buck 5V |
| Motors spin wrong way | M+ and M− swapped | Swap motor output wires |
| No audio from speaker | SD pin floating | Pull MAX98357A SD to 5V |
| Mic not picking up sound | L/R pin not grounded | Connect INMP441 L/R to GND |
| Speaker jitter on power on/off | SD pin floating | Confirmed fix: SD to 5V |
| Servo arm not responding | PCA9685 power or I2C issue | Check 5V on green terminal and SDA/SCL wiring |
| ESP32 reboots when motors run | Insufficient grounding | Add thick ground wire (14 AWG), add 1000µF cap across battery |
| IR sensor always triggered | VCC too high | Use 3.3V instead of 5V |

---

## 🗺️ Visual Layout

```
                    ROVA TOP VIEW
                      [Front]
                 M1 ●──⚙──● M3
                    │     │
       LEFT [BTS#1] │     │ [BTS#2] RIGHT
                    │     │
                 M2 ●──⚙──● M4
                      [Back]

M1, M2 (Left)  → BTS7960 Driver #1
M3, M4 (Right) → BTS7960 Driver #2
```

```
POWER DISTRIBUTION:
         12V Battery
              │
    ┌─────────┼──────────┐
    │         │          │
BTS7960#1   Buck       BTS7960#2
 (B+,B−)  (12V→5V)    (B+,B−)
              │
    ┌─────────┼──────────┐
    │         │          │
BTS7960#1  ESP32     BTS7960#2
 (VCC,EN)  (5V,GND)   (VCC,EN)
```

---

*Guide compiled from: `BTS7960_Wiring_Guide.md` + `connection with esp32 and inmp441 mic.txt`*
*Project: ROVA — Takshashila Academy, Kathmandu, Nepal*
