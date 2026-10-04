#include <OneWire.h>
#include <DallasTemperature.h>
#include <Wire.h>

#define ONE_WIRE_BUS 2
OneWire oneWire(ONE_WIRE_BUS);
DallasTemperature sensors(&oneWire);

const int MPU_ADDR = 0x68;

void setup(void) {
  Serial.begin(9600);
  
  sensors.begin();
  
  Wire.begin();
  Wire.beginTransmission(MPU_ADDR);
  Wire.write(0x6B);
  Wire.write(0);
  Wire.endTransmission(true);
}

void loop(void) {
  sensors.requestTemperatures(); 
  float tempF = sensors.getTempFByIndex(0);
  
  Wire.beginTransmission(MPU_ADDR);
  Wire.write(0x3B);
  Wire.endTransmission(false);
  Wire.requestFrom(MPU_ADDR, 6);
  
  int16_t AcX = Wire.read() << 8 | Wire.read();
  int16_t AcY = Wire.read() << 8 | Wire.read();
  int16_t AcZ = Wire.read() << 8 | Wire.read();
  
  float ax = (AcX / 16384.0) * 9.81;
  float ay = (AcY / 16384.0) * 9.81;
  float az = (AcZ / 16384.0) * 9.81;
  
  float accel_magnitude = sqrt(sq(ax) + sq(ay) + sq(az));
  
  Serial.print(tempF);
  Serial.print(",");
  Serial.println(accel_magnitude);
  
  delay(200); 
}