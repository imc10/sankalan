"""The five screens: Templates, Add files, Map columns, Validate, Output."""
from __future__ import annotations

from datetime import datetime
from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (QButtonGroup, QCheckBox, QComboBox, QFrame, QGridLayout, QHBoxLayout,
                               QLineEdit, QMenu, QRadioButton, QScrollArea, QSpinBox, QSplitter,
                               QTableWidgetItem, QVBoxLayout, QWidget, QHeaderView, QSizePolicy)

from ..core import convert as cv
from ..core.mapping import norm
from ..core.output import build_filename
from ..core.session import source_key
from ..core.validation import RULES
from . import style as S
from .widgets import Banner, RulesEditor, Tile, button, card, item, label, restyle, table


def _date(iso):
    try:
        return datetime.fromisoformat(iso).strftime("%d-%m-%Y")
    except Exception:
        return iso or ""


class Page(QScrollArea):
    def __init__(self, main, title, subtitle=""):
        super().__init__()
        self.main = main
        self.setWidgetResizable(True)
        self.setFrameShape(QFrame.Shape.NoFrame)
        inner = QWidget()
        inner.setObjectName("page")
        self.setWidget(inner)
        self.lay = QVBoxLayout(inner)
        self.lay.setContentsMargins(32, 24, 32, 24)
        self.lay.setSpacing(16)
        self.title = label(title, "h1")
        self.subtitle = label(subtitle, "sub", wrap=True)
        head = QVBoxLayout()
        head.setSpacing(4)
        head.addWidget(self.title)
        head.addWidget(self.subtitle)
        self.head_row = QHBoxLayout()
        self.head_row.addLayout(head, 1)
        self.lay.addLayout(self.head_row)

    def footer(self, back=None, nxt=None):
        row = QHBoxLayout()
        if back:
            row.addWidget(back)
        row.addStretch()
        if nxt:
            if isinstance(nxt, (list, tuple)):
                for b in nxt:
                    row.addWidget(b)
            else:
                row.addWidget(nxt)
        self.lay.addLayout(row)


# =============================================================================== 1. Templates
class HomePage(Page):
    def __init__(self, main):
        super().__init__(main, "Templates", "Run a saved template on this month's files, or set up a new consolidation.")
        self.new_btn = button("+  New consolidation", "primary", main.new_consolidation, "newConsolidation")
        self.head_row.addWidget(self.new_btn, 0, Qt.AlignmentFlag.AlignBottom)
        bar = QHBoxLayout()
        col = QVBoxLayout()
        col.addWidget(label("Search by client or task", "small"))
        self.search = QLineEdit()
        self.search.setObjectName("tplSearch")
        self.search.setPlaceholderText("e.g. Acme, purchase")
        self.search.textChanged.connect(self.refresh)
        self.search.setMaximumWidth(360)
        col.addWidget(self.search)
        bar.addLayout(col)
        bar.addStretch()
        self.folder_lbl = label("", "sub")
        bar.addWidget(self.folder_lbl, 0, Qt.AlignmentFlag.AlignBottom)
        bar.addWidget(button("Change…", slot=main.change_template_folder, obj="changeFolder"), 0,
                      Qt.AlignmentFlag.AlignBottom)
        self.lay.addLayout(bar)
        self.table = table(["Client", "Task", "Columns", "Output", "Modified", "Version", ""])
        self.table.setObjectName("templatesTable")
        self.table.setMinimumHeight(320)
        self.lay.addWidget(self.table, 1)
        self.count = label("", "small", wrap=True)
        self.lay.addWidget(self.count)

    def refresh(self):
        store = self.main.store
        self.folder_lbl.setText(f"Templates folder: {store.folder}")
        ts = store.list(self.search.text())
        self.templates = ts
        self.table.setRowCount(0)
        for t in ts:
            r = self.table.rowCount()
            self.table.insertRow(r)
            self.table.setItem(r, 0, item(t.client, bold=True))
            self.table.setItem(r, 1, item(t.task))
            self.table.setItem(r, 2, item(len(t.columns)))
            self.table.setItem(r, 3, item("." + t.output.get("format", "xlsx")))
            self.table.setItem(r, 4, item(_date(t.modified)))
            self.table.setItem(r, 5, item(f"v{t.version}", color=S.QUIET))
            w = QWidget()
            hl = QHBoxLayout(w)
            hl.setContentsMargins(4, 2, 4, 2)
            run = button("Run", "primary", lambda _=False, t=t: self.main.start_run(t), "run")
            edit = button("Edit", slot=lambda _=False, t=t: self.main.edit_template(t), obj="edit")
            more = button("⋯", obj="more")
            more.setAccessibleName("More actions: duplicate, rename, delete")
            menu = QMenu(more)
            menu.addAction("Duplicate…", lambda t=t: self.main.duplicate_template(t))
            menu.addAction("Rename…", lambda t=t: self.main.rename_template(t))
            menu.addAction("Delete…", lambda t=t: self.main.delete_template(t))
            more.setMenu(menu)
            for b, wd in ((run, 70), (edit, 70), (more, 44)):
                b.setFixedWidth(wd)
                hl.addWidget(b)
            hl.addStretch()
            self.table.setCellWidget(r, 6, w)
        self.table.resizeRowsToContents()
        clients = len({t.client.lower() for t in ts})
        self.count.setText(f"{len(ts)} template{'s' if len(ts) != 1 else ''} across {clients} client"
                           f"{'s' if clients != 1 else ''}. Each template is one JSON file in the templates folder; "
                           f"point two PCs at one shared folder to use the same templates.")


