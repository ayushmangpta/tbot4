# AI-Powered Telegram Bot

An intelligent Telegram bot that leverages Google's Gemini AI model for chat interactions, image analysis, PDF summarization, and web search capabilities. The bot maintains conversation history and user data using MongoDB for a personalized experience.

## Features

- 💬 AI-powered chat with conversation memory
- 📸 Image analysis and description
- 📄 PDF document summarization
- 🔍 Web search with AI-generated summaries
- 👤 User registration with phone number verification
- 💾 Persistent storage of conversations and user data

## Prerequisites

- Python 3.8+
- Telegram Bot Token
- Google Gemini API Key
- SerpAPI Key
- MongoDB Connection String

## Installation

1. Clone the repository:
```bash
git clone <repository-url>
cd telegram-bot
```

2. Install required dependencies:
```bash
pip install -r requirements.txt
```

3. Create a `.env` file in the root directory with the following variables:
```
bot_key=YOUR_TELEGRAM_BOT_TOKEN
gemini_key=YOUR_GEMINI_API_KEY
serpapi_key=YOUR_SERPAPI_API_KEY
mongo_url=YOUR_MONGODB_CONNECTION_STRING
```

## Required Dependencies

```
python-telegram-bot
google-generativeai
python-dotenv
Pillow
PyPDF2
requests
pymongo
serpapi
```

## Usage

1. Start the bot:
```bash
python main.py
```

2. In Telegram, interact with the bot using these commands:
- `/start` - Register and set up your profile
- `/help` - View available commands and features
- `/clear` - Clear conversation history
- `/websearch [query]` - Perform web search with AI summary

3. Additional Features:
- Send text messages to chat with the AI
- Send images to get AI-generated descriptions
- Share PDF files to receive summaries
- Share contact information for registration

## Bot Capabilities

### Chat Interface
- Maintains conversation history
- Contextual responses based on chat history
- Maximum history length of 10 messages for context

### Image Processing
- Supports JPG/PNG formats
- Generates detailed descriptions using Gemini AI
- Stores image metadata in MongoDB

### Document Handling
- PDF file support
- Text extraction and summarization
- Document metadata storage

### Web Search
- Integration with SerpAPI for web results
- AI-generated summaries of search results
- Source link preservation
- Results sorted by date

### Data Storage
- User profiles
- Chat histories
- File metadata
- Search queries and results

## Database Structure

The bot uses MongoDB with the following collections:
- `users`: Stores user profiles and contact information
- `chats`: Maintains conversation histories and contexts
- `files`: Stores metadata for processed files

## Error Handling

- Comprehensive logging system
- Graceful error messages for users
- Exception handling for API failures

## Security Features

- Phone number verification
- Secure storage of user data
- Environment variable configuration
- API key protection

## Contributing

1. Fork the repository
2. Create a feature branch
3. Commit your changes
4. Push to the branch
5. Create a Pull Request

## Acknowledgments

- Google Gemini AI for natural language processing
- SerpAPI for web search capabilities
- MongoDB for data storage
- Python Telegram Bot community
