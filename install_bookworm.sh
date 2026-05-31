#!/bin/bash
# PlayerScope Installation Script for Raspberry Pi Debian Bookworm (Python 3.11)
echo "Installing PlayerScope system dependencies..."
sudo apt install -y \
    python3-pyaudio \
    python3-pydub \
    python3-pyqtgraph
