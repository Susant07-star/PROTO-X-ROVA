#include <Adafruit_PWMServoDriver.h>
#include <WiFi.h>
#include <Wire.h>

// --- WIFI CONFIGURATION ---
const char *ssid = "wifiname";
const char *password = "wifipassword";
const char *host = "ip"; // Laptop Hotspot IP
const int port = 4001;

// --- PCA9685 CONFIG ---
#define SDA_PIN 21 // Standard I2C SDA
#define SCL_PIN 22 // Standard I2C SCL
Adafruit_PWMServoDriver pwm = Adafruit_PWMServoDriver();

// --- SERVO PORTS ---
#define PORT_LS 0 // Left Shoulder
#define PORT_LE 1 // Left Elbow
#define PORT_RS 2 // Right Shoulder
#define PORT_RE 9 // Right Elbow - Changed from 8 to 9
#define PORT_LW 4 // Left Wrist
#define PORT_LG 5 // Left Gripper
#define PORT_RW 6 // Right Wrist
#define PORT_RG 7 // Right Gripper

// --- PULSE SETTINGS ---
// Standard: 150 (approx 0deg) to 500 (approx 180deg) for safer range
// Previous was 100-600 which creates ~0.5ms to 2.9ms (too extreme for standard
// servos)
#define SERVOMIN 150
#define SERVOMAX 500

// --- SERVO LIMITS ---
#define SHOULDER_MAX 180   // Changed from 270: 180-degree servo logic
#define SHOULDER_LIMIT 180 // Software limit for safety
#define ELBOW_MAX 180      // Standard range
#define WRIST_MAX 180
#define LEFT_WRIST_MAX 180 // Reset to 180 for standard behavior
#define GRIPPER_MAX                                                            \
  100 // Increased slightly for full open test (check visually)

WiFiClient client;
bool isConnected = false;

// --- NON-BLOCKING SERVO STRUCTURE ---
struct ServoState {
  int channel;
  int currentPos; // Internal float for smoothness? Int is fine for servo
  int targetPos;
  int maxAngle;
  unsigned long lastUpdate;
  int speedDelay; // ms per degree (Lower = Faster)
};

// Init States (Wrists at 90, Grippers at 45, Elbows split 0/180)
ServoState sLS = {PORT_LS, 90, 90, SHOULDER_MAX, 0, 10};
ServoState sLE = {PORT_LE, 0, 0, ELBOW_MAX, 0, 15}; // Left Elbow 0
ServoState sRS = {PORT_RS, 90, 90, SHOULDER_MAX, 0, 10};
ServoState sRE = {PORT_RE, 180, 180, ELBOW_MAX, 0, 15};    // Right Elbow 180
ServoState sLW = {PORT_LW, 90, 90, LEFT_WRIST_MAX, 0, 10}; // Updated Max
ServoState sLG = {PORT_LG, 45, 45, GRIPPER_MAX, 0, 10};    // Gripper 45
ServoState sRW = {PORT_RW, 90, 90, WRIST_MAX, 0, 10};
ServoState sRG = {PORT_RG, 45, 45, GRIPPER_MAX, 0, 10}; // Gripper 45

int angleToPulse(int angle, int maxAngle) {
  // Map 0 -> maxAngle  TO  SERVOMIN -> SERVOMAX
  // e.g. 0-270 maps to 100-600
  return map(angle, 0, maxAngle, SERVOMIN, SERVOMAX);
}

