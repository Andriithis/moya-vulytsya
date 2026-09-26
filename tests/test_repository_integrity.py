"""Незавершене злиття не повинне проходити перевірки репозиторію."""
from pathlib import Path
import re
import subprocess
import unittest


class RepositoryIntegrityTests(unittest.TestCase):
    def test_tracked_text_has_no_merge_conflicts(self):
        root = Path(__file__).resolve().parents[1]
        paths = subprocess.check_output(
            ['git', 'ls-files', '-z'], cwd=root).decode().split('\0')
        marker = re.compile(r'^(?:<{7} |={7}$|>{7} |\|{7} )', re.MULTILINE)
        conflicts = []
        for name in filter(None, paths):
            path = root / name
            if not path.is_file():
                continue
            raw = path.read_bytes()
            if b'\0' in raw:
                continue
            try:
                content = raw.decode('utf-8-sig').replace('\r\n', '\n')
            except UnicodeDecodeError:
                continue
            if marker.search(content):
                conflicts.append(name)
        self.assertEqual(conflicts, [], 'Залишилися маркери конфлікту злиття')
