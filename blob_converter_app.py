"""
Rive ASCII Blob Converter — Local Web App
Run this script and a browser opens with drag-and-drop conversion UI.

Usage:
  python blob_converter_app.py

Dependencies:
  pip install flask Pillow opencv-python
"""

import os
import sys
import shutil
import tempfile
import webbrowser
from threading import Timer
from flask import Flask, render_template, request, send_file, jsonify
from PIL import Image

# Add script directory to path so we can import the existing converters
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, SCRIPT_DIR)

from ascii_preprocess import convert_image_to_ascii_bin
from ascii_preprocess_sequence import (
    extract_frames_from_video as _extract_frames_from_video,
    convert_sequence_to_blob,
    HAS_CV2,
)


def extract_frames_from_video(video_path, max_frames=None):
    """Wrapper that catches sys.exit from the original function."""
    try:
        return _extract_frames_from_video(video_path, max_frames=max_frames)
    except SystemExit as e:
        raise RuntimeError(f"Video extraction failed (exit code {e.code})")

app = Flask(__name__)
app.config["MAX_CONTENT_LENGTH"] = 200 * 1024 * 1024  # 200 MB

IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg", ".bmp", ".tiff", ".tif", ".webp"}
VIDEO_EXTENSIONS = {".mp4", ".mov", ".avi", ".mkv", ".webm", ".gif"}

ASCII_RAMP = ' .:-=+*#%@'

# Track temp dirs to clean up after response is sent
_pending_cleanup = []


@app.after_request
def cleanup_temp_dirs(response):
    while _pending_cleanup:
        path = _pending_cleanup.pop()
        shutil.rmtree(path, ignore_errors=True)
    return response


@app.route("/")
def index():
    return render_template("index.html", has_cv2=HAS_CV2)


@app.route("/convert/image", methods=["POST"])
def convert_image():
    if "file" not in request.files:
        return jsonify(error="No file uploaded"), 400

    file = request.files["file"]
    if not file.filename:
        return jsonify(error="No file selected"), 400

    ext = os.path.splitext(file.filename)[1].lower()
    if ext not in IMAGE_EXTENSIONS:
        return jsonify(error=f"Unsupported image format: {ext}"), 400

    cols = request.form.get("cols", 100, type=int)
    rows = request.form.get("rows", 60, type=int)
    cols = max(1, min(cols, 500))
    rows = max(1, min(rows, 500))

    tmp_dir = tempfile.mkdtemp()
    _pending_cleanup.append(tmp_dir)

    try:
        input_path = os.path.join(tmp_dir, "input" + ext)
        output_path = os.path.join(tmp_dir, "ascii_data.blob")
        file.save(input_path)

        convert_image_to_ascii_bin(input_path, cols, rows, output_path)

        return send_file(
            output_path,
            as_attachment=True,
            download_name="ascii_data.blob",
            mimetype="application/octet-stream",
        )
    except Exception as e:
        return jsonify(error=str(e)), 500


@app.route("/convert/video", methods=["POST"])
def convert_video():
    if not HAS_CV2:
        return jsonify(error="OpenCV not installed. Run: pip install opencv-python"), 400

    if "file" not in request.files:
        return jsonify(error="No file uploaded"), 400

    file = request.files["file"]
    if not file.filename:
        return jsonify(error="No file selected"), 400

    ext = os.path.splitext(file.filename)[1].lower()
    if ext not in VIDEO_EXTENSIONS:
        return jsonify(error=f"Unsupported video format: {ext}"), 400

    cols = request.form.get("cols", 100, type=int)
    rows = request.form.get("rows", 60, type=int)
    fps = request.form.get("fps", 0, type=int)
    max_frames = request.form.get("max_frames", 0, type=int)

    cols = max(1, min(cols, 500))
    rows = max(1, min(rows, 500))

    tmp_dir = tempfile.mkdtemp()
    _pending_cleanup.append(tmp_dir)

    try:
        input_path = os.path.join(tmp_dir, "input" + ext)
        output_path = os.path.join(tmp_dir, "ascii_sequence.blob")
        file.save(input_path)

        frames, source_fps = extract_frames_from_video(
            input_path,
            max_frames=max_frames if max_frames > 0 else None,
        )

        if not frames:
            return jsonify(error="No frames extracted from video"), 400

        actual_fps = fps if fps > 0 else max(1, int(round(source_fps)))

        convert_sequence_to_blob(frames, cols, rows, actual_fps, output_path)

        return send_file(
            output_path,
            as_attachment=True,
            download_name="ascii_sequence.blob",
            mimetype="application/octet-stream",
        )
    except Exception as e:
        return jsonify(error=str(e)), 500


