import csv
import tempfile
import unittest
import zipfile
from pathlib import Path

from pipeline.edrsr_snapshot import iter_documents, sha256_file


class EdrsrSnapshotTests(unittest.TestCase):
    def make_zip(self, rows):
        td = tempfile.TemporaryDirectory()
        root = Path(td.name)
        tsv = root / "documents.csv"
        with tsv.open("w", encoding="utf-8", newline="") as fh:
            writer = csv.writer(fh, delimiter="\t", lineterminator="\n")
            writer.writerow([
                "doc_id", "court_code", "judgment_code", "justice_kind",
                "category_code", "cause_num", "adjudication_date",
                "receipt_date", "judge", "doc_url", "status", "date_publ",
            ])
            writer.writerows(rows)
        archive = root / "edrsr_data_2026.zip"
        with zipfile.ZipFile(archive, "w", zipfile.ZIP_DEFLATED) as zf:
            zf.write(tsv, "documents.csv")
        return td, archive

    def test_parses_known_fields_and_hashes_row(self):
        row = [
            "123", "2601", "1", "2", "cat", "case-1",
            "2026-09-01 00:00:00", "2026-09-02 00:00:00", "Judge",
            "https://example.test/doc/123", "1", "2026-09-03 12:00:00",
        ]
        td, archive = self.make_zip([row])
        self.addCleanup(td.cleanup)

        docs = list(iter_documents(archive))
        self.assertEqual(len(docs), 1)
        doc = docs[0]
        self.assertEqual(doc.doc_id, "123")
        self.assertEqual(doc.court_code, "2601")
        self.assertEqual(doc.adjudication_date, "2026-09-01")
        self.assertEqual(doc.status, 1)
        self.assertEqual(len(doc.source_row_hash), 64)
        self.assertEqual(len(sha256_file(archive)), 64)

    def test_rejects_invalid_status(self):
        row = [
            "123", "2601", "1", "2", "cat", "case-1",
            "2026-09-01", "2026-09-02", "Judge",
            "https://example.test/doc/123", "9", "2026-09-03",
        ]
        td, archive = self.make_zip([row])
        self.addCleanup(td.cleanup)

        with self.assertRaisesRegex(ValueError, "unexpected status"):
            list(iter_documents(archive))


if __name__ == "__main__":
    unittest.main()
