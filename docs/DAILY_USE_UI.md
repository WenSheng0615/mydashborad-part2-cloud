# Daily-use interface update

Branch: `fix/daily-use-interface`, based on `v0.2.0-homecloud-foundation`.

## Current status — 2026-10-15

Deployed application checkpoint: `19c4763`. Desktop retains its original layout; desktop/mobile share graphite/teal dark tokens. Mobile has three destinations: Home, Workspace, Calendar. The 2026-10-13 icon uses a teal F on graphite; Apple touch (180) and manifest PNGs (192/512) were verified over HTTPS.

Private owner-scoped iCloud CalDAV authenticated successfully on 2026-10-13 and returned three events for that month. Only read-only retrieval was verified; no claim of write support or complete recurrence/device coverage. The white/blue theme and the complete redesigned App surfaces/mini-player remain standalone prototypes.

Real-device iPhone keyboard, Safari toolbar and safe-area verification is still pending. Browser regression uses Chromium with isolated/mocked data; it does not replace real Google consent or iPhone testing.

The following initial implementation notes are historical; where they differ, this dated status takes precedence.

## Initial changes
- Mobile dock: Workspace, Notes, Calendar, All Apps. Home remains scrollable.
- Dynamic viewport and safe-area padding protect navigation from mobile browser chrome.
- Local FocusFlow vector logo and PNG icons (192/512/180 px); Apple touch icon.
- Homepage hierarchy, shared spacing, focus styles and reduced-motion support.
- Music cover click / Enter / Space toggles the existing audio player; this is not video playback.
- Calendar counts, clearer today marker, source labels, non-overlapping event actions.
- Month navigation avoids January 31 overflow; stale network responses cannot overwrite a newer month.
- Google and optional iCloud requests are isolated; failures are shown per source.

## Private iCloud setup (deployment owner only)
Read-only CalDAV integration; no database migration and no credentials stored in the browser.
In the server private environment file set:

```
ICLOUD_OWNER_EMAIL=<exact signed-in FocusFlow email>
ICLOUD_USERNAME=<Apple account email>
ICLOUD_APP_PASSWORD=<Apple app-specific password>
```

Never commit this file or paste the password into chat. Use an Apple app-specific password, not the primary account password. See https://support.apple.com/en-us/102654 .

Rebuild the application image to install the pinned CalDAV dependency, then recreate the application container to load the environment. Preserve data and Redis volumes. Other FocusFlow users receive no iCloud events. Unconfigured integration makes no external request. Each CalDAV request has a 15-second timeout; accounts with many calendars may take longer overall. No background synchronization, cache, or iCloud write operations are introduced.

## Verification / remaining gates
- 65 Python tests passed (308 existing-style deprecation warnings).
- Mocked browser coverage: 9 panels at desktop/mobile widths; four-item mobile dock, workspace clearance, Home access, month overflow, cover mouse/keyboard controls and existing injection checks.
- Real Apple authentication, recurrence behavior against iCloud, real-device safe areas and production deployment remain unverified.
- The reported need to switch pages has not been reproduced in these isolated browser tests; do not claim it fixed without reproducing the affected screen.
- Existing Google endpoint reads the primary Google calendar; iCloud reads the account calendars. No cross-provider deduplication or two-way synchronization.
- New icons may require removing and re-adding an existing home-screen shortcut.


## Workspace / Today redesign
- Shared FocusFlow logo, surface colors, rounded controls and a clearer search/header hierarchy.
- Empty accounts see a three-step introduction and one primary action instead of four zero counters.
- Existing workspace without projects prompts project creation; archived projects are preserved with a restore hint.
- Populated Today uses summary cards and a two-column task layout on wide screens.
- Mobile workspace navigation is collapsible, keyboard-closeable, and keeps content visible first.
- Isolated real SQLite browser workflow passed including mobile navigation and workspace-to-project onboarding. No production database or deployment changed.


## Music system media information — 2026-10-17

