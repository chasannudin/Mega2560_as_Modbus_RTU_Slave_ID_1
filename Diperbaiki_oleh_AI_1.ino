#include <modbus.h>
#include <modbusDevice.h>
#include <modbusRegBank.h>
#include <modbusSlave.h>
modbusDevice regBank;
modbusSlave slave;
#include <DS3231.h>
#include <Wire.h>
DS3231 Clock;
#include <LiquidCrystal_I2C.h>
LiquidCrystal_I2C lcd(0x3F,16,2);

#define SLAVE_ID 1   //isi Slave ID Modbus RTU
#define GREEN_LED 3
#define INTERNAL_LED LED_BUILTIN
#define RED_LED 5
#define BUTTON 2
#define POTENTIOMETER A0
#define echoPin 12 // attach pin 12 Arduino to pin Echo of HC-SR04
#define trigPin 11 //attach pin 11 Arduino to pin Trig of HC-SR04

long duration; // variable for the duration of sound wave travel
int distance_cm; // variable for centimeters measurement
byte Year;
byte Month;
byte Date;
byte DoW;
byte Hour;
byte Minute;
byte Second;
bool Century=false;
bool h12;
bool PM;

// Variabel Penjadwalan Waktu (Non-blocking)
unsigned long prevMillisSensor = 0;
unsigned long prevMillisLCD = 0;
const long intervalSensor = 200; // Baca ultrasonic setiap 200ms
const long intervalLCD = 500;    // Update LCD setiap 500ms

void setup()
{ 
  pinMode(trigPin, OUTPUT); // Sets the trigPin as an OUTPUT
  pinMode(echoPin, INPUT); // Sets the echoPin as an INPUT  
  
  Wire.begin();
  Clock.setClockMode(false);  // set to 24h
  
  pinMode(GREEN_LED, OUTPUT);
  pinMode(INTERNAL_LED, OUTPUT);
  pinMode(RED_LED, OUTPUT);
  pinMode(BUTTON, INPUT_PULLUP);
  
  lcd.init();                      
  lcd.init();
  lcd.backlight();
  lcd.setCursor(0,0);
  lcd.print("   MODBUS RTU   ");
  lcd.setCursor(1,1);
  lcd.print("  Chasannudin   ");
  delay(3000); 
  lcd.clear();
  
  regBank.setId(SLAVE_ID);

  //Add Digital Output registers
  regBank.add(1);
  regBank.add(2); //Data Lampu internal
  regBank.add(3); //Data HMI tombol set RTC
  regBank.add(4); //Data HMI tombol get Data RTC

  //Add Digital Input registers
  regBank.add(10001);
  
  //Add Analog Output registers  
  regBank.add(40010); 
  regBank.add(40011);
  regBank.add(40012);
  regBank.add(40013);
  regBank.add(40014);
  regBank.add(40015);
  regBank.add(40016);
  regBank.add(40017);  
  
  //Analog input registers
  regBank.add(30001);
  regBank.add(30011); //Data tahun
  regBank.add(30012); //Data bulan
  regBank.add(30013); //Data tanggal
  regBank.add(30014); //Data DoW
  regBank.add(30015); //Data Jam
  regBank.add(30016); // Data Menit
  regBank.add(30017); // Data Detik
  regBank.add(30018); // Data Temperature
  
  slave._device = &regBank; 
  slave.setBaud(9600);  
}

void loop()
{
  // Ambil data waktu dari RTC sekali saja di awal loop untuk efisiensi
  Hour   = Clock.getHour(h12, PM);
  Minute = Clock.getMinute();
  Second = Clock.getSecond();
  Date   = Clock.getDate();
  Month  = Clock.getMonth(Century);
  Year   = Clock.getYear();

  // --- 1. DIGITAL OUTPUT LOGIC ---
  int DO3 = regBank.get(1);
  digitalWrite(GREEN_LED, (DO3 >= 1) ? HIGH : LOW);

  int DOinternal = regBank.get(2);
  digitalWrite(INTERNAL_LED, (DOinternal >= 1) ? HIGH : LOW);

  int setRTC = regBank.get(3); 
  if (setRTC >= 1){
      Clock.setYear(regBank.get(40011));
      Clock.setMonth(regBank.get(40012));
      Clock.setDate(regBank.get(40013));
      Clock.setDoW(regBank.get(40014));
      Clock.setHour(regBank.get(40015));
      Clock.setMinute(regBank.get(40016));
      Clock.setSecond(regBank.get(40017));
      regBank.set(3, 0); // Kembali menggunakan .set() & mereset tombol HMI ke 0
  }

  int getRTC = regBank.get(4); 
  if (getRTC >= 1){
      regBank.set(40011, (word)Year); 
      regBank.set(40012, (word)Month); 
      regBank.set(40013, (word)Date); 
      regBank.set(40014, (word)Clock.getDoW()); 
      regBank.set(40015, (word)Hour); 
      regBank.set(40016, (word)Minute); 
      regBank.set(40017, (word)Second); 
      regBank.set(4, 0); // Koreksi: alamat diubah dari 400 ke 4 sesuai inisialisasi di setup
  }
  
  // --- 2. DIGITAL INPUT LOGIC ---
  byte DI2 = digitalRead(BUTTON);
  regBank.set(10001, (DI2 == LOW) ? 1 : 0); 

  // --- 3. SENSOR & ANALOG INPUT LOGIC (Diproses berkala via millis) ---
  unsigned long currentMillis = millis();
  if (currentMillis - prevMillisSensor >= intervalSensor) {
    prevMillisSensor = currentMillis;

    // Baca HC-SR04
    digitalWrite(trigPin, LOW);
    delayMicroseconds(2);
    digitalWrite(trigPin, HIGH);
    delayMicroseconds(10);
    digitalWrite(trigPin, LOW);
    duration = pulseIn(echoPin, HIGH, 30000); 
    distance_cm = duration * 0.034 / 2;

    // Update Modbus Register Bank
    regBank.set(30001, distance_cm);
    regBank.set(30011, (word)Year); 
    regBank.set(30012, (word)Month); 
    regBank.set(30013, (word)Date); 
    regBank.set(30014, (word)Clock.getDoW()); 
    regBank.set(30015, (word)Hour); 
    regBank.set(30016, (word)Minute); 
    regBank.set(30017, (word)Second); 
    regBank.set(30018, (word)Clock.getTemperature());
  }
  
  // --- 4. ANALOG OUTPUT LOGIC ---
  word AO10 = regBank.get(40010);
  analogWrite(RED_LED, AO10);
    
  // --- 5. RUN MODBUS (Eksekusi Non-blocking secepat mungkin) ---
  slave.run();
  
  // --- 6. UPDATE LCD (Diproses berkala via millis) ---
  if (currentMillis - prevMillisLCD >= intervalLCD) {
    prevMillisLCD = currentMillis;
    digitalClockDisplay();
  }
}

void digitalClockDisplay()
{
    lcd.setCursor(0,0);
    lcd.print("Time: ");
    if(Hour < 10) lcd.print('0');
    lcd.print(Hour);
    lcd.print(":");
    if(Minute < 10) lcd.print('0');
    lcd.print(Minute);
    lcd.print(":");
    if(Second < 10) lcd.print('0');
    lcd.print(Second);
    lcd.print("   "); 

    lcd.setCursor(0,1);
    lcd.print("Date: ");
    if(Date < 10) lcd.print('0');
    lcd.print(Date);
    lcd.print("/");
    if(Month < 10) lcd.print('0');
    lcd.print(Month);
    lcd.print("/");
    lcd.print(Year);
    lcd.print("   ");
}
