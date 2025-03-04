#!/usr/bin/env python
"""
Interactive CLI for InfoRetriever

Run this script to interactively test the InfoRetriever module.
It allows you to create information retrieval tasks and have
conversations with the retriever.
"""

import json
import os
import datetime
import time
from info_retriever import InfoRetriever

def clear_screen():
    """Clear the terminal screen."""
    os.system('cls' if os.name == 'nt' else 'clear')

def print_header(title):
    """Print a formatted header."""
    width = 60
    print("\n" + "=" * width)
    print(f"{title.center(width)}")
    print("=" * width + "\n")

def print_message(sender, message):
    """Print a formatted message."""
    if sender == "assistant":
        print(f"\n📱 Assistant: {message}\n")
    else:
        print(f"\n👤 You: {message}\n")

def format_timestamp(timestamp):
    """Format a timestamp for display."""
    if isinstance(timestamp, str):
        return timestamp
    
    if isinstance(timestamp, datetime.datetime):
        return timestamp.strftime("%Y-%m-%d %H:%M:%S")
    
    return str(timestamp)

def create_new_task(retriever):
    """Create a new information retrieval task."""
    print_header("Create New Information Retrieval Task")
    
    # Get information need
    information_need = input("What information do you want to collect? (e.g., 'Ask the user for their favorite food'): ")
    
    # Get output schema
    print("\nNow let's define the output schema (the data you want to collect).")
    print("Enter each field one by one. Enter a blank field name when done.")
    
    schema = {}
    while True:
        field_name = input("\nField name (or blank to finish): ")
        if not field_name:
            break
        field_description = input(f"Description for '{field_name}': ")
        schema[field_name] = field_description
    
    # Get optional context
    context = input("\nAny additional context? (optional, press Enter to skip): ")
    
    # Create the task
    result = retriever.create_task(
        information_need=information_need,
        output_schema=schema,
        context=context if context else None
    )
    
    # Start the conversation
    have_conversation(retriever, result['task_id'], result['message'])

def have_conversation(retriever, task_id, first_message=None):
    """Have an interactive conversation with the retriever."""
    clear_screen()
    print_header("Information Retrieval Conversation")
    
    print("Type your responses below. The conversation will continue until all information is collected.")
    print("Type 'history' to see the conversation history.")
    print("Type 'status' to see the current status of the task.")
    print("Type 'quit' to end the conversation.\n")
    
    # Get the conversation history
    conversation = retriever.get_conversation(task_id)
    
    # If first_message is provided, it's a new conversation
    # Otherwise, show the last message from the assistant
    if first_message:
        print_message("assistant", first_message)
    elif conversation:
        # Find the last message from the assistant
        assistant_messages = [msg for msg in conversation if msg['sender'] == 'assistant']
        if assistant_messages:
            last_message = assistant_messages[-1]['content']
            print_message("assistant", last_message)
    
    # Check task status
    status = retriever.get_task_status(task_id)
    if status['status'] != 'in_progress':
        print(f"\nThis conversation is already {status['status']}.")
        if status['data']:
            print("\nCollected information:")
            print(json.dumps(status['data'], indent=2))
        elif status['error']:
            print(f"\nError: {status['error']}")
        
        input("\nPress Enter to return to the main menu...")
        return
    
    while True:
        # Get user input
        user_input = input("> ")
        
        # Handle special commands
        if user_input.lower() == 'quit':
            break
        elif user_input.lower() == 'history':
            show_history(retriever, task_id)
            continue
        elif user_input.lower() == 'status':
            show_status(retriever, task_id)
            continue
        
        # Process the user response
        print_message("user", user_input)
        response = retriever.process_response(task_id, user_input)
        
        # Show the assistant response
        print_message("assistant", response['message'])
        
        # Check if conversation is complete
        if response['complete']:
            print("\n🎉 Conversation complete!")
            collected_data = None
            
            if response['data']:
                print("\nCollected information:")
                print(json.dumps(response['data'], indent=2))
                collected_data = response['data']
            else:
                print(f"\nError: {response['error']}")
            
            # Show conversation summary
            print("\n" + "=" * 60)
            print("Conversation Summary".center(60))
            print("=" * 60)
            
            conversation = retriever.get_conversation(task_id)
            for message in conversation:
                sender = message['sender']
                content = message['content']
                timestamp = message['timestamp']
                if isinstance(timestamp, datetime.datetime):
                    timestamp = timestamp.strftime("%H:%M:%S")
                
                if sender == "assistant":
                    print(f"[{timestamp}] 📱 Assistant: {content}")
                else:
                    print(f"[{timestamp}] 👤 You: {content}")
            
            # Ask if user wants to save the conversation
            if collected_data:
                print("\nWould you like to save this conversation and collected data to a file?")
                save_choice = input("Save to file? (y/n): ")
                
                if save_choice.lower().startswith('y'):
                    filepath = save_conversation(task_id, conversation, collected_data)
                    print(f"\nConversation saved to: {filepath}")
            
            # Add pause to review results before returning to menu
            print("\n" + "=" * 60)
            input("Press Enter to return to the main menu...")
            break

