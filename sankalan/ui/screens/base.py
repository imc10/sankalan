"""Screens: one level per screen (UX §3, GEN-06), each with breadcrumbs, a banner slot, a heading and its body.

A screen that holds unsaved work returns a ``LeaveGuard`` from ``leave_guard()``; the window asks before leaving it
(UX §5 Leaving): unsaved edits → Save / Discard / Stay; the run wizard → "Leave and discard this run?"; an unsaved
analysis → Save… / Leave without saving / Stay.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Callable

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QHBoxLayout, QLabel, QVBoxLayout, QWidget

from sankalan.ui import theme
from sankalan.ui.widgets.banner import Banner
from sankalan.ui.widgets.breadcrumb import Breadcrumb, Crumb

if TYPE_CHECKING:
    from sankalan.ui.window import MainWindow

STAY = "stay"


@dataclass
class LeaveGuard:
    """What to ask before leaving. ``options``: (key, label, kind, action). The action runs when picked and returns
    True when leaving may go on (a Save that fails returns False). ``STAY`` never leaves."""
    title: str
    text: str
    options: list[tuple[str, str, str | None, Callable[[], bool] | None]] = field(default_factory=list)

    @classmethod
    def unsaved(cls, save: Callable[[], bool], discard: Callable[[], bool] | None = None,
                what: str = "your changes") -> "LeaveGuard":
        return cls("Save your changes?", f"If you leave without saving, {what} will be lost.",
                   [(STAY, "Stay", None, None), ("discard", "Discard", None, discard or (lambda: True)),
                    ("save", "Save", "primary", save)])

    @classmethod
    def discard_run(cls, discard: Callable[[], bool]) -> "LeaveGuard":
        """Dialog 7.6."""
        return cls("Leave and discard this run?",
                   "Nothing has been loaded yet. Your mapping decisions for this run will be lost; the files stay "
                   "where they are.", [(STAY, "Stay", None, None), ("discard", "Discard run", "destructive", discard)])

    @classmethod
    def unsaved_analysis(cls, save: Callable[[], bool], leave: Callable[[], bool] | None = None) -> "LeaveGuard":
        """Dialog 7.7."""
        return cls("This analysis isn't saved", "If you leave, its settings and result are cleared.",
                   [(STAY, "Stay", None, None), ("leave", "Leave without saving", None, leave or (lambda: True)),
                    ("save", "Save…", "primary", save)])


class Screen(QWidget):
    """Base for every screen. Subclasses set ``area`` and ``title``, override ``crumbs()`` and fill ``self.content``
    (a ``QVBoxLayout``) and ``self.actions`` (the header's right side)."""
    area = "clients"
    title = ""

    def __init__(self, window: "MainWindow | None" = None, parent=None):
        super().__init__(parent)
        self.window_ = window
        self.setObjectName("Page")
        outer = QVBoxLayout(self)
        left, top, right, bottom = theme.PAGE_MARGINS
        outer.setContentsMargins(left, top, right, bottom)
        outer.setSpacing(0)
        self.breadcrumb = Breadcrumb([], self)
        outer.addWidget(self.breadcrumb)
        outer.addSpacing(12)
        self.banner_slot = QVBoxLayout()
        self.banner_slot.setSpacing(8)
        outer.addLayout(self.banner_slot)
        head = QHBoxLayout()
        head.setSpacing(16)
        titles = QVBoxLayout()
        titles.setSpacing(4)
        self.h1 = QLabel(self.title, self)
        self.h1.setProperty("kind", "h1")
        self.subtitle = QLabel("", self)
        self.subtitle.setProperty("kind", "subtitle")
        self.subtitle.hide()
        titles.addWidget(self.h1)
        titles.addWidget(self.subtitle)
        head.addLayout(titles, 1)
        self.actions = QHBoxLayout()
        self.actions.setSpacing(12)
        head.addLayout(self.actions)
        head.setAlignment(self.actions, Qt.AlignmentFlag.AlignBottom)
        outer.addLayout(head)
        outer.addSpacing(20)
        self.content = QVBoxLayout()
        self.content.setSpacing(theme.SECTION_GAP)
        outer.addLayout(self.content, 1)

    # ------------------------------------------------------------------------------------------ to override
    def crumbs(self) -> list[Crumb]:
        """Breadcrumbs above the heading; empty for the top level of an area."""
        return []

    def leave_guard(self) -> LeaveGuard | None:
        return None

    def shown(self) -> None:
        """Called each time the window opens this screen (load data here, through Jobs)."""

    def closing(self) -> None:
        """Called when the window leaves this screen for good."""

    # ------------------------------------------------------------------------------------------ helpers
    def set_title(self, title: str, subtitle: str | None = None) -> None:
        self.h1.setText(title)
        if subtitle is not None:
            self.subtitle.setText(subtitle)
            self.subtitle.setVisible(bool(subtitle))

    def refresh_crumbs(self) -> None:
        self.breadcrumb.set_crumbs(self.crumbs())

    def show_banner(self, banner: Banner) -> Banner:
        banner.setParent(self)
        self.banner_slot.addWidget(banner)
        self.banner_slot.addSpacing(0)
        return banner

    def banners(self) -> list[Banner]:
        return [w for w in self.findChildren(Banner) if not w.isHidden()]


class PlaceholderScreen(Screen):
    """An area's top screen until its phase builds it (Clients in Phase 7, Analysis in Phase 10)."""

    def __init__(self, area: str, title: str, text: str, window=None, parent=None):
        self.area = area
        self.title = title
        super().__init__(window, parent)
        note = QLabel(text, self)
        note.setProperty("kind", "body")
        note.setWordWrap(True)
        self.content.addWidget(note)
        self.content.addStretch(1)
