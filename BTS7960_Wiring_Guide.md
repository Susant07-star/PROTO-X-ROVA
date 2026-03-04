# 🤖 4-Wheel Robot Wiring Guide
## BTS7960 Motor Drivers + ESP32 + GH37-385 Motors

---

## � SUPER SIMPLE CONNECTION TABLES

### Table 1: Battery → Everything (12V Power)

| FROM (Battery) | TO (Component) | TO (Exact Pin Name) | Wire Color | Wire Size |
|----------------|----------------|---------------------|------------|-----------|
| Battery **+** | BTS7960 Driver #1 | **B+** | Red | 16 AWG |
| Battery **+** | BTS7960 Driver #2 | **B+** | Red | 16 AWG |
| Battery **+** | Buck Converter | **IN+** | Red | 16 AWG |
| Battery **-** | BTS7960 Driver #1 | **B-** | Black | 16 AWG |
| Battery **-** | BTS7960 Driver #2 | **B-** | Black | 16 AWG |
| Battery **-** | Buck Converter | **IN-** | Black | 16 AWG |
| Battery **-** | ESP32 Board | **GND** | Black | 16 AWG |

---

### Table 2: Buck Converter → Drivers & ESP32 (5V Logic Power)

| FROM (Buck Converter) | TO (Component) | TO (Exact Pin Name) | Wire Color | Wire Size |
|-----------------------|----------------|---------------------|------------|-----------|
| Buck **OUT+** (5V) | BTS7960 Driver #1 | **VCC** | Red | 22 AWG |
| Buck **OUT+** (5V) | BTS7960 Driver #1 | **L_EN** | Red | 22 AWG |
| Buck **OUT+** (5V) | BTS7960 Driver #1 | **R_EN** | Red | 22 AWG |
| Buck **OUT+** (5V) | BTS7960 Driver #2 | **VCC** | Red | 22 AWG |
| Buck **OUT+** (5V) | BTS7960 Driver #2 | **L_EN** | Red | 22 AWG |
| Buck **OUT+** (5V) | BTS7960 Driver #2 | **R_EN** | Red | 22 AWG |
| Buck **OUT+** (5V) | ESP32 Board | **5V** (or VIN) | Red | 22 AWG |
| Buck **OUT-** (GND) | BTS7960 Driver #1 | **GND** | Black | 22 AWG |
| Buck **OUT-** (GND) | BTS7960 Driver #2 | **GND** | Black | 22 AWG |

---

### Table 3: ESP32 → BTS7960 Drivers (Control Signals)

| FROM (ESP32) | TO (Component) | TO (Exact Pin Name) | Wire Color | Wire Size | Purpose |
|--------------|----------------|---------------------|------------|-----------|---------|
| ESP32 **GPIO 13** | BTS7960 Driver #1 | **L_PWM** | Yellow | 22 AWG | Left Forward |
| ESP32 **GPIO 12** | BTS7960 Driver #1 | **R_PWM** | Orange | 22 AWG | Left Reverse |
| ESP32 **GPIO 14** | BTS7960 Driver #2 | **L_PWM** | Green | 22 AWG | Right Forward |
| ESP32 **GPIO 27** | BTS7960 Driver #2 | **R_PWM** | Blue | 22 AWG | Right Reverse |

---

### Table 4: BTS7960 Drivers → Motors (Motor Power)

| FROM (Driver) | FROM (Exact Pin) | TO (Motors) | Wire Color | Wire Size |
|---------------|------------------|-------------|------------|-----------|
| BTS7960 Driver #1 | **M+** | Front Left Motor **(+)** | Red | 16 AWG |
| BTS7960 Driver #1 | **M+** | Rear Left Motor **(+)** | Red | 16 AWG |
| BTS7960 Driver #1 | **M-** | Front Left Motor **(-)** | Black | 16 AWG |
| BTS7960 Driver #1 | **M-** | Rear Left Motor **(-)** | Black | 16 AWG |
| BTS7960 Driver #2 | **M+** | Front Right Motor **(+)** | Red | 16 AWG |
| BTS7960 Driver #2 | **M+** | Rear Right Motor **(+)** | Red | 16 AWG |
| BTS7960 Driver #2 | **M-** | Front Right Motor **(-)** | Black | 16 AWG |
| BTS7960 Driver #2 | **M-** | Rear Right Motor **(-)** | Black | 16 AWG |

> **Note**: Motors on same side connect in PARALLEL (both motors share same M+ and M- from driver)

---

## �📦 Components Needed

| Component | Quantity | Specifications |
|-----------|----------|----------------|
| **GH37-385 Motors** | 4 | 12V DC, 100 RPM |
| **BTS7960 Motor Driver** | 2 | 43A motor drivers |
| **ESP32 Dev Board** | 1 | Your current board |
| **12V Battery** | 1 | 3S LiPo or Lead-acid, 3000mAh+ |
| **Buck Converter** | 1 | LM2596 (12V → 5V, 1A+) |
| **Wires** | - | 16 AWG (power), 22 AWG (signal) |
| **Power Switch** | 1 | Optional but recommended |

