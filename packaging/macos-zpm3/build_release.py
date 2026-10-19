#!/usr/bin/env python3
"""Build an ad-hoc signed, relocatable macOS arm64 ZP/M app and media ZIPs."""
from pathlib import Path
import argparse
import hashlib
import json
import os
import plistlib
import re
import shutil
import subprocess
import tempfile
import zipfile

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
SYSTEM = ROOT / 'systems/mz700-zpm3'


def run(*args):
    result = subprocess.run(list(map(str, args)), stdout=subprocess.PIPE,
                            stderr=subprocess.STDOUT, text=True)
    if result.returncode:
        raise RuntimeError(f'{args[0]} failed ({result.returncode}):\n{result.stdout}')
    return result.stdout


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def dependencies(path):
    return [line.strip().split(' (compatibility')[0]
            for line in run('otool', '-L', path).splitlines()[1:]]


def system_library(name):
    return name.startswith(('/usr/lib/', '/System/Library/'))


def resolve(name, owner):
    if name.startswith('@loader_path/'):
        return (owner.parent / name[len('@loader_path/'):]).resolve(strict=True)
    if name.startswith('@rpath/'):
        suffix = name[len('@rpath/'):]
        candidates = [owner.parent / suffix]
        commands = run('otool', '-l', owner)
        for value in re.findall(r'cmd LC_RPATH\s+cmdsize \d+\s+path (.+?) \(offset', commands):
            base = value.replace('@loader_path', str(owner.parent))
            candidates.append(Path(base) / suffix)
        for candidate in candidates:
            if candidate.is_file():
                return candidate.resolve(strict=True)
    if name.startswith('/'):
        return Path(name).resolve(strict=True)
    raise ValueError(f'Unresolved non-system dependency {name!r} in {owner}')


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--output', type=Path, required=True)
    ap.add_argument('--binary', type=Path,
                    default=ROOT / 'build-mac/build-mz700emu-pal/mz700emu-pal')
    ap.add_argument('--version', default='0.1.0')
    args = ap.parse_args()
    out = args.output.resolve(); out.mkdir(parents=True, exist_ok=True)
    version = args.version
    if not re.fullmatch(r'[0-9]+\.[0-9]+\.[0-9]+', version):
        raise ValueError('Version must have three numeric components')
    binary = args.binary.resolve(strict=True)
    if 'arm64' not in run('file', binary):
        raise ValueError('This release builder requires an arm64 emulator')
    minos = re.search(r'\bminos\s+(\S+)', run('vtool', '-show-build', binary))[1]
    if minos != '27.0':
        raise ValueError(f'Update release labels for this minimum macOS version: {minos}')
    # Build outside iCloud/File Provider folders, which re-add FinderInfo.
    stage = Path(tempfile.mkdtemp(prefix='mz700-release-stage-', dir='/private/tmp'))
    top = stage / f'MZ700-ZPM3-v{version}-macOS27-arm64'; top.mkdir(parents=True)
    app = top / 'MZ-700 ZPM3.app'
    contents = app / 'Contents'
    macos = contents / 'MacOS'; macos.mkdir(parents=True)
    frameworks = contents / 'Frameworks'; frameworks.mkdir()
    resources = contents / 'Resources'; resources.mkdir()
    shutil.copytree(ROOT / 'ui_resources', resources / 'ui_resources',
                    ignore=shutil.ignore_patterns('.DS_Store'))
    system = resources / 'system'
    for sub in ['images', 'roms', 'notices']:
        shutil.copytree(SYSTEM / sub, system / sub)
    for name in ['README.md', 'APPLICATIONS.txt', 'APPLICATION-PROVENANCE.json', 'manifest.json']:
        shutil.copy2(SYSTEM / name, system / name)
    (system / 'README.md').rename(system / 'SOURCE-README.md')
    for name, rec in json.loads((SYSTEM / 'manifest.json').read_text())['files'].items():
        copied = system / name
        if copied.exists() and sha(copied) != rec['sha256']:
            raise ValueError(f'Media checksum mismatch: {name}')
    shutil.copy2(ROOT / 'LICENSE', resources / 'EMULATOR-LICENSE.txt')
    shutil.copy2(HERE / 'GETTING-STARTED.md', top / 'GETTING-STARTED.md')
    shutil.copy2(HERE / 'GETTING-STARTED.md', resources / 'GETTING-STARTED.md')
    executable = macos / 'mz700emu-pal'; shutil.copy2(binary, executable)
    launcher = macos / 'MZ700-ZPM3'
    run('cc', '-std=c11', '-O2', '-Wall', '-Wextra', '-Werror',
        '-mmacosx-version-min=27.0', HERE / 'launcher.c', '-o', launcher)
    with (contents / 'Info.plist').open('wb') as dst:
        plistlib.dump(dict(CFBundleExecutable='MZ700-ZPM3',
            CFBundleIdentifier='io.github.benjamindonnachie.mz700-zpm3',
            CFBundleName='MZ-700 ZPM3', CFBundleDisplayName='MZ-700 ZPM3',
            CFBundlePackageType='APPL', CFBundleShortVersionString=version,
            CFBundleVersion=version, LSMinimumSystemVersion='27.0',
            NSHighResolutionCapable=True), dst)
    # Copy the complete non-system load-command closure. Original files stay untouched.
    graph = {}; todo = [binary]
    while todo:
        owner = todo.pop()
        if owner in graph:
            continue
        graph[owner] = dependencies(owner)
        for name in graph[owner]:
            if not system_library(name):
                dep = resolve(name, owner)
                if dep != owner and dep not in graph:
                    todo.append(dep)
    libraries = sorted(p for p in graph if p != binary)
    names = {}
    for source in libraries:
        if source.name in names and names[source.name] != source:
            raise ValueError(f'Conflicting library basename: {source.name}')
        names[source.name] = source
        shutil.copy2(source, frameworks / source.name)
    changed = {binary: executable, **{p: frameworks / p.name for p in libraries}}
    for source, target in changed.items():
        target.chmod(0o755)
        if source != binary:
            run('install_name_tool', '-id', '@rpath/' + target.name, target)
        for dep in graph[source]:
            if system_library(dep):
                continue
            actual = resolve(dep, source)
            if actual == source:
                continue
            relative = ('@loader_path/../Frameworks/' if source == binary
                        else '@loader_path/') + actual.name
            run('install_name_tool', '-change', dep, relative, target)
    notices = resources / 'Third-party'; notices.mkdir()
    formulae = {}
    for lib in libraries:
        # Homebrew's realpath is Cellar/<formula>/<version>/lib/<file>.
        parts = lib.parts
        if 'Cellar' not in parts:
            raise ValueError(f'Collect provenance for non-Homebrew library: {lib}')
        index = parts.index('Cellar')
        prefix = Path(*parts[:index + 3])
        name, installed = parts[index + 1:index + 3]
        if name in formulae:
            continue
        dest = notices / name; dest.mkdir()
        recipe = next((prefix / '.brew').glob('*.rb'))
        shutil.copy2(recipe, dest / recipe.name)
        text = recipe.read_text()
        source_url = re.search(r'^\s*url "([^"]+)"', text, re.M)
        licence = re.search(r'^\s*license\s+(.+)', text, re.M)
        copied = []
        for p in prefix.rglob('*'):
            if (p.is_file() and p.name.lower().startswith(
                    ('license', 'licence', 'copying', 'copyright', 'authors'))
                    and p.stat().st_size < 2_000_000):
                rel = p.relative_to(prefix); dst = dest / rel
                dst.parent.mkdir(parents=True, exist_ok=True); shutil.copy2(p, dst)
                copied.append(str(rel))
        extra = HERE / 'licences' / (name + '-COPYING')
        if extra.exists():
            shutil.copy2(extra, dest / 'COPYING'); copied.append('COPYING')
        if not any(Path(p).name.lower().startswith(('license', 'licence', 'copying')) for p in copied):
            raise ValueError(f'No licence text collected for {name}')
        formulae[name] = dict(version=installed, source_url=source_url[1] if source_url else None,
                              licence_expression=licence[1] if licence else None,
                              notices=sorted(set(copied)))
    shutil.copy2(HERE / 'licences/provenance.json', notices / 'licence-provenance.json')
    # Verify every rewritten link before signing. No Homebrew paths may remain.
    for path in changed.values():
        for dep in dependencies(path):
            if not system_library(dep) and not dep.startswith(('@loader_path/', '@rpath/')):
                raise ValueError(f'Unbundled dependency: {path}: {dep}')
    # Source files can carry Finder metadata; strip only this generated bundle.
    run('xattr', '-cr', app)
    for path in [*sorted(frameworks.glob('*.dylib')), executable, launcher, app]:
        run('codesign', '--force', '--sign', '-', '--timestamp=none', path)
    run('codesign', '--verify', '--deep', '--strict', '--verbose=2', app)
    commit = run('git', '-C', ROOT, 'rev-parse', 'HEAD').strip()
    manifest = dict(version=version, tag=f'mz700-zpm3-v{version}', source_commit=commit,
        architecture='arm64', minimum_macos=minos, signing='ad-hoc; not notarised',
        stage_directory=str(stage),
        source_binary_sha256=sha(binary), packaged_binary_sha256=sha(executable),
        runtime_libraries=[dict(name=p.name, source=str(p), sha256=sha(frameworks / p.name)) for p in libraries],
        third_party=formulae,
        media=json.loads((SYSTEM / 'manifest.json').read_text()),
        app_files={str(p.relative_to(app)): sha(p) for p in sorted(app.rglob('*')) if p.is_file()})
    manifest_path = out / 'RELEASE-MANIFEST.json'
    manifest_path.write_text(json.dumps(manifest, indent=2) + '\n')
    # The app ZIP retains POSIX executable modes and Apple code signatures.
    app_zip = out / (top.name + '.zip')
    run('ditto', '-c', '-k', '--keepParent', top, app_zip)
    media_root = stage / f'MZ700-ZPM3-v{version}-GIDE-media'
    for sub in ['images', 'roms', 'notices']:
        shutil.copytree(SYSTEM / sub, media_root / sub)
    for name in ['README.md', 'APPLICATIONS.txt', 'APPLICATION-PROVENANCE.json', 'manifest.json']:
        shutil.copy2(SYSTEM / name, media_root / name)
    (media_root / 'README.md').rename(media_root / 'SOURCE-README.md')
    (media_root / 'README.md').write_text(
        '# MZ-700 ZP/M GIDE media\n\n'
        'Read [GETTING-STARTED.md](GETTING-STARTED.md) for the Mac app and manual configuration.\n'
        'Original software notices are in notices/. SOURCE-README.md preserves the repository guide.\n')
    shutil.copy2(HERE / 'GETTING-STARTED.md', media_root / 'GETTING-STARTED.md')
    media_zip = out / (media_root.name + '.zip')
    run('ditto', '-c', '-k', '--keepParent', media_root, media_zip)
    for p in [app_zip, media_zip]:
        with zipfile.ZipFile(p) as z:
            bad = z.testzip()
            if bad:
                raise ValueError(f'Corrupt ZIP member: {p}: {bad}')
    shutil.copy2(HERE / 'GETTING-STARTED.md', out / 'GETTING-STARTED.md')
    assets = [app_zip, media_zip, manifest_path, out / 'GETTING-STARTED.md']
    (out / 'SHA256SUMS.txt').write_text(''.join(f'{sha(p)}  {p.name}\n' for p in assets))
    print(json.dumps(dict(app=str(app), assets=[str(p) for p in assets],
        dylibs=len(libraries), minimum_macos=minos, source_commit=commit), indent=2))


if __name__ == '__main__':
    main()
