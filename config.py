"""
Runtime configuration for Watermark Remover.

Priority (highest first):
  1. Environment variables
  2. Defaults below

Set environment variables before starting the server, e.g.:
  Windows CMD:   set VIDEOS_DIR=D:\MyVideos
  PowerShell:    $env:VIDEOS_DIR="D:\MyVideos"
  Linux/Mac:     export VIDEOS_DIR=/home/user/Videos
"""

import os

# Directory scanned for .mp4 input files and where output files are saved.
# Default: the current working directory so the app works out-of-the-box.
VIDEOS_DIR: str = os.environ.get(
    "VIDEOS_DIR",
    os.path.join(os.path.dirname(os.path.abspath(__file__)), "videos"),
)

# Host and port for the Flask dev server.
HOST: str = os.environ.get("HOST", "localhost")
PORT: int = int(os.environ.get("PORT", "5000"))

# Enable Flask debug mode (auto-reload, debugger).
# Set to "0" or "false" in production.
DEBUG: bool = os.environ.get("DEBUG", "true").lower() not in ("0", "false", "no")
