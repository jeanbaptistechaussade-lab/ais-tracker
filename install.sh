#!/bin/bash
#############################################
# AIS Tracker - Automated Installation
# For Raspberry Pi Zero 2 W
# https://github.com/jeanbaptistechaussade-lab/ais-tracker
#############################################

set -e  # Exit on error
INSTALL_DIR="/tmp/ais-install"
CHECKPOINT_DIR="$INSTALL_DIR/checkpoints"
LOG_FILE="$INSTALL_DIR/install.log"
PROJECT_DIR="/home/pi/ais-server"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Create directories
mkdir -p "$CHECKPOINT_DIR"
mkdir -p "$PROJECT_DIR/templates"

# Logging function
log() {
    echo -e "${GREEN}[$(date +'%H:%M:%S')]${NC} $1" | tee -a "$LOG_FILE"
}

error() {
    echo -e "${RED}[ERROR]${NC} $1" | tee -a "$LOG_FILE"
}

warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1" | tee -a "$LOG_FILE"
}

# Check if step is complete
is_complete() {
    [ -f "$CHECKPOINT_DIR/$1" ]
}

# Mark step as complete
mark_complete() {
    touch "$CHECKPOINT_DIR/$1"
    log "✓ Checkpoint: $1"
}

# Retry function
retry() {
    local max_attempts=3
    local delay=5
    local attempt=1
    local command="$@"
    
    while [ $attempt -le $max_attempts ]; do
        if eval "$command"; then
            return 0
        else
            if [ $attempt -lt $max_attempts ]; then
                warning "Attempt $attempt/$max_attempts failed. Retrying in ${delay}s..."
                sleep $delay
                ((attempt++))
            else
                error "Failed after $max_attempts attempts"
                return 1
            fi
        fi
    done
}

echo ""
echo "========================================="
echo "  AIS Tracker - Automated Installation  "
echo "========================================="
echo ""
log "Starting installation..."
log "Installation log: $LOG_FILE"
echo ""

# Check if running as root/sudo
if [ "$EUID" -ne 0 ]; then 
    error "Please run with sudo: sudo ./install.sh"
    exit 1
fi

# Check architecture
ARCH=$(uname -m)
if [ "$ARCH" != "aarch64" ]; then
    error "Wrong architecture: $ARCH (expected aarch64)"
    error "You must use Raspberry Pi OS Lite 64-bit"
    exit 1
fi

# Check for RTL-SDR
if ! lsusb | grep -q "RTL2832U"; then
    warning "RTL-SDR not detected. Please connect it before continuing."
    read -p "Continue anyway? (y/n) " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        exit 1
    fi
fi

#############################################
# STEP 1: Update System
#############################################
if ! is_complete "step1_update"; then
    log "Step 1/8: Updating system..."
    retry "apt update" || exit 1
    retry "apt upgrade -y" || exit 1
    mark_complete "step1_update"
else
    log "Step 1/8: Already complete (skipping)"
fi

#############################################
# STEP 2: Install Dependencies
#############################################
if ! is_complete "step2_dependencies"; then
    log "Step 2/8: Installing dependencies..."
    
    # RTL-SDR and build tools
    retry "apt install -y rtl-sdr librtlsdr-dev sox git cmake build-essential pkg-config" || exit 1
    
    # Python and web server
    retry "apt install -y python3-pip python3-flask sqlite3" || exit 1
    
    # WiFi hotspot
    retry "apt install -y hostapd dnsmasq" || exit 1
    
    mark_complete "step2_dependencies"
else
    log "Step 2/8: Already complete (skipping)"
fi

#############################################
# STEP 3: Blacklist DVB Drivers
#############################################
if ! is_complete "step3_blacklist"; then
    log "Step 3/8: Blacklisting conflicting drivers..."
    
    cat > /etc/modprobe.d/blacklist-rtl.conf <<'EOF'
blacklist dvb_usb_rtl28xxu
blacklist rtl2832
blacklist rtl2830
EOF
    
    mark_complete "step3_blacklist"
else
    log "Step 3/8: Already complete (skipping)"
fi

#############################################
# STEP 4: Build AIS-catcher
#############################################
if ! is_complete "step4_ais_catcher"; then
    log "Step 4/8: Building AIS-catcher (this takes 15-30 minutes)..."
    
    cd /home/pi
    
    if [ ! -d "AIS-catcher" ]; then
        retry "git clone https://github.com/jvde-github/AIS-catcher.git" || exit 1
    fi
    
    cd AIS-catcher
    mkdir -p build
    cd build
    
    log "Running cmake..."
    cmake .. || exit 1
    
    log "Compiling (this is slow on Pi Zero 2 W)..."
    make -j2 || exit 1
    
    # Verify binary exists
    if [ ! -f "./AIS-catcher" ]; then
        error "AIS-catcher binary not found after build"
        exit 1
    fi
    
    log "AIS-catcher built successfully"
    mark_complete "step4_ais_catcher"
else
    log "Step 4/8: Already complete (skipping)"
fi

