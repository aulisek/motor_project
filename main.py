# -*- coding: utf-8 -*-
# Author: Vladislav Aulich

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
