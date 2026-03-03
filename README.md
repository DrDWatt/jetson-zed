# Jetson ZED 2i Stereo Capture System

Web-controlled stereo video capture system for NVIDIA Jetson with ZED 2i camera.

## Architecture

```
┌──────────────────────────────────────────────┐
│                  Jetson Nano                  │
│  +----------------------------------------+  │
│  │ Docker Host & NVIDIA Container Runtime │  │
│  +-----------------------+----------------+  │
│                          │                   │
│      Host Service        │    Docker         │
│  (Video Capture)         │    (Web Server)   │
│                          │                   │
│   ZED SDK + GStreamer    │  FastAPI + UI     │
│   Stereo SVO Recording   │  Control Panel    │
│                          │                   │
└──────────────────┬───────┴───────────────────┘
                   │
            Shared Volume
            /home/nvidia/jetson-zed/videos
```

## Features

- **Start/Stop Recording**: Control video capture via web UI
- **Real-time Status**: WebSocket-based live status updates
- **Video Management**: List, download, and delete recordings
- **Stereo Capture**: Full resolution side-by-side stereo from ZED 2i
- **Dynamic Camera Settings**: Resolution, depth mode, exposure, gain, white balance, compression
- **Scene Analysis**: Pre-capture brightness analysis with recommended settings
- **SVO Preview**: Auto-converts SVO recordings to browser-playable MP4 previews

## Requirements

- NVIDIA Jetson Nano (JetPack 4.6+)
- ZED 2i Camera connected via USB 3.0
- ZED SDK 3.8 (SDK 4.0 not compatible with L4T 32.7.1)
- Docker with NVIDIA Container Runtime
- Network access to Jetson

## Quick Start

### 1. Clone to Jetson

```bash
git clone https://github.com/DrDWatt/jetson-zed.git ~/jetson-zed
```

### 2. Build and Run

```bash
cd ~/jetson-zed

# Build web container
docker-compose build

# Start web container
docker-compose up -d

# Install and start capture service
sudo cp scripts/zed-capture-host.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable zed-capture-host
sudo systemctl start zed-capture-host
```

### 3. Access Web UI

Open browser to: `http://<jetson-ip>:8080`

## API Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/` | GET | Web UI |
| `/api/start` | POST | Start recording |
| `/api/stop` | POST | Stop recording |
| `/api/status` | GET | Current capture status |
| `/api/settings` | GET/POST | Camera settings |
| `/api/analyze` | POST | Scene brightness analysis |
| `/api/analysis` | GET | Latest analysis results |
| `/api/videos` | GET | List all recordings |
| `/api/video/{name}` | GET | Download video |
| `/api/stream/{name}` | GET | Stream video preview |
| `/api/video/{name}` | DELETE | Delete video |
| `/ws` | WebSocket | Real-time status updates |

## Camera Settings

| Setting | Range | Notes |
|---------|-------|-------|
| Resolution | HD720, HD1080, HD2K | Requires camera restart |
| Depth Mode | NEURAL, ULTRA, QUALITY, PERFORMANCE, NONE | Requires camera restart |
| Compression | H.264, H.265, H.264 Lossless, H.265 Lossless | Applied on next recording |
| Brightness | 0-8 | Live adjustment |
| Exposure | 1-100 (shows shutter speed) | Live adjustment |
| Gain | 0-100 | Live adjustment |
| White Balance | 2800-6500K | Live adjustment |

## Development

### Sync and Deploy

```bash
# Sync changes to Jetson
./sync-jetson.sh ~/jetson-zed

# Or manual rsync
rsync -avz --exclude '.git' ~/jetson-zed/ jetson:/home/nvidia/jetson-zed/

# Rebuild web container
ssh jetson "cd ~/jetson-zed && docker-compose build --no-cache && docker-compose up -d"

# Restart capture service
ssh jetson "sudo systemctl restart zed-capture-host"
```

## Troubleshooting

### Camera not detected

```bash
lsusb | grep -i stereo
ls -la /dev/video*
sudo systemctl restart zed-capture-host
```

### ZED SDK Issues on Jetson Nano

- Must use SDK 3.8 (SDK 4.0 causes SIGILL on Cortex-A57)
- Set `OPENBLAS_CORETYPE=ARMV8` to prevent numpy SIGILL
- Fix SDK permissions: `sudo chmod -R o+rX /usr/local/zed/`
- AI model permissions: `sudo chmod -R a+rwX /usr/local/zed/resources/`

## License

MIT License
