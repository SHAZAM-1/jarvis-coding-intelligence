"""Tests for resource budgeting without loading a model or reading host RAM."""

import os
import unittest
from unittest.mock import patch

from src import resource_guard
from src.resource_guard import (
    ResourceLimitError,
    ensure_memory_headroom,
    generation_options,
    inference_slot,
)


class ResourceGuardTests(unittest.TestCase):
    @patch("src.resource_guard.available_memory_mb", return_value=800)
    @patch("src.resource_guard.minimum_free_ram_mb", return_value=1536)
    def test_low_memory_blocks_inference(self, _threshold, _available):
        with self.assertRaisesRegex(ResourceLimitError, "Inference paused"):
            ensure_memory_headroom()

    @patch("src.resource_guard.available_memory_mb", return_value=2048)
    @patch("src.resource_guard.minimum_free_ram_mb", return_value=1536)
    def test_sufficient_memory_allows_inference(self, _threshold, _available):
        self.assertEqual(ensure_memory_headroom(), 2048)

    @patch("src.resource_guard.available_memory_mb", return_value=None)
    def test_unknown_memory_keeps_bounded_fallback(self, _available):
        self.assertIsNone(ensure_memory_headroom())

    def test_generation_options_are_conservative_by_default(self):
        with patch.dict(os.environ, {}, clear=True):
            options = generation_options()
        self.assertEqual(options["num_ctx"], 2048)
        self.assertEqual(options["num_predict"], 384)
        self.assertEqual(options["num_batch"], 128)
        self.assertEqual(options["num_thread"], 2)

    def test_generation_options_are_clamped(self):
        settings = {
            "JARVIS_OLLAMA_NUM_CTX": "999999",
            "JARVIS_OLLAMA_NUM_PREDICT": "999999",
            "JARVIS_OLLAMA_NUM_BATCH": "999999",
            "JARVIS_OLLAMA_NUM_THREAD": "999999",
        }
        with patch.dict(os.environ, settings, clear=True):
            options = generation_options()
        self.assertEqual(options["num_ctx"], 4096)
        self.assertEqual(options["num_predict"], 1024)
        self.assertEqual(options["num_batch"], 256)
        self.assertEqual(options["num_thread"], 4)

    @patch("src.resource_guard.available_memory_mb", return_value=2048)
    @patch("src.resource_guard.minimum_free_ram_mb", return_value=1536)
    def test_inference_slot_yields_measured_memory(self, _threshold, _available):
        with inference_slot() as free_mb:
            self.assertEqual(free_mb, 2048)


if __name__ == "__main__":
    unittest.main(verbosity=2)
