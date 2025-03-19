"""
Conversational Information Retriever Library

A lightweight Python module that manages asynchronous information retrieval conversations
between an AI assistant and users, handling prompt engineering, conversation state management,
and structured data extraction.
"""

import json
import uuid
import logging
import os
import shutil
import time
import pathlib
from datetime import datetime
from typing import Dict, List, Optional, Any, Union, Tuple, Set
import xml.etree.ElementTree as ET
from xml.dom import minidom

from ai import AI

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Current state version - increment when format changes
STATE_VERSION = "1.0"

class ConversationState:
    """Manages conversation history and state."""
    
    def __init__(self, task_id: str, information_need: str, output_schema: Union[Dict, str], context: Optional[str] = None):
        """Initialize a new conversation state.
        
        Args:
            task_id: Unique identifier for this conversation
            information_need: The question or information to obtain
            output_schema: Schema defining the expected JSON structure
            context: Additional context for the conversation
        """
        self.task_id = task_id
        self.information_need = information_need
        
        # Handle output_schema as either dict or string
        if isinstance(output_schema, dict):
            self.output_schema = json.dumps(output_schema, indent=2)
        else:
            self.output_schema = output_schema
            
        self.context = context or ""
        self.messages = []
        self.created_at = datetime.now()
        self.last_updated = self.created_at
        self.status = "in_progress"
        self.data = None
        self.error = None
    
    def add_message(self, sender: str, content: str) -> Dict:
        """
        Add a message to the conversation history with timestamp.
        
        Args:
            sender: 'user' or 'assistant'
            content: The message content
            
        Returns:
            The message object with timestamp
        """
        if sender not in ['user', 'assistant']:
            raise ValueError("Sender must be either 'user' or 'assistant'")
        
        message = {
            'sender': sender,
            'content': content,
            'timestamp': datetime.now()
        }
        
        self.messages.append(message)
        self.last_updated = message['timestamp']
        return message
    
    def get_history(self) -> List[Dict]:
        """
        Get the full conversation history.
        
        Returns:
            List of message objects with timestamps
        """
        return self.messages
    
    def get_formatted_history(self) -> str:
        """
        Format the conversation history as XML for the AI prompt.
        
        Returns:
            Formatted conversation history
        """
        if not self.messages:
            return ""
        
        history = []
        for msg in self.messages:
            sender = msg['sender']
            content = msg['content']
            
            if sender == 'assistant':
                history.append(f"<assistant>\n<user_message>{content}</user_message>\n</assistant>")
            else:
                history.append(f"<user>{content}</user>")
        
        return "\n".join(history)
    
    def get_formatted_prompt(self) -> str:
        """
        Generate the formatted prompt for the AI including conversation history.
        
        Returns:
            The formatted prompt
        """
        system_prompt_template = """
<agent_initialization>
  <role>Information Retrieval Assistant</role>
  <purpose>To collect specific information from users conversationally and return structured JSON data only upon completion</purpose>
  
  <input_structure>
    <system_query>
      <information_need>The specific question or information to obtain from the user</information_need>
      <context>Optional background information to frame the conversation</context>
      <output_schema>Required structure for returning information as JSON</output_schema>
    </system_query>
  </input_structure>

  <output_requirements>
    <!-- During information collection -->
    <incomplete>
      <user_message>Conversational text to the user</user_message>
    </incomplete>
    
    <!-- Only when collection is complete -->
    <complete>
      <user_message>Final confirmation message to the user</user_message>
      <system_message format="json">
        {{
          "collected_information": "JSON following output_schema",
          "status": "complete" / "incomplete",
          "error": null
        }}
      </system_message>
    </complete>
  </output_requirements>
</agent_initialization>

<critical_rules>
  <formatting>
    • ALWAYS wrap user-facing text in <user_message> tags
    • NEVER output raw text without proper XML tags
    • Only include system_message with JSON when ALL information is collected, or when you are facing a problem that seems unresolvable (uncooperative user, user unable to provide information, unresolvable lack of context...)
  </formatting>
  
  <example>
    <correct>
      <user_message>Hello! Could you tell me about your progress?</user_message>
    </correct>
    <incorrect>Hello! Could you tell me about your progress?</incorrect>
  </example>
  
  <workflow>
    1. Parse system query to understand information needs and output schema
    2. Engage user with questions to obtain required information
    3. Output ONLY <user_message> tags during information collection
    4. Once ALL information is collected, output both final <user_message> and JSON <system_message>
  </workflow>
</critical_rules>

<conversation_guidelines>
  <tone>Professional, friendly, and concise</tone>
  <persistence>Continue until all required information is obtained</persistence>
  <validation>Verify responses satisfy information requirements</validation>
</conversation_guidelines>

<!-- BEGINING -->

<system_query>
    <information_need>{information_need}</information_need>
    <context>{context}</context>
    <output_schema>
        {output_schema}
    </output_schema>
</system_query>

<!-- CONVERSATION HISTORY -->
{conversation_history}
"""
        
        formatted_prompt = system_prompt_template.format(
            information_need=self.information_need,
            context=self.context,
            output_schema=self.output_schema,
            conversation_history=self.get_formatted_history()
        )
        
        return formatted_prompt
    
    def set_complete(self, data: Optional[Dict] = None, error: Optional[str] = None) -> None:
        """
        Mark the conversation as complete.
        
        Args:
            data: The collected data
            error: Error message if completion failed
        """
        if data:
            self.status = "complete"
            self.data = data
        elif error:
            self.status = "error"
            self.error = error
        else:
            self.status = "incomplete"
        
        self.last_updated = datetime.now()
    
    def to_dict(self) -> Dict:
        """
        Convert the conversation state to a dictionary for serialization.
        
        Returns:
            Dictionary representation of the conversation state
        """
        # Convert datetime objects to ISO format strings
        serializable_messages = []
        for msg in self.messages:
            serializable_msg = msg.copy()
            serializable_msg['timestamp'] = msg['timestamp'].isoformat()
            serializable_messages.append(serializable_msg)
        
        return {
            'task_id': self.task_id,
            'information_need': self.information_need,
            'output_schema': self.output_schema,
            'context': self.context,
            'messages': serializable_messages,
            'created_at': self.created_at.isoformat(),
            'last_updated': self.last_updated.isoformat(),
            'status': self.status,
            'data': self.data,
            'error': self.error
        }
    
    @classmethod
    def from_dict(cls, data: Dict) -> 'ConversationState':
        """
        Create a ConversationState instance from a dictionary.
        
        Args:
            data: Dictionary representation of a conversation state
            
        Returns:
            A ConversationState instance
        """
        # Create a new instance
        state = cls(
            task_id=data['task_id'],
            information_need=data['information_need'],
            output_schema=data['output_schema'],
            context=data['context']
        )
        
        # Set the properties that were loaded from the dictionary
        state.status = data['status']
        state.data = data['data']
        state.error = data['error']
        state.created_at = datetime.fromisoformat(data['created_at'])
        state.last_updated = datetime.fromisoformat(data['last_updated'])
        
        # Convert message timestamps from ISO format strings to datetime objects
        state.messages = []
        for msg in data['messages']:
            serializable_msg = msg.copy()
            serializable_msg['timestamp'] = datetime.fromisoformat(msg['timestamp'])
            state.messages.append(serializable_msg)
        
        return state

