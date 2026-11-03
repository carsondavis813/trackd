from pathlib import Path
import os
import sqlite3
import json
import re
import urllib.parse
import urllib.request
from flask import Flask, abort, flash, redirect, render_template, request, session, url_for
from werkzeug.security import check_password_hash, generate_password_hash

BASE_DIR = Path(__file__).resolve().parent
DB_PATH = Path(os.environ.get('TRACKD_DATABASE_PATH', BASE_DIR / 'trackd.db'))
app = Flask(__name__)
app.secret_key = os.environ.get('TRACKD_SECRET_KEY', 'local-development-only-change-before-deploying')

ALBUMS = [
    (1, 'Blonde', 'Frank Ocean', 2016, 'Pop', 'art-blonde'),
    (2, 'IGOR', 'Tyler, The Creator', 2019, 'Hip-hop', 'art-igor'),
    (3, 'Rodeo', 'Travis Scott', 2015, 'Hip-hop', 'art-rodeo'),
    (4, 'The Forever Story', 'JID', 2022, 'Hip-hop', 'art-story'),
    (5, 'Alfredo', 'Freddie Gibbs & The Alchemist', 2020, 'Hip-hop', 'art-alfredo'),
    (6, 'Heaven or Hell', 'Don Toliver', 2020, 'Hip-hop', 'art-heaven'),
    (7, 'MM..FOOD', 'MF DOOM', 2004, 'Hip-hop', 'art-food'),
    (8, 'Currents', 'Tame Impala', 2015, 'Rock', 'art-currents'),
    (10, 'Die Lit', 'Playboi Carti', 2018, 'Hip-hop', 'art-die-lit'),
    (11, 'ye', 'Ye', 2018, 'Hip-hop', 'art-ye'),
    (12, 'rascal 51', 'bleood', 2025, 'Hip-hop', 'art-rascal-51'),
    (13, 'PROTAGONIST', 'bleood', 2026, 'Hip-hop', 'art-protagonist'),
    (14, 'pain', 'bleood', 2025, 'Hip-hop', 'art-pain'),
]

SAMPLE_SONGS = (
    (10, 'trackd:playboi-carti-die-lit-1', 'Long Time (Intro)', 1),
    (10, 'trackd:playboi-carti-die-lit-2', 'R.I.P.', 2),
    (10, 'trackd:playboi-carti-die-lit-3', 'Lean 4 Real', 3),
    (10, 'trackd:playboi-carti-die-lit-4', 'Old Money', 4),
    (10, 'trackd:playboi-carti-die-lit-5', 'Love Hurts', 5),
    (10, 'trackd:playboi-carti-die-lit-6', 'Shoota', 6),
    (10, 'trackd:playboi-carti-die-lit-7', 'Right Now', 7),
    (10, 'trackd:playboi-carti-die-lit-8', 'Poke It Out', 8),
    (10, 'trackd:playboi-carti-die-lit-9', 'Home (KOD)', 9),
    (10, 'trackd:playboi-carti-die-lit-10', 'Fell in Luv', 10),
    (11, 'trackd:ye-ye-1', 'I Thought About Killing You', 1),
    (11, 'trackd:ye-ye-2', 'Yikes', 2),
    (11, 'trackd:ye-ye-3', 'All Mine', 3),
    (11, 'trackd:ye-ye-4', "Wouldn't Leave", 4),
    (11, 'trackd:ye-ye-5', 'No Mistakes', 5),
    (11, 'trackd:ye-ye-6', 'Ghost Town', 6),
    (11, 'trackd:ye-ye-7', 'Violent Crimes', 7),
)


MOMENT_CATEGORIES = (
    'Late-night drive', 'Heartbreak', 'Gym', 'Party', 'Cooking',
    'Getting ready', 'Focus', 'Road trip', 'Chilling', 'Crying in the kitchen',
)

GENRES = (
    'Classical', 'Blues', 'Country', 'Electronic', 'Folk',
    'Hip-hop', 'Jazz', 'Pop', 'Rock', 'Movie scores',
)
GENRE_SLUGS = {genre: genre.lower().replace(' ', '-') for genre in GENRES}
ALBUM_GENRES = {
    1: ('Pop', 'Blues'),
    2: ('Hip-hop',),
    3: ('Hip-hop',),
    4: ('Hip-hop',),
    5: ('Hip-hop',),
    6: ('Hip-hop',),
    7: ('Hip-hop',),
    8: ('Rock',),
    10: ('Hip-hop',),
    11: ('Hip-hop', 'Pop'),
    12: ('Hip-hop',),
    13: ('Hip-hop',),
    14: ('Hip-hop',),
}

MUSICIANS = (
    ('bleood', 'bleood', ('Hip-hop',)),
    ('Playboi Carti', 'playboi-carti', ('Hip-hop',)),
    ('Travis Scott', 'travis-scott', ('Hip-hop',)),
    ('Ken Carson', 'ken-carson', ('Hip-hop',)),
    ('Destroy Lonely', 'destroy-lonely', ('Hip-hop',)),
    ('Don Toliver', 'don-toliver', ('Hip-hop',)),
    ('Boolymon', 'boolymon', ('Hip-hop',)),
    ('OsamaSon', 'osamason', ('Hip-hop',)),
    ('Che', 'che', ('Hip-hop',)),
    ('Nettspend', 'nettspend', ('Hip-hop',)),
    ('Young Thug', 'young-thug', ('Hip-hop',)),
    ('Tezzus', 'tezzus', ('Hip-hop',)),
    ('Diamond*', 'diamond', ('Hip-hop',)),
    ("Pz'", 'pz', ('Hip-hop',)),
    ('SlimeGetEm', 'slimegetem', ('Hip-hop',)),
    ('Drake', 'drake', ('Hip-hop', 'Pop')),
    ('SoFaygo', 'sofaygo', ('Hip-hop',)),
    ('Homixide Gang', 'homixide-gang', ('Hip-hop',)),
    ('A$AP Rocky', 'asap-rocky', ('Hip-hop',)),
    ('Taylor Swift', 'taylor-swift', ('Country', 'Pop')),
    ('Luke Bryan', 'luke-bryan', ('Country',)),
    ('Lady Gaga', 'lady-gaga', ('Pop',)),
    ('Nicki Minaj', 'nicki-minaj', ('Hip-hop', 'Pop')),
    ('Cardi B', 'cardi-b', ('Hip-hop',)),
    ('Offset', 'offset', ('Hip-hop',)),
    ('Quavo', 'quavo', ('Hip-hop',)),
    ('Takeoff', 'takeoff', ('Hip-hop',)),
    ("Pi'erre Bourne", 'pierre-bourne', ('Hip-hop', 'Electronic')),
    ('Lil Uzi Vert', 'lil-uzi-vert', ('Hip-hop',)),
    ('Kanye West', 'kanye-west', ('Hip-hop', 'Pop')),
    ('Ye', 'ye', ('Hip-hop', 'Pop')),
)

