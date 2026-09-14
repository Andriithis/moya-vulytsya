"""Приватні робочі файли не мають входити до дерева Git."""
from pathlib import Path
import subprocess
import unittest


class PrivateArtifactTests(unittest.TestCase):
    def test_git_contains_no_private_artifacts(self):
        root = Path(__file__).resolve().parents[1]
        tracked = subprocess.check_output(
            ['git', 'ls-files', '-z'], cwd=root).decode().split('\0')
        forbidden = [p for p in tracked if p and (
            p == 'FABULA_REZULTAT.txt' or p == 'data/fabuly.csv.gz'
            or p.startswith('private/')
            or any(p.endswith(s) for s in ('.db', '.db.gz', '.sqlite', '.sqlite3', '.rtf'))
            or '.db-wal' in p or '.db-shm' in p)]
        self.assertEqual(forbidden, [])