@app.route("/preview", methods=["POST"])
def preview():
    """Generate an ASCII text preview from an uploaded image."""
    if "file" not in request.files:
        return jsonify(error="No file uploaded"), 400

    file = request.files["file"]
    if not file.filename:
        return jsonify(error="No file selected"), 400

    cols = request.form.get("cols", 100, type=int)
    rows = request.form.get("rows", 60, type=int)
    cols = max(1, min(cols, 500))
    rows = max(1, min(rows, 500))

    try:
        img = Image.open(file.stream).convert("L")
        img = img.resize((cols, rows), Image.LANCZOS)
        pixels = img.tobytes()

        lines = []
        for row in range(rows):
            chars = []
            for col in range(cols):
                brightness = pixels[row * cols + col]
                idx = brightness * (len(ASCII_RAMP) - 1) // 255
                chars.append(ASCII_RAMP[idx])
            lines.append("".join(chars))

        return jsonify(preview="\n".join(lines), cols=cols, rows=rows)
    except Exception as e:
        return jsonify(error=str(e)), 500


@app.route("/dimensions/video", methods=["POST"])
def video_dimensions():
    """Return width, height, fps, and frame count of an uploaded video."""
    if not HAS_CV2:
        return jsonify(error="OpenCV not installed"), 400

    if "file" not in request.files:
        return jsonify(error="No file uploaded"), 400

    file = request.files["file"]
    if not file.filename:
        return jsonify(error="No file selected"), 400

    tmp_dir = tempfile.mkdtemp()
    try:
        ext = os.path.splitext(file.filename)[1].lower()
        input_path = os.path.join(tmp_dir, "input" + ext)
        file.save(input_path)

        import cv2
        cap = cv2.VideoCapture(input_path)
        width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        source_fps = cap.get(cv2.CAP_PROP_FPS)
        total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        cap.release()

        return jsonify(
            width=width,
            height=height,
            source_fps=round(source_fps, 1),
            total_frames=total_frames,
        )
    except Exception as e:
        return jsonify(error=str(e)), 500
    finally:
        shutil.rmtree(tmp_dir, ignore_errors=True)


@app.route("/preview/video", methods=["POST"])
def preview_video():
    """Generate an ASCII text preview from the first frame of a video.
    Also returns source fps and total frame count (via OpenCV metadata, not full decode)."""
    if not HAS_CV2:
        return jsonify(error="OpenCV not installed"), 400

    if "file" not in request.files:
        return jsonify(error="No file uploaded"), 400

    file = request.files["file"]
    if not file.filename:
        return jsonify(error="No file selected"), 400

    cols = request.form.get("cols", 100, type=int)
    rows = request.form.get("rows", 60, type=int)
    cols = max(1, min(cols, 500))
    rows = max(1, min(rows, 500))

    tmp_dir = tempfile.mkdtemp()
    try:
        ext = os.path.splitext(file.filename)[1].lower()
        input_path = os.path.join(tmp_dir, "input" + ext)
        file.save(input_path)

        # Get metadata (fps and total frames) without decoding all frames
        import cv2
        cap = cv2.VideoCapture(input_path)
        source_fps = cap.get(cv2.CAP_PROP_FPS)
        total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        cap.release()

        # Extract just the first frame for preview
        frames, _ = extract_frames_from_video(input_path, max_frames=1)
        if not frames:
            return jsonify(error="Could not extract frames"), 400

        img = frames[0].convert("L").resize((cols, rows), Image.LANCZOS)
        pixels = img.tobytes()

        lines = []
        for row in range(rows):
            chars = []
            for col in range(cols):
                brightness = pixels[row * cols + col]
                idx = brightness * (len(ASCII_RAMP) - 1) // 255
                chars.append(ASCII_RAMP[idx])
            lines.append("".join(chars))

        return jsonify(
            preview="\n".join(lines),
            cols=cols,
            rows=rows,
            source_fps=round(source_fps, 1),
            total_frames=total_frames,
        )
    except Exception as e:
        return jsonify(error=str(e)), 500
    finally:
        shutil.rmtree(tmp_dir, ignore_errors=True)


def open_browser(port):
    try:
        webbrowser.open(f"http://localhost:{port}")
    except Exception:
        pass  # No GUI on cloud servers


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    print("=" * 50)
    print("  Rive ASCII Blob Converter")
    print(f"  http://localhost:{port}")
    print("  Press Ctrl+C to stop")
    print("=" * 50)
    Timer(1.0, open_browser, args=[port]).start()
    app.run(host="0.0.0.0", debug=False, port=port)