COMING_SOON_SECTIONS = {
    'songs': 'Songs',
    'my-account': 'My Account',
}

def get_db():
    connection = sqlite3.connect(DB_PATH)
    connection.row_factory = sqlite3.Row
    connection.execute('PRAGMA foreign_keys = ON')
    return connection


def get_sort(requested_sort, default='trending'):
    return requested_sort if requested_sort in ('trending', 'popular', 'newest') else default


def init_db():
    with get_db() as db:
        db.executescript('''
            CREATE TABLE IF NOT EXISTS albums (
                id INTEGER PRIMARY KEY,
                title TEXT NOT NULL,
                artist TEXT NOT NULL,
                year INTEGER NOT NULL,
                genre TEXT NOT NULL,
                art_class TEXT NOT NULL,
                musicbrainz_id TEXT UNIQUE,
                release_type TEXT NOT NULL DEFAULT 'Album',
                cover_url TEXT
            );
            CREATE TABLE IF NOT EXISTS reviews (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                album_id INTEGER NOT NULL REFERENCES albums(id),
                display_name TEXT NOT NULL,
                rating REAL NOT NULL CHECK(rating >= 0.5 AND rating <= 5),
                review_text TEXT NOT NULL,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            );
            CREATE TABLE IF NOT EXISTS genres (
                id INTEGER PRIMARY KEY,
                name TEXT NOT NULL UNIQUE,
                slug TEXT NOT NULL UNIQUE
            );
            CREATE TABLE IF NOT EXISTS album_genres (
                album_id INTEGER NOT NULL REFERENCES albums(id),
                genre_id INTEGER NOT NULL REFERENCES genres(id),
                PRIMARY KEY (album_id, genre_id)
            );
            CREATE TABLE IF NOT EXISTS album_musicians (
                album_id INTEGER NOT NULL REFERENCES albums(id),
                musician_id INTEGER NOT NULL REFERENCES musicians(id),
                PRIMARY KEY (album_id, musician_id)
            );
            CREATE TABLE IF NOT EXISTS musicians (
                id INTEGER PRIMARY KEY,
                name TEXT NOT NULL UNIQUE,
                slug TEXT NOT NULL UNIQUE,
                musicbrainz_id TEXT UNIQUE,
                image_url TEXT,
                image_source_url TEXT,
                image_license TEXT,
                image_license_url TEXT,
                image_credit TEXT
            );
            CREATE TABLE IF NOT EXISTS musician_genres (
                musician_id INTEGER NOT NULL REFERENCES musicians(id),
                genre_id INTEGER NOT NULL REFERENCES genres(id),
                PRIMARY KEY (musician_id, genre_id)
            );
            CREATE TABLE IF NOT EXISTS songs (
                id INTEGER PRIMARY KEY,
                musicbrainz_id TEXT NOT NULL UNIQUE,
                album_id INTEGER NOT NULL REFERENCES albums(id),
                title TEXT NOT NULL,
                track_number INTEGER NOT NULL,
                length_ms INTEGER,
                preview_url TEXT
            );
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT NOT NULL UNIQUE,
                password_hash TEXT NOT NULL,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            );
            CREATE TABLE IF NOT EXISTS user_genres (
                user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                genre_id INTEGER NOT NULL REFERENCES genres(id) ON DELETE CASCADE,
                PRIMARY KEY (user_id, genre_id)
            );
            CREATE TABLE IF NOT EXISTS listening_moments (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                album_id INTEGER NOT NULL REFERENCES albums(id) ON DELETE CASCADE,
                mvp_song_id INTEGER REFERENCES songs(id) ON DELETE SET NULL,
                listen_type TEXT NOT NULL CHECK(listen_type IN ('active', 'passive')),
                context TEXT NOT NULL,
                note TEXT NOT NULL DEFAULT '',
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            );
        ''')
        album_columns = {row['name'] for row in db.execute('PRAGMA table_info(albums)')}
        if 'musicbrainz_id' not in album_columns:
            db.execute('ALTER TABLE albums ADD COLUMN musicbrainz_id TEXT')
        if 'release_type' not in album_columns:
            db.execute("ALTER TABLE albums ADD COLUMN release_type TEXT NOT NULL DEFAULT 'Album'")
        if 'cover_url' not in album_columns:
            db.execute('ALTER TABLE albums ADD COLUMN cover_url TEXT')
        db.execute('CREATE INDEX IF NOT EXISTS idx_songs_album_id ON songs(album_id)')
        review_columns = {row['name'] for row in db.execute('PRAGMA table_info(reviews)')}
        if 'category' not in review_columns:
            db.execute("ALTER TABLE reviews ADD COLUMN category TEXT NOT NULL DEFAULT 'Chilling'")
        moment_columns = {row['name'] for row in db.execute('PRAGMA table_info(listening_moments)')}
        if 'category' not in moment_columns:
            db.execute("ALTER TABLE listening_moments ADD COLUMN category TEXT NOT NULL DEFAULT 'Chilling'")
        song_columns = {row['name'] for row in db.execute('PRAGMA table_info(songs)')}
        if 'preview_url' not in song_columns:
            db.execute('ALTER TABLE songs ADD COLUMN preview_url TEXT')
        db.executescript('''CREATE TABLE IF NOT EXISTS song_reviews (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            song_id INTEGER NOT NOT REFERENCES songs(id) ON DELETE CASCADE,
            display_name TEXT NOT NULL,
            rating REAL NOT NULL CHECK(rating >= 0.5 AND rating <= 5),
            review_text TEXT NOT NULL,
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            category TEXT NOT NULL DEFAULT 'Chilling'
        );'''.replace('song_id INTEGER NOT NOT REFERENCES', 'song_id INTEGER NOT NULL REFERENCES'))
        if 'chart_rank' not in song_columns:
            db.execute('ALTER TABLE songs ADD COLUMN chart_rank INTEGER')
        if 'chart_rank_updated_at' not in song_columns:
            db.execute('ALTER TABLE songs ADD COLUMN chart_rank_updated_at TEXT')
        album_columns = {row['name'] for row in db.execute('PRAGMA table_info(albums)')}
        if 'chart_rank' not in album_columns:
            db.execute('ALTER TABLE albums ADD COLUMN chart_rank INTEGER')
        if 'chart_rank_updated_at' not in album_columns:
            db.execute('ALTER TABLE albums ADD COLUMN chart_rank_updated_at TEXT')
        musician_columns = {row['name'] for row in db.execute('PRAGMA table_info(musicians)')}
        if 'chart_rank' not in musician_columns:
            db.execute('ALTER TABLE musicians ADD COLUMN chart_rank INTEGER')
        if 'chart_rank_updated_at' not in musician_columns:
            db.execute('ALTER TABLE musicians ADD COLUMN chart_rank_updated_at TEXT')
        for column in (
            'musicbrainz_id', 'image_url', 'image_source_url',
            'image_license', 'image_license_url', 'image_credit',
        ):
            if column not in musician_columns:
                db.execute(f'ALTER TABLE musicians ADD COLUMN {column} TEXT')
        # Remove the unverified bleood sample release without touching reviews or the musician.
        invalid_bleood_album = db.execute(
            "SELECT id FROM albums WHERE title = 'Seal of Memories' AND artist = 'bleood'"
        ).fetchone()
        if invalid_bleood_album and db.execute(
            'SELECT COUNT(*) FROM reviews WHERE album_id = ?', (invalid_bleood_album['id'],)
        ).fetchone()[0] == 0:
            db.execute('DELETE FROM songs WHERE album_id = ?', (invalid_bleood_album['id'],))
            db.execute('DELETE FROM album_musicians WHERE album_id = ?', (invalid_bleood_album['id'],))
            db.execute('DELETE FROM album_genres WHERE album_id = ?', (invalid_bleood_album['id'],))
            db.execute('DELETE FROM albums WHERE id = ?', (invalid_bleood_album['id'],))

        db.execute(
            'CREATE UNIQUE INDEX IF NOT EXISTS albums_musicbrainz_id ON albums (musicbrainz_id)'
        )
        db.execute(
            'CREATE UNIQUE INDEX IF NOT EXISTS musicians_musicbrainz_id ON musicians (musicbrainz_id)'
        )
        db.executemany(
            '''INSERT OR IGNORE INTO albums (id, title, artist, year, genre, art_class)
               VALUES (?, ?, ?, ?, ?, ?)''',
            ALBUMS,
        )
        db.executemany(
            'INSERT OR IGNORE INTO genres (id, name, slug) VALUES (?, ?, ?)',
            [(index, genre, GENRE_SLUGS[genre]) for index, genre in enumerate(GENRES, 1)],
        )
        db.executemany(
            'UPDATE albums SET genre = ? WHERE id = ?',
            [(album[4], album[0]) for album in ALBUMS],
        )
        db.executemany(
            'DELETE FROM album_genres WHERE album_id = ?',
            [(album_id,) for album_id in ALBUM_GENRES],
        )
        db.executemany(
            '''INSERT OR IGNORE INTO album_genres (album_id, genre_id)
               SELECT ?, id FROM genres WHERE name = ?''',
            [(album_id, genre) for album_id, genres in ALBUM_GENRES.items() for genre in genres],
        )
        db.executemany(
            'INSERT OR IGNORE INTO musicians (name, slug) VALUES (?, ?)',
            [(name, slug) for name, slug, _ in MUSICIANS],
        )
        db.executemany(
            '''DELETE FROM musician_genres
               WHERE musician_id = (SELECT id FROM musicians WHERE slug = ?)''',
            [(slug,) for _, slug, _ in MUSICIANS],
        )
        db.executemany(
            '''INSERT OR IGNORE INTO musician_genres (musician_id, genre_id)
               SELECT musicians.id, genres.id
               FROM musicians, genres
               WHERE musicians.slug = ? AND genres.name = ?''',
            [(slug, genre) for _, slug, genres in MUSICIANS for genre in genres],
        )
        db.executemany(
            '''INSERT OR IGNORE INTO album_musicians (album_id, musician_id)
               SELECT albums.id, musicians.id
               FROM albums, musicians
               WHERE albums.id = ? AND musicians.name = ?''',
            [(album[0], album[2]) for album in ALBUMS],
        )
        db.executemany(
            '''INSERT OR IGNORE INTO songs (musicbrainz_id, album_id, title, track_number)
               VALUES (?, ?, ?, ?)''',
            [(song_id, album_id, title, track_number)
             for album_id, song_id, title, track_number in SAMPLE_SONGS],
        )
        db.execute(
            "UPDATE musicians SET musicbrainz_id = ? WHERE slug = ? AND musicbrainz_id IS NULL",
            ('ce6a32ee-197d-4a59-9dad-37eb21b45c30', 'bleood'),
        )
        db.execute(
            "UPDATE musicians SET musicbrainz_id = ? WHERE slug = ? AND musicbrainz_id IS NULL",
            ('2baf3276-ed6a-4349-8d2e-f4601e7b2167', 'playboi-carti'),
        )
        db.execute(
            "UPDATE musicians SET musicbrainz_id = ? WHERE slug = ? AND musicbrainz_id IS NULL",
            ('164f0d73-1234-4e2c-8743-d77bf2191051', 'ye'),
        )
        db.execute(
            "UPDATE albums SET cover_url = ? WHERE id = 10",
            ('https://coverartarchive.org/release-group/f7479a73-66a7-41be-9f77-9e70828a5809/front-250',),
        )
        db.execute(
            "UPDATE albums SET cover_url = ?, musicbrainz_id = COALESCE(musicbrainz_id, ?) WHERE id = 11",
            ('https://coverartarchive.org/release-group/6448381d-9d98-4f84-b99d-733b6acde906/front-250',
             '6448381d-9d98-4f84-b99d-733b6acde906'),
        )
        db.execute(
            "UPDATE albums SET musicbrainz_id = ? WHERE id = 10 AND musicbrainz_id IS NULL",

            ('f7479a73-66a7-41be-9f77-9e70828a5809',),
        )
        db.execute(
            '''UPDATE musicians SET image_url = ?, image_source_url = ?, image_license = ?, image_license_url = ?, image_credit = ?
               WHERE slug = ?''',
            ('https://upload.wikimedia.org/wikipedia/commons/4/49/Bleood.jpg',
             'https://commons.wikimedia.org/wiki/File:Bleood.jpg', 'Public domain',
             'https://commons.wikimedia.org/wiki/Commons:Copyright_tags#Public_domain',
             'proxiser pro / Wikimedia Commons', 'bleood'),
        )
        db.execute(
            '''UPDATE musicians SET image_url = ?, image_source_url = ?, image_license = ?, image_license_url = ?, image_credit = ?
               WHERE slug = ?''',
            ('https://upload.wikimedia.org/wikipedia/commons/0/0f/Playboi_Carti%2C_Clout_Festival_2024_05_%28cropped%29.jpg',
             'https://commons.wikimedia.org/wiki/File:Playboi_Carti,_Clout_Festival_2024_05_(cropped).jpg',
             'CC BY 4.0', 'https://creativecommons.org/licenses/by/4.0/',
             'Wojciech Pędzich / Wikimedia Commons', 'playboi-carti'),
        )
        db.execute(
            '''UPDATE musicians SET image_url = ?, image_source_url = ?, image_license = ?, image_license_url = ?, image_credit = ?
               WHERE slug = ?''',
            ('https://upload.wikimedia.org/wikipedia/commons/1/10/Kanye_West_at_the_2009_Tribeca_Film_Festival_%28cropped%29.jpg',
             'https://commons.wikimedia.org/wiki/File:Kanye_West_at_the_2009_Tribeca_Film_Festival_(cropped).jpg',
             'CC BY-SA 3.0', 'https://creativecommons.org/licenses/by-sa/3.0/',
             'David Shankbone / Wikimedia Commons', 'ye'),
        )

