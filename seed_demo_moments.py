import sqlite3
from pathlib import Path

DB_PATH = Path(__file__).resolve().parent / 'trackd.db'

MOMENTS = [
    ('nightdrive_nia', 'Heaven or Hell', 'Don Toliver', 'Late-night drive', 'Late-night highway drive', 'After Party sounded built for empty roads.', 'active'),
    ('crate_daniel', 'Rodeo', 'Travis Scott', 'Party', 'House party after midnight', '90210 turned the whole room cinematic.', 'passive'),
    ('velvetmaria', 'Die Lit', 'Playboi Carti', 'Gym', 'Weights before sunrise', 'Long Time made the warm-up feel twice as fast.', 'active'),
    ('mixtape_maya', 'Blonde', 'Frank Ocean', 'Heartbreak', 'Crying in the kitchen', 'White Ferrari made an ordinary night suddenly quiet.', 'active'),
    ('lowfi_leo', 'IGOR', 'Tyler, The Creator', 'Heartbreak', 'Alone on a rainy evening', 'GONE, GONE / THANK YOU was the perfect last word.', 'active'),
    ('crate_daniel', 'Currents', 'Tame Impala', 'Gym', 'Leg day', 'Let It Happen powered the whole session.', 'passive'),
    ('nightdrive_nia', 'rascal 51', 'bleood', 'Late-night drive', 'Rainy night drive', 'The production felt more spacious through headphones.', 'active'),
]

with sqlite3.connect(DB_PATH) as db:
    db.execute('PRAGMA foreign_keys = ON')
    columns = {row[1] for row in db.execute('PRAGMA table_info(listening_moments)').fetchall()}
    if 'category' not in columns:
        db.execute("ALTER TABLE listening_moments ADD COLUMN category TEXT NOT NULL DEFAULT 'Chilling'")
    added = 0
    for username, album, artist, category, context, note, listen_type in MOMENTS:
        user = db.execute('SELECT id FROM users WHERE username = ?', (username,)).fetchone()
        album_row = db.execute('SELECT id FROM albums WHERE title = ? AND artist = ? ORDER BY id LIMIT 1', (album, artist)).fetchone()
        if not user or not album_row:
            continue
        exists = db.execute('SELECT 1 FROM listening_moments WHERE user_id = ? AND album_id = ? AND note = ?', (user[0], album_row[0], note)).fetchone()
        if exists:
            continue
        db.execute('INSERT INTO listening_moments (user_id, album_id, listen_type, context, category, note) VALUES (?, ?, ?, ?, ?, ?)', (user[0], album_row[0], listen_type, context, category, note))
        added += 1
print(f'Seeded {added} demo listening moments.')
