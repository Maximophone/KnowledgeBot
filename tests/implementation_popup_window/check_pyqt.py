"""
Check PyQt5 installation and version
"""
import sys
import PyQt5
from PyQt5.QtWidgets import QApplication
from PyQt5.QtCore import QT_VERSION_STR

print(f"Python version: {sys.version}")
print(f"PyQt5 version: {PyQt5.QtCore.PYQT_VERSION_STR}")
print(f"Qt version: {QT_VERSION_STR}")

# Test creating an application
app = QApplication(sys.argv)
print("QApplication created successfully")

# Exit cleanly
sys.exit(0) 