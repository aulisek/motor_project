# -*- coding: utf-8 -*-
# Author: Vladislav Aulich

"""
Entry point for the Motor Controller GUI application.
Initializes the motor controller, main window, and starts the PyQt5 event loop.
"""

import sys
from PyQt5.QtWidgets import QApplication
from motor_controller import MotorController
from main_window import MainWindow

if __name__ == '__main__':
    motor_controller = MotorController()
    app = QApplication(sys.argv)
    window = MainWindow(motor_controller)
    window.show()
    sys.exit(app.exec_())