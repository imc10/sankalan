"""Header rename (Feature Spec A2 MEA-8, Tech spec A2 T51, 9.7): one header for the analysis grid (6.2) and the
Default outputs previews (3.2, 2.5).

``RenamableHeader`` paints a ✎ in the right 20 px of the sections the screen marks renamable (the measure columns of
an unsaved result or preview). A click on ✎ opens a text box over the section with its text selected; a click
elsewhere on the header sorts, as before.

- Enter emits ``rename_requested(section, text)``. The screen checks the name and calls ``finish()`` or
  ``show_error("Another column is already called …")``, which keeps the box open with the message under it.
- Esc or focus loss cancels.
- A blank name means the default (the screen restores it).

Hover text per section comes from ``set_tooltips(callback)`` (the default form, "Invoice No · Count").
"""
from __future__ import annotations

from typing import Callable

from PySide6.QtCore import QEvent, QPoint, QRect, Qt, Signal
from PySide6.QtGui import QColor, QPainter
from PySide6.QtWidgets import QHeaderView, QLabel, QLineEdit, QToolTip

from sankalan.ui import theme
from sankalan.ui.widgets import icons

PENCIL_WIDTH = 20
RENAME_TIP = "Rename this column"


class _Editor(QLineEdit):
    cancelled = Signal()

    def keyPressEvent(self, event) -> None:
        if event.key() == Qt.Key.Key_Escape:
            self.cancelled.emit()
            return
        super().keyPressEvent(event)

    def focusOutEvent(self, event) -> None:
        super().focusOutEvent(event)
        if event.reason() not in (Qt.FocusReason.PopupFocusReason, Qt.FocusReason.ActiveWindowFocusReason):
            self.cancelled.emit()


