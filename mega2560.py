import time
import json
import paho.mqtt.client as mqtt
from pymodbus.client import ModbusSerialClient
from pymodbus.exceptions import ModbusIOException, ConnectionException

# ==============================================================================
# 1. KONFIGURASI UTAMA (Silakan sesuaikan jika perlu)
# ==============================================================================
MQTT_BROKER = "localhost"
MQTT_PORT = 1883
MQTT_TOPIC_READ = "v1/system/rs485"
# TOPIK UNTUK MENERIMA PERINTAH TULIS DARI NODE-RED
MQTT_TOPIC_WRITE_HOLDING = "v1/system/rs485/write/holding"
MQTT_TOPIC_WRITE_BUTTON = "v1/system/rs485/write/button"
# BARU: Topik khusus untuk 5 push button boolean (Register 10001-10005)
MQTT_TOPIC_WRITE_BOOLEAN = "v1/system/rs485/write/boolean"

# Konfigurasi Modbus RTU Serial (Arduino Mega 2560)
MODBUS_PORT = '/dev/ttyACM0'
BAUDRATE = 9600
PARITY = 'N'
STOPBITS = 1
BYTESIZE = 8

# Parameter Register Modbus
SLAVE_ID = 1
START_ADDRESS = 10  # Register 30011 (1-based) -> Address 10 (0-based)
QUANTITY = 8        # Membaca 8 buah register (dari 30011 sampai 30018)
DELAY_DETIK = 1     # Delay pembacaan data (1 detik)

# ==============================================================================
# 2. INISIALISASI & CALLBACK MQTT (Format Paho v1.x Lama)
# ==============================================================================
def on_connect(client, userdata, flags, rc):
    if rc == 0:
        print("[MQTT] Terhubung dengan sukses ke MQTT Broker!")
        # Berlangganan (Subscribe) ke topik penulisan data dari Node-RED
        client.subscribe(MQTT_TOPIC_WRITE_HOLDING)
        client.subscribe(MQTT_TOPIC_WRITE_BUTTON)
        client.subscribe(MQTT_TOPIC_WRITE_BOOLEAN) # BARU: Subscribe topik boolean
        print(f"[MQTT] Berhasil subscribe ke topik tulis data.")
    else:
        print(f"[MQTT] Gagal terhubung, kode respon: {rc}")

def on_message(client, userdata, msg):
    """ Callback ini akan berjalan setiap ada data masuk dari Node-RED """
    try:
        topic = msg.topic
        payload_str = msg.payload.decode('utf-8')
        
        # PROSES 1: Menulis ke Holding Register (40011 - 40017)
        if topic == MQTT_TOPIC_WRITE_HOLDING:
            data = json.loads(payload_str)
            target_reg = int(data.get("register")) # Input user: 40011 s/d 40017
            nilai_tulis = int(data.get("value"))
            
            # Validasi range register 40011-40017
            if 40011 <= target_reg <= 40017:
                # Pemetaan ke 0-based address: 40011 dihitung sebagai address 10
                modbus_address = target_reg - 40011 + 10
                # Eksekusi tulis Modbus
                res = modbus_client.write_register(address=modbus_address, value=nilai_tulis, device_id=SLAVE_ID)
                if res.isError():
                    print(f"[Modbus Write Error] Gagal menulis ke register {target_reg}: {res}")
                else:
                    print(f"[Modbus Write Success] Register {target_reg} (Addr: {modbus_address}) diisi nilai: {nilai_tulis}")
            else:
                print(f"[Warning] Register {target_reg} di luar jangkauan area kerja (40011-40017)!")
                
        # PROSES 2: Menulis ke Register 3 (Push Button Int)
        elif topic == MQTT_TOPIC_WRITE_BUTTON:
            nilai_tombol = int(payload_str)
            address_tombol = 2
            res = modbus_client.write_register(address=address_tombol, value=nilai_tombol, device_id=SLAVE_ID)
            if res.isError():
                print(f"[Modbus Write Error] Gagal menulis tombol ke Register 3: {res}")
            else:
                print(f"[Modbus Write Success] Register 3 (Push Button) diisi nilai: {nilai_tombol}")
                
        # BARU - PROSES 3: Menulis data Boolean ke Coil/Register 10001 s/d 10005
        elif topic == MQTT_TOPIC_WRITE_BOOLEAN:
            data = json.loads(payload_str)
            target_reg = int(data.get("register")) # Input: 10001 sampai 10005
            nilai_bool = bool(data.get("value")) # Input: true atau false
            
            # Validasi range register 10001-10005
            if 10001 <= target_reg <= 10005:
                # Standar Modbus Coil: Register 10001-10005 dipetakan ke Address 0-4 (0-based)
                coil_address = target_reg - 10001
                # Eksekusi tulis Coil Boolean ke Modbus
                res = modbus_client.write_coil(address=coil_address, value=nilai_bool, device_id=SLAVE_ID)
                if res.isError():
                    print(f"[Modbus Write Error] Gagal menulis boolean ke register {target_reg}: {res}")
                else:
                    print(f"[Modbus Write Success] Boolean Register {target_reg} (Addr: {coil_address}) diisi nilai: {nilai_bool}")
            else:
                print(f"[Warning] Push button register {target_reg} di luar jangkauan (10001-10005)!")
                
    except Exception as e:
        print(f"[MQTT Recv Error] Gagal memproses data tulis: {e}")

