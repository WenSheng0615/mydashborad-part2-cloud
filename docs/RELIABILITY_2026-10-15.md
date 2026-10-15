# Reliability closure evidence — 2026-10-15

## Result

Private HTTPS and both containers were healthy during maintenance. The VM had rebooted and acquired 192.168.46.131; the previous LAN address was no longer valid. No app restart was needed.

## Storage

Root disk: 19 GB; before 86% used / 2.5 GB available; after 57% used / 7.7 GB available. Explicitly removed obsolete mobile/pre-mobile image tags and unused builder cache. Retained running release 19c4763 and previous palette release 5134925 for rollback. Docker volumes, live data, credential files and user backups were preserved.

## Network mitigation

Earlier incident evidence: vmnat.exe crashed twice near Modern Standby transitions; guest could reach host adapter but not NAT gateway. Current session HTTPS works. Changed AC lid action to Do nothing in the current Windows power plan, verified with powercfg. No VM network mode change or virtual network reset. NAT crash root cause remains unproven and recurrence requires observation; intentional host sleep/reboot still interrupts hosting.

## Backup corrections

Found a zero-byte final snapshot despite prior service-success status. Its historical failure cause could not be reconstructed. Replaced the host scheduled wrapper with flock + private staging + existing SQLite backup API/verification + atomic no-overwrite final publication. Old wrapper saved privately on host. Monitor selects verified snapshots.

Manual snapshots and isolated restore passed integrity/FK/revision (0004_daily_workspace). All 16 tables matched backup vs restore; Workspace=2, Project=0, Note=2, Task=0. The production DB was not overwritten. Invalid source regression left neither a published snapshot nor staging directory.

Updated Windows second-copy job to validate selected source and copied SQLite, compare SHA256, publish after success, reject invalid existing copies, check native command failures, and bound SSH/SCP stalled connections. Saved previous local script. Checked a real copied snapshot; task max duration set to five minutes. Manually triggering the actual Windows task then returned LastTaskResult=0 at 09:58; the next calendar-triggered run is still pending.

## Tests and limits

66 pytest tests passed, 308 pre-existing-style deprecation warnings. New backup regression covers selecting a valid older file when newer files are empty/corrupt and failing when none is valid. Real host failure drill and full-table restore comparison passed. Browser Core workflow passed with isolated guest identity/SQLite. Mocked browser security regression passed across nine Apps at desktop/mobile widths with no panel overflow or JavaScript errors; real Google consent and iPhone behavior were not automated. git diff --check passed.

Pending: observe next scheduled host/Windows backup, recurrence-free NAT operation, real iPhone keyboard/safe-area/toolbar behavior, geographic encrypted backup/host-failure recovery, attachment reliability and complete multi-user browser coverage. Do not declare unconditional production readiness. White/blue theme remains a prototype.

## Reproduce / rollback

Host scheduled wrapper: `scripts/backup-focusflow.sh` installed as `/home/wensheng/scripts/backup-focusflow.sh`. Previous wrapper retained privately as `/home/wensheng/builds/backup-focusflow-before-20261015.sh`. Previous health script retained as `/home/wensheng/builds/health-check-before-20261015.sh`; only its backup selection was changed to call `scripts/verify_backup.py --select`, taking the path before the `|` checksum separator. No alert destination or secret was changed.

Windows script source is `scripts/backup-homecloud.ps1`, installed at `C:/Users/urua0/HomeCloud-Backups/backup-homecloud.ps1`. The previous copy was saved outside Git. To revert maintenance logic, restore the saved wrapper/scripts; doing so restores the old backup weaknesses and should only be a temporary diagnostic step. Current app image and DB schema are unaffected.
