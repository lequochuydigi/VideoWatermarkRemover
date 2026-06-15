"""
Runtime configuration for Watermark Remover.

Priority (highest first):
  1. Environment variables
  2. Defaults below

Set environment variables before starting the server, e.g.:
  Windows CMD:   set VIDEOS_DIR=D:\MyVideos && python app.py
  PowerShell:    $env:VIDEOS_DIR="D:\MyVideos"; python app.py
  Linux/Mac:     VIDEOS_DIR=/home/user/Videos python app.py

Or just change the folder inside the web UI after opening the app.
"""

import os
import pathlib

# Directory scanned for video/image input files and where output files are saved.
# Defaults to the current user's Downloads folder.
VIDEOS_DIR: str = os.environ.get(
    "VIDEOS_DIR",
    str(pathlib.Path.home() / "Downloads"),
)

HOST: str = os.environ.get("HOST", "127.0.0.1")
PORT: int = int(os.environ.get("PORT", "5000"))
DEBUG: bool = os.environ.get("DEBUG", "true").lower() not in ("0", "false", "no")
