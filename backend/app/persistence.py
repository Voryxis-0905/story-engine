"""Coordinated writes for one local server process.

Guarantee scope: a process crash (including a killed worker) is recovered to a
whole state, before or after a turn, by a write-ahead commit journal. This is not
a power-loss guarantee: on-disk data is not fsynced, and multiple server workers
are not supported (the lock is per process). We never delete the last good copy
when staging or journaling fails — replacements only start after every staged
file and backup exists.
"""
import json
import os
import tempfile
import threading
import time
from functools import wraps

from app.commit_sanitizer import cross_check, CommitValidationError

JOURNAL_NAME = '_commit_journal.json'

_locks = {}
_locks_guard = threading.Lock()


def world_lock(world_path):
    key = os.path.normcase(os.path.abspath(world_path))
    with _locks_guard:
        return _locks.setdefault(key, threading.RLock())


def locked_world(function):
    @wraps(function)
    def wrapped(world_name, *args, **kwargs):
        from app.storage import world_path_of
        with world_lock(world_path_of(world_name)):
            return function(world_name, *args, **kwargs)
    return wrapped


def _stage(directory, content):
    fd, path = tempfile.mkstemp(dir=directory, suffix='.tmp')
    try:
        with os.fdopen(fd, 'wb') as stream:
            stream.write(content)
        return path
    except BaseException:
        os.unlink(path)
        raise


def _journal_path(world_path):
    return os.path.join(world_path, JOURNAL_NAME)


def _write_journal(world_path, journal):
    path = _journal_path(world_path)
    temporary = f'{path}.tmp'
    with open(temporary, 'w', encoding='utf-8') as stream:
        json.dump(journal, stream, ensure_ascii=False, indent=2)
    os.replace(temporary, path)


def _read_journal(path):
    with open(path, 'r', encoding='utf-8') as stream:
        data = json.load(stream)
    return data if isinstance(data, dict) else None


def _unlink(path):
    if path and os.path.exists(path):
        try:
            os.unlink(path)
        except OSError:
            pass


def _cleanup(paths):
    for path in paths:
        _unlink(path)


def _restore_entry(world_path, filename, entry):
    destination = os.path.join(world_path, filename)
    backup = entry.get('backup')
    if backup and os.path.isfile(backup):
        if os.path.isfile(destination):
            try:
                with open(destination, 'rb') as current, open(backup, 'rb') as saved:
                    if current.read() == saved.read():
                        # This file was never replaced; nothing to undo.
                        _unlink(backup)
                        return
            except OSError:
                pass
        os.replace(backup, destination)
    elif not entry.get('had_original'):
        # The file did not exist before the commit; remove the new one.
        _unlink(destination)


def _rollback(world_path, journal):
    entries = journal.get('entries', {}) if isinstance(journal, dict) else {}
    for filename, entry in entries.items():
        if isinstance(entry, dict):
            _restore_entry(world_path, filename, entry)
    for entry in entries.values():
        if isinstance(entry, dict):
            _unlink(entry.get('temp'))
            _unlink(entry.get('backup'))
    _unlink(_journal_path(world_path))


def recover_world(world_path):
    """Finish or undo an interrupted commit. Idempotent and safe to call anytime."""
    journal_path = _journal_path(world_path)
    if not os.path.isfile(journal_path):
        return {'recovered': False}
    try:
        journal = _read_journal(journal_path)
    except (json.JSONDecodeError, OSError) as error:
        # A journal we cannot read cannot be trusted. Do not delete any target
        # file; drop the journal and leftover temp files so the world can load.
        _cleanup(_leftover_temp_files(world_path))
        _unlink(journal_path)
        return {'recovered': False, 'reason': f'unreadable journal: {error}'}

    if not isinstance(journal, dict):
        _cleanup(_leftover_temp_files(world_path))
        _unlink(journal_path)
        return {'recovered': False, 'reason': 'malformed journal'}

    state = journal.get('state')
    if state == 'installed':
        # All replacements finished; keep the new state and only clean up.
        entries = journal.get('entries', {})
        for entry in entries.values():
            if isinstance(entry, dict):
                _unlink(entry.get('temp'))
                _unlink(entry.get('backup'))
        _unlink(journal_path)
        return {'recovered': True, 'action': 'roll_forward'}

    _rollback(world_path, journal)
    return {'recovered': True, 'action': 'rollback'}


def _leftover_temp_files(world_path):
    try:
        return [os.path.join(world_path, name) for name in os.listdir(world_path) if name.endswith('.tmp')]
    except OSError:
        return []


def commit_world_files(world_path, updates):
    """Atomically install a set of world files, journaled for crash recovery."""
    with world_lock(world_path):
        staged = {}
        backups = {}
        installed = []
        preserve_backups = False
        journal_written = False
        try:
            for filename, data in updates.items():
                if os.path.basename(filename) != filename or not filename.endswith('.json'):
                    raise ValueError('Expected a world JSON filename')
                errors = cross_check(filename, data)
                if errors:
                    raise CommitValidationError(f'{filename}: ' + '; '.join(errors))
                content = json.dumps(data, ensure_ascii=False, indent=2).encode('utf-8')
                staged[filename] = _stage(world_path, content)
                destination = os.path.join(world_path, filename)
                if os.path.isfile(destination):
                    with open(destination, 'rb') as stream:
                        backups[filename] = _stage(world_path, stream.read())
                else:
                    backups[filename] = None

            # Intent log written before any target is replaced, so a crash can be
            # detected and rolled back to the pre-commit state.
            _write_journal(world_path, {
                'state': 'installing',
                'created_at': time.strftime('%Y-%m-%d %H:%M:%S UTC', time.gmtime()),
                'entries': {
                    filename: {
                        'temp': staged[filename],
                        'backup': backups[filename],
                        'had_original': backups[filename] is not None,
                    }
                    for filename in staged
                },
            })
            journal_written = True

            for filename, temporary in staged.items():
                os.replace(temporary, os.path.join(world_path, filename))
                installed.append(filename)

            _write_journal(world_path, {
                'state': 'installed',
                'created_at': time.strftime('%Y-%m-%d %H:%M:%S UTC', time.gmtime()),
                'entries': {
                    filename: {'temp': None, 'backup': backups[filename], 'had_original': backups[filename] is not None}
                    for filename in staged
                },
            })

            _cleanup(backups.values())
            _unlink(_journal_path(world_path))
            journal_written = False
        except BaseException:
            if journal_written:
                try:
                    recover_world(world_path)
                except OSError as recovery_error:
                    preserve_backups = True
                    raise RuntimeError(
                        f'World rollback failed; recovery journal retained at {_journal_path(world_path)}'
                    ) from recovery_error
            else:
                _cleanup(staged.values())
                _cleanup(backups.values())
            raise
        finally:
            if not preserve_backups:
                _cleanup(staged.values())
                _cleanup(backups.values())