# Inisialisasi client MQTT versi lama sesuai format Anda
mqtt_client = mqtt.Client()
mqtt_client.on_connect = on_connect
mqtt_client.on_message = on_message # Pasang fungsi penangkap pesan

try:
    print(f"[MQTT] Menghubungkan ke Broker {MQTT_BROKER}:{MQTT_PORT}...")
    mqtt_client.connect(MQTT_BROKER, MQTT_PORT, 60)
    mqtt_client.loop_start()
except Exception as e:
    print(f"[MQTT Error] Koneksi broker gagal: {e}")
    exit(1)

# ==============================================================================
# 3. INISIALISASI MODBUS RTU CLIENT
# ==============================================================================
modbus_client = ModbusSerialClient(
    port=MODBUS_PORT,
    baudrate=BAUDRATE,
    parity=PARITY,
    stopbits=STOPBITS,
    bytesize=BYTESIZE,
    timeout=1
)

print(f"[Modbus] Membuka port serial {MODBUS_PORT}...")
if not modbus_client.connect():
    print(f"[Modbus Error] Gagal membuka port serial {MODBUS_PORT}!")
    print("-> Solusi: Pastikan kabel terpasang dan jalankan 'sudo chmod 666 /dev/ttyACM0' di terminal.")
    mqtt_client.loop_stop()
    mqtt_client.disconnect()
    exit(1)

print("\n=== SEMUA KONEKSI SIAP ===")
print(f"Membaca data setiap {DELAY_DETIK} detik. Menunggu perintah tulis dari Node-RED...")
print("Tekan Ctrl+C untuk menghentikan program.\n")

# ==============================================================================
# 4. LOOP UTAMA PEMBACAAN DAN PENGIRIMAN DATA
# ==============================================================================
try:
    while True:
        payload = {}
        status_baca_sukses = False
        
        # ----------------------------------------------------------------------
        # TAMBAHAN: Membaca Input Register 30001 (Address 0)
        # ----------------------------------------------------------------------
        try:
            response_30001 = modbus_client.read_input_registers(
                address=0, 
                count=1, 
                device_id=SLAVE_ID
            )
            if response_30001 and not response_30001.isError():
                payload["register_30001"] = response_30001.registers[0]
                status_baca_sukses = True
            else:
                print(f"[Modbus Warning] Gagal membaca register 30001: {response_30001}")
        except (ModbusIOException, ConnectionException, Exception) as err_30001:
            print(f"[Hardware Error] Gagal baca register 30001: {err_30001}")

        # ----------------------------------------------------------------------
        # ASLI: Membaca Input Registers 30011 s/d 30018 (Address 10, Count 8)
        # ----------------------------------------------------------------------
        try:
            response = modbus_client.read_input_registers(
                address=START_ADDRESS,
                count=QUANTITY,
                device_id=SLAVE_ID
            )
            if response and not response.isError():
                registers_data = response.registers
                status_baca_sukses = True
                # Memetakan nilai register ke dalam format JSON (register_30011 sampai register_30018)
                for i, val in enumerate(registers_data):
                    reg_num = 30011 + i
                    payload[f"register_{reg_num}"] = val
            else:
                print(f"[Modbus Warning] Perangkat merespon, namun terjadi Modbus Error pada 30011-30018: {response}")
                if not status_baca_sukses:
                    payload["modbus_status"] = "modbus_error"
        except (ModbusIOException, ConnectionException, Exception) as hw_err:
            print(f"[Hardware Error] Gagal berkomunikasi fisik dengan Arduino (30011-30018): {hw_err}")
            if not status_baca_sukses:
                payload["modbus_status"] = "hardware_timeout_or_disconnected"

        # Set status sukses jika salah satu atau semua register berhasil dibaca
        if status_baca_sukses and "modbus_status" not in payload:
            payload["modbus_status"] = "success"

        # Menambahkan data waktu pengiriman
        payload["timestamp"] = int(time.time())

        # Mengirimkan payload gabungan ke MQTT Broker (Membaca)
        try:
            json_payload = json.dumps(payload)
            mqtt_client.publish(MQTT_TOPIC_READ, json_payload)
            # Cetak logs baca ke layar terminal
            print(f"[Sent to MQTT] Topic: {MQTT_TOPIC_READ}")
            print(json.dumps(payload, indent=4))
            print("-" * 50)
        except Exception as mqtt_err:
            print(f"[MQTT Error] Gagal mempublikasikan data: {mqtt_err}")

        # Jeda interval waktu pembacaan (1 detik)
        time.sleep(DELAY_DETIK)

except KeyboardInterrupt:
    print("\n[Sistem] Program dihentikan oleh pengguna via Ctrl+C.")
finally:
    modbus_client.close()
    print("[Clean Up] Koneksi Modbus ditutup.")
    mqtt_client.loop_stop()
    mqtt_client.disconnect()
    print("(Clean Up) Koneksi MQTT Ditutup. Selesai.")

