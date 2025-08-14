#!/usr/bin/env python3
"""
OpenAI Assistants API Integration Script
Simple script to send requests to OpenAI's Assistants API and get responses
"""

import os
import time
from openai import OpenAI
from typing import Optional
from dotenv import load_dotenv

load_dotenv('.env')

class OpenAIAssistant:
    def __init__(self, api_key: Optional[str] = None):
        """Initialize the OpenAI Assistant client"""
        self.client = OpenAI(api_key=api_key or os.getenv('OPENAI_API_KEY'))
        self.assistant_id = None
        self.thread_id = None
    
    def create_assistant(self, 
                        name: str = "Chat Assistant",
                        instructions: str = "You are a helpful AI assistant. Answer questions clearly and concisely.",
                        model: str = "gpt-4-1106-preview") -> str:
        """Create a new assistant"""
        try:
            assistant = self.client.beta.assistants.create(
                name=name,
                instructions=instructions,
                model=model,
                tools=[{"type": "code_interpreter"}]  # Optional: add tools
            )
            self.assistant_id = assistant.id
            print(f"✅ Assistant created with ID: {assistant.id}")
            return assistant.id
        except Exception as e:
            print(f"❌ Error creating assistant: {e}")
            return None
    
    def create_thread(self) -> str:
        """Create a new conversation thread"""
        try:
            thread = self.client.beta.threads.create()
            self.thread_id = thread.id
            print(f"✅ Thread created with ID: {thread.id}")
            return thread.id
        except Exception as e:
            print(f"❌ Error creating thread: {e}")
            return None
    
    def send_message(self, message: str, assistant_id: Optional[str] = None, thread_id: Optional[str] = None) -> str:
        """Send a message and get the assistant's response"""
        try:
            # Use provided IDs or fall back to instance variables
            assistant_id = assistant_id or self.assistant_id
            thread_id = thread_id or self.thread_id
            
            if not assistant_id or not thread_id:
                raise ValueError("Assistant ID and Thread ID are required")
            
            # Add message to thread
            self.client.beta.threads.messages.create(
                thread_id=thread_id,
                role="user",
                content=message
            )
            
            # Run the assistant
            run = self.client.beta.threads.runs.create(
                thread_id=thread_id,
                assistant_id=assistant_id
            )
            
            # Wait for completion
            print("🤖 Assistant is thinking...")
            while run.status in ['queued', 'in_progress', 'cancelling']:
                time.sleep(1)
                run = self.client.beta.threads.runs.retrieve(
                    thread_id=thread_id,
                    run_id=run.id
                )
            
            if run.status == 'completed':
                # Retrieve messages
                messages = self.client.beta.threads.messages.list(
                    thread_id=thread_id
                )
                
                # Get the latest assistant message
                for message in messages.data:
                    if message.role == "assistant":
                        response_text = message.content[0].text.value
                        print("✅ Response received!")
                        return response_text
                        
            else:
                print(f"❌ Run failed with status: {run.status}")
                return f"Error: Run failed with status {run.status}"
                
        except Exception as e:
            print(f"❌ Error sending message: {e}")
            return f"Error: {str(e)}"
    
    def chat_session(self):
        """Interactive chat session"""
        print("🚀 Starting OpenAI Assistant Chat Session")
        print("Type 'quit' or 'exit' to end the session\n")
        
        # Create assistant and thread if not exists
        if not self.assistant_id:
            self.create_assistant()
        if not self.thread_id:
            self.create_thread()
        
        while True:
            try:
                user_input = input("You: ").strip()
                
                if user_input.lower() in ['quit', 'exit', 'q']:
                    print("👋 Goodbye!")
                    break
                
                if not user_input:
                    continue
                
                response = self.send_message(user_input)
                print(f"\nAssistant: {response}\n")
                
            except KeyboardInterrupt:
                print("\n👋 Goodbye!")
                break
            except Exception as e:
                print(f"❌ Error in chat session: {e}")


# Flask Integration Functions
def create_flask_response(message: str, assistant_id: str = None, thread_id: str = None) -> dict:
    """Function specifically for Flask integration"""
    assistant = OpenAIAssistant()
    
    # Set IDs if provided
    if assistant_id:
        assistant.assistant_id = assistant_id
    if thread_id:
        assistant.thread_id = thread_id
    
    # Create assistant and thread if needed
    if not assistant.assistant_id:
        assistant.create_assistant()
    if not assistant.thread_id:
        assistant.create_thread()
    
    response = assistant.send_message(message)
    
    return {
        "response": response,
        "assistant_id": assistant.assistant_id,
        "thread_id": assistant.thread_id,
        "status": "success" if not response.startswith("Error:") else "error"
    }


# Example Flask route (add this to your Flask app)
"""
from flask import Flask, request, jsonify, render_template

app = Flask(__name__)

@app.route('/')
def index():
    return render_template('chat.html')

@app.route('/api/chat', methods=['POST'])
def chat():
    data = request.get_json()
    message = data.get('message', '')
    assistant_id = data.get('assistant_id')
    thread_id = data.get('thread_id')
    
    if not message:
        return jsonify({"error": "Message is required"}), 400
    
    try:
        result = create_flask_response(message, assistant_id, thread_id)
        return jsonify(result)
    except Exception as e:
        return jsonify({"error": str(e)}), 500

if __name__ == '__main__':
    app.run(debug=True)
"""


def main():
    """Main function for testing"""
    # Make sure to set your OpenAI API key
    api_key = os.getenv('OPENAI_API_KEY')
    print(os.getenv('OPENAI_API_KEY'))
    if not api_key:
        print("❌ Please set your OPENAI_API_KEY environment variable")
        print("   You can get one from: https://platform.openai.com/api-keys")
        return
    
    # Example usage
    assistant = OpenAIAssistant()
    
    # Option 1: Interactive chat session
    assistant.chat_session()
    
    # Option 2: Single message (uncomment to use)
    # assistant.create_assistant()
    # assistant.create_thread()
    # response = assistant.send_message("Hello! Can you help me with Python programming?")
    # print(f"Response: {response}")


if __name__ == "__main__":
    main()