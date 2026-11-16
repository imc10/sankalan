"""All modal questions go through a Prompter, so tests can answer them without dialogs."""
from __future__ import annotations

from PySide6.QtWidgets import (QComboBox, QDialog, QDialogButtonBox, QFileDialog, QFormLayout,
                               QInputDialog, QLineEdit, QMessageBox, QPushButton, QHBoxLayout, QWidget)


class Prompter:
    def __init__(self, parent=None):
        self.parent = parent

    def files(self, title="Add files"):
        paths, _ = QFileDialog.getOpenFileNames(self.parent, title, "",
                                                "Excel and CSV (*.xlsx *.xlsm *.xls *.csv *.txt)")
        return paths

    def folder(self, title="Choose folder", start=""):
        return QFileDialog.getExistingDirectory(self.parent, title, start) or None

    def save_file(self, title, default, filt="Excel (*.xlsx)"):
        path, _ = QFileDialog.getSaveFileName(self.parent, title, default, filt)
        return path or None

    def password(self, filename):
        text, ok = QInputDialog.getText(self.parent, "Password needed",
                                        f"{filename} is password-protected. Enter its password:",
                                        QLineEdit.EchoMode.Password)
        return text if ok and text else None

    def confirm(self, title, text, yes="Yes", no="Cancel"):
        box = QMessageBox(QMessageBox.Icon.Question, title, text, parent=self.parent)
        y = box.addButton(yes, QMessageBox.ButtonRole.AcceptRole)
        box.addButton(no, QMessageBox.ButtonRole.RejectRole)
        box.exec()
        return box.clickedButton() is y

    def info(self, title, text):
        QMessageBox.information(self.parent, title, text)

    def error(self, title, text):
        QMessageBox.warning(self.parent, title, text)

    def text(self, title, label, value=""):
        t, ok = QInputDialog.getText(self.parent, title, label, text=value)
        return t.strip() if ok and t.strip() else None

    def new_consolidation(self):
        """Returns (client, task, sample_path) or None."""
        dlg = QDialog(self.parent)
        dlg.setWindowTitle("New consolidation")
        form = QFormLayout(dlg)
        client, task, sample = QLineEdit(), QLineEdit(), QLineEdit()
        browse = QPushButton("Browse…")
        row = QWidget()
        hl = QHBoxLayout(row)
        hl.setContentsMargins(0, 0, 0, 0)
        hl.addWidget(sample)
        hl.addWidget(browse)
        browse.clicked.connect(lambda: sample.setText((self.files("Pick a sample file") or [""])[0]))
        form.addRow("Client", client)
        form.addRow("Task", task)
        form.addRow("Sample file", row)
        bb = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        bb.accepted.connect(dlg.accept)
        bb.rejected.connect(dlg.reject)
        form.addRow(bb)
        if dlg.exec() and client.text().strip() and task.text().strip() and sample.text().strip():
            return client.text().strip(), task.text().strip(), sample.text().strip()
        return None