# =============================================================================== 2. Add files
class DropZone(QFrame):
    def __init__(self, on_drop):
        super().__init__()
        self.setObjectName("drop")
        self.setAcceptDrops(True)
        self.on_drop = on_drop

    def dragEnterEvent(self, e):
        if e.mimeData().hasUrls():
            e.acceptProposedAction()

    def dropEvent(self, e):
        paths = [u.toLocalFile() for u in e.mimeData().urls() if u.isLocalFile()]
        if paths:
            self.on_drop(paths)


class FilesPage(Page):
    def __init__(self, main):
        super().__init__(main, "Add files")
        top = QHBoxLayout()
        self.drop = DropZone(self.add_paths)
        dl = QHBoxLayout(self.drop)
        dl.setContentsMargins(18, 18, 18, 18)
        dl.addStretch()
        dl.addWidget(label("Drag files or a folder here"))
        dl.addWidget(button("Add files…", slot=self.pick_files, obj="addFiles"))
        dl.addWidget(button("Add folder…", slot=self.pick_folder, obj="addFolder"))
        dl.addStretch()
        top.addWidget(self.drop, 1)
        opts, ol = card()
        ol.addWidget(label("Folder options", "h2"))
        g = QHBoxLayout()
        c1 = QVBoxLayout()
        c1.addWidget(label("File name pattern", "small"))
        self.pattern = QLineEdit("*")
        self.pattern.setObjectName("pattern")
        c1.addWidget(self.pattern)
        g.addLayout(c1)
        self.subfolders = QCheckBox("Include subfolders")
        self.subfolders.setObjectName("subfolders")
        g.addWidget(self.subfolders, 0, Qt.AlignmentFlag.AlignBottom)
        ol.addLayout(g)
        top.addWidget(opts, 1)
        self.lay.addLayout(top)

        self.table = table(["File", "Sheet", "Header row", "Rows", "Columns", "Status"])
        self.table.setObjectName("filesTable")
        self.table.setMinimumHeight(220)
        self.table.itemSelectionChanged.connect(self.show_preview)
        self.lay.addWidget(self.table)
        frow = QHBoxLayout()
        self.total_lbl = label("", "small")
        self.skipped_lbl = label("", "small", wrap=True)
        frow.addWidget(self.total_lbl)
        frow.addStretch()
        frow.addWidget(self.skipped_lbl)
        frow.addWidget(button("Remove file", slot=self.remove_selected, obj="removeFile"))
        self.lay.addLayout(frow)

        pv, pl = card()
        hr = QHBoxLayout()
        hc = QVBoxLayout()
        self.pv_title = label("Preview", "h2")
        self.pv_note = label("Select a file to see its first rows.", "small", wrap=True)
        hc.addWidget(self.pv_title)
        hc.addWidget(self.pv_note)
        hr.addLayout(hc, 1)
        self.sheet = QComboBox()
        self.sheet.setObjectName("sheetCombo")
        self.header = QSpinBox()
        self.header.setObjectName("headerRow")
        self.header.setRange(0, 1000)
        self.header.setSpecialValueText("Auto")
        for cap, w in (("Sheet", self.sheet), ("Header row", self.header)):
            c = QVBoxLayout()
            c.addWidget(label(cap, "small"))
            c.addWidget(w)
            hr.addLayout(c)
        self.apply_btn = button("Apply", slot=self.apply_options, obj="applyOptions")
        self.pw_btn = button("Enter password…", slot=self.ask_password, obj="enterPassword")
        hr.addWidget(self.apply_btn, 0, Qt.AlignmentFlag.AlignBottom)
        hr.addWidget(self.pw_btn, 0, Qt.AlignmentFlag.AlignBottom)
        pl.addLayout(hr)
        self.preview = table([], stretch_last=False)
        self.preview.setObjectName("previewTable")
        self.preview.setMinimumHeight(180)
        pl.addWidget(self.preview)
        self.lay.addWidget(pv)
        self.next_btn = button("Next: Map columns", "primary", main.go_map, "nextMap")
        self.footer(button("Back", slot=main.go_home, obj="back"), self.next_btn)

    @property
    def session(self):
        return self.main.session

    def on_enter(self):
        t = self.session.template
        self.subtitle.setText(f"{t.client} · {t.task}. Check each file's sheet and header row before mapping.")
        self.pattern.setText(t.input.get("pattern") or "*")
        self.subfolders.setChecked(bool(t.input.get("include_subfolders")))
        self.refresh()

    def pick_files(self):
        paths = self.main.prompter.files()
        if paths:
            self.add_paths(paths)

    def pick_folder(self):
        f = self.main.prompter.folder("Choose the folder with this month's files")
        if f:
            self.add_paths([f])

    def add_paths(self, paths):
        self.session.template.input["pattern"] = self.pattern.text().strip() or "*"
        self.session.template.input["include_subfolders"] = self.subfolders.isChecked()
        self.session.add(paths)
        self.main.run_job(lambda p, c: self.session.load(p, c), self.after_load)

    def after_load(self, _=None):
        for p in list(self.session.needs_password):
            pw = self.main.prompter.password(p.name)
            if pw:
                self.session.set_password(p, pw)
        self.refresh()

    def refresh(self):
        s = self.session
        self.table.setRowCount(0)
        rows_total = 0
        for fd in s.sources:
            r = self.table.rowCount()
            self.table.insertRow(r)
            self.table.setItem(r, 0, item(fd.name, bold=True, data=str(fd.path)))
            self.table.setItem(r, 1, item(fd.sheet or "-"))
            self.table.setItem(r, 2, item(fd.header_row or "-"))
            self.table.setItem(r, 3, item(f"{len(fd.rows):,}" if fd.headers else "-", align_right=True))
            self.table.setItem(r, 4, item(len(fd.headers) if fd.headers else "-", align_right=True))
            if fd.status == "OK":
                st, color = "OK", S.OK
            elif fd.status == "warning":
                st, color = "Note: " + "; ".join(fd.notes), S.WARN
            elif fd.status == "password":
                st, color = "Password needed", S.ERROR
            else:
                st, color = "Error: " + fd.error, S.ERROR
            self.table.setItem(r, 5, item(st, color=color))
            rows_total += len(fd.rows)
        files = len({fd.path for fd in s.sources})
        self.total_lbl.setText(f"Total: {rows_total:,} rows from {files} file{'s' if files != 1 else ''}")
        sk = [f"{x.path.name} ({x.reason})" for x in s.skipped]
        self.skipped_lbl.setText(("Skipped: " + "; ".join(sk)) if sk else "")
        self.next_btn.setEnabled(bool(s.good_sources()))
        self.show_preview()

    def selected(self):
        r = self.table.currentRow()
        if r < 0 or r >= len(self.session.sources):
            return None
        return self.session.sources[r]

    def show_preview(self):
        fd = self.selected()
        self.preview.clear()
        self.preview.setRowCount(0)
        self.preview.setColumnCount(0)
        self.pw_btn.setVisible(bool(fd and fd.status == "password"))
        self.apply_btn.setEnabled(bool(fd and fd.status != "password"))
        if not fd:
            self.pv_title.setText("Preview")
            return
        self.pv_title.setText(f"Preview: {fd.name}")
        self.sheet.blockSignals(True)
        self.sheet.clear()
        self.sheet.addItems(fd.sheets or ([fd.sheet] if fd.sheet else []))
        if fd.sheet:
            self.sheet.setCurrentText(fd.sheet)
        self.sheet.blockSignals(False)
        o = self.session.file_options.get(str(fd.path), {})
        self.header.setValue(o.get("header_row") or 0)
        note = []
        if fd.header_row and fd.header_row != 1:
            note.append(f"Headers were found on row {fd.header_row}. Change it if that's wrong.")
        if fd.error:
            note.append(fd.error)
        self.pv_note.setText(" ".join(note) or "Rows as read from the file; the header row is highlighted.")
        prev = fd.preview[:200]
        width = max((len(r) for _, r in prev), default=0)
        self.preview.setColumnCount(width + 1)
        self.preview.setHorizontalHeaderLabels(["Row"] + [""] * width)
        from PySide6.QtGui import QColor
        for n, r in prev:
            i = self.preview.rowCount()
            self.preview.insertRow(i)
            self.preview.setItem(i, 0, item(n, color=S.QUIET))
            for j, v in enumerate(r):
                txt = cv.to_text(v)[0] if v is not None else ""
                it = item(txt, bold=(n == fd.header_row))
                if n == fd.header_row:
                    it.setBackground(QColor("#E5EEF8"))
                self.preview.setItem(i, j + 1, it)

    def apply_options(self):
        fd = self.selected()
        if not fd:
            return
        hr = self.header.value() or None
        sheet = self.sheet.currentText()
        if sheet and sheet != fd.sheet:
            self.session.set_file_options(fd.path, sheet_mode="name", sheet_value=sheet, header_row=hr)
        else:
            self.session.set_file_options(fd.path, header_row=hr)
        self.refresh()

    def ask_password(self):
        fd = self.selected()
        if fd:
            pw = self.main.prompter.password(fd.name)
            if pw:
                self.session.set_password(fd.path, pw)
                self.refresh()

    def remove_selected(self):
        fd = self.selected()
        if fd:
            self.session.remove(fd.path)
            self.refresh()