def get_album_musicians(db, album_ids):
    album_ids = list(dict.fromkeys(album_ids))
    if not album_ids:
        return {}
    placeholders = ', '.join('?' for _ in album_ids)
    rows = db.execute(
        f'''SELECT album_musicians.album_id, musicians.*
            FROM album_musicians
            JOIN musicians ON musicians.id = album_musicians.musician_id
            WHERE album_musicians.album_id IN ({placeholders})
            ORDER BY musicians.name COLLATE NOCASE''',
        album_ids,
    ).fetchall()
    result = {album_id: [] for album_id in album_ids}
    for row in rows:
        result[row['album_id']].append(row)
    return result

def get_album_genres(db, album_ids):
    album_ids = list(dict.fromkeys(album_ids))
    if not album_ids:
        return {}
    placeholders = ', '.join('?' for _ in album_ids)
    rows = db.execute(
        f'''SELECT album_genres.album_id, genres.name
            FROM album_genres
            JOIN genres ON genres.id = album_genres.genre_id
            WHERE album_genres.album_id IN ({placeholders})
            ORDER BY genres.id''',
        album_ids,
    ).fetchall()
    result = {album_id: [] for album_id in album_ids}
    for row in rows:
        result[row['album_id']].append(row['name'])
    return result

def get_musician_genres(db, musician_ids):
    musician_ids = list(dict.fromkeys(musician_ids))
    if not musician_ids:
        return {}
    placeholders = ', '.join('?' for _ in musician_ids)
    rows = db.execute(
        f'''SELECT musician_genres.musician_id, genres.name
            FROM musician_genres
            JOIN genres ON genres.id = musician_genres.genre_id
            WHERE musician_genres.musician_id IN ({placeholders})
            ORDER BY genres.id''',
        musician_ids,
    ).fetchall()
    result = {musician_id: [] for musician_id in musician_ids}
    for row in rows:
        result[row['musician_id']].append(row['name'])
    return result

