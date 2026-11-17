# Windows distribution notices

VideoBatchConverter 3.0.0 source code is copyright deuxdoom and is available under
the MIT license in the repository's `LICENSE` file. This does not replace the
licenses of the included dependencies. The combined Windows application includes
GPLv3 PyQt6 and is distributed under GPLv3, with the original MIT notices retained.
The GPLv3 text is included in the PyQt6 license directory.

The application source and build scripts corresponding to this release are at:

- https://github.com/deuxdoom/VideoBatchConverter/tree/v3.0.0
- https://github.com/deuxdoom/VideoBatchConverter/archive/refs/tags/v3.0.0.zip

Exact dependency versions, corresponding source downloads, and source hashes are
listed in `sources.json` beside this file in the ZIP. In the repository, see
[`tools/release-sources.json`](https://github.com/deuxdoom/VideoBatchConverter/blob/v3.0.0/tools/release-sources.json). All dependencies are
used without local source modifications. The upstream Qt source archive includes
Qt's third-party source, notices and license texts.

| Component | License / notice |
| --- | --- |
| PyQt6 | GNU GPL version 3; Riverbank Computing |
| Qt | GNU LGPL version 3, with component-specific notices; The Qt Company and contributors |
| PyQt6-sip | BSD 2-Clause; original text included |
| Python | Python Software Foundation license and included third-party notices |
| PyInstaller bootloader | GPL with the bootloader exception in its included license |
| Requests | Apache 2.0 |
| urllib3, charset-normalizer, idna, setuptools | Their included MIT/BSD and vendored component notices |
| certifi | Mozilla Public License 2.0 |
| Noto Sans CJK KR | SIL Open Font License 1.1; `bin/fonts/LICENSE-Noto.txt` |
| Fluent System Icons | Microsoft MIT; `bin/icons/LICENSE` |
| Kenney Interface Sounds | CC0; `bin/audio/LICENSE-Kenney.txt` |

The ZIP contains the original dependency license files in `bin/licenses/`.
Python and Qt DLLs remain separate files; modified compatible libraries and
application builds can be used. Build the application using `requirements.txt`,
the exact versions in `tools/release-sources.json`, and `tools/build_windows.ps1`.
The release was built on 64-bit Windows with Python 3.14.7 and PyInstaller 6.22.0.

FFmpeg and FFprobe are not included in the release ZIP. The application downloads
them on first launch from the FFmpeg-Builds project. Their separate upstream
build, licenses and sources are available at:

- https://github.com/FFmpeg-Builds/FFmpeg-Builds
- https://ffmpeg.org/legal.html

This software is supplied without warranty as described in its licenses.