void setup() {
  Serial.begin(115200);

  // I2C Init
  Wire.begin(SDA_PIN, SCL_PIN);
  pwm.begin();
  pwm.setOscillatorFrequency(27000000);
  pwm.setPWMFreq(50);

  Serial.println("System Starting... Moving to Home");

  // Initial Position via Direct Write (Fast Home) - DISABLED FOR SAFETY
  // User requested "No Move on Power On" to prevent plastic collisions.
  // These calls are commented out so servos start "limp" (no torque).
  /*
  pwm.setPWM(PORT_LS, 0, angleToPulse(90, SHOULDER_MAX));
  pwm.setPWM(PORT_LE, 0, angleToPulse(0, ELBOW_MAX)); // 0
  pwm.setPWM(PORT_RS, 0, angleToPulse(90, SHOULDER_MAX));
  pwm.setPWM(PORT_RE, 0, angleToPulse(180, ELBOW_MAX)); // 180
  pwm.setPWM(PORT_LW, 0, angleToPulse(90, WRIST_MAX));
  pwm.setPWM(PORT_LG, 0, angleToPulse(45, GRIPPER_MAX)); // 45
  pwm.setPWM(PORT_RW, 0, angleToPulse(90, WRIST_MAX));
  pwm.setPWM(PORT_RG, 0, angleToPulse(45, GRIPPER_MAX)); // 45
  delay(1000);
  */

  // WiFi Setup
  WiFi.begin(ssid, password);
  while (WiFi.status() != WL_CONNECTED) {
    delay(500);
    Serial.print(".");
  }
  Serial.println("\nWiFi Connected!");
  Serial.println(WiFi.localIP());
}

// --- CORE UPDATE FUNCTION (Call frequently) ---
void updateServo(ServoState &s) {
  if (s.currentPos == s.targetPos)
    return;

  if (millis() - s.lastUpdate >= s.speedDelay) {
    s.lastUpdate = millis();

    // Step Direction
    if (s.currentPos < s.targetPos)
      s.currentPos++;
    else
      s.currentPos--;

    // Safety Clamps
    if (s.currentPos < 0)
      s.currentPos = 0;
    if (s.currentPos > s.maxAngle)
      s.currentPos = s.maxAngle;

    // Send I2C Command
    int pulse = angleToPulse(s.currentPos, s.maxAngle);
    pwm.setPWM(s.channel, 0, pulse);

    // Debug print only occasionally to avoid spam? No, spam is fine for
    // debugging Serial.printf("Ch%d: %d\n", s.channel, s.currentPos);
  }
}

void loop() {
  // 1. UPDATE ALL SERVOS SIMULTANEOUSLY
  updateServo(sLS);
  updateServo(sLE);
  updateServo(sRS);
  updateServo(sRE);
  updateServo(sLW);
  updateServo(sLG);
  updateServo(sRW);
  updateServo(sRG);

  // 2. NETWORK HANDLER
  if (!client.connected()) {
    if (client.connect(host, port)) {
      client.println("ARMS_V2_READY");
      Serial.println("Connected to Brain");
    } else {
      // Non-blocking reconnect delay logic
      static unsigned long lastReconnect = 0;
      if (millis() - lastReconnect > 2000) {
        lastReconnect = millis();
        // Try connect once
        return;
      }
      return;
    }
  }

  // 3. READ COMMANDS
  while (client.available()) {
    String line = client.readStringUntil('\n');
    line.trim();
    if (line.length() > 0) {
      Serial.println("Cmd: " + line);
      parseCommand(line);
    }
  }

  // 4. TELEMETRY (Send Temp every 5s)
  static unsigned long lastTemp = 0;
  if (millis() - lastTemp > 5000) {
    lastTemp = millis();
    if (client.connected()) {
      float temp = temperatureRead(); // ESP32 Internal Temp
      client.println("TEMP:" + String(temp));
    }
  }
}

void parseCommand(String cmd) {
  int sep = cmd.indexOf(':');
  if (sep == -1)
    return;
  String part = cmd.substring(0, sep);
  int val = cmd.substring(sep + 1).toInt();

  // Update TARGET only. loop() handles the movement.
  if (part == "LS") {
    if (val > SHOULDER_LIMIT)
      val = SHOULDER_LIMIT;
    sLS.targetPos = val;
  } else if (part == "LE")
    sLE.targetPos = val;
  else if (part == "RS") {
    if (val > SHOULDER_LIMIT)
      val = SHOULDER_LIMIT;
    sRS.targetPos = val;
  } else if (part == "RE")
    sRE.targetPos = val;
  else if (part == "LW")
    sLW.targetPos = val;
  else if (part == "LG")
    sLG.targetPos = val;
  else if (part == "RW")
    sRW.targetPos = val;
  else if (part == "RG")
    sRG.targetPos = val;
}
