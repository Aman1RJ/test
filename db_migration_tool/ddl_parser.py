"""Parse SQL DDL statements from MSSQL or Oracle into generic structures."""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import List, Optional, Tuple


_CREATE_TABLE_REGEX = re.compile(
    r"CREATE\s+TABLE\s+([^(\s]+)\s*\((.*)\)\s*;?",
    re.IGNORECASE | re.DOTALL,
)
_COLUMN_KEYWORD_REGEX = re.compile(
    r"\b(NOT\s+NULL|NULL|DEFAULT|CONSTRAINT|PRIMARY\s+KEY|UNIQUE|CHECK|REFERENCES|IDENTITY|GENERATED)\b",
    re.IGNORECASE,
)
_DEFAULT_REGEX = re.compile(
    r"DEFAULT\s+((?:\([^)]*\)|'[^']*'|\"[^\"]*\"|\S+))",
    re.IGNORECASE,
)


@dataclass
class ColumnDefinition:
    """Represents a column in a table."""

    name: str
    data_type: str
    nullable: bool = True
    default: Optional[str] = None
    extra: str = ""
    notes: List[str] = field(default_factory=list)


@dataclass
class TableDefinition:
    """Represents a database table."""

    name: str
    columns: List[ColumnDefinition] = field(default_factory=list)
    constraints: List[str] = field(default_factory=list)


class SchemaParser:
    """Convert SQL text into table definitions."""

    @staticmethod
    def _strip_comments(sql_text: str) -> str:
        without_block = re.sub(r"/\*.*?\*/", "", sql_text, flags=re.DOTALL)
        lines = []
        for line in without_block.splitlines():
            if "--" in line:
                line = line.split("--", 1)[0]
            if line.strip():
                lines.append(line)
        return "\n".join(lines)

    @staticmethod
    def _split_definitions(definitions: str) -> List[str]:
        parts: List[str] = []
        current: List[str] = []
        depth = 0
        for char in definitions:
            if char == "(":
                depth += 1
                current.append(char)
            elif char == ")":
                depth = max(0, depth - 1)
                current.append(char)
            elif char == "," and depth == 0:
                part = "".join(current).strip()
                if part:
                    parts.append(part)
                current = []
            else:
                current.append(char)
        if current:
            part = "".join(current).strip()
            if part:
                parts.append(part)
        return parts

    @staticmethod
    def _normalize_identifier(identifier: str) -> str:
        identifier = identifier.strip()
        quote_pairs = {"[": "]", '"': '"', "`": "`"}
        for opening, closing in quote_pairs.items():
            if identifier.startswith(opening) and identifier.endswith(closing):
                identifier = identifier[1:-1]
        return identifier

    @classmethod
    def _parse_column(cls, definition: str) -> ColumnDefinition:
        tokens = definition.strip()
        if not tokens:
            raise ValueError("Empty column definition")

        parts = tokens.split(None, 1)
        if not parts:
            raise ValueError(f"Invalid column definition: {definition}")
        name = cls._normalize_identifier(parts[0])
        remainder = parts[1] if len(parts) > 1 else ""

        data_type, remainder = cls._extract_data_type(remainder)
        nullable = not re.search(r"NOT\s+NULL", remainder, re.IGNORECASE)
        default_match = _DEFAULT_REGEX.search(remainder)
        default = default_match.group(1).strip() if default_match else None

        cleaned_remainder = re.sub(r"NOT\s+NULL", "", remainder, flags=re.IGNORECASE)
        cleaned_remainder = re.sub(r"\bNULL\b", "", cleaned_remainder, flags=re.IGNORECASE)
        cleaned_remainder = _DEFAULT_REGEX.sub("", cleaned_remainder)

        notes: List[str] = []
        identity_match = re.search(r"\bIDENTITY\s*\([^)]*\)", remainder, re.IGNORECASE)
        if identity_match:
            notes.append(identity_match.group(0).strip())
            cleaned_remainder = re.sub(r"\bIDENTITY\s*\([^)]*\)", "", cleaned_remainder, flags=re.IGNORECASE)

        generated_match = re.search(r"\bGENERATED\b[^,]*", remainder, re.IGNORECASE)
        if generated_match:
            notes.append(generated_match.group(0).strip())
            cleaned_remainder = re.sub(r"\bGENERATED\b[^,]*", "", cleaned_remainder, flags=re.IGNORECASE)

        extra = " ".join(segment.strip() for segment in cleaned_remainder.split() if segment.strip())

        return ColumnDefinition(name=name, data_type=data_type, nullable=nullable, default=default, extra=extra, notes=notes)

    @staticmethod
    def _extract_data_type(remainder: str) -> Tuple[str, str]:
        if not remainder:
            return "", ""
        match = _COLUMN_KEYWORD_REGEX.search(remainder)
        if match:
            data_type = remainder[: match.start()].strip()
            rest = remainder[match.start():].strip()
            return data_type, rest
        return remainder.strip(), ""

    def parse(self, sql_text: str) -> List[TableDefinition]:
        cleaned = self._strip_comments(sql_text)
        tables: List[TableDefinition] = []
        for match in _CREATE_TABLE_REGEX.finditer(cleaned):
            table_name = self._normalize_identifier(match.group(1))
            raw_columns = match.group(2)
            definitions = self._split_definitions(raw_columns)
            columns: List[ColumnDefinition] = []
            constraints: List[str] = []
            for definition in definitions:
                if not definition:
                    continue
                upper = definition.strip().upper()
                if upper.startswith("CONSTRAINT") or upper.startswith("PRIMARY KEY") or upper.startswith("UNIQUE") or upper.startswith("CHECK"):
                    constraints.append(definition.strip())
                    continue
                column = self._parse_column(definition)
                columns.append(column)
            tables.append(TableDefinition(name=table_name, columns=columns, constraints=constraints))
        return tables


__all__ = ["SchemaParser", "TableDefinition", "ColumnDefinition"]
