# Database helpers

Requires Python 3.9 or newer. Install in a dedicated virtual environment:

```sh
python -m pip install ./db_lib
```

The distribution is named `setoolkit-db` and the Python module remains `db`.
It can be installed alongside the separate `setoolkit-cli` distribution.
The installation includes DuckDB, boto3, pandas, chardet, and PyArrow. pandas
2.2 provides wheels for current Python versions and supports NumPy 2; pandas
1.3 could fail to build on Python 3.11 or import with newer NumPy releases.
The minimum Python version matches the pandas and PyArrow requirements.
The boto3 constraint also permits a urllib3 version compatible with PyGithub,
so the database and CLI packages can share an environment.

For `file_to_table_spark`, install the optional Spark dependencies:

```sh
python -m pip install './db_lib[spark]'
```

Spark also requires a compatible Java installation. The existing `build` extra
installs IPython for interactive development and requires Python 3.10 or newer.

For an offline import smoke test without accessing instance metadata:

```sh
AWS_EC2_METADATA_DISABLED=true python -c 'import db; print("Database helpers imported")'
```