@app.context_processor
def current_account():
    user = None
    if session.get('user_id'):
        with get_db() as db:
            user = db.execute('SELECT id, username FROM users WHERE id = ?', (session['user_id'],)).fetchone()
    return {'current_user': user}


def normalize_catalog_name(value):
    return re.sub(r'[^a-z0-9]+', ' ', value.lower()).strip()


@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        password = request.form.get('password', '')
        genre_ids = [int(value) for value in request.form.getlist('genres') if value.isdigit()]
        if not (3 <= len(username) <= 30) or not (6 <= len(password) <= 128):
            flash('Choose a username of 3–30 characters and a password of at least 6 characters.', 'error')
        else:
            with get_db() as db:
                if db.execute('SELECT 1 FROM users WHERE lower(username) = lower(?)', (username,)).fetchone():
                    flash('That username is already taken.', 'error')
                else:
                    cursor = db.execute(
                        'INSERT INTO users (username, password_hash) VALUES (?, ?)',
                        (username, generate_password_hash(password)),
                    )
                    db.executemany(
                        'INSERT OR IGNORE INTO user_genres (user_id, genre_id) VALUES (?, ?)',
                        [(cursor.lastrowid, genre_id) for genre_id in genre_ids],
                    )
                    session['user_id'] = cursor.lastrowid
                    session['username'] = username
                    flash('Your Trackd account is ready.', 'success')
                    return redirect(url_for('account'))
    with get_db() as db:
        genres = db.execute('SELECT * FROM genres ORDER BY id').fetchall()
    return render_template('register.html', genres=genres)


@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        password = request.form.get('password', '')
        with get_db() as db:
            user = db.execute('SELECT * FROM users WHERE lower(username) = lower(?)', (username,)).fetchone()
        if user is None or not check_password_hash(user['password_hash'], password):
            flash('Incorrect username or password.', 'error')
        else:
            session['user_id'] = user['id']
            session['username'] = user['username']
            flash('Welcome back.', 'success')
            return redirect(url_for('account'))
    return render_template('login.html')


@app.route('/logout', methods=['POST'])
def logout():
    session.clear()
    flash('You have been logged out.', 'success')
    return redirect(url_for('index'))


@app.route('/account', methods=['GET', 'POST'])
def account():
    if not session.get('user_id'):
        return redirect(url_for('login'))
    with get_db() as db:
        user = db.execute('SELECT * FROM users WHERE id = ?', (session['user_id'],)).fetchone()
        genres = db.execute('SELECT * FROM genres ORDER BY id').fetchall()
        selected_ids = {row['genre_id'] for row in db.execute(
            'SELECT genre_id FROM user_genres WHERE user_id = ?', (user['id'],)
        ).fetchall()}
        if request.method == 'POST':
            genre_ids = [int(value) for value in request.form.getlist('genres') if value.isdigit()]
            db.execute('DELETE FROM user_genres WHERE user_id = ?', (user['id'],))
            db.executemany(
                'INSERT OR IGNORE INTO user_genres (user_id, genre_id) VALUES (?, ?)',
                [(user['id'], genre_id) for genre_id in genre_ids],
            )
            selected_ids = set(genre_ids)
            flash('Your music interests were updated.', 'success')
        recommendations = db.execute('''SELECT DISTINCT albums.* FROM albums
            JOIN album_genres ON album_genres.album_id = albums.id
            JOIN user_genres ON user_genres.genre_id = album_genres.genre_id
            WHERE user_genres.user_id = ?
            ORDER BY albums.year DESC, albums.title LIMIT 12''', (user['id'],)).fetchall()
    return render_template('account.html', user=user, genres=genres, selected_ids=selected_ids,
                           recommendations=recommendations)


@app.route('/moments')
def moments_index():
    category = request.args.get('category', '').strip()
    with get_db() as db:
        query = '''SELECT listening_moments.*, users.username,
                          albums.title AS album_title, albums.artist, albums.cover_url,
                          songs.title AS mvp_title
                   FROM listening_moments
                   JOIN users ON users.id = listening_moments.user_id
                   JOIN albums ON albums.id = listening_moments.album_id
                   LEFT JOIN songs ON songs.id = listening_moments.mvp_song_id'''
        params = []
        if category in MOMENT_CATEGORIES:
            query += ' WHERE listening_moments.category = ?'
            params.append(category)
        query += ' ORDER BY listening_moments.created_at DESC LIMIT 50'
        moments = db.execute(query, params).fetchall()
    return render_template('moments.html', moments=moments,
                           categories=MOMENT_CATEGORIES, active_category=category)


