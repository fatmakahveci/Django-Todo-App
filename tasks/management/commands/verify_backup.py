import sqlite3
from pathlib import Path

from django.core.management.base import BaseCommand, CommandError


class Command(BaseCommand):
    help = 'Restore a backup into a NEW SQLite file and verify it; never replace the live database.'

    def add_arguments(self, parser):
        parser.add_argument('--source', required=True)
        parser.add_argument('--output', required=True)

    def handle(self, *args, **options):
        source = Path(options['source']).resolve()
        target = Path(options['output']).resolve()
        if not source.is_file() or target.exists():
            raise CommandError('Source must exist and output must be a new file.')
        with sqlite3.connect(source.as_uri() + '?mode=ro', uri=True) as backup:
            if backup.execute('PRAGMA integrity_check').fetchone()[0] != 'ok':
                raise CommandError('Invalid backup.')
            # Exclusive creation prevents accidentally replacing an existing database.
            target.touch(mode=0o600, exist_ok=False)
            try:
                with sqlite3.connect(target) as restored:
                    backup.backup(restored)
                    if restored.execute('PRAGMA integrity_check').fetchone()[0] != 'ok':
                        raise CommandError('Restored database failed integrity verification.')
            except Exception:
                target.unlink(missing_ok=True)
                raise
        self.stdout.write(f'Restore verified: {target}')
