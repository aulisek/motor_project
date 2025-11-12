from PyQt5.QtCore import pyqtSignal
from PyQt5.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QPushButton
from pyqtgraph import PlotWidget


class PlotTab(QWidget):
    """Hosts plot widgets and motion control buttons."""

    start_motion_requested = pyqtSignal()
    stop_motion_requested = pyqtSignal()
    set_home_requested = pyqtSignal()

    def __init__(self, plot_manager, parent=None):
        super().__init__(parent)
        self.plot_manager = plot_manager
        self._build_ui()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)

        self.data_widget = PlotWidget()
        self.position_widget = PlotWidget()

        self._configure_plots()

        layout.addWidget(self.data_widget)
        layout.addWidget(self.position_widget)

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

        layout.addLayout(button_layout)

    def _configure_plots(self) -> None:
        """Prepare both PyQtGraph widgets via the shared plot manager."""
        self.plot_manager.setup_plots(self.data_widget, self.position_widget)

    def set_motion_controls_enabled(self, enabled: bool) -> None:
        self.set_home_button.setEnabled(enabled)
        self.start_motor_button.setEnabled(enabled)
        # Keep stop enabled so users can always abort.
        self.stop_motion_button.setEnabled(True)
