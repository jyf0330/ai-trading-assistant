import unittest
from unittest.mock import patch

from app_shell.local_ops import latest_price, normalize_symbol


class LocalOpsTest(unittest.TestCase):
    def test_normalize_symbol_for_a_share(self) -> None:
        self.assertEqual(normalize_symbol('600519'), '600519.SH')
        self.assertEqual(normalize_symbol('000001'), '000001.SZ')
        self.assertEqual(normalize_symbol('300750'), '300750.SZ')
        self.assertEqual(normalize_symbol('600519.SH'), '600519.SH')
        self.assertEqual(normalize_symbol('aapl'), 'AAPL')

    @patch('app_shell.local_ops._fetch_akshare_history')
    def test_latest_price_prefers_akshare_for_a_share(self, mock_fetch_akshare_history) -> None:
        mock_fetch_akshare_history.return_value = [
            {'Date': '2026-04-17', 'Close': 10.0},
            {'Date': '2026-04-18', 'Close': 11.5},
        ] * 35

        price, records, source = latest_price('600519')

        self.assertEqual(source, 'akshare')
        self.assertEqual(price, 11.5)
        self.assertTrue(records)


if __name__ == '__main__':
    unittest.main()
