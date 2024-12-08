import pyqtgraph as pg
from pyqtgraph import PlotWidget

class NIDevice:
    def get_measurement(self):
        # Dummy function to simulate electrode data collection
        import random
        return random.uniform(0, 10)  # Example value