
from PIL import Image
from pathlib import Path

cursor_dir = Path("public/cursors")

cursors = {
    "green-triangle.png": "small-green-triangle.png",
    "green-hand.png": "small-green-hand.png"
}

for original, resized in cursors.items():
    source = cursor_dir / original
    output = cursor_dir / resized

    if not source.exists():
        print(f"Missing file: {source}")
        continue

    image = Image.open(source).convert("RGBA")
    image.thumbnail((32, 32), Image.Resampling.LANCZOS)
    image.save(output)

    print(f"Created: {output} ({image.width}x{image.height})")
