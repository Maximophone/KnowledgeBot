"""
Minimal test script for the FilterableComboBox class
"""
import sys
from PyQt5.QtWidgets import QApplication, QMainWindow, QVBoxLayout, QWidget, QLabel
from ui.popup_window import FilterableComboBox

class TestWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("FilterableComboBox Test")
        self.setGeometry(100, 100, 400, 200)
        
        # Central widget
        central = QWidget()
        self.setCentralWidget(central)
        layout = QVBoxLayout(central)
        
        # Add label
        label = QLabel("Test the filterable dropdown below:")
        layout.addWidget(label)
        
        # Add the combobox
        self.combo = FilterableComboBox()
        self.combo.add_items(["apple", "banana", "cherry", "date", "elderberry", "fig", "grape"])
        layout.addWidget(self.combo)
        
        # Status label
        self.status = QLabel("Type to filter the dropdown items")
        layout.addWidget(self.status)
        
        # Connect signals
        self.combo.activated.connect(self.on_item_selected)
        
    def on_item_selected(self, index):
        """Handle item selection"""
        self.status.setText(f"Selected: {self.combo.currentText()}")

def main():
    """Run the test application"""
    print("Starting FilterableComboBox test")
    app = QApplication(sys.argv)
    
    window = TestWindow()
    window.show()
    print("Test window shown")
    
    sys.exit(app.exec_())

if __name__ == "__main__":
    main() 