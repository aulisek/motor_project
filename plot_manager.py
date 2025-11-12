from collections import deque

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

        self.data_save_rate = 500  # ms

    def setup_plots(self, data_widget, position_widget):
        self.data_plot = data_widget
        self.data_plot.setTitle("Electrode Data")
        self.data_plot.setLabel("left", "Resistance (Ω)")
        self.data_plot.setLabel("bottom", "Sample count")
        self.data_plot.showGrid(x=True, y=True)
        self.data_curve = self.data_plot.plot(
            pen=pg.mkPen(color="r", width=1),
            symbol="+",
            symbolSize=8,
            symbolBrush="w",
        )

        self.position_plot = position_widget
        self.position_plot.setTitle("Motor Position")
        self.position_plot.setLabel("left", "Angle (°)")
        self.position_plot.setLabel("bottom", "Sample count")
        self.position_plot.showGrid(x=True, y=True)
        self.position_curve = self.position_plot.plot(
            pen=pg.mkPen(color="b", width=1),
            symbol="+",
            symbolSize=8,
            symbolBrush="w",
        )

    def update_plot(self):
        self.data_curve.setData(self.resistance_buffer)
        self.position_curve.setData(self.position_buffer)

    def handle_new_data(self, timestamp, position, resistance, humidity, temperature):
        self.resistance_buffer.append(resistance)
        self.position_buffer.append(position)
        self.update_plot()

    def start_acquisition(self):
        if not self.daq_controller.isRunning():
            self.daq_controller.start()

    def set_save_rate(self, rate: int):
        safe_rate = max(1, int(rate))
        self.data_save_rate = safe_rate
        self.daq_controller.change_sample_rate(safe_rate)

    def stop_acquisition(self):
        self.daq_controller.stop()

    def set_daq_sample_rate(self, rate_key: str):
        self.daq_controller.set_ads1263_sample_rate(rate_key)
