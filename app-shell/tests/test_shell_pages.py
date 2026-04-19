import unittest

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

    def test_paper_page_renders(self) -> None:
        response = self.client.get('/paper')
        self.assertEqual(response.status_code, 200)
        self.assertIn('模拟盘', response.text)


if __name__ == '__main__':
    unittest.main()
