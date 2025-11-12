from PyQt5.QtCore import pyqtSignal, Qt
from PyQt5.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QComboBox,
    QSlider,
    QSpinBox,
)


class ExpertTab(QWidget):
    """Provides advanced device and acquisition controls."""

    refresh_ports_requested = pyqtSignal()
    connect_port_requested = pyqtSignal(int)
    sampling_rate_changed = pyqtSignal(int)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._build_ui()

    def _build_ui(self) -> None:
        main_layout = QVBoxLayout(self)

        sampling_rate_layout = QVBoxLayout()
        sampling_rate_layout.addWidget(QLabel("Sampling Rate for Data Saving (Hz):"))
        self.sampling_rate_spinbox = self._create_spinbox(1, 50, 2)
        sampling_rate_layout.addWidget(self.sampling_rate_spinbox)

        com_port_layout = QVBoxLayout()
        com_port_layout.addWidget(QLabel("Select COM Port:"))
        self.com_port_combo = QComboBox()
        com_port_layout.addWidget(self.com_port_combo)

        self.refresh_ports_button = QPushButton("Refresh Ports")
        self.refresh_ports_button.clicked.connect(self.refresh_ports_requested.emit)
        com_port_layout.addWidget(self.refresh_ports_button)

        self.select_port_button = QPushButton("Connect selected Device")
        self.select_port_button.clicked.connect(self._emit_selected_port)
        com_port_layout.addWidget(self.select_port_button)

        acceleration_layout = QVBoxLayout()
        acceleration_layout.addWidget(QLabel("Profile Acceleration (units/s²):"))
        self.acceleration_slider, self.acceleration_spinbox = self._create_slider_spinbox_pair(
            10, 10000, 5000
        )
        acceleration_row = QHBoxLayout()
        acceleration_row.addWidget(self.acceleration_slider)
        acceleration_row.addWidget(self.acceleration_spinbox)
        acceleration_layout.addLayout(acceleration_row)

        deceleration_layout = QVBoxLayout()
        deceleration_layout.addWidget(QLabel("Profile Deceleration (units/s²):"))
        self.deceleration_slider, self.deceleration_spinbox = self._create_slider_spinbox_pair(
            10, 10000, 5000
        )
        deceleration_row = QHBoxLayout()
        deceleration_row.addWidget(self.deceleration_slider)
        deceleration_row.addWidget(self.deceleration_spinbox)
        deceleration_layout.addLayout(deceleration_row)

        slider_layout = QHBoxLayout()
        slider_layout.addLayout(acceleration_layout)
        slider_layout.addLayout(deceleration_layout)

        main_layout.addLayout(sampling_rate_layout)
        main_layout.addLayout(com_port_layout)
        main_layout.addLayout(slider_layout)

        self.sampling_rate_spinbox.valueChanged.connect(
            lambda value: self.sampling_rate_changed.emit(int(value))
        )

    def _create_spinbox(self, minimum: int, maximum: int, initial: int) -> QSpinBox:
        spinbox = QSpinBox()
        spinbox.setRange(minimum, maximum)
        spinbox.setValue(initial)
        return spinbox

    def _create_slider_spinbox_pair(self, minimum: int, maximum: int, initial: int):
        slider = QSlider(Qt.Horizontal)
        slider.setRange(minimum, maximum)
        slider.setValue(initial)

        spinbox = QSpinBox()
        spinbox.setRange(minimum, maximum)
        spinbox.setValue(initial)

        slider.valueChanged.connect(spinbox.setValue)
        spinbox.valueChanged.connect(slider.setValue)
        return slider, spinbox

    def _emit_selected_port(self) -> None:
        self.connect_port_requested.emit(self.com_port_combo.currentIndex())

    def set_com_ports(self, ports) -> None:
        self.com_port_combo.clear()
        if ports:
            self.com_port_combo.addItems(ports)
        else:
            self.com_port_combo.addItem("No hardware found")

    def get_accel_settings(self):
        return {
            "acceleration": self.acceleration_spinbox.value(),
            "deceleration": self.deceleration_spinbox.value(),
        }
