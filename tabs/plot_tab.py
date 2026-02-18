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
    QDoubleSpinBox,
    QComboBox,
    QToolButton,
    QProgressBar,
    QGroupBox,
    QScrollArea,
    QFrame,
    QLineEdit,
    QPlainTextEdit,
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
    refresh_ports_requested = pyqtSignal()
    connect_port_requested = pyqtSignal(int)
    reference_resistance_changed = pyqtSignal(float)

    def __init__(self, plot_manager, parent=None):
        super().__init__(parent)
        self.plot_manager = plot_manager
        self._motor_initialized = False
        self._motion_controls_enabled = True
        self._build_ui()
        self.plot_manager.daq_controller.data_signal.connect(self._update_live_data)
        self._update_motion_control_buttons()

    def _build_ui(self) -> None:
        root_layout = QHBoxLayout(self)
        root_layout.setContentsMargins(12, 12, 12, 12)
        root_layout.setSpacing(12)

        controls_panel = QWidget()
        controls_layout = QVBoxLayout(controls_panel)
        controls_layout.setContentsMargins(0, 0, 0, 0)
        controls_layout.setSpacing(12)
        root_layout.addWidget(controls_panel, 0)

        status_group = self._create_group_box("Motor Status")
        status_layout = status_group.layout()
        motor_status_layout = QHBoxLayout()
        self.motor_status_indicator = QLabel()
        self.motor_status_indicator.setFixedSize(16, 16)
        self.motor_status_indicator.setStyleSheet("background-color: #c0392b; border: 1px solid #96281b;")
        motor_status_layout.addWidget(self.motor_status_indicator)
        self.motor_status_text = QLabel("Motor not initialized")
        motor_status_layout.addWidget(self.motor_status_text)
        motor_status_layout.addSpacing(20)
        self.live_angle_label = QLabel("Angle: -- °")
        motor_status_layout.addWidget(self.live_angle_label)
        motor_status_layout.addSpacing(10)
        self.live_voltage_label = QLabel("Voltage: -- V")
        motor_status_layout.addWidget(self.live_voltage_label)
        motor_status_layout.addSpacing(10)
        self.live_resistance_label = QLabel("Resistance: -- Ω")
        motor_status_layout.addWidget(self.live_resistance_label)
        motor_status_layout.addStretch()
        status_layout.addLayout(motor_status_layout)
        self.status_label = QLabel("")
        self.status_label.setWordWrap(True)
        status_layout.addWidget(self.status_label)
        controls_layout.addWidget(status_group)

        self.init_controls_container = self._create_group_box("Connection")
        init_layout = self.init_controls_container.layout()
        init_layout.addWidget(QLabel("Available devices:"))
        self.init_com_combo = QComboBox()
        init_layout.addWidget(self.init_com_combo)
        buttons_row = QHBoxLayout()
        self.init_refresh_button = QPushButton("Refresh")
        self.init_refresh_button.clicked.connect(self.refresh_ports_requested.emit)
        buttons_row.addWidget(self.init_refresh_button)
        self.init_connect_button = QPushButton("Connect")
        self.init_connect_button.clicked.connect(lambda: self.connect_port_requested.emit(self.init_com_combo.currentIndex()))
        buttons_row.addWidget(self.init_connect_button)
        init_layout.addLayout(buttons_row)
        controls_layout.addWidget(self.init_controls_container)

        experiment_group = self._create_group_box("Experiment Info")
        experiment_layout = experiment_group.layout()
        experiment_layout.addWidget(QLabel("Experiment name:"))
        self.experiment_name_edit = QLineEdit()
        self.experiment_name_edit.setPlaceholderText("e.g., Sample sweep #5")
        experiment_layout.addWidget(self.experiment_name_edit)
        experiment_layout.addWidget(QLabel("Description / notes:"))
        self.experiment_description_edit = QPlainTextEdit()
        self.experiment_description_edit.setPlaceholderText("Add details about this run...")
        self.experiment_description_edit.setFixedHeight(80)
        experiment_layout.addWidget(self.experiment_description_edit)
        controls_layout.addWidget(experiment_group)

        plan_group = self._create_group_box("Motion Plan")
        plan_layout = plan_group.layout()
        self.positions_container = QWidget()
        self.positions_layout = QVBoxLayout(self.positions_container)
        self.positions_layout.setContentsMargins(0, 0, 0, 0)
        self.positions_layout.setSpacing(8)
        positions_scroll = QScrollArea()
        positions_scroll.setWidget(self.positions_container)
        positions_scroll.setWidgetResizable(True)
        positions_scroll.setFrameShape(QFrame.NoFrame)
        plan_layout.addWidget(positions_scroll)
        self.add_position_button = QPushButton("Add Motion Step")
        self.add_position_button.clicked.connect(self._add_position_row)
        plan_actions = QHBoxLayout()
        plan_actions.addWidget(self.add_position_button)
        plan_actions.addStretch()
        repetitions_layout = QHBoxLayout()
        repetitions_layout.addWidget(QLabel("Repetitions:"))
        self.repetitions_spinbox = QSpinBox()
        self.repetitions_spinbox.setRange(1, 1_000_000)
        self.repetitions_spinbox.setValue(1)
        self.repetitions_spinbox.setSuffix(" cycles")
        repetitions_layout.addWidget(self.repetitions_spinbox)
        plan_actions.addLayout(repetitions_layout)
        plan_layout.addLayout(plan_actions)
        controls_layout.addWidget(plan_group, 1)

        acquisition_group = self._create_group_box("Acquisition")
        acquisition_layout = acquisition_group.layout()
        acquisition_layout.addWidget(QLabel("DAQ sampling rate:"))
        self.daq_rate_combo = QComboBox()
        for key, label in ADS1263_SAMPLE_RATE_LABELS:
            self.daq_rate_combo.addItem(label, key)
        default_index = self.daq_rate_combo.findData(DEFAULT_ADS1263_RATE_KEY)
        if default_index >= 0:
            self.daq_rate_combo.setCurrentIndex(default_index)
        self.daq_rate_combo.currentIndexChanged.connect(self._handle_daq_rate_change)
        acquisition_layout.addWidget(self.daq_rate_combo)
        resistance_layout = QHBoxLayout()
        resistance_layout.addWidget(QLabel("Reference resistor (Ω):"))
        self.reference_res_spinbox = QDoubleSpinBox()
        self.reference_res_spinbox.setDecimals(1)
        self.reference_res_spinbox.setRange(0.1, 20_000_000.0)
        self.reference_res_spinbox.setValue(110_000.0)
        self.reference_res_spinbox.setSingleStep(100.0)
        self.reference_res_spinbox.valueChanged.connect(self.reference_resistance_changed.emit)
        resistance_layout.addWidget(self.reference_res_spinbox)
        resistance_layout.addStretch()
        acquisition_layout.addLayout(resistance_layout)
        daq_buttons = QHBoxLayout()
        self.start_daq_button = QPushButton("Start DAQ")
        self.stop_daq_button = QPushButton("Stop DAQ")
        self.start_daq_button.clicked.connect(self.plot_manager.start_acquisition)
        self.stop_daq_button.clicked.connect(self.plot_manager.stop_acquisition)
        daq_buttons.addWidget(self.start_daq_button)
        daq_buttons.addWidget(self.stop_daq_button)
        acquisition_layout.addLayout(daq_buttons)
        controls_layout.addWidget(acquisition_group)

        motion_group = self._create_group_box("Motion Control")
        motion_layout = motion_group.layout()
        motion_buttons = QHBoxLayout()
        self.set_home_button = QPushButton("Set Home")
        self.start_motor_button = QPushButton("Start Motion")
        self.stop_motion_button = QPushButton("Stop Motion")
        self.set_home_button.clicked.connect(self.set_home_requested.emit)
        self.start_motor_button.clicked.connect(self.start_motion_requested.emit)
        self.stop_motion_button.clicked.connect(self.stop_motion_requested.emit)
        motion_buttons.addWidget(self.set_home_button)
        motion_buttons.addWidget(self.start_motor_button)
        motion_buttons.addWidget(self.stop_motion_button)
        motion_layout.addLayout(motion_buttons)
        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 1)
        self.progress_bar.setFormat("%v / %m cycles")
        self.progress_bar.hide()
        motion_layout.addWidget(self.progress_bar)
        self.eta_label = QLabel("")
        self.eta_label.hide()
        motion_layout.addWidget(self.eta_label)
        controls_layout.addWidget(motion_group)
        controls_layout.addStretch()

        self.progress_timer = QTimer(self)
        self.progress_timer.setInterval(200)
        self.progress_timer.timeout.connect(self._update_progress_timer)
        self._progress_total_duration = 0.0
        self._progress_cycle_time = 0.0
        self._progress_total_cycles = 0
        self._progress_start_ts = 0.0

        plots_panel = QWidget()
        plots_layout = QVBoxLayout(plots_panel)
        plots_layout.setContentsMargins(0, 0, 0, 0)
        plots_layout.setSpacing(8)
        root_layout.addWidget(plots_panel, 1)

        self.data_widget = PlotWidget()
        self.position_widget = PlotWidget()
        self._configure_plots()
        plots_layout.addWidget(self.data_widget)
        plots_layout.addWidget(self.position_widget)

        self._add_position_row()

    @staticmethod
    def _create_group_box(title: str) -> QGroupBox:
        group = QGroupBox(title)
        layout = QVBoxLayout()
        layout.setContentsMargins(10, 8, 10, 10)
        layout.setSpacing(6)
        group.setLayout(layout)
        return group

    def _add_position_row(self):
        position_widget = QWidget()
        position_layout = QHBoxLayout(position_widget)
        position_layout.setContentsMargins(0, 0, 0, 0)
        position_layout.setSpacing(6)

        label = QLabel("")
        label.setObjectName("positionLabel")
        angle_slider = QSlider(Qt.Orientation.Horizontal)
        angle_slider.setRange(0, 360)
        angle_slider.setValue(0)
        angle_slider.setTickInterval(30)
        angle_slider.setTickPosition(QSlider.TicksBelow)
        angle_slider.setPageStep(5)

        angle_spinbox = QSpinBox()
        angle_spinbox.setObjectName("angleSpinbox")
        angle_spinbox.setRange(0, 360)
        angle_spinbox.setValue(0)
        angle_spinbox.setSuffix("°")

        angle_slider.valueChanged.connect(angle_spinbox.setValue)
        angle_spinbox.valueChanged.connect(angle_slider.setValue)
        angle_spinbox.valueChanged.connect(self._emit_positions_changed)

        delay_slider = QSlider(Qt.Orientation.Horizontal)
        delay_slider.setRange(0, 5000)
        delay_slider.setValue(500)
        delay_slider.setTickInterval(250)
        delay_slider.setTickPosition(QSlider.TicksBelow)
        delay_slider.setPageStep(50)

        delay_spinbox = QSpinBox()
        delay_spinbox.setObjectName("delaySpinbox")
        delay_spinbox.setRange(0, 5000)
        delay_spinbox.setValue(500)
        delay_spinbox.setSuffix(" ms")

        delay_slider.valueChanged.connect(delay_spinbox.setValue)
        delay_spinbox.valueChanged.connect(delay_slider.setValue)
        delay_spinbox.valueChanged.connect(self._emit_positions_changed)

        delete_button = QToolButton()
        delete_button.setText("Remove")
        delete_button.setAutoRaise(True)
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
        self._motion_controls_enabled = bool(enabled)
        self._update_motion_control_buttons()
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

    def current_daq_rate_label(self) -> str:
        return self.daq_rate_combo.currentText()

    def emit_current_daq_rate(self):
        self.daq_rate_changed.emit(self.current_daq_rate_key())

    def emit_current_reference_resistance(self):
        self.reference_resistance_changed.emit(self.reference_resistance_ohms())

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

    def set_motor_initialized(self, initialized: bool):
        self._motor_initialized = bool(initialized)
        if initialized:
            self.motor_status_indicator.setStyleSheet("background-color: #27ae60; border: 1px solid #1e8449;")
            self.motor_status_text.setText("Motor initialized")
            self.init_controls_container.hide()
        else:
            self.motor_status_indicator.setStyleSheet("background-color: #c0392b; border: 1px solid #96281b;")
            self.motor_status_text.setText("Motor not initialized")
            self.init_controls_container.show()
        self._update_motion_control_buttons()

    def set_com_ports(self, ports):
        self.init_com_combo.clear()
        if ports:
            self.init_com_combo.addItems(ports)
        else:
            self.init_com_combo.addItem("No hardware found")

    def experiment_name(self) -> str:
        return self.experiment_name_edit.text().strip()

    def experiment_description(self) -> str:
        return self.experiment_description_edit.toPlainText().strip()

    def reference_resistance_ohms(self) -> float:
        return float(self.reference_res_spinbox.value())

    def _update_live_data(self, timestamp, position, resistance, humidity, temperature, voltage):
        self.live_angle_label.setText(f"Angle: {position:.2f}°")
        self.live_voltage_label.setText(f"Voltage: {voltage:.3f} V")
        if resistance >= 1e6:
            res_str = f"{resistance/1e6:.2f} MΩ"
        elif resistance >= 1e3:
            res_str = f"{resistance/1e3:.2f} kΩ"
        else:
            res_str = f"{resistance:.1f} Ω"
        self.live_resistance_label.setText(f"Resistance: {res_str}")

    def _update_motion_control_buttons(self):
        can_control = self._motor_initialized and self._motion_controls_enabled
        self.set_home_button.setEnabled(can_control)
        self.start_motor_button.setEnabled(can_control)
