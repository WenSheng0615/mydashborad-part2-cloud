# Daily-use interface update

Branch: `fix/daily-use-interface`, based on `v0.2.0-homecloud-foundation`.

## Changes
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
