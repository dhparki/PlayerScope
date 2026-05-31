#!/bin/bash
# PlayerScope Installation Script for Raspberry Pi Debian Trixie (Python 3.13)
echo "Installing PlayerScope system dependencies..."
sudo apt install -y \
    python3-pyaudio \
    python3-soundfile \
    python3-pyqtgraph