# =============================================================================== 3. Map columns
TYPE_LABELS = [("text", "Text"), ("number", "Number"), ("date", "Date")]


class MapPage(Page):
    def __init__(self, main):
        super().__init__(main, "Map columns",
                         "Each row is one column in the output. Pick which column in each file feeds it.")
        self.banner = Banner()
        self.lay.addWidget(self.banner)
        body = QHBoxLayout()
        left = QVBoxLayout()
        self.grid = table([])
        self.grid.setObjectName("mapGrid")
        self.grid.setMinimumHeight(300)
        self.grid.itemSelectionChanged.connect(self.show_column)
        self.grid.cellClicked.connect(lambda r, c: self.show_column())
        left.addWidget(self.grid)
        ex, el = card(QHBoxLayout)
        self.extra_lbl = label("", "small", wrap=True)
        el.addWidget(self.extra_lbl, 1)
        self.drop_extra = QRadioButton("Leave them out")
        self.keep_extra = QRadioButton("Keep them as extra columns at the end")
        self.keep_extra.setObjectName("keepExtra")
        grp = QButtonGroup(self)
        grp.addButton(self.drop_extra)
        grp.addButton(self.keep_extra)
        self.keep_extra.toggled.connect(self.extra_changed)
        el.addWidget(self.drop_extra)
        el.addWidget(self.keep_extra)
        left.addWidget(ex)
        body.addLayout(left, 3)

        side, sl = card()
        side.setMinimumWidth(320)
        self.col_title = label("Select a column", "h2")
        sl.addWidget(self.col_title)
        g = QGridLayout()
        self.ctype = QComboBox()
        self.ctype.setObjectName("colType")
        for k, v in TYPE_LABELS:
            self.ctype.addItem(v, k)
        self.dorder = QComboBox()
        self.dorder.setObjectName("dateOrder")
        self.dorder.addItem("Day first (DD-MM-YYYY)", "DMY")
        self.dorder.addItem("Month first (MM-DD-YYYY)", "MDY")
        self.required = QCheckBox("Required")
        self.required.setObjectName("colRequired")
        self.include = QCheckBox("Include in output")
        self.include.setObjectName("colInclude")
        self.total = QCheckBox("Include in totals check")
        self.total.setObjectName("colTotal")
        g.addWidget(label("Type", "small"), 0, 0)
        g.addWidget(self.ctype, 1, 0)
        g.addWidget(label("Date order", "small"), 0, 1)
        g.addWidget(self.dorder, 1, 1)
        g.addWidget(self.required, 2, 0)
        g.addWidget(self.include, 2, 1)
        g.addWidget(self.total, 3, 0, 1, 2)
        sl.addLayout(g)
        self.type_note = label("Number reads 1,23,456.00, ₹ 500 and (1,234) as −1,234. Values that can't be "
                               "converted are flagged.", "small", wrap=True)
        sl.addWidget(self.type_note)
        sl.addWidget(label("Checks", "small"))
        self.rules = RulesEditor()
        sl.addWidget(self.rules)
        sl.addStretch()
        for w in (self.ctype, self.dorder):
            w.currentIndexChanged.connect(self.column_changed)
        for w in (self.required, self.include, self.total):
            w.toggled.connect(self.column_changed)
        self.rules.changed.connect(self.column_changed)
        body.addWidget(side, 2)
        self.lay.addLayout(body)
        self.next_btn = button("Next: Validate", "primary", main.go_validate, "nextValidate")
        self.footer(button("Back", slot=lambda: main.go("files"), obj="back"), self.next_btn)
        self._loading = False
        self._col = None

    @property
    def session(self):
        return self.main.session

    def on_enter(self):
        t = self.session.template
        self._loading = True
        self.keep_extra.setChecked(t.extra_columns == "keep")
        self.drop_extra.setChecked(t.extra_columns != "keep")
        self._loading = False
        self.refresh()

    def refresh(self):
        s = self.session
        cols = s.template.columns
        srcs = s.good_sources()
        multi = {}
        for fd in srcs:
            multi[fd.path] = multi.get(fd.path, 0) + 1
        heads = ["Output column", "Type", "Required"] + [
            (fd.path.stem + (f" › {fd.sheet}" if multi[fd.path] > 1 else "")) for fd in srcs]
        self.grid.blockSignals(True)
        self.grid.clear()
        self.grid.setColumnCount(len(heads))
        self.grid.setHorizontalHeaderLabels(heads)
        self.grid.setRowCount(len(cols))
        maps = [s.mapping_for(fd) for fd in srcs]
        for r, c in enumerate(cols):
            self.grid.setItem(r, 0, item(c["name"], bold=True,
                                         color=None if c.get("include", True) else S.QUIET))
            tl = dict(TYPE_LABELS)[c.get("type", "text")]
            if c.get("type") == "date":
                tl += " · " + ("DD-MM-YYYY" if c.get("date_order", "DMY") == "DMY" else "MM-DD-YYYY")
            self.grid.setItem(r, 1, item(tl, color=S.QUIET))
            self.grid.setItem(r, 2, item("Yes" if c.get("required") else "-"))
            for j, (fd, m) in enumerate(zip(srcs, maps)):
                src, meth = m.get(c["name"], (None, None))
                combo = QComboBox()
                combo.setProperty("target", c["name"])
                combo.setProperty("source", source_key(fd))
                combo.addItem("Choose…" if c.get("required") else "(none)", None)
                for h in fd.headers:
                    combo.addItem(h + ("  · alias" if (h == src and meth == "alias") else ""), h)
                combo.setCurrentIndex(max(0, combo.findData(src)) if src else 0)
                if not src and c.get("include", True):
                    combo.setStyleSheet(
                        f"QComboBox {{ border: 2px solid {'#C42B1C' if c.get('required') else '#C19C00'};"
                        f" background: {S.ERROR_BG if c.get('required') else S.WARN_BG}; }}")
                combo.currentIndexChanged.connect(lambda _i, cb=combo, fd=fd: self.mapping_changed(cb, fd))
                self.grid.setCellWidget(r, 3 + j, combo)
        self.grid.blockSignals(False)
        self.grid.resizeColumnsToContents()
        # banner
        inc = [c for c in cols if c.get("include", True)]
        unmatched = [(fd, t) for fd, t in s.unmatched() if s.template.column(t).get("include", True)]
        fully = sum(1 for c in inc if all(m[c["name"]][0] for m in maps))
        probs = s.mapping_problems()
        if not srcs:
            self.banner.show_msg("warning", "No readable files", "Go back and add files.")
        elif not unmatched:
            self.banner.show_msg("ok", f"All {len(inc)} output columns matched in every file.")
        else:
            detail = "; ".join(f"{t} has no match in {fd.name}" for fd, t in unmatched[:4])
            if len(unmatched) > 4:
                detail += f"; and {len(unmatched) - 4} more"
            self.banner.show_msg("error" if probs else "warning",
                                 f"{fully} of {len(inc)} output columns matched in every file.", detail + ".")
        extras = s.extra_headers()
        self.extra_lbl.setText("Columns in the files that aren't mapped: " + (", ".join(extras) if extras else "none"))
        self.next_btn.setEnabled(bool(srcs))
        if self._col is None and cols:
            self.grid.selectRow(0)
        self.show_column()

    def mapping_changed(self, combo, fd):
        target = combo.property("target")
        header = combo.currentData()
        save_alias = False
        col = self.session.template.column(target)
        if header and norm(header) != norm(target) and norm(header) not in {norm(a) for a in col.get("aliases", [])}:
            save_alias = self.main.prompter.confirm(
                "Save alias?", f'{fd.name} has a column "{header}". Save it as an alias of {target} in this '
                               f'template, so next month\'s file maps itself?', yes="Map and save as alias",
                no="This run only")
        self.session.set_mapping(fd, target, header, save_alias)
        self.refresh()

    def extra_changed(self):
        if self._loading:
            return
        self.session.template.extra_columns = "keep" if self.keep_extra.isChecked() else "drop"
        self.session.validation = None
        self.refresh()

    def show_column(self):
        r = self.grid.currentRow()
        cols = self.session.template.columns if self.main.session else []
        if r < 0 or r >= len(cols):
            return
        c = cols[r]
        self._col = c["name"]
        self._loading = True
        self.col_title.setText(c["name"])
        self.ctype.setCurrentIndex(self.ctype.findData(c.get("type", "text")))
        self.dorder.setCurrentIndex(self.dorder.findData(c.get("date_order", "DMY")))
        self.dorder.setEnabled(c.get("type") == "date")
        self.required.setChecked(bool(c.get("required")))
        self.include.setChecked(bool(c.get("include", True)))
        self.total.setChecked(bool(c.get("total")))
        self.total.setEnabled(c.get("type") == "number")
        self.rules.set_rules(c.get("rules", []))
        self._loading = False

    def column_changed(self, *_):
        if self._loading or not self._col:
            return
        c = self.session.template.column(self._col)
        c["type"] = self.ctype.currentData()
        c["date_order"] = self.dorder.currentData()
        c["required"] = self.required.isChecked()
        c["include"] = self.include.isChecked()
        c["total"] = self.total.isChecked() and c["type"] == "number"
        c["rules"] = self.rules.rules()
        self.session.validation = None
        row = self.grid.currentRow()
        self.refresh()
        self.grid.selectRow(row)


