"""Utilities for extracting schema DDL from MSSQL or Oracle automatically."""
from __future__ import annotations

import importlib
import importlib.util
import re
from dataclasses import dataclass
from typing import Iterable, List, Optional, Sequence, Tuple


@dataclass
class ExtractedTable:
    """Represents a table extracted from a source database."""

    schema: str
    name: str
    ddl: str


def _quote_identifier(identifier: str) -> str:
    identifier = identifier.strip()
    if identifier.startswith("\"") and identifier.endswith("\""):
        return identifier
    if identifier.startswith("[") and identifier.endswith("]"):
        identifier = identifier[1:-1]
    return f'"{identifier}"'


def _clean_default(default: Optional[str]) -> Optional[str]:
    if default is None:
        return None
    cleaned = default.strip()
    if not cleaned:
        return None
    while cleaned.startswith("(") and cleaned.endswith(")"):
        inner = cleaned[1:-1].strip()
        if not inner:
            break
        cleaned = inner
    cleaned = re.sub(r"\s+", " ", cleaned)
    return cleaned


def _fetch_as_dict(cursor) -> List[dict]:  # type: ignore[override]
    columns = [column[0].lower() for column in cursor.description]
    rows = cursor.fetchall()
    results: List[dict] = []
    for row in rows:
        results.append({column: row[idx] for idx, column in enumerate(columns)})
    return results


class BaseSchemaExtractor:
    """Base functionality shared by all schema extractors."""

    def __init__(self, connection):
        self.connection = connection

    def list_tables(self, schema: Optional[str] = None) -> List[Tuple[str, str]]:
        raise NotImplementedError

    def fetch_table(self, schema: str, table: str) -> ExtractedTable:
        raise NotImplementedError

    def extract(self, schema: Optional[str] = None, tables: Optional[Sequence[str]] = None) -> List[ExtractedTable]:
        table_refs: Iterable[Tuple[str, str]]
        if tables:
            parsed_tables: List[Tuple[str, str]] = []
            for table in tables:
                table_name = table.strip()
                if not table_name:
                    continue
                if "." in table_name:
                    table_schema, actual_name = table_name.split(".", 1)
                    parsed_tables.append((table_schema.strip(), actual_name.strip()))
                else:
                    parsed_tables.append((schema or self._default_schema(), table_name))
            table_refs = parsed_tables
        else:
            table_refs = self.list_tables(schema)
        results: List[ExtractedTable] = []
        for table_schema, table_name in table_refs:
            results.append(self.fetch_table(table_schema, table_name))
        return results

    def extract_as_sql(self, schema: Optional[str] = None, tables: Optional[Sequence[str]] = None) -> str:
        extracted = self.extract(schema=schema, tables=tables)
        return "\n\n".join(item.ddl for item in extracted)

    def _default_schema(self) -> str:
        raise NotImplementedError


