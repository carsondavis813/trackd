import random
import sqlite3
from pathlib import Path

DB_PATH = Path(__file__).resolve().parent / 'trackd.db'

REVIEWERS = [
    'nightdrive_nia', 'crate_daniel', 'velvetmaria', 'lowfi_leo', 'mixtape_maya',
    'analog_iris', 'neonnoah', 'sideb_track', 'cedar_rose', 'deepcuts_dev',
]
CATEGORIES = ['Late-night drive', 'Heartbreak', 'Gym', 'Party', 'Cooking', 'Getting ready', 'Focus', 'Road trip', 'Chilling', 'Crying in the kitchen']

POSITIVE = (
    'The best parts of “{title}” feel effortless, with the production leaving enough room for the vocal and rhythm to breathe. It has real replay value.',
    '“{title}” finds its identity quickly. The arrangement is confident, the hook lands without feeling forced, and the details keep revealing themselves.',
    'This is one of the more memorable moments on {release}. The pacing is strong and the performance gives the song a distinct emotional center.',
    '“{title}” balances its catchiest idea with a surprisingly thoughtful atmosphere. It works immediately but still rewards another listen.',
    'A strong blend of personality and polish. “{title}” knows exactly what it wants to be, and every part of the arrangement supports that idea.',
)
MIXED = (
    '“{title}” has a strong idea and a few excellent moments, though some of the production choices make the middle feel less focused.',
    'The vocal performance carries “{title}.” It is not the strongest track on {release}, but there are enough memorable details to make it worthwhile.',
    'There is real potential in “{title},” especially in the hook and final section. A little more restraint in the arrangement could have made it hit harder.',
)
SILLY_ALBUMS = (
    'I put on “{title}” to clean one room and somehow emotionally adopted the entire apartment. Ten out of ten, no regrets.',
    '“{title}” has absolutely no right to make my grocery run feel like the finale of a movie. I was buying cereal at full dramatic intensity.',
    'The neighbors have asked if I am okay because “{title}” has been playing on repeat. The answer is not important right now.',
    '“{title}” went into my headphones, took control of my personality for 38 minutes, and left me considering entirely new outfits.',
    'My dog usually hates albums. Even he stopped staring at the door during “{title}.” That is a rare endorsement.',
)
SILLY_SONGS = (
    '“{title}” walked into my day, stole the aux, and refused to return it. Honestly, I understand its decision.',
    'I played “{title}” once and immediately became that person nodding slowly by the window like I am in a prestige drama.',
    '“{title}” understands the assignment better than I understand my own laundry schedule. Immediate replay.',
    'My kitchen playlist needed one more thing, then “{title}” showed up and turned the pasta into an emotional event.',
    '“{title}” has 15 seconds of charm per second, somehow, and I am not filing a complaint.',
)

with sqlite3.connect(DB_PATH) as db:
    db.row_factory = sqlite3.Row
    db.execute('PRAGMA foreign_keys = ON')
    db.execute("CREATE TABLE IF NOT EXISTS song_reviews (id INTEGER PRIMARY KEY AUTOINCREMENT, song_id INTEGER NOT NULL REFERENCES songs(id) ON DELETE CASCADE, display_name TEXT NOT NULL, rating REAL NOT NULL CHECK(rating >= 0.5 AND rating <= 5), review_text TEXT NOT NULL, created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP, category TEXT NOT NULL DEFAULT 'Chilling')")

    random.seed(20261102)
    albums = db.execute("SELECT id,title,artist FROM albums WHERE lower(release_type)=?", ('album',)).fetchall()
    chart_albums = [row['id'] for row in db.execute("SELECT id FROM albums WHERE chart_rank IS NOT NULL ORDER BY chart_rank LIMIT 89")]
    albums.sort(key=lambda row: 0 if row['id'] in chart_albums else 1)

    album_added = 0
    for index, album in enumerate(albums[:350]):
        reviewer = REVIEWERS[index % len(REVIEWERS)]
        exists = db.execute('SELECT 1 FROM reviews WHERE album_id=? AND display_name=?', (album['id'], reviewer)).fetchone()
        if exists:
            continue
        rating = random.choice((3.5, 4.0, 4.0, 4.5, 4.5, 5.0))
        text = random.choice(POSITIVE).format(title=album['title'], release=album['title'])
        db.execute('INSERT INTO reviews (album_id,display_name,rating,review_text,category) VALUES (?,?,?,?,?)',
                   (album['id'], reviewer, rating, text, random.choice(CATEGORIES)))
        album_added += 1

    songs = db.execute('''SELECT songs.id,songs.title,albums.artist,albums.title album_title
                          FROM songs JOIN albums ON albums.id=songs.album_id LIMIT 5000''').fetchall()
    chart_song_ids = [row['id'] for row in db.execute('SELECT id FROM songs WHERE chart_rank IS NOT NULL ORDER BY chart_rank')]
    songs.sort(key=lambda row: 0 if row['id'] in chart_song_ids else 1)
    song_added = 0
    for index, song in enumerate(songs[:350]):
        reviewer = REVIEWERS[(index * 3) % len(REVIEWERS)]
        exists = db.execute('SELECT 1 FROM song_reviews WHERE song_id=? AND display_name=?', (song['id'], reviewer)).fetchone()
        if exists:
            continue
        rating = random.choice((3.0, 3.5, 4.0, 4.0, 4.5, 4.5))
        template = random.choice(POSITIVE if rating >= 4 else MIXED)
        text = template.format(title=song['title'], release=f'{song["artist"]}’s catalog')
        db.execute('INSERT INTO song_reviews (song_id,display_name,rating,review_text,category) VALUES (?,?,?,?,?)',
                   (song['id'], reviewer, rating, text, random.choice(CATEGORIES)))
        song_added += 1

    placeholders = ','.join('?' for _ in REVIEWERS)
    for row in db.execute(f'''SELECT reviews.id, reviews.album_id, reviews.review_text, albums.title
                              FROM reviews JOIN albums ON albums.id=reviews.album_id
                              WHERE reviews.display_name IN ({placeholders})''', REVIEWERS):
        if row['id'] % 3 == 0:
            text = random.choice(SILLY_ALBUMS).format(title=row['title'])
            db.execute("UPDATE reviews SET review_text=?, category=? WHERE id=?",
                       (text, random.choice(('Cereal-run soundtrack', 'Cleaning soundtrack', 'Window-seat drama')), row['id']))

    for row in db.execute(f'''SELECT song_reviews.id, songs.title
                              FROM song_reviews JOIN songs ON songs.id=song_reviews.song_id
                              WHERE song_reviews.display_name IN ({placeholders})''', REVIEWERS):
        if row['id'] % 3 == 0:
            text = random.choice(SILLY_SONGS).format(title=row['title'])
            db.execute("UPDATE song_reviews SET review_text=?, category=? WHERE id=?",
                       (text, random.choice(('Kitchen chaos', 'Main-character walk', 'Pasta soundtrack')), row['id']))
    db.commit()

print(f'Realistic review seed complete: {album_added} album reviews and {song_added} song reviews added. Sample posts now include casual humor.')