The audio player now publishes Media Session title, author/channel, FocusFlow Music album label and cover artwork when the resolved track is selected. The existing stream extraction returns channel/uploader metadata too, so history entries need no extra provider lookup. Missing/unsafe cover URLs use the shipped local app icon. A request sequence prevents delayed old stream responses from replacing the selected track, system metadata or spinner state. Play/pause and bounded seeking update the system session; supported previous/next actions use the existing queue. Unsupported actions/APIs cannot block playback.

Browser regression uses an isolated recorded Media Session and controlled audio events/provider responses: metadata, artwork, missing cover/author, stale responses, seeking boundaries, pause/resume and unsupported API paths. It does not prove physical iPhone lock-screen rendering or background longevity; owner acceptance should reload the site/PWA, play a song, lock the phone, check title/cover, then switch tracks and check controls. The system owns layout and available buttons. No database migration or background-playback guarantee is introduced.


## Full playlist loading — 2026-10-17

Playlist-item API responses now expose next_page_token and accept the provider page token (50 items per request). The player follows every page automatically with progress feedback, preserves provider order and repeated video entries, and replaces the playback queue only after the complete list loads. Page errors/timeouts show retry feedback instead of a silently truncated playlist; closing/changing the view invalidates stale requests. Rows without a provider video ID cannot be played and are skipped. No hard 50-song display limit is retained. Search results, history limits and the separate list of owned playlists are unchanged.

Validation: mocked 237-song/five-page browser workflow, final-track selection, page-two failure/retry and cancelled-response isolation; API page-token forwarding, empty last page, safe provider errors and authentication. No live private playlist is modified; owner verification of the real playlist remains manual. No schema migration.


## Seeking and background transitions — 2026-10-17

Stream extraction prefers direct HTTPS M4A/AAC before other available formats, remains read-only, and runs in FastAPI's worker thread rather than blocking the event loop during next-track preparation. It returns expiry/format metadata with no-store caching. No server-side media download/cache or range proxy was added; seeking beyond buffered data still depends on the upstream URL's range support, codec and network throughput. M4A selection is a compatibility improvement, not proof that every source supports arbitrary seeking.

The player prepares only the next track's signed URL (not media bytes) while the current track plays, stores at most three resolved URLs in this page's memory, checks expiry and refreshes near track end. Pending lookups are shared and failed warm-ups have a cooldown. Shuffle plans one stable next choice. A ready next URL reaches audio.play() synchronously from ended/media controls, removing the previous required fetch before play. Browsing search/history/playlists does not replace the active playback queue; selecting a row does.

Scrubbing previews time while dragging and commits a single seek on release/change. Waiting/seeking/error states pause Media Session progress reporting; playing restores it, preventing the app's supplied system position from extrapolating while buffering. The UI reports loading/failure. Unsupported browser APIs remain optional.

Regression tests use recorded Media Session and controlled media events/provider responses: synchronous prepared-track transition, preparation before ended, expired URL eviction, scrub preview/commit, waiting-to-playing states and existing metadata/pagination scenarios. The real yt-dlp selector is tested against HTTPS M4A, HLS M4A and higher-bitrate WebM with fallback. Physical iPhone background continuation, upstream Range behavior and long-duration locked-screen playback remain owner acceptance checks. iOS may still suspend JavaScript/network or reject automatic playback; no silent-audio workaround, native-background guarantee or new infrastructure is claimed.


## Playlist loading presentation — 2026-10-18

Provider page counters are no longer exposed in the Music UI. A stable five-row skeleton with a single loading announcement represents pending playlist data; aria-busy marks the list and reduced-motion disables the pulse. Completion shows only the final song count; failure uses a dedicated empty-state card with retry and preservation guidance, without partial page numbers. Full pagination, ordering, cancellation, active queue preservation and retry behavior are unchanged. Browser regression and mobile/desktop loading/error/ready screenshot review cover this increment.
