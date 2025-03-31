from PyQt5.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QSlider, QSpinBox, QTabWidget, QFileDialog, QComboBox, QMessageBox, QInputDialog, QLineEdit, QFormLayout, QGraphicsView, QGraphicsScene, QGraphicsEllipseItem, QGraphicsEllipseItem, QGraphicsLineItem, QFormLayout, QSizePolicy, QScrollArea, QGridLayout
)
from PyQt5.QtCore import Qt, QTimer, QThread, pyqtSignal, QObject, QPointF, pyqtSignal
from PyQt5.QtGui import QPen, QMouseEvent
import pyqtgraph as pg
from pyqtgraph import PlotWidget
from data_controller import DAQController
import csv
import sys
import threading
import math
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
        """Create the UI layout with dynamic position inputs."""

        tab_widget = QWidget()
        self.layout = QVBoxLayout(tab_widget)

        # **Step 1: Global Settings (Velocity & Repetitions)**
        global_inputs_layout = QFormLayout()

        self.velocity_input = QSpinBox()
        self.velocity_input.setRange(1, 1000)
        self.velocity_input.setSuffix(" mm/s")
        global_inputs_layout.addRow("Velocity:", self.velocity_input)

        self.repetitions_input = QSpinBox()
        self.repetitions_input.setRange(1, 100)
        global_inputs_layout.addRow("Repetitions:", self.repetitions_input)

        self.layout.addLayout(global_inputs_layout)

        # **Step 2: Number of Positions Selector**
        self.num_positions_label = QLabel("Number of Positions:")
        self.num_positions_spinbox = QSpinBox()
        self.num_positions_spinbox.setRange(1, 10)
        self.num_positions_spinbox.valueChanged.connect(self.create_position_inputs)

        self.layout.addWidget(self.num_positions_label)
        self.layout.addWidget(self.num_positions_spinbox)

        # **Step 3: Container for Dynamic Inputs**
        self.positions_container = QWidget()
        self.positions_layout = QVBoxLayout()  
        self.positions_container.setLayout(self.positions_layout)
        self.layout.addWidget(self.positions_container)

        self.create_position_inputs()  # Initialize with default value

        return tab_widget

    def create_position_inputs(self):
        """Dynamically create position input fields and properly clear the layout."""

        # **Step 1: Remove old widgets properly**
        while self.positions_layout.count():
            item = self.positions_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        num_positions = self.num_positions_spinbox.value()

        for i in range(num_positions):
            position_widget = QWidget()
            position_layout = QHBoxLayout(position_widget)

            # **Label**
            label = QLabel(f"Position {i+1}:")

            # **Angle Selector**
            angle_slider = QSlider(Qt.Orientation.Horizontal)
            angle_slider.setRange(-180, 180)
            angle_slider.setValue(0)

            angle_spinbox = QSpinBox()
            angle_spinbox.setRange(-180, 180)
            angle_spinbox.setValue(0)

            angle_slider.valueChanged.connect(angle_spinbox.setValue)
            angle_spinbox.valueChanged.connect(angle_slider.setValue)

            # **Delay Input (Slider + Spinbox)**
            delay_slider = QSlider(Qt.Orientation.Horizontal)
            delay_slider.setRange(0, 5000)
            delay_slider.setValue(500)

            delay_spinbox = QSpinBox()
            delay_spinbox.setRange(0, 5000)
            delay_spinbox.setValue(500)
            delay_spinbox.setSuffix(" ms")

            delay_slider.valueChanged.connect(delay_spinbox.setValue)
            delay_spinbox.valueChanged.connect(delay_slider.setValue)

            # **Add widgets to layout**
            position_layout.addWidget(label)
            position_layout.addWidget(angle_slider)
            position_layout.addWidget(angle_spinbox)
            position_layout.addWidget(QLabel("Delay:"))
            position_layout.addWidget(delay_slider)
            position_layout.addWidget(delay_spinbox)

            self.positions_layout.addWidget(position_widget)

        self.positions_container.update()

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
        #main_layout.addWidget(self.status_label)
        

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
        """Start the motion sequence using multiple positions and delays."""
        
        prof_velocity = self.velocity_input.value()  # Get velocity
        repetitions = self.repetitions_input.value()  # Get number of repetitions

        max_acceleration = 30
        prof_acceleration = 30
        max_deceleration = 30
        prof_deceleration = 30
        end_velocity = 0
        home_position = 3600  # Initial position

        # **Extract positions and delays from UI**
        positions = []
        delays = []

        for i in range(self.positions_layout.count()):
            item = self.positions_layout.itemAt(i)
            if item and item.widget():
                position_widget = item.widget()
                inputs = position_widget.findChildren(QSpinBox)

                if len(inputs) >= 2:
                    angle_spinbox = inputs[0]
                    delay_spinbox = inputs[1]

                    angle = angle_spinbox.value() * 10  # Convert to 10th degrees
                    delay = delay_spinbox.value()  # Get delay in ms

                    positions.append(3600 - angle)  # Convert to motor position
                    delays.append(delay)

        # **Ensure valid data**
        if not positions:
            self.status_label.setText("No positions defined!")
            return

        # **Disable UI and show status**
        self.toggle_inputs(False)
        #self.status_label.setText("Processing... Please wait.")

        # **Set motion parameters**
        self.motor_controller.set_motion_parameters(
            max_acceleration, prof_acceleration, max_deceleration, prof_deceleration,
            prof_velocity, end_velocity
        )

        # **Create thread and worker**
        self.thread = QThread()
        self.worker = MotionWorker(
            self.motor_controller, home_position, positions, delays, repetitions
        )
        self.worker.moveToThread(self.thread)

        # **Connect signals and slots**
        self.thread.started.connect(self.worker.run)
        self.worker.finished.connect(self.thread.quit)
        self.worker.finished.connect(self.worker.deleteLater)
        self.thread.finished.connect(self.thread.deleteLater)
      #  self.worker.status_updated.connect(self.status_label.setText)
        self.worker.finished.connect(lambda: self.toggle_inputs(True))

        # **Start motion thread**
        self.thread.start()
        
    def toggle_inputs(self, enabled):
            # Now these sliders and buttons are accessible because they are instance variables
            #self.velocity_slider.setEnabled(enabled)
            #self.position_slider.setEnabled(enabled)
            #self.repetition_spinbox.setEnabled(enabled)
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

    def __init__(self, motor_controller, home_position, positions, delays, repetitions):
        super().__init__()
        self.motor_controller = motor_controller
        self.home_position = home_position
        self.positions = positions  # List of target positions
        self.delays = delays  # List of delays (in ms)
        self.repetitions = repetitions

    def run(self):
        try:
            self.status_updated.emit("Executing motion...")
            self.motor_controller.execute_motion(
                self.home_position, self.positions, self.delays, self.repetitions
            )
            self.status_updated.emit("Motion completed successfully.")
        except Exception as e:
            self.status_updated.emit(f"Error during motion: {str(e)}")
        finally:
            self.finished.emit()