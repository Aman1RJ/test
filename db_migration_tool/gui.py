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
        self.root.geometry("1200x860")
        self.root.minsize(1100, 760)

        self.source_var = tk.StringVar(value="oracle")
        self.converter: Optional[SchemaConverter] = None

        self.source_conn_vars: Dict[str, tk.StringVar] = {}
        self.target_conn_vars: Dict[str, tk.StringVar] = {}

        self.component_vars: Dict[str, tk.BooleanVar] = {}
        self.component_labels: Dict[str, str] = {}
        self.label_to_key: Dict[str, str] = {}
        self.component_definitions = [
            ("tables", "Tables", True),
            ("constraints", "Constraints", True),
            ("indexes", "Indexes", False),
            ("triggers", "Triggers", False),
            ("data", "Data", False),
        ]
        for key, label, default in self.component_definitions:
            self.component_vars[key] = tk.BooleanVar(value=default)
            self.component_labels[key] = label
            self.label_to_key[label] = key

        self.available_listbox: Optional[tk.Listbox] = None
        self.selected_listbox: Optional[tk.Listbox] = None

        self.source_schema_var = tk.StringVar()
        self.output_directory_var = tk.StringVar()
        self.db2_not_installed_var = tk.BooleanVar(value=False)

        self.extract_rows_var = tk.BooleanVar(value=True)
        self.extract_lobs_var = tk.BooleanVar(value=False)
        self.allow_nulls_var = tk.BooleanVar(value=True)
        self.truncate_target_var = tk.BooleanVar(value=False)

        self.source_test_button: Optional[ttk.Button] = None
        self.status_var = tk.StringVar(
            value="Browse for a schema file or paste DDL to begin the migration."
        )

        self.input_text: Optional[scrolledtext.ScrolledText] = None
        self.output_text: Optional[scrolledtext.ScrolledText] = None

        self._build_widgets()
        self._refresh_component_lists()

    def _build_widgets(self) -> None:
        main_frame = ttk.Frame(self.root, padding=10)
        main_frame.pack(fill=tk.BOTH, expand=True)

        connections_frame = ttk.Frame(main_frame)
        connections_frame.pack(fill=tk.X)

        source_section = self._build_source_section(connections_frame)
        source_section.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(0, 8))

        target_section = self._build_target_section(connections_frame)
        target_section.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(8, 0))

        selection_frame = self._build_component_selection(main_frame)
        selection_frame.pack(fill=tk.BOTH, expand=False, pady=(12, 0))

        options_frame = self._build_options_section(main_frame)
        options_frame.pack(fill=tk.X, pady=(12, 0))

        text_frame = ttk.Frame(main_frame)
        text_frame.pack(fill=tk.BOTH, expand=True, pady=(12, 0))

        left_text = ttk.Frame(text_frame)
        left_text.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(0, 6))
        ttk.Label(left_text, text="Source Schema (MSSQL/Oracle)").pack(anchor=tk.W)
        self.input_text = scrolledtext.ScrolledText(left_text, wrap=tk.WORD, height=18)
        self.input_text.pack(fill=tk.BOTH, expand=True, pady=(4, 0))

        right_text = ttk.Frame(text_frame)
        right_text.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(6, 0))
        ttk.Label(right_text, text="Converted IBM DB2 Schema").pack(anchor=tk.W)
        self.output_text = scrolledtext.ScrolledText(right_text, wrap=tk.WORD, height=18)
        self.output_text.pack(fill=tk.BOTH, expand=True, pady=(4, 0))

        actions_frame = ttk.Frame(main_frame)
        actions_frame.pack(fill=tk.X, pady=(12, 0))

        ttk.Button(actions_frame, text="Convert Schema", command=self._convert).pack(
            side=tk.LEFT
        )
        ttk.Button(actions_frame, text="Save Converted SQL", command=self._save_output).pack(
            side=tk.LEFT, padx=8
        )
        ttk.Button(
            actions_frame,
            text="Generate Data Movement Scripts",
            command=self._generate_scripts,
        ).pack(side=tk.LEFT, padx=8)
        ttk.Button(
            actions_frame,
            text="Execute DB2 Script",
            command=self._execute_db2_script,
        ).pack(side=tk.LEFT, padx=8)
        ttk.Button(actions_frame, text="Clear Output", command=self._clear_output).pack(
            side=tk.RIGHT
        )

        status_frame = ttk.Frame(main_frame, padding=(0, 12, 0, 0))
        status_frame.pack(fill=tk.X)
        ttk.Label(status_frame, textvariable=self.status_var).pack(anchor=tk.W)

    def _build_source_section(self, parent: ttk.Frame) -> ttk.LabelFrame:
        frame = ttk.LabelFrame(parent, text="Source Database (MSSQL/Oracle)", padding=10)

        ttk.Label(frame, text="Vendor:").grid(row=0, column=0, sticky=tk.W)
        vendor_combo = ttk.Combobox(
            frame,
            textvariable=self.source_var,
            values=("mssql", "oracle"),
            state="readonly",
        )
        vendor_combo.grid(row=0, column=1, sticky=tk.EW, padx=(8, 0), pady=2)
        vendor_combo.bind("<<ComboboxSelected>>", self._on_source_vendor_change)

        field_definitions = [
            ("Server Name", "host", False),
            ("Port Number", "port", False),
            ("Database / Service", "database", False),
            ("Schema", "schema", False),
            ("User Name", "username", False),
            ("Password", "password", True),
            ("JDBC Drivers", "jdbc", False),
        ]
        for row, (label, key, is_password) in enumerate(field_definitions, start=1):
            self.source_conn_vars[key] = tk.StringVar()
            ttk.Label(frame, text=f"{label}:").grid(
                row=row,
                column=0,
                sticky=tk.W,
                pady=2,
            )
            entry = ttk.Entry(frame, textvariable=self.source_conn_vars[key])
            if is_password:
                entry.configure(show="*")
            entry.grid(row=row, column=1, sticky=tk.EW, padx=(8, 0), pady=2)

        ttk.Label(frame, text="Source Schema File:").grid(
            row=len(field_definitions) + 1,
            column=0,
            sticky=tk.W,
            pady=(8, 2),
        )
        schema_entry = ttk.Entry(frame, textvariable=self.source_schema_var)
        schema_entry.grid(
            row=len(field_definitions) + 1,
            column=1,
            sticky=tk.EW,
            padx=(8, 0),
            pady=(8, 2),
        )
        browse_frame = ttk.Frame(frame)
        browse_frame.grid(
            row=len(field_definitions) + 2,
            column=0,
            columnspan=2,
            sticky=tk.EW,
        )
        ttk.Button(browse_frame, text="Browse…", command=self._open_file).pack(
            side=tk.LEFT
        )
        ttk.Button(
            browse_frame, text="Load from Path", command=self._load_schema_from_entry
        ).pack(side=tk.LEFT, padx=6)

        self.source_test_button = ttk.Button(
            frame,
            text="Test Connection to ORACLE",
            command=self._test_source_connection,
        )
        self.source_test_button.grid(
            row=len(field_definitions) + 3,
            column=0,
            columnspan=2,
            sticky=tk.EW,
            pady=(12, 0),
        )

        frame.grid_columnconfigure(1, weight=1)
        return frame

    def _build_target_section(self, parent: ttk.Frame) -> ttk.LabelFrame:
        frame = ttk.LabelFrame(parent, text="Target Database (IBM DB2)", padding=10)

        field_definitions = [
            ("Server Name", "host", False),
            ("Port Number", "port", False),
            ("Database Name", "database", False),
            ("Schema", "schema", False),
            ("User Name", "username", False),
            ("Password", "password", True),
            ("JDBC Drivers", "jdbc", False),
        ]
        for row, (label, key, is_password) in enumerate(field_definitions):
            self.target_conn_vars[key] = tk.StringVar()
            ttk.Label(frame, text=f"{label}:").grid(
                row=row,
                column=0,
                sticky=tk.W,
                pady=2,
            )
            entry = ttk.Entry(frame, textvariable=self.target_conn_vars[key])
            if is_password:
                entry.configure(show="*")
            entry.grid(row=row, column=1, sticky=tk.EW, padx=(8, 0), pady=2)

        ttk.Checkbutton(
            frame,
            text="DB2 not installed",
            variable=self.db2_not_installed_var,
            command=self._toggle_db2_installed,
        ).grid(
            row=len(field_definitions),
            column=0,
            columnspan=2,
            sticky=tk.W,
            pady=(6, 2),
        )

        ttk.Label(frame, text="Output Directory:").grid(
            row=len(field_definitions) + 1,
            column=0,
            sticky=tk.W,
            pady=(8, 2),
        )
        output_entry = ttk.Entry(frame, textvariable=self.output_directory_var)
        output_entry.grid(
            row=len(field_definitions) + 1,
            column=1,
            sticky=tk.EW,
            padx=(8, 0),
            pady=(8, 2),
        )
        ttk.Button(frame, text="Browse…", command=self._browse_output_directory).grid(
            row=len(field_definitions) + 2,
            column=0,
            columnspan=2,
            sticky=tk.W,
        )

        ttk.Button(
            frame,
            text="Test Connection to DB2",
            command=self._test_target_connection,
        ).grid(
            row=len(field_definitions) + 3,
            column=0,
            columnspan=2,
            sticky=tk.EW,
            pady=(12, 0),
        )

        frame.grid_columnconfigure(1, weight=1)
        return frame

    def _build_component_selection(self, parent: ttk.Frame) -> ttk.LabelFrame:
        frame = ttk.LabelFrame(parent, text="Schema Selection", padding=10)

        available_frame = ttk.Frame(frame)
        available_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        ttk.Label(available_frame, text="Available Components").pack(anchor=tk.W)
        self.available_listbox = tk.Listbox(
            available_frame, height=10, selectmode=tk.EXTENDED, exportselection=False
        )
        self.available_listbox.pack(fill=tk.BOTH, expand=True, pady=(4, 0))

        controls = ttk.Frame(frame, padding=(10, 0))
        controls.pack(side=tk.LEFT, fill=tk.Y)
        ttk.Button(controls, text="Select All", command=self._select_all_components).pack(
            fill=tk.X, pady=2
        )
        ttk.Button(controls, text="Add ▶", command=self._add_selected_components).pack(
            fill=tk.X, pady=2
        )
        ttk.Button(controls, text="◀ Remove", command=self._remove_selected_components).pack(
            fill=tk.X, pady=2
        )
        ttk.Button(controls, text="Clear", command=self._clear_component_selections).pack(
            fill=tk.X, pady=2
        )
        ttk.Button(controls, text="Defaults", command=self._reset_component_defaults).pack(
            fill=tk.X, pady=2
        )
        ttk.Button(
            controls,
            text="Download to DB2",
            command=self._deploy_objects,
        ).pack(fill=tk.X, pady=12)

        selected_frame = ttk.Frame(frame)
        selected_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        ttk.Label(selected_frame, text="Components to Convert").pack(anchor=tk.W)
        self.selected_listbox = tk.Listbox(
            selected_frame, height=10, selectmode=tk.EXTENDED, exportselection=False
        )
        self.selected_listbox.pack(fill=tk.BOTH, expand=True, pady=(4, 0))

        return frame

    def _build_options_section(self, parent: ttk.Frame) -> ttk.LabelFrame:
        frame = ttk.LabelFrame(parent, text="Migration Options", padding=10)

        ttk.Checkbutton(
            frame,
            text="Extract Rows",
            variable=self.extract_rows_var,
        ).grid(row=0, column=0, sticky=tk.W)
        ttk.Checkbutton(
            frame,
            text="Extract LOBs",
            variable=self.extract_lobs_var,
        ).grid(row=0, column=1, sticky=tk.W, padx=(16, 0))
        ttk.Checkbutton(
            frame,
            text="Allow Nulls",
            variable=self.allow_nulls_var,
        ).grid(row=0, column=2, sticky=tk.W, padx=(16, 0))
        ttk.Checkbutton(
            frame,
            text="Truncate Target",
            variable=self.truncate_target_var,
        ).grid(row=0, column=3, sticky=tk.W, padx=(16, 0))

        for column in range(4):
            frame.grid_columnconfigure(column, weight=1)
        return frame

    def _refresh_component_lists(self) -> None:
        if not self.available_listbox or not self.selected_listbox:
            return
        self.available_listbox.delete(0, tk.END)
        self.selected_listbox.delete(0, tk.END)
        for key, label, _ in self.component_definitions:
            if self.component_vars[key].get():
                self.selected_listbox.insert(tk.END, label)
            else:
                self.available_listbox.insert(tk.END, label)

    @staticmethod
    def _collect_connection_details(variables: Dict[str, tk.StringVar]) -> Dict[str, str]:
        return {key: value.get().strip() for key, value in variables.items()}

    def _load_schema_file(self, file_path: str) -> None:
        try:
            with open(file_path, "r", encoding="utf-8") as sql_file:
                content = sql_file.read()
        except OSError as exc:
            messagebox.showerror("File Error", f"Could not read file: {exc}")
            return
        if self.input_text is not None:
            self.input_text.delete("1.0", tk.END)
            self.input_text.insert(tk.END, content)
        self.status_var.set(f"Loaded schema from {file_path}")

    def _open_file(self) -> None:
        file_path = filedialog.askopenfilename(
            title="Select schema file",
            filetypes=[("SQL files", "*.sql"), ("All files", "*.*")],
        )
        if not file_path:
            return
        self.source_schema_var.set(file_path)
        self._load_schema_file(file_path)

    def _load_schema_from_entry(self) -> None:
        file_path = self.source_schema_var.get().strip()
        if not file_path:
            messagebox.showwarning("No File", "Enter the path to a schema file to load.")
            return
        self._load_schema_file(file_path)

    def _browse_output_directory(self) -> None:
        directory = filedialog.askdirectory(title="Select output directory")
        if directory:
            self.output_directory_var.set(directory)
            self.status_var.set(f"Output directory set to {directory}")

    def _on_source_vendor_change(self, *_event: object) -> None:
        vendor = self.source_var.get().upper()
        if self.source_test_button is not None:
            self.source_test_button.configure(text=f"Test Connection to {vendor}")
        self.converter = None
        self.status_var.set(f"Source vendor set to {vendor}.")

    def _toggle_db2_installed(self) -> None:
        if self.db2_not_installed_var.get():
            self.status_var.set("DB2 installation marked as unavailable. Download client tools before deployment.")
        else:
            self.status_var.set("DB2 installation available for deployment.")

    def _test_source_connection(self) -> None:
        vendor = self.source_var.get().upper()
        details = self._collect_connection_details(self.source_conn_vars)
        summary = ", ".join(f"{key}={value}" for key, value in details.items() if value)
        message = summary or "No connection parameters provided."
        messagebox.showinfo(
            "Test Connection",
            f"Simulated connection test for {vendor}.\n\n{message}",
        )

    def _test_target_connection(self) -> None:
        details = self._collect_connection_details(self.target_conn_vars)
        summary = ", ".join(f"{key}={value}" for key, value in details.items() if value)
        messagebox.showinfo(
            "Test Connection",
            f"Simulated connection test for DB2.\n\n{summary or 'No connection parameters provided.'}",
        )

    def _selected_component_keys(self, listbox: tk.Listbox) -> Dict[str, str]:
        selections = listbox.curselection()
        labels = [listbox.get(index) for index in selections]
        keys = {}
        for label in labels:
            key = self.label_to_key.get(label)
            if key:
                keys[label] = key
        return keys

    def _add_selected_components(self) -> None:
        if not self.available_listbox:
            return
        mapping = self._selected_component_keys(self.available_listbox)
        for key in mapping.values():
            self.component_vars[key].set(True)
        self._refresh_component_lists()

    def _remove_selected_components(self) -> None:
        if not self.selected_listbox:
            return
        mapping = self._selected_component_keys(self.selected_listbox)
        for key in mapping.values():
            self.component_vars[key].set(False)
        self._refresh_component_lists()

    def _select_all_components(self) -> None:
        for key in self.component_vars:
            self.component_vars[key].set(True)
        self._refresh_component_lists()

    def _clear_component_selections(self) -> None:
        for key in self.component_vars:
            self.component_vars[key].set(False)
        self._refresh_component_lists()

    def _reset_component_defaults(self) -> None:
        for key, _label, default in self.component_definitions:
            self.component_vars[key].set(default)
        self._refresh_component_lists()

    def _generate_scripts(self) -> None:
        messagebox.showinfo(
            "Generate Scripts",
            "Data movement script generation is not automated in this demo.",
        )

    def _deploy_objects(self) -> None:
        messagebox.showinfo(
            "Deploy",
            "Deployment to DB2 is not automated in this demo. Export the converted SQL instead.",
        )

    def _execute_db2_script(self) -> None:
        messagebox.showinfo(
            "Execute",
            "DB2 script execution is not available. Use your preferred DB2 tooling to run the generated SQL.",
        )

    def _clear_output(self) -> None:
        if self.output_text is not None:
            self.output_text.delete("1.0", tk.END)
        self.status_var.set("Cleared converted schema output.")

    def _ensure_converter(self) -> SchemaConverter:
        source = self.source_var.get()
        if self.converter is None or self.converter.source != source:
            self.converter = SchemaConverter(source)
        return self.converter

    def _convert(self) -> None:
        if self.input_text is None or self.output_text is None:
            return
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
        self.output_text.insert(
            tk.END, result.ddl or "-- No tables were parsed from the input."
        )

        if result.tables:
            summary = f"Converted {len(result.tables)} table(s)."
        else:
            summary = "No tables detected in the provided schema."
        component_summary = ", ".join(
            self.component_labels[key]
            for key in selected_components
            if key in self.component_labels
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
        self._refresh_component_lists()

    def _save_output(self) -> None:
        if self.output_text is None:
            return
        ddl = self.output_text.get("1.0", tk.END).strip()
        if not ddl:
            messagebox.showwarning("No Output", "There is no converted schema to save.")
            return
        initial_dir = self.output_directory_var.get() or None
        file_path = filedialog.asksaveasfilename(
            title="Save converted schema",
            defaultextension=".sql",
            initialdir=initial_dir,
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
