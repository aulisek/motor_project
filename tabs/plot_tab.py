from dataclasses import dataclass
from typing import List, Tuple

import time

from PyQt5.QtCore import pyqtSignal, Qt, QTimer
from PyQt5.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QPushButton,
    QLabel,
    QSlider,
    QSpinBox,
    QComboBox,
    QToolButton,
    QProgressBar,
)
from pyqtgraph import PlotWidget

from data_controller import ADS1263_SAMPLE_RATE_LABELS, DEFAULT_ADS1263_RATE_KEY


@dataclass
class MotionPlan:
    positions: List[int]
    delays: List[int]
    repetitions: int = 1


class PlotTab(QWidget):
    """Hosts plot widgets, motion controls, and the position sidebar."""

    start_motion_requested = pyqtSignal()
    stop_motion_requested = pyqtSignal()
    set_home_requested = pyqtSignal()
    daq_rate_changed = pyqtSignal(str)
    positions_changed = pyqtSignal(list, list, list)

    def __init__(self, plot_manager, parent=None):
        super().__init__(parent)
        self.plot_manager = plot_manager
        self._build_ui()

    def _build_ui(self) -> None:
        root_layout = QHBoxLayout(self)

        # Sidebar with dynamic positions
        sidebar = QWidget()
        sidebar_layout = QVBoxLayout(sidebar)

        self.positions_container = QWidget()
        self.positions_layout = QVBoxLayout(self.positions_container)
        sidebar_layout.addWidget(self.positions_container)

        self.status_label = QLabel("")
        sidebar_layout.addWidget(self.status_label)

        repetitions_layout = QHBoxLayout()
        repetitions_layout.addWidget(QLabel("Repetitions:"))
        self.repetitions_spinbox = QSpinBox()
        self.repetitions_spinbox.setRange(1, 1_000_000)
        self.repetitions_spinbox.setValue(1)
        self.repetitions_spinbox.setSuffix(" cycles")
        repetitions_layout.addWidget(self.repetitions_spinbox)
        sidebar_layout.addLayout(repetitions_layout)

        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 1)
        self.progress_bar.setFormat("%v / %m cycles")
        self.progress_bar.hide()
        sidebar_layout.addWidget(self.progress_bar)

        self.eta_label = QLabel("")
        self.eta_label.hide()
        sidebar_layout.addWidget(self.eta_label)

        self.progress_timer = QTimer(self)
        self.progress_timer.setInterval(200)
        self.progress_timer.timeout.connect(self._update_progress_timer)
        self._progress_total_duration = 0.0
        self._progress_cycle_time = 0.0
        self._progress_total_cycles = 0
        self._progress_start_ts = 0.0

        self.add_position_button = QPushButton("Add Position")
        self.add_position_button.clicked.connect(self._add_position_row)
        sidebar_layout.addWidget(self.add_position_button)

        rate_layout = QVBoxLayout()
        rate_layout.addWidget(QLabel("DAQ Sampling Rate:"))
        self.daq_rate_combo = QComboBox()
        for key, label in ADS1263_SAMPLE_RATE_LABELS:
            self.daq_rate_combo.addItem(label, key)
        default_index = self.daq_rate_combo.findData(DEFAULT_ADS1263_RATE_KEY)
        if default_index >= 0:
            self.daq_rate_combo.setCurrentIndex(default_index)
        self.daq_rate_combo.currentIndexChanged.connect(self._handle_daq_rate_change)
        rate_layout.addWidget(self.daq_rate_combo)
        sidebar_layout.addLayout(rate_layout)

        root_layout.addWidget(sidebar, 0)

        # Plot column with buttons
        plots_layout = QVBoxLayout()
        self.data_widget = PlotWidget()
        self.position_widget = PlotWidget()
        self._configure_plots()

        plots_layout.addWidget(self.data_widget)
        plots_layout.addWidget(self.position_widget)

        self.set_home_button = QPushButton("Set HOME")
        self.start_motor_button = QPushButton("Start Motion")
        self.stop_motion_button = QPushButton("Stop Motion")
        self.start_daq_button = QPushButton("Start DAQ")
        self.stop_daq_button = QPushButton("STOP DAQ")

        self.set_home_button.clicked.connect(self.set_home_requested.emit)
        self.start_motor_button.clicked.connect(self.start_motion_requested.emit)
        self.stop_motion_button.clicked.connect(self.stop_motion_requested.emit)
        self.start_daq_button.clicked.connect(self.plot_manager.start_acquisition)
        self.stop_daq_button.clicked.connect(self.plot_manager.stop_acquisition)

        button_layout = QHBoxLayout()
        button_layout.addWidget(self.set_home_button)
        button_layout.addWidget(self.start_motor_button)
        button_layout.addWidget(self.stop_motion_button)
        button_layout.addWidget(self.start_daq_button)
        button_layout.addWidget(self.stop_daq_button)
        plots_layout.addLayout(button_layout)

        root_layout.addLayout(plots_layout, 1)

        self._add_position_row()

    def _add_position_row(self):
        position_widget = QWidget()
        position_layout = QHBoxLayout(position_widget)

        label = QLabel("")
        label.setObjectName("positionLabel")
        angle_slider = QSlider(Qt.Orientation.Horizontal)
        angle_slider.setRange(0, 360)
        angle_slider.setValue(0)

        angle_spinbox = QSpinBox()
        angle_spinbox.setObjectName("angleSpinbox")
        angle_spinbox.setRange(0, 360)
        angle_spinbox.setValue(0)

        angle_slider.valueChanged.connect(angle_spinbox.setValue)
        angle_spinbox.valueChanged.connect(angle_slider.setValue)
        angle_spinbox.valueChanged.connect(self._emit_positions_changed)

        delay_slider = QSlider(Qt.Orientation.Horizontal)
        delay_slider.setRange(0, 5000)
        delay_slider.setValue(500)

        delay_spinbox = QSpinBox()
        delay_spinbox.setObjectName("delaySpinbox")
        delay_spinbox.setRange(0, 5000)
        delay_spinbox.setValue(500)
        delay_spinbox.setSuffix(" ms")

        delay_slider.valueChanged.connect(delay_spinbox.setValue)
        delay_spinbox.valueChanged.connect(delay_slider.setValue)
        delay_spinbox.valueChanged.connect(self._emit_positions_changed)

        delete_button = QToolButton()
        delete_button.setText("🗑")
        delete_button.clicked.connect(lambda: self._remove_position_row(position_widget))
        delete_button.setToolTip("Remove this position")

        position_layout.addWidget(label)
        position_layout.addWidget(angle_slider)
        position_layout.addWidget(angle_spinbox)
        position_layout.addWidget(QLabel("Delay:"))
        position_layout.addWidget(delay_slider)
        position_layout.addWidget(delay_spinbox)
        position_layout.addWidget(delete_button)

        self.positions_layout.addWidget(position_widget)
        self._refresh_position_labels()
        self._emit_positions_changed()

    def _remove_position_row(self, widget: QWidget):
        widget.setParent(None)
        widget.deleteLater()
        if self.positions_layout.count() == 0:
            self._add_position_row()
        self._refresh_position_labels()
        self._emit_positions_changed()

    def _refresh_position_labels(self):
        for index in range(self.positions_layout.count()):
            item = self.positions_layout.itemAt(index)
            widget = item.widget() if item else None
            if not widget:
                continue
            label = widget.findChild(QLabel, "positionLabel")
            if label:
                label.setText(f"Position {index + 1}:")

    def build_motion_plan(self) -> MotionPlan:
        positions, delays = self._extract_positions_and_delays()
        if not positions:
            raise ValueError("No positions defined!")
        return MotionPlan(
            positions=positions,
            delays=delays,
            repetitions=self.repetitions_spinbox.value(),
        )

    def _extract_positions_and_delays(self) -> Tuple[List[int], List[int]]:
        positions_counts: List[int] = []
        delays: List[int] = []

        for index in range(self.positions_layout.count()):
            item = self.positions_layout.itemAt(index)
            widget = item.widget() if item else None
            if not widget:
                continue

            angle_spinbox = widget.findChild(QSpinBox, "angleSpinbox")
            delay_spinbox = widget.findChild(QSpinBox, "delaySpinbox")
            if angle_spinbox is None or delay_spinbox is None:
                continue

            angle_deg = float(angle_spinbox.value())
            positions_counts.append(3600 - int(round(angle_deg * 10)))
            delays.append(delay_spinbox.value())

        return positions_counts, delays

    def set_status(self, text: str) -> None:
        self.status_label.setText(text or "")

    def set_position_inputs_enabled(self, enabled: bool) -> None:
        self.add_position_button.setEnabled(enabled)
        self.repetitions_spinbox.setEnabled(enabled)
        for index in range(self.positions_layout.count()):
            item = self.positions_layout.itemAt(index)
            widget = item.widget() if item else None
            if widget:
                widget.setEnabled(enabled)

    def set_motion_controls_enabled(self, enabled: bool) -> None:
        self.set_home_button.setEnabled(enabled)
        self.start_motor_button.setEnabled(enabled)
        self.stop_motion_button.setEnabled(True)

    def set_motion_ui_enabled(self, enabled: bool) -> None:
        self.set_position_inputs_enabled(enabled)
        self.set_motion_controls_enabled(enabled)

    def _configure_plots(self) -> None:
        """Prepare both PyQtGraph widgets via the shared plot manager."""
        self.plot_manager.setup_plots(self.data_widget, self.position_widget)

    def _handle_daq_rate_change(self):
        self.daq_rate_changed.emit(self.current_daq_rate_key())

    def current_daq_rate_key(self) -> str:
        return self.daq_rate_combo.currentData() or DEFAULT_ADS1263_RATE_KEY

    def emit_current_daq_rate(self):
        self.daq_rate_changed.emit(self.current_daq_rate_key())

    def emit_current_positions(self):
        counts, degrees, delays = self._extract_path_data()
        self.positions_changed.emit(counts, degrees, delays)

    def _emit_positions_changed(self):
        counts, degrees, delays = self._extract_path_data()
        self.positions_changed.emit(counts, degrees, delays)

    def _extract_positions_counts(self) -> List[int]:
        positions, _, _ = self._extract_path_data()
        return positions

    def _extract_path_data(self) -> Tuple[List[int], List[float], List[int]]:
        positions_counts: List[int] = []
        positions_degrees: List[float] = []
        delays_ms: List[int] = []
        for index in range(self.positions_layout.count()):
            item = self.positions_layout.itemAt(index)
            widget = item.widget() if item else None
            if not widget:
                continue
            angle_spinbox = widget.findChild(QSpinBox, "angleSpinbox")
            delay_spinbox = widget.findChild(QSpinBox, "delaySpinbox")
            if angle_spinbox is None:
                continue
            angle_deg = float(angle_spinbox.value())
            positions_degrees.append(angle_deg)
            positions_counts.append(3600 - int(round(angle_deg * 10)))
            delays_ms.append(delay_spinbox.value() if delay_spinbox else 0)
        return positions_counts, positions_degrees, delays_ms

    def start_progress_tracking(self, cycle_time_s: float, total_cycles: int):
        if cycle_time_s is None or cycle_time_s <= 0 or total_cycles <= 0:
            self.stop_progress_tracking()
            return
        self._progress_cycle_time = float(cycle_time_s)
        self._progress_total_cycles = int(total_cycles)
        self._progress_total_duration = self._progress_cycle_time * self._progress_total_cycles
        self._progress_start_ts = time.time()
        self.progress_bar.setRange(0, self._progress_total_cycles)
        self.progress_bar.setValue(0)
        self.progress_bar.show()
        self.eta_label.setText(f"ETA: {self._format_duration(self._progress_total_duration)}")
        self.eta_label.show()
        self.progress_timer.start()
        self.set_progress_cycles(0)

    def stop_progress_tracking(self):
        self.progress_timer.stop()
        self.progress_bar.hide()
        self.eta_label.hide()
        self._progress_total_duration = 0.0
        self._progress_cycle_time = 0.0
        self._progress_total_cycles = 0
        self._progress_start_ts = 0.0
        self.eta_label.setText("")
        self.progress_bar.setValue(0)

    def set_progress_cycles(self, completed_cycles: int):
        if self._progress_total_cycles <= 0:
            return
        value = max(0, min(completed_cycles, self._progress_total_cycles))
        self.progress_bar.setValue(value)
        if value >= self._progress_total_cycles:
            self.stop_progress_tracking()

    def _update_progress_timer(self):
        if self._progress_cycle_time <= 0 or self._progress_total_cycles <= 0:
            self.stop_progress_tracking()
            return
        elapsed = max(0.0, time.time() - self._progress_start_ts)
        remaining = max(0.0, self._progress_total_duration - elapsed)
        self.eta_label.setText(f"ETA: {self._format_duration(remaining)}")

    @staticmethod
    def _format_duration(seconds: float) -> str:
        seconds = max(0, int(round(seconds)))
        if seconds < 60:
            return f"{seconds}s"
        minutes, secs = divmod(seconds, 60)
        if minutes < 60:
            return f"{minutes}m {secs:02d}s"
        hours, minutes = divmod(minutes, 60)
        return f"{hours}h {minutes:02d}m"
