import sqlite3
import tempfile
import unittest
from pathlib import Path

from app_shell.journedge_export import load_journedge_export, render_journedge_markdown


class JournedgeExportTest(unittest.TestCase):
    def test_export_reads_accounts_trades_and_tags(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            db_path = Path(tmp) / 'journedge.db'
            conn = sqlite3.connect(db_path)
            cur = conn.cursor()
            cur.execute('CREATE TABLE Account (id TEXT PRIMARY KEY, name TEXT, broker TEXT, initialBalance REAL, currency TEXT, createdAt TEXT)')
            cur.execute('CREATE TABLE Trade (id TEXT PRIMARY KEY, date TEXT, symbol TEXT, underlying TEXT, type TEXT, direction TEXT, optionType TEXT, strike REAL, expiry TEXT, quantity REAL, entryPrice REAL, exitPrice REAL, commission REAL, fees REAL, pnl REAL, status TEXT, entryTime TEXT, exitTime TEXT, rr TEXT, mae REAL, mfe REAL, tags TEXT DEFAULT "[]", journalEntry TEXT, link TEXT, imageUrls TEXT DEFAULT "[]", accountId TEXT, createdAt TEXT)')
            cur.execute('CREATE TABLE Tag (id TEXT PRIMARY KEY, name TEXT UNIQUE)')
            cur.execute("INSERT INTO Account VALUES ('acc1','Main','TestBroker',10000,'USD','2026-04-20T10:00:00')")
            cur.execute("INSERT INTO Tag VALUES ('t1','breakout')")
            cur.execute("INSERT INTO Trade VALUES ('tr1','2026-04-19','600519.SH','600519.SH','stock','long',NULL,NULL,NULL,100,1500,1510,1,0,900,'WIN',NULL,NULL,NULL,NULL,NULL,'[\"breakout\"]','note',NULL,'[]','acc1','2026-04-20T11:00:00')")
            conn.commit()
            conn.close()

            payload = load_journedge_export(db_path)
            markdown = render_journedge_markdown(payload)

            self.assertEqual(payload['summary']['trade_count'], 1)
            self.assertEqual(payload['summary']['account_count'], 1)
            self.assertEqual(payload['accounts'][0]['name'], 'Main')
            self.assertEqual(payload['tags'][0]['name'], 'breakout')
            self.assertEqual(payload['recent_trades'][0]['symbol'], '600519.SH')
            self.assertIn('600519.SH', markdown)
            self.assertIn('breakout', markdown)


if __name__ == '__main__':
    unittest.main()
