"""Unit tests for market data parsing and safe HTML rendering (offline)."""
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from market_pulse import render_market_pulse
from update_market_pulse import calculate_rent_growth, parse_metric_csv, refresh


class MarketPulseTests(unittest.TestCase):
    def test_rent_growth_seattle_and_us(self):
        content = (
            "RegionName,2024-01-31,2025-01-31,2025-02-28\n"
            "Seattle-Tacoma-Bellevue, WA,100,105,106\n"
        )
        # Quoted metro names containing commas are supported by standard CSV parsing.
        content = (
            "RegionName,2024-01-31,2025-01-31\n"
            '"Seattle-Tacoma-Bellevue, WA",100,105\n'
            '"United States",100,103\n'
        )
        result = calculate_rent_growth(content)
        self.assertEqual(result["series"][-1]["seattle"], 5.0)
        self.assertEqual(result["series"][-1]["us"], 3.0)

    def test_vacancy_fraction_converted_to_percentage(self):
        csv_text = 'RegionName,2025-01-01\n"Seattle-Tacoma-Bellevue, WA",0.062\n'
        result = parse_metric_csv(csv_text, "vacancy")
        self.assertAlmostEqual(result["series"][0]["seattle"], 6.2)

    def test_missing_cache_yields_four_empty_cards(self):
        with tempfile.TemporaryDirectory() as temp:
            document = render_market_pulse(Path(temp) / "missing.json")
            self.assertEqual(document.count('class="market-pulse-card"'), 4)
            self.assertIn("No cached observations yet", document)
            self.assertNotIn("+1.8%", document)

    def test_offline_refresh_without_sources_keeps_cache_unchanged(self):
        with tempfile.TemporaryDirectory() as temp:
            cache = Path(temp) / "cache.json"
            sources = Path(temp) / "sources"
            self.assertFalse(refresh(no_download=True, cache_path=cache, source_dir=sources))
            self.assertFalse(cache.exists())


if __name__ == "__main__":
    unittest.main()
