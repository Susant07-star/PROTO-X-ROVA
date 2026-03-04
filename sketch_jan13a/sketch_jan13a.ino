#include "driver/i2s.h"
#include <Arduino.h>
#include <WiFi.h>
#include <climits>
#include <cmath>

// WiFi Configuration
const char *ssid = "DigitalSusant";
const char *password = "thisisthewifi";
const char *serverIP = "192.168.137.1";
const int serverPort = 4000;

WiFiClient client;

// --- MOTOR PINS & PWM (LEDC) CONFIG ---
// BTS7960
const int L_PWM_LEFT = 13;
const int R_PWM_LEFT = 12;
const int L_PWM_RIGHT = 14;
const int R_PWM_RIGHT = 27;

// LEDC Channels (0-15) - Not strictly needed in v3 but good for reference if we
// need to track logic
#define CH_L_FWD 0
#define CH_L_BCK 1
#define CH_R_FWD 2
#define CH_R_BCK 3

void setupMotors() {
  // ESP32 CORE 3.x API
  // ledcAttach(pin, frequency, resolution_bits);

  ledcAttach(L_PWM_LEFT, 1000, 8);
  ledcAttach(R_PWM_LEFT, 1000, 8);
  ledcAttach(L_PWM_RIGHT, 1000, 8);
  ledcAttach(R_PWM_RIGHT, 1000, 8);

  // Stop initially
  ledcWrite(L_PWM_LEFT, 0);
  ledcWrite(R_PWM_LEFT, 0);
  ledcWrite(L_PWM_RIGHT, 0);
  ledcWrite(R_PWM_RIGHT, 0);

  Serial.println("✅ Motors Initialized (LEDC v3 PWM)");
}

void setMotors(int leftSpeed, int rightSpeed) {
  Serial.printf("🚗 MOTOR L=%d R=%d\n", leftSpeed, rightSpeed);

  // LEFT MOTOR
  if (leftSpeed > 0) {
    ledcWrite(L_PWM_LEFT, leftSpeed);
    ledcWrite(R_PWM_LEFT, 0);
  } else if (leftSpeed < 0) {
    ledcWrite(L_PWM_LEFT, 0);
    ledcWrite(R_PWM_LEFT, -leftSpeed);
  } else {
    ledcWrite(L_PWM_LEFT, 0);
    ledcWrite(R_PWM_LEFT, 0);
  }

  // RIGHT MOTOR
  if (rightSpeed > 0) {
    ledcWrite(L_PWM_RIGHT, rightSpeed);
    ledcWrite(R_PWM_RIGHT, 0);
  } else if (rightSpeed < 0) {
    ledcWrite(L_PWM_RIGHT, 0);
    ledcWrite(R_PWM_RIGHT, -rightSpeed);
  } else {
    ledcWrite(L_PWM_RIGHT, 0);
    ledcWrite(R_PWM_RIGHT, 0);
  }
}

void playTone(int freq, int durationMs) {
  size_t bytes_written;
  int totalSamples = 16000 * durationMs / 1000;
  int chunkSize = 128;
  int32_t buffer[chunkSize * 2];

  for (int i = 0; i < totalSamples; i += chunkSize) {
    int samplesToDo =
        (i + chunkSize > totalSamples) ? (totalSamples - i) : chunkSize;

    for (int j = 0; j < samplesToDo; j++) {
      int16_t wave = (int16_t)(10000 * sin(2 * PI * freq * (i + j) / 16000.0));
      int32_t val = ((int32_t)wave) << 16;
      buffer[2 * j] = val;
      buffer[2 * j + 1] = val;
    }
    i2s_write(I2S_NUM_0, buffer, samplesToDo * 8, &bytes_written,
              portMAX_DELAY);
  }
}

const i2s_port_t I2S_PORT = I2S_NUM_0;
const int BLOCK_SIZE = 128;

unsigned long last_voice_activity = 0;
const int PAUSE_THRESHOLD = 500;
unsigned long motorStopTime = 0;

void setup() {
  Serial.begin(115200);
  delay(500);

  setupMotors();

  // I2S Config
  i2s_config_t i2s_config = {
      .mode = i2s_mode_t(I2S_MODE_MASTER | I2S_MODE_RX | I2S_MODE_TX),
      .sample_rate = 16000,
      .bits_per_sample = I2S_BITS_PER_SAMPLE_32BIT,
      .channel_format = I2S_CHANNEL_FMT_RIGHT_LEFT,
      .communication_format =
          i2s_comm_format_t(I2S_COMM_FORMAT_I2S | I2S_COMM_FORMAT_I2S_MSB),
      .intr_alloc_flags = ESP_INTR_FLAG_LEVEL1,
      .dma_buf_count = 8,
      .dma_buf_len = 256,
      .use_apll = false,
      .tx_desc_auto_clear = true,
      .fixed_mclk = 0};

  i2s_pin_config_t pin_config = {
      .bck_io_num = 26, .ws_io_num = 22, .data_out_num = 25, .data_in_num = 34};

  i2s_driver_install(I2S_PORT, &i2s_config, 0, NULL);
  i2s_set_pin(I2S_PORT, &pin_config);
  i2s_zero_dma_buffer(I2S_PORT);

  // WiFi Connection
  WiFi.mode(WIFI_STA);
  Serial.print("Connecting to WiFi");
  WiFi.begin(ssid, password);
  while (WiFi.status() != WL_CONNECTED) {
    delay(500);
    Serial.print(".");
  }
  Serial.println("\nWiFi Connected!");
  Serial.print("IP: ");
  Serial.println(WiFi.localIP());

  // Connect to Server
  Serial.print("Connecting to Server IP: ");
  Serial.println(serverIP);
  client.setNoDelay(true);
  client.setTimeout(5000);

  while (!client.connect(serverIP, serverPort)) {
    delay(1000);
    Serial.print(".");
  }
  Serial.println("\nConnected to Server!");

  playTone(440, 500);
}