# =============================================================================== 4. Validate
class ValidatePage(Page):
    def __init__(self, main):
        super().__init__(main, "Validation results")
        self.banner = Banner()
        self.lay.addWidget(self.banner)
        tiles = QHBoxLayout()
        self.t_err, self.t_warn, self.t_rows, self.t_hidden = (Tile("Errors"), Tile("Warnings"),
                                                               Tile("Rows checked"), Tile("Hidden data skipped"))
        for t in (self.t_err, self.t_warn, self.t_rows, self.t_hidden):
            tiles.addWidget(t)
        self.lay.addLayout(tiles)
        bc, bl = card()
        bl.addWidget(label("By check", "h2"))
        self.by_rule = table(["Check", "Severity", "Count", "Files"])
        self.by_rule.setObjectName("byRule")
        self.by_rule.setMinimumHeight(140)
        bl.addWidget(self.by_rule)
        self.lay.addWidget(bc)
        ic, il = card()
        ir = QHBoxLayout()
        self.tabs = {}
        for key, cap in (("all", "All"), ("error", "Errors"), ("warning", "Warnings")):
            b = button(cap, "tab", lambda _=False, k=key: self.set_filter(k), f"filter_{key}")
            self.tabs[key] = b
            ir.addWidget(b)
        ir.addStretch()
        ir.addWidget(button("Export issue list (.xlsx)", slot=self.export, obj="exportIssues"))
        il.addLayout(ir)
        self.issues = table(["File", "Sheet", "Row", "Column", "Value", "Problem"])
        self.issues.setObjectName("issuesTable")
        self.issues.setMinimumHeight(220)
        il.addWidget(self.issues)
        self.more_lbl = label("", "small")
        il.addWidget(self.more_lbl)
        self.lay.addWidget(ic)
        self.override_btn = button("Write output anyway…", "danger", self.override, "writeAnyway")
        self.recheck_btn = button("Re-check files", slot=main.recheck, obj="recheck")
        self.next_btn = button("Next: Output", "primary", lambda: main.go_output(False), "nextOutput")
        self.footer(button("Back", slot=lambda: main.go("map"), obj="back"),
                    [self.override_btn, self.recheck_btn, self.next_btn])
        self.filter = "error"

    def on_enter(self):
        v = self.main.session.validation
        s = self.main.session
        errs, warns = v.errors, v.warnings
        self.subtitle.setText(f"{v.rows_checked:,} rows checked against this template's rules.")
        if errs:
            files = len({i.file for i in errs})
            self.banner.show_msg("error", f"Output not written: {len(errs)} error{'s' if len(errs) != 1 else ''} "
                                          f"in {files} file{'s' if files != 1 else ''}",
                                 "Fix them in the source files, then re-check. Warnings don't stop the run.")
            self.filter = "error"
        else:
            self.banner.show_msg("ok", "No errors", f"{len(warns)} warning{'s' if len(warns) != 1 else ''}; "
                                                    "you can continue to the output.")
            self.filter = "all"
        self.t_err.set(str(len(errs)), S.ERROR if errs else None)
        self.t_warn.set(str(len(warns)), S.WARN if warns else None)
        self.t_rows.set(f"{v.rows_checked:,}")
        hr = sum(fd.hidden_rows for fd in s.sources)
        hs = sum(len(fd.hidden_sheets) for fd in {fd.path: fd for fd in s.sources}.values())
        self.t_hidden.set(f"{hr} row{'s' if hr != 1 else ''}, {hs} sheet{'s' if hs != 1 else ''}")
        self.by_rule.setRowCount(0)
        for (rule, sev), e in sorted(v.by_rule().items(), key=lambda kv: (kv[0][1] != "error", kv[0][0])):
            r = self.by_rule.rowCount()
            self.by_rule.insertRow(r)
            name = {"mapping": "Required column mapped", "read": "File readable"}.get(rule, RULES.get(rule, rule))
            self.by_rule.setItem(r, 0, item(name))
            self.by_rule.setItem(r, 1, item(sev.capitalize(), bold=True, color=S.ERROR if sev == "error" else S.WARN))
            self.by_rule.setItem(r, 2, item(e["count"], bold=True, align_right=True))
            self.by_rule.setItem(r, 3, item(", ".join(e["files"]), color=S.QUIET))
        self.override_btn.setVisible(bool(errs))
        self.recheck_btn.setObjectName("primary" if errs else "")
        restyle(self.recheck_btn)
        self.next_btn.setVisible(not errs)
        self.set_filter(self.filter)

    def set_filter(self, key):
        self.filter = key
        v = self.main.session.validation
        for k, b in self.tabs.items():
            n = len(v.issues) if k == "all" else len([i for i in v.issues if i.severity == k])
            b.setText({"all": "All", "error": "Errors", "warning": "Warnings"}[k] + f" ({n})")
            b.setProperty("selected", k == key)
            restyle(b)
        rows = v.issues if key == "all" else [i for i in v.issues if i.severity == key]
        self.issues.setRowCount(0)
        limit = 2000
        self.issues.setRowCount(min(len(rows), limit))
        for r, i in enumerate(rows[:limit]):
            self.issues.setItem(r, 0, item(i.file, bold=True))
            self.issues.setItem(r, 1, item(i.sheet))
            self.issues.setItem(r, 2, item(f"{i.row:,}" if i.row else "-", align_right=True))
            self.issues.setItem(r, 3, item(i.column))
            self.issues.setItem(r, 4, item(i.value))
            self.issues.setItem(r, 5, item(i.message, color=S.ERROR if i.severity == "error" else None))
        self.more_lbl.setText(f"Showing the first {limit:,} of {len(rows):,}. Export the list to see all."
                              if len(rows) > limit else "")

    def export(self):
        s = self.main.session
        default = str(Path(s.template.output.get("folder") or Path.home()) /
                      f"{s.template.client}_{s.template.task}_issues.xlsx".replace(" ", "-"))
        path = self.main.prompter.save_file("Export issue list", default)
        if path:
            s.export_issues(path)
            self.main.prompter.info("Exported", f"Issue list saved to {path}")

    def override(self):
        n = len(self.main.session.validation.errors)
        if self.main.prompter.confirm("Write output anyway?",
                                      f"{n} error{'s' if n != 1 else ''} will be written into the output as they are. "
                                      "Continue only if you have checked them.", yes="Write anyway"):
            self.main.go_output(True)


