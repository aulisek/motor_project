from PyQt5.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QSlider, QSpinBox, QTabWidget, QFileDialog
)
from PyQt5.QtCore import Qt, QTimer, QThread, pyqtSignal, QObject
import pyqtgraph as pg
from pyqtgraph import PlotWidget
import csv
import sys

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
        self.expert_tab = self.create_expert_tab()
        self.plot_tab = self.create_plot_tab()

        self.tab_widget.addTab(self.basic_tab, "Basic Options")
        self.tab_widget.addTab(self.expert_tab, "Expert Options")
        self.tab_widget.addTab(self.plot_tab, "Data plots")

        # Set central widget
        self.setCentralWidget(self.tab_widget)

    def create_basic_tab(self):
        # Basic tab layout
        basic_tab = QWidget()

        self.velocity_slider = self.create_slider(1, 100, 50)
        self.velocity_value_label = QLabel(f"{self.velocity_slider.value()}")
        self.position_slider = self.create_slider(0, 360, 50)
        self.position_value_label = QLabel(f"{self.position_slider.value()}")
        self.repetition_spinbox = self.create_spinbox(0, 1000, 10)
        self.start_button = QPushButton("Start Motion")
        self.status_label = QLabel("Set values and press Start.")

        # Layouts
        main_layout = QVBoxLayout()
        slider_layout = QHBoxLayout()

        # Velocity slider with label
        velocity_layout = QVBoxLayout()
        velocity_layout.addWidget(QLabel("Velocity (rotations/min):"))
        velocity_slider_layout = QHBoxLayout()
        velocity_slider_layout.addWidget(self.velocity_slider)
        velocity_slider_layout.addWidget(self.velocity_value_label)
        velocity_layout.addLayout(velocity_slider_layout)

        # Position slider with label
        position_layout = QVBoxLayout()
        position_layout.addWidget(QLabel("Desired Angle (0-360°):"))
        position_slider_layout = QHBoxLayout()
        position_slider_layout.addWidget(self.position_slider)
        position_slider_layout.addWidget(self.position_value_label)
        position_layout.addLayout(position_slider_layout)

        slider_layout.addLayout(velocity_layout)
        slider_layout.addLayout(position_layout)

        main_layout.addLayout(slider_layout)
        main_layout.addWidget(QLabel("Number of Repetitions:"))
        main_layout.addWidget(self.repetition_spinbox)
        main_layout.addWidget(self.start_button)
        main_layout.addWidget(self.status_label)

        basic_tab.setLayout(main_layout)

        # Connections
        self.start_button.clicked.connect(self.start_motion)
        self.velocity_slider.valueChanged.connect(lambda: self.velocity_value_label.setText(f"{self.velocity_slider.value()}"))
        self.position_slider.valueChanged.connect(lambda: self.position_value_label.setText(f"{self.position_slider.value()}"))

        return basic_tab

    def create_expert_tab(self):
        # Expert tab layout
        expert_tab = QWidget()

        # Example widgets for expert options
        advanced_setting_1 = QLabel("Advanced Setting 1:")
        advanced_slider = self.create_slider(0, 200, 100)
        advanced_value_label = QLabel(f"{advanced_slider.value()}")
        advanced_slider.valueChanged.connect(lambda: advanced_value_label.setText(f"{advanced_slider.value()}"))

        advanced_layout = QVBoxLayout()
        advanced_layout.addWidget(advanced_setting_1)
        advanced_slider_layout = QHBoxLayout()
        advanced_slider_layout.addWidget(advanced_slider)
        advanced_slider_layout.addWidget(advanced_value_label)
        advanced_layout.addLayout(advanced_slider_layout)

        advanced_setting_2 = QLabel("Advanced Setting 2:")
        advanced_spinbox = self.create_spinbox(0, 500, 250)
        advanced_layout.addWidget(advanced_setting_2)
        advanced_layout.addWidget(advanced_spinbox)

        expert_tab.setLayout(advanced_layout)
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
        self.start_button = QPushButton("Start Plotting")
        self.stop_button = QPushButton("Stop Plotting")
        self.save_button = QPushButton("Save Data")

        self.start_button.clicked.connect(self.plot_manager.start)
        self.stop_button.clicked.connect(self.plot_manager.stop)
        self.save_button.clicked.connect(self.save_plot_data)

        button_layout = QHBoxLayout()
        button_layout.addWidget(self.start_button)
        button_layout.addWidget(self.stop_button)
        button_layout.addWidget(self.save_button)
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

    def start_motion(self):
        prof_velocity = self.velocity_slider.value()
        target_position1 = self.position_slider.value() * 10
        repetitions = self.repetition_spinbox.value()
        max_acceleration = 40 
        prof_acceleration = 40  
        max_deceleration = 40 
        prof_deceleration = 40 
        # prof_velocity = 100
        end_velocity = 0 
        home_position = 900  # Pocatecni pozice
        # target_position1 = 3600  # Cílová pozice 1
        target_position2 = 900  # Cílová pozice 2 
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
        self.start_button.setEnabled(enabled)
    
    def save_plot_data(self):
        """Prompt the user to select a file path and save the data."""
        file_path, _ = QFileDialog.getSaveFileName(
            self, "Save Data", "", "CSV Files (*.csv);;All Files (*)"
        )
        if file_path:
            self.plot_manager.save_data(file_path)

