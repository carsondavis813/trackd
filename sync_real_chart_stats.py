import json
import re
import sqlite3
import unicodedata
import urllib.request
import urllib.parse
from datetime import datetime, timezone
from pathlib import Path

DB_PATH = Path(__file__).resolve().parent / 'trackd.db'


def normalize(value):
    value = unicodedata.normalize('NFKD', value).encode('ascii', 'ignore').decode()
    return ' '.join(re.findall(r'[a-z0-9]+', value.lower()))


def chart(category, limit=100):
    url = f'https://api.deezer.com/chart/0/{category}?limit={limit}'
    request = urllib.request.Request(url, headers={'User-Agent': 'Trackd/1.0 local-development'})
    with urllib.request.urlopen(request, timeout=30) as response:
        return json.loads(response.read()).get('data', [])[:limit]


def api(path):
    url = 'https://api.deezer.com' + path
    request = urllib.request.Request(url, headers={'User-Agent': 'Trackd/1.0 local-development'})
    with urllib.request.urlopen(request, timeout=30) as response:
        return json.loads(response.read())


def slug(value):
    return '-'.join(re.findall(r'[a-z0-9]+', value.lower()))


def ensure_musician(db, artist):
    name = artist.get('name', '').strip()
    if not name:
        return None
    row = db.execute('SELECT id FROM musicians WHERE lower(name) = lower(?)', (name,)).fetchone()
    if row:
        return row['id']
    artist_slug = slug(name)
    unique_slug = artist_slug
    suffix = 2
    while db.execute('SELECT 1 FROM musicians WHERE slug = ?', (unique_slug,)).fetchone():
        unique_slug = f'{artist_slug}-{suffix}'
        suffix += 1
    cursor = db.execute('''INSERT INTO musicians (name, slug, image_url, image_source_url, image_credit)
                           VALUES (?, ?, ?, ?, 'Deezer')''',
                        (name, unique_slug, artist.get('picture_xl') or artist.get('picture_big'),
                         f"https://www.deezer.com/artist/{artist.get('id', '')}"))
    return cursor.lastrowid


def ensure_album(db, details, fallback_artist):
    title = details.get('title', '').strip()
    artist = details.get('artist') or fallback_artist
    artist_name = artist.get('name', '').strip()
    if not title or not artist_name:
        return None, None
    musician_id = ensure_musician(db, artist)
    row = db.execute('SELECT id FROM albums WHERE lower(title) = lower(?) AND lower(artist) = lower(?) LIMIT 1',
                     (title, artist_name)).fetchone()
    release_type = (details.get('record_type') or 'album').lower()
    release_type = {'album': 'Album', 'ep': 'EP', 'single': 'Single'}.get(release_type, 'Album')
    date = details.get('release_date', '')
    year_match = re.match(r'\d{4}', date or '')
    year = int(year_match.group()) if year_match else 0
    if row:
        album_id = row['id']
        db.execute('''UPDATE albums SET cover_url = COALESCE(cover_url, ?),
                       year = CASE WHEN year = 0 THEN ? ELSE year END,
                       release_type = CASE WHEN release_type IS NULL OR release_type = 'Album' THEN ? ELSE release_type END
                       WHERE id = ?''', (details.get('cover_xl') or details.get('cover_big'), year, release_type, album_id))
    else:
        cursor = db.execute('''INSERT INTO albums (title, artist, year, genre, art_class, release_type, cover_url)
                               VALUES (?, ?, ?, 'Pop', 'art-imported', ?, ?)''',
                            (title, artist_name, year, release_type,
                             details.get('cover_xl') or details.get('cover_big')))
        album_id = cursor.lastrowid
    db.execute('INSERT OR IGNORE INTO album_musicians (album_id, musician_id) VALUES (?, ?)',
               (album_id, musician_id))
    tracks = details.get('tracks', {}).get('data', [])
    for position, track in enumerate(tracks, 1):
        track_title = track.get('title', '').strip()
        if not track_title:
            continue
        existing = db.execute('SELECT id FROM songs WHERE album_id = ? AND lower(title) = lower(?) LIMIT 1',
                              (album_id, track_title)).fetchone()
        preview = track.get('preview') or None
        if existing:
            db.execute('''UPDATE songs SET track_number = ?, length_ms = COALESCE(length_ms, ?),
                          preview_url = COALESCE(preview_url, ?) WHERE id = ?''',
                       (position, int(track.get('duration', 0) * 1000) or None, preview, existing['id']))
        else:
            deezer_id = track.get('id')
            db.execute('''INSERT INTO songs
                          (musicbrainz_id, album_id, title, track_number, length_ms, preview_url)
                          VALUES (?, ?, ?, ?, ?, ?)''',
                       (f'deezer-track-{deezer_id}' if deezer_id else f'deezer-chart-{album_id}-{position}',
                        album_id, track_title, position,
                        int(track.get('duration', 0) * 1000) or None, preview))
    return album_id, musician_id


