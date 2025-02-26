from PyQt5.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QSlider, QSpinBox, QTabWidget, QFileDialog, QComboBox, QMessageBox, QInputDialog
)
from PyQt5.QtCore import Qt, QTimer, QThread, pyqtSignal, QObject
import pyqtgraph as pg
from pyqtgraph import PlotWidget
from data_controller import DAQController
import csv
import sys
import threading
from queue import Queue
from collections import deque
from datetime import datetime

class MainWindow(QMainWindow):
    def __init__(self, motor_controller, ni_device):
        super().__init__()
        self.motor_controller = motor_controller
        self.ni_device = ni_device
        self.plot_manager = PlotManager(self.ni_device, self.motor_controller)
        self.init_ui()

    def init_ui(self):
        self.setWindowTitle("Motor Controller GUI")
        self.setGeometry(100, 100, 500, 300)

        # Tab widget
        self.tab_widget = QTabWidget()

        # Tabs
        self.basic_tab = self.create_basic_tab()
        self.plot_tab = self.create_plot_tab()
        self.expert_tab = self.create_expert_tab()

        self.tab_widget.addTab(self.basic_tab, "Basic Options")
        self.tab_widget.addTab(self.plot_tab, "Data plots")
        self.tab_widget.addTab(self.expert_tab, "Expert Options")

        # Set central widget
        self.setCentralWidget(self.tab_widget)

    def init_daq(self):
        self.daq_controller = DAQController()
    
    def create_basic_tab(self):
        # Basic tab layout
        basic_tab = QWidget()

        # Velocity
        self.velocity_slider, self.velocity_spinbox = self.create_slider_spinbox_pair(1, 500, 100)
        self.velocity_value_label = QLabel(f"{self.velocity_slider.value()}")

        # Position
        self.position_slider, self.position_spinbox = self.create_slider_spinbox_pair(0, 20, 10)
        self.position_value_label = QLabel(f"{self.position_slider.value()}")

        self.repetition_spinbox = self.create_spinbox(0, 10000, 10)
        
        self.status_label = QLabel("Set values and press Start.")

        # Layouts
        main_layout = QVBoxLayout()
        slider_layout = QHBoxLayout()

        # Velocity layout
        velocity_layout = QVBoxLayout()
        velocity_layout.addWidget(QLabel("Velocity (rotations/min):"))
        velocity_slider_layout = QHBoxLayout()
        velocity_slider_layout.addWidget(self.velocity_slider)
        velocity_slider_layout.addWidget(self.velocity_spinbox)
        velocity_layout.addLayout(velocity_slider_layout)

        # Position layout
        position_layout = QVBoxLayout()
        position_layout.addWidget(QLabel("Desired Angle (0-20°):"))
        position_slider_layout = QHBoxLayout()
        position_slider_layout.addWidget(self.position_slider)
        position_slider_layout.addWidget(self.position_spinbox)
        position_layout.addLayout(position_slider_layout)

        slider_layout.addLayout(velocity_layout)
        slider_layout.addLayout(position_layout)

        main_layout.addLayout(slider_layout)
        main_layout.addWidget(QLabel("Number of Repetitions:"))
        main_layout.addWidget(self.repetition_spinbox)
        main_layout.addWidget(self.status_label)

        basic_tab.setLayout(main_layout)      

        return basic_tab

    def create_expert_tab(self):
              # Basic tab layout
        expert_tab = QWidget()

         # Sampling rate for saving data
        self.sampling_rate_spinbox = self.create_spinbox(1, 50, 2)
        
        self.refresh_ports_button = QPushButton("Refresh Ports")
        self.refresh_ports_button.clicked.connect(self.update_com_ports)

        self.select_port_button = QPushButton("Connect selected Device")
        self.select_port_button.clicked.connect(self.select_com_port)

         # COM port selection
        self.com_port_combo = QComboBox()
        self.update_com_ports()
        
        # Acceleration
        self.acceleration_slider, self.acceleration_spinbox = self.create_slider_spinbox_pair(10, 10000, 5000)
        self.acceleration_value_label = QLabel(f"{self.acceleration_slider.value()}")

        # Deceleration
        self.deceleration_slider, self.deceleration_spinbox = self.create_slider_spinbox_pair(10, 10000, 5000)
        self.deceleration_value_label = QLabel(f"{self.deceleration_slider.value()}")

        # Layouts
        main_layout = QVBoxLayout()
        slider_layout = QHBoxLayout()

        # Sampling rate layout
        sampling_rate_layout = QVBoxLayout()
        sampling_rate_layout.addWidget(QLabel("Sampling Rate for Data Saving (Hz):"))
        sampling_rate_layout.addWidget(self.sampling_rate_spinbox)

        # COM port layout
        com_port_layout = QVBoxLayout()
        com_port_layout.addWidget(QLabel("Select COM Port:"))
        com_port_layout.addWidget(self.com_port_combo)
        com_port_layout.addWidget(self.refresh_ports_button)
        com_port_layout.addWidget(self.select_port_button)

        # Acceleration layout
        acceleration_layout = QVBoxLayout()
        acceleration_layout.addWidget(QLabel("Profile Acceleration (units/s²):"))
        acceleration_slider_layout = QHBoxLayout()
        acceleration_slider_layout.addWidget(self.acceleration_slider)
        acceleration_slider_layout.addWidget(self.acceleration_spinbox)
        acceleration_layout.addLayout(acceleration_slider_layout)

        # Deceleration layout
        deceleration_layout = QVBoxLayout()
        deceleration_layout.addWidget(QLabel("Profile Deceleration (units/s²):"))
        deceleration_slider_layout = QHBoxLayout()
        deceleration_slider_layout.addWidget(self.deceleration_slider)
        deceleration_slider_layout.addWidget(self.deceleration_spinbox)
        deceleration_layout.addLayout(deceleration_slider_layout)

        slider_layout.addLayout(acceleration_layout)
        slider_layout.addLayout(deceleration_layout)

        main_layout.addLayout(sampling_rate_layout)
        main_layout.addLayout(com_port_layout)
        main_layout.addLayout(slider_layout)
        main_layout.addWidget(self.status_label)
        

        expert_tab.setLayout(main_layout)

        # Connections
        self.acceleration_slider.valueChanged.connect(lambda: self.sync_slider_spinbox(self.acceleration_slider, self.acceleration_spinbox))
        self.deceleration_slider.valueChanged.connect(lambda: self.sync_slider_spinbox(self.deceleration_slider, self.deceleration_spinbox))
        # convert Hz to ms
        self.sampling_rate_spinbox.valueChanged.connect(lambda: self.plot_manager.set_save_rate(self.sampling_rate_spinbox.value()))

        return expert_tab
    
    def create_plot_tab(self):
        # Create the plot tab
        plot_tab = QWidget()
        layout = QVBoxLayout()

        # Create PyQtGraph widgets
        self.data_widget = PlotWidget()
        self.position_widget = PlotWidget()

        # Setup plots
        self.plot_manager.setup_plots(self.data_widget, self.position_widget)

        # Add widgets to layout
        layout.addWidget(self.data_widget)
        layout.addWidget(self.position_widget)

        # Add controls
        self.set_home_button = QPushButton("Set HOME")
        self.start_motor_button = QPushButton("Start Motion")
        self.stop_motion_button = QPushButton("Stop Motion")
        self.start_daq_button = QPushButton("Start DAQ")
        self.stop_daq_button = QPushButton("STOP DAQ")

        self.start_motor_button.clicked.connect(self.start_motion)
        self.set_home_button.clicked.connect(self.motor_controller.set_home_position)
        self.stop_motion_button.clicked.connect(self.motor_controller.stop_movement)
        self.start_daq_button.clicked.connect(self.plot_manager.start_acquisition)
        self.stop_daq_button.clicked.connect(self.plot_manager.stop_acquisition)

        button_layout = QHBoxLayout()
        button_layout.addWidget(self.set_home_button)
        button_layout.addWidget(self.start_motor_button)
        button_layout.addWidget(self.stop_motion_button)
        button_layout.addWidget(self.start_daq_button)
        button_layout.addWidget(self.stop_daq_button)
        layout.addLayout(button_layout)

        plot_tab.setLayout(layout)
        return plot_tab

    @staticmethod
    def create_slider(min_value, max_value, initial_value):
        slider = QSlider(Qt.Horizontal)
        slider.setRange(min_value, max_value)
        slider.setValue(initial_value)
        return slider

    @staticmethod
    def create_spinbox(min_value, max_value, initial_value):
        spinbox = QSpinBox()
        spinbox.setRange(min_value, max_value)
        spinbox.setValue(initial_value)
        return spinbox

    def create_slider_spinbox_pair(self, min_value, max_value, initial_value):
        """Creates a synchronized slider and spinbox pair."""
        slider = QSlider(Qt.Horizontal)
        slider.setRange(min_value, max_value)
        slider.setValue(initial_value)

        spinbox = QSpinBox()
        spinbox.setRange(min_value, max_value)
        spinbox.setValue(initial_value)

        # Synchronize slider and spinbox
        slider.valueChanged.connect(spinbox.setValue)
        spinbox.valueChanged.connect(slider.setValue)
        return slider, spinbox

    def start_motion(self):
        prof_velocity = self.velocity_slider.value()
        # angle for rotation in 10th degrees (3600=one round)
        angle = self.position_slider.value() * 10
        target_position1 = 3600-angle
        repetitions = self.repetition_spinbox.value()
        max_acceleration = 5000 
        prof_acceleration = 5000  
        max_deceleration = 500 
        prof_deceleration = 500 
        # prof_velocity = 100
        end_velocity = 0 
        home_position = 3600  # Pocatecni pozice
        # target_position1 = 3600  # Cílová pozice 1
        target_position2 = 3600  # Cílová pozice 2 
        # repetitions = 2 # number of repetition

        self.toggle_inputs(False)
        self.status_label.setText("Processing... Please wait.")
        # Set motion parameters
        self.motor_controller.set_motion_parameters(
        max_acceleration, prof_acceleration, max_deceleration, prof_deceleration,
        prof_velocity, end_velocity)
        #QTimer.singleShot(100, lambda: self.motor_controller.set_motion_parameters(max_acceleration, prof_acceleration, max_deceleration, prof_deceleration,
        #                       prof_velocity, end_velocity))
        #QTimer.singleShot(100, lambda: self.motor_controller.execute_motion(home_position, target_position1, target_position2, repetitions))
        # Create a thread and worker
        self.thread = QThread()
        self.worker = MotionWorker(
            self.motor_controller, home_position, target_position1, target_position2, repetitions
        )
        self.worker.moveToThread(self.thread)

        # Connect signals and slots
        self.thread.started.connect(self.worker.run)
        self.worker.finished.connect(self.thread.quit)
        self.worker.finished.connect(self.worker.deleteLater)
        self.thread.finished.connect(self.thread.deleteLater)
        self.worker.status_updated.connect(self.status_label.setText)
        self.worker.finished.connect(lambda: self.toggle_inputs(True))

        # Start the thread
        self.thread.start()

    def toggle_inputs(self, enabled):
        # Now these sliders and buttons are accessible because they are instance variables
        self.velocity_slider.setEnabled(enabled)
        self.position_slider.setEnabled(enabled)
        self.repetition_spinbox.setEnabled(enabled)
        #self.stop_motion_button.setEnabled(enabled)
        self.set_home_button.setEnabled(enabled)

    def update_com_ports(self):
        try:
            bus_hw, hardware_items = self.motor_controller.select_bus_hardware()
            print(f"Bus hardware IDs: {bus_hw}")
            print(f"Hardware items: {hardware_items}")
            self.com_port_combo.clear()
            self.com_port_combo.addItems(hardware_items)
        except Exception as e:
            print(f"Error updating COM ports: {e}")
            self.com_port_combo.clear()
            self.com_port_combo.addItem("No hardware found")

    def select_com_port(self):
        try:
            # Get selected index
            selected_index = self.com_port_combo.currentIndex()
            if selected_index < 0:
                raise Exception("No hardware selected.")
            
            # Initialize motor with selected hardware
            self.motor_controller.initialize_motor(selected_index)
            QMessageBox.information(self, "Success", "Motor initialized successfully!")
        except Exception as e:
            QMessageBox.critical(self, "Error", str(e))

