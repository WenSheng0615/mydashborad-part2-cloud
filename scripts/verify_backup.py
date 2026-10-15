"""Select a valid snapshot or verify a copied one; never expose database content."""
import hashlib
from pathlib import Path
import sqlite3
import sys

if __package__:
    from .backup_restore import verify
else:
    from backup_restore import verify


def digest(path):
    with Path(path).open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def select(directory):
    for path in sorted(Path(directory).glob('focusflow-*.db'), key=lambda p: p.stat().st_mtime, reverse=True):
        try:
            if not path.stat().st_size:
                continue
            verify(path)
        except (sqlite3.Error, RuntimeError, OSError):
            continue
        return path.resolve(), digest(path)
    raise RuntimeError('No verified backup available')


if __name__ == '__main__':
    if len(sys.argv) == 3 and sys.argv[1] == '--select':
        path, checksum = select(sys.argv[2])
        print(str(path) + '|' + checksum)
    elif len(sys.argv) == 3 and sys.argv[1] == '--verify':
        verify(sys.argv[2])
        print(digest(sys.argv[2]))
    else:
        raise SystemExit('Usage: verify_backup.py --select DIRECTORY | --verify FILE')
