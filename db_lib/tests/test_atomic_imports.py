"""Run with: python -m unittest discover -s db_lib/tests -p test_atomic_imports.py."""

import importlib.util
import inspect
import os
from pathlib import Path
import re
import sys
import tempfile
from types import ModuleType, SimpleNamespace
import unittest
from unittest.mock import Mock, patch

import boto3
import duckdb
import pandas as pd
import pyarrow as pa


spec = importlib.util.spec_from_file_location("atomic_db", Path(__file__).parents[1] / "db.py")
db = importlib.util.module_from_spec(spec)
with patch.object(boto3, "client"):
    spec.loader.exec_module(db)


class AtomicImportTests(unittest.TestCase):
    def setUp(self):
        self.connection = duckdb.connect()
        self.addCleanup(self.connection.close)
        self.connection.sql("CREATE TABLE destination AS SELECT 'original' AS value")
        self.fail_create = False
        sql_patch = patch.object(db.duckdb, "sql", side_effect=self.execute_sql)
        sql_patch.start()
        self.addCleanup(sql_patch.stop)
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.source = Path(self.temp.name) / "input.txt"
        self.source.write_text("value\nreplacement\n")

    def execute_sql(self, query):
        # Skip network-dependent extension setup, but execute every table mutation.
        query = re.sub(r"INSTALL httpfs;|LOAD httpfs;|CREATE SECRET IF NOT EXISTS \(.*?\);", "", query, flags=re.S)
        if "SELECT * FROM df" in query:
            if self.fail_create:
                query = query.replace("SELECT * FROM df", "SELECT CAST('invalid' AS INTEGER) AS value")
            else:
                frame = inspect.currentframe()
                try:
                    while frame and "df" not in frame.f_locals:
                        frame = frame.f_back
                    self.connection.register("df", frame.f_locals["df"])
                finally:
                    del frame
        if query.strip():
            return self.connection.sql(query)

    def assert_original(self):
        self.assertEqual(self.connection.sql("SELECT * FROM destination").fetchall(), [("original",)])

    def test_missing_file_preserves_destination(self):
        with self.assertRaises((AssertionError, FileNotFoundError)):
            db.file_to_table(str(self.source.with_name("missing.txt")), "destination", encoding="utf-8")
        self.assert_original()

    def test_failed_decoding_preserves_destination(self):
        self.source.write_bytes(b"value\n\xff\n")
        with self.assertRaises(UnicodeDecodeError):
            db.file_to_table(str(self.source), "destination", encoding="utf-8")
        self.assert_original()

    def test_successful_load_replaces_destination(self):
        db.file_to_table(str(self.source), "destination", encoding="utf-8")
        self.assertEqual(self.connection.sql("SELECT * FROM destination").fetchall(), [("replacement",)])

    def test_failed_create_preserves_destination(self):
        self.fail_create = True
        with self.assertRaises(duckdb.ConversionException):
            db.file_to_table(str(self.source), "destination", encoding="utf-8")
        self.assert_original()

    def test_arrow_failure_preserves_destination(self):
        with patch.object(db, "detect_csv_dialect", side_effect=OSError("download failed")):
            with self.assertRaises(OSError):
                db.file_to_table_pa("s3://bucket/input", "destination")
        self.assert_original()

    def test_arrow_success_replaces_destination(self):
        with patch.object(db, "detect_csv_dialect", return_value=({}, SimpleNamespace())), patch.object(db, "get_csv_headers", return_value=["value"]), patch.object(db, "read_pa_table", return_value=pa.table({"value": ["replacement"]})):
            db.file_to_table_pa("s3://bucket/input", "destination")
        self.assertEqual(self.connection.sql("SELECT * FROM destination").fetchall(), [("replacement",)])

    def spark_modules(self, failure=False):
        session = Mock()
        if failure:
            session.read.csv.side_effect = OSError("read failed")
        else:
            session.read.csv.return_value.toPandas.return_value = pd.DataFrame({"value": ["replacement"]})
        builder = Mock()
        builder.master.return_value = builder
        builder.config.return_value = builder
        builder.getOrCreate.return_value = session
        module = ModuleType("pyspark.sql")
        module.SparkSession = SimpleNamespace(builder=builder)
        return {"pyspark": ModuleType("pyspark"), "pyspark.sql": module}

    def test_spark_failure_preserves_destination(self):
        with patch.dict(sys.modules, self.spark_modules(failure=True)), patch.dict(os.environ, AWS_ACCESS_KEY_ID="test", AWS_SECRET_ACCESS_KEY="test", AWS_SESSION_TOKEN="test"):
            with self.assertRaises(OSError):
                db.file_to_table_spark("s3a://bucket/input", "destination")
        self.assert_original()

    def test_spark_success_replaces_destination(self):
        with patch.dict(sys.modules, self.spark_modules()), patch.dict(os.environ, AWS_ACCESS_KEY_ID="test", AWS_SECRET_ACCESS_KEY="test", AWS_SESSION_TOKEN="test"):
            db.file_to_table_spark("s3a://bucket/input", "destination")
        self.assertEqual(self.connection.sql("SELECT * FROM destination").fetchall(), [("replacement",)])
