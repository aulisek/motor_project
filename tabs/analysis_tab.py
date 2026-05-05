from PyQt5.QtWidgets import QWidget, QVBoxLayout, QPushButton, QLabel, QFileDialog


class AnalysisTab(QWidget):
    """
    Tab for future analysis of measured data.
    Currently contains only a file load element.
    """
    def __init__(self, parent=None):
        super().__init__(parent)
        self._build_ui()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        
        self.load_button = QPushButton("Load file for analysis...")
        self.load_button.clicked.connect(self._load_file)
        layout.addWidget(self.load_button)

        self.placeholder_label = QLabel("Analysis and graphs will be displayed here in the future...")
        self.placeholder_label.setStyleSheet("color: gray; font-style: italic;")
        layout.addWidget(self.placeholder_label)

        layout.addStretch()

    def _load_file(self):
        filename, _ = QFileDialog.getOpenFileName(self, "Select CSV file", "", "CSV Files (*.csv);;All Files (*)")
        if filename:
            self.placeholder_label.setText(f"Selected file:\n{filename}\n\n(Analysis will take place here)")