class MSSQLSchemaExtractor(BaseSchemaExtractor):
    """Extract DDL from Microsoft SQL Server using pyodbc."""

    def list_tables(self, schema: Optional[str] = None) -> List[Tuple[str, str]]:
        cursor = self.connection.cursor()
        base_query = (
            "SELECT TABLE_SCHEMA, TABLE_NAME FROM INFORMATION_SCHEMA.TABLES "
            "WHERE TABLE_TYPE = 'BASE TABLE'"
        )
        if schema:
            query = base_query + " AND TABLE_SCHEMA = ? ORDER BY TABLE_NAME"
            cursor.execute(query, schema)
        else:
            query = base_query + " ORDER BY TABLE_SCHEMA, TABLE_NAME"
            cursor.execute(query)
        rows = _fetch_as_dict(cursor)
        return [(row["table_schema"], row["table_name"]) for row in rows]

    def fetch_table(self, schema: str, table: str) -> ExtractedTable:
        column_query = (
            "SELECT c.COLUMN_NAME, c.DATA_TYPE, c.IS_NULLABLE, c.COLUMN_DEFAULT, "
            "c.CHARACTER_MAXIMUM_LENGTH, c.NUMERIC_PRECISION, c.NUMERIC_SCALE, c.DATETIME_PRECISION, "
            "ic.seed_value, ic.increment_value "
            "FROM INFORMATION_SCHEMA.COLUMNS c "
            "LEFT JOIN sys.schemas s ON s.name = c.TABLE_SCHEMA "
            "LEFT JOIN sys.tables t ON t.name = c.TABLE_NAME AND t.schema_id = s.schema_id "
            "LEFT JOIN sys.identity_columns ic ON ic.object_id = t.object_id AND ic.name = c.COLUMN_NAME "
            "WHERE c.TABLE_SCHEMA = ? AND c.TABLE_NAME = ? "
            "ORDER BY c.ORDINAL_POSITION"
        )
        cursor = self.connection.cursor()
        cursor.execute(column_query, schema, table)
        columns = _fetch_as_dict(cursor)
        if not columns:
            raise ValueError(f"Table {schema}.{table} not found or has no columns.")

        pk_query = (
            "SELECT k.COLUMN_NAME FROM INFORMATION_SCHEMA.TABLE_CONSTRAINTS t "
            "JOIN INFORMATION_SCHEMA.KEY_COLUMN_USAGE k ON t.CONSTRAINT_NAME = k.CONSTRAINT_NAME "
            "AND t.TABLE_SCHEMA = k.TABLE_SCHEMA AND t.TABLE_NAME = k.TABLE_NAME "
            "WHERE t.TABLE_SCHEMA = ? AND t.TABLE_NAME = ? AND t.CONSTRAINT_TYPE = 'PRIMARY KEY' "
            "ORDER BY k.ORDINAL_POSITION"
        )
        cursor.execute(pk_query, schema, table)
        pk_rows = _fetch_as_dict(cursor)
        pk_columns = [row["column_name"] for row in pk_rows]

        lines = [self._render_column(row) for row in columns]
        if pk_columns:
            quoted = ", ".join(_quote_identifier(column) for column in pk_columns)
            lines.append(f"PRIMARY KEY ({quoted})")
        formatted_name = f'{_quote_identifier(schema)}.{_quote_identifier(table)}'
        ddl = "CREATE TABLE {name} (\n    {body}\n);".format(name=formatted_name, body=",\n    ".join(lines))
        return ExtractedTable(schema=schema, name=table, ddl=ddl)

    def _render_column(self, column: dict) -> str:
        column_name = _quote_identifier(column["column_name"])
        data_type = self._render_data_type(column)
        nullable = column["is_nullable"].upper() == "YES"
        parts = [column_name, data_type]
        if not nullable:
            parts.append("NOT NULL")
        default = _clean_default(column.get("column_default"))
        if default:
            parts.append(f"DEFAULT {default}")
        seed = column.get("seed_value")
        increment = column.get("increment_value")
        if seed is not None and increment is not None:
            seed_value = int(seed)
            increment_value = int(increment)
            parts.append(f"IDENTITY({seed_value}, {increment_value})")
        return " ".join(parts)

    @staticmethod
    def _render_data_type(column: dict) -> str:
        data_type = column["data_type"].upper()
        char_length = column.get("character_maximum_length")
        numeric_precision = column.get("numeric_precision")
        numeric_scale = column.get("numeric_scale")
        datetime_precision = column.get("datetime_precision")
        if data_type in {"CHAR", "NCHAR", "VARCHAR", "NVARCHAR", "BINARY", "VARBINARY"}:
            if char_length is None:
                return data_type
            length_value = int(char_length)
            if length_value == -1:
                return f"{data_type}(MAX)"
            return f"{data_type}({length_value})"
        if data_type in {"DECIMAL", "NUMERIC"}:
            if numeric_scale is None or numeric_precision is None:
                return data_type
            return f"{data_type}({int(numeric_precision)}, {int(numeric_scale)})"
        if data_type in {"FLOAT", "REAL"}:
            return data_type
        if data_type in {"DATETIME2", "DATETIMEOFFSET", "TIME"} and datetime_precision is not None:
            return f"{data_type}({int(datetime_precision)})"
        return data_type

    def _default_schema(self) -> str:
        cursor = self.connection.cursor()
        cursor.execute("SELECT SCHEMA_NAME()")
        row = cursor.fetchone()
        if not row:
            return "dbo"
        return row[0]


