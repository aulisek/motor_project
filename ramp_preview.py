"""
Module containing a widget for a graphical preview of acceleration and motion ramps (RampPreviewWidget).
Generates a simplified kinematic model (trapezoidal/triangular) and sends
these acceleration settings back to the controller.
"""
from PyQt5 import QtWidgets, QtCore
from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QFormLayout, QDoubleSpinBox,
    QLabel, QPushButton, QGridLayout
)
import numpy as np
import pyqtgraph as pg
import core.constants as const

COUNTS_PER_REV = const.COUNTS_PER_REV

# ---- Trapezoid/Triangle motion profile solver (v rev, rev/s, rev/s²) ----
def solve_trapezoid(distance_rev, v_max_rps, a_up_rs2, a_down_rs2, dt=0.001):
    """
    Calculates the velocity and position profile over time using a trapezoidal
    or triangular (if max velocity is not reached) profile.

    Args:
        distance_rev (float): Target distance to travel in revolutions.
        v_max_rps (float): Maximum allowed velocity in rev/s.
        a_up_rs2 (float): Acceleration in rev/s^2.
        a_down_rs2 (float): Deceleration in rev/s^2.
        dt (float): Time step for discretization.

    Returns:
        tuple: (time axis t, velocity axis v(t), position axis s(t), info_dict)
    """
    L = float(distance_rev)
    v  = float(v_max_rps)
    au = float(a_up_rs2)
    ad = float(a_down_rs2)

    if L <= 0 or v <= 0 or au <= 0 or ad <= 0:
        return np.array([0.0]), np.array([0.0]), np.array([0.0]), {
            'type': 'invalid', 'T': 0.0, 't_acc': 0.0, 't_cruise': 0.0, 't_dec': 0.0, 'peak_v': 0.0
        }

    t_acc = v / au
    t_dec = v / ad
    s_acc = 0.5 * au * t_acc**2
    s_dec = 0.5 * v * t_dec  # = 0.5 * ad * t_dec**2

    s_cruise = L - (s_acc + s_dec)

    if s_cruise >= 0:
        # Trapezoid
        t_cruise = s_cruise / v
        T = t_acc + t_cruise + t_dec
        t = np.arange(0.0, T + dt, dt)
        v_t = np.zeros_like(t)
        s_t = np.zeros_like(t)
        for i, ti in enumerate(t):
            if ti <= t_acc:
                v_t[i] = au * ti
                s_t[i] = 0.5 * au * ti**2
            elif ti <= t_acc + t_cruise:
                v_t[i] = v
                tc = ti - t_acc
                s_t[i] = s_acc + v * tc
            else:
                td = ti - (t_acc + t_cruise)
                v_t[i] = max(v - ad * td, 0.0)
                s_t[i] = s_acc + s_cruise + (v * td - 0.5 * ad * td**2)
        info = dict(type='trapezoid', t_acc=t_acc, t_cruise=t_cruise, t_dec=t_dec, T=T, peak_v=v)
    else:
        # Triangle
        v_p = np.sqrt(2 * L * au * ad / (au + ad))
        t_acc = v_p / au
        t_dec = v_p / ad
        T = t_acc + t_dec
        t = np.arange(0.0, T + dt, dt)
        v_t = np.zeros_like(t)
        s_t = np.zeros_like(t)
        for i, ti in enumerate(t):
            if ti <= t_acc:
                v_t[i] = au * ti
                s_t[i] = 0.5 * au * ti**2
            else:
                td = ti - t_acc
                v_t[i] = max(v_p - ad * td, 0.0)
                s_t[i] = (0.5 * au * t_acc**2) + (v_p * td - 0.5 * ad * td**2)
        info = dict(type='triangle', t_acc=t_acc, t_cruise=0.0, t_dec=t_dec, T=T, peak_v=v_p)

    return t, v_t, s_t, info


