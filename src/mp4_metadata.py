"""Read declared AAC maxima from MP4 sample descriptions without reading media packets."""

from pathlib import Path


def _boxes(stream, start, end, cancelled):
    position = start
    count = 0
    while position + 8 <= end and not cancelled() and count < 10000:
        count += 1
        stream.seek(position)
        header = stream.read(8)
        if len(header) != 8:
            return
        size = int.from_bytes(header[:4], 'big')
        length = 8
        if size == 1:
            extended = stream.read(8)
            if len(extended) != 8:
                return
            size = int.from_bytes(extended, 'big')
            length = 16
        elif size == 0:
            size = end - position
        if size < length or position + size > end:
            return
        yield header[4:], position + length, position + size
        position += size


def _path(stream, start, end, names, cancelled):
    for kind, payload, limit in _boxes(stream, start, end, cancelled):
        if kind == names[0]:
            if len(names) == 1:
                yield payload, limit
            else:
                yield from _path(stream, payload, limit, names[1:], cancelled)


def _esds_maximum(data, start=4, end=None, depth=0):
    if depth > 8:
        return None
    end = len(data) if end is None else end
    while start < end:
        tag = data[start]
        start += 1
        size = 0
        for _ in range(4):
            if start >= end:
                return None
            byte = data[start]
            start += 1
            size = (size << 7) | (byte & 127)
            if not byte & 128:
                break
        else:
            return None
        limit = start + size
        if limit > end:
            return None
        if tag == 4 and size >= 13 and data[start] in (0x40, 0x66, 0x67, 0x68):
            return int.from_bytes(data[start + 5:start + 9], 'big') or None
        if tag == 3 and size >= 3:
            flags = data[start + 2]
            child = start + 3 + (2 if flags & 128 else 0)
            if flags & 64:
                if child >= limit:
                    return None
                child += 1 + data[child]
            child += 2 if flags & 32 else 0
            if child <= limit:
                value = _esds_maximum(data, child, limit, depth + 1)
                if value:
                    return value
        start = limit
    return None


def _sample_maximum(stream, start, end, cancelled, depth=0):
    fallback = None
    for kind, payload, limit in _boxes(stream, start, end, cancelled):
        if kind == b'esds' and limit - payload <= 65536:
            stream.seek(payload)
            value = _esds_maximum(stream.read(limit - payload))
            if value:
                return value
        elif kind == b'btrt' and limit - payload >= 12:
            stream.seek(payload + 4)
            fallback = int.from_bytes(stream.read(4), 'big') or None
        elif kind == b'wave' and depth < 2:
            value = _sample_maximum(stream, payload, limit, cancelled, depth + 1)
            if value:
                return value
    return fallback


def aac_maximum_bitrate(file_path, stream_id=None, cancelled=lambda: False):
    """Return the selected audio track's declared maximum, never a packet-derived spike."""
    try:
        track_id = int(str(stream_id), 0) if stream_id is not None else None
        with Path(file_path).open('rb') as stream:
            stream.seek(0, 2)
            end = stream.tell()
            for start, limit in _path(stream, 0, end, (b'moov', b'trak'), cancelled):
                selected_id = None
                for payload, stop in _path(stream, start, limit, (b'tkhd',), cancelled):
                    stream.seek(payload)
                    header = stream.read(min(28, stop - payload))
                    offset = 20 if header and header[0] == 1 else 12
                    if len(header) >= offset + 4:
                        selected_id = int.from_bytes(header[offset:offset + 4], 'big')
                if track_id is not None and selected_id != track_id:
                    continue
                handlers = list(_path(stream, start, limit, (b'mdia', b'hdlr'), cancelled))
                if not handlers or handlers[0][1] - handlers[0][0] < 12:
                    continue
                stream.seek(handlers[0][0] + 8)
                if stream.read(4) != b'soun':
                    continue
                for payload, stop in _path(stream, start, limit, (b'mdia', b'minf', b'stbl', b'stsd'), cancelled):
                    for kind, entry, entry_end in _boxes(stream, payload + 8, stop, cancelled):
                        if kind not in (b'mp4a', b'enca') or entry_end - entry < 28:
                            continue
                        stream.seek(entry + 8)
                        version = int.from_bytes(stream.read(2), 'big')
                        extra = {0: 0, 1: 16, 2: 36}.get(version)
                        if extra is not None:
                            value = _sample_maximum(stream, entry + 28 + extra, entry_end, cancelled)
                            if value:
                                return value
                if track_id is None:
                    return None
    except (OSError, ValueError):
        return None
    return None
