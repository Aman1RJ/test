"""Convert parsed schema definitions into IBM DB2 DDL."""
from __future__ import annotations


from dataclasses import dataclass
from typing import List

from .ddl_parser import ColumnDefinition, SchemaParser, TableDefinition
from .type_mappings import TypeMapper


@dataclass
class ConversionResult:
    """Holds the outcome of a schema conversion."""

    ddl: str
    tables: List[TableDefinition]
    warnings: List[str]


class SchemaConverter:
    """Convert MSSQL or Oracle DDL into IBM DB2 DDL."""

    def __init__(self, source: str):
        self.source = source.lower()
        self.parser = SchemaParser()
        self.mapper = TypeMapper(self.source)

    @staticmethod
    def _format_identifier(identifier: str) -> str:
        parts = [part.strip() for part in identifier.split(".") if part.strip()]
        return ".".join(f'"{part}"' for part in parts) if parts else identifier

    def _convert_column(self, column: ColumnDefinition, warnings: List[str]) -> str:
        mapping = self.mapper.convert(column.data_type or "VARCHAR(255)")
        if mapping.warning:
            warnings.append(f"{column.name}: {mapping.warning}")
        for note in column.notes:
            note_upper = note.upper()
            if "IDENTITY" in note_upper or "GENERATED" in note_upper:
                warnings.append(f"{column.name}: {note} requires manual migration to DB2 identity/sequence semantics.")
            else:
                warnings.append(f"{column.name}: Review clause '{note}' for DB2 compatibility.")
        column_parts = [self._format_identifier(column.name), mapping.target_type]
        if not column.nullable:
            column_parts.append("NOT NULL")
        if column.default:
            column_parts.append(f"DEFAULT {column.default}")
        if column.extra:
            column_parts.append(column.extra)
        return " ".join(part for part in column_parts if part)

    def _render_table(self, table: TableDefinition, warnings: List[str]) -> str:
        rendered_columns = [self._convert_column(column, warnings) for column in table.columns]
        rendered_constraints = [constraint for constraint in table.constraints]
        all_lines = rendered_columns + rendered_constraints
        formatted_name = self._format_identifier(table.name)
        column_block = ",\n    ".join(all_lines)
        return f"CREATE TABLE {formatted_name} (\n    {column_block}\n);"

    def convert(self, sql_text: str) -> ConversionResult:
        tables = self.parser.parse(sql_text)
        warnings: List[str] = []
        ddl_statements = [self._render_table(table, warnings) for table in tables]
        ddl = "\n\n".join(ddl_statements)
        return ConversionResult(ddl=ddl, tables=tables, warnings=warnings)


__all__ = ["SchemaConverter", "ConversionResult"]
