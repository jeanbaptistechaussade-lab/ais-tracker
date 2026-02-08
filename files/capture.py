#!/usr/bin/env python3
"""
AIS Capture Script - Reads AIS messages and stores in database
With error logging and diagnostics
"""

import sqlite3
import sys
import subprocess
from datetime import datetime
import json
import os

DB_PATH = '/home/pi/ais-server/ais_db.sqlite'
ERROR_LOG = '/home/pi/ais-server/errors.log'
MAX_LOG_SIZE = 10 * 1024 * 1024  # 10 MB

def log_error(message):
    """Log error to file with rotation"""
    try:
        # Check log size and rotate if needed
        if os.path.exists(ERROR_LOG) and os.path.getsize(ERROR_LOG) > MAX_LOG_SIZE:
            if os.path.exists(ERROR_LOG + '.old'):
                os.remove(ERROR_LOG + '.old')
            os.rename(ERROR_LOG, ERROR_LOG + '.old')
        
        with open(ERROR_LOG, 'a') as f:
            timestamp = datetime.utcnow().isoformat()
            f.write(f"[{timestamp}] {message}\n")
    except Exception as e:
        print(f"Failed to log error: {e}", file=sys.stderr)

def init_db():
    """Create database if it doesn't exist"""
    try:
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        c.execute('''
            CREATE TABLE IF NOT EXISTS vessels (
                mmsi TEXT PRIMARY KEY,
                name TEXT,
                latitude REAL,
                longitude REAL,
                speed REAL,
                course REAL,
                heading INTEGER,
                timestamp TEXT,
                vessel_type TEXT,
                callsign TEXT,
                imo TEXT,
                dimension_bow INTEGER,
                dimension_stern INTEGER,
                dimension_port INTEGER,
                dimension_starboard INTEGER,
                draught REAL,
                destination TEXT,
                nav_status TEXT,
                last_updated TEXT
            )
        ''')
        
        # Create diagnostics table
        c.execute('''
            CREATE TABLE IF NOT EXISTS diagnostics (
                key TEXT PRIMARY KEY,
                value TEXT,
                updated TEXT
            )
        ''')
        
        conn.commit()
        conn.close()
        print("[DB] Database initialized", file=sys.stderr)
    except Exception as e:
        log_error(f"Database init failed: {e}")
        raise

def update_diagnostic(key, value):
    """Update diagnostic value"""
    try:
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        now = datetime.utcnow().isoformat() + 'Z'
        c.execute('''
            INSERT OR REPLACE INTO diagnostics (key, value, updated)
            VALUES (?, ?, ?)
        ''', (key, str(value), now))
        conn.commit()
        conn.close()
    except Exception as e:
        log_error(f"Failed to update diagnostic {key}: {e}")

