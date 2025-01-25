from PyQt5.QtWidgets import QApplication, QMessageBox, QTextEdit, QSizePolicy
from PyQt5.QtCore import Qt
from typing import Dict, Any
from ai.tools import Tool
import json

def confirm_tool_execution(tool: Tool, arguments: Dict[str, Any]) -> bool:
    """
    Show a Qt popup to confirm execution of an unsafe tool.
    
    Args:
        tool: The tool to be executed
        arguments: The arguments to be passed to the tool
    
    Returns:
        bool: True if user confirms, False otherwise
    """
    # Ensure we have a QApplication instance
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    
    # Create custom dialog with scrollable text area
    msg_box = QMessageBox()
    msg_box.setIcon(QMessageBox.Warning)
    msg_box.setWindowTitle("Confirm Tool Execution")
    
    # Create main text
    main_text = f"The AI wants to execute tool: {tool.name}\n"
    main_text += f"Description: {tool.description}"
    msg_box.setText(main_text)
    
    # Create scrollable detailed text for arguments
    msg_box.setDetailedText(json.dumps(arguments, indent=2))
    
    msg_box.setStandardButtons(QMessageBox.Yes | QMessageBox.No)
    msg_box.setDefaultButton(QMessageBox.No)  # Safer default
    
    # Find and modify the text edit widget
    textEdit = msg_box.findChild(QTextEdit)
    if textEdit is not None:
        # Set a larger fixed size for the text area
        textEdit.setMinimumHeight(300)
        textEdit.setMinimumWidth(400)
        # Make sure the text edit can expand
        textEdit.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOn)
        textEdit.setHorizontalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        # Ensure the widget can grow as needed
        textEdit.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
    
    return msg_box.exec_() == QMessageBox.Yes 