# DB Schema Migration Tool

This project provides a desktop GUI for converting Microsoft SQL Server or Oracle database schema definitions into IBM DB2 compatible DDL.

## Features

- Load schema definitions from an SQL file or paste them directly into the application.
- Convert common data types from MSSQL/Oracle to their IBM DB2 equivalents.
- Preserve table and column structure, including constraints.
- Highlight potential migration issues (for example, unsupported identity columns).
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
2. Paste the source DDL into the "Source Schema" pane or load an SQL file using **Open SQL File**.
3. Click **Convert** to generate the IBM DB2 DDL.
4. Review any warnings and optionally save the converted schema with **Save Output**.

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
