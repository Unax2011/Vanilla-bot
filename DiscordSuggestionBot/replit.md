# Discord Reminder Bot

## Overview

This is a Python-based Discord bot that monitors messages in a specific channel and sends reminder messages after a configurable number of messages have been posted. The bot is designed to help maintain engagement by periodically reminding users to use specific Discord features (like slash commands for creating suggestions).

## System Architecture

The application follows a modular Python architecture with clear separation of concerns:

- **Entry Point**: `main.py` - Handles bot initialization and startup
- **Bot Logic**: `bot.py` - Contains the main bot class and message handling logic
- **Configuration**: `config.py` - Manages environment variables and bot settings
- **Persistence**: JSON file storage for message counters

## Key Components

### Discord Bot (`ReminderBot` class)
- Extends `discord.ext.commands.Bot`
- Monitors messages in configured channels
- Maintains message counters with persistent storage
- Sends reminder messages when thresholds are reached

### Configuration Management
- Environment variable-based configuration
- Validation of required settings
- Default values for optional parameters
- Support for multiple Discord intents

### Message Counter System
- Tracks message counts per channel
- Persistent storage using JSON files
- Automatic loading and saving of counter data

## Data Flow

1. Bot starts and loads configuration from environment variables
2. Message counters are loaded from JSON file (if exists)
3. Bot connects to Discord using provided token
4. For each message in monitored channels:
   - Increment message counter for that channel
   - Check if counter reaches configured threshold
   - If threshold reached, send reminder message and reset counter
   - Save updated counters to JSON file

## External Dependencies

### Core Dependencies
- **discord.py (>=2.5.2)**: Discord API wrapper for Python
- **python-dotenv (>=1.1.0)**: Environment variable management

### Runtime Dependencies
- **aiohttp**: HTTP client library (dependency of discord.py)
- **asyncio**: Asynchronous programming support

## Deployment Strategy

The application is configured for Replit deployment with:
- **Runtime**: Python 3.11 on Nix stable-24_05
- **Automatic dependency installation**: Uses pip to install required packages
- **Environment configuration**: Requires `.env` file with bot credentials
- **Persistent storage**: JSON files for maintaining state across restarts

### Required Environment Variables
- `BOT_TOKEN`: Discord bot token from Developer Portal
- `CHANNEL_ID`: Target channel ID for message monitoring
- `MESSAGE_THRESHOLD`: Number of messages before sending reminder (default: 5)
- `REMINDER_MESSAGE`: Custom reminder text (has default value)

## User Preferences

- Preferred communication style: Simple, everyday language (Spanish)
- Prefers direct, concise communication without excessive explanation

## Recent Changes

- June 23, 2025: Initial Discord bot setup completed
- June 23, 2025: Bot successfully connects to Discord and operational
- June 23, 2025: Resolved privileged intents issue by disabling message_content intent
- June 23, 2025: Updated reminder message with enhanced formatting and emojis
- June 23, 2025: Added OOC/IC/Discord categories to suggestion prompt
- June 23, 2025: Added welcome/goodbye message system for member joins/leaves
- June 23, 2025: Updated test commands to use slash format: "/test bienvenida" and "/test despedida"
- June 23, 2025: Enabled message_content intent for command functionality
- June 23, 2025: Created complete strikes management system with slash commands
- June 23, 2025: Added strikes bot with /strike add, /strike check, /strike remove commands
- June 23, 2025: Added /aceptar command for accepting applications with role assignment
- June 23, 2025: Fixed role permission issues - bot role must be above target roles in hierarchy
- June 23, 2025: Updated /aceptar message to more welcoming format with emojis and team language
- June 23, 2025: Added /denegar command for denying applications with DM notification and ban
- June 24, 2025: Added complete suggestions system with /suggest create, /suggest accept, /suggest deny commands

## Current Status - COMPLETED

Bot ecosystem fully operational with multiple systems:

**Main Bot (Discord Bot workflow):**
✓ **Suggestion System**: Monitoring channel 📬-sugerencias, sending reminder messages every 5 messages
✓ **Welcome System**: Automatic welcome/goodbye messages + test commands
✓ Enhanced messages with emojis and Discord formatting
✓ Persistent counter system working correctly
✓ Both channels successfully found and accessible

**Management Systems (Integrated into main bot):**
✓ **Strikes System**: /strike add, /strike check, /strike remove with automatic warnings
✓ **Acceptance System**: /aceptar @usuario @rol with custom message and role assignment
✓ **Denial System**: /denegar @usuario with DM notification and automatic ban
✓ **Permission System**: Only "👑 Gerente" and "👑 Subgerente" roles can use management commands
✓ **Data Persistence**: JSON file storage with complete strike history
✓ **Rich Embeds**: Beautiful Discord embeds for all management responses
✓ **Strike Types**: leve, moderado, grave with different limit thresholds
✓ **Role Management**: Automatic role assignment with permission validation
✓ **DM Notifications**: Private message delivery before banning users
✓ **Command Sync**: Successfully synchronized with Discord (3 slash commands active)
✓ **Custom Messages**: Personalized acceptance and denial messages

**Suggestions System (New):**
✓ **Create Suggestions**: /suggest create command for users to submit suggestions
✓ **Accept/Deny**: /suggest accept and /suggest deny commands for administrators
✓ **Visual Feedback**: Color-coded embeds (blue=pending, green=accepted, red=denied)
✓ **Automatic Voting**: 👍👎 reactions added automatically to new suggestions
✓ **Data Persistence**: JSON storage with complete suggestion history and metadata
✓ **Permission Control**: Only administrators can accept/deny suggestions
✓ **Results Channel**: Accepted/denied suggestions automatically moved to #☑️-sugerencias-resultados
✓ **Enhanced Embeds**: Shows reviewer name, timestamp and final vote count on processed suggestions
✓ **Vote Tracking**: Displays final 👍👎 vote count when suggestions are accepted/denied
✓ **Command Reminders**: Automatic reminder message every 5 `/suggest create` commands in suggestions channel
✓ **Channel Restrictions**: Only administrators can send text messages in #📬-sugerencias, others restricted to commands only
✓ **Help Messages**: Automatic help reminder every 10 normal messages in any server channel

**Tickets System (New):**
✓ **Create Tickets**: Anyone can create tickets with `/ticket crear [motivo]`
✓ **Admin-Only Responses**: Only administrators and ticket creator can send messages in ticket channels
✓ **Priority Positioning**: New tickets appear at the top of channel list (position 0)
✓ **Close Tickets**: Only administrators can close tickets with `/ticket cerrar`
✓ **Add Users**: Administrators can add users to tickets with `/ticket add @usuario`
✓ **Transcript Generation**: Automatic transcript creation when tickets are closed
✓ **File Export**: Transcripts saved as .txt files in #transkript channel
✓ **Permission Management**: Automatic permission setup for creators and administrators
✓ **Message Restrictions**: Non-admin users' messages deleted with warning (except creator)
✓ **Complete Logging**: Full message history preserved in transcript files