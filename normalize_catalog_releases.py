import sqlite3
from pathlib import Path
import re

DB_PATH = Path(__file__).resolve().parent / 'trackd.db'

EP_TITLE_MARKERS = re.compile(r'\b(ep|remixes?|expanded edition)\b|\bremix(es)?\b', re.IGNORECASE)

with sqlite3.connect(DB_PATH) as db:
    db.row_factory = sqlite3.Row
    releases = db.execute('''
        SELECT albums.id, albums.title, albums.release_type,
               COUNT(songs.id) AS track_count
        FROM albums LEFT JOIN songs ON songs.album_id = albums.id
        GROUP BY albums.id
    ''').fetchall()

    for release in releases:
        title = release['title'] or ''
        current = (release['release_type'] or '').strip().lower()
        track_count = release['track_count']

        # Explicit release labels and remix collections must not become albums
        # merely because they contain many downloadable tracks.
        if EP_TITLE_MARKERS.search(title) or current in ('ep', 'eps'):
            release_type = 'EP'
        elif current in ('single', 'singles') or track_count == 1:
            release_type = 'Single'
        elif track_count <= 6:
            release_type = 'EP'
        else:
            release_type = 'Album'

        db.execute('UPDATE albums SET release_type = ? WHERE id = ?',
                   (release_type, release['id']))
    db.commit()

print('Corrected release classifications by type labels, title, and track count.')
