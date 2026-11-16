"""Saved templates (TPL-1 .. TPL-7): one readable JSON file per template."""
from __future__ import annotations

import copy
import json
import os
import re
import uuid
from datetime import datetime
from pathlib import Path

SCHEMA_VERSION = 1


def default_output():
    return {
        "format": "xlsx",              # OUT-1: xlsx | csv
        "folder": "",
        "name_pattern": "{client}_{task}_{yyyymm}",   # OUT-5
        "csv_encoding": "utf-8-sig",   # OUT-3
        "csv_delimiter": ",",
        "source_file": True,           # OUT-4
        "source_sheet": False,
        "source_row": True,
        "indian_format": True,         # OUT-7
        "issues_sheet": True,          # OUT-8
    }


def default_input():
    return {
        "pattern": "*",                # IN-2
        "include_subfolders": False,
        "sheet_mode": "first",         # IN-5: first | name | pattern
        "sheet_value": "",
        "header_row": None,            # IN-6: None = auto
        "trailer_words": ["Total", "Grand Total"],   # IN-7
        "csv_delimiter": "auto",       # IN-4
    }


def new_column(name, col_type="text", required=False, aliases=None, rules=None, total=False,
               date_order="DMY"):
    return {"name": name, "type": col_type, "date_order": date_order, "required": required,
            "aliases": list(aliases or []), "rules": list(rules or []), "total": total, "include": True}


class Template:
    def __init__(self, client="", task="", columns=None, **kw):
        now = datetime.now().isoformat(timespec="seconds")
        self.id = kw.get("id") or uuid.uuid4().hex[:12]
        self.client = client
        self.task = task
        self.version = kw.get("version", 0)
        self.created = kw.get("created", now)
        self.modified = kw.get("modified", now)
        self.columns = columns or []
        self.input = {**default_input(), **(kw.get("input") or {})}
        self.output = {**default_output(), **(kw.get("output") or {})}
        self.duplicate_keys = kw.get("duplicate_keys", [])      # [{"columns":[...], "severity":"error"}]
        self.extra_columns = kw.get("extra_columns", "drop")     # MAP-7: drop | keep
        self.gstin_exceptions = kw.get("gstin_exceptions", [])
        self.path = None

    # ---- serialisation
    def to_dict(self):
        return {"schema_version": SCHEMA_VERSION, "id": self.id, "client": self.client, "task": self.task,
                "version": self.version, "created": self.created, "modified": self.modified,
                "input": self.input, "columns": self.columns, "duplicate_keys": self.duplicate_keys,
                "extra_columns": self.extra_columns, "gstin_exceptions": self.gstin_exceptions,
                "output": self.output}

    @classmethod
    def from_dict(cls, d):
        d = dict(d)
        d.pop("schema_version", None)
        client, task, cols = d.pop("client", ""), d.pop("task", ""), d.pop("columns", [])
        cols = [{**new_column(c["name"]), **c} for c in cols]
        return cls(client, task, cols, **d)

    def copy(self):
        t = Template.from_dict(copy.deepcopy(self.to_dict()))
        t.path = self.path
        return t

    def column(self, name):
        for c in self.columns:
            if c["name"] == name:
                return c
        return None

    def known_names(self):
        from .mapping import norm
        names = set()
        for c in self.columns:
            names.add(norm(c["name"]))
            names.update(norm(a) for a in c.get("aliases", []))
        return names

    def add_alias(self, column_name, alias):
        """MAP-5: learn an alias."""
        c = self.column(column_name)
        if c is not None and alias not in c["aliases"] and alias != c["name"]:
            c["aliases"].append(alias)
            return True
        return False


def _slug(s):
    s = re.sub(r"[^A-Za-z0-9]+", "-", s.strip()).strip("-")
    return s or "untitled"


def default_store_folder() -> Path:
    base = Path(os.environ.get("USERPROFILE") or Path.home())
    return base / "Documents" / "Sankalan" / "Templates"


class TemplateStore:
    """TPL-2, TPL-4, TPL-5: templates as JSON files in one folder (can be a shared network folder)."""

    def __init__(self, folder=None):
        self.folder = Path(folder) if folder else default_store_folder()
        self.folder.mkdir(parents=True, exist_ok=True)

    def _path_for(self, t: Template) -> Path:
        return self.folder / f"{_slug(t.client)}__{_slug(t.task)}.json"

    def list(self, search: str = ""):
        out = []
        for p in sorted(self.folder.glob("*.json")):
            try:
                t = Template.from_dict(json.loads(p.read_text(encoding="utf-8")))
            except Exception:
                continue
            t.path = p
            if search:
                s = search.lower()
                if s not in t.client.lower() and s not in t.task.lower():
                    continue
            out.append(t)
        return sorted(out, key=lambda t: (t.client.lower(), t.task.lower()))

    def exists(self, client, task, exclude_id=None):
        return any(t.client.lower() == client.lower() and t.task.lower() == task.lower()
                   and t.id != exclude_id for t in self.list())

    def save(self, t: Template) -> Path:
        """TPL-7: every save bumps the version and the modified date."""
        if not t.client.strip() or not t.task.strip():
            raise ValueError("Client and task names are required")
        if self.exists(t.client, t.task, exclude_id=t.id):
            raise ValueError(f'A template "{t.client} → {t.task}" already exists')
        t.version += 1
        t.modified = datetime.now().isoformat(timespec="seconds")
        new_path = self._path_for(t)
        tmp = new_path.with_suffix(".json.tmp")
        tmp.write_text(json.dumps(t.to_dict(), indent=2, ensure_ascii=False), encoding="utf-8")
        os.replace(tmp, new_path)
        if t.path and Path(t.path) != new_path and Path(t.path).exists():
            Path(t.path).unlink()  # renamed
        t.path = new_path
        return new_path

    def duplicate(self, t: Template, new_task: str) -> Template:
        d = t.copy()
        d.id = uuid.uuid4().hex[:12]
        d.task, d.version, d.path = new_task, 0, None
        d.created = datetime.now().isoformat(timespec="seconds")
        self.save(d)
        return d

    def rename(self, t: Template, client: str, task: str) -> Template:
        t.client, t.task = client, task
        self.save(t)
        return t

    def delete(self, t: Template):
        if t.path and Path(t.path).exists():
            Path(t.path).unlink()
