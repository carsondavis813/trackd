import sqlite3
from pathlib import Path
from werkzeug.security import generate_password_hash

DB_PATH = Path(__file__).resolve().parent / 'trackd.db'

ACCOUNTS = [
    ('nightdrive_nia', 'Nia Torres'),
    ('crate_daniel', 'Daniel Kim'),
    ('velvetmaria', 'Maria Chen'),
    ('lowfi_leo', 'Leo Mercer'),
    ('mixtape_maya', 'Maya Brooks'),
]

REVIEW_CATEGORIES = {
    'Heaven or Hell': 'Late-night drive',
    'Rodeo': 'Party',
    'Die Lit': 'Party',
    'ye': 'Chilling',
    'Blonde': 'Heartbreak',
    'IGOR': 'Heartbreak',
    'rascal 51': 'Late-night drive',
    'PROTAGONIST': 'Focus',
    'pain': 'Crying in the kitchen',
    'Currents': 'Gym',
}

REVIEWS = [
    ('Heaven or Hell', 'Don Toliver', 'Don Toliver turns the album’s title into a promise and a warning. “Cardigan” floats, but “After Party” is the song that explains why this record still moves so many rooms.', 4.5, 'nightdrive_nia'),
    ('Rodeo', 'Travis Scott', 'Rodeo has a theatrical sense of scale. “90210” changes shape so dramatically that the track feels like two different dreams stitched together, while “Antidote” keeps the whole trip accessible.', 4.5, 'crate_daniel'),
    ('Die Lit', 'Playboi Carti', '“Long Time” is an immaculate introduction, and “Shoota” makes chaos feel engineered rather than random. The album’s melodies are a little more durable than its sparse lyricism suggests.', 4.0, 'velvetmaria'),
    ('ye', 'Ye', 'The blunt intensity of “Yikes” and the uneasy warmth of “Ghost Town” make ye feel tightly focused. It is only a short record, but its best moments leave a larger afterimage.', 4.0, 'lowfi_leo'),
    ('Blonde', 'Frank Ocean', '“Nikes,” “Self Control,” and “White Ferrari” turn restraint into emotion. Blonde rewards patience: every small vocal decision feels intentional and deeply personal.', 5.0, 'mixtape_maya'),
    ('IGOR', 'Tyler, The Creator', 'IGOR uses love like a broken synthesizer—beautiful, unstable, and loud. “EARFQUAKE” is the hook, but “GONE, GONE / THANK YOU” gives the heartbreak its most memorable shape.', 4.5, 'nightdrive_nia'),
    ('rascal 51', 'bleood', 'bleood keeps the edges raw here. “protagnosit” bends in strange directions, while “rascal 51” shows how much atmosphere can carry when the vocal stays close and confidential.', 4.0, 'crate_daniel'),
    ('PROTAGONIST', 'bleood', 'The momentum comes from tension: tracks pull toward a melody and then reject it. It is less polished than mainstream rap, which is exactly where its identity becomes interesting.', 4.0, 'lowfi_leo'),
    ('pain', 'bleood', 'pain feels personal without becoming literal. The strongest moments use repetition as pressure, especially around tracks that sound like unfinished thoughts rather than conventional hooks.', 3.5, 'velvetmaria'),
    ('Currents', 'Tame Impala', '“Let It Happen” makes surrender sound enormous, and “The Less I Know the Better” remains the sharpest pop turn Kevin Parker has written. Currents is elegant even when it is falling apart.', 4.5, 'mixtape_maya'),
]

with sqlite3.connect(DB_PATH) as db:
    db.execute('PRAGMA foreign_keys = ON')
    review_columns = {row[1] for row in db.execute('PRAGMA table_info(reviews)').fetchall()}
    if 'category' not in review_columns:
        db.execute("ALTER TABLE reviews ADD COLUMN category TEXT NOT NULL DEFAULT 'Chilling'")
    for username, display_name in ACCOUNTS:
        existing = db.execute('SELECT id FROM users WHERE lower(username) = lower(?)', (username,)).fetchone()
        if existing:
            continue
        db.execute(
            'INSERT INTO users (username, password_hash) VALUES (?, ?)',
            (username, generate_password_hash('trackd-demo-2026')),
        )

    added = 0
    for album_title, artist, review, rating, username in REVIEWS:
        album = db.execute(
            'SELECT id FROM albums WHERE title = ? AND artist = ? ORDER BY id LIMIT 1',
            (album_title, artist),
        ).fetchone()
        if not album:
            print(f'SKIPPED: {artist} — {album_title} is not on the site')
            continue
        display_name = dict(ACCOUNTS)[username]
        exists = db.execute(
            'SELECT 1 FROM reviews WHERE album_id = ? AND display_name = ?',
            (album[0], display_name),
        ).fetchone()
        if exists:
            db.execute('UPDATE reviews SET category = ? WHERE album_id = ? AND display_name = ?',
                       (REVIEW_CATEGORIES.get(album_title, 'Chilling'), album[0], display_name))
            continue
        db.execute(
            'INSERT INTO reviews (album_id, display_name, rating, review_text, category) VALUES (?, ?, ?, ?, ?)',
            (album[0], display_name, rating, review, REVIEW_CATEGORIES.get(album_title, 'Chilling')),
        )
        added += 1

print(f'Seeded {len(ACCOUNTS)} demo accounts and {added} reviews.')
print('Demo login password: trackd-demo-2026')
