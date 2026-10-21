"""Low-overhead resource guard for local Ollama inference.

The guard does not try to predict exact model memory use. It applies conservative
generation limits and refuses to start inference when the host reports too
little available RAM. A process-wide lock prevents concurrent requests through
this module from multiplying memory use.
"""

import contextlib
import ctypes
import os
import sys
import threading


DEFAULT_MIN_FREE_RAM_MB = 1536
DEFAULT_NUM_CTX = 2048
DEFAULT_NUM_PREDICT = 384
DEFAULT_NUM_BATCH = 128
DEFAULT_NUM_THREAD = 2

# Limits are intentionally conservative for an 8 GB host.
MAX_NUM_CTX = 4096
MAX_NUM_PREDICT = 1024
MAX_NUM_BATCH = 256
MAX_NUM_THREAD = 4

_INFERENCE_LOCK = threading.Lock()


class ResourceLimitError(RuntimeError):
    """Raised when a request would exceed the configured resource budget."""


def _bounded_env_int(name, default, minimum, maximum):
    """Read an integer environment setting and clamp it to safe bounds."""
    try:
        value = int(os.getenv(name, str(default)))
    except (TypeError, ValueError):
        value = default
    return max(minimum, min(value, maximum))


def available_memory_mb():
    """Return available physical RAM in MiB, or None if it cannot be measured."""
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
            if ctypes.windll.kernel32.GlobalMemoryStatusEx(
                ctypes.byref(status)
            ):
                return int(status.ullAvailPhys // (1024 * 1024))
        except (AttributeError, OSError):
            return None
        return None

    if sys.platform.startswith("linux"):
        try:
            with open("/proc/meminfo", encoding="ascii") as memory_info:
                for line in memory_info:
                    if line.startswith("MemAvailable:"):
                        return int(line.split()[1]) // 1024
        except (OSError, ValueError, IndexError):
            return None

    # Optional dependency: keep the project usable without psutil.
    try:
        import psutil  # type: ignore[import-not-found]

        return int(psutil.virtual_memory().available // (1024 * 1024))
    except (ImportError, AttributeError, OSError):
        return None


def generation_options():
    """Return bounded Ollama generation settings."""
    return {
        "num_ctx": _bounded_env_int(
            "JARVIS_OLLAMA_NUM_CTX", DEFAULT_NUM_CTX, 512, MAX_NUM_CTX
        ),
        "num_predict": _bounded_env_int(
            "JARVIS_OLLAMA_NUM_PREDICT",
            DEFAULT_NUM_PREDICT,
            64,
            MAX_NUM_PREDICT,
        ),
        "num_batch": _bounded_env_int(
            "JARVIS_OLLAMA_NUM_BATCH", DEFAULT_NUM_BATCH, 32, MAX_NUM_BATCH
        ),
        "num_thread": _bounded_env_int(
            "JARVIS_OLLAMA_NUM_THREAD", DEFAULT_NUM_THREAD, 1, MAX_NUM_THREAD
        ),
    }


def minimum_free_ram_mb():
    """Return the minimum free-RAM threshold (512–4096 MiB)."""
    return _bounded_env_int(
        "JARVIS_MIN_FREE_RAM_MB", DEFAULT_MIN_FREE_RAM_MB, 512, 4096
    )


def ensure_memory_headroom():
    """Refuse inference when measured free RAM is below the safety threshold.

    If the platform cannot report memory, generation remains bounded but the
    RAM preflight cannot be guaranteed; callers can inspect the returned None.
    """
    free_mb = available_memory_mb()
    if free_mb is not None and free_mb < minimum_free_ram_mb():
        raise ResourceLimitError(
            f"Inference paused: only {free_mb} MiB RAM is available; "
            f"Jarvis requires at least {minimum_free_ram_mb()} MiB free. "
            "Close memory-heavy apps or lower JARVIS_MIN_FREE_RAM_MB "
            "deliberately before retrying."
        )
    return free_mb


@contextlib.contextmanager
def inference_slot():
    """Serialize local inference and perform a RAM preflight before each call."""
    with _INFERENCE_LOCK:
        free_mb = ensure_memory_headroom()
        yield free_mb
