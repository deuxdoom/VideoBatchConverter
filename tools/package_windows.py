"""Package a clean Windows ZIP with dependency licenses and matching sources."""

import argparse
import hashlib
import importlib.metadata as metadata
import json
from pathlib import Path
import platform
import re
import sys
import zipfile

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from src.profiles import APP_VERSION

DEPENDENCIES = ('PyQt6', 'PyQt6-Qt6', 'PyQt6-sip', 'PyInstaller', 'requests',
                'urllib3', 'charset-normalizer', 'certifi', 'idna', 'setuptools')


def distributable(path):
    parts = tuple(part.lower() for part in path.parts)
    return (parts[0] in ('videobatchconverter.exe', 'license', 'bin')
            and parts[:2] != ('bin', 'ffmpeg')
            and '__pycache__' not in parts
            and path.suffix.lower() not in ('.ini', '.log', '.pyc')
            and not any(part.startswith('.install-') for part in parts))


def package(app_dir, output_dir):
    app_dir, output_dir = app_dir.resolve(), output_dir.resolve()
    if output_dir == app_dir or app_dir in output_dir.parents:
        raise ValueError('The output directory must be outside the app directory.')
    if not (app_dir / 'VideoBatchConverter.exe').is_file() or not (app_dir / 'bin').is_dir():
        raise ValueError('Build the Windows application first.')
    output_dir.mkdir(parents=True, exist_ok=True)
    archive = output_dir / f'VideoBatchConverter-{APP_VERSION}-windows-x64.zip'
    prefix = 'VideoBatchConverter/'
    sources = json.loads((ROOT / 'tools/release-sources.json').read_text(encoding='utf-8'))
    assert platform.python_version() == sources['Python']['version'] and sys.maxsize > 2**32
    manifest = {'version': APP_VERSION, 'files': [], 'dependencies': {}}
    with zipfile.ZipFile(archive, 'w', compression=zipfile.ZIP_DEFLATED, compresslevel=9) as package_zip:
        for path in sorted(app_dir.rglob('*')):
            relative = path.relative_to(app_dir)
            if path.is_file() and distributable(relative):
                package_zip.write(path, prefix + relative.as_posix())
                manifest['files'].append(relative.as_posix())
        for name in DEPENDENCIES:
            distribution = metadata.distribution(name)
            version = distribution.version
            # A source manifest from a different build must never silently ship.
            assert version == sources[name]['version'], (name, version, sources[name]['version'])
            manifest['dependencies'][name] = version
            licenses = [f for f in distribution.files or []
                        if re.match(r'(?i)^(license|copying|notice|copyright)([._-]|$)', Path(f).name)]
            if not licenses:
                raise ValueError(f'No license found for {name}')
            for file in licenses:
                package_zip.write(distribution.locate_file(file), prefix + f'bin/licenses/{name}/{file}')
        python_license = Path(sys.base_prefix) / 'LICENSE.txt'
        package_zip.write(python_license, prefix + 'bin/licenses/Python-LICENSE.txt')
        package_zip.write(ROOT / 'THIRD_PARTY_NOTICES.md', prefix + 'bin/licenses/README.md')
        package_zip.write(ROOT / 'tools/release-sources.json', prefix + 'bin/licenses/sources.json')
        package_zip.write(ROOT / 'README.md', prefix + 'README.md')
    with zipfile.ZipFile(archive) as check:
        if check.testzip() is not None:
            raise ValueError('The release ZIP failed its CRC check.')
        names = check.namelist()
        assert not any('/ffmpeg/' in name or name.endswith(('.ini', '.log')) for name in names)
        assert prefix + 'bin/licenses/README.md' in names
    with archive.open('rb') as stream:
        digest = hashlib.file_digest(stream, 'sha256').hexdigest()
    (output_dir / 'SHA256SUMS.txt').write_text(f'{digest}  {archive.name}\n', encoding='utf-8')
    manifest.update(archive=archive.name, sha256=digest, bytes=archive.stat().st_size)
    (output_dir / 'package-manifest.json').write_text(json.dumps(manifest, indent=2), encoding='utf-8')
    print(json.dumps({key: manifest[key] for key in ('archive', 'sha256', 'bytes')}))
    return archive


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--app-dir', type=Path, default=ROOT / 'dist/VideoBatchConverter')
    parser.add_argument('--output-dir', type=Path, required=True)
    args = parser.parse_args()
    package(args.app_dir, args.output_dir)