class OracleSchemaExtractor(BaseSchemaExtractor):
    """Extract DDL from Oracle using cx_Oracle/oracledb."""

    def list_tables(self, schema: Optional[str] = None) -> List[Tuple[str, str]]:
        cursor = self.connection.cursor()
        if schema:
            owner = schema.upper()
            query = (
                "SELECT OWNER, TABLE_NAME FROM ALL_TABLES WHERE OWNER = :owner ORDER BY TABLE_NAME"
            )
            cursor.execute(query, owner=owner)
        else:
            query = "SELECT :owner AS OWNER, TABLE_NAME FROM USER_TABLES ORDER BY TABLE_NAME"
            current_schema = self._default_schema()
            cursor.execute(query, owner=current_schema)
        rows = _fetch_as_dict(cursor)
        return [(row["owner"], row["table_name"]) for row in rows]

    def fetch_table(self, schema: str, table: str) -> ExtractedTable:
        owner = schema.upper()
        table_name = table.upper()
        column_query = (
            "SELECT COLUMN_NAME, DATA_TYPE, DATA_LENGTH, DATA_PRECISION, DATA_SCALE, DATA_DEFAULT, NULLABLE, "
            "IDENTITY_COLUMN FROM ALL_TAB_COLUMNS WHERE OWNER = :owner AND TABLE_NAME = :table ORDER BY COLUMN_ID"
        )
        cursor = self.connection.cursor()
        cursor.execute(column_query, owner=owner, table=table_name)
        columns = _fetch_as_dict(cursor)
        if not columns:
            raise ValueError(f"Table {schema}.{table} not found or has no columns.")

        pk_query = (
            "SELECT acc.COLUMN_NAME FROM ALL_CONSTRAINTS ac "
            "JOIN ALL_CONS_COLUMNS acc ON ac.OWNER = acc.OWNER AND ac.CONSTRAINT_NAME = acc.CONSTRAINT_NAME "
            "WHERE ac.OWNER = :owner AND ac.TABLE_NAME = :table AND ac.CONSTRAINT_TYPE = 'P' "
            "ORDER BY acc.POSITION"
        )
        cursor.execute(pk_query, owner=owner, table=table_name)
        pk_rows = _fetch_as_dict(cursor)
        pk_columns = [row["column_name"] for row in pk_rows]

        lines = [self._render_column(row) for row in columns]
        if pk_columns:
            quoted = ", ".join(_quote_identifier(column) for column in pk_columns)
            lines.append(f"PRIMARY KEY ({quoted})")
        formatted_name = f'{_quote_identifier(owner)}.{_quote_identifier(table_name)}'
        ddl = "CREATE TABLE {name} (\n    {body}\n);".format(name=formatted_name, body=",\n    ".join(lines))
        return ExtractedTable(schema=owner, name=table_name, ddl=ddl)

    @staticmethod
    def _render_column(column: dict) -> str:
        column_name = _quote_identifier(column["column_name"])
        data_type = OracleSchemaExtractor._render_data_type(column)
        parts = [column_name, data_type]
        if column.get("nullable", "Y") == "N":
            parts.append("NOT NULL")
        default = _clean_default(column.get("data_default"))
        if default:
            parts.append(f"DEFAULT {default}")
        if column.get("identity_column", "NO") == "YES":
            parts.append("GENERATED ALWAYS AS IDENTITY")
        return " ".join(parts)

    @staticmethod
    def _render_data_type(column: dict) -> str:
        data_type = column["data_type"].upper()
        data_length = column.get("data_length")
        precision = column.get("data_precision")
        scale = column.get("data_scale")
        if data_type in {"CHAR", "NCHAR", "VARCHAR2", "NVARCHAR2", "RAW"}:
            if data_length is None:
                return data_type
            return f"{data_type}({int(data_length)})"
        if data_type == "NUMBER":
            if precision is None:
                return data_type
            if scale is None:
                return f"NUMBER({int(precision)})"
            return f"NUMBER({int(precision)}, {int(scale)})"
        return data_type

    def _default_schema(self) -> str:
        cursor = self.connection.cursor()
        cursor.execute("SELECT SYS_CONTEXT('USERENV', 'CURRENT_SCHEMA') FROM dual")
        row = cursor.fetchone()
        if row and row[0]:
            return row[0]
        cursor.execute("SELECT USER FROM dual")
        row = cursor.fetchone()
        if row and row[0]:
            return row[0]
        raise ValueError("Unable to determine Oracle schema")


