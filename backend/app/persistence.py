"""Coordinated writes for one local server process.

Rollback covers Python/I/O exceptions, not power loss or multiple server workers.
"""
import json
import os
import tempfile
import threading
from functools import wraps

from app.commit_sanitizer import cross_check, CommitValidationError

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


def commit_world_files(world_path, updates):
    """Validate/stage every file first; restore original bytes if replacement fails."""
    with world_lock(world_path):
        staged = {}
        backups = {}
        installed = []
        preserve_backups = False
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
            for filename, temporary in staged.items():
                os.replace(temporary, os.path.join(world_path, filename))
                installed.append(filename)
        except BaseException:
            try:
                for filename in reversed(installed):
                    destination = os.path.join(world_path, filename)
                    backup = backups[filename]
                    if backup is None:
                        os.unlink(destination)
                    else:
                        os.replace(backup, destination)
                        backups[filename] = None
            except OSError as recovery_error:
                preserve_backups = True
                remaining = {name: path for name, path in backups.items() if path}
                raise RuntimeError(f'World rollback failed; recovery copies retained: {remaining}') from recovery_error
            raise
        finally:
            cleanup = list(staged.values()) + ([] if preserve_backups else list(backups.values()))
            for temporary in cleanup:
                if temporary and os.path.exists(temporary):
                    os.unlink(temporary)
