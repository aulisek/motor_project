# -*- coding: utf-8 -*-
# Author: Vladislav Aulich

import sys
from PyQt5.QtWidgets import QApplication
from motor_controller import MotorController
from main_window import MainWindow
from data_controller import NIDevice

if __name__ == '__main__':
    motor_controller = MotorController()
    ni_device = NIDevice()
    app = QApplication(sys.argv)
    window = MainWindow(motor_controller, ni_device)
    window.show()
    sys.exit(app.exec_())