class RenamableHeader(QHeaderView):
    rename_requested = Signal(int, str)

    def __init__(self, parent=None, orientation=Qt.Orientation.Horizontal):
        super().__init__(orientation, parent)
        self._renamable: Callable[[int], bool] = lambda _s: False
        self._tooltip: Callable[[int], str | None] = lambda _s: None
        self._pressed_pencil = False
        self.editing: int | None = None
        self.editor: _Editor | None = None
        self.error: QLabel | None = None
        self._pencil = None

    # ------------------------------------------------------------------------------------------ set-up
    def set_renamable(self, callback: Callable[[int], bool] | None) -> None:
        """Which sections show ✎ (None: none)."""
        self.finish()
        self._renamable = callback or (lambda _s: False)
        self.viewport().update()

    def set_tooltips(self, callback: Callable[[int], str | None] | None) -> None:
        self._tooltip = callback or (lambda _s: None)

    def renamable(self, section: int) -> bool:
        try:
            return bool(self._renamable(section))
        except (IndexError, KeyError):
            return False

    def pencil_rect(self, section: int) -> QRect:
        """The ✎ area of a section, in viewport coordinates."""
        x = self.sectionViewportPosition(section) + self.sectionSize(section) - PENCIL_WIDTH
        return QRect(x, 0, PENCIL_WIDTH, self.height())

    # ------------------------------------------------------------------------------------------ painting
    def paintSection(self, painter: QPainter, rect: QRect, section: int) -> None:
        pencil = self.renamable(section)
        painter.save()
        if pencil:          # the background over the whole section, the text left of the ✎
            painter.fillRect(rect, QColor(theme.HEADER_BG))
            painter.setClipRect(rect)
            super().paintSection(painter, rect.adjusted(0, 0, -PENCIL_WIDTH + 4, 0), section)
            painter.setPen(QColor(theme.BORDER))                       # the section's bottom border (theme)
            painter.drawLine(rect.right() - PENCIL_WIDTH, rect.bottom(), rect.right(), rect.bottom())
        else:
            super().paintSection(painter, rect, section)
        painter.restore()
        if pencil:
            if self._pencil is None:
                self._pencil = icons.pixmap("edit", theme.MUTED, 14)
            painter.drawPixmap(rect.right() - PENCIL_WIDTH + 2, rect.center().y() - 7, self._pencil)

    def sectionSizeFromContents(self, logicalIndex: int):
        size = super().sectionSizeFromContents(logicalIndex)
        if self.renamable(logicalIndex):
            size.setWidth(size.width() + PENCIL_WIDTH)
        return size

    # ------------------------------------------------------------------------------------------ mouse
    def _pencil_at(self, pos: QPoint) -> int | None:
        section = self.logicalIndexAt(pos)
        if section >= 0 and self.renamable(section) and self.pencil_rect(section).contains(pos):
            return section
        return None

    def mousePressEvent(self, event) -> None:
        section = self._pencil_at(event.position().toPoint())
        if section is not None and event.button() == Qt.MouseButton.LeftButton:
            self._pressed_pencil = True
            self.start_edit(section)
            event.accept()
            return
        self._pressed_pencil = False
        super().mousePressEvent(event)

    def mouseReleaseEvent(self, event) -> None:
        if self._pressed_pencil:            # the ✎ click never sorts
            self._pressed_pencil = False
            event.accept()
            return
        super().mouseReleaseEvent(event)

    def viewportEvent(self, event) -> bool:
        if event.type() == QEvent.Type.ToolTip:
            pos = event.pos()
            section = self.logicalIndexAt(pos)
            tip = None
            if section >= 0:
                tip = RENAME_TIP if self._pencil_at(pos) is not None else self._tooltip(section)
            if tip:
                QToolTip.showText(event.globalPos(), tip, self)
            else:
                QToolTip.hideText()
                event.ignore()
            return True
        return super().viewportEvent(event)

    # ------------------------------------------------------------------------------------------ editing
    def start_edit(self, section: int) -> None:
        """Open the text box over ``section`` with its text selected."""
        self.finish()
        self.editing = section
        text = self.model().headerData(section, self.orientation(), Qt.ItemDataRole.DisplayRole) if self.model() \
            else ""
        ed = _Editor(self)
        ed.setAccessibleName("Column name")
        ed.setMaxLength(200)
        ed.setText(str(text or ""))
        ed.setStyleSheet(f"QLineEdit {{ min-height: 0; border: 1px solid {theme.TEAL}; border-radius: 4px; "
                         f"padding: 0 6px; font-size: {theme.GRID_TEXT_PX}px; }}")
        x = self.sectionViewportPosition(section)
        ed.setGeometry(x + 2, 4, max(80, self.sectionSize(section) - 4), self.height() - 8)
        ed.returnPressed.connect(lambda: self.rename_requested.emit(section, ed.text()))
        ed.cancelled.connect(self.finish)
        ed.textEdited.connect(lambda _t: self._hide_error())
        self.editor = ed
        ed.show()
        ed.selectAll()
        ed.setFocus(Qt.FocusReason.MouseFocusReason)

    def finish(self) -> None:
        """Close the text box (after a rename was taken, or to cancel)."""
        ed, self.editor, self.editing = self.editor, None, None
        if ed is not None:
            ed.blockSignals(True)
            ed.hide()
            ed.deleteLater()
        if self.error is not None:
            self.error.hide()
            self.error.deleteLater()
            self.error = None

    def show_error(self, message: str) -> None:
        """Keep the box open with ``message`` under it (MEA-8)."""
        if self.editor is None:
            return
        host = self.parentWidget() or self
        if self.error is None:
            self.error = QLabel(host)
            self.error.setProperty("kind", "error")
            self.error.setStyleSheet(f"background: {theme.WHITE}; color: {theme.ERROR}; border: 1px solid "
                                     f"{theme.ERROR}; border-radius: 4px; padding: 2px 6px;")
        self.error.setText(message)
        self.error.adjustSize()
        top_left = self.editor.mapTo(host, QPoint(0, self.editor.height() + 6))
        self.error.move(top_left)
        self.error.show()
        self.error.raise_()
        self.editor.setFocus()

    def _hide_error(self) -> None:
        if self.error is not None:
            self.error.hide()
