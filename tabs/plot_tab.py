from dataclasses import dataclass
from typing import List, Tuple

from PyQt5.QtCore import pyqtSignal, Qt
from PyQt5.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QPushButton,
    QLabel,
    QSlider,
    QSpinBox,
    QComboBox,
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

    def __init__(self, plot_manager, parent=None):
        super().__init__(parent)
        self.plot_manager = plot_manager
        self._build_ui()

    def _build_ui(self) -> None:
        root_layout = QHBoxLayout(self)

        # Sidebar with dynamic positions
        sidebar = QWidget()
        sidebar_layout = QVBoxLayout(sidebar)

        count_layout = QHBoxLayout()
        count_layout.addWidget(QLabel("Number of Positions:"))
        self.num_positions_spinbox = QSpinBox()
        self.num_positions_spinbox.setRange(1, 10)
        self.num_positions_spinbox.valueChanged.connect(self._create_position_inputs)
        count_layout.addWidget(self.num_positions_spinbox)
        sidebar_layout.addLayout(count_layout)

        self.positions_container = QWidget()
        self.positions_layout = QVBoxLayout(self.positions_container)
        sidebar_layout.addWidget(self.positions_container)

        self.status_label = QLabel("")
        sidebar_layout.addWidget(self.status_label)

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

        self._create_position_inputs()

    def _create_position_inputs(self) -> None:
        while self.positions_layout.count():
            item = self.positions_layout.takeAt(0)
            widget = item.widget()
            if widget:
                widget.deleteLater()

        for index in range(self.num_positions_spinbox.value()):
            position_widget = QWidget()
            position_layout = QHBoxLayout(position_widget)

            label = QLabel(f"Position {index + 1}:")
            angle_slider = QSlider(Qt.Orientation.Horizontal)
            angle_slider.setRange(0, 360)
            angle_slider.setValue(0)

            angle_spinbox = QSpinBox()
            angle_spinbox.setRange(0, 360)
            angle_spinbox.setValue(0)

            angle_slider.valueChanged.connect(angle_spinbox.setValue)
            angle_spinbox.valueChanged.connect(angle_slider.setValue)

            delay_slider = QSlider(Qt.Orientation.Horizontal)
            delay_slider.setRange(0, 5000)
            delay_slider.setValue(500)

            delay_spinbox = QSpinBox()
            delay_spinbox.setRange(0, 5000)
            delay_spinbox.setValue(500)
            delay_spinbox.setSuffix(" ms")

            delay_slider.valueChanged.connect(delay_spinbox.setValue)
            delay_spinbox.valueChanged.connect(delay_slider.setValue)

            position_layout.addWidget(label)
            position_layout.addWidget(angle_slider)
            position_layout.addWidget(angle_spinbox)
            position_layout.addWidget(QLabel("Delay:"))
            position_layout.addWidget(delay_slider)
            position_layout.addWidget(delay_spinbox)

            self.positions_layout.addWidget(position_widget)

        self.positions_container.update()

    def build_motion_plan(self) -> MotionPlan:
        positions, delays = self._extract_positions_and_delays()
        if not positions:
            raise ValueError("No positions defined!")
        return MotionPlan(positions=positions, delays=delays)

    def _extract_positions_and_delays(self) -> Tuple[List[int], List[int]]:
        positions: List[int] = []
        delays: List[int] = []

        for index in range(self.positions_layout.count()):
            item = self.positions_layout.itemAt(index)
            widget = item.widget() if item else None
            if not widget:
                continue

            inputs = widget.findChildren(QSpinBox)
            if len(inputs) < 2:
                continue

            angle_spinbox, delay_spinbox = inputs[0], inputs[1]
            angle = angle_spinbox.value() * 10  # convert to 0.1° counts
            delay = delay_spinbox.value()
            positions.append(3600 - angle)
            delays.append(delay)

        return positions, delays

    def set_status(self, text: str) -> None:
        self.status_label.setText(text or "")

    def set_position_inputs_enabled(self, enabled: bool) -> None:
        self.num_positions_spinbox.setEnabled(enabled)
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