# =============================================================================== 5. Output
class OutputPage(Page):
    def __init__(self, main):
        super().__init__(main, "Output", "Choose how the merged file is written, then check the run summary.")
        self.banner = Banner()
        self.open_file = button("Open file", "primary", main.open_output, "openFile")
        self.open_folder = button("Open folder", slot=main.open_output_folder, obj="openFolder")
        self.lay.addWidget(self.banner)
        ob = QHBoxLayout()
        ob.addStretch()
        ob.addWidget(self.open_file)
        ob.addWidget(self.open_folder)
        self.lay.addLayout(ob)
        body = QHBoxLayout()
        sc, sl = card()
        sl.addWidget(label("Output settings", "h2"))
        fr = QHBoxLayout()
        self.fmt_xlsx = QRadioButton("Excel (.xlsx)")
        self.fmt_xlsx.setObjectName("fmtXlsx")
        self.fmt_csv = QRadioButton("CSV")
        self.fmt_csv.setObjectName("fmtCsv")
        g = QButtonGroup(self)
        g.addButton(self.fmt_xlsx)
        g.addButton(self.fmt_csv)
        fr.addWidget(self.fmt_xlsx)
        fr.addWidget(self.fmt_csv)
        fr.addStretch()
        sl.addWidget(label("Format", "small"))
        sl.addLayout(fr)
        self.csv_box = QWidget()
        cb = QHBoxLayout(self.csv_box)
        cb.setContentsMargins(0, 0, 0, 0)
        self.csv_enc = QComboBox()
        self.csv_enc.setObjectName("csvEncoding")
        self.csv_enc.addItem("UTF-8 with BOM (opens in Excel)", "utf-8-sig")
        self.csv_enc.addItem("UTF-8", "utf-8")
        self.csv_delim = QComboBox()
        self.csv_delim.setObjectName("csvDelimiter")
        for cap, d in (("Comma", ","), ("Semicolon", ";"), ("Tab", "\t"), ("Pipe", "|")):
            self.csv_delim.addItem(cap, d)
        cb.addWidget(self.csv_enc)
        cb.addWidget(self.csv_delim)
        sl.addWidget(self.csv_box)
        sl.addWidget(label("Save to folder", "small"))
        frow = QHBoxLayout()
        self.folder = QLineEdit()
        self.folder.setObjectName("outFolder")
        frow.addWidget(self.folder)
        frow.addWidget(button("Browse…", slot=self.browse, obj="browseOut"))
        sl.addLayout(frow)
        sl.addWidget(label("File name pattern", "small"))
        self.pattern = QLineEdit()
        self.pattern.setObjectName("namePattern")
        sl.addWidget(self.pattern)
        self.name_preview = label("", "small")
        sl.addWidget(self.name_preview)
        sl.addWidget(label("Add to the file", "small"))
        self.cb_file = QCheckBox("Source File column")
        self.cb_sheet = QCheckBox("Source Sheet column")
        self.cb_row = QCheckBox("Source Row column")
        self.cb_indian = QCheckBox("Indian number format (1,23,45,678.00)")
        self.cb_issues = QCheckBox("Issues sheet listing the warnings")
        for name, cbx in (("cbFile", self.cb_file), ("cbSheet", self.cb_sheet), ("cbRow", self.cb_row),
                          ("cbIndian", self.cb_indian), ("cbIssues", self.cb_issues)):
            cbx.setObjectName(name)
            sl.addWidget(cbx)
        self.write_btn = button("Write output", "primary", self.write, "writeOutput")
        sl.addWidget(self.write_btn)
        body.addWidget(sc, 1)
        right = QVBoxLayout()
        sm, sml = card()
        sml.addWidget(label("Run summary", "h2"))
        self.summary = QGridLayout()
        sml.addLayout(self.summary)
        self.hidden_lbl = label("", wrap=True)
        sml.addWidget(self.hidden_lbl)
        right.addWidget(sm)
        tc, tl = card()
        tl.addWidget(label("Totals check", "h2"))
        tl.addWidget(label("Sum of all input files vs the output file", "small"))
        self.totals = table(["Column", "Input total (₹)", "Output total (₹)", "Result"])
        self.totals.setObjectName("totalsTable")
        self.totals.setMinimumHeight(120)
        tl.addWidget(self.totals)
        right.addWidget(tc)
        right.addStretch()
        body.addLayout(right, 1)
        self.lay.addLayout(body)
        self.alias_lbl = label("", "small")
        self.save_btn = button("Save to template", "primary", main.save_run_template, "saveTemplate")
        self.footer(button("New run", slot=main.go_home, obj="newRun"), [self.alias_lbl, self.save_btn])
        for w in (self.fmt_xlsx, self.fmt_csv, self.cb_file, self.cb_sheet, self.cb_row, self.cb_indian,
                  self.cb_issues):
            w.toggled.connect(self.settings_changed)
        for w in (self.csv_enc, self.csv_delim):
            w.currentIndexChanged.connect(self.settings_changed)
        for w in (self.folder, self.pattern):
            w.textChanged.connect(self.settings_changed)
        self._loading = False
        self.result = None

    def on_enter(self):
        s = self.main.session
        o = s.template.output
        self._loading = True
        self.fmt_csv.setChecked(o.get("format") == "csv")
        self.fmt_xlsx.setChecked(o.get("format") != "csv")
        self.csv_enc.setCurrentIndex(max(0, self.csv_enc.findData(o.get("csv_encoding", "utf-8-sig"))))
        self.csv_delim.setCurrentIndex(max(0, self.csv_delim.findData(o.get("csv_delimiter", ","))))
        folder = o.get("folder") or (str(s.paths[0].parent) if s.paths else str(Path.home()))
        self.folder.setText(folder)
        self.pattern.setText(o.get("name_pattern", "{client}_{task}_{yyyymm}"))
        self.cb_file.setChecked(bool(o.get("source_file")))
        self.cb_sheet.setChecked(bool(o.get("source_sheet")))
        self.cb_row.setChecked(bool(o.get("source_row")))
        self.cb_indian.setChecked(bool(o.get("indian_format")))
        self.cb_issues.setChecked(bool(o.get("issues_sheet")))
        self._loading = False
        self.result = None
        self.banner.hide()
        self.open_file.hide()
        self.open_folder.hide()
        self.show_summary(None)
        self.settings_changed()

    def settings_changed(self, *_):
        if self._loading:
            return
        o = self.main.session.template.output
        o["format"] = "csv" if self.fmt_csv.isChecked() else "xlsx"
        o["csv_encoding"] = self.csv_enc.currentData()
        o["csv_delimiter"] = self.csv_delim.currentData()
        o["folder"] = self.folder.text().strip()
        o["name_pattern"] = self.pattern.text().strip() or "{client}_{task}_{yyyymm}"
        o["source_file"] = self.cb_file.isChecked()
        o["source_sheet"] = self.cb_sheet.isChecked()
        o["source_row"] = self.cb_row.isChecked()
        o["indian_format"] = self.cb_indian.isChecked()
        o["issues_sheet"] = self.cb_issues.isChecked()
        self.csv_box.setVisible(o["format"] == "csv")
        self.cb_indian.setEnabled(o["format"] == "xlsx")
        self.cb_issues.setEnabled(o["format"] == "xlsx")
        try:
            self.name_preview.setText("Gives: " + self.main.session.output_path(o["folder"]).name)
        except Exception:
            self.name_preview.setText("")
        t = self.main.session.template
        self.save_btn.setText(f"Save to template (v{t.version} → v{t.version + 1})" if t.version
                              else "Save as new template")
        na = self.main.session.new_aliases
        self.alias_lbl.setText(("This run added the alias " + ", ".join(f'"{a}" → {t_}' for t_, a in na) + ".")
                               if na else "")

    def browse(self):
        f = self.main.prompter.folder("Save output to", self.folder.text())
        if f:
            self.folder.setText(f)

    def write(self):
        self.main.write_output()

    def show_summary(self, res):
        while self.summary.count():
            w = self.summary.takeAt(0).widget()
            if w:
                w.deleteLater()
        self.totals.setRowCount(0)
        self.hidden_lbl.setText("")
        if not res:
            self.summary.addWidget(label("Write the output to see the summary.", "small"), 0, 0)
            return
        lines = [("Files read", f"{res.files_read}"), ("Rows read", f"{res.rows_read:,}"),
                 ("Rows written", f"{res.rows_written:,}"), ("Rows left out", f"{res.rows_left_out:,}"),
                 ("Warnings", f"{res.warnings}" + (", on the Issues sheet" if
                                                   self.main.session.template.output.get("issues_sheet") and
                                                   self.main.session.template.output.get("format") == "xlsx" and res.warnings else ""))]
        if res.errors_overridden:
            lines.append(("Errors written anyway", f"{res.errors_overridden}"))
        lines.append(("Time taken", f"{res.seconds:.1f} s"))
        for i, (k, v) in enumerate(lines):
            self.summary.addWidget(label(k, "quiet"), i, 0)
            lb = label(v)
            lb.setStyleSheet("font-weight: 600")
            self.summary.addWidget(lb, i, 1)
        h = res.hidden + res.skipped_rows
        self.hidden_lbl.setText(("Hidden data and total rows skipped:\n" + "\n".join(h)) if h else
                                "No hidden rows or sheets.")
        for t in res.totals:
            r = self.totals.rowCount()
            self.totals.insertRow(r)
            self.totals.setItem(r, 0, item(t.column))
            self.totals.setItem(r, 1, item(indian(t.input_total), align_right=True))
            self.totals.setItem(r, 2, item(indian(t.output_total), align_right=True))
            self.totals.setItem(r, 3, item("Match" if t.match else "Mismatch", bold=True,
                                           color=S.OK if t.match else S.ERROR))


def indian(v: float) -> str:
    """1,23,45,678.50"""
    neg = v < 0
    s = f"{abs(v):.2f}"
    whole, frac = s.split(".")
    if len(whole) > 3:
        head, tail = whole[:-3], whole[-3:]
        parts = []
        while len(head) > 2:
            parts.insert(0, head[-2:])
            head = head[:-2]
        if head:
            parts.insert(0, head)
        whole = ",".join(parts) + "," + tail
    return ("-" if neg else "") + whole + "." + frac
