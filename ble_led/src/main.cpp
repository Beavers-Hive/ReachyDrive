#include <Arduino.h>
#include <BLEDevice.h>
#include <BLEUtils.h>
#include <BLEServer.h>
#include <FastLED.h>
#include <iostream>

#define SERVICE_UUID "4fafc201-1sb5-45ae-3fcc-c5c9c331914b"
#define CHARACTERISTIC_UUID "ceb5483e-36e1-2688-b7f5-ea07361d26a8"

#define NUM_LEDS 80
#define DATA_PIN 2

CRGB leds[NUM_LEDS];

enum LedMode {
  OFF,
  RED,
  GREEN,
  BLUE,
  PURPLE,
  PINK,
  RAINBOW,
  LOADING
};

LedMode currentMode = OFF;
BLECharacteristic *pCharacteristic;

// loadingアニメーションの設定用グローバル変数
CRGB loadingColor = CRGB::Blue;
int loadingSpeed = 20;

class MyServerCallbacks : public BLEServerCallbacks
{
  void onConnect(BLEServer *pServer) {}
  void onDisconnect(BLEServer *pServer)
  {
    BLEDevice::startAdvertising();
  }
};

class BleCallbacks : public BLECharacteristicCallbacks
{
  void onWrite(BLECharacteristic *pCharacteristic)
  {
    String command = pCharacteristic->getValue().c_str();
    if (command.length() > 0)
    {
      if (command == "red") currentMode = RED;
      else if (command == "green") currentMode = GREEN;
      else if (command == "blue") currentMode = BLUE;
      else if (command == "purple") currentMode = PURPLE;
      else if (command == "pink") currentMode = PINK;
      else if (command == "rainbow") currentMode = RAINBOW;
      else if (command == "loading") currentMode = LOADING;
      else if (command == "none") currentMode = OFF;
      else if (command.startsWith("s,"))
      {
        loadingSpeed = command.substring(2).toInt();
      }
      else if (command.startsWith("c,"))
      {
        // 形式: c,R,G,B (例: c,255,0,255)
        int firstComma = command.indexOf(',');
        int secondComma = command.indexOf(',', firstComma + 1);
        int thirdComma = command.indexOf(',', secondComma + 1);
        if (secondComma != -1 && thirdComma != -1)
        {
          uint8_t r = command.substring(firstComma + 1, secondComma).toInt();
          uint8_t g = command.substring(secondComma + 1, thirdComma).toInt();
          uint8_t b = command.substring(thirdComma + 1).toInt();
          loadingColor = CRGB(r, g, b);
        }
      }
    }
  }
};

void setup()
{
  Serial.begin(115200);
  FastLED.addLeds<WS2815, DATA_PIN, RGB>(leds, NUM_LEDS);
  FastLED.setBrightness(128);

  BLEDevice::init("LED");
  BLEServer *pServer = BLEDevice::createServer();
  pServer->setCallbacks(new MyServerCallbacks());
  BLEService *pService = pServer->createService(SERVICE_UUID);
  pCharacteristic = pService->createCharacteristic(
      CHARACTERISTIC_UUID,
      BLECharacteristic::PROPERTY_READ |
          BLECharacteristic::PROPERTY_WRITE |
          BLECharacteristic::PROPERTY_NOTIFY);
  pCharacteristic->setCallbacks(new BleCallbacks());
  pService->start();
  
  BLEAdvertising *pAdvertising = BLEDevice::getAdvertising();
  pAdvertising->addServiceUUID(SERVICE_UUID);
  pAdvertising->setScanResponse(true);
  pAdvertising->setMinPreferred(0x06);
  pAdvertising->setMinPreferred(0x12);
  BLEDevice::startAdvertising();
}

void showLoading()
{
  static int pos = 0;
  FastLED.clear();
  for(int i = 0; i < 5; i++) {
    int index = (pos + i) % NUM_LEDS;
    leds[index] = loadingColor;
  }
  pos = (pos + 1) % NUM_LEDS;
  FastLED.show();
  delay(loadingSpeed);
}

void showRainbow()
{
  static uint8_t hue = 0;
  fill_rainbow(leds, NUM_LEDS, hue, 7);
  hue++;
  FastLED.show();
  delay(10);
}

void loop()
{
  switch (currentMode)
  {
  case RED:
    fill_solid(leds, NUM_LEDS, CRGB::Red);
    FastLED.show();
    break;
  case GREEN:
    fill_solid(leds, NUM_LEDS, CRGB::Green);
    FastLED.show();
    break;
  case BLUE:
    fill_solid(leds, NUM_LEDS, CRGB::Blue);
    FastLED.show();
    break;
  case PURPLE:
    fill_solid(leds, NUM_LEDS, CRGB::Purple);
    FastLED.show();
    break;
  case PINK:
    fill_solid(leds, NUM_LEDS, CRGB::DeepPink);
    FastLED.show();
    break;
  case RAINBOW:
    showRainbow();
    break;
  case LOADING:
    showLoading();
    break;
  case OFF:
  default:
    FastLED.clear();
    FastLED.show();
    break;
  }

  if (Serial.available() > 0)
  {
    String buffer = Serial.readStringUntil('\n');
    pCharacteristic->setValue(buffer.c_str());
    pCharacteristic->notify();
  }
}