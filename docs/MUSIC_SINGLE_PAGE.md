# Mobile music single-page layout — 2026-10-18

## Scope
- Mobile (up to 768px): search, current track, then a single library viewport.
- Playlists remain rows; history opens from the header and returns to the previous section.
- Search accepts keywords and YouTube links. Clearing returns to the library.
- Returning from search/history retains an open playlist and its scroll position.
- Existing full-player sheet, gestures, playback queue and single audio element are retained.
- Desktop keeps its player and Search / Playlists / History tabs.
- No database, credentials, provider API or playback transport changes.

## Validation
- pytest: 106 passed; existing deprecations retained. A unique temporary base directory was needed because the default Windows pytest temp directory was inaccessible.
- browser_core.py: isolated SQLite guest workflow passed.
- browser_security.py: mocked APIs, no account writes; search/history/clear, 237-song pagination, queue controls, sheet gestures, 320/390/393px clipping, search/player order through 768px and desktop restoration passed; no JavaScript errors.
- JavaScript syntax and git diff whitespace checks passed.
- Physical iPhone background audio / OS return destination remains a manual check; the reported NTUB return issue is not claimed fixed by this layout change.
