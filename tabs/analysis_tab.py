from PyQt5.QtWidgets import QWidget, QVBoxLayout, QPushButton, QLabel, QFileDialog


class AnalysisTab(QWidget):
    """
    Tab pro budoucí analýzu naměřených dat.
    Zatím obsahuje pouze prvek pro nahrání souboru.
    """
    def __init__(self, parent=None):
        super().__init__(parent)
        self._build_ui()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        
        self.load_button = QPushButton("Nahrát soubor k analýze...")
        self.load_button.clicked.connect(self._load_file)
        layout.addWidget(self.load_button)

        self.placeholder_label = QLabel("Zde se v budoucnu zobrazí analýza a grafy...")
        self.placeholder_label.setStyleSheet("color: gray; font-style: italic;")
        layout.addWidget(self.placeholder_label)

        layout.addStretch()

    def _load_file(self):
        filename, _ = QFileDialog.getOpenFileName(self, "Vybrat CSV soubor", "", "CSV Files (*.csv);;All Files (*)")
        if filename:
            self.placeholder_label.setText(f"Vybrán soubor:\n{filename}\n\n(Zde proběhne analýza)")