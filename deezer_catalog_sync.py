import json
import re
import time
import unicodedata
import urllib.parse
import urllib.request

from app import get_db

API = 'https://api.deezer.com'


def normalize(value):
    value = unicodedata.normalize('NFKD', value).encode('ascii', 'ignore').decode()
    return ' '.join(re.findall(r'[a-z0-9]+', value.lower()))


def api_get(path):
    url = API + path
    for attempt in range(5):
        try:
            request = urllib.request.Request(url, headers={'User-Agent': 'Trackd/1.0 local-development'})
            with urllib.request.urlopen(request, timeout=30) as response:
                return json.loads(response.read())
        except Exception:
            if attempt == 4:
                raise
            time.sleep(2 * (attempt + 1))


def find_artist(name):
    data = api_get('/search/artist?' + urllib.parse.urlencode({'q': name, 'limit': 25}))
    wanted = normalize(name)
    aliases = {wanted}
    if wanted == 'destroy lonely':
        aliases.add('destory lonely')
    if wanted == 'young thug':
        aliases.add('thugger')
    for candidate in data.get('data', []):
        if normalize(candidate.get('name', '')) in aliases:
            return candidate
    for candidate in data.get('data', []):
        if normalize(candidate.get('name', '')).replace('.', '') == wanted.replace('.', ''):
            return candidate
    return None


def pages(path, limit=100):
    results = []
    next_path = path + ('&' if '?' in path else '?') + urllib.parse.urlencode({'limit': limit})
    while next_path and len(results) < 1000:
        data = api_get(next_path)
        results.extend(data.get('data', []))
        next_path = data.get('next')
        if next_path:
            next_path = next_path.replace(API, '')
        if len(data.get('data', [])) < limit:
            break
    return results


def sync_artist(db, musician, artist):
    artist_id = artist['id']
    db.execute(
        '''UPDATE musicians SET image_url = COALESCE(image_url, ?),
           image_source_url = COALESCE(image_source_url, ?) WHERE id = ?''',
        (artist.get('picture_xl') or artist.get('picture_big'),
         f'https://www.deezer.com/artist/{artist_id}', musician['id']),
    )
    albums = pages(f'/artist/{artist_id}/albums')
    added_albums = 0
    added_songs = 0
    for release in albums:
        release_type = release.get('record_type') or 'album'
        if release_type == 'compile':
            continue
        title = release.get('title', '').strip()
        if not title:
            continue
        details = api_get('/album/' + str(release['id']))
        date = details.get('release_date', '')
        year = int(date[:4]) if re.match(r'^\d{4}', date or '') else 0
        row = db.execute(
            'SELECT id FROM albums WHERE title = ? AND artist = ? LIMIT 1',
            (title, musician['name']),
        ).fetchone()
        if row:
            album_id = row['id']
            db.execute(
                '''UPDATE albums SET year = CASE WHEN year = 0 THEN ? ELSE year END,
                   cover_url = COALESCE(cover_url, ?), release_type = COALESCE(release_type, ?) WHERE id = ?''',
                (year, details.get('cover_xl') or details.get('cover_big'), release_type.capitalize(), album_id),
            )
        else:
            cursor = db.execute(
                '''INSERT INTO albums
                   (title, artist, year, genre, art_class, release_type, cover_url)
                   VALUES (?, ?, ?, ?, 'art-imported', ?, ?)''',
                (title, musician['name'], year, 'Hip-hop', release_type.capitalize(),
                 details.get('cover_xl') or details.get('cover_big')),
            )
            album_id = cursor.lastrowid
            added_albums += 1
        db.execute('INSERT OR IGNORE INTO album_musicians (album_id, musician_id) VALUES (?, ?)',
                   (album_id, musician['id']))
        db.execute(
            '''INSERT OR IGNORE INTO album_genres (album_id, genre_id)
               SELECT ?, genre_id FROM musician_genres WHERE musician_id = ?''',
            (album_id, musician['id']),
        )
        db.execute(
            '''UPDATE albums SET genre = (
               SELECT genres.name FROM album_genres JOIN genres ON genres.id = album_genres.genre_id
               WHERE album_genres.album_id = albums.id ORDER BY genres.id LIMIT 1) WHERE id = ?''',
            (album_id,),
        )
        for position, track in enumerate(details.get('tracks', {}).get('data', []), 1):
            result = db.execute(
                'SELECT id FROM songs WHERE album_id = ? AND title = ? LIMIT 1',
                (album_id, track['title']),
            ).fetchone()
            duration_ms = int(track.get('duration', 0) * 1000) or None
            preview = track.get('preview') or None
            if result:
                db.execute(
                    '''UPDATE songs SET track_number = ?, length_ms = COALESCE(length_ms, ?),
                       preview_url = COALESCE(preview_url, ?) WHERE id = ?''',
                    (position, duration_ms, preview, result['id']),
                )
            else:
                db.execute(
                    '''INSERT INTO songs (musicbrainz_id, album_id, title, track_number, length_ms, preview_url)
                           VALUES (?, ?, ?, ?, ?, ?)''',
                        (f'deezer:{musician["slug"]}:album:{release["id"]}:track:{position}', album_id, track['title'], position, duration_ms, preview),
                )
                added_songs += 1
        time.sleep(0.05)
    return added_albums, added_songs


def main():
    totals = [0, 0]
    errors = []
    with get_db() as db:
        musicians = db.execute('SELECT id, name, slug FROM musicians ORDER BY name COLLATE NOCASE').fetchall()
        for musician in musicians:
            try:
                artist = find_artist(musician['name'])
                if not artist:
                    errors.append(f'{musician["name"]}: no exact Deezer artist match')
                    print(f'ERROR {musician["name"]}: no exact Deezer artist match')
                    continue
                print(f'Syncing {musician["name"]} (Deezer {artist["id"]}) ...', flush=True)
                added = sync_artist(db, musician, artist)
                totals[0] += added[0]
                totals[1] += added[1]
                db.commit()
            except Exception as error:
                db.rollback()
                errors.append(f'{musician["name"]}: {error}')
                print(f'ERROR {musician["name"]}: {error}', flush=True)
    print(f'Deezer catalog sync finished: {totals[0]} albums and {totals[1]} songs added.')
    if errors:
        print('Skipped/errors:')
        for error in errors:
            print(error)


if __name__ == '__main__':
    main()
