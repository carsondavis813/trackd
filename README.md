# Trackd — Flask starter

A local MVP of a Letterboxd-style music website. Search sample albums, post half-star ratings and reviews, browse ten genres and 30 musicians, and see recent activity. Run the optional catalog sync to import album/track metadata from MusicBrainz and artist photos from Wikimedia Commons when a reuse-compatible license and attribution are available. Albums and tracks inherit the listed musician genres. Data is stored in `trackd.db`; existing reviews are preserved.

**Windows (Command Prompt):**

1. Install Python 3.11+ from https://www.python.org/downloads/ and VS Code from https://code.visualstudio.com/.
2. Extract this zip, open Command Prompt in the extracted `trackd_starter` folder.
3. Run:

```bat
py -3 -m venv .venv
.venv\Scripts\activate.bat
python -m pip install -r requirements.txt
python -m flask --app app run --debug
```

4. Open http://127.0.0.1:5000 in your browser.
5. Press `Ctrl+C` in Command Prompt to stop the server.

On subsequent runs, open Command Prompt in the project folder and run `.venv\Scripts\activate.bat` and `python -m flask --app app run --debug`.

**Import albums, songs, and reusable artist photos (optional):**

With the virtual environment active and an internet connection, run:

```bat
set TRACKD_CONTACT_EMAIL=you@example.com
python catalog_sync.py
```

The importer checks exact artist-name matches, imports album, EP, and single release groups with their tracklists, and uses Wikimedia Commons photos only when a reuse-compatible license and attribution are available. It leaves a generated initials avatar when no suitable photo is found. The import is incremental and can take a long time because MusicBrainz limits request rates; it is safe to run again. To import one musician, pass their profile slug, for example `python catalog_sync.py --musician travis-scott`. Set `TRACKD_CONTACT_EMAIL` to a contact address so MusicBrainz can identify the client. A failed upstream request is reported and does not erase existing catalog data.

For a broader local catalog refresh, `python deezer_catalog_sync.py` matches each listed musician against Deezer, imports available album/EP/single releases, release artwork, tracklists, durations, artist images, and 30-second preview links. The import is additive and preserves reviews and existing records. External service availability and catalog completeness may vary.

The imported catalog is available at `/songs`; album pages show tracklists, and musician profiles show their imported albums, songs, photo credits, and genre tags.

**Files:**
- `app.py`: Flask routes, database setup, seeded catalog, review saving.
- `templates/base.html`: shared header/footer.
- `templates/index.html`: homepage, search, album grid, review feed.
- `templates/album.html`: album detail/review form.
- `templates/genres.html` and `templates/genre.html`: genre directory and genre-filtered albums.
- `templates/musicians.html` and `templates/musician.html`: musician directory and profiles.
- `templates/songs.html` and `templates/song.html`: song browser and track pages.
- `catalog_sync.py`: optional MusicBrainz and Wikimedia Commons catalog importer.
- `templates/coming_soon.html`: placeholder for sections not built yet.
- `static/style.css`, `static/genres.css`, `static/musicians.css`, and `static/catalog.css`: visual design.
- `requirements.txt`: Python dependencies.

**Important:** Development-only. Official release cover artwork is shown from the Cover Art Archive when available; unreleased or unverified catalog entries should not be added. The sample bleood album was removed because it is not an officially released DSP album. There are **no user accounts, moderation, or CSRF protections** yet. Never deploy this directly to the public internet. The album cover graphics are CSS placeholders; song and album metadata comes from MusicBrainz when imported. Don't run the Flask debugger on a public server.
