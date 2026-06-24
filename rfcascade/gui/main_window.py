"""Main application window: assembles every panel, toolbar and action."""

from __future__ import annotations

import os
from typing import List, Optional

from PySide6.QtCore import Qt, QSize
from PySide6.QtGui import QAction, QKeySequence
from PySide6.QtWidgets import (
    QAbstractItemView, QApplication, QDockWidget, QFileDialog, QHBoxLayout,
    QHeaderView, QLabel, QMainWindow, QMenu, QMessageBox, QSizePolicy, QSplitter,
    QTableView, QTabWidget, QToolBar, QVBoxLayout, QWidget,
)

from ..core.components import Component, ComponentKind, SignalSource
from ..core.cascade import IMDMode, analyze, frequency_response
from ..core import library, project as project_mod
from ..core import touchstone as touchstone_mod
from . import theme, icons
from .chain_model import ChainModel, KindDelegate
from .results_model import ResultsModel
from .source_panel import SourcePanel
from .summary_panel import SummaryPanel
from .library_panel import LibraryPanel
from .component_editor import ComponentEditor
from .circuit_builder import CircuitBuilderDialog
from .plots import LevelDiagram, MetricsView, SweepView, MonteCarloView, FreqResponseView
from .fmt import num

APP_NAME = "RF Cascade Studio"


