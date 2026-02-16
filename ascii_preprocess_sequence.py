"""
ASCII Art Sequence Blob Generator for Rive
Converts a video, GIF, or folder of PNG frames into a single .blob file
containing all frames for animated ASCII art in Rive.

Binary format (8-byte header):
  Bytes 0-1:  cols       (u16 LE)
  Bytes 2-3:  rows       (u16 LE)
  Bytes 4-5:  frameCount (u16 LE)
  Bytes 6-7:  fps        (u16 LE)
  Bytes 8+:   brightness data, cols*rows bytes per frame, frame after frame

Usage:
  # From a folder of PNGs:
  python ascii_preprocess_sequence.py frames/
  python ascii_preprocess_sequence.py frames/ --cols 100 --rows 60 --fps 24

  # From a video or GIF:
  python ascii_preprocess_sequence.py animation.mp4
  python ascii_preprocess_sequence.py animation.gif --cols 80 --rows 48 --fps 12

  # Custom output path:
  python ascii_preprocess_sequence.py frames/ -o my_animation.blob

Supports: MP4, MOV, AVI, GIF (via OpenCV) or folder of PNG/JPG images.
If OpenCV is not installed, only PNG/JPG folder input is supported.

Dependencies:
  pip install Pillow
  pip install opencv-python   (optional, needed for video/GIF input)
"""

import struct
import sys
import os
import glob
import argparse
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

# Try to import OpenCV for video support
try:
    import cv2
    HAS_CV2 = True
except ImportError:
    HAS_CV2 = False


def extract_frames_from_video(video_path, max_frames=None):
    """Extract frames from a video/GIF file using OpenCV. Returns list of PIL Images."""
    if not HAS_CV2:
        print("ERROR: opencv-python is required for video/GIF input.")
        print("  Install it with: pip install opencv-python")
        sys.exit(1)

    cap = cv2.VideoCapture(video_path)
    if not cap.isOpened():
        print(f"ERROR: Could not open video: {video_path}")
        sys.exit(1)

    source_fps = cap.get(cv2.CAP_PROP_FPS)
    total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    print(f"Video: {total_frames} frames at {source_fps:.1f} fps")

    frames = []
    count = 0
    while True:
        ret, frame = cap.read()
        if not ret:
            break
        # Convert BGR (OpenCV) to RGB, then to PIL Image
        rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        pil_img = Image.fromarray(rgb)
        frames.append(pil_img)
        count += 1
        if max_frames and count >= max_frames:
            break

    cap.release()
    print(f"Extracted {len(frames)} frames from video")
    return frames, source_fps


def gather_frames_from_folder(folder_path):
    """Gather image files from a folder, sorted by name. Returns list of PIL Images."""
    extensions = ("*.png", "*.jpg", "*.jpeg", "*.bmp", "*.tiff")
    files = []
    for ext in extensions:
        files.extend(glob.glob(os.path.join(folder_path, ext)))
        files.extend(glob.glob(os.path.join(folder_path, ext.upper())))

    # Remove duplicates and sort
    files = sorted(set(files))

    if not files:
        print(f"ERROR: No image files found in '{folder_path}'")
        print(f"  Looked for: {', '.join(extensions)}")
        sys.exit(1)

    print(f"Found {len(files)} image files in '{folder_path}'")
    frames = []
    for path in files:
        frames.append(Image.open(path))

    return frames


def convert_sequence_to_blob(frames, cols=100, rows=60, fps=24, output_path="ascii_sequence.blob"):
    """Convert a list of PIL Images to the animated ASCII blob format."""
    num_frames = len(frames)

    if num_frames > 65535:
        print(f"WARNING: {num_frames} frames exceeds u16 max (65535). Truncating.")
        frames = frames[:65535]
        num_frames = 65535

    frame_size = cols * rows
    total_size = 8 + frame_size * num_frames

    print(f"Converting {num_frames} frames to {cols}x{rows} grid...")
    print(f"Output: {output_path}")
    print(f"Expected file size: {total_size:,} bytes ({total_size / 1024:.1f} KB)")

    # Backup existing blob before overwriting
    backup_blob(output_path)

    with open(output_path, "wb") as f:
        # 8-byte header
        f.write(struct.pack("<HHHH", cols, rows, num_frames, fps))

        for i, img in enumerate(frames):
            # Convert to grayscale and resize
            gray = img.convert("L")
            gray = gray.resize((cols, rows), Image.LANCZOS)
            f.write(gray.tobytes())

            if (i + 1) % 10 == 0 or (i + 1) == num_frames:
                print(f"  Processed {i + 1}/{num_frames} frames")

    actual_size = os.path.getsize(output_path)
    print()
    print(f"=== Done ===")
    print(f"  Frames: {num_frames}")
    print(f"  Grid:   {cols}x{rows} ({frame_size} cells per frame)")
    print(f"  FPS:    {fps}")
    print(f"  Size:   {actual_size:,} bytes ({actual_size / 1024:.1f} KB)")
    print(f"  Output: {output_path}")


def main():
    parser = argparse.ArgumentParser(
        description="Convert video, GIF, or image sequence to animated ASCII blob for Rive"
    )
    parser.add_argument(
        "input",
        help="Path to video file (MP4/MOV/AVI/GIF) or folder of PNG/JPG frames"
    )
    parser.add_argument("--cols", type=int, default=100, help="Grid columns (default: 100)")
    parser.add_argument("--rows", type=int, default=60, help="Grid rows (default: 60)")
    parser.add_argument("--fps", type=int, default=None, help="Playback FPS (default: auto from video, or 24 for image sequence)")
    parser.add_argument("--max-frames", type=int, default=None, help="Max frames to extract (default: all)")
    parser.add_argument("-o", "--output", default="ascii_sequence.blob", help="Output .blob path (default: ascii_sequence.blob)")

    args = parser.parse_args()

    input_path = args.input

    # Determine input type
    if os.path.isdir(input_path):
        # Folder of images
        print(f"Input: image sequence folder '{input_path}'")
        frames = gather_frames_from_folder(input_path)
        if args.max_frames:
            frames = frames[:args.max_frames]
        fps = args.fps if args.fps else 24
    elif os.path.isfile(input_path):
        # Video or GIF file
        ext = os.path.splitext(input_path)[1].lower()
        video_exts = (".mp4", ".mov", ".avi", ".mkv", ".webm", ".gif")
        if ext in video_exts:
            print(f"Input: video file '{input_path}'")
            frames, source_fps = extract_frames_from_video(input_path, args.max_frames)
            fps = args.fps if args.fps else max(1, int(round(source_fps)))
        else:
            print(f"ERROR: Unsupported file type '{ext}'")
            print(f"  Supported: {', '.join(video_exts)} or folder of images")
            sys.exit(1)
    else:
        print(f"ERROR: '{input_path}' is not a valid file or folder")
        sys.exit(1)

    if not frames:
        print("ERROR: No frames to process")
        sys.exit(1)

    # Ensure .blob extension
    output = args.output
    if not output.endswith(".blob"):
        base = os.path.splitext(output)[0]
        output = base + ".blob"
        print(f"NOTE: Changed output extension to .blob (Rive requires .blob for import)")

    convert_sequence_to_blob(frames, args.cols, args.rows, fps, output)


if __name__ == "__main__":
    main()
