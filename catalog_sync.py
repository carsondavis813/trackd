import argparse
import html
import json
import os
import re
import sys
import time
import unicodedata
import urllib.error
import urllib.parse
import urllib.request

from app import GENRES, MUSICIANS, get_db


MUSICBRAINZ_API = 'https://musicbrainz.org/ws/2'
COMMONS_API = 'https://commons.wikimedia.org/w/api.php'
REQUEST_TIMEOUT = 30


class CatalogSyncError(Exception):
    pass


class JsonApi:
    def __init__(self, user_agent, minimum_interval=1.1):
        self.user_agent = user_agent
        self.minimum_interval = minimum_interval
        self.last_request = 0.0

    def get(self, url):
        for attempt in range(5):
            wait = self.minimum_interval - (time.monotonic() - self.last_request)
            if wait > 0:
                time.sleep(wait)
            request = urllib.request.Request(
                url,
                headers={
                    'Accept': 'application/json',
                    'User-Agent': self.user_agent,
                },
            )
            try:
                with urllib.request.urlopen(request, timeout=REQUEST_TIMEOUT) as response:
                    body = response.read()
                break
            except urllib.error.HTTPError as error:
                self.last_request = time.monotonic()
                if error.code in (429, 503, 502) and attempt < 4:
                    time.sleep(5 * (attempt + 1))
                    continue
                raise CatalogSyncError(f'API request failed for {url}: {error}') from error
            except (urllib.error.URLError, TimeoutError) as error:
                self.last_request = time.monotonic()
                if attempt < 4:
                    time.sleep(5 * (attempt + 1))
                    continue
                raise CatalogSyncError(f'API request failed for {url}: {error}') from error
            finally:
                self.last_request = time.monotonic()
        try:
            return json.loads(body)
        except (UnicodeDecodeError, json.JSONDecodeError) as error:
            raise CatalogSyncError(f'API returned invalid JSON for {url}: {error}') from error


def normalize_name(value):
    value = unicodedata.normalize('NFKD', value).encode('ascii', 'ignore').decode()
    return ' '.join(re.findall(r'[a-z0-9]+', value.lower()))


def find_musicbrainz_artist(api, name):
    query = urllib.parse.urlencode({
        'query': f'artist:"{name}"',
        'fmt': 'json',
        'limit': 25,
    })
    data = api.get(f'{MUSICBRAINZ_API}/artist/?{query}')
    exact_matches = [
        artist for artist in data.get('artists', [])
        if normalize_name(artist.get('name', '')) == normalize_name(name)
    ]
    if len(exact_matches) != 1:
        match_type = 'no' if not exact_matches else 'multiple'
        raise CatalogSyncError(
            f'{match_type} exact MusicBrainz matches for "{name}"; skipped to avoid importing the wrong artist.'
        )
    return exact_matches[0]


def musicbrainz_release_groups(api, artist_id):
    release_groups = []
    offset = 0
    while True:
        query = urllib.parse.urlencode({
            'artist': artist_id,
            'type': 'album|ep|single',
            'fmt': 'json',
            'limit': 100,
            'offset': offset,
        })
        data = api.get(f'{MUSICBRAINZ_API}/release-group?{query}')
        batch = data.get('release-groups', [])
        release_groups.extend(batch)
        offset += len(batch)
        if not batch or offset >= data.get('release-group-count', 0):
            return release_groups


def choose_release(releases):
    candidates = []
    for release in releases:
        media = release.get('media', [])
        tracks = [
            track
            for medium in media
            for track in medium.get('tracks', [])
            if track.get('id') and track.get('title')
        ]
        if not tracks:
            continue
        sort_key = (
            release.get('status') != 'Official',
            release.get('country') != 'US',
            release.get('date', '9999'),
            release.get('id', ''),
        )
        candidates.append((sort_key, tracks))
    if not candidates:
        return []
    return min(candidates, key=lambda candidate: candidate[0])[1]


def musicbrainz_tracks(api, release_group_id):
    query = urllib.parse.urlencode({
        'release-group': release_group_id,
        'fmt': 'json',
        'limit': 100,
        'inc': 'recordings',
    })
    data = api.get(f'{MUSICBRAINZ_API}/release/?{query}')
    releases = sorted(
        data.get('releases', []),
        key=lambda release: (
            release.get('status') != 'Official',
            release.get('country') != 'US',
            release.get('date', '9999'),
            release.get('id', ''),
        ),
    )
    return choose_release(releases)


def clean_metadata(value):
    return html.unescape(re.sub(r'<[^>]+>', '', value or '')).strip()


