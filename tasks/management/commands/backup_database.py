import os
import sqlite3
from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError


class Command(BaseCommand):
    help = 'Create and integrity-check a consistent SQLite backup without overwriting files.'

    def add_arguments(self, parser):
        parser.add_argument('--output', required=True)

    def handle(self, *args, **options):
        config = settings.DATABASES['default']
        if config['ENGINE'] != 'django.db.backends.sqlite3' or config['NAME'] == ':memory:':
            raise CommandError('This command requires a file-backed SQLite database.')
        source = Path(config['NAME']).resolve()
        destination = Path(options['output']).resolve()
        if not source.is_file() or source == destination:
            raise CommandError('Choose an existing source database and a different output file.')
        destination.parent.mkdir(parents=True, exist_ok=True)
        try:
            fd = os.open(destination, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
        except FileExistsError as exc:
            raise CommandError('Output already exists; refusing to overwrite it.') from exc
        os.close(fd)
        try:
            with sqlite3.connect(source.as_uri() + '?mode=ro', uri=True) as origin:
                with sqlite3.connect(destination) as backup:
                    origin.backup(backup)
                    if backup.execute('PRAGMA integrity_check').fetchone()[0] != 'ok':
                        raise CommandError('Backup integrity check failed.')
        except Exception:
            destination.unlink(missing_ok=True)
            raise
        self.stdout.write(f'Backup verified: {destination}')