void loop() {
  if (!client.connected()) {
    Serial.println("Disconnected! Reconnecting...");
    setMotors(0, 0);
    while (!client.connect(serverIP, serverPort)) {
      delay(1000);
    }
    Serial.println("Reconnected!");
  }

  // 1. RECORDING
  if (client.available() == 0 &&
      (millis() - last_voice_activity > PAUSE_THRESHOLD)) {
    int32_t samples[BLOCK_SIZE * 2];
    size_t bytes_read = 0;

    esp_err_t result = i2s_read(I2S_PORT, (void *)samples, sizeof(samples),
                                &bytes_read, 10 / portTICK_PERIOD_MS);

    if (result == ESP_OK && bytes_read > 0) {
      int samples_read = bytes_read / 8;
      int16_t output_buffer[BLOCK_SIZE];

      for (int i = 0; i < samples_read; i++) {
        int32_t left = samples[i * 2] >> 16;
        int32_t right = samples[i * 2 + 1] >> 16;
        int32_t mixed = left + right;
        if (mixed > 32767)
          mixed = 32767;
        if (mixed < -32768)
          mixed = -32768;
        output_buffer[i] = (int16_t)mixed;
      }

      if (client.availableForWrite() >= samples_read * 2) {
        client.write((uint8_t *)output_buffer, samples_read * 2);
      }
    }
  }

  // 2. PLAYBACK & COMMANDS
  if (client.available()) {
    last_voice_activity = millis();
    size_t len = client.available();

    size_t max_read = 512;
    if (len > max_read)
      len = max_read;

    if (len > 0) {
      uint8_t buffer[512];
      size_t bytesRead = client.readBytes(buffer, len);

      // --- COMMAND PARSING ---
      if (bytesRead >= 5) {
        for (int i = 0; i < bytesRead - 4; i++) {
          if (buffer[i] == 'C' && buffer[i + 1] == 'M' &&
              buffer[i + 2] == 'D' && buffer[i + 3] == ':') {

            char cmd = buffer[i + 4];
            int duration = 0;

            Serial.printf("RX CMD: %c\n", cmd);

            if (i + 5 < bytesRead && buffer[i + 5] == ':') {
              int k = i + 6;
              String numStr = "";
              while (k < bytesRead && isDigit(buffer[k])) {
                numStr += (char)buffer[k];
                k++;
              }
              duration = numStr.toInt();
            }

            int speed = 200;

            if (cmd == 'F') {
              Serial.println("✅ FORWARD command received");
              setMotors(speed, speed);
            } else if (cmd == 'B') {
              Serial.println("✅ BACKWARD command received");
              setMotors(-speed, -speed);
            } else if (cmd == 'L') {
              Serial.println("✅ LEFT command received");
              setMotors(-speed, 200);
            } else if (cmd == 'R') {
              Serial.println("✅ RIGHT command received");
              setMotors(200, -speed);
            } else if (cmd == 'S') {
              Serial.println("✅ STOP command received");
              setMotors(0, 0);
            } else if (cmd == 'X') {
              Serial.println("✅ STOP (X) command received");
              setMotors(0, 0);
            } else {
              Serial.printf("❌ Unknown command: %c\n", cmd);
            }

            if (duration > 0 && cmd != 'S') {
              motorStopTime = millis() + duration;
              Serial.printf("Keeping for %d ms\n", duration);
            } else {
              motorStopTime = 0;
            }

            // Zero out command bytes
            for (int k = i; k < i + 10 && k < bytesRead; k++) {
              buffer[k] = 0;
            }
          }
        }
      }

      // --- PLAY AUDIO ---
      size_t validLen = bytesRead;
      if (validLen % 2 != 0)
        validLen--;

      if (validLen > 0) {
        size_t samples_read = validLen / 2;
        int16_t *input_16 = (int16_t *)buffer;
        int32_t i2s_write_buffer[512];

        for (int i = 0; i < samples_read; i++) {
          int32_t val = ((int32_t)input_16[i]) << 16;
          i2s_write_buffer[2 * i] = val;
          i2s_write_buffer[2 * i + 1] = val;
        }

        size_t bytes_written = 0;
        i2s_write(I2S_PORT, i2s_write_buffer, samples_read * 2 * 4,
                  &bytes_written, portMAX_DELAY);
      }
    }
  }

  // --- AUTO STOP MOTOR ---
  if (motorStopTime > 0 && millis() > motorStopTime) {
    setMotors(0, 0);
    motorStopTime = 0;
    Serial.println("🛑 Auto Stop");
  }

  // --- TELEMETRY ---
  static unsigned long lastTemp = 0;
  if (millis() - lastTemp > 5000) {
    lastTemp = millis();
    if (client.connected()) {
      float temp = temperatureRead();
      client.println("TEMP:" + String(temp));
    }
  }
}
