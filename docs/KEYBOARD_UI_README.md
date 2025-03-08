# Keyboard-First UI Documentation

## Overview

The Keyboard-First UI is designed to maximize productivity through efficient keyboard navigation and shortcuts. It allows users to perform common text processing actions rapidly without touching the mouse, while maintaining discoverability for new users.

## Key Features

### 1. Single-Key Shortcuts

The UI provides direct keyboard shortcuts for common actions:

| Key | Action | Description |
|-----|--------|-------------|
| `c` | Correction | Fix grammar and spelling issues |
| `i` | Improvement | Lightly improve text quality |
| `f` | Format | Format text as a conversation |
| `p` | Custom Prompt | Use a custom prompt |
| `h` | Toggle Hints | Show/hide keyboard shortcut hints |
| `Esc` | Exit/Close | Exit edit mode or close window |
| `Ctrl+Enter` | Copy & Close | Copy text and close window |

### 2. Type-Ahead Filtering

The prompt dropdown supports real-time filtering as you type:

- Start typing to filter the dropdown list
- Items matching your input will be shown
- Press Enter to select, Escape to reset filter
- Supports fuzzy matching for flexibility

### 3. Keyboard Navigation Flow

The UI is designed for natural keyboard navigation flow:

- Tab key moves focus logically between UI elements
- In Navigate mode, single-key shortcuts are active
- In Edit mode, normal text editing is active
- Escape key exits Edit mode back to Navigate mode
- Status bar shows current mode and available actions

### 4. Toggleable Shortcut Hints

For new users or as a reminder, keyboard shortcut hints can be toggled:

- Press `h` to show/hide shortcut indicators in UI
- When enabled, buttons show their shortcut keys: "Correction (c)"
- When disabled, a cleaner interface is shown: "Correction"
- Setting persists between sessions

## Usage Modes

### Navigate Mode

- Default mode for keyboard navigation
- Single-key shortcuts are active (c, i, f, p, h)
- Tab key navigates between UI elements
- Status bar indicates "Mode: Navigate"

### Edit Mode

- Active when editing text in input or prompt areas
- Normal text editing behavior (no single-key shortcuts)
- Escape key returns to Navigate mode
- Status bar indicates "Mode: Edit"

## Implementation Details

### Key Components

1. **FilterableComboBox**: Extends QComboBox with real-time filtering
2. **KeyboardFocusFrame**: Provides visual feedback for keyboard focus
3. **ActionButton**: Button with integrated shortcut hint display
4. **TextTab**: Main interface with keyboard navigation support
5. **PopupWindow**: Container with global keyboard event handling

### Keyboard Event Handling

The implementation carefully manages keyboard events:

```python
def keyPressEvent(self, event):
    key = event.key()
    
    # In Navigate mode, single-key shortcuts trigger actions
    if self.mode == "Navigate":
        key_text = chr(key).lower()
        if key_text in ACTIONS:
            self.process_key_action(key_text)
            return
            
    # Mode switching with Escape
    if key == Qt.Key_Escape:
        if self.mode == "Edit":
            self.enter_navigate_mode()
            return
        
    # Default handling
    super().keyPressEvent(event)
```

## Accessibility Considerations

- Visual focus indicators help users track current position
- Status bar provides contextual information
- Keyboard shortcuts can be displayed or hidden based on preference
- Tab navigation follows a logical flow
- Color contrast meets accessibility standards

## Developer Notes

When extending this UI:

1. Add new shortcuts to the ACTIONS dictionary
2. Implement corresponding action functions
3. Update the status bar messages for user feedback
4. Add appropriate focus handling for new UI elements
5. Test thoroughly with keyboard-only navigation

## Testing

A test script (`test_keyboard_ui.py`) is provided to verify keyboard functionality:

```python
python test_keyboard_ui.py
```

This will demonstrate the keyboard navigation, shortcuts, and filtering features.

## Future Enhancements

Planned improvements include:

- Custom user-defined shortcuts
- More advanced filtering options
- Additional keyboard navigation patterns
- Context-sensitive help system
- Enhanced accessibility features 