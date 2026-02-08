#!/usr/bin/env python3
"""
AIS Web Server - Serves the map and vessel data
With diagnostics endpoint
"""

from flask import Flask, render_template, jsonify, request
import sqlite3
from datetime import datetime, timedelta
import math
import os

app = Flask(__name__)
DB_PATH = '/home/pi/ais-server/ais_db.sqlite'
ERROR_LOG = '/home/pi/ais-server/errors.log'

def get_db():
    """Connect to database"""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def calculate_distance(lat1, lon1, lat2, lon2):
    """Calculate distance in nautical miles"""
    R = 3440.065  # Earth radius in nautical miles
    
    lat1_rad = math.radians(lat1)
    lat2_rad = math.radians(lat2)
    delta_lat = math.radians(lat2 - lat1)
    delta_lon = math.radians(lon2 - lon1)
    
    a = math.sin(delta_lat/2)**2 + math.cos(lat1_rad) * math.cos(lat2_rad) * math.sin(delta_lon/2)**2
    c = 2 * math.asin(math.sqrt(a))
    
    return R * c

def calculate_bearing(lat1, lon1, lat2, lon2):
    """Calculate bearing in degrees"""
    lat1_rad = math.radians(lat1)
    lat2_rad = math.radians(lat2)
    delta_lon = math.radians(lon2 - lon1)
    
    y = math.sin(delta_lon) * math.cos(lat2_rad)
    x = math.cos(lat1_rad) * math.sin(lat2_rad) - math.sin(lat1_rad) * math.cos(lat2_rad) * math.cos(delta_lon)
    
    bearing = math.degrees(math.atan2(y, x))
    return (bearing + 360) % 360

@app.route('/')
def index():
    """Serve main page"""
    return render_template('index.html')

@app.route('/api/vessels')
def get_vessels():
    """Get all vessels from last 48 hours"""
    my_lat = request.args.get('my_lat', type=float)
    my_lon = request.args.get('my_lon', type=float)
    
    conn = get_db()
    c = conn.cursor()
    
    # Get vessels from last 48 hours
    cutoff = (datetime.utcnow() - timedelta(hours=48)).isoformat() + 'Z'
    c.execute('''
        SELECT * FROM vessels 
        WHERE latitude IS NOT NULL 
        AND longitude IS NOT NULL
        AND last_updated > ?
        ORDER BY last_updated DESC
    ''', (cutoff,))
    
    vessels = []
    for row in c.fetchall():
        vessel = {
            'mmsi': row['mmsi'],
            'name': row['name'] or 'Unknown',
            'latitude': row['latitude'],
            'longitude': row['longitude'],
            'speed': row['speed'],
            'course': row['course'],
            'heading': row['heading'],
            'timestamp': row['last_updated'],
            'vessel_type': row['vessel_type'] or '',
            'callsign': row['callsign'] or '',
            'imo': row['imo'] or '',
            'dimension_bow': row['dimension_bow'],
            'dimension_stern': row['dimension_stern'],
            'dimension_port': row['dimension_port'],
            'dimension_starboard': row['dimension_starboard'],
            'draught': row['draught'],
            'destination': row['destination'] or '',
            'nav_status': row['nav_status'] or '',
        }
        
        # Calculate distance if user position provided
        if my_lat is not None and my_lon is not None:
            vessel['distance'] = round(calculate_distance(my_lat, my_lon, 
                                                         row['latitude'], row['longitude']), 2)
            vessel['bearing'] = round(calculate_bearing(my_lat, my_lon,
                                                       row['latitude'], row['longitude']), 1)
        
        vessels.append(vessel)
    
    conn.close()
    return jsonify(vessels)

@app.route('/api/diagnostics')
def get_diagnostics():
    """Get system diagnostics"""
    try:
        conn = get_db()
        c = conn.cursor()
        
        # Get vessel count
        c.execute('SELECT COUNT(*) as count FROM vessels WHERE latitude IS NOT NULL')
        vessel_count = c.fetchone()['count']
        
        # Get database size
        db_size = 0
        if os.path.exists(DB_PATH):
            db_size = os.path.getsize(DB_PATH) / (1024 * 1024)  # MB
        
        # Get diagnostics from table
        c.execute('SELECT * FROM diagnostics')
        diag_rows = c.fetchall()
        diagnostics = {row['key']: row['value'] for row in diag_rows}
        
        # Check for RTL-SDR
        rtl_sdr_connected = os.system('lsusb | grep -q RTL2832U') == 0
        
        # Get last message time
        last_msg_time = diagnostics.get('last_message_time', 'Never')
        if last_msg_time != 'Never':
            try:
                last_msg_dt = datetime.fromisoformat(last_msg_time.replace('Z', ''))
                seconds_ago = (datetime.utcnow() - last_msg_dt).total_seconds()
            except:
                seconds_ago = 999999
        else:
            seconds_ago = 999999
        
        # Get errors from log (last 10 lines)
        errors = []
        if os.path.exists(ERROR_LOG):
            try:
                with open(ERROR_LOG, 'r') as f:
                    lines = f.readlines()
                    errors = [line.strip() for line in lines[-10:]]
            except:
                pass
        
        # Build status
        status = {
            'vessel_count': vessel_count,
            'db_size_mb': round(db_size, 2),
            'last_message': last_msg_time,
            'seconds_since_message': int(seconds_ago),
            'rtl_sdr_connected': rtl_sdr_connected,
            'ais_catcher_status': diagnostics.get('ais_catcher_status', 'Unknown'),
            'total_messages': diagnostics.get('total_messages', 0),
            'recent_errors': errors[-3:] if errors else []
        }
        
        conn.close()
        return jsonify(status)
        
    except Exception as e:
        return jsonify({
            'error': str(e),
            'vessel_count': 0,
            'db_size_mb': 0,
            'rtl_sdr_connected': False
        })

@app.route('/api/cleanup')
def cleanup_old_data():
    """Remove vessels older than 48 hours"""
    conn = get_db()
    c = conn.cursor()
    
    cutoff = (datetime.utcnow() - timedelta(hours=48)).isoformat() + 'Z'
    c.execute('DELETE FROM vessels WHERE last_updated < ?', (cutoff,))
    deleted = c.rowcount
    
    conn.commit()
    conn.close()
    
    return jsonify({'deleted': deleted})

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=80, debug=False)
