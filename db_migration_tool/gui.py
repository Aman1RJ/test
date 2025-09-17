"""Tkinter GUI for the database migration tool."""
from __future__ import annotations

import tkinter as tk
from tkinter import filedialog, messagebox, scrolledtext, ttk
from typing import Optional

from .converter import SchemaConverter


class MigrationGUI:
    """Encapsulates the Tkinter-based GUI."""

    def __init__(self, root: tk.Tk):
        self.root = root
        self.root.title("DB Schema Migration to IBM DB2")
        self.root.geometry("960x720")

        self.source_var = tk.StringVar(value="mssql")
        self.converter: Optional[SchemaConverter] = None

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

        if result.warnings:
            summary += f" Review {len(result.warnings)} warning(s)."
            messagebox.showwarning("Conversion Warnings", "\n".join(result.warnings))

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
