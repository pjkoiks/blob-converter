"""
Generates a test gradient image and converts it to ascii_data.bin
Use this to verify the workflow before using your own image.
"""

from PIL import Image
from ascii_preprocess import convert_image_to_ascii_bin

# Create a 400x240 gradient test image (diamond-like radial pattern)
width, height = 400, 240
img = Image.new("L", (width, height))

cx, cy = width // 2, height // 2
max_dist = ((cx ** 2) + (cy ** 2)) ** 0.5

pixels = img.load()
for y in range(height):
    for x in range(width):
        dist = ((x - cx) ** 2 + (y - cy) ** 2) ** 0.5
        brightness = int(255 * max(0, 1 - dist / max_dist))
        pixels[x, y] = brightness

img.save("test_gradient.png")
print("Created test_gradient.png")

# Convert to binary
convert_image_to_ascii_bin("test_gradient.png", cols=100, rows=60)

# Verify the output
import struct

with open("ascii_data.bin", "rb") as f:
    data = f.read()

cols, rows = struct.unpack("<HH", data[:4])
body = data[4:]
print(f"\nVerification:")
print(f"  Header: cols={cols}, rows={rows}")
print(f"  Body length: {len(body)} bytes (expected {cols * rows})")
print(f"  Match: {len(body) == cols * rows}")
print(f"  Brightness range: {min(body)} - {max(body)}")
print(f"\nFirst row sample (10 values): {list(body[:10])}")