def allowed_license(metadata):
    license_id = metadata.get('License', {}).get('value', '').lower()
    short_name = metadata.get('LicenseShortName', {}).get('value', '')
    license_url = metadata.get('LicenseUrl', {}).get('value', '')
    reusable = (
        license_id == 'cc0'
        or license_id.startswith('cc-by-')
        or license_id.startswith('cc-by-sa-')
        or license_id.startswith('pd-')
        or short_name.lower() in ('public domain', 'cc0')
    )
    if not reusable or not license_url:
        return None
    return short_name, license_url


def find_commons_photo(api, name):
    search = urllib.parse.urlencode({
        'action': 'query',
        'generator': 'search',
        'gsrsearch': f'filetype:bitmap "{name}"',
        'gsrnamespace': 6,
        'gsrlimit': 10,
        'prop': 'imageinfo',
        'iiprop': 'url|extmetadata',
        'iiurlwidth': 480,
        'format': 'json',
    })
    data = api.get(f'{COMMONS_API}?{search}')
    pages = data.get('query', {}).get('pages', {}).values()
    normalized_name = normalize_name(name)
    forbidden_terms = ('logo', 'album cover', 'single cover', 'poster', 'artwork')
    for page in sorted(pages, key=lambda item: item.get('index', 999)):
        if any(term in page.get('title', '').lower() for term in forbidden_terms):
            continue
        image_info = (page.get('imageinfo') or [{}])[0]
        metadata = image_info.get('extmetadata', {})
        license_info = allowed_license(metadata)
        if license_info is None:
            continue
        description = ' '.join((
            page.get('title', ''),
            clean_metadata(metadata.get('ImageDescription', {}).get('value', '')),
        ))
        if normalized_name not in normalize_name(description):
            continue
        credit = clean_metadata(
            metadata.get('Artist', {}).get('value')
            or metadata.get('Credit', {}).get('value')
        )
        if not credit or not image_info.get('thumburl') or not image_info.get('descriptionurl'):
            continue
        return {
            'image_url': image_info['thumburl'],
            'image_source_url': image_info.get('descriptionurl', ''),
            'image_license': license_info[0],
            'image_license_url': license_info[1],
            'image_credit': credit,
        }
    return None


def upsert_artist_metadata(db, musician, artist):
    db.execute(
        'UPDATE musicians SET musicbrainz_id = ? WHERE id = ?',
        (artist['id'], musician['id']),
    )


def add_release_group(db, musician, release_group, tracks):
    year_match = re.match(r'\d{4}', release_group.get('first-release-date', ''))
    year = int(year_match.group()) if year_match else 0
    title = release_group.get('title', '').strip()
    if not title:
        return False
    existing = db.execute(
        'SELECT id FROM albums WHERE musicbrainz_id = ?',
        (release_group['id'],),
    ).fetchone()
    if existing is None:
        existing = db.execute(
            '''SELECT id FROM albums
               WHERE title = ? AND artist = ? AND year = ? LIMIT 1''',
            (title, musician['name'], year),
        ).fetchone()
    if existing is None:
        release_type = release_group.get('primary-type') or 'Album'
        cover_url = f'https://coverartarchive.org/release-group/{release_group["id"]}/front-250'
        cursor = db.execute(
            '''INSERT INTO albums
               (title, artist, year, genre, art_class, musicbrainz_id, release_type, cover_url)
               VALUES (?, ?, ?, ?, 'art-imported', ?, ?, ?)''',
            (
                title, musician['name'], year, GENRES[0],
                release_group['id'], release_type, cover_url,
            ),
        )
        album_id = cursor.lastrowid
    else:
        album_id = existing['id']
        cover_url = f'https://coverartarchive.org/release-group/{release_group["id"]}/front-250'
        db.execute(
            '''UPDATE albums SET musicbrainz_id = COALESCE(musicbrainz_id, ?),
               cover_url = COALESCE(cover_url, ?) WHERE id = ?''',
            (release_group['id'], cover_url, album_id),
        )
    db.execute(
        'INSERT OR IGNORE INTO album_musicians (album_id, musician_id) VALUES (?, ?)',
        (album_id, musician['id']),
    )
    db.execute(
        '''INSERT OR IGNORE INTO album_genres (album_id, genre_id)
           SELECT ?, genre_id FROM musician_genres WHERE musician_id = ?''',
        (album_id, musician['id']),
    )
    db.execute(
        '''UPDATE albums SET genre = (
               SELECT genres.name FROM album_genres
               JOIN genres ON genres.id = album_genres.genre_id
               WHERE album_genres.album_id = albums.id
               ORDER BY genres.id LIMIT 1
           ) WHERE id = ?''',
        (album_id,),
    )
    for track in tracks:
        recording = track.get('recording') or {}
        length = track.get('length') or recording.get('length')
        position = track.get('position')
        if not position:
            number_match = re.search(r'\d+', str(track.get('number', '')))
            position = int(number_match.group()) if number_match else 0
        db.execute(
            '''INSERT OR IGNORE INTO songs
               (musicbrainz_id, album_id, title, track_number, length_ms)
               VALUES (?, ?, ?, ?, ?)''',
            (
                track['id'],
                album_id,
                track['title'].strip(),
                int(position),
                int(length) if length else None,
            ),
        )
    return True


