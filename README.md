# AIS Tracker

Standalone AIS vessel tracker for Raspberry Pi Zero 2 W. Creates its own WiFi hotspot and displays ships on a web-based map - no internet required!

![AIS Tracker](https://img.shields.io/badge/Platform-Raspberry%20Pi-red)
![License](https://img.shields.io/badge/License-MIT-blue)
![Status](https://img.shields.io/badge/Status-Tested-green)

## Features

- 🌐 **WiFi Hotspot** - Creates "AIS-TRACKER" network
- 🗺️ **Real-time Map** - Shows vessels with heading and speed
- 📊 **Data Table** - Complete vessel information
- 📍 **Position Input** - Add yourself to the map
- 💾 **48-hour History** - Automatic data retention
- 🔄 **Auto-restart** - Survives power loss
- 📡 **Completely Offline** - No internet needed
- 🔍 **System Diagnostics** - Built-in status panel

## Hardware Required

- Raspberry Pi Zero 2 W
- RTL-SDR dongle (RTL2832U chip)
- AIS antenna (162 MHz marine band)
- USB extension cable (0.5-1m)
- 32GB microSD card
- 5V 2.5A power supply

## Quick Start

### One-Command Installation

Flash Raspberry Pi OS Lite 64-bit, boot your Pi, then run:

```bash
curl -sSL https://raw.githubusercontent.com/jeanbaptistechaussade-lab/ais-tracker/main/install.sh | sudo bash
```

Wait 20-30 minutes for installation to complete.

### Manual Installation

```bash
git clone https://github.com/jeanbaptistechaussade-lab/ais-tracker.git
cd ais-tracker
chmod +x install.sh
sudo ./install.sh
```

### After Installation

1. Run these commands to activate the hotspot:
```bash
sudo systemctl stop wpa_supplicant
sudo systemctl mask wpa_supplicant
sudo killall wpa_supplicant
sudo systemctl restart dhcpcd
sudo systemctl restart hostapd
sudo systemctl restart dnsmasq
```

2. Wait 30 seconds

3. Connect to WiFi: **AIS-TRACKER** (password: `ais12345`)

4. Open browser: **http://192.168.4.1**

## What You'll See

**On the web interface:**
- Black grid map with vessel positions
- Orange dots = vessels with heading arrows
- Speed and MMSI shown under each vessel
- Green dot = your position (if entered)
- Data table with all vessel details
- System diagnostics panel at bottom

**System Status Panel:**
- 🟢 RTL-SDR: Connected
- 🟢 AIS Capture: Running
- 🟢 Last Message: 5s ago
- 🟢 Database: 12 vessels, 1.2 MB

## Installation Features

✅ **Checkpoint System** - Resume from failures  
✅ **Retry Logic** - Auto-retry failed downloads  
✅ **Error Logging** - Track issues in /home/pi/ais-server/errors.log  
✅ **Progress Display** - See what's happening  

## Troubleshooting

### No Vessels Appearing

```bash
sudo journalctl -u ais-capture -f
```

Should see: `[DB] Updated vessel 123456789`

**Fix:**
- Check antenna connection
- Move antenna near window
- Verify RTL-SDR is connected: `lsusb | grep RTL`
- Check diagnostics panel on web interface

### Can't Connect to WiFi

```bash
sudo systemctl status hostapd
sudo systemctl status dnsmasq
```

**Fix:**
```bash
sudo systemctl restart hostapd
sudo systemctl restart dnsmasq
```

### Web Page Won't Load

```bash
sudo systemctl status ais-webserver
```

**Fix:**
```bash
sudo systemctl restart ais-webserver
```

## Customization

### Change WiFi Password

```bash
sudo nano /etc/hostapd/hostapd.conf
# Change: wpa_passphrase=ais12345
sudo systemctl restart hostapd
```

### Change Data Retention

```bash
nano /home/pi/ais-server/server.py
# Line 55: Change timedelta(hours=48)
sudo systemctl restart ais-webserver
```

### Adjust Gain

```bash
nano /home/pi/ais-server/capture.py
# Line 167: Change '17.9' to 7.1, 12.5, or 19.7
sudo systemctl restart ais-capture
```

## File Structure

```
/home/pi/
├── AIS-catcher/build/AIS-catcher    # AIS decoder
└── ais-server/
    ├── capture.py                    # AIS → Database
    ├── server.py                     # Web server
    ├── ais_db.sqlite                 # Vessel database
    ├── errors.log                    # Error log
    └── templates/index.html          # Web interface
```

## Performance

**On Pi Zero 2 W:**
- Boot time: 60-90 seconds
- AIS messages: 10-500/minute (location dependent)
- Range: 5-30km (depends on antenna)
- Power: ~0.5-1W
- WiFi range: 10-30 meters

## Building Multiple Units

After first successful build, clone the SD card:

**Mac/Linux:**
```bash
sudo dd if=/dev/diskX of=ais-tracker.img bs=4M
# Then write to new cards:
sudo dd if=ais-tracker.img of=/dev/diskX bs=4M
```

Change SSID for each unit:
```bash
sudo nano /etc/hostapd/hostapd.conf
# Change: ssid=AIS-TRACKER-1
```

## Credits

Built with:
- [AIS-catcher](https://github.com/jvde-github/AIS-catcher) by jvde-github
- Raspberry Pi OS
- Flask web framework
- SQLite database

## License

MIT License - Free to use and modify

## Support

- Check diagnostics panel on web interface
- Review error log: `/home/pi/ais-server/errors.log`
- Check service logs: `sudo journalctl -u ais-capture -n 100`
- Open an issue on GitHub

## Author

Created by [@jeanbaptistechaussade-lab](https://github.com/jeanbaptistechaussade-lab)

---

**Happy ship tracking!** 🚢📡