def save_conversation(task_id, conversation, data):
    """Save conversation and collected data to a file."""
    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"conversation_{task_id}_{timestamp}.json"
    
    # Create results directory if it doesn't exist
    os.makedirs("results", exist_ok=True)
    
    # Prepare data for serialization (convert datetime objects to strings)
    serializable_conversation = []
    for message in conversation:
        serializable_message = message.copy()
        if isinstance(serializable_message['timestamp'], datetime.datetime):
            serializable_message['timestamp'] = serializable_message['timestamp'].strftime("%Y-%m-%d %H:%M:%S")
        serializable_conversation.append(serializable_message)
    
    # Create the output structure
    output = {
        "task_id": task_id,
        "timestamp": timestamp,
        "conversation": serializable_conversation,
        "collected_data": data
    }
    
    # Save to file
    filepath = os.path.join("results", filename)
    with open(filepath, 'w', encoding='utf-8') as f:
        json.dump(output, f, indent=2)
    
    return filepath

def show_history(retriever, task_id):
    """Show the conversation history."""
    print_header("Conversation History")
    
    conversation = retriever.get_conversation(task_id)
    
    for message in conversation:
        sender = message['sender']
        content = message['content']
        timestamp = message['timestamp']
        if isinstance(timestamp, datetime.datetime):
            timestamp = timestamp.strftime("%H:%M:%S")
        
        if sender == "assistant":
            print(f"[{timestamp}] 📱 Assistant: {content}")
        else:
            print(f"[{timestamp}] 👤 You: {content}")
    
    input("\nPress Enter to continue...")

def show_status(retriever, task_id):
    """Show the current status of the task."""
    print_header("Task Status")
    
    status = retriever.get_task_status(task_id)
    
    print(f"Status: {status['status']}")
    
    if status['created_at']:
        created_at = format_timestamp(status['created_at'])
        print(f"Created at: {created_at}")
    
    if status['last_updated']:
        last_updated = format_timestamp(status['last_updated'])
        print(f"Last updated: {last_updated}")
    
    if status['data']:
        print("\nCollected data:")
        print(json.dumps(status['data'], indent=2))
    
    if status['error']:
        print(f"\nError: {status['error']}")
    
    input("\nPress Enter to continue...")

