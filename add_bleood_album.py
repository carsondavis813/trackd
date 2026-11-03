import json
import sqlite3
import urllib.request

DB_PATH = 'trackd.db'
ALBUM_ID = 1134317221

with urllib.request.urlopen(f'https://api.deezer.com/album/{ALBUM_ID}', timeout=30) as response:
    release = json.loads(response.read())

with sqlite3.connect(DB_PATH) as db:
    db.execute('PRAGMA foreign_keys = ON')
    musician = db.execute("SELECT id FROM musicians WHERE slug = 'bleood'").fetchone()
    if musician is None:
        raise SystemExit('bleood musician not found')

    existing = db.execute(
        "SELECT id FROM albums WHERE title = ? AND lower(artist) = 'bleood' LIMIT 1",
        (release['title'],),
    ).fetchone()
    if existing:
        album_id = existing[0]
        db.execute(
            'UPDATE albums SET year = ?, cover_url = ?, release_type = ? WHERE id = ?',
            (int(release['release_date'][:4]), release['cover_xl'], 'Album', album_id),
        )
    else:
        cursor = db.execute(
            "INSERT INTO albums (title, artist, year, genre, art_class, release_type, cover_url) VALUES (?, ?, ?, ?, ?, ?, ?)",
            ('KILL YOUR IDOLS', 'bleood', 2026, 'Hip-hop', 'art-imported', 'Album', release['cover_xl']),
        )
        album_id = cursor.lastrowid

    db.execute('INSERT OR IGNORE INTO album_musicians (album_id, musician_id) VALUES (?, ?)', (album_id, musician[0]))
    db.execute(
        "INSERT OR IGNORE INTO album_genres (album_id, genre_id) SELECT ?, id FROM genres WHERE name = 'Hip-hop'",
        (album_id,),
    )

    for position, track in enumerate(release['tracks']['data'], 1):
        duration_ms = track.get('duration', 0) * 1000 or None
        existing_song = db.execute(
            'SELECT id FROM songs WHERE album_id = ? AND title = ? LIMIT 1',
            (album_id, track['title']),
        ).fetchone()
        if existing_song:
            db.execute(
                'UPDATE songs SET track_number = ?, length_ms = COALESCE(length_ms, ?), preview_url = COALESCE(preview_url, ?) WHERE id = ?',
                (position, duration_ms, track.get('preview'), existing_song[0]),
            )
        else:
            db.execute(
                'INSERT INTO songs (musicbrainz_id, album_id, title, track_number, length_ms, preview_url) VALUES (?, ?, ?, ?, ?, ?)',
                (f'deezer:bleood:album:{ALBUM_ID}:track:{position}', album_id, track['title'], position, duration_ms, track.get('preview')),
            )

print(f"Added KILL YOUR IDOLS with {len(release['tracks']['data'])} tracks to bleood")
