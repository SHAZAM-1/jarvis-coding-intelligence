"""Offline tests for resource sampling; no model or host load is created."""

import unittest
from types import SimpleNamespace
from unittest.mock import patch

from src.resource_metrics import (
    ResourceSampler,
    _cpu_counters,
    _total_physical_memory_mb,
)


class ResourceSamplerTests(unittest.TestCase):
    @patch("src.resource_metrics._total_physical_memory_mb", return_value=8000)
    @patch(
        "src.resource_metrics.available_memory_mb",
        side_effect=[1000, 700],
    )
    @patch(
        "src.resource_metrics._cpu_counters",
        side_effect=[(1000, 200), (2000, 400)],
    )
    def test_reports_ram_pressure_and_system_cpu(
        self, _cpu, _available, _total
    ):
        with ResourceSampler(interval_seconds=60) as sampler:
            pass

        report = sampler.report()
        self.assertEqual(report["measurement_scope"], "system_wide_not_model_process_attributed")
        self.assertEqual(report["total_ram_mb"], 8000)
        self.assertEqual(report["available_ram_before_mb"], 1000)
        self.assertEqual(report["available_ram_min_mb"], 700)
        self.assertEqual(report["available_ram_after_mb"], 700)
        self.assertEqual(report["available_ram_drop_from_start_mb"], 300)
        self.assertEqual(report["estimated_peak_system_ram_used_mb"], 7300)
        self.assertEqual(report["system_cpu_average_percent"], 80.0)
        self.assertEqual(report["system_cpu_peak_percent"], 80.0)
        self.assertEqual(report["memory_sample_count"], 2)
        self.assertEqual(report["cpu_interval_sample_count"], 1)
        self.assertTrue(report["limitations"])

    @patch("src.resource_metrics._total_physical_memory_mb", return_value=None)
    @patch("src.resource_metrics.available_memory_mb", return_value=None)
    @patch("src.resource_metrics._cpu_counters", return_value=None)
    def test_unavailable_counters_are_null_not_guessed(
        self, _cpu, _available, _total
    ):
        with ResourceSampler(interval_seconds=60) as sampler:
            pass

        report = sampler.report()
        self.assertIsNone(report["total_ram_mb"])
        self.assertIsNone(report["available_ram_before_mb"])
        self.assertIsNone(report["available_ram_min_mb"])
        self.assertIsNone(report["estimated_peak_system_ram_used_mb"])
        self.assertIsNone(report["system_cpu_average_percent"])
        self.assertEqual(report["memory_sample_count"], 0)

    @patch("src.resource_metrics.sys.platform", "win32")
    @patch(
        "src.resource_metrics.ctypes.windll",
        new_callable=lambda: SimpleNamespace(
            kernel32=SimpleNamespace(
                GlobalMemoryStatusEx=lambda pointer: (
                    setattr(pointer._obj, "ullTotalPhys", 8 * 1024 * 1024 * 1024) or 1
                )
            )
        ),
        create=True,
    )
    def test_windows_total_ram_uses_global_memory_status(self, _windll):
        self.assertEqual(_total_physical_memory_mb(), 8192)

    @patch("src.resource_metrics.sys.platform", "win32")
    @patch(
        "src.resource_metrics.ctypes.windll",
        new_callable=lambda: SimpleNamespace(
            kernel32=SimpleNamespace(
                GetSystemTimes=lambda idle, kernel, user: (
                    setattr(idle._obj, "dwLowDateTime", 100) or
                    setattr(kernel._obj, "dwLowDateTime", 500) or
                    setattr(user._obj, "dwLowDateTime", 500) or 1
                )
            )
        ),
        create=True,
    )
    def test_windows_cpu_counter_reads_system_times(self, _windll):
        self.assertEqual(_cpu_counters(), (1000, 100))

    def test_rejects_invalid_sampling_interval(self):
        for interval in (0, -1, float("nan"), float("inf"), True, 61):
            with self.subTest(interval=interval):
                with self.assertRaises(ValueError):
                    ResourceSampler(interval_seconds=interval)


if __name__ == "__main__":
    unittest.main(verbosity=2)