class AIHandler:
    """Handles communication with AI service."""
    
    def __init__(self, ai_client=None, max_retries: int = 2):
        """
        Initialize the AI handler.
        
        Args:
            ai_client: Client for AI service (defaults to Claude-3 if None)
            max_retries: Maximum attempts to get valid output format from AI
        """
        self.max_retries = max_retries
        self.ai_client = ai_client or AI("sonnet3.7")
    
    def get_response(self, prompt: str, conversation_state: ConversationState) -> Dict:
        """
        Get a response from the AI service.
        
        Args:
            prompt: The formatted prompt
            conversation_state: Current conversation state
            
        Returns:
            dict: {
                'message': str,  # Message to show user
                'complete': bool,  # Whether information collection is complete
                'data': dict or None,  # Structured data if complete
                'error': str or None  # Error message if any
            }
        """
        try:
            for attempt in range(self.max_retries):
                try:
                    # Get response from AI
                    response = self.ai_client.message(prompt).content

                    # Validate response format
                    is_valid, error_message = self._validate_response_format(response)
                    
                    if is_valid:
                        # Extract user-facing message
                        user_message = self._extract_user_message(response)
                        
                        # Extract system message (JSON data) if present
                        system_data = self._extract_system_message(response)
                        
                        if system_data:
                            # Conversation is complete
                            status = system_data.get("status", "")
                            
                            if status == "complete":
                                collected_data = system_data.get("collected_information", {})
                                conversation_state.set_complete(data=collected_data)
                                return {
                                    'message': user_message,
                                    'complete': True,
                                    'data': collected_data,
                                    'error': None
                                }
                            elif system_data.get("error"):
                                # There was an error completing the task
                                error_msg = system_data.get("error", "Unknown error occurred")
                                conversation_state.set_complete(error=error_msg)
                                return {
                                    'message': user_message,
                                    'complete': True,
                                    'data': None,
                                    'error': error_msg
                                }
                        
                        # Conversation is not complete yet
                        return {
                            'message': user_message,
                            'complete': False,
                            'data': None,
                            'error': None
                        }
                    
                    elif attempt < self.max_retries - 1:
                        # Format is invalid, retry with error message
                        retry_prompt = f"{prompt}\n\n<assistant_error>\nYour previous response had formatting issues: {error_message}\nPlease ensure you follow the correct format from the instructions.\n</assistant_error>"
                        logger.warning(f"Retrying due to validation error: {error_message}")
                        prompt = retry_prompt
                    else:
                        # Max retries reached, return error
                        conversation_state.set_complete(error=f"Failed to get valid response after {self.max_retries} attempts: {error_message}")
                        return {
                            'message': "I apologize, but I'm having trouble processing this information. Let's try a different approach.",
                            'complete': True,
                            'data': None,
                            'error': f"Failed to get valid response after {self.max_retries} attempts: {error_message}"
                        }
                
                except Exception as e:
                    if attempt < self.max_retries - 1:
                        logger.error(f"Error processing AI response (attempt {attempt+1}/{self.max_retries}): {str(e)}")
                    else:
                        # Max retries reached, return error
                        error_msg = f"Error communicating with AI service: {str(e)}"
                        conversation_state.set_complete(error=error_msg)
                        return {
                            'message': "I apologize, but I'm experiencing technical difficulties. Please try again later.",
                            'complete': True,
                            'data': None,
                            'error': error_msg
                        }
        
        except Exception as e:
            # Catch any unexpected exceptions
            error_msg = f"Unexpected error: {str(e)}"
            conversation_state.set_complete(error=error_msg)
            return {
                'message': "I apologize, but an unexpected error occurred. Please try again later.",
                'complete': True,
                'data': None,
                'error': error_msg
            }
    
    def _validate_response_format(self, response: str) -> Tuple[bool, Optional[str]]:
        """
        Validate that the AI response follows the required format.
        
        Args:
            response: The AI response
            
        Returns:
            tuple: (is_valid, error_message)
        """
        try:
            # Check if the response has at least a user_message tag
            if "<user_message>" not in response:
                return False, "Response must contain <user_message> tags"
            
            # If the response has a system_message tag, check if it contains valid JSON
            if "<system_message" in response:
                # Extract the system message content
                start_idx = response.find("<system_message")
                end_idx = response.find("</system_message>", start_idx)
                
                if end_idx == -1:
                    return False, "Unclosed <system_message> tag"
                
                # Get the content between the opening and closing tags
                content_start = response.find(">", start_idx) + 1
                system_content = response[content_start:end_idx].strip()
                
                try:
                    # Try to parse as JSON
                    json.loads(system_content)
                except json.JSONDecodeError as e:
                    return False, f"Invalid JSON in system_message: {str(e)}"
            
            return True, None
        
        except Exception as e:
            return False, f"Error validating response format: {str(e)}"
    
    def _extract_user_message(self, response: str) -> str:
        """
        Extract the user-facing message from the AI response.
        
        Args:
            response: The AI response
            
        Returns:
            The user-facing message
        """
        try:
            # Use XML parsing to extract the user_message
            # Wrap the response in a root element to handle multiple user_message tags
            wrapped_response = f"<root>{response}</root>"
            
            try:
                root = ET.fromstring(wrapped_response)
                user_messages = root.findall('.//user_message')
                
                if user_messages:
                    # Combine all user_message contents
                    return ''.join(msg.text or '' for msg in user_messages)
                else:
                    # Fallback to simple string extraction if XML parsing fails
                    return self._extract_between_tags(response, 'user_message')
            
            except ET.ParseError:
                # Fallback to simple string extraction
                return self._extract_between_tags(response, 'user_message')
        
        except Exception:
            # Last resort fallback
            return "I apologize, but I'm having trouble generating a proper response. Let's continue our conversation."
    
    def _extract_between_tags(self, text: str, tag_name: str) -> str:
        """
        Extract content between XML tags using string operations.
        
        Args:
            text: The text to extract from
            tag_name: The name of the tag
            
        Returns:
            The content between the tags
        """
        start_tag = f"<{tag_name}>"
        end_tag = f"</{tag_name}>"
        
        start_pos = text.find(start_tag)
        if start_pos == -1:
            return ""
        
        start_pos += len(start_tag)
        end_pos = text.find(end_tag, start_pos)
        
        if end_pos == -1:
            return text[start_pos:]
        
        return text[start_pos:end_pos]
    
    def _extract_system_message(self, response: str) -> Optional[Dict]:
        """
        Extract the system message (JSON data) from the AI response if present.
        
        Args:
            response: The AI response
            
        Returns:
            The system message as a dictionary, or None if not present
        """
        try:
            # Check if there's a system_message tag
            if "<system_message" not in response:
                return None
            
            # Extract the system message content
            system_content = self._extract_between_tags(response, 'system_message')
            
            if not system_content:
                return None
            
            # Try to parse as JSON
            return json.loads(system_content)
        
        except (json.JSONDecodeError, Exception):
            return None