@app.route('/moments/new/<int:album_id>', methods=['POST'])
def create_moment(album_id):
    if not session.get('user_id'):
        flash('Log in to record a listening moment.', 'error')
        return redirect(url_for('login'))
    context = request.form.get('context', '').strip()
    custom_context = request.form.get('custom_context', '').strip()
    listen_type = request.form.get('listen_type', 'active')
    note = request.form.get('note', '').strip()
    mvp_song_id = request.form.get('mvp_song_id', type=int)
    category = request.form.get('category', 'Chilling').strip()
    context = custom_context or context
    if category not in MOMENT_CATEGORIES:
        flash('Choose a valid moment category.', 'error')
        return redirect(url_for('album_detail', album_id=album_id))
    if context not in ('Late-night highway drive', 'Cooking pasta alone',
                       'Crying in the kitchen', 'Working out') and len(context) > 80:
        flash('Keep your listening context under 80 characters.', 'error')
        return redirect(url_for('album_detail', album_id=album_id))
    if listen_type not in ('active', 'passive') or not context:
        flash('Choose a listen type and listening context.', 'error')
        return redirect(url_for('album_detail', album_id=album_id))
    with get_db() as db:
        album = db.execute('SELECT id FROM albums WHERE id = ?', (album_id,)).fetchone()
        if album is None:
            abort(404)
        if mvp_song_id:
            valid = db.execute('SELECT 1 FROM songs WHERE id = ? AND album_id = ?',
                               (mvp_song_id, album_id)).fetchone()
            if not valid:
                mvp_song_id = None
        db.execute('''INSERT INTO listening_moments
                      (user_id, album_id, mvp_song_id, listen_type, context, category, note)
                      VALUES (?, ?, ?, ?, ?, ?, ?)''',
                   (session['user_id'], album_id, mvp_song_id, listen_type, context, category, note[:240]))
    flash('Listening moment added.', 'success')
    return redirect(url_for('moments_index'))


@app.route('/preview/<int:song_id>')
def refresh_preview(song_id):
    with get_db() as db:
        song = db.execute('''SELECT songs.*, albums.artist FROM songs
                             JOIN albums ON albums.id = songs.album_id WHERE songs.id = ?''', (song_id,)).fetchone()
    if song is None:
        abort(404)
    query = urllib.parse.urlencode({'q': f'{song["title"]} {song["artist"]}', 'limit': 25})
    try:
        with urllib.request.urlopen('https://api.deezer.com/search?' + query, timeout=15) as response:
            results = json.loads(response.read()).get('data', [])
    except Exception:
        results = []
    wanted_title = normalize_catalog_name(song['title'])
    wanted_artist = normalize_catalog_name(song['artist'])
    preview = None
    for result in results:
        artist = normalize_catalog_name(result.get('artist', {}).get('name', ''))
        title = normalize_catalog_name(result.get('title', result.get('title_short', '')))
        if title == wanted_title and wanted_artist in artist:
            preview = result.get('preview')
            if preview:
                break
    if preview:
        with get_db() as db:
            db.execute('UPDATE songs SET preview_url = ? WHERE id = ?', (preview, song_id))
        return redirect(preview)
    abort(404)


@app.route('/')
def index():
    query = request.args.get('q', '').strip()
    with get_db() as db:
        preferred_genres = []
        if session.get('user_id'):
            preferred_genres = [row['name'] for row in db.execute('''SELECT genres.name
                FROM user_genres JOIN genres ON genres.id = user_genres.genre_id
                WHERE user_genres.user_id = ?''', (session['user_id'],)).fetchall()]
        preferred = {name.casefold() for name in preferred_genres}

        def chart_rank(row):
            try:
                return int(row['chart_rank'])
            except (TypeError, ValueError):
                return 9999

        album_rows = db.execute('''SELECT albums.*, COUNT(reviews.id) popularity
            FROM albums LEFT JOIN reviews ON reviews.album_id = albums.id
            WHERE lower(albums.release_type) = 'album' AND
                  (? = '' OR lower(albums.title) LIKE ? OR lower(albums.artist) LIKE ?)
            GROUP BY albums.id LIMIT 500''', ('', '', '')).fetchall() if not query else db.execute('''SELECT albums.*, COUNT(reviews.id) popularity
            FROM albums LEFT JOIN reviews ON reviews.album_id = albums.id
            WHERE lower(albums.release_type) = 'album' AND
                  (lower(albums.title) LIKE ? OR lower(albums.artist) LIKE ?)
            GROUP BY albums.id LIMIT 500''', (f'%{query.lower()}%', f'%{query.lower()}%')).fetchall()
        album_genres = get_album_genres(db, [row['id'] for row in album_rows])
        ranked_albums = sorted(album_rows, key=lambda row: (
            sum(name.casefold() in preferred for name in album_genres[row['id']]),
            -chart_rank(row), row['popularity'] or 0), reverse=True)
        albums = []
        artist_counts = {}
        for album in ranked_albums:
            artist_key = (album['artist'] or '').casefold().strip()
            if artist_counts.get(artist_key, 0) >= 2 and len(albums) < 12:
                continue
            albums.append(album)
            artist_counts[artist_key] = artist_counts.get(artist_key, 0) + 1
            if len(albums) == 12:
                break

        song_rows = db.execute('''SELECT songs.*, albums.title album_title, albums.artist, albums.cover_url,
            albums.year, COUNT(song_reviews.id) popularity
            FROM songs JOIN albums ON albums.id = songs.album_id
            LEFT JOIN song_reviews ON song_reviews.song_id = songs.id
            GROUP BY songs.id LIMIT 1000''').fetchall()
        song_album_genres = get_album_genres(db, [row['album_id'] for row in song_rows])
        ranked_songs = sorted(song_rows, key=lambda row: (
            sum(name.casefold() in preferred for name in song_album_genres[row['album_id']]),
            -chart_rank(row), row['popularity'] or 0), reverse=True)
        songs = []
        album_counts = {}
        for song in ranked_songs:
            album_key = song['album_id']
            if album_counts.get(album_key, 0) >= 2 and len(songs) < 12:
                continue
            songs.append(song)
            album_counts[album_key] = album_counts.get(album_key, 0) + 1
            if len(songs) == 12:
                break

        musician_rows = db.execute('''SELECT musicians.*, COUNT(DISTINCT reviews.id) popularity
            FROM musicians LEFT JOIN album_musicians ON album_musicians.musician_id = musicians.id
            LEFT JOIN reviews ON reviews.album_id = album_musicians.album_id
            GROUP BY musicians.id LIMIT 500''').fetchall()
        musician_genres = get_musician_genres(db, [row['id'] for row in musician_rows])
        musicians = sorted(musician_rows, key=lambda row: (
            sum(name.casefold() in preferred for name in musician_genres[row['id']]),
            -chart_rank(row), row['popularity'] or 0), reverse=True)[:12]

        genres = db.execute('SELECT * FROM genres ORDER BY id').fetchall()
        genres = sorted(genres, key=lambda row: (
            row['name'].casefold() in preferred,
            db.execute('SELECT COUNT(*) FROM album_genres WHERE genre_id=?', (row['id'],)).fetchone()[0]), reverse=True)[:10]

        recent = db.execute('''SELECT reviews.*, albums.title AS album_title, albums.artist,
            albums.art_class, albums.cover_url FROM reviews JOIN albums ON albums.id = reviews.album_id
            ORDER BY reviews.created_at DESC, reviews.id DESC LIMIT 12''').fetchall()
        album_review_genres = get_album_genres(db, [row['album_id'] for row in recent])
        recent.sort(key=lambda row: (sum(name.casefold() in preferred for name in album_review_genres[row['album_id']]),
                                     -row['id']), reverse=True)

        song_reviews = db.execute('''SELECT song_reviews.*, songs.title AS song_title, songs.preview_url,
            albums.id AS album_id, albums.title AS album_title, albums.artist FROM song_reviews
            JOIN songs ON songs.id=song_reviews.song_id JOIN albums ON albums.id=songs.album_id
            ORDER BY song_reviews.created_at DESC, song_reviews.id DESC LIMIT 12''').fetchall()
        song_review_genres = get_album_genres(db, [row['album_id'] for row in song_reviews])
        song_reviews.sort(key=lambda row: (sum(name.casefold() in preferred
            for name in song_review_genres[row['album_id']]), -row['id']), reverse=True)
        moments = db.execute('''SELECT listening_moments.*, users.username, albums.title album_title,
            albums.artist, albums.cover_url FROM listening_moments JOIN users ON users.id=listening_moments.user_id
            JOIN albums ON albums.id=listening_moments.album_id ORDER BY listening_moments.created_at DESC LIMIT 12''').fetchall()
        moment_genres = get_album_genres(db, [row['album_id'] for row in moments])
        moments.sort(key=lambda row: sum(name.casefold() in preferred for name in moment_genres[row['album_id']]), reverse=True)

        genres_by_album = album_genres
        genres_by_album.update(get_album_genres(db, [row['album_id'] for row in recent]))
        genres_by_musician = musician_genres
    return render_template('index.html', albums=albums, songs=songs, musicians=musicians,
        genres=genres, recent=recent, song_reviews=song_reviews, moments=moments,
        query=query, genres_by_album=genres_by_album,
        genres_by_musician=genres_by_musician, genre_slugs=GENRE_SLUGS,
        preferred_genres=preferred_genres, sort='trending')

