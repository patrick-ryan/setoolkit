from typing import Optional, Tuple, List
import io
import os
import pathlib
import re
import tempfile
import gzip
import csv

import duckdb
import boto3
import chardet
import pandas as pd
import pyarrow as pa
import pyarrow.csv as pc
import pyarrow.dataset as ds


s3_client = boto3.client('s3')


def download_first_file(s3_uri):
    s3_path = s3_uri.split("s3://")[1]
    bucket, s3_key = s3_path.split("/", maxsplit=1)
    file = tempfile.NamedTemporaryFile()

    response = s3_client.list_objects_v2(Bucket=bucket, Prefix=s3_key)

    if 'Contents' not in response:
        print("No files found with the given prefix.")
        return None, None

    first_file_key = response['Contents'][0]['Key']
    print(f"Downloading {first_file_key}...")

    s3_client.download_fileobj(bucket, first_file_key, file)
    print(f"File downloaded to {file.name}")

    file.seek(0)

    return file, "gz" if first_file_key.endswith("gz") else "txt"


def custom_split(line):
    # Use regex to split on '|' only if it's NOT surrounded by spaces
    return re.split(r'(?<=\S)\|(?=.)|(?<=.)\|(?=\S)|^\||\|$', line.strip())


def custom_read_csv(file: io.BytesIO, override_dtype: Optional[dict] = None, encoding: Optional[str] = None):
    # Read file line by line
    lines = file.read().decode(encoding=encoding).split("\n")

    # Process the lines
    data = [custom_split(line) for line in lines if line.strip()]

    # Create DataFrame
    df = pd.DataFrame(data[1:], columns=data[0])  # First row is the header

    if override_dtype:
        return df.astype(override_dtype)
    else:
        return df


def file_to_table(file_path: str, table_name: str, override_dtype: Optional[dict] = None, encoding: Optional[str] = None):
    duckdb.sql(
        f"""
        INSTALL httpfs;
        LOAD httpfs;
        CREATE SECRET IF NOT EXISTS (
            TYPE S3,
            PROVIDER CREDENTIAL_CHAIN
        );

        drop table if exists {table_name};
        """
    )

    buffer = io.BytesIO()

    path = pathlib.Path(file_path)
    file = None
    file_type = None

    if file_path.startswith("s3://"):
        file, file_type = download_first_file(file_path)
        if not file:
            raise RuntimeError(f"expected file at {file_path}")
    else:
        file_type = "gz" if path.name.endswith("gz") else "txt"
        assert path.exists()

    try:
        new_path = pathlib.Path(file.name if file else path)

        if file_type == "gz":
            with gzip.open(new_path, "rb") as f:
                buffer.write(f.read().decode(encoding="ISO-8859-1").encode())
        else:
            buffer.write(new_path.read_bytes())

        buffer.seek(0)

        df = custom_read_csv(buffer, override_dtype=override_dtype, encoding=encoding)

        duckdb.sql(f"create table {table_name} as (SELECT * FROM df);")
    finally:
        if file:
            file.close()


def file_to_table_spark(file_path: str, table_name: str, override_dtype: Optional[dict] = None, encoding: Optional[str] = None):
    from pyspark.sql import SparkSession
    
    duckdb.sql(
        f"""
        INSTALL httpfs;
        LOAD httpfs;
        CREATE SECRET IF NOT EXISTS (
            TYPE S3,
            PROVIDER CREDENTIAL_CHAIN
        );

        drop table if exists {table_name};
        """
    )

    aws_access_key_id = os.environ['AWS_ACCESS_KEY_ID']
    aws_secret_access_key = os.environ['AWS_SECRET_ACCESS_KEY']
    session_token = os.environ['AWS_SESSION_TOKEN']

    session: SparkSession = (
        SparkSession.builder
        .master("local")
        .config("spark.jars.packages", "org.apache.hadoop:hadoop-aws:3.3.1")
        .config("spark.hadoop.fs.s3a.access.key", aws_access_key_id)
        .config("spark.hadoop.fs.s3a.secret.key", aws_secret_access_key)
        .config("spark.hadoop.fs.s3a.session.token", session_token)
        .config("spark.driver.memory", "12g")
        .config("spark.hadoop.fs.s3a.aws.credentials.provider", "org.apache.hadoop.fs.s3a.TemporaryAWSCredentialsProvider")
        .getOrCreate()
    )

    print(session.conf.get("spark.driver.memory"))

    df = session.read.csv(
        file_path,
        sep="|",
        header=True,
    ).toPandas()

    duckdb.sql(f"create table {table_name} as (SELECT * FROM df);")


