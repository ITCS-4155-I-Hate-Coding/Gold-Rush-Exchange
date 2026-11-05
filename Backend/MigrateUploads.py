# run once from the Backend folder:  python migrate_uploads.py
# copies pictures saved in the old ../uploads folder into the post_images table,
# so posts made before the switch to database storage show their pictures again.
# safe to run again (files already copied are skipped).

import psycopg2

import ImageBackend as images
from db import query

copied = 0
for path in sorted(images.UPLOAD_DIR.glob("*")):
    if not images.valid_name(path.name):
        continue
    ext = path.suffix.lstrip(".").lower()
    query(
        "INSERT INTO post_images (name, mime, data) VALUES (%s, %s, %s) ON CONFLICT (name) DO NOTHING",
        (path.name, images.MIME_TYPES[ext], psycopg2.Binary(path.read_bytes())),
        fetch=False,
    )
    copied += 1
    print("copied", path.name)

print(f"done, {copied} picture(s) processed")