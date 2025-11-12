from PyQt5 import QtWidgets, QtCore
from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QFormLayout, QDoubleSpinBox,
    QLabel, QPushButton, QGridLayout
)
import numpy as np
import pyqtgraph as pg

COUNTS_PER_REV = 3600.0  # 0.1°/count → 360°/rev → 3600 counts/rev

# ---- Trapezoid/Triangle motion profile solver (v rev, rev/s, rev/s²) ----
def solve_trapezoid(distance_rev, v_max_rps, a_up_rs2, a_down_rs2, dt=0.001):
    """
    distance_rev ... [rev]
    v_max_rps   ... [rev/s]
    a_up_rs2    ... [rev/s^2]
    a_down_rs2  ... [rev/s^2]
    Returns t, v(t) [rev/s], s(t) [rev], info dict
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
    """PyQt widget: preview rampy a zápis do PD1-C.
    GUI očekává:
      - Distance: counts (0.1°), 3600 = 1 rev
      - Max velocity: rpm
      - Accel/Decel: rpm/s
      - Target position: counts (0.1°)
    Náhled přepočítá na rev/rps/rs², grafy zobrazí v rpm a countech.
    """
    def __init__(self, motor_controller=None, parent=None):
        super().__init__(parent)
        self.motor_controller = motor_controller
        self._build_ui()
        self._wire_signals()
        self._recompute()

    # ----- UI -----
    def _build_ui(self):
        layout = QVBoxLayout(self)

        form = QFormLayout()
        # Distance in counts (0.1°)
        self.spin_distance = QDoubleSpinBox()
        self.spin_distance.setDecimals(3)
        self.spin_distance.setRange(0.0001, 1e9)
        self.spin_distance.setValue(3600.0)  # 1 rev
        self.spin_distance.setSuffix(' cnts (0.1°)')

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

        # Target position in counts (0.1°)
        self.spin_target = QDoubleSpinBox()
        self.spin_target.setDecimals(3)
        self.spin_target.setRange(-1e12, 1e12)
        self.spin_target.setValue(3600.0)
        self.spin_target.setSuffix(' cnts (0.1°)')

        form.addRow("Move distance:", self.spin_distance)
        form.addRow("Max velocity:", self.spin_vmax)
        form.addRow("Acceleration:", self.spin_acc)
        form.addRow("Deceleration:", self.spin_dec)
        form.addRow("Target position:", self.spin_target)
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

        self.plot_s = pg.PlotWidget(title="Position vs Time [counts]")
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
        for w in (self.spin_distance, self.spin_vmax, self.spin_acc, self.spin_dec):
            w.valueChanged.connect(self._recompute)
        self.btn_recompute.clicked.connect(self._recompute)
        self.btn_apply_params.clicked.connect(self._apply_to_drive)
        self.btn_move.clicked.connect(self._move_to_target)

    # ----- Helpers: GUI→solver převody -----
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
    def _recompute(self):
        # GUI (drive units): counts, rpm, rpm/s
        L_counts = self.spin_distance.value()
        v_rpm    = self.spin_vmax.value()
        a_up_rpms = self.spin_acc.value()
        a_dn_rpms = self.spin_dec.value()

        # To solver (rev, rps, rs²)
        L_rev   = self.counts_to_rev(L_counts)
        v_rps   = self.rpm_to_rps(v_rpm)
        a_up_rs2 = self.rpms_to_rs2(a_up_rpms)
        a_dn_rs2 = self.rpms_to_rs2(a_dn_rpms)

        t, v_rps_t, s_rev_t, info = solve_trapezoid(L_rev, v_rps, a_up_rs2, a_dn_rs2, dt=0.001)

        # For plots: rpm, counts
        v_rpm_t = self.rps_to_rpm(v_rps_t)
        s_counts_t = self.rev_to_counts(s_rev_t)

        self.curve_v.setData(t, v_rpm_t)
        self.curve_s.setData(t, s_counts_t)

        if info['type'] == 'invalid':
            self.lbl_summary.setText("Enter positive values.")
        else:
            v_peak_rpm = info['peak_v'] * 60.0
            extra = f"  cruise: {info['t_cruise']:.3f}s" if info['type'] == 'trapezoid' else ""
            self.lbl_summary.setText(
                f"Profile: {info['type']} | T = {info['T']:.3f}s | "
                f"t_acc = {info['t_acc']:.3f}s | t_dec = {info['t_dec']:.3f}s{extra} | "
                f"v_peak ≈ {v_peak_rpm:.3f} rpm"
            )

    def _apply_to_drive(self):
        if self.motor_controller is None:
            return
        # Zapisujeme v jednotkách driveru (rpm, rpm/s, counts)
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
        if self.motor_controller is None:
            return
        try:
            pos_counts = int(round(self.spin_target.value()))  # 0.1°/LSB
            self.motor_controller.set_profile_position_mode()
            self.motor_controller.move_to_position(pos_counts)
        except Exception as e:
            QtWidgets.QMessageBox.critical(self, "Move failed", str(e))