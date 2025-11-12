from PyQt5.QtCore import QObject, pyqtSignal


class MotionWorker(QObject):
    finished = pyqtSignal()
    status_updated = pyqtSignal(str)

    def __init__(self, motor_controller, home_position, positions, delays, repetitions):
        super().__init__()
        self.motor_controller = motor_controller
        self.home_position = home_position
        self.positions = positions
        self.delays = delays
        self.repetitions = repetitions
        self.delay_sequence = list(delays or [])

    def run(self):
        try:
            self.status_updated.emit("Executing motion...")
            result = self.motor_controller.execute_motion(
                self.home_position, self.positions, self.delays, self.repetitions
            )
            if result == 0:
                self.status_updated.emit("Motion stopped by user.")
            else:
                self.status_updated.emit("Motion completed successfully.")
        except Exception as exc:
            self.status_updated.emit(f"Error during motion: {exc}")
        finally:
            self.finished.emit()
