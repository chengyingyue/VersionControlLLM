import requests
import json
import logging
import os
import re

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

BASE_URL = "http://localhost:8002"
USER_ID = "debug_user"

session = requests.Session()

def login():
    logging.info(f"Attempting to log in as {USER_ID}...")
    try:
        response = session.post(f"{BASE_URL}/api/login", json={"user_id": USER_ID})
        response.raise_for_status()
        logging.info(f"Login successful: {response.json()}")
    except requests.exceptions.RequestException as e:
        logging.error(f"Login failed: {e}")
        exit(1)

def create_conversation(name: str, system_prompt: str = "You are a helpful AI assistant.") -> str:
    logging.info(f"Creating conversation '{name}'...")
    try:
        response = session.post(f"{BASE_URL}/api/conversations", json={"name": name, "system_prompt": system_prompt})
        response.raise_for_status()
        conv_id = response.json()["id"]
        logging.info(f"Conversation created with ID: {conv_id}")
        return conv_id
    except requests.exceptions.RequestException as e:
        logging.error(f"Failed to create conversation: {e}")
        exit(1)

def get_conversation_content(conv_id: str) -> str:
    logging.info(f"Getting content for conversation {conv_id}...")
    try:
        response = session.get(f"{BASE_URL}/api/conversations/{conv_id}/export")
        response.raise_for_status()
        logging.info(f"Successfully retrieved content for {conv_id}")
        return response.text
    except requests.exceptions.RequestException as e:
        logging.error(f"Failed to get conversation content: {e}")
        exit(1)

def update_conversation_content(conv_id: str, new_content: str):
    logging.info(f"Updating content for conversation {conv_id}...")
    try:
        response = session.put(f"{BASE_URL}/api/conversations/{conv_id}/content", json={"content": new_content})
        response.raise_for_status()
        logging.info(f"Successfully updated content for {conv_id}: {response.json()}")
    except requests.exceptions.RequestException as e:
        logging.error(f"Failed to update conversation content: {e}")
        exit(1)

def main():
    login()
    conv_id = create_conversation("Test Global Edit")

    # Get initial content
    initial_content = get_conversation_content(conv_id)
    logging.info(f"Initial content:\n{initial_content}")

    # Modify content
    modified_content = initial_content.replace("You are a helpful AI assistant.", "You are a helpful and friendly AI assistant.")
    modified_content += "\n# Message 1 (User)\nHello, world!\n# Message 2 (Assistant)\nHello to you too!"
    logging.info(f"Modified content:\n{modified_content}")

    # Update content
    update_conversation_content(conv_id, modified_content)

    # Verify update
    verified_content = get_conversation_content(conv_id)
    logging.info(f"Verified content:\n{verified_content}")

    if re.sub(r"updated_at: .*\n", "", modified_content).strip() == re.sub(r"updated_at: .*\n", "", verified_content).strip():
        logging.info("Content update verified successfully!")
    else:
        logging.error("Content update verification FAILED!")
        logging.error(f"Expected:\n{modified_content}")
        logging.error(f"Got:\n{verified_content}")

if __name__ == "__main__":
    main()
