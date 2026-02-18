from collections import deque

from PyQt5.QtCore import QTimer
import pyqtgraph as pg
from data_controller import DAQController


class PlotManager:
    """Encapsulates data acquisition hooks and PyQtGraph setup."""

    def __init__(self, motor_controller):
        self.motor_controller = motor_controller
        self.daq_controller = DAQController(self.motor_controller, 500)
        self.daq_controller.data_signal.connect(self.handle_new_data)

        self.position_buffer = deque(maxlen=500)
        self.resistance_buffer = deque(maxlen=500)
        self._plotting_enabled = False

        self._plot_timer = QTimer()
        self._plot_timer.setInterval(50)
        self._plot_timer.timeout.connect(self._flush_plot_data)
        self._plot_dirty = False

    def setup_plots(self, data_widget, position_widget):
        self.data_plot = data_widget
        self.data_plot.setTitle("Electrode Data")
        self.data_plot.setLabel("left", "Resistance (Ω)")
        self.data_plot.setLabel("bottom", "Sample count")
        self.data_plot.showGrid(x=True, y=True)
        # Draw markers so individual samples remain visible on dense traces.
        sample_symbol = {"symbol": "x", "symbolSize": 8}
        self.data_curve = self.data_plot.plot(
            pen=pg.mkPen(color="r", width=1),
            symbolPen=pg.mkPen(color="r"),
            **sample_symbol,
        )

        self.position_plot = position_widget
        self.position_plot.setTitle("Motor Position")
        self.position_plot.setLabel("left", "Angle (°)")
        self.position_plot.setLabel("bottom", "Sample count")
        self.position_plot.showGrid(x=True, y=True)
        self.position_curve = self.position_plot.plot(
            pen=pg.mkPen(color="b", width=1),
            symbolPen=pg.mkPen(color="b"),
            **sample_symbol,
        )

    def update_plot(self):
        self.data_curve.setData(self.resistance_buffer)
        self.position_curve.setData(self.position_buffer)

    def handle_new_data(self, timestamp, position, resistance, humidity, temperature, voltage):
        if not self._plotting_enabled:
            return
        self.resistance_buffer.append(resistance)
        self.position_buffer.append(position)
        self._plot_dirty = True
        if not self._plot_timer.isActive():
            self._plot_timer.start()

    def _flush_plot_data(self):
        if not self._plot_dirty:
            self._plot_timer.stop()
            return
        self._plot_dirty = False
        self.update_plot()

    def reset_plot_data(self):
        """Clear buffers so each motion run starts with fresh plots."""
        self.resistance_buffer.clear()
        self.position_buffer.clear()
        self._plot_dirty = False
        self._plot_timer.stop()
        if hasattr(self, "data_curve"):
            self.data_curve.setData([])
        if hasattr(self, "position_curve"):
            self.position_curve.setData([])

    def start_acquisition(self):
        if not self.daq_controller.isRunning():
            self.daq_controller.start()
        self.daq_controller.start_logging()
        self._plotting_enabled = True

    def start_monitoring(self):
        """Start the DAQ thread for live values without logging to CSV."""
        if not self.daq_controller.isRunning():
            self.daq_controller.start()

    def set_experiment_metadata(self, metadata: dict):
        self.daq_controller.set_experiment_metadata(metadata or {})

    def set_reference_resistance(self, value: float):
        """Forward the user-selected reference resistor to the DAQ thread."""
        self.daq_controller.set_reference_resistance(value)

    def stop_acquisition(self):
        self.daq_controller.stop_logging()
        self._plotting_enabled = False
        self.reset_plot_data()

    def set_daq_sample_rate(self, rate_key: str):
        self.daq_controller.set_ads1263_sample_rate(rate_key)

    def shutdown(self):
        """Completely stop and release DAQ resources."""
        self.daq_controller.cleanup()
