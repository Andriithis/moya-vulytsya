"""Синтетична перевірка приватності сліпої форми."""
import hashlib
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from pipeline.qa_review_form import build


class ReviewFormTests(unittest.TestCase):
    def test_blind_escaped_payload_and_no_overwrite(self):
        with tempfile.TemporaryDirectory() as td:
            p = Path(td)
            text = '</script><script>alert(1)</script>\r\nСинтетичний текст'
            row = dict(doc_id='1', source_row_hash='a'*64, text=text,
                       text_sha256=hashlib.sha256(text.encode()).hexdigest(),
                       prediction='SECRET_PREDICTION', notes='SECRET_NOTES')
            source = p / 'review-ready.jsonl'
            source.write_text(json.dumps(row)+'\n', encoding='utf-8')
            before = source.read_bytes()
            with patch('pipeline.qa_review_form.PRIVATE', p):
                self.assertEqual(build(source, p/'form.html')['documents'], 1)
                html = (p/'form.html').read_text(encoding='utf-8')
                self.assertNotIn('</script><script>alert', html)
                self.assertNotIn('SECRET_', html)
                self.assertIn("connect-src 'none'", html)
                with self.assertRaises(FileExistsError):
                    build(source, p/'form.html')
                self.assertEqual(source.read_bytes(), before)
                row['text'] = 'Змінено'
                source.write_text(json.dumps(row), encoding='utf-8')
                with self.assertRaises(ValueError):
                    build(source, p/'invalid.html')
                self.assertFalse((p/'invalid.html').exists())

    def test_public_paths_rejected(self):
        with self.assertRaises(ValueError):
            build('data/review-ready.jsonl', 'private/form.html')
        with self.assertRaises(ValueError):
            build('private/review-ready.jsonl', 'public/form.html')
