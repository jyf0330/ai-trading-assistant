import unittest
from unittest.mock import patch

from fastapi.testclient import TestClient

from app_shell.main import app


class ShellPagesTest(unittest.TestCase):
    def setUp(self) -> None:
        self.client = TestClient(app)

    def test_home_has_primary_nav_links(self) -> None:
        response = self.client.get('/')
        self.assertEqual(response.status_code, 200)
        body = response.text
        self.assertIn('href="/records"', body)
        self.assertIn('href="/analysis"', body)
        self.assertIn('href="/paper"', body)

    def test_records_page_renders(self) -> None:
        response = self.client.get('/records')
        self.assertEqual(response.status_code, 200)
        self.assertIn('交易记录', response.text)

    def test_analysis_page_renders(self) -> None:
        response = self.client.get('/analysis')
        self.assertEqual(response.status_code, 200)
        self.assertIn('股票分析', response.text)

    def test_records_page_prefers_exported_data(self) -> None:
        from unittest.mock import patch

        exported = {
            'db_path': '/tmp/journedge.db',
            'summary': {'trade_count': 2, 'account_count': 1, 'total_pnl': 500, 'win_count': 1, 'loss_count': 1, 'tag_frequency': [{'name': 'breakout', 'count': 1}]},
            'recent_trades': [{'date': '2026-04-20', 'symbol': '600519.SH', 'direction': 'long', 'type': 'stock', 'quantity': 100, 'pnl': 500, 'status': 'WIN', 'tags_list': ['breakout']}],
            'accounts': [{'name': 'Main', 'broker': 'TestBroker', 'initialBalance': 10000, 'currency': 'USD'}],
        }
        with patch('app_shell.main.load_exported_journedge', return_value=exported):
            response = self.client.get('/records')
        self.assertEqual(response.status_code, 200)
        self.assertIn('600519.SH', response.text)
        self.assertIn('breakout', response.text)
        self.assertIn('/tmp/journedge.db', response.text)

    def test_behavior_page_renders(self) -> None:
        response = self.client.get('/behavior')
        self.assertEqual(response.status_code, 200)
        self.assertIn('行为画像', response.text)

    def test_analysis_page_shows_local_ollama_model(self) -> None:
        tradingagents_snapshot = {
            'status': 'ready_local_model',
            'ollama': {
                'reachable': True,
                'host': 'http://172.26.208.1:11434',
                'models': [{'name': 'qwen3.6:35b-a3b-q4_K_M'}],
            },
            'recent_result_files': [],
            'results_dir': '/tmp/results',
            'cache_dir': '/tmp/cache',
            'env_status': {},
        }
        vectorbt_snapshot = {'example_files': []}
        with patch('app_shell.main.load_snapshot', side_effect=[tradingagents_snapshot, vectorbt_snapshot]):
            response = self.client.get('/analysis')
        self.assertEqual(response.status_code, 200)
        self.assertIn('qwen3.6:35b-a3b-q4_K_M', response.text)
        self.assertIn('172.26.208.1:11434', response.text)

    def test_paper_page_renders(self) -> None:
        response = self.client.get('/paper')
        self.assertEqual(response.status_code, 200)
        self.assertIn('模拟盘', response.text)


if __name__ == '__main__':
    unittest.main()
