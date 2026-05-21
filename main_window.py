from PyQt5.QtCore import QThread
from PyQt5.QtWidgets import QMainWindow, QTabWidget, QMessageBox
import logging

logger = logging.getLogger(__name__)

from core.motion_worker import MotionWorker
from core.plot_manager import PlotManager
from tabs.ramp_preview import RampPreviewWidget
from tabs.plot_tab import PlotTab
from tabs.analysis_tab import AnalysisTab
import core.constants as const


class MainWindow(QMainWindow):
    """
    Top-level window that wires together the modular tab widgets.
    Acts as the central orchestrator routing signals between the 
    UI components (PlotTab, RampPreviewWidget) and the backend 
    controllers (PlotManager, MotorController, MotionWorker).
    """

    def __init__(self, motor_controller):
        """Initializes the main window and underlying managers."""
        super().__init__()
        self.motor_controller = motor_controller
        self.plot_manager = PlotManager(self.motor_controller)
        self.motion_thread = None
        self.motion_worker = None

        self._init_ui()
        self._wire_signals()
        self.update_com_ports()

    def _init_ui(self) -> None:
        """Configures the main layout, window properties, and tab widgets."""
        self.setWindowTitle("Motor Controller GUI")
        self.setGeometry(100, 100, 500, 300)
        self.showMaximized()

        self.tab_widget = QTabWidget()

        self.plot_tab = PlotTab(self.plot_manager)
        self.ramp_preview_tab = RampPreviewWidget(self.motor_controller)
        self.analysis_tab = AnalysisTab()

        self.tab_widget.addTab(self.plot_tab, "Data plots")
        self.tab_widget.addTab(self.ramp_preview_tab, "Ramp Preview")
        self.tab_widget.addTab(self.analysis_tab, "Data Analysis")

        self.setCentralWidget(self.tab_widget)
        self.plot_tab.set_motor_initialized(self.motor_controller.is_initialized())

    def _wire_signals(self) -> None:
        """Connects PyQt signals from the UI tabs to their respective backend slots."""
        self.plot_tab.start_motion_requested.connect(self.start_motion)
        self.plot_tab.stop_motion_requested.connect(self.stop_motion)
        self.plot_tab.go_home_requested.connect(self.motor_controller.go_to_home_position)
        self.plot_tab.set_home_requested.connect(self._handle_set_home)
        self.plot_tab.daq_rate_changed.connect(self.plot_manager.set_daq_sample_rate)
        self.plot_tab.positions_changed.connect(self.ramp_preview_tab.set_motion_positions)
        self.plot_tab.refresh_ports_requested.connect(self.update_com_ports)
        self.plot_tab.reference_resistance_changed.connect(self.plot_manager.set_reference_resistance)  # Connect the new signal
        self.plot_tab.resistor_position_changed.connect(self.plot_manager.set_resistor_position)
        self.plot_tab.connect_port_requested.connect(self.select_com_port)
        self.plot_tab.emit_current_daq_rate()
        self.plot_tab.emit_current_positions()
        self.plot_tab.emit_current_reference_resistance()
        self.plot_tab.emit_current_resistor_position()

    def _get_ramp_preview_motion_params(self):
        """
        Retrieves the acceleration, deceleration, and velocity parameters 
        currently set in the Ramp Preview tab.
        
        Returns:
            dict or None: A dictionary containing 'acc', 'dec', and 'vel', or None if invalid.
        """
        widget = getattr(self, "ramp_preview_tab", None)
        if widget is None:
            return None

        acc_value = getattr(widget, "spin_acc", None)
        dec_value = getattr(widget, "spin_dec", None)
        vel_value = getattr(widget, "spin_vmax", None)
        if acc_value is None or dec_value is None or vel_value is None:
            return None

        try:
            acc = int(round(acc_value.value()))
            dec = int(round(dec_value.value()))
            vel = int(round(vel_value.value()))
        except Exception:
            return None

        return {"acc": acc, "dec": dec, "vel": vel}

    def _collect_experiment_metadata(
        self,
        plan,
        max_acceleration,
        prof_acceleration,
        max_deceleration,
        prof_deceleration,
        prof_velocity,
        reference_resistance,
        loop_mode,
        resistor_position,
    ):
        """Aggregates all experiment parameters to be saved in the CSV log header."""
        positions_summary = []
        for idx, count in enumerate(plan.positions):
            delay = plan.delays[idx] if idx < len(plan.delays) else 0
            degrees = round((const.DEFAULT_HOME_POSITION - count) / 10.0, 2)
            positions_summary.append(
                {"index": idx + 1, "counts": count, "degrees": degrees, "delay_ms": delay}
            )

        return {
            "experiment_name": self.plot_tab.experiment_name(),
            "experiment_description": self.plot_tab.experiment_description(),
            "daq_rate_key": self.plot_tab.current_daq_rate_key(),
            "daq_rate_label": self.plot_tab.current_daq_rate_label(),
            "repetitions": plan.repetitions,
            "positions": positions_summary,
            "acceleration": {"max_acc": max_acceleration, "profile_acc": prof_acceleration},
            "deceleration": {"max_dec": max_deceleration, "profile_dec": prof_deceleration},
            "velocity": prof_velocity,
            "reference_resistance": reference_resistance,
            "loop_mode": loop_mode,
            "resistor_position": resistor_position,
        }

    def start_motion(self):
        """
        Prepares and starts the motor motion sequence in a background thread.
        Also handles configuring the DAQ logging session with the correct metadata.
        """
        try:
            plan = self.plot_tab.build_motion_plan()
        except ValueError as exc:
            self.plot_tab.set_status(str(exc))
            return

        preview_params = self._get_ramp_preview_motion_params()
        if preview_params:
            max_acceleration = preview_params["acc"]
            prof_acceleration = preview_params["acc"]
            max_deceleration = preview_params["dec"]
            prof_deceleration = preview_params["dec"]
            prof_velocity = preview_params["vel"]
        else:
            max_acceleration = const.DEFAULT_KINEMATICS_VALUE
            prof_acceleration = const.DEFAULT_KINEMATICS_VALUE
            max_deceleration = const.DEFAULT_KINEMATICS_VALUE
            prof_deceleration = const.DEFAULT_KINEMATICS_VALUE
            prof_velocity = const.DEFAULT_KINEMATICS_VALUE

        end_velocity = 0
        home_position = const.DEFAULT_HOME_POSITION

        reference_resistance = self.plot_tab.reference_resistance_ohms()
        resistor_position = self.plot_tab.current_resistor_position()
        loop_mode = self.plot_tab.get_loop_mode()
        use_closed_loop = (loop_mode == "Closed Loop")
        self.motor_controller.set_closed_loop(use_closed_loop)

        experiment_metadata = self._collect_experiment_metadata(
            plan,
            max_acceleration,
            prof_acceleration,
            max_deceleration,
            prof_deceleration,
            prof_velocity,
            reference_resistance,
            loop_mode,
            resistor_position,
        )

        self._set_motion_ui_enabled(False)
        self.plot_tab.set_status("Preparing motion...")
        # Always stop any existing DAQ session so each motion gets a fresh log
        self.plot_manager.stop_acquisition()
        self.plot_manager.set_reference_resistance(reference_resistance)
        self.plot_manager.set_resistor_position(resistor_position)
        self.plot_manager.set_experiment_metadata(experiment_metadata)
        self.plot_manager.set_current_cycle(1)
        self.plot_manager.reset_plot_data()
        # Ensure DAQ logging is running whenever we kick off a motion sequence
        self.plot_manager.start_acquisition()

        self.motor_controller.set_motion_parameters(
            max_acceleration,
            prof_acceleration,
            max_deceleration,
            prof_deceleration,
            prof_velocity,
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
        self.motion_worker.status_updated.connect(self.plot_tab.set_status)
        self.motion_worker.finished.connect(self._handle_motion_finished)
        self.motion_worker.cycle_completed.connect(self._handle_cycle_progress)

        self.motion_thread.start()
        cycle_time = self.ramp_preview_tab.get_cycle_time()
        if cycle_time > 0:
            self.plot_tab.start_progress_tracking(cycle_time, plan.repetitions)
        else:
            self.plot_tab.stop_progress_tracking()

    def _set_motion_ui_enabled(self, enabled: bool) -> None:
        """Enables or disables UI elements during active motion."""
        self.plot_tab.set_motion_ui_enabled(enabled)

    def stop_motion(self):
        """Sends an abort signal to the motor controller and halts DAQ logging."""
        self.plot_tab.set_status("Stop requested...")
        self.motor_controller.stop_movement()
        self.plot_tab.stop_progress_tracking()
        # If user manually stops motion, shut down DAQ immediately
        self.plot_manager.stop_acquisition()

    def _handle_set_home(self):
        """Handles the request to save the current physical position as 0 degrees."""
        try:
            self.motor_controller.set_current_position_as_home()
            QMessageBox.information(self, "Success", "Current position set and saved as Home (0°).")
        except Exception as exc:
            QMessageBox.critical(self, "Error", f"Failed to set home: {exc}")

    def _handle_motion_finished(self):
        """Cleans up the UI state and DAQ logging once the motion sequence ends."""
        self._set_motion_ui_enabled(True)
        self.plot_tab.stop_progress_tracking()
        # Stop DAQ logging after motion completes
        self.plot_manager.stop_acquisition()

    def _handle_cycle_progress(self, completed_cycles: int):
        """Updates the progress bar in the UI based on completed motion cycles."""
        self.plot_tab.set_progress_cycles(completed_cycles)
        self.plot_manager.set_current_cycle(completed_cycles + 1)

    def update_com_ports(self):
        """Polls the Nanolib wrapper for available hardware COM ports."""
        try:
            bus_hw, hardware_items = self.motor_controller.select_bus_hardware()
            logger.info(f"Bus hardware IDs: {bus_hw}")
            logger.info(f"Hardware items: {hardware_items}")
            self.plot_tab.set_com_ports(hardware_items)
        except Exception as exc:
            logger.error(f"Error updating COM ports: {exc}")
            self.plot_tab.set_com_ports([])

    def select_com_port(self, selected_index: int):
        """Attempts to initialize the motor on the selected hardware index."""
        try:
            if selected_index is None or selected_index < 0:
                raise Exception("No hardware selected.")
            self.motor_controller.initialize_motor(selected_index)
            QMessageBox.information(self, "Success", "Motor initialized successfully!")
            self.plot_tab.set_motor_initialized(True)
            self.plot_manager.start_monitoring()
        except Exception as exc:
            QMessageBox.critical(self, "Error", str(exc))
            self.plot_tab.set_motor_initialized(self.motor_controller.is_initialized())

    def closeEvent(self, event):
        """Ensures hardware and DAQ threads are cleanly shut down upon exiting the application."""
        self.plot_manager.shutdown()
        super().closeEvent(event)