def sync_musician(api, musician):
    with get_db() as db:
        current = db.execute(
            'SELECT * FROM musicians WHERE id = ?', (musician['id'],)
        ).fetchone()
    if current is None:
        raise CatalogSyncError(f'Musician {musician["name"]} is not in the local catalog.')
    artist = find_musicbrainz_artist(api, musician['name'])
    groups = musicbrainz_release_groups(api, artist['id'])
    added = 0
    for release_group in groups:
        with get_db() as db:
            existing = db.execute(
                'SELECT id FROM albums WHERE musicbrainz_id = ?',
                (release_group['id'],),
            ).fetchone()
            if existing is not None and db.execute(
                'SELECT 1 FROM songs WHERE album_id = ? LIMIT 1',
                (existing['id'],),
            ).fetchone():
                continue
        tracks = musicbrainz_tracks(api, release_group['id'])
        with get_db() as db:
            add_release_group(db, current, release_group, tracks)
            upsert_artist_metadata(db, current, artist)
            added += len(tracks)
    with get_db() as db:
        db.execute(
            'UPDATE musicians SET musicbrainz_id = ? WHERE id = ?',
            (artist['id'], current['id']),
        )
    return added


def sync_photo(api, musician):
    with get_db() as db:
        current = db.execute(
            'SELECT * FROM musicians WHERE id = ?', (musician['id'],)
        ).fetchone()
    if current['image_url']:
        return False
    photo = find_commons_photo(api, musician['name'])
    if photo is None:
        print(f'No reuse-licensed Commons photo found for {musician["name"]}.')
        return False
    with get_db() as db:
        db.execute(
            '''UPDATE musicians SET image_url = ?, image_source_url = ?,
               image_license = ?, image_license_url = ?, image_credit = ?
               WHERE id = ?''',
            (
                photo['image_url'],
                photo['image_source_url'],
                photo['image_license'],
                photo['image_license_url'],
                photo['image_credit'],
                musician['id'],
            ),
        )
    return True


def sync_catalog(selected_slug=None):
    contact = os.environ.get('TRACKD_CONTACT_EMAIL')
    if not contact:
        raise CatalogSyncError(
            'Set TRACKD_CONTACT_EMAIL to a contact address before making MusicBrainz requests.'
        )
    musicbrainz = JsonApi(f'Trackd/1.0 ({contact})', minimum_interval=1.1)
    commons = JsonApi('Trackd/1.0 (local development)', minimum_interval=0.2)
    selected = [
        item for item in MUSICIANS
        if selected_slug is None or item[1] == selected_slug
    ]
    if not selected:
        raise CatalogSyncError(f'Unknown musician slug: {selected_slug}')
    errors = []
    total_tracks = 0
    photo_count = 0
    with get_db() as db:
        rows = db.execute('SELECT id, name, slug FROM musicians').fetchall()
    local_by_slug = {row['slug']: row for row in rows}
    for name, slug, _ in selected:
        musician = local_by_slug.get(slug)
        if musician is None:
            errors.append(f'{name}: missing local musician record')
            continue
        print(f'Syncing {name} ...', flush=True)
        try:
            total_tracks += sync_musician(musicbrainz, musician)
        except CatalogSyncError as error:
            errors.append(f'{name}: {error}')
            print(f'ERROR {name}: {error}', file=sys.stderr, flush=True)
        try:
            photo_count += sync_photo(commons, musician)
        except CatalogSyncError as error:
            errors.append(f'{name} photo: {error}')
            print(f'ERROR {name} photo: {error}', file=sys.stderr, flush=True)
    print(f'Catalog sync finished: {total_tracks} tracks added, {photo_count} photos added.')
    if errors:
        raise CatalogSyncError(
            f'{len(errors)} item(s) failed or were skipped; see the messages above.'
        )


def main():
    parser = argparse.ArgumentParser(
        description='Import MusicBrainz albums/tracks and licensed Commons artist photos.'
    )
    parser.add_argument(
        '--musician',
        help='Sync one musician by local slug instead of the full catalog.',
    )
    args = parser.parse_args()
    try:
        sync_catalog(args.musician)
    except CatalogSyncError as error:
        parser.exit(1, f'Catalog sync failed: {error}\n')


if __name__ == '__main__':
    main()