@app.route('/reviews')
def reviews_index():
    return posts_index()


@app.route('/posts')
def posts_index():
    sort = get_sort(request.args.get('sort', '').strip(), default='trending')
    with get_db() as db:
        if sort == 'popular':
            order = 'ORDER BY reviews.rating DESC, reviews.id DESC'
        else:
            order = 'ORDER BY reviews.created_at DESC, reviews.id DESC'
        album_reviews = db.execute('''SELECT reviews.*, albums.id AS album_id, albums.title AS album_title,
                                             albums.artist, albums.cover_url, albums.art_class
                                      FROM reviews
                                      JOIN albums ON albums.id = reviews.album_id
                                      LIMIT 200''').fetchall()
        song_reviews = db.execute('''SELECT song_reviews.*, songs.id AS song_id, songs.title AS song_title,
                                            songs.album_id AS album_id, albums.title AS album_title,
                                            albums.artist, albums.cover_url, albums.art_class
                                     FROM song_reviews
                                     JOIN songs ON songs.id = song_reviews.song_id
                                     JOIN albums ON albums.id = songs.album_id
                                     LIMIT 200''').fetchall()

        reviews = []
        for review in album_reviews:
            reviews.append(dict(review, post_type='album'))
        for review in song_reviews:
            reviews.append(dict(review, post_type='song'))
        if sort == 'popular':
            reviews.sort(key=lambda review: (review['rating'], review['id']), reverse=True)
        else:
            reviews.sort(key=lambda review: (review['created_at'], review['id']), reverse=True)
        reviews = reviews[:200]
        genres_by_album = get_album_genres(db, [review['album_id'] for review in reviews])
    return render_template(
        'reviews.html', reviews=reviews, genres_by_album=genres_by_album,
        genre_slugs=GENRE_SLUGS, sort=sort,
    )


@app.route('/albums')
def albums_index():
    sort = get_sort(request.args.get('sort', '').strip())
    with get_db() as db:
        albums_query = '''SELECT albums.*, COALESCE(review_stats.review_count, 0) AS review_count,
                                 COALESCE(review_stats.average_rating, 0) AS average_rating,
                                 COALESCE(moment_stats.moment_count, 0) AS moment_count,
                                 COALESCE(review_stats.recent_count, 0) + COALESCE(moment_stats.recent_count, 0) AS recent_activity,
                                 COALESCE(review_stats.review_count, 0) + COALESCE(moment_stats.moment_count, 0) AS popularity
                          FROM albums
                          LEFT JOIN (SELECT album_id, COUNT(*) review_count, AVG(rating) average_rating,
                                            SUM(CASE WHEN created_at >= datetime('now', '-30 days') THEN 1 ELSE 0 END) recent_count
                                     FROM reviews GROUP BY album_id) review_stats ON review_stats.album_id = albums.id
                          LEFT JOIN (SELECT album_id, COUNT(*) moment_count,
                                            SUM(CASE WHEN created_at >= datetime('now', '-30 days') THEN 1 ELSE 0 END) recent_count
                                     FROM listening_moments GROUP BY album_id) moment_stats ON moment_stats.album_id = albums.id
                          WHERE lower(albums.release_type) = 'album' '''
        if sort == 'popular':
            albums_query += '''ORDER BY CASE WHEN albums.chart_rank IS NULL THEN 1 ELSE 0 END,
                               albums.chart_rank, popularity DESC, average_rating DESC,
                               title COLLATE NOCASE LIMIT 300'''
        elif sort == 'newest':
            albums_query += 'ORDER BY year DESC, title COLLATE NOCASE LIMIT 300'
        else:
            albums_query += '''ORDER BY CASE WHEN recent_activity > 0 THEN 0 ELSE 1 END,
                               CASE WHEN albums.chart_rank IS NULL THEN 1 ELSE 0 END,
                               albums.chart_rank, recent_activity DESC, popularity DESC,
                               year DESC, title COLLATE NOCASE LIMIT 300'''
        albums = db.execute(albums_query).fetchall()
        genres_by_album = get_album_genres(db, [album['id'] for album in albums])
        recent = db.execute('''SELECT reviews.*, albums.title AS album_title,
                              albums.art_class AS art_class FROM reviews
                              JOIN albums ON albums.id = reviews.album_id
                              ORDER BY reviews.id DESC LIMIT 4''').fetchall()
    return render_template(
        'index.html', albums=albums, recent=recent, query='',
        genres_by_album=genres_by_album, genre_slugs=GENRE_SLUGS,
        sort=sort,
    )

