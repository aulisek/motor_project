from PyQt5.QtCore import QObject, pyqtSignal


class MotionWorker(QObject):
    finished = pyqtSignal()
    status_updated = pyqtSignal(str)
    cycle_completed = pyqtSignal(int)

    def __init__(self, motor_controller, home_position, positions, delays, repetitions):
        super().__init__()
        self.motor_controller = motor_controller
        self.home_position = home_position
        self.positions = positions
        self.delays = delays
        self.repetitions = repetitions

    def run(self):
        try:
            self.status_updated.emit("Executing motion...")
            result = self.motor_controller.execute_motion(
                self.home_position,
                self.positions,
                self.delays,
                self.repetitions,
                progress_callback=self._cycle_progress_callback,
            )
            if result == 0:
                self.status_updated.emit("Motion stopped by user.")
            else:
                self.status_updated.emit("Motion completed successfully.")
        except Exception as exc:
            self.status_updated.emit(f"Error during motion: {exc}")
        finally:
            self.finished.emit()

    def _cycle_progress_callback(self, cycle_number: int):
        self.cycle_completed.emit(int(cycle_number))
