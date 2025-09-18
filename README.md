# DB Schema Migration Tool

This project provides a desktop GUI for converting Microsoft SQL Server or Oracle database schema definitions into IBM DB2 compatible DDL.

## Features

- Load schema definitions from an SQL file or paste them directly into the application.
- Capture source (MSSQL/Oracle) and target (IBM DB2) connection parameters alongside the migration session.
- Convert common data types from MSSQL/Oracle to their IBM DB2 equivalents.
- Preserve table and column structure, including constraints.
- Highlight potential migration issues (for example, unsupported identity columns).
- Optional automation helpers to extract schema directly from MSSQL/Oracle instances and apply the converted DDL to DB2.
- Export the converted schema to a file for further review or execution.

## Getting Started

### Prerequisites

- Python 3.9 or later.
- The standard Tkinter library (included with most Python installations).

### Install dependencies

No third-party dependencies are required for the base functionality. If you plan to extend the tool with database connectivity, install the required DB drivers separately.

### Run the application

```bash
python app.py
```

## Usage

1. Choose the source database type (MSSQL or Oracle).
2. Fill in the connection parameters for both the source and target databases (host, port, database/service, schema, username, password) if you plan to use the automation helpers or simply want to track the migration context.
3. Select the schema components you intend to migrate. Tables and constraints are enabled by default, while indexes, triggers, and data can be toggled on to note additional migration work. The GUI will flag components that require manual handling (for example, data export/import).
4. Paste the source DDL into the "Source Schema" pane or load an SQL file using **Open SQL File**.
5. Click **Convert** to generate the IBM DB2 DDL.
6. Review any warnings and optionally save the converted schema with **Save Output**.

### Automated extraction and insertion

If you prefer to operate on live databases instead of manual SQL files, the package exposes helper modules:

```python
from db_migration_tool import (
    connect_mssql,
    connect_oracle,
    extract_schema,
    SchemaConverter,
    connect_db2,
    DB2SchemaApplier,
)

# 1. Extract MSSQL DDL automatically
mssql_conn = connect_mssql(server="sql-host", database="example", user="sa", password="Secret123!")
source_sql = extract_schema(mssql_conn, source="mssql", schema="dbo")

# 2. Convert to IBM DB2 DDL
converter = SchemaConverter("mssql")
conversion = converter.convert(source_sql)

# 3. Apply converted DDL to DB2 automatically
db2_conn = connect_db2(database="TARGET", hostname="db2-host", uid="db2user", pwd="passw0rd", port=50000)
applier = DB2SchemaApplier(db2_conn)
results = applier.apply(conversion.ddl)

for item in results:
    print(item.statement, "->", "OK" if item.success else item.error)
```

For Oracle sources, swap `connect_mssql` for `connect_oracle` when building the extraction connection. These helpers rely on
standard DB-API drivers (`pyodbc` for MSSQL, `cx_Oracle` or `python-oracledb` for Oracle, and `ibm_db_dbi` for DB2) which must
be installed separately.

## Limitations

- The parser focuses on common `CREATE TABLE` statements. More complex vendor-specific syntax may require manual adjustments.
- Identity or auto-generated column semantics are flagged for manual review.
- Foreign key references and advanced constraints are preserved as-is but may need adaptation for DB2.

## Development

The core logic lives in the `db_migration_tool` package:

- `ddl_parser.py`: lightweight parser that converts SQL DDL into structured objects.
- `type_mappings.py`: source-to-DB2 data type mappings and heuristics.
- `converter.py`: orchestration logic that generates DB2 DDL and aggregates warnings.
- `gui.py`: Tkinter GUI exposing the functionality to end users.

Feel free to extend the project with automated tests, direct database connectivity, or additional migration rules.