with sqlite3.connect(DB_PATH) as db:
    db.row_factory = sqlite3.Row
    updated_at = datetime.now(timezone.utc).isoformat(timespec='seconds')

    imported_albums = imported_songs = 0
    try:
        top_tracks = chart('tracks', 100)
        for chart_track in top_tracks:
            try:
                track = api('/track/' + str(chart_track['id']))
                album_ref = track.get('album') or chart_track.get('album')
                if album_ref and album_ref.get('id'):
                    details = api('/album/' + str(album_ref['id']))
                    before = db.execute('SELECT COUNT(*) FROM albums').fetchone()[0]
                    ensure_album(db, details, track.get('artist') or chart_track.get('artist'))
                    imported_albums += db.execute('SELECT COUNT(*) FROM albums').fetchone()[0] > before
            except Exception as error:
                print(f"Skipped track {chart_track.get('title')}: {error}")
        db.commit()
    except Exception as error:
        print(f'Song chart import skipped: {error}')

    for chart_album in chart('albums', 100):
        try:
            ensure_album(db, api('/album/' + str(chart_album['id'])), chart_album.get('artist'))
        except Exception as error:
            print(f"Skipped album {chart_album.get('title')}: {error}")
    db.commit()

    db.execute('UPDATE albums SET chart_rank = NULL, chart_rank_updated_at = NULL')
    db.execute('UPDATE songs SET chart_rank = NULL, chart_rank_updated_at = NULL')
    db.execute('UPDATE musicians SET chart_rank = NULL, chart_rank_updated_at = NULL')

    album_rows = db.execute("SELECT id, title, artist FROM albums WHERE lower(release_type) = 'album'").fetchall()
    album_matches = {(normalize(row['title']), normalize(row['artist'])): row['id'] for row in album_rows}
    album_rank = 0
    for position, release in enumerate(chart('albums'), 1):
        key = (normalize(release.get('title', '')), normalize(release.get('artist', {}).get('name', '')))
        album_id = album_matches.get(key)
        if album_id:
            album_rank += 1
            db.execute('UPDATE albums SET chart_rank = ?, chart_rank_updated_at = ? WHERE id = ?',
                       (position, updated_at, album_id))

    track_matches = {}
    for row in db.execute('''SELECT songs.id, songs.title, albums.artist
                             FROM songs JOIN albums ON albums.id = songs.album_id'''):
        track_matches.setdefault((normalize(row['title']), normalize(row['artist'])), []).append(row['id'])
    song_rank = 0
    for position, track in enumerate(chart('tracks'), 1):
        key = (normalize(track.get('title', track.get('title_short', ''))),
               normalize(track.get('artist', {}).get('name', '')))
        for song_id in track_matches.get(key, [])[:1]:
            song_rank += 1
            db.execute('UPDATE songs SET chart_rank = ?, chart_rank_updated_at = ? WHERE id = ?',
                       (position, updated_at, song_id))

    musician_matches = {normalize(row['name']): row['id'] for row in db.execute('SELECT id, name FROM musicians')}
    artist_rank = 0
    for position, artist in enumerate(chart('artists'), 1):
        musician_id = musician_matches.get(normalize(artist.get('name', '')))
        if musician_id:
            artist_rank += 1
            db.execute('UPDATE musicians SET chart_rank = ?, chart_rank_updated_at = ? WHERE id = ?',
                       (position, updated_at, musician_id))

    db.commit()

print(f'Real Deezer chart rankings saved: {album_rank} albums, {song_rank} songs, {artist_rank} musicians.')
