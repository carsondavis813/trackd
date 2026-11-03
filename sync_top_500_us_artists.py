import json
import sqlite3
import time
import urllib.request
from deezer_catalog_sync import api_get, find_artist, sync_artist, get_db

APPLE_GENRES = (20, 21, 18, 6, 17, 12, 13, 15, 16, 24, 26, 5, 7, 8, 14, 115)


def discover_apple_artists(names, limit=500):
    urls = ['https://itunes.apple.com/us/rss/topsongs/limit=200/json']
    urls.extend(f'https://itunes.apple.com/us/rss/topsongs/limit=200/genre={genre}/json' for genre in APPLE_GENRES)
    for url in urls:
        if len(names) >= limit:
            break
        try:
            request = urllib.request.Request(url, headers={'User-Agent': 'Trackd/1.0 local-development'})
            with urllib.request.urlopen(request, timeout=30) as response:
                feed = json.loads(response.read()).get('feed', {})
            for item in feed.get('entry', []):
                artist = item.get('im:artist', {}).get('label', '').strip()
                if artist and artist not in names:
                    names[artist] = len(names) + 1
                if len(names) >= limit:
                    break
        except Exception as error:
            print(f'Apple chart discovery skipped {url}: {error}')


DISCOVERY_GENRES = (
    132, 116, 122, 152, 113, 165, 85, 186, 106, 466, 144, 129, 84, 464, 169,
    153, 197, 67, 65, 98, 173, 2, 16, 75, 71, 81, 95,
)


def discover_artists(limit=100):
    names = {}

    def add(rows, rank_base=0):
        for rank, artist in enumerate(rows, rank_base + 1):
            name = (artist.get('name') or '').strip()
            if name and name not in names:
                names[name] = rank

    add(api_get('/chart/0/artists?' + 'limit=100').get('data', []))
    add(api_get('/chart/0/tracks?' + 'limit=300').get('data', []))
    # Music chart endpoints above return track objects rather than artist objects.
    if len(names) < limit:
        for track in api_get('/chart/0/tracks?' + 'limit=300').get('data', []):
            artist = track.get('artist') or {}
            add([artist], len(names))

    for genre_id in DISCOVERY_GENRES:
        if len(names) >= limit:
            break
        try:
            data = api_get(f'/genre/{genre_id}/artists?limit=100').get('data', [])
            add(data, len(names))
        except Exception as error:
            print(f'Genre {genre_id} discovery skipped: {error}')

    discover_apple_artists(names, limit)
    return list(names)[:limit]


def ensure_musician(db, name):
    row = db.execute('SELECT id, name, slug FROM musicians WHERE lower(name) = lower(?)', (name,)).fetchone()
    if row:
        return row
    artist = find_artist(name)
    if not artist:
        return None
    official_name = artist['name'].strip()
    slug = '-'.join(''.join(c.lower() if c.isalnum() else ' ' for c in official_name).split())
    base_slug = slug
    suffix = 2
    while db.execute('SELECT 1 FROM musicians WHERE slug = ?', (slug,)).fetchone():
        slug = f'{base_slug}-{suffix}'
        suffix += 1
    cursor = db.execute(
        '''INSERT INTO musicians (name, slug, image_url, image_source_url, image_license, image_credit)
           VALUES (?, ?, ?, ?, ?, ?)''',
        (official_name, slug, artist.get('picture_xl') or artist.get('picture_big'),
         f'https://www.deezer.com/artist/{artist["id"]}', 'Deezer artist image', 'Deezer'),
    )
    if db.execute('SELECT 1 FROM genres WHERE name = ?', ('Pop',)).fetchone():
        db.execute('''INSERT OR IGNORE INTO musician_genres (musician_id, genre_id)
                      SELECT ?, id FROM genres WHERE name = ?''', (cursor.lastrowid, 'Pop'))
    return db.execute('SELECT id, name, slug FROM musicians WHERE id = ?', (cursor.lastrowid,)).fetchone()


def normalize_release_types(db):
    ep_markers = ('ep', 'remix', 'remixes', 'expanded edition')
    for album in db.execute('SELECT id, title, release_type FROM albums').fetchall():
        tracks = db.execute('SELECT COUNT(*) FROM songs WHERE album_id = ?', (album['id'],)).fetchone()[0]
        title = (album['title'] or '').lower()
        release_type = (album['release_type'] or '').strip().lower()
        if release_type in ('ep', 'eps') or any(marker in title for marker in ep_markers):
            normalized = 'EP'
        elif release_type in ('single', 'singles'):
            normalized = 'Single'
        elif tracks == 1:
            normalized = 'Single'
        elif tracks <= 6:
            normalized = 'EP'
        else:
            normalized = 'Album'
        db.execute('UPDATE albums SET release_type = ? WHERE id = ?', (normalized, album['id']))


def main():
    names = discover_artists(100)
    with get_db() as db:
        existing_names = {row['name'].casefold() for row in db.execute('SELECT name FROM musicians')}
    names = [name for name in names if name.casefold() not in existing_names]
    # A fast pass is enough for the site: new chart artists and a compact official discography.
    names = names[:35]
    print(f'Discovered {len(names)} new US-chart artists (existing artists skipped); starting fast pass.', flush=True)
    added = synced = 0
    with get_db() as db:
        for name in names:
            try:
                musician = ensure_musician(db, name)
                if musician is None:
                    print(f'SKIP {name}: no verified Deezer profile match')
                    continue
                existing = db.execute('SELECT 1 FROM albums JOIN album_musicians ON album_musicians.album_id = albums.id WHERE album_musicians.musician_id = ?', (musician['id'],)).fetchone()
                if not existing:
                    added += 1
                artist = find_artist(musician['name'])
                if artist:
                    sync_artist(db, musician, artist)
                    synced += 1
                db.commit()
                print(f'OK {musician["name"]}')
                time.sleep(0.05)
            except Exception as error:
                db.rollback()
                print(f'ERROR {name}: {error}')
        normalize_release_types(db)
        db.commit()
    print(f'Catalog sync finished: {added} new profiles and {synced} profiles synced.')


if __name__ == '__main__':
    main()
