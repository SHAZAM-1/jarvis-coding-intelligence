"""Low-overhead, system-wide resource sampling for explicit benchmark runs.

RAM and CPU measurements describe the whole host, not the Ollama process alone.
They are diagnostic estimates affected by background activity and short tasks.
Importing this module starts no thread and performs no system sampling.
"""

import ctypes
import math
import os
import sys
import threading
from statistics import fmean

from src.resource_guard import available_memory_mb


DEFAULT_SAMPLE_INTERVAL_SECONDS = 0.25


def _total_physical_memory_mb():
    """Return total physical RAM in MiB, or None when unavailable."""
    if sys.platform == "win32":
        class MEMORYSTATUSEX(ctypes.Structure):
            _fields_ = [
                ("dwLength", ctypes.c_ulong),
                ("dwMemoryLoad", ctypes.c_ulong),
                ("ullTotalPhys", ctypes.c_ulonglong),
                ("ullAvailPhys", ctypes.c_ulonglong),
                ("ullTotalPageFile", ctypes.c_ulonglong),
                ("ullAvailPageFile", ctypes.c_ulonglong),
                ("ullTotalVirtual", ctypes.c_ulonglong),
                ("ullAvailVirtual", ctypes.c_ulonglong),
                ("ullAvailExtendedVirtual", ctypes.c_ulonglong),
            ]

        status = MEMORYSTATUSEX()
        status.dwLength = ctypes.sizeof(status)
        try:
            if ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(status)):
                return int(status.ullTotalPhys // (1024 * 1024))
        except (AttributeError, OSError):
            return None
        return None

    if sys.platform.startswith("linux"):
        try:
            with open("/proc/meminfo", encoding="ascii") as memory_info:
                for line in memory_info:
                    if line.startswith("MemTotal:"):
                        return int(line.split()[1]) // 1024
        except (OSError, ValueError, IndexError):
            return None
    return None


def _cpu_counters():
    """Return cumulative (total, idle) system CPU counters when supported."""
    if sys.platform == "win32":
        class FILETIME(ctypes.Structure):
            _fields_ = [
                ("dwLowDateTime", ctypes.c_ulong),
                ("dwHighDateTime", ctypes.c_ulong),
            ]

        idle = FILETIME()
        kernel = FILETIME()
        user = FILETIME()
        try:
            succeeded = ctypes.windll.kernel32.GetSystemTimes(
                ctypes.byref(idle), ctypes.byref(kernel), ctypes.byref(user)
            )
            if not succeeded:
                return None

            def as_integer(value):
                return (value.dwHighDateTime << 32) | value.dwLowDateTime

            idle_value = as_integer(idle)
            total_value = as_integer(kernel) + as_integer(user)
            return total_value, idle_value
        except (AttributeError, OSError):
            return None

    if sys.platform.startswith("linux"):
        try:
            with open("/proc/stat", encoding="ascii") as stat_file:
                fields = stat_file.readline().split()
            if not fields or fields[0] != "cpu" or len(fields) < 5:
                return None
            values = [int(value) for value in fields[1:]]
            return sum(values), values[3] + values[4]
        except (OSError, ValueError, IndexError):
            return None
    return None


class ResourceSampler:
    """Sample host RAM availability and system CPU while a workload runs."""

    def __init__(self, interval_seconds=DEFAULT_SAMPLE_INTERVAL_SECONDS):
        if (
            not isinstance(interval_seconds, (int, float))
            or isinstance(interval_seconds, bool)
            or not math.isfinite(interval_seconds)
            or interval_seconds <= 0
            or interval_seconds > 60
        ):
            raise ValueError("interval_seconds must be finite and in (0, 60].")
        self.interval_seconds = float(interval_seconds)
        self._total_ram_mb = None
        self._samples = []
        self._cpu_percentages = []
        self._lock = threading.Lock()
        self._stop = threading.Event()
        self._thread = None

    def _capture(self):
        available_mb = available_memory_mb()
        cpu = _cpu_counters()
        with self._lock:
            previous = self._samples[-1] if self._samples else None
            if previous and previous["cpu"] is not None and cpu is not None:
                previous_total, previous_idle = previous["cpu"]
                current_total, current_idle = cpu
                total_delta = current_total - previous_total
                idle_delta = current_idle - previous_idle
                if total_delta > 0 and idle_delta >= 0:
                    busy_percent = 100.0 * (1 - idle_delta / total_delta)
                    self._cpu_percentages.append(
                        round(max(0.0, min(100.0, busy_percent)), 2)
                    )
            self._samples.append({"available_ram_mb": available_mb, "cpu": cpu})

    def _sample_loop(self):
        while not self._stop.wait(self.interval_seconds):
            self._capture()

    def __enter__(self):
        self._total_ram_mb = _total_physical_memory_mb()
        self._capture()
        self._thread = threading.Thread(
            target=self._sample_loop,
            name="jarvis-resource-sampler",
            daemon=True,
        )
        self._thread.start()
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        self._stop.set()
        if self._thread is not None:
            self._thread.join(timeout=min(1.0, self.interval_seconds + 0.1))
        self._capture()
        return False

    def report(self):
        """Return JSON-serializable metrics and explicit attribution limits."""
        with self._lock:
            samples = list(self._samples)
            cpu_percentages = list(self._cpu_percentages)

        ram_values = [
            sample["available_ram_mb"]
            for sample in samples
            if isinstance(sample["available_ram_mb"], int)
            and sample["available_ram_mb"] >= 0
        ]
        before_mb = ram_values[0] if ram_values else None
        minimum_mb = min(ram_values) if ram_values else None
        after_mb = ram_values[-1] if ram_values else None
        ram_drop_mb = (
            max(0, before_mb - minimum_mb)
            if before_mb is not None and minimum_mb is not None
            else None
        )
        estimated_peak_used_mb = (
            max(0, self._total_ram_mb - minimum_mb)
            if self._total_ram_mb is not None and minimum_mb is not None
            else None
        )

        return {
            "measurement_scope": "system_wide_not_model_process_attributed",
            "total_ram_mb": self._total_ram_mb,
            "available_ram_before_mb": before_mb,
            "available_ram_min_mb": minimum_mb,
            "available_ram_after_mb": after_mb,
            "available_ram_drop_from_start_mb": ram_drop_mb,
            "estimated_peak_system_ram_used_mb": estimated_peak_used_mb,
            "system_cpu_average_percent": (
                round(fmean(cpu_percentages), 2) if cpu_percentages else None
            ),
            "system_cpu_peak_percent": (
                max(cpu_percentages) if cpu_percentages else None
            ),
            "memory_sample_count": len(ram_values),
            "cpu_interval_sample_count": len(cpu_percentages),
            "sample_interval_ms": round(self.interval_seconds * 1000, 1),
            "limitations": [
                "RAM and CPU describe the whole system and are not attributed to Ollama.",
                "Peak used RAM is estimated as total physical RAM minus minimum available RAM.",
                "Background applications affect measurements; short tasks may have few CPU samples.",
                "Unsupported or failed platform counters are reported as null, not guessed.",
            ],
        }
