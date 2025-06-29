"""
Configuration module for Discord bot
Handles environment variables and bot settings
"""

import os
from dotenv import load_dotenv

class Config:
    """Configuration class to manage bot settings"""
    
    def __init__(self):
        # Load environment variables from .env file
        load_dotenv()
        
        # Bot token from Discord Developer Portal
        self.BOT_TOKEN = os.getenv('BOT_TOKEN')
        
        # Channel ID where the bot should monitor messages
        self.CHANNEL_ID = int(os.getenv('CHANNEL_ID', 0)) if os.getenv('CHANNEL_ID') else None
        
        # Message counter threshold (after how many messages to send reminder)
        self.MESSAGE_THRESHOLD = int(os.getenv('MESSAGE_THRESHOLD', 5))
        
        # The reminder message to send
        self.REMINDER_MESSAGE = os.getenv('REMINDER_MESSAGE', '💬 __***¿Tienes alguna sugerencia?***__\nPuedes enviar ideas tanto 🧠 **OOC**, 🎭 **IC** como del 🌐 **Discord**.\nUsa el comando 👉 `/suggest create` para hacer tu propuesta.')
        
        # Bot intents configuration
        self.ENABLE_MESSAGE_CONTENT = False
        self.ENABLE_GUILDS = True
        
    def validate(self):
        """Validate that all required configuration is present"""
        errors = []
        
        if not self.BOT_TOKEN:
            errors.append("BOT_TOKEN is required")
        
        if not self.CHANNEL_ID:
            errors.append("CHANNEL_ID is required")
        
        if self.MESSAGE_THRESHOLD <= 0:
            errors.append("MESSAGE_THRESHOLD must be greater than 0")
        
        return errors
