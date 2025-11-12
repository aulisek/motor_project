from PyQt5.QtCore import QThread
from PyQt5.QtWidgets import QMainWindow, QTabWidget, QMessageBox

from motion_worker import MotionWorker
from plot_manager import PlotManager
from ramp_preview import RampPreviewWidget
from tabs.basic_tab import BasicTab
from tabs.plot_tab import PlotTab
from tabs.expert_tab import ExpertTab


class MainWindow(QMainWindow):
    """Top-level window that wires together the modular tab widgets."""

    def __init__(self, motor_controller):
        super().__init__()
        self.motor_controller = motor_controller
        self.plot_manager = PlotManager(self.motor_controller)
        self.motion_thread = None
        self.motion_worker = None

        self._init_ui()
        self._wire_signals()
        self.update_com_ports()

    def _init_ui(self) -> None:
        self.setWindowTitle("Motor Controller GUI")
        self.setGeometry(100, 100, 500, 300)

        self.tab_widget = QTabWidget()

        self.basic_tab = BasicTab()
        self.plot_tab = PlotTab(self.plot_manager)
        self.expert_tab = ExpertTab()
        self.ramp_preview_tab = RampPreviewWidget(self.motor_controller)

        self.tab_widget.addTab(self.basic_tab, "Basic Options")
        self.tab_widget.addTab(self.plot_tab, "Data plots")
        self.tab_widget.addTab(self.expert_tab, "Expert Options")
        self.tab_widget.addTab(self.ramp_preview_tab, "Ramp Preview")

        self.setCentralWidget(self.tab_widget)

    def _wire_signals(self) -> None:
        self.plot_tab.start_motion_requested.connect(self.start_motion)
        self.plot_tab.stop_motion_requested.connect(self.stop_motion)
        self.plot_tab.set_home_requested.connect(self.motor_controller.set_home_position)

        self.expert_tab.refresh_ports_requested.connect(self.update_com_ports)
        self.expert_tab.connect_port_requested.connect(self.select_com_port)
        self.expert_tab.sampling_rate_changed.connect(self.plot_manager.set_save_rate)

    def _get_ramp_preview_motion_params(self):
        widget = getattr(self, "ramp_preview_tab", None)
        if widget is None:
            return None

        acc_value = getattr(widget, "spin_acc", None)
        dec_value = getattr(widget, "spin_dec", None)
        if acc_value is None or dec_value is None:
            return None

        try:
            acc = int(round(acc_value.value()))
            dec = int(round(dec_value.value()))
        except Exception:
            return None

        return {"acc": acc, "dec": dec}

    def start_motion(self):
        try:
            plan = self.basic_tab.build_motion_plan()
        except ValueError as exc:
            self.basic_tab.set_status(str(exc))
            return

        preview_params = self._get_ramp_preview_motion_params()
        if preview_params:
            max_acceleration = preview_params["acc"]
            prof_acceleration = preview_params["acc"]
            max_deceleration = preview_params["dec"]
            prof_deceleration = preview_params["dec"]
        else:
            max_acceleration = 300
            prof_acceleration = 300
            max_deceleration = 300
            prof_deceleration = 300

        end_velocity = 0
        home_position = 3600

        self._set_motion_ui_enabled(False)
        self.basic_tab.set_status("Preparing motion...")

        self.motor_controller.set_motion_parameters(
            max_acceleration,
            prof_acceleration,
            max_deceleration,
            prof_deceleration,
            plan.velocity,
            end_velocity,
        )

        self.motion_thread = QThread()
        self.motion_worker = MotionWorker(
            self.motor_controller,
            home_position,
            plan.positions,
            plan.delays,
            plan.repetitions,
        )
        self.motion_worker.moveToThread(self.motion_thread)

        self.motion_thread.started.connect(self.motion_worker.run)
        self.motion_worker.finished.connect(self.motion_thread.quit)
        self.motion_worker.finished.connect(self.motion_worker.deleteLater)
        self.motion_thread.finished.connect(self.motion_thread.deleteLater)
        self.motion_worker.status_updated.connect(self.basic_tab.set_status)
        self.motion_worker.finished.connect(lambda: self._set_motion_ui_enabled(True))

        self.motion_thread.start()

    def _set_motion_ui_enabled(self, enabled: bool) -> None:
        self.basic_tab.set_inputs_enabled(enabled)
        self.plot_tab.set_motion_controls_enabled(enabled)

    def stop_motion(self):
        self.basic_tab.set_status("Stop requested...")
        self.motor_controller.stop_movement()

    def update_com_ports(self):
        try:
            bus_hw, hardware_items = self.motor_controller.select_bus_hardware()
            print(f"Bus hardware IDs: {bus_hw}")
            print(f"Hardware items: {hardware_items}")
            self.expert_tab.set_com_ports(hardware_items)
        except Exception as exc:
            print(f"Error updating COM ports: {exc}")
            self.expert_tab.set_com_ports([])

    def select_com_port(self, selected_index: int):
        try:
            if selected_index is None or selected_index < 0:
                raise Exception("No hardware selected.")
            self.motor_controller.initialize_motor(selected_index)
            QMessageBox.information(self, "Success", "Motor initialized successfully!")
        except Exception as exc:
            QMessageBox.critical(self, "Error", str(exc))

    def closeEvent(self, event):
        self.plot_manager.stop_acquisition()
        super().closeEvent(event)