def list_and_select_saved_tasks(retriever):
    """List all saved tasks and let the user select one."""
    clear_screen()
    print_header("Saved Conversations")
    
    tasks = retriever.list_saved_tasks()
    
    if not tasks:
        print("No saved conversations found.")
        input("\nPress Enter to return to the main menu...")
        return None
    
    # Display tasks in a numbered list
    task_ids = list(tasks.keys())
    
    for i, task_id in enumerate(task_ids, 1):
        task = tasks[task_id]
        status = task.get("status", "unknown")
        info_need = task.get("information_need", "")
        created = format_timestamp(task.get("created_at", "unknown"))
        last_updated = format_timestamp(task.get("last_updated", "unknown"))
        
        status_emoji = "✅" if status == "complete" else "🔄" if status == "in_progress" else "🗄️"
        
        print(f"{i}. {status_emoji} [{task_id[:8]}...] {info_need}")
        print(f"   Status: {status}, Created: {created}, Updated: {last_updated}")
        print()
    
    # Let user select a task
    while True:
        choice = input("\nEnter task number to resume (or 'q' to go back): ")
        
        if choice.lower() == 'q':
            return None
        
        try:
            index = int(choice) - 1
            if 0 <= index < len(task_ids):
                return task_ids[index]
            else:
                print("Invalid task number. Please try again.")
        except ValueError:
            print("Please enter a valid number or 'q'.")

def archive_saved_task(retriever):
    """Archive a saved task."""
    clear_screen()
    print_header("Archive Conversation")
    
    # Let user select a task
    task_id = list_and_select_saved_tasks(retriever)
    
    if not task_id:
        return
    
    # Confirm archiving
    confirm = input(f"\nAre you sure you want to archive task {task_id}? (y/n): ")
    
    if confirm.lower().startswith('y'):
        success = retriever.archive_task(task_id)
        
        if success:
            print(f"\nTask {task_id} successfully archived.")
        else:
            print(f"\nFailed to archive task {task_id}.")
    
    input("\nPress Enter to return to the main menu...")

def delete_saved_task(retriever):
    """Delete a saved task."""
    clear_screen()
    print_header("Delete Conversation")
    
    # Let user select a task
    task_id = list_and_select_saved_tasks(retriever)
    
    if not task_id:
        return
    
    # Confirm deletion
    confirm = input(f"\nAre you sure you want to DELETE task {task_id}? This cannot be undone. (y/n): ")
    
    if confirm.lower().startswith('y'):
        success = retriever.delete_task(task_id)
        
        if success:
            print(f"\nTask {task_id} successfully deleted.")
        else:
            print(f"\nFailed to delete task {task_id}.")
    
    input("\nPress Enter to return to the main menu...")

def task_management_menu(retriever):
    """Display the task management menu."""
    while True:
        clear_screen()
        print_header("Task Management")
        
        print("1. List and Resume Saved Tasks")
        print("2. Archive Task")
        print("3. Delete Task")
        print("4. Return to Main Menu")
        
        choice = input("\nChoose an option (1-4): ")
        
        if choice == '1':
            task_id = list_and_select_saved_tasks(retriever)
            if task_id:
                have_conversation(retriever, task_id)
        elif choice == '2':
            archive_saved_task(retriever)
        elif choice == '3':
            delete_saved_task(retriever)
        elif choice == '4':
            break
        else:
            input("Invalid choice. Press Enter to try again...")

def main_menu():
    """Display the main menu."""
    # Create the InfoRetriever with persistence enabled
    retriever = InfoRetriever(
        persistence_enabled=True,
        storage_dir="~/.info_retriever",
        auto_save=True
    )
    
    while True:
        clear_screen()
        print_header("Interactive Info Retriever")
        
        print("1. Create a new information retrieval task")
        print("2. Task Management (list/resume/archive/delete)")
        print("3. Exit")
        
        choice = input("\nChoose an option (1-3): ")
        
        if choice == '1':
            create_new_task(retriever)
        elif choice == '2':
            task_management_menu(retriever)
        elif choice == '3':
            # Save state before exiting
            retriever.save_state()
            print("\nGoodbye!")
            break
        else:
            input("Invalid choice. Press Enter to try again...")

if __name__ == "__main__":
    main_menu() 