"""Tkinter GUI for the database migration tool."""
from __future__ import annotations

import tkinter as tk
from tkinter import filedialog, messagebox, scrolledtext, ttk
from typing import Dict, Optional

from .converter import SchemaConverter


class MigrationGUI:
    """Encapsulates the Tkinter-based GUI."""

    def __init__(self, root: tk.Tk):
        self.root = root
        self.root.title("DB Schema Migration to IBM DB2")
        self.root.geometry("1100x780")

        self.source_var = tk.StringVar(value="mssql")
        self.converter: Optional[SchemaConverter] = None
        self.source_conn_vars: Dict[str, tk.StringVar] = {}
        self.target_conn_vars: Dict[str, tk.StringVar] = {}
        self.component_vars: Dict[str, tk.BooleanVar] = {}
        self.component_labels: Dict[str, str] = {}

        self._build_widgets()

    def _build_widgets(self) -> None:
        top_frame = ttk.Frame(self.root, padding=10)
        top_frame.pack(side=tk.TOP, fill=tk.X)

        ttk.Label(top_frame, text="Source database:").pack(side=tk.LEFT)
        source_menu = ttk.OptionMenu(
            top_frame,
            self.source_var,
            self.source_var.get(),
            "mssql",
            "oracle",
        )
        source_menu.pack(side=tk.LEFT, padx=(8, 16))

        ttk.Button(top_frame, text="Open SQL File", command=self._open_file).pack(side=tk.LEFT)
        ttk.Button(top_frame, text="Convert", command=self._convert).pack(side=tk.LEFT, padx=8)
        ttk.Button(top_frame, text="Save Output", command=self._save_output).pack(side=tk.LEFT)

        self.status_var = tk.StringVar(value="Load a schema file or paste DDL into the input area.")
        status_label = ttk.Label(top_frame, textvariable=self.status_var)
        status_label.pack(side=tk.LEFT, padx=16)

        connection_frame = ttk.Frame(self.root, padding=(10, 0))
        connection_frame.pack(fill=tk.X)

        source_section, self.source_conn_vars = self._build_connection_section(
            connection_frame,
            "Source Connection (MSSQL/Oracle)",
        )
        source_section.pack(side=tk.LEFT, expand=True, fill=tk.X, padx=(0, 5))

        target_section, self.target_conn_vars = self._build_connection_section(
            connection_frame,
            "Target Connection (IBM DB2)",
        )
        target_section.pack(side=tk.LEFT, expand=True, fill=tk.X, padx=(5, 0))

        components_frame = ttk.LabelFrame(
            self.root,
            text="Schema Components",
            padding=(10, 8),
        )
        components_frame.pack(fill=tk.X, padx=10, pady=(10, 0))
        self._build_component_selectors(components_frame)

        text_frame = ttk.Frame(self.root, padding=(10, 0, 10, 10))
        text_frame.pack(fill=tk.BOTH, expand=True)

        input_label = ttk.Label(text_frame, text="Source Schema (MSSQL/Oracle)")
        input_label.pack(anchor=tk.W)
        self.input_text = scrolledtext.ScrolledText(text_frame, wrap=tk.WORD, height=15)
        self.input_text.pack(fill=tk.BOTH, expand=True, pady=(0, 10))

        output_label = ttk.Label(text_frame, text="Converted IBM DB2 Schema")
        output_label.pack(anchor=tk.W)
        self.output_text = scrolledtext.ScrolledText(text_frame, wrap=tk.WORD, height=15, state=tk.NORMAL)
        self.output_text.pack(fill=tk.BOTH, expand=True)

    def _build_connection_section(
        self,
        parent: ttk.Frame,
        title: str,
    ) -> tuple[ttk.LabelFrame, Dict[str, tk.StringVar]]:
        frame = ttk.LabelFrame(parent, text=title, padding=10)
        field_definitions = [
            ("Host", "host", False),
            ("Port", "port", False),
            ("Database/Service", "database", False),
            ("Schema", "schema", False),
            ("Username", "username", False),
            ("Password", "password", True),
        ]
        variables: Dict[str, tk.StringVar] = {}
        for row, (label, key, is_password) in enumerate(field_definitions):
            variables[key] = tk.StringVar()
            ttk.Label(frame, text=f"{label}:").grid(
                row=row,
                column=0,
                sticky=tk.W,
                padx=(0, 8),
                pady=2,
            )
            entry = ttk.Entry(frame, textvariable=variables[key], width=28)
            if is_password:
                entry.configure(show="*")
            entry.grid(row=row, column=1, sticky=tk.EW, pady=2)
        frame.grid_columnconfigure(1, weight=1)
        return frame, variables

    def _build_component_selectors(self, parent: ttk.LabelFrame) -> None:
        component_definitions = [
            ("tables", "Tables", True),
            ("constraints", "Constraints", True),
            ("indexes", "Indexes", False),
            ("triggers", "Triggers", False),
            ("data", "Data", False),
        ]
        for column, (key, label, default) in enumerate(component_definitions):
            variable = tk.BooleanVar(value=default)
            check = ttk.Checkbutton(parent, text=label, variable=variable)
            check.grid(row=0, column=column, padx=8, pady=4, sticky=tk.W)
            self.component_vars[key] = variable
            self.component_labels[key] = label

    @staticmethod
    def _collect_connection_details(variables: Dict[str, tk.StringVar]) -> Dict[str, str]:
        return {key: value.get().strip() for key, value in variables.items()}

    def _open_file(self) -> None:
        file_path = filedialog.askopenfilename(
            title="Select schema file",
            filetypes=[("SQL files", "*.sql"), ("All files", "*.*")],
        )
        if not file_path:
            return
        try:
            with open(file_path, "r", encoding="utf-8") as sql_file:
                content = sql_file.read()
            self.input_text.delete("1.0", tk.END)
            self.input_text.insert(tk.END, content)
            self.status_var.set(f"Loaded schema from {file_path}")
        except OSError as exc:
            messagebox.showerror("File Error", f"Could not read file: {exc}")

    def _ensure_converter(self) -> SchemaConverter:
        source = self.source_var.get()
        if self.converter is None or self.converter.source != source:
            self.converter = SchemaConverter(source)
        return self.converter

    def _convert(self) -> None:
        sql_text = self.input_text.get("1.0", tk.END).strip()
        if not sql_text:
            messagebox.showwarning("No Input", "Please provide MSSQL or Oracle DDL to convert.")
            return

        selected_components = [
            key for key, variable in self.component_vars.items() if variable.get()
        ]
        if "tables" not in selected_components:
            messagebox.showwarning(
                "Tables Required",
                "Conversion requires the Tables component to be selected.",
            )
            return

        converter = self._ensure_converter()
        try:
            result = converter.convert(sql_text)
        except Exception as exc:  # pragma: no cover - GUI safety
            messagebox.showerror("Conversion Error", f"Failed to convert schema: {exc}")
            return

        self.output_text.delete("1.0", tk.END)
        self.output_text.insert(tk.END, result.ddl or "-- No tables were parsed from the input.")

        if result.tables:
            summary = f"Converted {len(result.tables)} table(s)."
        else:
            summary = "No tables detected in the provided schema."
        component_summary = ", ".join(
            self.component_labels[key] for key in selected_components if key in self.component_labels
        )
        if component_summary:
            summary += f" Components: {component_summary}."

        additional_warnings = []
        unsupported_messages = {
            "indexes": "Index DDL generation is not automated; review indexes manually.",
            "triggers": "Trigger migration is not automated; recreate triggers in DB2 manually.",
            "data": "Data export/import is not handled by the GUI. Use database utilities to migrate table data.",
        }
        for key, message in unsupported_messages.items():
            if self.component_vars.get(key) and self.component_vars[key].get():
                additional_warnings.append(message)

        if result.warnings or additional_warnings:
            combined = list(result.warnings) + additional_warnings
            summary += f" Review {len(combined)} warning(s)."
            messagebox.showwarning("Conversion Warnings", "\n".join(combined))

        source_conn = self._collect_connection_details(self.source_conn_vars)
        target_conn = self._collect_connection_details(self.target_conn_vars)
        if source_conn.get("database"):
            summary += f" Source DB: {source_conn['database']}."
        elif source_conn.get("schema"):
            summary += f" Source schema: {source_conn['schema']}."
        if target_conn.get("database"):
            summary += f" Target DB: {target_conn['database']}."

        self.status_var.set(summary)

    def _save_output(self) -> None:
        ddl = self.output_text.get("1.0", tk.END).strip()
        if not ddl:
            messagebox.showwarning("No Output", "There is no converted schema to save.")
            return
        file_path = filedialog.asksaveasfilename(
            title="Save converted schema",
            defaultextension=".sql",
            filetypes=[("SQL files", "*.sql"), ("All files", "*.*")],
        )
        if not file_path:
            return
        try:
            with open(file_path, "w", encoding="utf-8") as ddl_file:
                ddl_file.write(ddl)
            self.status_var.set(f"Saved converted schema to {file_path}")
        except OSError as exc:
            messagebox.showerror("File Error", f"Could not save file: {exc}")


def launch_gui() -> None:
    """Initialize and run the GUI application."""

    root = tk.Tk()
    MigrationGUI(root)
    root.mainloop()


__all__ = ["MigrationGUI", "launch_gui"]