---

## 🎨 Wire Color Code (Recommended)

| Connection Type | Color | Wire Gauge |
|----------------|-------|------------|
| **Battery (+) / 12V Power** | 🔴 Red | 16 AWG |
| **Battery (-) / Ground** | ⚫ Black | 16 AWG |
| **Motor Positive** | 🔴 Red | 16 AWG |
| **Motor Negative** | ⚫ Black | 16 AWG |
| **5V Logic Power** | 🔴 Red | 22 AWG |
| **Logic Ground** | ⚫ Black | 22 AWG |
| **ESP32 → Left Forward** | 🟡 Yellow | 22 AWG |
| **ESP32 → Left Reverse** | 🟠 Orange | 22 AWG |
| **ESP32 → Right Forward** | 🟢 Green | 22 AWG |
| **ESP32 → Right Reverse** | 🔵 Blue | 22 AWG |

---

## 🔧 STEP-BY-STEP WIRING

### ⚡ STEP 1: Prepare Buck Converter (DO THIS FIRST!)

1. **DO NOT connect anything yet**
2. Connect only battery to buck converter:
   - Battery (+) → Buck **IN+**
   - Battery (-) → Buck **IN-**
3. Use multimeter on buck converter output
4. Turn potentiometer screw until output reads **exactly 5.0V**
5. Disconnect battery
6. ✅ Buck converter is now ready

---

### 🔋 STEP 2: Battery Power Distribution

**Connect battery (+) to:**
- BTS7960 #1: **B+** (16 AWG red wire)
- BTS7960 #2: **B+** (16 AWG red wire)  
- Buck Converter: **IN+** (16 AWG red wire)

**Connect battery (-) to:**
- BTS7960 #1: **B-** (16 AWG black wire)
- BTS7960 #2: **B-** (16 AWG black wire)
- Buck Converter: **IN-** (16 AWG black wire)
- ESP32: **GND** (16 AWG black wire)

> ⚠️ **CRITICAL**: All grounds must be connected together!

---

### 🔌 STEP 3: BTS7960 #1 (LEFT SIDE) Connections

**Power Connections:**
```
Battery (+12V) ──► B+
Battery (GND)  ──► B-
Buck (5V OUT+) ──► VCC
Buck (GND OUT-)──► GND
```

**Enable Pins (always ON):**
```
Buck (5V OUT+) ──► L_EN
Buck (5V OUT+) ──► R_EN
```

**PWM Control from ESP32:**
```
ESP32 GPIO 13 ──► L_PWM (yellow wire)
ESP32 GPIO 12 ──► R_PWM (orange wire)
```

**Motor Outputs (LEFT side motors):**
```
M+ ──┬── Front Left Motor (+)
     └── Rear Left Motor (+)

M- ──┬── Front Left Motor (-)
     └── Rear Left Motor (-)
```

---

### 🔌 STEP 4: BTS7960 #2 (RIGHT SIDE) Connections

**Power Connections:**
```
Battery (+12V) ──► B+
Battery (GND)  ──► B-
Buck (5V OUT+) ──► VCC
Buck (GND OUT-)──► GND
```

**Enable Pins (always ON):**
```
Buck (5V OUT+) ──► L_EN
Buck (5V OUT+) ──► R_EN
```

**PWM Control from ESP32:**
```
ESP32 GPIO 14 ──► L_PWM (green wire)
ESP32 GPIO 27 ──► R_PWM (blue wire)
```

**Motor Outputs (RIGHT side motors):**
```
M+ ──┬── Front Right Motor (+)
     └── Rear Right Motor (+)

M- ──┬── Front Right Motor (-)
     └── Rear Right Motor (-)
```

---

### 🎮 STEP 5: ESP32 Connections

| ESP32 Pin | Connects To | Purpose |
|-----------|-------------|---------|
| **GND** | Battery (-) & All GND points | Common ground |
| **5V** or **VIN** | Buck Converter (5V OUT+) | Power ESP32 |
| **GPIO 13** | BTS7960 #1 → L_PWM | Left motors forward |
| **GPIO 12** | BTS7960 #1 → R_PWM | Left motors reverse |
| **GPIO 14** | BTS7960 #2 → L_PWM | Right motors forward |
| **GPIO 27** | BTS7960 #2 → R_PWM | Right motors reverse |

---

## 📊 Complete Connection Table

### BTS7960 #1 (LEFT MOTORS)

| BTS7960 Pin | Wire To | Wire Color | Wire Gauge |
|-------------|---------|------------|------------|
| B+ | Battery (+) | Red | 16 AWG |
| B- | Battery (-) | Black | 16 AWG |
| VCC | Buck 5V (OUT+) | Red | 22 AWG |
| GND | Buck GND (OUT-) | Black | 22 AWG |
| L_EN | Buck 5V (OUT+) | Red | 22 AWG |
| R_EN | Buck 5V (OUT+) | Red | 22 AWG |
| L_PWM | ESP32 GPIO 13 | Yellow | 22 AWG |
| R_PWM | ESP32 GPIO 12 | Orange | 22 AWG |
| M+ | Front Left (+) & Rear Left (+) | Red | 16 AWG |
| M- | Front Left (-) & Rear Left (-) | Black | 16 AWG |

