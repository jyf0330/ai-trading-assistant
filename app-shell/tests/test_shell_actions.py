import unittest
from unittest.mock import patch

from fastapi.testclient import TestClient

from app_shell.main import app


class ShellActionsTest(unittest.TestCase):
    def setUp(self) -> None:
        self.client = TestClient(app)

    @patch("app_shell.main.run_ma_strategy")
    def test_paper_strategy_run_displays_result(self, mock_run_ma_strategy) -> None:
        mock_run_ma_strategy.return_value = {
            "symbol": "AAPL",
            "action": "buy",
            "signal": "golden_cross",
            "price": 180.5,
            "quantity": 5,
            "message": "Executed buy for AAPL",
        }

        response = self.client.post(
            "/paper/strategy-run",
            data={"symbol": "AAPL", "allocation": "1000"},
        )

        self.assertEqual(response.status_code, 200)
        self.assertIn("golden_cross", response.text)
        self.assertIn("Executed buy for AAPL", response.text)

    @patch("app_shell.main.run_tradingagents_analysis")
    def test_analysis_run_displays_result(self, mock_run_tradingagents_analysis) -> None:
        mock_run_tradingagents_analysis.return_value = {
            "symbol": "NVDA",
            "trade_date": "2026-04-19",
            "summary": "偏多，关注高波动风险",
            "model": "qwen3.6:35b-a3b-q4_K_M",
            "result_path": "/tmp/nvda.json",
        }

        response = self.client.post(
            "/analysis/run",
            data={"symbol": "NVDA", "trade_date": "2026-04-19"},
        )

        self.assertEqual(response.status_code, 200)
        self.assertIn("偏多，关注高波动风险", response.text)
        self.assertIn("qwen3.6:35b-a3b-q4_K_M", response.text)

    @patch("app_shell.main.run_a_share_analysis")
    @patch("app_shell.main.run_tradingagents_analysis")
    def test_analysis_run_uses_a_share_path(self, mock_run_tradingagents_analysis, mock_run_a_share_analysis) -> None:
        mock_run_a_share_analysis.return_value = {
            "symbol": "600519.SH",
            "trade_date": "2026-04-19",
            "summary": "A股本地分析：偏中性",
            "model": "qwen3.6:35b-a3b-q4_K_M",
            "result_path": "/tmp/600519.json",
        }

        response = self.client.post(
            "/analysis/run",
            data={"symbol": "600519", "trade_date": "2026-04-19"},
        )

        self.assertEqual(response.status_code, 200)
        mock_run_a_share_analysis.assert_called_once()
        mock_run_tradingagents_analysis.assert_not_called()
        self.assertIn("600519.SH", response.text)
        self.assertIn("A股本地分析：偏中性", response.text)


if __name__ == "__main__":
    unittest.main()