@app.route('/genres')
def genres_index():
    with get_db() as db:
        genres = db.execute(
            '''SELECT genres.name, genres.slug,
                      (SELECT COUNT(*) FROM album_genres WHERE album_genres.genre_id = genres.id) AS album_count,
                      (SELECT COUNT(*) FROM musician_genres WHERE musician_genres.genre_id = genres.id) AS musician_count,
                      (SELECT COUNT(*) FROM songs
                       JOIN albums ON albums.id = songs.album_id
                       JOIN album_genres ON album_genres.album_id = albums.id
                       WHERE album_genres.genre_id = genres.id) AS song_count
               FROM genres
               ORDER BY genres.id'''
        ).fetchall()
    return render_template('genres.html', genres=genres)

@app.route('/musicians')
def musicians_index():
    sort = get_sort(request.args.get('sort', '').strip())
    with get_db() as db:
        musicians_query = '''SELECT musicians.*, COALESCE(activity.review_count, 0) AS review_count,
                                    COALESCE(activity.moment_count, 0) AS moment_count,
                                    COALESCE(activity.recent_activity, 0) AS recent_activity,
                                    COALESCE(activity.review_count, 0) + COALESCE(activity.moment_count, 0) AS popularity
                             FROM musicians
                             LEFT JOIN (
                               SELECT album_musicians.musician_id,
                                      COUNT(DISTINCT reviews.id) review_count,
                                      COUNT(DISTINCT listening_moments.id) moment_count,
                                      SUM(CASE WHEN reviews.created_at >= datetime('now', '-30 days') THEN 1 ELSE 0 END)
                                      + SUM(CASE WHEN listening_moments.created_at >= datetime('now', '-30 days') THEN 1 ELSE 0 END) recent_activity
                               FROM album_musicians
                               LEFT JOIN reviews ON reviews.album_id = album_musicians.album_id
                               LEFT JOIN listening_moments ON listening_moments.album_id = album_musicians.album_id
                               GROUP BY album_musicians.musician_id
                             ) activity ON activity.musician_id = musicians.id '''
        if sort == 'popular':
            musicians_query += '''ORDER BY CASE WHEN musicians.chart_rank IS NULL THEN 1 ELSE 0 END,
                                  musicians.chart_rank, popularity DESC,
                                  musicians.name COLLATE NOCASE LIMIT 300'''
        elif sort == 'newest':
            musicians_query += 'ORDER BY musicians.id DESC, musicians.name COLLATE NOCASE LIMIT 300'
        else:
            musicians_query += '''ORDER BY CASE WHEN recent_activity > 0 THEN 0 ELSE 1 END,
                                  CASE WHEN musicians.chart_rank IS NULL THEN 1 ELSE 0 END,
                                  musicians.chart_rank, recent_activity DESC, popularity DESC,
                                  musicians.name COLLATE NOCASE LIMIT 300'''
        musicians = db.execute(musicians_query).fetchall()
        genres_by_musician = get_musician_genres(
            db, [musician['id'] for musician in musicians]
        )
    return render_template(
        'musicians.html',
        musicians=musicians,
        genres_by_musician=genres_by_musician,
        genre_slugs=GENRE_SLUGS,
        sort=sort,
    )

@app.route('/musicians/<slug>')
def musician_detail(slug):
    with get_db() as db:
        musician = db.execute('SELECT * FROM musicians WHERE slug = ?', (slug,)).fetchone()
        if musician is None:
            abort(404)
        genres = get_musician_genres(db, [musician['id']])[musician['id']]
        albums = db.execute(
            '''SELECT albums.* FROM albums
               JOIN album_musicians ON album_musicians.album_id = albums.id
               WHERE album_musicians.musician_id = ?
                 AND lower(albums.release_type) = 'album'
               ORDER BY year DESC, title''',
            (musician['id'],),
        ).fetchall()
        album_genres = get_album_genres(db, [album['id'] for album in albums])
        songs = db.execute(
            '''SELECT songs.*, albums.title AS album_title FROM songs
               JOIN albums ON albums.id = songs.album_id
               JOIN album_musicians ON album_musicians.album_id = albums.id
               WHERE album_musicians.musician_id = ?
               ORDER BY albums.year DESC, songs.track_number LIMIT 60''',
            (musician['id'],),
        ).fetchall()
    return render_template(
        'musician.html',
        musician=musician,
        genres=genres,
        albums=albums,
        album_genres=album_genres,
        songs=songs,
        genre_slugs=GENRE_SLUGS,
    )

