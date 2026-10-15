# Built-in App modules — first implementation

Date: 2026-10-15. Scope: per-user management of trusted Apps shipped with FocusFlow. This stage is not a marketplace, remote installer, third-party runtime or process sandbox.

## Product boundary

Identity, Home, Settings and Workspace/Project remain platform Core. Core includes local Project Task and Note workflows; disabling the standalone Notes App does not remove project notes or the owner-scoped Core export/search APIs. Google Tasks is a separate optional App, not the Core Task store.

Optional App IDs: notes, tasks, calendar, drive, music, money, chat, quiz. The catalog lives in services/module_service.py. Entries describe integrations but do not grant credentials or imply provider readiness. Modules ship in the existing modular monolith; enabling an App does not download code or configure Google/iCloud/Firebase automatically.

## User workflow

Home → 管理 App (or Settings) → 我的 App 模組. Toggle an optional App. Preferences are stored per authenticated/guest identity and reload with that identity across devices. Existing users default to all Apps enabled. Core entries cannot be disabled. Disabled App cards/sidebar links and Calendar mobile destination disappear; Home/Settings/Core remain reachable. Re-enable to resume using preserved data.

No uninstall or destructive-data option is offered. External provider authorization is retained until separately revoked. An unavailable preference API shows retry feedback; failed saves restore the original choice. Existing active requests are not retroactively cancelled. Another device must refresh its UI; server requests still check the current preference. Existing Chat subscriptions are rechecked at the existing 30-second session interval and close when disabled.

## Implementation

GET /api/modules returns the owner's catalog. PATCH /api/modules/{id} accepts only a strict boolean enabled field. Session-derived ownership; caller cannot select another owner. Unknown IDs return 404, Core disable returns 409, invalid payloads 422. Updates use SQLite upsert under the existing transaction boundary. Guest sign-in migration preserves existing signed-in preferences and transfers only non-conflicting guest choices.

Router dependencies reject disabled App HTTP requests (403) and Chat WebSocket handshakes (4403). This is a feature-availability boundary, not a substitute for each router's ownership/provider checks or a third-party permission sandbox. File download/Core APIs retain their existing owner checks. Already-authorized shared-file/Core access is independent of standalone App visibility.

Notes/Money/Keep no longer start requests when Home loads. App data loads on entry after preferences resolve. Keep's optional QR library loads on entry. The unused global YouTube iframe API bootstrap was removed; the existing Music audio functionality is retained. Disabling Music pauses local audio; disabling Keep closes the local socket. Light/dark settings label state was corrected and unsupported Notification APIs no longer stop Settings initialization.

## Migration / rollback

0005_module_preferences adds module_preferences(user_email, module_id, enabled) only. It does not backfill/alter existing domain rows. Old revisions continue to use default-enabled behavior after migration. 0004 → 0005 and schema/model parity are tested on isolated SQLite. Downgrade is allowed only while the new table is empty; once preferences exist, use a verified backup or keep the additive table while rolling back app behavior, rather than silently discarding choices.

Backup verification supports both known 0004 and 0005 revisions, verifies new preference columns for 0005, and copies preference rows using the same SQLite Backup API. Production rollout must update host backup helpers too, otherwise an old verifier will reject 0005 snapshots. Before rollout: verified live backup → isolated copy migration → compare existing rows → maintenance cutover → migration/preflight → health and UI checks. A failed cutover must restore the matching DB/image pair from the verified checkpoint.

## Roadmap after this stage

1. Observe built-in module use, provider configuration gaps and discoverability.
2. Define versioned manifests and trusted package compatibility/migration contracts; evaluate packaging using real needs.
3. Only then design download/update/install transactions, explicit permission scopes and trust/isolation for third-party extensions. Do not execute arbitrary downloaded Python under the app identity.

## Verification

See tests/test_modules.py (owner isolation, Core protection, strict payloads, data preservation, disabled router/WebSocket rejection, guest preference merge), migration/backup regressions and tests/browser_core.py (real isolated browser workflow). Browser security regression continues to cover desktop/mobile App panels and injection boundaries. Real iPhone keyboard behavior is still pending. 79 pytest tests passed (386 existing-style deprecation warnings). JavaScript syntax checks, real isolated browser Core/module workflow and mocked nine-panel desktop/mobile regression passed; git diff --check passed. Migration tests cover old row preservation, empty preference-table downgrade and refusal to discard saved preferences; backup tests preserve disabled choices across snapshots. Deployment results will be recorded after execution.


## HomeCloud rollout — 2026-10-15

Release `0de1d0d` deployed after an isolated migration of a production snapshot. All 15 pre-existing non-revision tables compared equal before/after; new preference table empty. Production migration to 0005 passed preflight/integrity/FK checks. Cutover snapshot retained privately as `focusflow-20261015-pre-modules.db`, with pre-module image `focusflow-icons:19c4763` available for a matched rollback. No restore was required.

A post-upgrade snapshot and Windows copy both passed SQLite/SHA256 verification; root disk remained 57% used. Live HTTPS health and unauthenticated module entry were checked. One networkidle-based browser navigation timed out; a subsequent DOM-loaded check reached the manager with no JavaScript errors. User-authenticated toggle behavior was tested in isolated real SQLite/browser E2E, not with the owner's production credentials. A follow-up includes shared module visibility CSS on the Workspace page, covered by cross-page E2E.


Final deployed application checkpoint: `bba3f83` (`focusflow-modules:bba3f83`, also `focusflow-focusflow:latest`). Cross-page Calendar visibility passed the real isolated E2E. Live desktop/mobile management entry passed with no eager Notes/Money/Chat/Music requests, JavaScript errors or horizontal overflow. Production schema preflight passed; no owner credentials were used for automated UI testing.