class MainWindow(QMainWindow):
    def __init__(self, proj: Optional[project_mod.Project] = None):
        super().__init__()
        self._project = proj or project_mod.Project(
            source=SignalSource(), components=library.default_chain())
        self._path: Optional[str] = None
        self._dirty = False

        self.setWindowTitle(APP_NAME)
        self.resize(1480, 940)

        self.chain_model = ChainModel(self._project.components)
        self.results_model = ResultsModel()

        self._build_central()
        self._build_docks()
        self._build_toolbar()
        self._build_menu()
        self.statusBar().showMessage("Ready")

        self.chain_model.chainChanged.connect(self._on_data_changed)
        self.source_panel.sourceChanged.connect(self._on_data_changed)
        self.source_panel.imdModeChanged.connect(self._on_imd_changed)
        self.library_panel.addRequested.connect(self._add_component)
        self.chain_view.selectionModel().selectionChanged.connect(self._update_action_state)

        self._select_row(0)
        self.recompute()
        self._update_title()

    # ------------------------------------------------------------------ build
    def _build_central(self):
        self.source_panel = SourcePanel(self._project.source, self._project.imd_mode)

        # Chain editor table.
        self.chain_view = QTableView()
        self.chain_view.setModel(self.chain_model)
        self.chain_view.setItemDelegateForColumn(2, KindDelegate(self.chain_view))
        self.chain_view.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.chain_view.setSelectionMode(QAbstractItemView.ExtendedSelection)
        self.chain_view.setAlternatingRowColors(True)
        self.chain_view.setEditTriggers(
            QAbstractItemView.DoubleClicked | QAbstractItemView.SelectedClicked
            | QAbstractItemView.EditKeyPressed | QAbstractItemView.AnyKeyPressed)
        self.chain_view.verticalHeader().setDefaultSectionSize(30)
        self.chain_view.setContextMenuPolicy(Qt.CustomContextMenu)
        self.chain_view.customContextMenuRequested.connect(self._chain_context_menu)
        self.chain_view.doubleClicked.connect(self._maybe_edit_on_double)
        hh = self.chain_view.horizontalHeader()
        hh.setSectionResizeMode(0, QHeaderView.Fixed)
        hh.resizeSection(0, 34)
        hh.setSectionResizeMode(1, QHeaderView.Stretch)
        for c in range(2, self.chain_model.columnCount()):
            hh.setSectionResizeMode(c, QHeaderView.Interactive)
        hh.resizeSection(2, 120)
        for c in range(3, 7):
            hh.resizeSection(c, 78)
        hh.resizeSection(7, 90)

        chain_header = QLabel("Signal Chain")
        chain_header.setObjectName("Heading")
        chain_hint = QLabel("Edit cells inline · double-click a name for full editor · drag from Library")
        chain_hint.setObjectName("SubHeading")

        top = QWidget()
        tlay = QVBoxLayout(top)
        tlay.setContentsMargins(10, 10, 10, 6)
        tlay.setSpacing(8)
        tlay.addWidget(self.source_panel)
        head_row = QHBoxLayout()
        head_row.addWidget(chain_header)
        head_row.addStretch(1)
        head_row.addWidget(chain_hint)
        tlay.addLayout(head_row)
        tlay.addWidget(self.chain_view, 1)

        # Bottom analysis tabs.
        self.tabs = QTabWidget()
        self.results_view = QTableView()
        self.results_view.setModel(self.results_model)
        self.results_view.setAlternatingRowColors(True)
        self.results_view.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.results_view.verticalHeader().setVisible(False)
        self.results_view.horizontalHeader().setSectionResizeMode(0, QHeaderView.Stretch)
        for c in range(1, self.results_model.columnCount()):
            self.results_view.horizontalHeader().setSectionResizeMode(c, QHeaderView.ResizeToContents)

        self.level_view = LevelDiagram()
        self.metrics_view = MetricsView()
        self.freq_view = FreqResponseView()
        self.sweep_view = SweepView()
        self.mc_view = MonteCarloView()

        self.tabs.addTab(self.results_view, "Cascade Table")
        self.tabs.addTab(self.level_view, "Level Diagram")
        self.tabs.addTab(self.metrics_view, "Metrics")
        self.tabs.addTab(self.freq_view, "Frequency Response")
        self.tabs.addTab(self.sweep_view, "Power Sweep")
        self.tabs.addTab(self.mc_view, "Monte Carlo")

        splitter = QSplitter(Qt.Vertical)
        splitter.addWidget(top)
        splitter.addWidget(self.tabs)
        splitter.setStretchFactor(0, 3)
        splitter.setStretchFactor(1, 4)
        splitter.setSizes([460, 480])
        self.setCentralWidget(splitter)

    def _build_docks(self):
        self.summary_panel = SummaryPanel()
        sdock = QDockWidget("Summary", self)
        sdock.setObjectName("SummaryDock")
        host = QWidget()
        hl = QVBoxLayout(host)
        hl.setContentsMargins(10, 10, 10, 10)
        hl.addWidget(self.summary_panel)
        sdock.setWidget(host)
        sdock.setFeatures(QDockWidget.DockWidgetMovable | QDockWidget.DockWidgetFloatable)
        sdock.setMinimumWidth(330)
        self.addDockWidget(Qt.RightDockWidgetArea, sdock)
        self._summary_dock = sdock

        self.library_panel = LibraryPanel()
        ldock = QDockWidget("Library", self)
        ldock.setObjectName("LibraryDock")
        ldock.setWidget(self.library_panel)
        ldock.setFeatures(QDockWidget.DockWidgetMovable | QDockWidget.DockWidgetFloatable
                          | QDockWidget.DockWidgetClosable)
        ldock.setMinimumWidth(260)
        self.addDockWidget(Qt.LeftDockWidgetArea, ldock)
        self._library_dock = ldock

    def _act(self, icon_name, text, slot, shortcut=None, tip=None, checkable=False):
        a = QAction(icons.icon(icon_name), text, self)
        a.triggered.connect(slot)
        if shortcut:
            a.setShortcut(QKeySequence(shortcut))
        a.setToolTip(f"{tip or text}" + (f"  ({QKeySequence(shortcut).toString()})" if shortcut else ""))
        a.setCheckable(checkable)
        return a

    def _build_toolbar(self):
        tb = QToolBar("Main")
        tb.setMovable(False)
        tb.setToolButtonStyle(Qt.ToolButtonTextBesideIcon)
        tb.setIconSize(QSize(20, 20))
        self.addToolBar(tb)

        self.a_new = self._act("new", "New", self.new_project, "Ctrl+N")
        self.a_open = self._act("open", "Open", self.open_project, "Ctrl+O")
        self.a_save = self._act("save", "Save", self.save_project, "Ctrl+S")
        tb.addAction(self.a_new)
        tb.addAction(self.a_open)
        tb.addAction(self.a_save)
        tb.addSeparator()

        self.a_add = self._act("add", "Add Stage", self.add_stage, "Ctrl+Shift+A")
        self.a_edit = self._act("edit", "Edit", self.edit_stage, "Return")
        self.a_dup = self._act("duplicate", "Duplicate", self.duplicate_stage, "Ctrl+D")
        self.a_del = self._act("delete", "Delete", self.delete_stage, "Delete")
        self.a_up = self._act("up", "Up", lambda: self.move_stage(-1), "Ctrl+Up")
        self.a_down = self._act("down", "Down", lambda: self.move_stage(1), "Ctrl+Down")
        for a in (self.a_add, self.a_edit, self.a_dup, self.a_del, self.a_up, self.a_down):
            tb.addAction(a)
        tb.addSeparator()

        self.a_block = self._act("circuit", "Build Block", self.build_block,
                                 tip="Build a two-port from lumped L/C/R components")
        self.a_import_snp = self._act("import", "Import .s2p", self.import_touchstone,
                                      tip="Add a stage from a Touchstone S-parameter file")
        tb.addAction(self.a_block)
        tb.addAction(self.a_import_snp)
        tb.addSeparator()

        self.a_sweep = self._act("sweep", "Power Sweep", self.run_sweep)
        self.a_mc = self._act("montecarlo", "Monte Carlo", self.run_montecarlo)
        tb.addAction(self.a_sweep)
        tb.addAction(self.a_mc)
        tb.addSeparator()

        self.a_export = self._act("export", "Export CSV", self.export_csv)
        self.a_export_snp = self._act("freq", "Export .s2p", self.export_touchstone,
                                      tip="Export the cascaded chain response as a Touchstone file")
        tb.addAction(self.a_export)
        tb.addAction(self.a_export_snp)

        spacer = QWidget()
        spacer.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
        tb.addWidget(spacer)

        self.a_lib = self._act("library", "Library", self.toggle_library, checkable=True)
        self.a_lib.setChecked(True)
        self.a_theme = self._act("theme", "Theme", self.toggle_theme)
        tb.addAction(self.a_lib)
        tb.addAction(self.a_theme)

    def _build_menu(self):
        m = self.menuBar()
        fm = m.addMenu("&File")
        fm.addActions([self.a_new, self.a_open, self.a_save])
        a_saveas = QAction("Save As…", self)
        a_saveas.setShortcut("Ctrl+Shift+S")
        a_saveas.triggered.connect(lambda: self.save_project(force_dialog=True))
        fm.addAction(a_saveas)
        fm.addAction(self.a_export)
        fm.addSeparator()
        a_quit = QAction("Quit", self)
        a_quit.setShortcut("Ctrl+Q")
        a_quit.triggered.connect(self.close)
        fm.addAction(a_quit)

        em = m.addMenu("&Edit")
        em.addActions([self.a_add, self.a_edit, self.a_dup, self.a_del, self.a_up, self.a_down])

        cm = m.addMenu("&Circuit")
        self.a_edit_ckt = QAction("Edit Lumped Circuit…", self)
        self.a_edit_ckt.triggered.connect(self.edit_circuit)
        cm.addAction(self.a_block)
        cm.addAction(self.a_edit_ckt)
        cm.addSeparator()
        cm.addAction(self.a_import_snp)
        cm.addAction(self.a_export_snp)

        am = m.addMenu("&Analysis")
        am.addActions([self.a_sweep, self.a_mc])

        vm = m.addMenu("&View")
        vm.addAction(self.a_lib)
        vm.addAction(self.a_theme)

        hm = m.addMenu("&Help")
        a_about = QAction("About", self)
        a_about.triggered.connect(self._about)
        hm.addAction(a_about)

    # --------------------------------------------------------------- selection
    def _selected_rows(self) -> List[int]:
        return sorted({i.row() for i in self.chain_view.selectionModel().selectedRows()})

    def _current_row(self) -> int:
        rows = self._selected_rows()
        if rows:
            return rows[0]
        idx = self.chain_view.currentIndex()
        return idx.row() if idx.isValid() else -1

    def _select_row(self, row: int):
        if 0 <= row < self.chain_model.rowCount():
            self.chain_view.selectRow(row)
            self.chain_view.setCurrentIndex(self.chain_model.index(row, 1))

    def _update_action_state(self, *_):
        has_sel = self._current_row() >= 0
        for a in (self.a_edit, self.a_dup, self.a_del, self.a_up, self.a_down):
            a.setEnabled(has_sel)

    # ----------------------------------------------------------------- compute
    def _on_data_changed(self):
        self._dirty = True
        self._update_title()
        self.recompute()

    def _on_imd_changed(self, mode: IMDMode):
        self._project.imd_mode = mode
        self._dirty = True
        self.recompute()

    def _sync_network_gains(self):
        """Re-pin every network-backed stage's scalar gain to the source freq.

        Lumped-circuit and Touchstone stages carry a frequency-dependent
        response; the scalar gain the cascade uses is a single-frequency sample
        of it. Without this, that sample only refreshed when a stage was
        re-opened in an editor, so changing the source frequency left the
        cascade table / summary stale until each stage was double-clicked.
        """
        freq = self._design_freq()
        changed = [r for r, comp in enumerate(self._project.components)
                   if comp.sync_gain_to(freq)]
        if changed:
            self.chain_model.refresh_rows(changed)

    def recompute(self):
        src = self._project.source
        comps = self._project.components
        mode = self.source_panel.imd_mode()
        self._sync_network_gains()
        result = analyze(src, comps, mode)

        self.results_model.set_result(result)
        self.summary_panel.update_summary(result.summary)
        self.level_view.update_result(result)
        self.metrics_view.update_result(result)
        self.freq_view.set_inputs(src, comps)
        self.sweep_view.set_inputs(src, comps, mode)
        self.mc_view.set_inputs(src, comps, mode)

        s = result.summary
        self.statusBar().showMessage(
            f"{s.n_stages} active stages   ·   Gain {num(s.total_gain_db,2)} dB   ·   "
            f"NF {num(s.total_nf_db,2)} dB   ·   OIP3 {num(s.oip3_dbm,1)} dBm   ·   "
            f"OP1dB {num(s.op1db_dbm,1)} dBm   ·   Out {num(s.output_power_dbm,1)} dBm   ·   "
            f"SNR {num(s.output_snr_db,1)} dB   ·   SFDR {num(s.sfdr_db,1)} dB"
        )

    # ------------------------------------------------------------ chain edits
    def add_stage(self):
        comp = Component.make(ComponentKind.AMPLIFIER, "New Amplifier")
        row = self._current_row()
        new_row = self.chain_model.insert_component(comp, row + 1 if row >= 0 else None)
        self._select_row(new_row)

    def _add_component(self, comp: Component):
        row = self._current_row()
        new_row = self.chain_model.insert_component(comp, row + 1 if row >= 0 else None)
        self._select_row(new_row)
        self.statusBar().showMessage(f"Added “{comp.name}” to the chain", 4000)

    def _maybe_edit_on_double(self, index):
        # Double-clicking the name column opens the full editor; other columns edit inline.
        # For a lumped block the name opens the circuit builder instead.
        if index.column() in (1,):
            comp = self.chain_model.component_at(index.row())
            if comp is not None and comp.network_kind == "lumped":
                self.edit_circuit()
            else:
                self.edit_stage()

    def edit_stage(self):
        row = self._current_row()
        comp = self.chain_model.component_at(row)
        if comp is None:
            return
        dlg = ComponentEditor(comp, self)
        if dlg.exec():
            dlg.apply_to(comp)
            self.chain_model.update_component(row)
            self._select_row(row)

    def duplicate_stage(self):
        row = self._current_row()
        if row >= 0:
            new_row = self.chain_model.duplicate_row(row)
            self._select_row(new_row)

    def delete_stage(self):
        rows = self._selected_rows()
        if not rows:
            return
        self.chain_model.remove_rows(rows)
        self._select_row(min(rows[0], self.chain_model.rowCount() - 1))

    def move_stage(self, delta: int):
        row = self._current_row()
        if row < 0:
            return
        new_row = self.chain_model.move_row(row, delta)
        self._select_row(new_row)

    def _chain_context_menu(self, pos):
        menu = QMenu(self)
        menu.addActions([self.a_edit, self.a_dup, self.a_del])
        comp = self.chain_model.component_at(self._current_row())
        if comp is not None and comp.network_kind == "lumped":
            menu.addAction(self.a_edit_ckt)
        menu.addSeparator()
        menu.addActions([self.a_up, self.a_down])
        menu.addSeparator()
        menu.addAction(self.a_add)
        menu.exec(self.chain_view.viewport().mapToGlobal(pos))

    # --------------------------------------------------------------- analyses
    def run_sweep(self):
        self.tabs.setCurrentWidget(self.sweep_view)
        self.sweep_view.run()

    def run_montecarlo(self):
        self.tabs.setCurrentWidget(self.mc_view)
        any_tol = any((c.tol_gain_db or c.tol_nf_db or c.tol_oip3_db)
                      for c in self._project.components if c.enabled)
        if not any_tol:
            QMessageBox.information(
                self, "Monte Carlo",
                "No component tolerances are set yet.\n\n"
                "Open a stage (Edit) and set Gain/NF/OIP3 σ values, then run again.")
            return
        self.mc_view.run()

    # --------------------------------------------------------- circuit / S-params
    def _design_freq(self) -> float:
        return self._project.source.frequency_hz or 1.0e9

    def build_block(self):
        dlg = CircuitBuilderDialog(None, default_freq_hz=self._design_freq(), parent=self)
        if not dlg.exec():
            return
        circ = dlg.result_circuit()
        comp = Component(name=circ.name, kind=ComponentKind.FILTER, nf_db=None)
        comp.set_circuit(circ, sync_gain_at_hz=self._design_freq())
        comp.frequency_hz = self._design_freq()
        self._add_component(comp)
        self.tabs.setCurrentWidget(self.freq_view)

    def edit_circuit(self):
        row = self._current_row()
        comp = self.chain_model.component_at(row)
        if comp is None:
            return
        circ = comp.get_circuit()
        if circ is None:
            QMessageBox.information(
                self, "Edit Lumped Circuit",
                "This stage is not built from lumped components.\n\n"
                "Use “Build Block” to create one, or this only applies to "
                "lumped-circuit stages.")
            return
        dlg = CircuitBuilderDialog(circ, default_freq_hz=self._design_freq(), parent=self)
        if not dlg.exec():
            return
        new_circ = dlg.result_circuit()
        comp.set_circuit(new_circ, sync_gain_at_hz=self._design_freq())
        comp.name = new_circ.name
        self.chain_model.update_component(row)
        self._select_row(row)

    def import_touchstone(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "Import Touchstone", "",
            "Touchstone (*.s1p *.s2p *.snp);;All files (*)")
        if not path:
            return
        try:
            net = touchstone_mod.read_touchstone(path)
        except Exception as exc:  # noqa: BLE001
            QMessageBox.critical(self, "Import failed", str(exc))
            return
        name = os.path.splitext(os.path.basename(path))[0]
        peak_db = float(net.s21_db().max())
        kind = ComponentKind.AMPLIFIER if peak_db > 0.5 else ComponentKind.FILTER
        comp = Component(name=name, kind=kind, nf_db=None)
        comp.set_sparams(net, sync_gain_at_hz=self._design_freq())
        self._add_component(comp)
        self.tabs.setCurrentWidget(self.freq_view)
        self.statusBar().showMessage(
            f"Imported {os.path.basename(path)} — {net.n} points, "
            f"{num(peak_db, 1)} dB peak |S21|", 5000)

    def export_touchstone(self):
        freqs = self.freq_view._freqs()
        if freqs.size == 0:
            QMessageBox.information(
                self, "Export Touchstone",
                "Open the Frequency Response tab and set a valid frequency span "
                "first; the chain is exported over that range.")
            return
        path, _ = QFileDialog.getSaveFileName(
            self, "Export Cascaded S-parameters",
            (self._project.name or "chain") + ".s2p",
            "Touchstone 2-port (*.s2p);;All files (*)")
        if not path:
            return
        net = frequency_response(self._project.source, self._project.components, freqs)
        try:
            touchstone_mod.write_touchstone(path, net, fmt="DB")
        except Exception as exc:  # noqa: BLE001
            QMessageBox.critical(self, "Export failed", str(exc))
            return
        self.statusBar().showMessage(f"Exported {os.path.basename(path)}", 4000)

    # ----------------------------------------------------------------- files
    def new_project(self):
        if not self._confirm_discard():
            return
        self._project = project_mod.Project(
            source=SignalSource(), components=library.default_chain())
        self._path = None
        self._reload_project()

    def open_project(self):
        if not self._confirm_discard():
            return
        path, _ = QFileDialog.getOpenFileName(
            self, "Open Project", "", "RF Cascade Project (*.rfc *.json);;All files (*)")
        if not path:
            return
        try:
            self._project = project_mod.Project.load(path)
        except Exception as exc:  # noqa: BLE001
            QMessageBox.critical(self, "Open failed", str(exc))
            return
        self._path = path
        self._reload_project()
        self.statusBar().showMessage(f"Opened {os.path.basename(path)}", 4000)

    def save_project(self, force_dialog: bool = False):
        if self._path is None or force_dialog:
            path, _ = QFileDialog.getSaveFileName(
                self, "Save Project", self._project.name + ".rfc",
                "RF Cascade Project (*.rfc *.json);;All files (*)")
            if not path:
                return
            self._path = path
            self._project.name = os.path.splitext(os.path.basename(path))[0]
        try:
            self._project.save(self._path)
        except Exception as exc:  # noqa: BLE001
            QMessageBox.critical(self, "Save failed", str(exc))
            return
        self._dirty = False
        self._update_title()
        self.statusBar().showMessage(f"Saved {os.path.basename(self._path)}", 4000)

    def export_csv(self):
        path, _ = QFileDialog.getSaveFileName(
            self, "Export Cascade Table", (self._project.name or "cascade") + ".csv",
            "CSV (*.csv);;All files (*)")
        if not path:
            return
        result = self._project.analyze()
        try:
            project_mod.export_results_csv(path, result)
        except Exception as exc:  # noqa: BLE001
            QMessageBox.critical(self, "Export failed", str(exc))
            return
        self.statusBar().showMessage(f"Exported {os.path.basename(path)}", 4000)

    def _reload_project(self):
        self.source_panel.set_source(self._project.source)
        i = self.source_panel.imd.findData(self._project.imd_mode)
        if i >= 0:
            self.source_panel.imd.setCurrentIndex(i)
        self.chain_model.set_items(self._project.components)
        self._dirty = False
        self._select_row(0)
        self.recompute()
        self._update_title()

    def _confirm_discard(self) -> bool:
        if not self._dirty:
            return True
        r = QMessageBox.question(
            self, "Unsaved changes", "Discard unsaved changes?",
            QMessageBox.Save | QMessageBox.Discard | QMessageBox.Cancel)
        if r == QMessageBox.Save:
            self.save_project()
            return not self._dirty
        return r == QMessageBox.Discard

    def closeEvent(self, event):
        if self._confirm_discard():
            event.accept()
        else:
            event.ignore()

    # ------------------------------------------------------------------- view
    def toggle_library(self):
        vis = not self._library_dock.isVisible()
        self._library_dock.setVisible(vis)
        self.a_lib.setChecked(vis)

    def toggle_theme(self):
        app = QApplication.instance()
        new = theme.LIGHT if theme.current_palette().name == "dark" else theme.DARK
        theme.apply_theme(app, new)
        # Refresh icons (they're tinted to the text colour) and replots.
        self._refresh_icons()
        self.recompute()

    def _refresh_icons(self):
        mapping = {
            self.a_new: "new", self.a_open: "open", self.a_save: "save",
            self.a_add: "add", self.a_edit: "edit", self.a_dup: "duplicate",
            self.a_del: "delete", self.a_up: "up", self.a_down: "down",
            self.a_block: "circuit", self.a_import_snp: "import",
            self.a_sweep: "sweep", self.a_mc: "montecarlo",
            self.a_export: "export", self.a_export_snp: "freq",
            self.a_lib: "library", self.a_theme: "theme",
        }
        for act, name in mapping.items():
            act.setIcon(icons.icon(name))

    def _update_title(self):
        star = "•  " if self._dirty else ""
        name = self._project.name if self._path is None else os.path.basename(self._path)
        self.setWindowTitle(f"{star}{name} — {APP_NAME}")

    def _about(self):
        QMessageBox.about(
            self, f"About {APP_NAME}",
            f"<h3>{APP_NAME}</h3>"
            "<p>An RF signal-chain (cascade) analyzer.</p>"
            "<p>Cascaded gain, noise figure (Friis), IP3 / IP2, P1dB compression, "
            "signal &amp; noise levels, SNR, MDS, SFDR, plus two-tone power sweeps "
            "and Monte-Carlo tolerance analysis.</p>"
            "<p style='color:#888'>Built with PySide6 &amp; pyqtgraph.</p>")
