from PyQt5.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QSlider, QSpinBox, QTabWidget
)
from PyQt5.QtCore import Qt, QTimer


class MainWindow(QMainWindow):
    def __init__(self, motor_controller):
        super().__init__()
        self.motor_controller = motor_controller
        self.init_ui()

    def init_ui(self):
        self.setWindowTitle("Motor Controller GUI")
        self.setGeometry(100, 100, 500, 300)

        # Tab widget
        self.tab_widget = QTabWidget()

        # Tabs
        self.basic_tab = self.create_basic_tab()
        self.expert_tab = self.create_expert_tab()

        self.tab_widget.addTab(self.basic_tab, "Basic Options")
        self.tab_widget.addTab(self.expert_tab, "Expert Options")

        # Set central widget
        self.setCentralWidget(self.tab_widget)

    def create_basic_tab(self):
        # Basic tab layout
        basic_tab = QWidget()

        velocity_slider = self.create_slider(1, 100, 50)
        self.velocity_value_label = QLabel(f"{velocity_slider.value()}")
        position_slider = self.create_slider(0, 360, 50)
        self.position_value_label = QLabel(f"{position_slider.value()}")
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
        velocity_slider_layout.addWidget(velocity_slider)
        velocity_slider_layout.addWidget(self.velocity_value_label)
        velocity_layout.addLayout(velocity_slider_layout)

        # Position slider with label
        position_layout = QVBoxLayout()
        position_layout.addWidget(QLabel("Desired Angle (0-360°):"))
        position_slider_layout = QHBoxLayout()
        position_slider_layout.addWidget(position_slider)
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
        velocity_slider.valueChanged.connect(lambda: self.velocity_value_label.setText(f"{velocity_slider.value()}"))
        position_slider.valueChanged.connect(lambda: self.position_value_label.setText(f"{position_slider.value()}"))

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
        #velocity = self.velocity_slider.value()
        #target_position = self.position_slider.value() * 10
        #repetitions = self.repetition_spinbox.value()
        max_acceleration = 40 
        prof_acceleration = 40  
        max_deceleration = 40 
        prof_deceleration = 40 
        prof_velocity = 100
        end_velocity = 0 
        home_position = 0  # Pocatecni pozice
        target_position1 = 3600  # Cílová pozice 1
        target_position2 = 0  # Cílová pozice 2 
        repetitions = 2 # number of repetition

        #self.toggle_inputs(False)
        self.status_label.setText("Processing... Please wait.")
        QTimer.singleShot(100, lambda: self.motor_controller.set_motion_parameters(max_acceleration, prof_acceleration, max_deceleration, prof_deceleration,
                               prof_velocity, end_velocity))
        QTimer.singleShot(100, lambda: self.motor_controller.execute_motion(home_position, target_position1, target_position2, repetitions))

    def toggle_inputs(self, enabled):
        self.velocity_slider.setEnabled(enabled)
        self.position_slider.setEnabled(enabled)
        self.repetition_spinbox.setEnabled(enabled)
        self.start_button.setEnabled(enabled)
