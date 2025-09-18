"""Database schema migration tool package."""

from .auto_extract import (
    BaseSchemaExtractor,
    ExtractedTable,
    MSSQLSchemaExtractor,
    OracleSchemaExtractor,
    connect_mssql,
    connect_oracle,
    extract_schema,
)
from .auto_insert import DB2SchemaApplier, StatementExecution, connect_db2
from .converter import SchemaConverter, ConversionResult
from .ddl_parser import SchemaParser, TableDefinition, ColumnDefinition
from .type_mappings import TypeMapper

__all__ = [
    "BaseSchemaExtractor",
    "ExtractedTable",
    "MSSQLSchemaExtractor",
    "OracleSchemaExtractor",
    "connect_mssql",
    "connect_oracle",
    "extract_schema",
    "DB2SchemaApplier",
    "StatementExecution",
    "connect_db2",
    "SchemaConverter",
    "ConversionResult",
    "SchemaParser",
    "TableDefinition",
    "ColumnDefinition",
    "TypeMapper",
]
