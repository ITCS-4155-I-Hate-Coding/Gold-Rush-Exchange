#pip install Pillow, python apply_schema.py
import io
import re
import uuid
from pathlib import Path
import psycopg2
from db import query

from PIL import Image, ImageOps

# pictures are saved here, next to the Backend and Frontend folders (NOT inside Frontend, which Flask serves as-is)
UPLOAD_DIR = Path(__file__).resolve().parent.parent / "uploads"

IMAGE_MAX_BYTES = 5 * 1024 * 1024  # the biggest picture a user can send
REQUEST_MAX = IMAGE_MAX_BYTES + 512 * 1024  # picture plus the text fields around it
MAX_SIDE = 1600  # bigger photos are shrunk to this many pixels on the long side so pages stay fast

# refuse "decompression bombs": tiny files that unpack into enormous pictures
Image.MAX_IMAGE_PIXELS = 40_000_000

# the picture formats we accept, and the file ending each one is saved with
FORMATS = {"JPEG": "jpg", "PNG": "png", "GIF": "gif", "WEBP": "webp"}
MIME_TYPES = {"jpg": "image/jpeg", "png": "image/png", "gif": "image/gif", "webp": "image/webp"}

# names we create look like 32 hex letters + an ending; anything else is never served
NAME_RE = re.compile(r"^[0-9a-f]{32}\.(jpg|png|gif|webp)$")


def valid_name(name):
    return bool(NAME_RE.match(name or ""))


def url_for(filename):
    return f"/uploads/{filename}" if filename else None


def save_image(upload):
    """Check an uploaded picture and save it. Returns (filename, error_message)."""
    data = upload.read(IMAGE_MAX_BYTES + 1)
    if not data:
        return None, "That image is empty."
    if len(data) > IMAGE_MAX_BYTES:
        return None, "Images can be at most 5 MB."

    # open it for real instead of trusting the file name or the browser's content type,
    # both of which the sender controls
    try:
        img = Image.open(io.BytesIO(data))
        fmt = img.format
        img.verify()
        img = Image.open(io.BytesIO(data))  # verify() uses the picture up, so open it again
        animated = getattr(img, "is_animated", False)
        if fmt not in FORMATS:
            return None, "Please upload a JPG, PNG, GIF or WebP image."
        if animated:
            out = data  # keep GIFs / animated WebPs exactly as sent so they keep moving
        else:
            # phones store "which way is up" in hidden metadata (along with the GPS location).
            # turn the pixels the right way round, then save without any of that metadata
            img = ImageOps.exif_transpose(img)
            img.thumbnail((MAX_SIDE, MAX_SIDE))
            buf = io.BytesIO()
            if fmt == "JPEG":
                img.convert("RGB").save(buf, "JPEG", quality=85, optimize=True)
            elif fmt == "PNG":
                img.save(buf, "PNG", optimize=True)
            elif fmt == "WEBP":
                img.save(buf, "WEBP", quality=85)
            else:  # a single-frame GIF
                img.save(buf, "GIF")
            out = buf.getvalue()
    except Exception:
        return None, "That file isn't a valid image."

    ext = FORMATS[fmt]
    name = f"{uuid.uuid4().hex}.{ext}"
    query(
        "INSERT INTO post_images (name, mime, data) VALUES (%s, %s, %s)",
        (name, MIME_TYPES[ext], psycopg2.Binary(out)),
        fetch = False,
    )
    return name, None


def get_image(name):
    # return the (bytes, mime type) or None
    if not valid_name(name):
        return None

    row = query("SELECT mime, data FROM post_images WHERE name = %s", (name,), fetchone = True)
    if row:
        return bytes(row["data"]), row["mime"]

def delete_image(filename):
    if valid_name(filename):
        query("DELETE FROM post_images WHERE name = %s", (filename,), fetch = False)



#     # the name is random, so the sender's file name is never used on disk
#     name = f"{uuid.uuid4().hex}.{FORMATS[fmt]}"
#     UPLOAD_DIR.mkdir(exist_ok=True)
#     (UPLOAD_DIR / name).write_bytes(out)
#     return name, None


# def delete_image(filename):
#     # used when saving a post fails after its picture was already written
#     if valid_name(filename):
#         try:
#             (UPLOAD_DIR / filename).unlink()
#         except OSError:
#             pass

# name will be random so senders file name is not used
