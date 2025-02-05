from PyQt5.QtWidgets import QApplication, QMessageBox, QTextEdit, QSizePolicy, QVBoxLayout, QWidget, QLabel, QDialogButtonBox, QDialog
from PyQt5.QtCore import Qt
from typing import Dict, Any, Tuple
from ai.tools import Tool
import json

def confirm_tool_execution(tool: Tool, arguments: Dict[str, Any]) -> Tuple[bool, str]:
    """
    Show a Qt popup to confirm execution of an unsafe tool.
    
    Args:
        tool: The tool to be executed
        arguments: The arguments to be passed to the tool
    
    Returns:
        Tuple[bool, str]: (True if user confirms, False otherwise, Optional message to AI)
    """
    # Ensure we have a QApplication instance
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    
    # Create custom dialog
    dialog = QDialog()
    dialog.setWindowTitle("Confirm Tool Execution")
    # dialog.setWindowFlags(dialog.windowFlags() | Qt.WindowStaysOnTopHint)  # Make window stay on top
    
    # Create layout
    layout = QVBoxLayout()
    
    # Add warning icon and main text
    main_text = QLabel(f"The AI wants to execute tool: {tool.name}\nDescription: {tool.description}")
    layout.addWidget(main_text)
    
    # Add arguments text area
    args_label = QLabel("Arguments:")
    layout.addWidget(args_label)
    
    args_text = QTextEdit()
    args_text.setPlainText(json.dumps(arguments, indent=2))
    args_text.setReadOnly(True)
    args_text.setMinimumHeight(200)
    args_text.setMinimumWidth(400)
    layout.addWidget(args_text)
    
    # Add message to AI field
    message_label = QLabel("Optional message to AI:")
    layout.addWidget(message_label)
    
    message_text = QTextEdit()
    message_text.setPlaceholderText("Enter a message to send back to the AI (optional)")
    message_text.setMinimumHeight(100)
    layout.addWidget(message_text)
    
    # Add buttons
    button_box = QDialogButtonBox(QDialogButtonBox.Yes | QDialogButtonBox.No)
    button_box.accepted.connect(dialog.accept)
    button_box.rejected.connect(dialog.reject)
    layout.addWidget(button_box)
    
    dialog.setLayout(layout)
    
    # Play the system alert sound
    QApplication.beep()
    
    # Show dialog and get result
    dialog.raise_()  # Bring window to front
    dialog.activateWindow()  # Activate the window
    result = dialog.exec_()
    return (result == QDialog.Accepted, message_text.toPlainText().strip()) 