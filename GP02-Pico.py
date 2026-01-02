from machine import Pin, UART
import time

# --- CONFIGURATION ---
ENABLE_PPS = True       
PPS_PIN_ID = 15         
UART_ID = 0             
TX_PIN = 0              
RX_PIN = 1              
# ---------------------

gps_uart = UART(UART_ID, baudrate=9600, tx=Pin(TX_PIN), rx=Pin(RX_PIN))
led = Pin("LED", Pin.OUT)

pps_state = {
    "count": 0, "last_tick": 0, "interval": 0, "new_pulse": False,
    "last_utc": "N/A", "last_date": "N/A"
}

current_data = {
    "lat": 0.0, "lon": 0.0, "sats": "0", "status": "V", 
    "time": "00:00:00", "date": "00/00/00", "alt": "0",
    "speed": 0.0, "course": "0.0", "hdop": "9.9", "pdop": "9.9", "vdop": "9.9",
    "fix_type": "None"
}

def parse_nmea(line):
    parts = line.split(',')
    if len(parts) < 10: return None
    
    # RMC: Position, Status, Speed, Course
    if 'RMC' in parts[0]:
        current_data['status'] = parts[2] 
        t = parts[1]
        current_data['time'] = f"{t[0:2]}:{t[2:4]}:{t[4:6]}" if len(t) >= 6 else t
        d = parts[9]
        current_data['date'] = f"{d[0:2]}/{d[2:4]}/{d[4:6]}" if len(d) >= 6 else d
        current_data['speed'] = float(parts[7]) if parts[7] else 0.0
        current_data['course'] = parts[8] if parts[8] else "0.0"
        try:
            if parts[3] and parts[5]:
                lat = float(parts[3][:2]) + float(parts[3][2:])/60
                if parts[4] == 'S': lat = -lat
                lon = float(parts[5][:3]) + float(parts[5][3:])/60
                if parts[6] == 'W': lon = -lon
                current_data['lat'], current_data['lon'] = lat, lon
        except: pass

    # GGA: Alt, Quality, Sats
    elif 'GGA' in parts[0]:
        current_data['sats'] = parts[7]
        current_data['alt'] = parts[9]
        qual = parts[6]
        current_data['fix_type'] = "GPS SPS" if qual=="1" else "DGPS" if qual=="2" else "No Fix"

    # GSA: Precision (The "Odds")
    elif 'GSA' in parts[0]:
        current_data['pdop'] = parts[15]
        current_data['hdop'] = parts[16]
        current_data['vdop'] = parts[17].split('*')[0]

def pps_handler(pin):
    current = time.ticks_ms()
    pps_state["count"] += 1
    if pps_state["last_tick"] != 0:
        pps_state["interval"] = time.ticks_diff(current, pps_state["last_tick"])
    pps_state["last_tick"] = current
    pps_state["last_utc"] = current_data["time"]
    pps_state["last_date"] = current_data["date"]
    pps_state["new_pulse"] = True

if ENABLE_PPS:
    pps_pin = Pin(PPS_PIN_ID, Pin.IN)
    pps_pin.irq(trigger=Pin.IRQ_RISING, handler=pps_handler)

last_print = 0
while True:
    if pps_state["new_pulse"]:
        pps_state["new_pulse"] = False
        led.toggle()

    while gps_uart.any():
        try:
            line = gps_uart.readline().decode('utf-8').strip()
            if '*' in line: parse_nmea(line)
        except: pass

    if time.ticks_diff(time.ticks_ms(), last_print) > 1000:
        print("\033[2J\033[H")
        kph = current_data['speed'] * 1.852 # Knots to KPH
        
        print(f"=== GNSS TACTICAL DASHBOARD ===")
        print(f"STATUS: {current_data['fix_type']} | SATS: {current_data['sats']}")
        print(f"PRECISION (DOP): P:{current_data['pdop']} H:{current_data['hdop']} V:{current_data['vdop']}")
        print(f"DATE:   {current_data['date']} | TIME: {current_data['time']} UTC")
        print(f"COORD:  {current_data['lat']:.6f}, {current_data['lon']:.6f}")
        print(f"MOTION: {kph:.2f} km/h @ {current_data['course']}°")
        print(f"ALT:    {current_data['alt']} M")

        if ENABLE_PPS:
            # History calculation: Calculate the "jitter" in the PPS signal
            jitter = abs(1000 - pps_state['interval'])
            print(f"\n--- PPS SYNC (Jitter: {jitter}ms) ---")
            print(f"PULSE #{pps_state['count']} | SYNC: {pps_state['last_utc']}")
        
        last_print = time.ticks_ms()
    time.sleep(0.5)