#############################################
# STEP 5: Download Application Files
#############################################
if ! is_complete "step5_app_files"; then
    log "Step 5/8: Installing application files..."
    
    # Download files from GitHub
    cd "$INSTALL_DIR"
    
    BASE_URL="https://raw.githubusercontent.com/jeanbaptistechaussade-lab/ais-tracker/main/files"
    
    log "Downloading capture.py..."
    retry "curl -sSL $BASE_URL/capture.py -o capture.py" || exit 1
    
    log "Downloading server.py..."
    retry "curl -sSL $BASE_URL/server.py -o server.py" || exit 1
    
    log "Downloading index.html..."
    retry "curl -sSL $BASE_URL/index.html -o index.html" || exit 1
    
    # Copy to project directory
    cp capture.py "$PROJECT_DIR/"
    cp server.py "$PROJECT_DIR/"
    cp index.html "$PROJECT_DIR/templates/"
    
    # Make scripts executable
    chmod +x "$PROJECT_DIR/capture.py"
    chmod +x "$PROJECT_DIR/server.py"
    
    # Set ownership
    chown -R pi:pi "$PROJECT_DIR"
    
    mark_complete "step5_app_files"
else
    log "Step 5/8: Already complete (skipping)"
fi

#############################################
# STEP 6: Configure WiFi Hotspot
#############################################
if ! is_complete "step6_wifi"; then
    log "Step 6/8: Configuring WiFi hotspot..."
    
    # Stop services
    systemctl stop dnsmasq 2>/dev/null || true
    systemctl stop hostapd 2>/dev/null || true
    
    # Configure dnsmasq (DHCP)
    mv /etc/dnsmasq.conf /etc/dnsmasq.conf.backup 2>/dev/null || true
    cat > /etc/dnsmasq.conf <<'EOF'
interface=wlan0
dhcp-range=192.168.4.2,192.168.4.20,255.255.255.0,24h
EOF
    
    # Configure hostapd (WiFi AP) - Channel 6 for iPhone compatibility
    cat > /etc/hostapd/hostapd.conf <<'EOF'
interface=wlan0
driver=nl80211
ssid=AIS-TRACKER
hw_mode=g
channel=6
ieee80211n=1
wmm_enabled=0
macaddr_acl=0
auth_algs=1
ignore_broadcast_ssid=0
wpa=2
wpa_passphrase=ais12345
wpa_key_mgmt=WPA-PSK
wpa_pairwise=TKIP
rsn_pairwise=CCMP
EOF
    
    cat > /etc/default/hostapd <<'EOF'
DAEMON_CONF="/etc/hostapd/hostapd.conf"
EOF
    
    # Configure network (this is the key fix!)
    cat > /etc/dhcpcd.conf <<'EOF'
# AIS Tracker - Hotspot Only
interface wlan0
    static ip_address=192.168.4.1/24
    nohook wpa_supplicant
EOF
    
    # Enable services
    systemctl unmask hostapd
    systemctl enable hostapd
    systemctl enable dnsmasq
    
    mark_complete "step6_wifi"
else
    log "Step 6/8: Already complete (skipping)"
fi

#############################################
# STEP 7: Create Auto-Start Services
#############################################
if ! is_complete "step7_services"; then
    log "Step 7/8: Creating systemd services..."
    
    # AIS Capture Service
    cat > /etc/systemd/system/ais-capture.service <<'EOF'
[Unit]
Description=AIS Capture Service
After=network.target

[Service]
Type=simple
User=pi
WorkingDirectory=/home/pi/ais-server
ExecStart=/usr/bin/python3 /home/pi/ais-server/capture.py
Restart=always
RestartSec=10
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=multi-user.target
EOF
    
    # Web Server Service
    cat > /etc/systemd/system/ais-webserver.service <<'EOF'
[Unit]
Description=AIS Web Server
After=network.target ais-capture.service

[Service]
Type=simple
User=root
WorkingDirectory=/home/pi/ais-server
ExecStart=/usr/bin/python3 /home/pi/ais-server/server.py
Restart=always
RestartSec=10
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=multi-user.target
EOF
    
    # Enable services
    systemctl daemon-reload
    systemctl enable ais-capture.service
    systemctl enable ais-webserver.service
    
    # Add cleanup cron job
    (crontab -u pi -l 2>/dev/null || true; echo "0 * * * * curl -s http://localhost/api/cleanup > /dev/null 2>&1") | crontab -u pi -
    
    mark_complete "step7_services"
else
    log "Step 7/8: Already complete (skipping)"
fi

#############################################
# STEP 8: Initialize Database
#############################################
if ! is_complete "step8_database"; then
    log "Step 8/8: Initializing database..."
    
    sudo -u pi python3 - <<'PYTHON'
import sqlite3
DB_PATH = '/home/pi/ais-server/ais_db.sqlite'
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
conn.commit()
conn.close()
print('Database initialized')
PYTHON
    
    mark_complete "step8_database"
else
    log "Step 8/8: Already complete (skipping)"
fi

#############################################
# FINAL STEP: Disable Home WiFi
#############################################
log ""
log "Installation complete!"
log ""
warning "IMPORTANT: The Pi will now switch to hotspot mode."
warning "Your SSH connection will DROP when you run the next commands."
echo ""
echo "To activate the hotspot, run:"
echo ""
echo -e "${BLUE}sudo systemctl stop wpa_supplicant"
echo "sudo systemctl mask wpa_supplicant"
echo "sudo killall wpa_supplicant"
echo "sudo systemctl restart dhcpcd"
echo "sudo systemctl restart hostapd"
echo -e "sudo systemctl restart dnsmasq${NC}"
echo ""
echo "Or simply reboot:"
echo ""
echo -e "${BLUE}sudo reboot${NC}"
echo ""
echo "After reboot:"
echo "  WiFi Network: AIS-TRACKER"
echo "  Password: ais12345"
echo "  Web Interface: http://192.168.4.1"
echo ""
log "Installation log saved to: $LOG_FILE"
echo ""

# Save completion marker
touch "$CHECKPOINT_DIR/install_complete"
