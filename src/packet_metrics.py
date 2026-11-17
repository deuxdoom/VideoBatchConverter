"""Bounded packet statistics using stream time, including negative timestamps."""

import math

from .media_summary import number


def timestamp(value):
    try:
        value = float(value)
        return value if math.isfinite(value) else None
    except (TypeError, ValueError):
        return None


class PacketStats:
    def __init__(self):
        self.bytes = self.count = self.timed = self.positioned = 0
        self.seconds = 0.0
        self.first = self.last = None
        self.last_duration = 0.0

    def add(self, packet):
        size = number(packet.get('size'))
        if not size:
            return
        self.bytes += int(size)
        self.count += 1
        duration = number(packet.get('duration_time'))
        if duration:
            self.timed += 1
            self.seconds += duration
        position = timestamp(packet.get('pts_time'))
        if position is None:
            position = timestamp(packet.get('dts_time'))
        if position is not None:
            self.positioned += 1
            self.first = position if self.first is None else min(self.first, position)
            if self.last is None or position >= self.last:
                self.last = position
                self.last_duration = duration

    def duration(self, fallback=0.0):
        # MKV's millisecond time base truncates every packet duration (e.g.
        # 24 fps -> .041s). Summing those durations overstates the bitrate.
        if self.positioned == self.count and self.count > 1 and self.last > self.first:
            tail = self.last_duration or self.seconds / self.count
            return self.last - self.first + tail
        if self.count and self.timed == self.count:
            return self.seconds
        return number(fallback)
