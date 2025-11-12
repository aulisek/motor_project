from dataclasses import dataclass
from typing import List, Tuple

from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QSlider,
    QSpinBox,
    QFormLayout,
)


@dataclass
class MotionPlan:
    velocity: int
    repetitions: int
    positions: List[int]
    delays: List[int]


class BasicTab(QWidget):
    """Collects simple motion profile inputs and dynamic position/delay pairs."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._build_ui()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)

        global_inputs_layout = QFormLayout()

        self.velocity_input = QSpinBox()
        self.velocity_input.setRange(1, 1000)
        self.velocity_input.setSuffix(" mm/s")
        global_inputs_layout.addRow("Velocity:", self.velocity_input)

        self.repetitions_input = QSpinBox()
        self.repetitions_input.setRange(1, 100)
        global_inputs_layout.addRow("Repetitions:", self.repetitions_input)

        layout.addLayout(global_inputs_layout)

        self.num_positions_label = QLabel("Number of Positions:")
        self.num_positions_spinbox = QSpinBox()
        self.num_positions_spinbox.setRange(1, 10)
        self.num_positions_spinbox.valueChanged.connect(self._create_position_inputs)

        layout.addWidget(self.num_positions_label)
        layout.addWidget(self.num_positions_spinbox)

        self.positions_container = QWidget()
        self.positions_layout = QVBoxLayout(self.positions_container)
        layout.addWidget(self.positions_container)

        self.status_label = QLabel("")
        layout.addWidget(self.status_label)

        self._create_position_inputs()

    def _create_position_inputs(self) -> None:
        """Rebuild the angle/delay inputs when the user changes the count."""
        while self.positions_layout.count():
            item = self.positions_layout.takeAt(0)
            widget = item.widget()
            if widget:
                widget.deleteLater()

        for index in range(self.num_positions_spinbox.value()):
            position_widget = QWidget()
            position_layout = QHBoxLayout(position_widget)

            label = QLabel(f"Position {index + 1}:")
            angle_slider = QSlider(Qt.Orientation.Horizontal)
            angle_slider.setRange(0, 360)
            angle_slider.setValue(0)

            angle_spinbox = QSpinBox()
            angle_spinbox.setRange(0, 360)
            angle_spinbox.setValue(0)

            angle_slider.valueChanged.connect(angle_spinbox.setValue)
            angle_spinbox.valueChanged.connect(angle_slider.setValue)

            delay_slider = QSlider(Qt.Orientation.Horizontal)
            delay_slider.setRange(0, 5000)
            delay_slider.setValue(500)

            delay_spinbox = QSpinBox()
            delay_spinbox.setRange(0, 5000)
            delay_spinbox.setValue(500)
            delay_spinbox.setSuffix(" ms")

            delay_slider.valueChanged.connect(delay_spinbox.setValue)
            delay_spinbox.valueChanged.connect(delay_slider.setValue)

            position_layout.addWidget(label)
            position_layout.addWidget(angle_slider)
            position_layout.addWidget(angle_spinbox)
            position_layout.addWidget(QLabel("Delay:"))
            position_layout.addWidget(delay_slider)
            position_layout.addWidget(delay_spinbox)

            self.positions_layout.addWidget(position_widget)

        self.positions_container.update()

    def build_motion_plan(self) -> MotionPlan:
        """Return the configured sequence as a MotionPlan instance."""
        positions, delays = self._extract_positions_and_delays()
        if not positions:
            raise ValueError("No positions defined!")

        return MotionPlan(
            velocity=self.velocity_input.value(),
            repetitions=self.repetitions_input.value(),
            positions=positions,
            delays=delays,
        )

    def _extract_positions_and_delays(self) -> Tuple[List[int], List[int]]:
        positions: List[int] = []
        delays: List[int] = []

        for index in range(self.positions_layout.count()):
            item = self.positions_layout.itemAt(index)
            widget = item.widget() if item else None
            if not widget:
                continue

            inputs = widget.findChildren(QSpinBox)
            if len(inputs) < 2:
                continue

            angle_spinbox, delay_spinbox = inputs[0], inputs[1]
            angle = angle_spinbox.value() * 10  # convert to 0.1° counts
            delay = delay_spinbox.value()

            positions.append(3600 - angle)
            delays.append(delay)

        return positions, delays

    def set_inputs_enabled(self, enabled: bool) -> None:
        """Enable or disable the input widgets as a group."""
        widgets = [
            self.velocity_input,
            self.repetitions_input,
            self.num_positions_spinbox,
        ]

        for widget in widgets:
            widget.setEnabled(enabled)

        for index in range(self.positions_layout.count()):
            item = self.positions_layout.itemAt(index)
            widget = item.widget() if item else None
            if widget:
                widget.setEnabled(enabled)

    def set_status(self, text: str) -> None:
        self.status_label.setText(text or "")
