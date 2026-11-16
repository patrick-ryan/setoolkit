"""Regression coverage for plain and compressed CSV byte decoding."""

import gzip
import importlib.util
import io
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import boto3


spec = importlib.util.spec_from_file_location("encoding_db", Path(__file__).parents[1] / "db.py")
db = importlib.util.module_from_spec(spec)
with patch.object(boto3, "client"):
    spec.loader.exec_module(db)


class CsvEncodingTests(unittest.TestCase):
    def test_default_utf8(self):
        frame = db.custom_read_csv(io.BytesIO("name|count\ncafé 東京|2\n".encode()))
        self.assertEqual(frame.to_dict("records"), [{"name": "café 東京", "count": "2"}])

    def test_explicit_latin1_and_dtype(self):
        frame = db.custom_read_csv(
            io.BytesIO("name|count\ncafé|2\n".encode("latin-1")),
            encoding="latin-1",
            override_dtype={"count": int},
        )
        self.assertEqual(frame.to_dict("records"), [{"name": "café", "count": 2}])

    def test_invalid_utf8_is_not_silently_replaced(self):
        with self.assertRaises(UnicodeDecodeError):
            db.custom_read_csv(io.BytesIO(b"name\n\xff\n"))

    def test_plain_and_gzip_preserve_requested_encoding(self):
        for encoding, name in [(None, "café 東京"), ("latin-1", "café"), ("utf-16", "東京")]:
            for compressed in [False, True]:
                with self.subTest(encoding=encoding, compressed=compressed):
                    with tempfile.TemporaryDirectory() as temp:
                        source = Path(temp) / ("input.gz" if compressed else "input.txt")
                        data = f"name|count\n{name}|2\n".encode(encoding or "utf-8")
                        source.write_bytes(gzip.compress(data) if compressed else data)
                        frames = []
                        original_reader = db.custom_read_csv

                        def read(*args, **kwargs):
                            frame = original_reader(*args, **kwargs)
                            frames.append(frame)
                            return frame

                        with patch.object(db.duckdb, "sql"), patch.object(db, "custom_read_csv", side_effect=read):
                            db.file_to_table(str(source), "example", encoding=encoding)
                        self.assertEqual(frames[0].to_dict("records"), [{"name": name, "count": "2"}])

    def test_s3_gzip_preserves_utf8(self):
        source = tempfile.NamedTemporaryFile()
        self.addCleanup(source.close)
        source.write(gzip.compress("name\ncafé 東京\n".encode()))
        source.flush()
        with patch.object(db, "download_first_file", return_value=(source, "gz")), patch.object(db.duckdb, "sql"), patch.object(db, "custom_read_csv", wraps=db.custom_read_csv) as read:
            db.file_to_table("s3://bucket/input.gz", "example")
        self.assertEqual(read.call_count, 1)
        buffer = read.call_args.args[0]
        buffer.seek(0)
        self.assertEqual(db.custom_read_csv(buffer).iloc[0, 0], "café 東京")
        self.assertTrue(source.closed)
