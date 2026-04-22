import unittest
from unittest.mock import patch

from app_shell.local_ops import _build_tradingagents_command, latest_price, normalize_symbol


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

    @patch('app_shell.local_ops.shutil.which', return_value='/bin/bash')
    @patch('app_shell.local_ops.os.name', 'posix')
    def test_build_tradingagents_command_uses_bash_on_posix(self, _mock_which) -> None:
        command = _build_tradingagents_command('NVDA', '2026-04-19')

        self.assertEqual(command[0], 'bash')
        self.assertTrue(command[1].endswith('scripts/run-tradingagents-local.sh'))
        self.assertEqual(command[2:], ['NVDA', '2026-04-19'])

    @patch('app_shell.local_ops._windows_wsl_project_root', return_value='/mnt/c/workspace/ai-trading-assistant')
    @patch('app_shell.local_ops.shutil.which', return_value='C:\\Windows\\System32\\wsl.exe')
    @patch('app_shell.local_ops.os.name', 'nt')
    def test_build_tradingagents_command_uses_wsl_on_windows(self, _mock_which, _mock_root) -> None:
        command = _build_tradingagents_command('NVDA', '2026-04-19')

        self.assertEqual(command[:3], ['wsl.exe', 'bash', '-lc'])
        self.assertIn('cd /mnt/c/workspace/ai-trading-assistant', command[3])
        self.assertIn('./scripts/run-tradingagents-local.sh NVDA 2026-04-19', command[3])


if __name__ == '__main__':
    unittest.main()
