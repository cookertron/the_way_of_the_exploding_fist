#!/usr/bin/env python3
"""
portconfig.py -- the one place the tools read port.json.

Every tool in tools/ is game-agnostic.  Everything that is NOT -- which tape,
where the loader puts each block, the entry point, the PC of the game's own
CALL into the ROM loader, where the memory image and the saved states live --
comes from ONE manifest, port.json, at the repository root.  The build script
reads the same file (`name`, `template`, `out`, `includes`, `assets` are its
keys; the tools read `tape` and `z80`).

Rules:
  - NEVER fail at import.  A missing manifest or a null key yields the
    defaults below.  A tool complains only when it actually needs a value,
    through need(), and the message names the key to fill in.
  - Numbers may be JSON ints or hex strings ("0x8400" or "$8400"): JSON has
    no hex literals and a Z80 address in decimal is unreadable.  num() takes
    either.  A bare digit string is DECIMAL.
  - Paths are relative to the repository root, the directory holding
    port.json.  path() resolves them; absolute paths pass through.

The manifest is found by walking up from this file's directory, or taken
from the PORT_JSON environment variable if that is set.

Usage from a tool:
    import portconfig
    entry = portconfig.need('tape', 'entry', what='the post-loader entry point')
    img = portconfig.path(portconfig.get('z80', 'image'))
"""
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
MANIFEST = 'port.json'

# Every key a tool may ask for, with its default.  None means "not configured".
DEFAULTS = {
    'name': 'mygame',
    'template': 'web/template.html',
    'out': 'web/mygame.html',
    'includes': {},
    'assets': [],
    'tape': {
        'path': None,           # the tape the post-loader image is built from
        'deck': None,           # the tape served at runtime loads (default: path)
        'blocks': [],           # [] or "auto": follow the ROM headers; else a
                                # list of {dest, len, flag | block} -- README
        'copies': [],           # the loader's own post-load moves: {src, dst, len}
        'prog': '0x5CCB',       # where a BASIC block is LOADed (stock 48K)
        'entry': None,          # PC when the loader hands over to the game
        'sp': '0xFFFF',         # SP at that moment (the game usually sets its own)
        'tape_call_pc': None,   # PC of the game's own CALL into LD-BYTES, if any
        'tape_ret_pc': None,    # where that CALL returns (default: call + 3)
    },
    'z80': {
        'contended': True,      # CMIOSimulator (ULA contention) or plain Simulator
        'symbols': 'tools/symbols.json',
        'regions': 'tools/regions.json',
        'states': 'build',      # directory for saved machine states (*.pkl)
        'image': 'build/image.bin',   # the static post-loader 64K image
        'snapshot': None,       # a .z80/.szx to boot from instead (the snapshot route)
        'snapshot128': None,    # the same tape loaded on a 128K, for the 128K layer
        'varmap': 'tools/varmap.json',   # {name: {addr, width, note}} shared by sampler + engine
    },
}

_cache = None      # (manifest_path_or_None, merged_config)


def find_manifest(start=HERE):
    """The nearest port.json at or above `start`, or None."""
    env = os.environ.get('PORT_JSON')
    if env:
        return os.path.abspath(env)
    d = os.path.abspath(start)
    while True:
        p = os.path.join(d, MANIFEST)
        if os.path.isfile(p):
            return p
        parent = os.path.dirname(d)
        if parent == d:
            return None
        d = parent


def _merge(defaults, given):
    """Deep-merge `given` over `defaults`.  A null in the manifest means
    'use the default'; lists and scalars replace."""
    if not isinstance(given, dict):
        return defaults if given is None else given
    out = dict(defaults)
    for k, v in given.items():
        if v is None:
            continue
        if isinstance(out.get(k), dict) and isinstance(v, dict):
            out[k] = _merge(out[k], v)
        else:
            out[k] = v
    return out


def reload(manifest=None):
    """Re-read the manifest (tests use this with an explicit path)."""
    global _cache
    p = os.path.abspath(manifest) if manifest else find_manifest()
    given = {}
    if p and os.path.isfile(p):
        with open(p, 'r', encoding='utf-8') as f:
            given = json.load(f)
    else:
        p = None                        # named but absent: defaults, no root
    _cache = (p, _merge(DEFAULTS, given))
    return _cache[1]