def update_vessel(data):
    """Add or update vessel in database"""
    try:
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        
        mmsi = data.get('mmsi')
        if not mmsi:
            conn.close()
            return
        
        now = datetime.utcnow().isoformat() + 'Z'
        
        # Check if vessel exists
        c.execute('SELECT mmsi FROM vessels WHERE mmsi = ?', (mmsi,))
        exists = c.fetchone()
        
        if exists:
            # Update existing vessel
            update_fields = []
            update_values = []
            
            if 'name' in data and data['name']:
                update_fields.append('name = ?')
                update_values.append(data['name'])
            if 'latitude' in data:
                update_fields.append('latitude = ?')
                update_values.append(data['latitude'])
            if 'longitude' in data:
                update_fields.append('longitude = ?')
                update_values.append(data['longitude'])
            if 'speed' in data:
                update_fields.append('speed = ?')
                update_values.append(data['speed'])
            if 'course' in data:
                update_fields.append('course = ?')
                update_values.append(data['course'])
            if 'heading' in data:
                update_fields.append('heading = ?')
                update_values.append(data['heading'])
            if 'vessel_type' in data:
                update_fields.append('vessel_type = ?')
                update_values.append(data['vessel_type'])
            if 'callsign' in data:
                update_fields.append('callsign = ?')
                update_values.append(data['callsign'])
            if 'destination' in data:
                update_fields.append('destination = ?')
                update_values.append(data['destination'])
            if 'nav_status' in data:
                update_fields.append('nav_status = ?')
                update_values.append(data['nav_status'])
            
            update_fields.append('last_updated = ?')
            update_values.append(now)
            update_values.append(mmsi)
            
            if update_fields:
                sql = f"UPDATE vessels SET {', '.join(update_fields)} WHERE mmsi = ?"
                c.execute(sql, update_values)
        else:
            # Insert new vessel
            c.execute('''
                INSERT INTO vessels (
                    mmsi, name, latitude, longitude, speed, course, heading,
                    timestamp, vessel_type, callsign, nav_status, last_updated
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                mmsi,
                data.get('name', ''),
                data.get('latitude'),
                data.get('longitude'),
                data.get('speed'),
                data.get('course'),
                data.get('heading'),
                now,
                data.get('vessel_type', ''),
                data.get('callsign', ''),
                data.get('nav_status', ''),
                now
            ))
        
        conn.commit()
        conn.close()
        
        # Update last message time diagnostic
        update_diagnostic('last_message_time', now)
        
    except Exception as e:
        log_error(f"Failed to update vessel {mmsi}: {e}")

def main():
    """Main loop - starts AIS-catcher and processes output"""
    print("[AIS Capture] Starting...", file=sys.stderr)
    
    try:
        init_db()
    except Exception as e:
        log_error(f"FATAL: Database initialization failed: {e}")
        sys.exit(1)
    
    # Check if AIS-catcher exists
    ais_catcher_path = '/home/pi/AIS-catcher/build/AIS-catcher'
    if not os.path.exists(ais_catcher_path):
        error_msg = f"AIS-catcher not found at {ais_catcher_path}"
        log_error(error_msg)
        update_diagnostic('ais_catcher_status', 'ERROR: Binary not found')
        sys.exit(1)
    
    update_diagnostic('ais_catcher_status', 'Running')
    
    # Start AIS-catcher with JSON output
    cmd = [
        ais_catcher_path,
        '-d:0',
        '-s', '1024000',
        '-p', '-21',
        '-gr', 'TUNER', '17.9',
        'RTLAGC', 'off',
        '-c', 'AB',
        '-o', '5',  # JSON output
    ]
    
    print(f"[AIS Capture] Starting AIS-catcher", file=sys.stderr)
    
    try:
        process = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            universal_newlines=True,
            bufsize=1
        )
    except Exception as e:
        error_msg = f"Failed to start AIS-catcher: {e}"
        log_error(error_msg)
        update_diagnostic('ais_catcher_status', f'ERROR: {e}')
        sys.exit(1)
    
    message_count = 0
    last_log_time = datetime.utcnow()
    
    try:
        for line in process.stdout:
            line = line.strip()
            if not line or line.startswith('#'):
                continue
            
            try:
                data = json.loads(line)
                
                vessel_data = {'mmsi': data.get('mmsi')}
                
                # Position data
                if 'lat' in data:
                    vessel_data['latitude'] = data['lat']
                if 'lon' in data:
                    vessel_data['longitude'] = data['lon']
                if 'speed' in data:
                    vessel_data['speed'] = data['speed']
                if 'course' in data:
                    vessel_data['course'] = data['course']
                if 'heading' in data:
                    vessel_data['heading'] = data['heading']
                
                # Static data
                if 'shipname' in data:
                    vessel_data['name'] = data['shipname'].strip()
                if 'shiptype' in data:
                    vessel_data['vessel_type'] = data['shiptype']
                if 'callsign' in data:
                    vessel_data['callsign'] = data['callsign'].strip()
                if 'destination' in data:
                    vessel_data['destination'] = data['destination'].strip()
                if 'status' in data:
                    vessel_data['nav_status'] = data['status']
                
                if vessel_data.get('mmsi'):
                    update_vessel(vessel_data)
                    message_count += 1
                    
                    # Log every 100 messages
                    if message_count % 100 == 0:
                        print(f"[DB] Processed {message_count} messages", file=sys.stderr)
                        update_diagnostic('total_messages', message_count)
                
            except json.JSONDecodeError:
                continue
            except Exception as e:
                log_error(f"Error processing message: {e}")
                continue
    
    except KeyboardInterrupt:
        print("\n[AIS Capture] Stopped by user", file=sys.stderr)
        update_diagnostic('ais_catcher_status', 'Stopped')
        process.terminate()
    except Exception as e:
        log_error(f"Fatal error in main loop: {e}")
        update_diagnostic('ais_catcher_status', f'ERROR: {e}')
        process.terminate()

if __name__ == '__main__':
    main()
