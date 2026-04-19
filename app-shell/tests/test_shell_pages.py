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
