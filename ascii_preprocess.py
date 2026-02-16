"""
ASCII Art Blob Generator for Rive
Converts an image to a binary .blob file for use as a Rive Blob asset.

Binary format:
  - 2 bytes: cols (little-endian u16)
  - 2 bytes: rows (little-endian u16)
  - cols*rows bytes: brightness values (0-255), one byte per cell

Usage:
  python ascii_preprocess.py <image_path> [cols] [rows] [output_path]

Examples:
  python ascii_preprocess.py photo.png
  python ascii_preprocess.py photo.png 100 60
  python ascii_preprocess.py photo.png 100 60 ascii_data.blob
"""

import struct
import sys
import os
import shutil
from datetime import datetime
from PIL import Image

BACKUP_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "blob_backup")

def backup_blob(output_path):
    """Backup existing .blob file to blob_backup/ with incrementing name.
    Silently skips if filesystem is read-only (cloud deploy)."""
    if not os.path.exists(output_path):
        return
    try:
        os.makedirs(BACKUP_DIR, exist_ok=True)
        base = os.path.splitext(os.path.basename(output_path))[0]
        # Find next available backup number
        existing = [f for f in os.listdir(BACKUP_DIR) if f.startswith(base + "_")]
        next_num = len(existing) + 1
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_name = f"{base}_{next_num:03d}_{timestamp}.blob"
        backup_path = os.path.join(BACKUP_DIR, backup_name)
        shutil.copy2(output_path, backup_path)
        print(f"Backed up: {output_path} -> blob_backup/{backup_name}")
    except OSError:
        pass  # Skip backup on read-only filesystems (cloud deploy)

def convert_image_to_ascii_bin(image_path, cols=100, rows=60, output_path="ascii_data.blob"):
    # Open and convert to grayscale
    img = Image.open(image_path).convert("L")
    print(f"Original image size: {img.width}x{img.height}")

    # Resize to ASCII grid resolution with high-quality downsampling
    img = img.resize((cols, rows), Image.LANCZOS)
    print(f"Resized to ASCII grid: {cols}x{rows}")

    # Backup existing blob before overwriting
    backup_blob(output_path)

    # Write binary file
    with open(output_path, "wb") as f:
        # Header: 2 bytes for cols, 2 bytes for rows (little-endian u16)
        f.write(struct.pack("<HH", cols, rows))
        # Body: one byte per cell (brightness 0-255)
        f.write(img.tobytes())

    total_size = 4 + cols * rows
    print(f"Wrote {cols}x{rows} = {cols * rows} brightness values to {output_path}")
    print(f"File size: {total_size} bytes (4 byte header + {cols * rows} byte body)")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python ascii_preprocess.py <image_path> [cols] [rows] [output_path]")
        print("  cols: number of columns (default: 100)")
        print("  rows: number of rows (default: 60)")
        print("  output_path: output file path (default: ascii_data.blob)")
        sys.exit(1)

    image_path = sys.argv[1]
    cols = int(sys.argv[2]) if len(sys.argv) > 2 else 100
    rows = int(sys.argv[3]) if len(sys.argv) > 3 else 60
    output_path = sys.argv[4] if len(sys.argv) > 4 else "ascii_data.blob"

    convert_image_to_ascii_bin(image_path, cols, rows, output_path)
