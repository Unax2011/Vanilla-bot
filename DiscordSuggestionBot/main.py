#!/usr/bin/env python3
"""
Discord Bot Entry Point
Main script to run the Discord reminder bot
"""

import asyncio
import logging
from bot import ReminderBot
from config import Config

def setup_logging():
    """Configure logging for the bot"""
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.FileHandler('bot.log'),
            logging.StreamHandler()
        ]
    )

async def main():
    """Main function to start the Discord bot"""
    # Setup logging
    setup_logging()
    logger = logging.getLogger(__name__)
    
    try:
        # Load configuration
        config = Config()
        
        # Validate required environment variables
        if not config.BOT_TOKEN:
            logger.error("BOT_TOKEN not found in environment variables")
            return
        
        if not config.CHANNEL_ID:
            logger.error("CHANNEL_ID not found in environment variables")
            return
        
        # Create and start the bot
        bot = ReminderBot(config)
        logger.info("Starting Discord reminder bot...")
        
        # Run the bot
        await bot.start(config.BOT_TOKEN)
        
    except KeyboardInterrupt:
        logger.info("Bot stopped by user")
    except Exception as e:
        logger.error(f"Fatal error: {e}")
        raise

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\nBot stopped by user")
    except Exception as e:
        print(f"Failed to start bot: {e}")
