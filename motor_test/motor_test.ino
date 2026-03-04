// Simple BTS7960 Motor Test
// Upload this to test if motors work at all

const int L_PWM_LEFT = 13;
const int R_PWM_LEFT = 12;
const int L_PWM_RIGHT = 14;
const int R_PWM_RIGHT = 27;

void setup() {
  Serial.begin(115200);
  Serial.println("BTS7960 Motor Test Starting...");

  // Setup PWM
  ledcAttach(L_PWM_LEFT, 1000, 8);
  ledcAttach(R_PWM_LEFT, 1000, 8);
  ledcAttach(L_PWM_RIGHT, 1000, 8);
  ledcAttach(R_PWM_RIGHT, 1000, 8);

  // Stop all
  ledcWrite(L_PWM_LEFT, 0);
  ledcWrite(R_PWM_LEFT, 0);
  ledcWrite(L_PWM_RIGHT, 0);
  ledcWrite(R_PWM_RIGHT, 0);

  delay(2000);

  Serial.println("Testing LEFT motors FORWARD...");
  ledcWrite(L_PWM_LEFT, 200); // Left forward
  ledcWrite(R_PWM_LEFT, 0);
  delay(2000);
  ledcWrite(L_PWM_LEFT, 0);
  delay(1000);

  Serial.println("Testing LEFT motors BACKWARD...");
  ledcWrite(L_PWM_LEFT, 0);
  ledcWrite(R_PWM_LEFT, 200); // Left backward
  delay(2000);
  ledcWrite(R_PWM_LEFT, 0);
  delay(1000);

  Serial.println("Testing RIGHT motors FORWARD...");
  ledcWrite(L_PWM_RIGHT, 200); // Right forward
  ledcWrite(R_PWM_RIGHT, 0);
  delay(2000);
  ledcWrite(L_PWM_RIGHT, 0);
  delay(1000);

  Serial.println("Testing RIGHT motors BACKWARD...");
  ledcWrite(L_PWM_RIGHT, 0);
  ledcWrite(R_PWM_RIGHT, 200); // Right backward
  delay(2000);
  ledcWrite(R_PWM_RIGHT, 0);
  delay(1000);

  Serial.println("Testing ALL motors FORWARD...");
  ledcWrite(L_PWM_LEFT, 200);
  ledcWrite(L_PWM_RIGHT, 200);
  delay(2000);
  ledcWrite(L_PWM_LEFT, 0);
  ledcWrite(L_PWM_RIGHT, 0);

  Serial.println("Test complete! Motors should have moved.");
  Serial.println("If they didn't, check:");
  Serial.println("1. L_EN and R_EN connected to +5V on BOTH drivers");
  Serial.println("2. Common ground between ESP32 and drivers");
  Serial.println("3. Motor wires connected to M+ and M-");
  Serial.println("4. Battery voltage is 12V");
}

void loop() {
  // Do nothing
  delay(1000);
}