def connect_mssql(*, dsn: Optional[str] = None, driver: str = "ODBC Driver 17 for SQL Server", server: Optional[str] = None,
                  database: Optional[str] = None, user: Optional[str] = None, password: Optional[str] = None,
                  trusted_connection: bool = False, **kwargs):
    """Create a pyodbc connection for MSSQL extraction."""

    if dsn:
        connection_string = f"DSN={dsn}"
    else:
        if not server or not database:
            raise ValueError("'server' and 'database' are required when DSN is not provided.")
        parts = [f"DRIVER={{{{driver}}}}".format(driver=driver), f"SERVER={server}", f"DATABASE={database}"]
        if trusted_connection:
            parts.append("Trusted_Connection=yes")
        else:
            if not user or not password:
                raise ValueError("'user' and 'password' are required when Trusted_Connection is not used.")
            parts.append(f"UID={user}")
            parts.append(f"PWD={password}")
        for key, value in kwargs.items():
            parts.append(f"{key.upper()}={value}")
        connection_string = ";".join(parts)
    pyodbc_spec = importlib.util.find_spec("pyodbc")
    if pyodbc_spec is None:
        raise ImportError("pyodbc is required for MSSQL auto extraction but is not installed.")
    pyodbc = importlib.import_module("pyodbc")
    return pyodbc.connect(connection_string)


def connect_oracle(*, dsn: str, user: str, password: str, **kwargs):
    """Create an Oracle connection using cx_Oracle or python-oracledb."""

    cx_spec = importlib.util.find_spec("cx_Oracle")
    module_name = "cx_Oracle"
    if cx_spec is None:
        oracledb_spec = importlib.util.find_spec("oracledb")
        if oracledb_spec is None:
            raise ImportError("cx_Oracle or oracledb is required for Oracle auto extraction but is not installed.")
        module_name = "oracledb"
    oracle_driver = importlib.import_module(module_name)
    return oracle_driver.connect(user=user, password=password, dsn=dsn, **kwargs)


def extract_schema(connection, source: str, schema: Optional[str] = None, tables: Optional[Sequence[str]] = None) -> str:
    """Extract CREATE TABLE statements from the given connection."""

    source_lower = source.lower()
    if source_lower == "mssql":
        extractor: BaseSchemaExtractor = MSSQLSchemaExtractor(connection)
    elif source_lower == "oracle":
        extractor = OracleSchemaExtractor(connection)
    else:
        raise ValueError("Unsupported source for extraction. Use 'mssql' or 'oracle'.")
    return extractor.extract_as_sql(schema=schema, tables=tables)


__all__ = [
    "ExtractedTable",
    "BaseSchemaExtractor",
    "MSSQLSchemaExtractor",
    "OracleSchemaExtractor",
    "connect_mssql",
    "connect_oracle",
    "extract_schema",
]
