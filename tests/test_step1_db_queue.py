import unittest
from unittest.mock import patch

from pipeline.postgres_tasks import PendingDocument, PendingWork
import src.step1_download as step1


class Step1DatabaseQueueTests(unittest.TestCase):
    def test_known_categories_become_tasks_and_unknown_are_skipped(self):
        work = PendingWork(
            active=[
                PendingDocument(
                    doc_id="100",
                    court_code="2601",
                    category_code="41235",
                    date="2026-09-01",
                    doc_url="https://example.invalid/100",
                ),
                PendingDocument(
                    doc_id="101",
                    court_code="2601",
                    category_code="unknown-category",
                    date="2026-09-02",
                    doc_url="https://example.invalid/101",
                ),
            ],
            inactive_ids=["99"],
        )

        with patch("pipeline.postgres_tasks.load_pending_work", return_value=work) as load:
            tasks, inactive, skipped = step1.load_tasks_from_postgres("postgres://test")

        load.assert_called_once_with("postgres://test", step1.COURTS.keys())
        self.assertEqual([r["doc_id"] for r in tasks], ["100"])
        self.assertEqual(tasks[0]["court"], "Golosiivskyi")
        self.assertEqual(tasks[0]["group"], "ГП")
        self.assertEqual(inactive, ["99"])
        self.assertEqual(skipped, ["101"])

    def test_domestic_theme_is_never_public_step1_work(self):
        self.assertIn("ДОМ", step1.SKIP)


if __name__ == "__main__":
    unittest.main()