class RampPreviewWidget(QWidget):
    """
    PyQt widget: Provides a graphical preview of the path and velocity and allows
    applying settings directly to the motor controller.
    
    Conversion logic:
      - Motion path: provided from the Plot tab as counts (0.1°)
      - Max velocity: rpm
      - Accel/Decel: rpm/s
    Internal preview recalculates profile to rev/rps/rs², plots are drawn in rpm and degrees.
    """
    def __init__(self, motor_controller=None, parent=None):
        super().__init__(parent)
        self.motor_controller = motor_controller
        self.home_position_counts = float(const.DEFAULT_HOME_POSITION)
        self.home_position_deg = 0.0
        self.motion_positions_counts = []
        self.motion_positions_deg = []
        self.motion_delays_ms = []
        self.last_cycle_time_s = 0.0
        self._build_ui()
        self._wire_signals()
        self._recompute()

    # ----- UI -----
    def _build_ui(self):
        """Builds the forms and plots of the widget."""
        layout = QVBoxLayout(self)

        form = QFormLayout()
        # Velocity in rpm
        self.spin_vmax = QDoubleSpinBox()
        self.spin_vmax.setDecimals(3)
        self.spin_vmax.setRange(0.0001, 1e9)
        self.spin_vmax.setValue(60.0)  # 1 rps
        self.spin_vmax.setSuffix(' rpm')

        # Acc/Dec in rpm/s
        self.spin_acc = QDoubleSpinBox()
        self.spin_acc.setDecimals(3)
        self.spin_acc.setRange(0.0001, 1e9)
        self.spin_acc.setValue(120.0)
        self.spin_acc.setSuffix(' rpm/s')

        self.spin_dec = QDoubleSpinBox()
        self.spin_dec.setDecimals(3)
        self.spin_dec.setRange(0.0001, 1e9)
        self.spin_dec.setValue(120.0)
        self.spin_dec.setSuffix(' rpm/s')

        form.addRow("Max velocity:", self.spin_vmax)
        form.addRow("Acceleration:", self.spin_acc)
        form.addRow("Deceleration:", self.spin_dec)
        layout.addLayout(form)

        # Summary
        self.lbl_summary = QLabel("–")
        self.lbl_summary.setWordWrap(True)
        layout.addWidget(self.lbl_summary)

        # Plots
        plots = QGridLayout()
        self.plot_v = pg.PlotWidget(title="Velocity vs Time [rpm]")
        self.plot_v.showGrid(x=True, y=True)
        self.curve_v = self.plot_v.plot([], [])

        self.plot_s = pg.PlotWidget(title="Position vs Time [deg]")
        self.plot_s.showGrid(x=True, y=True)
        self.curve_s = self.plot_s.plot([], [])

        plots.addWidget(self.plot_v, 0, 0)
        plots.addWidget(self.plot_s, 0, 1)
        layout.addLayout(plots)

        # Buttons
        btn_row = QHBoxLayout()
        self.btn_recompute = QPushButton("Preview")
        self.btn_apply_params = QPushButton("Apply parameters → Drive")
        self.btn_move = QPushButton("Move to target")
        btn_row.addWidget(self.btn_recompute)
        btn_row.addStretch(1)
        btn_row.addWidget(self.btn_apply_params)
        btn_row.addWidget(self.btn_move)
        layout.addLayout(btn_row)

        if self.motor_controller is None:
            self.btn_apply_params.setEnabled(False)
            self.btn_move.setEnabled(False)

    def _wire_signals(self):
        """Connects click signals and value changes to methods for path recalculation."""
        for w in (self.spin_vmax, self.spin_acc, self.spin_dec):
            w.valueChanged.connect(self._recompute)
        self.btn_recompute.clicked.connect(self._recompute)
        self.btn_apply_params.clicked.connect(self._apply_to_drive)
        self.btn_move.clicked.connect(self._move_to_target)

    # ----- Helpers: GUI→solver conversions -----
    @staticmethod
    def counts_to_rev(counts: float) -> float:
        return counts / COUNTS_PER_REV

    @staticmethod
    def rpm_to_rps(rpm: float) -> float:
        return rpm / 60.0

    @staticmethod
    def rpms_to_rs2(rpm_per_s: float) -> float:
        return rpm_per_s / 60.0

    @staticmethod
    def rps_to_rpm(rps: np.ndarray) -> np.ndarray:
        return rps * 60.0

    @staticmethod
    def rev_to_counts(rev: np.ndarray) -> np.ndarray:
        return rev * COUNTS_PER_REV

    # ----- Logic -----
    def set_motion_positions(self, positions_counts, positions_degrees, delays_ms):
        """Accepts waypoints from the Plot Tab for modeling in the preview."""
        self.motion_positions_counts = list(positions_counts or [])
        self.motion_positions_deg = list(positions_degrees or [])
        self.motion_delays_ms = list(delays_ms or [])
        self._recompute()

    def _recompute(self):
        """Recalculates the path, kinematics of individual route points and redraws plots."""
        v_rpm = self.spin_vmax.value()
        a_up_rpms = self.spin_acc.value()
        a_dn_rpms = self.spin_dec.value()

        v_rps = self.rpm_to_rps(v_rpm)
        a_up_rs2 = self.rpms_to_rs2(a_up_rpms)
        a_dn_rs2 = self.rpms_to_rs2(a_dn_rpms)

        path_counts = [self.home_position_counts] + self.motion_positions_counts
        path_degrees = [self.home_position_deg] + self.motion_positions_deg
        delays_ms = list(self.motion_delays_ms or [])
        if len(delays_ms) < len(self.motion_positions_counts):
            delays_ms.extend([0] * (len(self.motion_positions_counts) - len(delays_ms)))
        if len(path_counts) < 2:
            self.curve_v.setData([], [])
            self.curve_s.setData([], [])
            self.lbl_summary.setText("Add at least one position in the Data plots tab to preview the ramp.")
            self.last_cycle_time_s = 0.0
            return

        time_segments = []
        velocity_segments = []
        position_segments_deg = []
        total_time = 0.0
        total_distance_deg = 0.0
        segment_count = 0
        current_start_counts = path_counts[0]
        current_start_deg = path_degrees[0]

        total_dwell = 0.0

        for idx, (target_counts, target_deg) in enumerate(zip(path_counts[1:], path_degrees[1:])):
            segment_delay_ms = delays_ms[idx] if idx < len(delays_ms) else 0
            dist_counts = abs(target_counts - current_start_counts)
            if dist_counts <= 0:
                current_start_counts = target_counts
                current_start_deg = target_deg
                if segment_delay_ms > 0:
                    dwell = segment_delay_ms / 1000.0
                    t_hold = np.array([total_time, total_time + dwell])
                    v_hold = np.zeros_like(t_hold)
                    s_hold = np.array([current_start_deg, current_start_deg])
                    time_segments.append(t_hold)
                    velocity_segments.append(v_hold)
                    position_segments_deg.append(s_hold)
                    total_time += dwell
                    total_dwell += dwell
                continue

            L_rev = self.counts_to_rev(dist_counts)
            t_seg, v_rps_seg, s_rev_seg, info = solve_trapezoid(L_rev, v_rps, a_up_rs2, a_dn_rs2, dt=0.001)
            if info['type'] == 'invalid':
                current_start_counts = target_counts
                current_start_deg = target_deg
                continue

            direction = 1 if target_counts >= current_start_counts else -1
            v_rpm_seg = self.rps_to_rpm(v_rps_seg)
            s_counts_seg = current_start_counts + direction * self.rev_to_counts(s_rev_seg)
            s_deg_seg = self.counts_to_degrees_array(s_counts_seg)

            time_segments.append(t_seg + total_time)
            velocity_segments.append(v_rpm_seg)
            position_segments_deg.append(s_deg_seg)

            total_time += info['T']
            total_distance_deg += abs(target_deg - current_start_deg)
            segment_count += 1
            current_start_counts = target_counts
            current_start_deg = target_deg

            if segment_delay_ms > 0:
                dwell = segment_delay_ms / 1000.0
                t_hold = np.array([total_time, total_time + dwell])
                v_hold = np.zeros_like(t_hold)
                s_hold = np.array([current_start_deg, current_start_deg])
                time_segments.append(t_hold)
                velocity_segments.append(v_hold)
                position_segments_deg.append(s_hold)
                total_time += dwell
                total_dwell += dwell

        if not time_segments:
            self.curve_v.setData([], [])
            self.curve_s.setData([], [])
            self.lbl_summary.setText("No movement distance detected in selected positions.")
            self.last_cycle_time_s = 0.0
            return

        t_plot = np.concatenate(time_segments)
        v_plot = np.concatenate(velocity_segments)
        s_plot = np.concatenate(position_segments_deg)

        self.curve_v.setData(t_plot, v_plot)
        self.curve_s.setData(t_plot, s_plot)

        summary = (
            f"Segments: {segment_count} | Total time ≈ {total_time:.3f}s | "
            f"Distance ≈ {total_distance_deg:.1f}°"
        )
        if total_dwell > 0:
            summary += f" | Dwell ≈ {total_dwell:.3f}s"
        self.lbl_summary.setText(summary)
        self.last_cycle_time_s = total_time

    def _apply_to_drive(self):
        """Writes currently set kinematic ramp values to the motor controller."""
        if self.motor_controller is None:
            return
        # Writing in driver units (rpm, rpm/s, counts)
        v_rpm = int(round(self.spin_vmax.value()))
        a_up  = int(round(self.spin_acc.value()))
        a_dn  = int(round(self.spin_dec.value()))
        try:
            self.motor_controller.set_motion_parameters(
                max_acceleration=a_up,
                prof_acceleration=a_up,
                max_deceleration=a_dn,
                prof_deceleration=a_dn,
                prof_velocity=v_rpm,
                end_velocity=0,
            )
        except Exception as e:
            QtWidgets.QMessageBox.critical(self, "Apply failed", str(e))
            return
        QtWidgets.QMessageBox.information(
            self, "Parameters applied",
            "Parameters written to drive (0x60C5/0x6083/0x60C6/0x6084/0x6081/0x6082)."
        )

    def _move_to_target(self):
        """Sends a command to the motor to move to the first target position defined in plot_tab."""
        if self.motor_controller is None:
            return
        try:
            if not self.motion_positions_counts:
                raise ValueError("No positions defined in the Plot tab.")
            pos_counts = int(round(self.motion_positions_counts[0]))
            self.motor_controller.set_profile_position_mode()
            self.motor_controller.move_to_position(pos_counts)
        except Exception as e:
            QtWidgets.QMessageBox.critical(self, "Move failed", str(e))

    @staticmethod
    def counts_to_degrees(counts: float) -> float:
        degrees = (COUNTS_PER_REV - counts) / 10.0
        return max(0.0, min(360.0, degrees))

    @staticmethod
    def counts_to_degrees_array(counts_array: np.ndarray) -> np.ndarray:
        degrees = (COUNTS_PER_REV - counts_array) / 10.0
        return np.clip(degrees, 0.0, 360.0)

    @staticmethod
    def degrees_to_counts(degrees: float) -> float:
        return COUNTS_PER_REV - (degrees * 10.0)

    def get_cycle_time(self) -> float:
        return max(0.0, float(self.last_cycle_time_s))
