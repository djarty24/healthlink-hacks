#include <OneWire.h>
#include <DallasTemperature.h>

// The yellow data wire is plugged into port 2 on the Arduino
#define ONE_WIRE_BUS 2

// Setup a oneWire instance to communicate with any OneWire devices
OneWire oneWire(ONE_WIRE_BUS);

// Pass our oneWire reference to Dallas Temperature sensor 
DallasTemperature sensors(&oneWire);

void setup(void) {
  Serial.begin(9600);
  sensors.begin(); // Start up the library
}

void loop(void) { 
  // Send the command to get temperatures
  sensors.requestTemperatures(); 
  
  // We use 0 because there is only one sensor on the wire
  float tempF = sensors.getTempFByIndex(0);
  
  // Print ONLY the number so Python can read it easily
  Serial.println(tempF);
  
  delay(500); // Read twice a second
}