@app.route('/songs')
def songs_index():
    query = request.args.get('q', '').strip()
    sort = get_sort(request.args.get('sort', '').strip())
    try:
        page = max(1, int(request.args.get('page', '1')))
    except ValueError:
        page = 1
    page_size = 50
    with get_db() as db:
        where = ''
        parameters = []
        if query:
            where = 'WHERE songs.title LIKE ? OR albums.title LIKE ? OR albums.artist LIKE ?'
            term = f'%{query}%'
            parameters.extend((term, term, term))
        total = db.execute(
            f'''SELECT COUNT(*) FROM songs
                JOIN albums ON albums.id = songs.album_id {where}''',
            parameters,
        ).fetchone()[0]
        if sort == 'popular':
            song_order = '''CASE WHEN songs.chart_rank IS NULL THEN 1 ELSE 0 END,
                            songs.chart_rank,
                            COALESCE(song_activity.mvp_count, 0) DESC,
                            COALESCE(album_activity.review_count, 0) DESC,
                            albums.artist COLLATE NOCASE, songs.title COLLATE NOCASE'''
        elif sort == 'newest':
            song_order = '''albums.year DESC, albums.title COLLATE NOCASE, songs.track_number'''
        else:
            song_order = '''CASE WHEN COALESCE(song_activity.recent_mvp_count, 0) > 0 OR COALESCE(album_activity.recent_activity, 0) > 0 THEN 0 ELSE 1 END,
                            CASE WHEN songs.chart_rank IS NULL THEN 1 ELSE 0 END,
                            songs.chart_rank,
                            COALESCE(song_activity.recent_mvp_count, 0) DESC,
                            COALESCE(album_activity.recent_activity, 0) DESC,
                            albums.artist COLLATE NOCASE, songs.title COLLATE NOCASE'''
        songs = db.execute(
            f'''SELECT songs.*, albums.title AS album_title, albums.artist, albums.year, albums.cover_url,
                       COALESCE(song_activity.mvp_count, 0) AS mvp_count,
                       COALESCE(album_activity.popularity, 0) AS album_popularity
                FROM songs JOIN albums ON albums.id = songs.album_id
                LEFT JOIN (SELECT mvp_song_id, COUNT(*) mvp_count,
                                  SUM(CASE WHEN created_at >= datetime('now', '-30 days') THEN 1 ELSE 0 END) recent_mvp_count
                           FROM listening_moments WHERE mvp_song_id IS NOT NULL GROUP BY mvp_song_id) song_activity
                  ON song_activity.mvp_song_id = songs.id
                LEFT JOIN (SELECT reviews.album_id,
                                  COUNT(reviews.id) review_count,
                                  COUNT(reviews.id) + COUNT(listening_moments.id) popularity,
                                  SUM(CASE WHEN reviews.created_at >= datetime('now', '-30 days') THEN 1 ELSE 0 END)
                                  + SUM(CASE WHEN listening_moments.created_at >= datetime('now', '-30 days') THEN 1 ELSE 0 END) recent_activity
                           FROM reviews LEFT JOIN listening_moments ON listening_moments.album_id = reviews.album_id
                           GROUP BY reviews.album_id) album_activity ON album_activity.album_id = albums.id
                {where}
                ORDER BY {song_order}
                LIMIT ? OFFSET ?''',
            [*parameters, page_size, (page - 1) * page_size],
        ).fetchall()
        genres_by_album = get_album_genres(db, [song['album_id'] for song in songs])
        musicians_by_album = get_album_musicians(db, [song['album_id'] for song in songs])
    return render_template(
        'songs.html',
        songs=songs,
        query=query,
        page=page,
        page_count=max(1, (total + page_size - 1) // page_size),
        genres_by_album=genres_by_album,
        musicians_by_album=musicians_by_album,
        genre_slugs=GENRE_SLUGS,
        sort=sort,
    )

@app.route('/song/<int:song_id>')
def song_detail(song_id):
    with get_db() as db:
        song = db.execute(
            '''SELECT songs.*, albums.title AS album_title, albums.artist, albums.year,
                      albums.release_type, albums.cover_url,
                      albums.id AS album_id
               FROM songs JOIN albums ON albums.id = songs.album_id
               WHERE songs.id = ?''',
            (song_id,),
        ).fetchone()
        if song is None:
            abort(404)
        genres = get_album_genres(db, [song['album_id']])[song['album_id']]
        musicians = get_album_musicians(db, [song['album_id']])[song['album_id']]
    return render_template(
        'song.html',
        song=song,
        genres=genres,
        musicians=musicians,
        genre_slugs=GENRE_SLUGS,
    )

@app.route('/genres/<slug>')
def genre_detail(slug):
    with get_db() as db:
        genre = db.execute('SELECT * FROM genres WHERE slug = ?', (slug,)).fetchone()
        if genre is None:
            abort(404)
        albums = db.execute(
            '''SELECT albums.* FROM albums
               JOIN album_genres ON album_genres.album_id = albums.id
               WHERE album_genres.genre_id = ?
               ORDER BY albums.title''',
            (genre['id'],),
        ).fetchall()
        genres_by_album = get_album_genres(db, [album['id'] for album in albums])
        musicians = db.execute(
            '''SELECT musicians.* FROM musicians
               JOIN musician_genres ON musician_genres.musician_id = musicians.id
               WHERE musician_genres.genre_id = ?
               ORDER BY musicians.name COLLATE NOCASE''',
            (genre['id'],),
        ).fetchall()
        genres_by_musician = get_musician_genres(
            db, [musician['id'] for musician in musicians]
        )
        songs = db.execute(
            '''SELECT songs.*, albums.title AS album_title, albums.artist FROM songs
               JOIN albums ON albums.id = songs.album_id
               JOIN album_genres ON album_genres.album_id = albums.id
               WHERE album_genres.genre_id = ?
               ORDER BY albums.artist COLLATE NOCASE, albums.title, songs.track_number
               LIMIT 60''',
            (genre['id'],),
        ).fetchall()
        song_count = db.execute(
               '''SELECT COUNT(*) FROM songs
                  JOIN albums ON albums.id = songs.album_id
                  JOIN album_genres ON album_genres.album_id = albums.id
                  WHERE album_genres.genre_id = ?''',
               (genre['id'],),
        ).fetchone()[0]
    return render_template(
        'genre.html',
        genre=genre,
        albums=albums,
        genres_by_album=genres_by_album,
        musicians=musicians,
        genres_by_musician=genres_by_musician,
        songs=songs,
        song_count=song_count,
        genre_slugs=GENRE_SLUGS,
    )

@app.route('/coming-soon/<section>')
def coming_soon(section):
    title = COMING_SOON_SECTIONS.get(section)
    if title is None:
        abort(404)
    return render_template('coming_soon.html', section=title)

@app.route('/album/<int:album_id>', methods=['GET', 'POST'])
def album_detail(album_id):
    with get_db() as db:
        album = db.execute('SELECT * FROM albums WHERE id = ?', (album_id,)).fetchone()
        if album is None:
            abort(404)
        if request.method == 'POST':
            name = request.form.get('name', '').strip()
            body = request.form.get('review', '').strip()
            try:
                rating = float(request.form.get('rating', ''))
            except ValueError:
                rating = 0
            category = request.form.get('category', 'Chilling').strip()
            if not (1 <= len(name) <= 40 and 1 <= len(body) <= 1000 and rating in [x / 2 for x in range(1, 11)] and category in MOMENT_CATEGORIES):
                flash('Enter a name, review, half-star rating, and valid listening category.', 'error')
            else:
                db.execute('''INSERT INTO reviews (album_id, display_name, rating, review_text, category)
                              VALUES (?, ?, ?, ?, ?)''', (album_id, name, rating, body, category))
                db.commit()
                flash('Your review was saved on this computer!', 'success')
                return redirect(url_for('album_detail', album_id=album_id))
        reviews = db.execute('SELECT * FROM reviews WHERE album_id = ? ORDER BY id DESC', (album_id,)).fetchall()
        average = db.execute('SELECT ROUND(AVG(rating), 1) FROM reviews WHERE album_id = ?', (album_id,)).fetchone()[0]
        genres = get_album_genres(db, [album_id])[album_id]
        musicians = get_album_musicians(db, [album_id])[album_id]
        tracks = db.execute(
            'SELECT * FROM songs WHERE album_id = ? ORDER BY track_number',
            (album_id,),
        ).fetchall()
    return render_template(
        'album.html',
        album=album,
        reviews=reviews,
        average=average,
        genres=genres,
        musicians=musicians,
        tracks=tracks,
        genre_slugs=GENRE_SLUGS,
        moment_categories=MOMENT_CATEGORIES,
    )

init_db()

if __name__ == '__main__':
    app.run(debug=True)