class InfoRetriever:
    """Main class for managing information retrieval conversations."""
    
    def __init__(self, ai_client=None, max_retries: int = 2, 
                 persistence_enabled: bool = False, 
                 storage_dir: str = "~/.info_retriever",
                 auto_save: bool = True):
        """
        Initialize the InfoRetriever.
        
        Args:
            ai_client: Client for AI service (defaults to Claude-3 if None)
            max_retries: Maximum attempts to get valid output format from AI
            persistence_enabled: Whether to save conversations to disk
            storage_dir: Directory to store conversation data
            auto_save: Whether to automatically save after each interaction
        """
        self.ai_handler = AIHandler(ai_client, max_retries)
        self.conversations = {}  # Store conversations by task_id
        
        # Persistence settings
        self.persistence_enabled = persistence_enabled
        self.auto_save = auto_save
        self.storage_dir = os.path.expanduser(storage_dir)
        
        # Initialize storage if persistence is enabled
        if self.persistence_enabled:
            self._init_storage()
            self._load_all_tasks()
    
    def _init_storage(self):
        """Initialize the storage directory structure."""
        try:
            # Create main storage directory
            os.makedirs(self.storage_dir, exist_ok=True)
            
            # Create subdirectories
            os.makedirs(os.path.join(self.storage_dir, "active"), exist_ok=True)
            os.makedirs(os.path.join(self.storage_dir, "completed"), exist_ok=True)
            os.makedirs(os.path.join(self.storage_dir, "archive"), exist_ok=True)
            
            # Create metadata file if it doesn't exist
            metadata_path = os.path.join(self.storage_dir, "metadata.json")
            if not os.path.exists(metadata_path):
                metadata = {
                    "version": STATE_VERSION,
                    "created_at": datetime.now().isoformat(),
                    "tasks": {}
                }
                self._atomic_write(metadata_path, metadata)
            
            logger.info(f"Storage initialized at {self.storage_dir}")
        
        except Exception as e:
            logger.error(f"Error initializing storage: {str(e)}")
            raise
    
    def _get_task_path(self, task_id: str) -> str:
        """
        Get the path to the task file.
        
        Args:
            task_id: The task identifier
            
        Returns:
            Path to the task file
        """
        # Check metadata to see if it's active, completed, or archived
        metadata = self._load_metadata()
        task_metadata = metadata.get("tasks", {}).get(task_id, {})
        status = task_metadata.get("status", "active")
        
        if status == "completed":
            return os.path.join(self.storage_dir, "completed", f"{task_id}.json")
        elif status == "archived":
            return os.path.join(self.storage_dir, "archive", f"{task_id}.json")
        else:
            return os.path.join(self.storage_dir, "active", f"{task_id}.json")
    
    def _load_metadata(self) -> Dict:
        """
        Load the metadata file.
        
        Returns:
            Metadata dictionary
        """
        metadata_path = os.path.join(self.storage_dir, "metadata.json")
        try:
            if os.path.exists(metadata_path):
                with open(metadata_path, 'r', encoding='utf-8') as f:
                    return json.load(f)
            return {"version": STATE_VERSION, "created_at": datetime.now().isoformat(), "tasks": {}}
        except Exception as e:
            logger.error(f"Error loading metadata: {str(e)}")
            return {"version": STATE_VERSION, "created_at": datetime.now().isoformat(), "tasks": {}}
    
    def _save_metadata(self, metadata: Dict):
        """
        Save the metadata file.
        
        Args:
            metadata: Metadata dictionary
        """
        metadata_path = os.path.join(self.storage_dir, "metadata.json")
        self._atomic_write(metadata_path, metadata)
    
    def _update_task_metadata(self, task_id: str, conversation: ConversationState):
        """
        Update the metadata for a task.
        
        Args:
            task_id: The task identifier
            conversation: The conversation state
        """
        metadata = self._load_metadata()
        
        metadata["tasks"][task_id] = {
            "status": conversation.status,
            "created_at": conversation.created_at.isoformat(),
            "last_updated": conversation.last_updated.isoformat(),
            "information_need": conversation.information_need,
            "message_count": len(conversation.messages)
        }
        
        self._save_metadata(metadata)
    
    def _atomic_write(self, filepath: str, data: Dict):
        """
        Write data to a file atomically to prevent corruption.
        
        Args:
            filepath: Path to the file
            data: Data to write
        """
        # Create a temporary file
        temp_filepath = f"{filepath}.tmp"
        
        try:
            # Write to the temporary file
            with open(temp_filepath, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2)
            
            # Rename the temporary file to the target file (atomic operation)
            os.replace(temp_filepath, filepath)
        
        except Exception as e:
            # Clean up the temporary file if an error occurs
            if os.path.exists(temp_filepath):
                os.remove(temp_filepath)
            logger.error(f"Error writing file {filepath}: {str(e)}")
            raise
    
    def _save_conversation(self, conversation: ConversationState):
        """
        Save a conversation to disk.
        
        Args:
            conversation: The conversation to save
        """
        if not self.persistence_enabled:
            return
        
        try:
            # Convert the conversation to a dictionary
            data = {
                "version": STATE_VERSION,
                "saved_at": datetime.now().isoformat(),
                "conversation": conversation.to_dict()
            }
            
            # Check if status has changed in metadata
            metadata = self._load_metadata()
            task_metadata = metadata.get("tasks", {}).get(conversation.task_id, {})
            old_status = task_metadata.get("status", "active")
            
            # If status has changed and is now completed, move from active to completed
            if old_status == "active" and conversation.status == "complete":
                old_path = os.path.join(self.storage_dir, "active", f"{conversation.task_id}.json")
                if os.path.exists(old_path):
                    # Make sure the destination directory exists
                    os.makedirs(os.path.join(self.storage_dir, "completed"), exist_ok=True)
                    # Move the file
                    new_path = os.path.join(self.storage_dir, "completed", f"{conversation.task_id}.json")
                    shutil.move(old_path, new_path)
                    logger.info(f"Moved completed task {conversation.task_id} from active to completed folder")
            
            # Get the appropriate path based on the conversation status
            task_path = self._get_task_path(conversation.task_id)
            
            # Save the conversation
            self._atomic_write(task_path, data)
            
            # Update the metadata
            self._update_task_metadata(conversation.task_id, conversation)
            
            logger.debug(f"Saved conversation {conversation.task_id} to {task_path}")
        
        except Exception as e:
            logger.error(f"Error saving conversation {conversation.task_id}: {str(e)}")
    
    def _load_conversation(self, task_id: str) -> Optional[ConversationState]:
        """
        Load a conversation from disk.
        
        Args:
            task_id: The task identifier
            
        Returns:
            The loaded conversation, or None if not found
        """
        if not self.persistence_enabled:
            return None
        
        try:
            # Get the path to the task file
            task_path = self._get_task_path(task_id)
            
            # Check if the file exists
            if not os.path.exists(task_path):
                logger.warning(f"Task file not found: {task_path}")
                return None
            
            # Load the file
            with open(task_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            # Check version compatibility
            file_version = data.get("version", "unknown")
            if file_version != STATE_VERSION:
                logger.warning(f"Task file version mismatch: {file_version} != {STATE_VERSION}")
            
            # Create a ConversationState from the data
            conversation_data = data.get("conversation", {})
            conversation = ConversationState.from_dict(conversation_data)
            
            logger.debug(f"Loaded conversation {task_id} from {task_path}")
            return conversation
        
        except Exception as e:
            logger.error(f"Error loading conversation {task_id}: {str(e)}")
            return None
    
    def _load_all_tasks(self):
        """Load all tasks from disk."""
        if not self.persistence_enabled:
            return
        
        try:
            # Get the metadata to find all tasks
            metadata = self._load_metadata()
            task_ids = set(metadata.get("tasks", {}).keys())
            
            # Load each task
            for task_id in task_ids:
                conversation = self._load_conversation(task_id)
                if conversation:
                    self.conversations[task_id] = conversation
            
            logger.info(f"Loaded {len(task_ids)} tasks from storage")
        
        except Exception as e:
            logger.error(f"Error loading tasks: {str(e)}")
    
    def save_state(self):
        """Save the current state of all conversations."""
        if not self.persistence_enabled:
            return
        
        try:
            for task_id, conversation in self.conversations.items():
                self._save_conversation(conversation)
            
            logger.info(f"Saved state with {len(self.conversations)} conversations")
        
        except Exception as e:
            logger.error(f"Error saving state: {str(e)}")
    
    def create_task(self, information_need: str, output_schema: Union[Dict, str], context: Optional[str] = None) -> Dict:
        """
        Create a new information retrieval task.
        
        Args:
            information_need: The question or information to obtain
            output_schema: Schema defining the expected JSON structure
            context: Additional context for the conversation
            
        Returns:
            dict: {
                'message': str,  # First message to send to user
                'task_id': str   # Unique ID for this conversation
            }
        """
        # Generate a unique task ID
        task_id = str(uuid.uuid4())
        
        # Create a new conversation state
        conversation = ConversationState(task_id, information_need, output_schema, context)
        self.conversations[task_id] = conversation
        
        # Generate the initial prompt
        prompt = conversation.get_formatted_prompt()
        
        # Get the first response from the AI
        response = self.ai_handler.get_response(prompt, conversation)
        
        # Add the assistant message to conversation history
        conversation.add_message('assistant', response['message'])
        
        # Save the conversation if auto-save is enabled
        if self.persistence_enabled and self.auto_save:
            self._save_conversation(conversation)
        
        return {
            'message': response['message'],
            'task_id': task_id
        }
    
    def process_response(self, task_id: str, user_message: str) -> Dict:
        """
        Process a user response and get the next assistant message.
        
        Args:
            task_id: The task identifier
            user_message: The user's response
            
        Returns:
            dict: {
                'message': str,  # Next message to show user
                'complete': bool,  # Whether information collection is complete
                'data': dict or None,  # Structured data if complete, else None
                'error': str or None  # Error message if any
            }
        """
        # Check if the task exists
        if task_id not in self.conversations:
            # Try to load it from disk if persistence is enabled
            if self.persistence_enabled:
                conversation = self._load_conversation(task_id)
                if conversation:
                    self.conversations[task_id] = conversation
                else:
                    return {
                        'message': "Sorry, I couldn't find that conversation.",
                        'complete': True,
                        'data': None,
                        'error': f"Task ID {task_id} not found"
                    }
            else:
                return {
                    'message': "Sorry, I couldn't find that conversation.",
                    'complete': True,
                    'data': None,
                    'error': f"Task ID {task_id} not found"
                }
        
        conversation = self.conversations[task_id]
        
        # If the conversation is already complete, just return the previous result
        if conversation.status != "in_progress":
            return {
                'message': "This conversation has already been completed.",
                'complete': True,
                'data': conversation.data,
                'error': conversation.error
            }
        
        # Add the user message to the history
        conversation.add_message('user', user_message)
        
        # Generate the prompt with updated history
        prompt = conversation.get_formatted_prompt()
        
        # Get the next response from the AI
        response = self.ai_handler.get_response(prompt, conversation)
        
        # Add the assistant message to conversation history
        conversation.add_message('assistant', response['message'])
        
        # Save the conversation if auto-save is enabled
        if self.persistence_enabled and self.auto_save:
            self._save_conversation(conversation)
        
        return response
    
    def get_conversation(self, task_id: str) -> List[Dict]:
        """
        Get the full conversation history with timestamps.
        
        Args:
            task_id: The task identifier
            
        Returns:
            list: List of message objects with sender, content, timestamp
        """
        # Check if the task exists in memory
        if task_id not in self.conversations:
            # Try to load it from disk if persistence is enabled
            if self.persistence_enabled:
                conversation = self._load_conversation(task_id)
                if conversation:
                    self.conversations[task_id] = conversation
                else:
                    return []
            else:
                return []
        
        return self.conversations[task_id].get_history()
    
    def get_task_status(self, task_id: str) -> Dict:
        """
        Get the current status of a task.
        
        Args:
            task_id: The task identifier
            
        Returns:
            dict: Task status information
        """
        # Check if the task exists in memory
        if task_id not in self.conversations:
            # Try to load it from disk if persistence is enabled
            if self.persistence_enabled:
                conversation = self._load_conversation(task_id)
                if conversation:
                    self.conversations[task_id] = conversation
                else:
                    return {
                        'status': 'error',
                        'data': None,
                        'error': f"Task ID {task_id} not found",
                        'created_at': None,
                        'last_updated': None
                    }
            else:
                return {
                    'status': 'error',
                    'data': None,
                    'error': f"Task ID {task_id} not found",
                    'created_at': None,
                    'last_updated': None
                }
        
        conversation = self.conversations[task_id]
        
        return {
            'status': conversation.status,
            'data': conversation.data,
            'error': conversation.error,
            'created_at': conversation.created_at,
            'last_updated': conversation.last_updated
        }
    
    def list_saved_tasks(self) -> Dict[str, Dict]:
        """
        List all saved tasks.
        
        Returns:
            dict: Dictionary of task IDs and their metadata
        """
        if not self.persistence_enabled:
            return {task_id: {
                "status": conv.status,
                "created_at": conv.created_at,
                "last_updated": conv.last_updated,
                "information_need": conv.information_need
            } for task_id, conv in self.conversations.items()}
        
        return self._load_metadata().get("tasks", {})
    
    def archive_task(self, task_id: str) -> bool:
        """
        Archive a task.
        
        Args:
            task_id: The task identifier
            
        Returns:
            bool: True if successful, False otherwise
        """
        if not self.persistence_enabled:
            return False
        
        try:
            # Check if the task exists
            if task_id not in self.conversations and not self._load_conversation(task_id):
                return False
            
            # Get the current path
            old_path = self._get_task_path(task_id)
            
            # Update metadata
            metadata = self._load_metadata()
            if task_id in metadata["tasks"]:
                metadata["tasks"][task_id]["status"] = "archived"
                self._save_metadata(metadata)
            
            # Move the file if it exists
            if os.path.exists(old_path):
                new_path = os.path.join(self.storage_dir, "archive", f"{task_id}.json")
                shutil.move(old_path, new_path)
            
            # Update the in-memory conversation if it exists
            if task_id in self.conversations:
                conversation = self.conversations[task_id]
                self._save_conversation(conversation)
            
            return True
        
        except Exception as e:
            logger.error(f"Error archiving task {task_id}: {str(e)}")
            return False
    
    def delete_task(self, task_id: str) -> bool:
        """
        Delete a task.
        
        Args:
            task_id: The task identifier
            
        Returns:
            bool: True if successful, False otherwise
        """
        if not self.persistence_enabled:
            if task_id in self.conversations:
                del self.conversations[task_id]
                return True
            return False
        
        try:
            # Remove from in-memory store
            if task_id in self.conversations:
                del self.conversations[task_id]
            
            # Get the file path
            task_path = self._get_task_path(task_id)
            
            # Delete the file if it exists
            if os.path.exists(task_path):
                os.remove(task_path)
            
            # Update metadata
            metadata = self._load_metadata()
            if task_id in metadata["tasks"]:
                del metadata["tasks"][task_id]
                self._save_metadata(metadata)
            
            return True
        
        except Exception as e:
            logger.error(f"Error deleting task {task_id}: {str(e)}")
            return False

# Usage example function
def example_usage():
    """Example of how to use the InfoRetriever class."""
    
    # Initialize the retriever with persistence enabled
    retriever = InfoRetriever(
        persistence_enabled=True,
        storage_dir="data/info_retriever",
        auto_save=True
    )
    
    # Try to list existing tasks
    tasks = retriever.list_saved_tasks()
    if tasks:
        print(f"Found {len(tasks)} existing tasks.")
        for task_id, task in tasks.items():
            print(f"Task {task_id[:8]}...: {task.get('information_need', '')}")
            print(f"  Status: {task.get('status', 'unknown')}")
            print(f"  Created: {task.get('created_at', 'unknown')}")
            print(f"  Updated: {task.get('last_updated', 'unknown')}")
            print(f"  Messages: {task.get('message_count', 0)}")
            print()
    else:
        print("No existing tasks found. Creating a new one...")
    
        # Create a new task
        result = retriever.create_task(
            information_need="Ask the user to confirm who they just had a meeting with",
            output_schema={
                "first_name": "The first name of the person they just had a meeting with",
                "last_name": "The last name of the person they just had a meeting with"
            }
        )
        
        # Get the first message to send to user
        first_message = result['message']
        task_id = result['task_id']
        
        print(f"Created new task with ID: {task_id}")
        print(f"First message: {first_message}")
        
        # Simulate a user response
        print("\nSimulating user response: 'I just met with John Smith.'")
        response = retriever.process_response(task_id, "I just met with John Smith.")
        
        # Check if complete
        if response['complete']:
            collected_data = response['data']
            print(f"Meeting confirmed with {collected_data['first_name']} {collected_data['last_name']}")
        else:
            # Continue the conversation
            next_message = response['message']
            print(f"Next message: {next_message}")
            
            # Simulate another user response
            print("\nSimulating user response: 'Yes, that's correct!'")
            response = retriever.process_response(task_id, "Yes, that's correct!")
            
            if response['complete']:
                collected_data = response['data']
                if collected_data:
                    print(f"Meeting confirmed with {collected_data['first_name']} {collected_data['last_name']}")
        
        # Check task status
        status = retriever.get_task_status(task_id)
        print(f"\nTask status: {status['status']}")
        if status['data']:
            print(f"Collected data: {status['data']}")
    
    # Show how to load an existing task
    print("\nTo load and continue an existing conversation:")
    print("retriever = InfoRetriever(persistence_enabled=True)")
    print("task_id = 'your-task-id'  # from the list above")
    print("conversation = retriever.get_conversation(task_id)")
    print("# Continue the conversation with:")
    print("response = retriever.process_response(task_id, 'user message')")

if __name__ == "__main__":
    example_usage() 