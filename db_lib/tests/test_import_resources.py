import csv
import importlib.util
import io
from pathlib import Path
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

import boto3
import pyarrow as pa


def load_db():
    spec = importlib.util.spec_from_file_location("resources_db", Path(__file__).parents[1] / "db.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class ImportResourceTests(unittest.TestCase):
    def setUp(self):
        with patch.object(boto3, "client"):
            self.db = load_db()

    def test_import_does_not_create_aws_client(self):
        with patch.object(boto3, "client", side_effect=AssertionError("AWS accessed on import")):
            load_db()

    def test_client_is_created_once_on_demand(self):
        with patch.object(boto3, "client") as client:
            first = self.db.get_s3_client()
            self.assertIs(first, self.db.get_s3_client())
            client.assert_called_once_with("s3")

    def test_no_matching_objects_does_not_open_temp_file(self):
        client = Mock()
        client.list_objects_v2.return_value = {}
        with patch.object(self.db, "get_s3_client", return_value=client), patch.object(self.db.tempfile, "NamedTemporaryFile") as temporary:
            self.assertEqual(self.db.download_first_file("s3://bucket/prefix"), (None, None))
        temporary.assert_not_called()

    def test_download_failure_closes_temp_file(self):
        client = Mock()
        client.list_objects_v2.return_value = {"Contents": [{"Key": "input.csv"}]}
        client.download_fileobj.side_effect = OSError("download failed")
        temporary = Mock()
        with patch.object(self.db, "get_s3_client", return_value=client), patch.object(self.db.tempfile, "NamedTemporaryFile", return_value=temporary):
            with self.assertRaises(OSError):
                self.db.download_first_file("s3://bucket/prefix")
        temporary.close.assert_called_once()

    def test_sniffing_and_headers_close_response_bodies(self):
        for operation in ["detect_csv_dialect", "get_csv_headers"]:
            with self.subTest(operation=operation):
                body = io.BytesIO(b"name|count\nhello|2\n")
                client = Mock()
                client.get_object.return_value = {"Body": body}
                with patch.object(self.db, "get_s3_client", return_value=client):
                    if operation == "detect_csv_dialect":
                        self.db.detect_csv_dialect("bucket", "key")
                    else:
                        headers = self.db.get_csv_headers("bucket", "key", {"encoding": "utf-8"}, csv.excel)
                        self.assertEqual(headers, ["name|count"])
                self.assertTrue(body.closed)

    def test_fragments_are_concatenated_in_path_order(self):
        fragments = [
            SimpleNamespace(path="z.csv", to_table=lambda: pa.table({"name": ["last"]})),
            SimpleNamespace(path="a.csv", to_table=lambda: pa.table({"name": ["first"]})),
        ]
        dataset = SimpleNamespace(get_fragments=lambda: iter(fragments))
        with patch.object(self.db.ds, "dataset", return_value=dataset):
            result = self.db.read_pa_table("unused", {"encoding": "utf-8"}, csv.excel, ["name"])
        self.assertEqual(result.to_pydict(), {"name": ["first", "last"], "source_file": ["a.csv", "z.csv"]})