class PlotManager:
    def __init__(self, ni_device, motor_controller):
        self.ni_device = ni_device
        self.motor_controller = motor_controller
        self.daq_controller = DAQController("Dev1", "ai1", 500, self.motor_controller)

        # Data buffers for voltage and position
        self.position_buffer = deque(maxlen=500)
        self.voltage_buffer = deque(maxlen=500)

        # Configuration
        self.data_save_rate = 500  # ms

    def setup_plots(self, data_widget, position_widget):
        """Setup PyQtGraph plots."""
        # Electrode Data Plot
        self.data_plot = data_widget
        self.data_plot.setTitle("Electrode Data")
        self.data_plot.setLabel("left", "Resistance (Ω)")
        self.data_plot.setLabel("bottom", "Sample count")
        self.data_plot.showGrid(x=True, y=True)
        self.data_curve = self.data_plot.plot(
            pen=pg.mkPen(color='r', width=1),  # Blue line with width=2
            symbol='+',  # Circle marker at each data point
            symbolSize=8,  # Marker size
            symbolBrush='w'  # Red color for points
        )

        # Motor Position Plot
        self.position_plot = position_widget
        self.position_plot.setTitle("Motor Position")
        self.position_plot.setLabel("left", "Angle (°)")
        self.position_plot.setLabel("bottom", "Sample count")
        self.position_plot.showGrid(x=True, y=True)
        self.position_curve = self.position_plot.plot(
            pen=pg.mkPen(color='b', width=1),  # Blue line with width=2
            symbol='+',  # Circle marker at each data point
            symbolSize=8,  # Marker size
            symbolBrush='w'  # Red color for points
        )

    def update_plot(self):
        """Update the plots with the latest data."""
        # Plot the latest data: voltage vs. timestamp (x-axis in seconds)
        self.data_curve.setData(self.voltage_buffer)
        self.position_curve.setData(self.position_buffer)

    def handle_new_data(self, timestamp, position, voltage):
        """Handle new data from DAQ thread."""
        self.voltage_buffer.append(voltage)
        self.position_buffer.append(position)
        
        # Update the plot immediately with new data
        self.update_plot()

    def browse_file(self):
        """Open a file dialog and suggest a default name based on date and time."""
        default_filename = f"measurement_{datetime.now().strftime('%Y%m%d_%H%M')}.csv"
        file_name, _ = QFileDialog.getSaveFileName(
            None, "Select File", default_filename, "CSV Files (*.csv);;All Files (*)"
        )
        if file_name:
            self.file_path = file_name
        return file_name

    def start_acquisition(self):
        """Start DAQ measurement and data saving."""
        # Start DAQ controller
        self.daq_controller.data_signal.connect(self.handle_new_data)
        self.daq_controller.start()

    def set_save_rate(self, rate):
        """Set the rate at which data is saved to the file."""
        self.data_save_rate = rate
        self.daq_controller.change_sample_rate(rate)


    def stop_acquisition(self):
        """Stop DAQ measurement and data saving."""
        self.daq_controller.stop()

    def closeEvent(self, event):
        """Ensure proper cleanup when closing the window."""
        self.stop_acquisition()
        event.accept()

class MotionWorker(QObject):
    finished = pyqtSignal()
    status_updated = pyqtSignal(str)

    def __init__(self, motor_controller, home_position, target_position1, target_position2, repetitions):
        super().__init__()
        self.motor_controller = motor_controller
        self.home_position = home_position
        self.target_position1 = target_position1
        self.target_position2 = target_position2
        self.repetitions = repetitions

    def run(self):
        try:
            self.status_updated.emit("Executing motion...")
            self.motor_controller.execute_motion(
                self.home_position, self.target_position1, self.target_position2, self.repetitions
            )
            self.status_updated.emit("Motion completed successfully.")
        except Exception as e:
            self.status_updated.emit(f"Error during motion: {str(e)}")
        finally:
            self.finished.emit()