def detect_csv_dialect(bucket, key) -> Tuple[chardet.ResultDict, csv.Dialect]:
    """
    Detect CSV dialect (delimiter, escape-char, etc) from S3 file
    """
    response = s3_client.get_object(Bucket=bucket, Key=key)
    sample_data = response["Body"].read(
        8192
    )  # Read only a small sample, enough to cover more than 1 line

    csv_encoding = chardet.detect(sample_data)

    sniffer = csv.Sniffer()
    csv_dialect = sniffer.sniff(sample_data.decode(csv_encoding["encoding"]))

    return csv_encoding, csv_dialect


def get_csv_headers(
    bucket, key, csv_encoding: chardet.ResultDict, csv_dialect: csv.Dialect
):
    """
    Get CSV headers from S3
    """
    response = s3_client.get_object(Bucket=bucket, Key=key)
    csv_data = response["Body"]

    cr = csv.reader(
        io.TextIOWrapper(csv_data, encoding=csv_encoding["encoding"]),
        dialect=csv_dialect,
    )
    header = next(cr)

    return header


def removeprefix(line: str, prefix: str):
    if line.startswith(prefix):
        return line[len(prefix):]
    return line


def parse_s3_uri(s3_uri: str):
    no_prefix = removeprefix(removeprefix(s3_uri, "s3://"), "s3a://")
    bucket, key = no_prefix.split("/", 1)
    return bucket, key


def read_pa_table(
    file_path: str,
    csv_encoding: chardet.ResultDict,
    csv_dialect: csv.Dialect,
    headers: List[str],
) -> pa.Table:
    dataset = ds.dataset(
        file_path,
        format=ds.CsvFileFormat(
            read_options=pc.ReadOptions(
                encoding=csv_encoding["encoding"],
                block_size=2097152,
            ),
            parse_options=pc.ParseOptions(
                delimiter=csv_dialect.delimiter,
                quote_char=csv_dialect.quotechar,
                double_quote=csv_dialect.doublequote,
                escape_char=csv_dialect.escapechar,
                newlines_in_values=True,
            ),
            convert_options=pc.ConvertOptions(
                column_types=pa.schema([(h, pa.string()) for h in headers]) if headers else None,
                strings_can_be_null=True,
            ),
        ),
    )

    # Scan each fragment and tag with its source file path
    tables = []
    for fragment in dataset.get_fragments():
        file_path = fragment.path
        table = fragment.to_table()
        # Add source_file column with the file path repeated for each row
        source_col = pa.array([file_path] * table.num_rows)
        table = table.append_column("source_file", source_col)
        tables.append(table)

    full_table = pa.concat_tables(tables)
    return full_table


def static_dialect():

    class dialect(csv.Dialect):
        _name = "sniffed"
        lineterminator = '\r\n'
        quoting = 0
        # escapechar = ''

    dialect.doublequote = True
    dialect.delimiter = "|"
    dialect.quotechar = '"'
    dialect.skipinitialspace = False

    return dialect


def file_to_table_pa(file_path: str, table_name: str, override_dtype: Optional[dict] = None, encoding: Optional[str] = None):
    duckdb.sql(
        f"""
        INSTALL httpfs;
        LOAD httpfs;
        CREATE SECRET IF NOT EXISTS (
            TYPE S3,
            PROVIDER CREDENTIAL_CHAIN
        );

        drop table if exists {table_name};
        """
    )

    data_bucket, data_key = parse_s3_uri(file_path)

    print(f"Sniffing CSV metadata for s3://{data_bucket}/{data_key}")
    csv_encoding, csv_dialect = detect_csv_dialect(data_bucket, data_key)

    print(f"Detected encoding {csv_encoding} & dialect {vars(csv_dialect)}")
    headers = get_csv_headers(data_bucket, data_key, csv_encoding, csv_dialect)

    # csv_encoding = chardet.resultdict.ResultDict(encoding=encoding)
    # csv_dialect = static_dialect()

    df = read_pa_table(file_path, csv_encoding, csv_dialect, headers)

    duckdb.sql(f"create table {table_name} as (SELECT * FROM df);")