### BTS7960 #2 (RIGHT MOTORS)

| BTS7960 Pin | Wire To | Wire Color | Wire Gauge |
|-------------|---------|------------|------------|
| B+ | Battery (+) | Red | 16 AWG |
| B- | Battery (-) | Black | 16 AWG |
| VCC | Buck 5V (OUT+) | Red | 22 AWG |
| GND | Buck GND (OUT-) | Black | 22 AWG |
| L_EN | Buck 5V (OUT+) | Red | 22 AWG |
| R_EN | Buck 5V (OUT+) | Red | 22 AWG |
| L_PWM | ESP32 GPIO 14 | Green | 22 AWG |
| R_PWM | ESP32 GPIO 27 | Blue | 22 AWG |
| M+ | Front Right (+) & Rear Right (+) | Red | 16 AWG |
| M- | Front Right (-) & Rear Right (-) | Black | 16 AWG |

---

## ✅ TESTING PROCEDURE

### Before Powering On

- [ ] Double-check all wire connections
- [ ] Verify buck converter outputs 5.0V
- [ ] Check for short circuits with multimeter
- [ ] Ensure battery is disconnected
- [ ] Verify motor polarity markings

### Power On Sequence

1. **Connect battery** (or turn on power switch)
2. **Check LED indicators**:
   - Buck converter LED should light up
   - BTS7960 power LEDs should light up
   - ESP32 should boot (Serial monitor shows startup)
3. **Test ONE motor first**:
   - Send command: `CMD:F:1000` (forward 1 second)
   - Observe motor direction
   - If wrong direction, swap M+ and M- wires
4. **Test all motors**:
   - Forward: Both sides should move forward
   - Backward: Both sides should reverse
   - Left turn: Left stops, right goes
   - Right turn: Right stops, left goes

### Test Commands (via Serial/Server)

| Command | Expected Behavior |
|---------|-------------------|
| `CMD:F` | All 4 motors forward |
| `CMD:B` | All 4 motors backward |
| `CMD:L` | Turn left (right motors move) |
| `CMD:R` | Turn right (left motors move) |
| `CMD:S` | Stop all motors |

---

## 🐛 Troubleshooting

### Motors Don't Move

- ✅ Check BTS7960 power LEDs are ON
- ✅ Verify L_EN and R_EN are connected to 5V
- ✅ Check PWM wires are connected correctly
- ✅ Verify common ground between ESP32 and BTS7960
- ✅ Test with higher speed: `setMotors(255, 255)`

### Motors Move Wrong Direction

- ✅ Swap M+ and M- wires on that driver
- ✅ Or modify code to invert speed value

### Only One Side Works

- ✅ Check PWM connections for non-working side
- ✅ Verify that BTS7960 is powered (check LEDs)
- ✅ Test with multimeter on L_PWM/R_PWM pins (should see ~0-3.3V)

### ESP32 Reboots When Motors Run

- ✅ **Most likely cause**: Grounds not connected properly
- ✅ Add thicker ground wire (14 AWG)
- ✅ Check battery capacity (may be too weak)
- ✅ Add 1000µF capacitor across battery terminals

### Motors Run Weak/Slow

- ✅ Check battery voltage (should be 12V)
- ✅ Check wire gauge (should be 16 AWG minimum)
- ✅ Verify buck converter is NOT connected to B+ (should be 5V only to VCC)
- ✅ Increase PWM speed in code

---

## 🛡️ Safety Tips

1. **Add a fuse**: 20A fuse between battery (+) and circuit
2. **Main power switch**: Easy emergency stop
3. **Heatsinks**: BTS7960 can get hot under load
4. **Wire strain relief**: Secure wires so they don't pull out
5. **Insulate connections**: Heat shrink or electrical tape on all joints
6. **Test incrementally**: One component at a time

---

## 📷 Quick Visual Reference

```
ROBOT TOP VIEW:
    [Front]
  M1 ●─⚙─● M3
     │   │
 [L] │   │ [R]
     │   │
  M2 ●─⚙─● M4
    [Back]

M1, M2 → BTS7960 #1 (Left)
M3, M4 → BTS7960 #2 (Right)
```

```
POWER DISTRIBUTION:
         12V Battery
            │
    ┌───────┼───────┐
    │       │       │
    │   Buck Conv  │
    │   (12V→5V)   │
    │       │       │
BTS7960#1  5V   BTS7960#2  ESP32
(B+,B-)  (VCC) (B+,B-)    (5V,GND)
   │              │          │
  M1,M2         M3,M4     (Control)
```

---

## 📝 Notes

- Your existing code in `sketch_jan13a.ino` is already configured correctly
- No code changes needed - just wire and test!
- Keep battery charged above 11V for best performance
- GH37-385 motors are geared, so they have good torque
- With 4 motors in parallel pairs, expect excellent hill-climbing ability

---

**Ready to build? Follow the steps in order and test as you go! Good luck! 🚀**
