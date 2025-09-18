"""Utilities for applying converted DDL to an IBM DB2 database."""
from __future__ import annotations

import importlib
import importlib.util
from dataclasses import dataclass
from typing import List, Optional


@dataclass
class StatementExecution:
    """Represents the outcome of executing an individual SQL statement."""

    statement: str
    success: bool
    error: Optional[str] = None


def _split_statements(sql: str) -> List[str]:
    statements: List[str] = []
    current: List[str] = []
    in_single_quote = False
    in_double_quote = False
    i = 0
    length = len(sql)
    while i < length:
        char = sql[i]
        next_char = sql[i + 1] if i + 1 < length else ""
        if not in_single_quote and not in_double_quote and char == "-" and next_char == "-":
            i += 2
            while i < length and sql[i] != "\n":
                i += 1
            continue
        if not in_single_quote and not in_double_quote and char == "/" and next_char == "*":
            i += 2
            while i + 1 < length and not (sql[i] == "*" and sql[i + 1] == "/"):
                i += 1
            i += 2
            continue
        if char == "'" and not in_double_quote:
            current.append(char)
            if in_single_quote and next_char == "'":
                current.append(next_char)
                i += 2
                continue
            in_single_quote = not in_single_quote
            i += 1
            continue
        if char == '"' and not in_single_quote:
            current.append(char)
            if in_double_quote and next_char == '"':
                current.append(next_char)
                i += 2
                continue
            in_double_quote = not in_double_quote
            i += 1
            continue
        if char == ";" and not in_single_quote and not in_double_quote:
            statement = "".join(current).strip()
            if statement:
                statements.append(statement)
            current = []
            i += 1
            continue
        current.append(char)
        i += 1
    trailing = "".join(current).strip()
    if trailing:
        statements.append(trailing)
    return statements


class DB2SchemaApplier:
    """Apply SQL statements to IBM DB2 using a DB-API connection."""

    def __init__(self, connection):
        self.connection = connection

    def apply(self, ddl: str, stop_on_error: bool = True) -> List[StatementExecution]:
        statements = _split_statements(ddl)
        results: List[StatementExecution] = []
        if not statements:
            return results
        cursor = self.connection.cursor()
        had_error = False
        for statement in statements:
            try:
                cursor.execute(statement)
            except Exception as exc:  # pragma: no cover - depends on runtime DB drivers
                had_error = True
                results.append(StatementExecution(statement=statement, success=False, error=str(exc)))
                if stop_on_error:
                    if hasattr(self.connection, "rollback"):
                        self.connection.rollback()
                    break
            else:
                results.append(StatementExecution(statement=statement, success=True))
        if not had_error:
            if hasattr(self.connection, "commit"):
                self.connection.commit()
        elif not stop_on_error and hasattr(self.connection, "rollback"):
            self.connection.rollback()
        try:
            cursor.close()
        except Exception:  # pragma: no cover - optional cleanup
            pass
        return results


def connect_db2(*, dsn: Optional[str] = None, database: Optional[str] = None, hostname: Optional[str] = None,
                port: int = 50000, uid: Optional[str] = None, pwd: Optional[str] = None, security: Optional[str] = None,
                **kwargs):
    """Create an ibm_db_dbi connection for DB2 schema insertion."""

    ibm_spec = importlib.util.find_spec("ibm_db_dbi")
    if ibm_spec is None:
        raise ImportError("ibm_db_dbi is required for DB2 auto insertion but is not installed.")
    ibm_db_dbi = importlib.import_module("ibm_db_dbi")
    if dsn:
        connection_string = dsn
    else:
        if not database or not hostname or not uid or not pwd:
            raise ValueError("'database', 'hostname', 'uid', and 'pwd' are required when DSN is not provided.")
        parts = [
            f"DATABASE={database}",
            f"HOSTNAME={hostname}",
            f"PORT={port}",
            "PROTOCOL=TCPIP",
            f"UID={uid}",
            f"PWD={pwd}",
        ]
        if security:
            parts.append(f"SECURITY={security}")
        for key, value in kwargs.items():
            parts.append(f"{key.upper()}={value}")
        connection_string = ";".join(parts)
    return ibm_db_dbi.connect(connection_string, "", "")


__all__ = ["StatementExecution", "DB2SchemaApplier", "connect_db2"]