class PlotManager:
    def __init__(self, ni_device, motor_controller):
        self.ni_device = ni_device
        self.motor_controller = motor_controller

        # Timers
        self.gui_timer = QTimer()
        self.data_timer = QTimer()

        # Data storage
        self.data = []  # Electrode data
        self.position_data = []  # Motor position data

        # PyQtGraph Plots
        self.data_plot = None
        self.position_plot = None
        self.data_curve = None
        self.position_curve = None

        # Configuration
        self.gui_refresh_rate = 50  # 100 ms for GUI updates
        self.data_save_rate = 50  # 1 second for storing data

    def setup_plots(self, data_widget: PlotWidget, position_widget: PlotWidget):
        """Setup PyQtGraph plots."""
        # Electrode Data Plot
        self.data_plot = data_widget
        self.data_plot.setTitle("Electrode Data")
        self.data_plot.setLabel("left", "Voltage (V)")
        self.data_plot.setLabel("bottom", "Time (s)")
        self.data_curve = self.data_plot.plot(pen=pg.mkPen(color='b', width=2))

        # Motor Position Plot
        self.position_plot = position_widget
        self.position_plot.setTitle("Motor Position")
        self.position_plot.setLabel("left", "Angle (°)")
        self.position_plot.setLabel("bottom", "Time (s)")
        self.position_curve = self.position_plot.plot(pen=pg.mkPen(color='r', width=2))

    def start(self):
        """Start real-time plotting and data storage with separate timers."""
        self.gui_timer.timeout.connect(self.update_plot)
        self.gui_timer.start(self.gui_refresh_rate)

        self.data_timer.timeout.connect(self.record_data)
        self.data_timer.start(self.data_save_rate)

    def stop(self):
        """Stop both plotting and data recording."""
        self.gui_timer.stop()
        self.data_timer.stop()

    def update_plot(self):
        """Update the plots with new data from NI device and motor controller."""
        # Plot the latest data
        self.data_curve.setData(self.data)
        self.position_curve.setData(self.position_data)

    def record_data(self):
        """Collect data from NI device and motor controller for storage."""
        # Get data
        electrode_value = self.ni_device.get_measurement()  
        motor_position = self.motor_controller.get_position()  

        # Store data
        self.data.append(electrode_value)
        self.position_data.append(motor_position)

    def save_data(self, file_path):
        """Save the recorded data to the specified CSV file."""
        try:
            with open(file_path, mode="w", newline="") as file:
                writer = csv.writer(file)
                writer.writerow(["Time", "Electrode Data", "Motor Position"])
                for i, (e_val, m_pos) in enumerate(zip(self.data, self.position_data)):
                    writer.writerow([i, e_val, m_pos])
            print(f"Data saved to {file_path}.")
        except Exception as e:
            print(f"Error saving data: {str(e)}")

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