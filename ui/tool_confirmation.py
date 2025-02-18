from PyQt5.QtWidgets import QApplication, QMessageBox, QTextEdit, QSizePolicy, QVBoxLayout, QWidget, QLabel, QDialogButtonBox, QDialog, QFrame
from PyQt5.QtCore import Qt
from typing import Dict, Any, Tuple
from ai.tools import Tool
import json
import codecs
import sys

def format_argument_value(param_type: str, value: Any) -> str:
    """
    Format an argument value based on its parameter type.
    
    Args:
        param_type: The type of the parameter ('string', 'integer', etc.)
        value: The value to format
    
    Returns:
        Formatted value as string
    """
    if value is None:
        return "None"
    
    if param_type == "string" and isinstance(value, str):
        try:
            # First try to encode the string as raw string to handle escapes
            raw_str = str(value).encode('raw_unicode_escape')
            # Then decode it back to handle the escapes
            return raw_str.decode('unicode_escape')
        except Exception:
            # If decoding fails, return the original string
            return value
    return str(value)

def create_argument_widget(name: str, value: Any, param_type: str, description: str) -> QFrame:
    """
    Create a framed widget for displaying a single argument.
    
    Args:
        name: Argument name
        value: Argument value
        param_type: Parameter type
        description: Parameter description
    
    Returns:
        QFrame containing the argument display
    """
    frame = QFrame()
    frame.setFrameStyle(QFrame.Panel | QFrame.Raised)
    frame.setLineWidth(1)
    frame.setMinimumWidth(600)  # Set minimum width for the frame
    
    layout = QVBoxLayout()
    
    # Create header with name and type
    header = QLabel(f"{name} ({param_type})")
    header.setStyleSheet("font-weight: bold;")
    layout.addWidget(header)
    
    # Add description
    if description:
        desc_label = QLabel(description)
        desc_label.setWordWrap(True)
        desc_label.setStyleSheet("color: gray; font-style: italic;")
        layout.addWidget(desc_label)
    
    # Add value text area
    value_text = QTextEdit()
    value_text.setPlainText(format_argument_value(param_type, value))
    value_text.setReadOnly(True)
    value_text.setMinimumWidth(580)  # Set minimum width for the text area
    
    # Adjust height based on content
    doc_height = value_text.document().size().height()
    value_text.setMinimumHeight(min(max(60, doc_height + 20), 200))
    
    layout.addWidget(value_text)
    frame.setLayout(layout)
    return frame

def confirm_tool_execution(tool: Tool, arguments: Dict[str, Any]) -> Tuple[bool, str]:
    """
    Show a Qt popup to confirm execution of an unsafe tool.
    
    Args:
        tool: The tool to be executed
        arguments: The arguments to be passed to the tool
    
    Returns:
        Tuple[bool, str]: (True if user confirms, False otherwise, Optional message to AI)
    """
    # Get the existing QApplication instance
    app = QApplication.instance()
    if app is None:
        app = QApplication(sys.argv)
    
    # Find the active window, which might be the PopupWindow
    parent = QApplication.activeWindow()
    if parent is None:
        # If no active window, try to get the PopupWindow instance if it exists
        try:
            from ui.popup_window import PopupWindow
            parent = PopupWindow.get_instance()
        except Exception:
            parent = None
    
    # Create custom dialog with proper parent
    dialog = QDialog(parent)
    dialog.setWindowTitle("Confirm Tool Execution")
    dialog.setWindowFlags(dialog.windowFlags() | Qt.WindowStaysOnTopHint)  # Make window stay on top
    dialog.setMinimumWidth(650)  # Set minimum width for the entire dialog
    
    # Create layout
    layout = QVBoxLayout()
    layout.setContentsMargins(20, 20, 20, 20)  # Add some padding around the edges
    
    # Add warning icon and main text
    main_text = QLabel(f"The AI wants to execute tool: {tool.name}\nDescription: {tool.description}")
    main_text.setWordWrap(True)
    # main_text.setStyleSheet("font-size: 12px;")
    layout.addWidget(main_text)
    
    # Add arguments section label
    args_label = QLabel("Arguments:")
    args_label.setStyleSheet("font-weight: bold; font-size: 14px;")
    layout.addWidget(args_label)
    
    # Add each argument in its own frame
    for arg_name, arg_value in arguments.items():
        param_info = tool.parameters.get(arg_name)
        if param_info:
            arg_widget = create_argument_widget(
                arg_name,
                arg_value,
                param_info.type,
                param_info.description
            )
            layout.addWidget(arg_widget)
    
    # Add message to AI field
    message_label = QLabel("Optional message to AI:")
    message_label.setStyleSheet("font-weight: bold; font-size: 14px;")
    layout.addWidget(message_label)
    
    message_text = QTextEdit()
    message_text.setPlaceholderText("Enter a message to send back to the AI (optional)")
    message_text.setMinimumHeight(100)
    message_text.setMinimumWidth(580)  # Set minimum width for the message text area
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