def manifest_path():
    if _cache is None:
        reload()
    return _cache[0]


def cfg():
    """The whole configuration, defaults filled in.  Never raises."""
    if _cache is None:
        reload()
    return _cache[1]


def root():
    """The repository root: the manifest's directory, or the parent of tools/
    when there is no manifest yet."""
    p = manifest_path()
    return os.path.dirname(p) if p else os.path.dirname(HERE)


def path(rel):
    """Resolve a manifest path against the repository root."""
    if rel is None:
        return None
    return rel if os.path.isabs(rel) else os.path.normpath(os.path.join(root(), rel))


def get(*keys, default=None):
    """cfg()['a']['b']..., or `default` when any level is missing/None."""
    v = cfg()
    for k in keys:
        if not isinstance(v, dict) or k not in v:
            return default
        v = v[k]
    return default if v is None else v


def num(v, what='value'):
    """int from a JSON int or a hex string.  None passes through."""
    if v is None or isinstance(v, int):
        return v
    if isinstance(v, str):
        s = v.strip().replace('$', '0x')
        try:
            return int(s, 0)
        except ValueError:
            pass
    sys.exit(f'port.json: {what} = {v!r} is not a number (use an int, "0x...", or "$...")')


def need(*keys, what=''):
    """A value the tool cannot proceed without.  Exits with the key path."""
    v = get(*keys)
    if v is None or v == [] or v == '':
        where = manifest_path() or os.path.join(root(), MANIFEST)
        why = f' ({what})' if what else ''
        sys.exit(f'port.json: {".".join(keys)} is not set{why} -- fill it in at {where}')
    return v


def state_path(name):
    """A saved-state file: an existing path as given, else NAME[.pkl] under
    z80.states."""
    if name is None:
        return None
    if os.path.exists(name) or os.path.dirname(name):
        return name
    if not os.path.splitext(name)[1]:
        name += '.pkl'
    return os.path.join(path(get('z80', 'states', default='build')), name)


# -- the loader's postcondition, normalised to ints ----------------------------

def blocks_spec():
    """tape.blocks as a list of dicts with int fields, or 'auto'."""
    spec = get('tape', 'blocks', default=[])
    if not spec or spec == 'auto':
        return 'auto'
    out = []
    for i, e in enumerate(spec):
        if not isinstance(e, dict) or 'dest' not in e:
            sys.exit(f'port.json: tape.blocks[{i}] must be an object with at least "dest"')
        out.append({'dest': num(e['dest'], f'tape.blocks[{i}].dest'),
                    'len': num(e.get('len'), f'tape.blocks[{i}].len'),
                    'flag': num(e.get('flag'), f'tape.blocks[{i}].flag'),
                    'block': num(e.get('block'), f'tape.blocks[{i}].block')})
        if out[-1]['flag'] is None and out[-1]['block'] is None:
            sys.exit(f'port.json: tape.blocks[{i}] needs "flag" (tape flag byte) or "block" (TZX block index)')
    return out


def copies_spec():
    """tape.copies as (src, dst, len) int triples."""
    out = []
    for i, c in enumerate(get('tape', 'copies', default=[])):
        try:
            out.append((num(c['src'], f'tape.copies[{i}].src'),
                        num(c['dst'], f'tape.copies[{i}].dst'),
                        num(c['len'], f'tape.copies[{i}].len')))
        except (KeyError, TypeError):
            sys.exit(f'port.json: tape.copies[{i}] must be an object with src, dst, len')
    return out


def contended():
    """z80.contended, overridable by PORT_CONTENDED=0/1 in the environment."""
    env = os.environ.get('PORT_CONTENDED')
    if env is not None and env != '':
        return env not in ('0', 'false', 'no', 'off')
    return bool(get('z80', 'contended', default=True))


if __name__ == '__main__':
    if '-h' in sys.argv or '--help' in sys.argv:
        print(__doc__.strip()); sys.exit(0)
    print(f'manifest: {manifest_path() or "(none found -- defaults)"}')
    print(f'root:     {root()}')
    print(json.dumps(cfg(), indent=2))
