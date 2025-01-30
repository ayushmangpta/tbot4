import logging
from PIL import Image
import io
from datetime import datetime
import PyPDF2
import dotenv as dotenv
import requests
import os
from collections import defaultdict
import google.generativeai as genai
from dotenv import load_dotenv
from telegram import Update, KeyboardButton, ReplyKeyboardMarkup
from telegram.ext import Updater, CommandHandler, MessageHandler, Filters, CallbackContext, ConversationHandler
from pymongo import MongoClient
from serpapi import GoogleSearch

load_dotenv()

logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)

TELEGRAM_TOKEN = os.environ.get("bot_key")
GEMINI_API_KEY = os.environ.get("gemini_key")
SERPAPI_API_KEY = os.environ.get("serpapi_key")
MONGODB_CONNECTION_STRING = os.environ.get("mongo_url")

genai.configure(api_key=GEMINI_API_KEY)
model = genai.GenerativeModel("gemini-1.5-flash")

client = MongoClient(MONGODB_CONNECTION_STRING)
db = client['telegram_bot_db']
users_collection = db['users']
chats_collection = db['chats']
files_collection = db['files']

chat_history = defaultdict(list)
MAX_HISTORY_LENGTH = 10  # Maximum number of messages to keep in context

def start(update: Update, context: CallbackContext):
    user = update.effective_user
    chat_id = update.effective_chat.id

    # Check if user already exists
    if users_collection.find_one({'chat_id': chat_id}) is None:
        # Save user details
        users_collection.insert_one({
            'chat_id': chat_id,
            'first_name': user.first_name,
            'username': user.username,
            'phone_number': None
        })
        logging.info(f"New user registered: {user.username} ({chat_id})")

        # Request phone number
        contact_button = KeyboardButton('Share Contact', request_contact=True)
        reply_markup = ReplyKeyboardMarkup([[contact_button]], one_time_keyboard=True)
        update.message.reply_text("Please share your contact number:", reply_markup=reply_markup)
    else:
        update.message.reply_text("Welcome back!")

def contact_handler(update: Update, context: CallbackContext):
    user = update.effective_user
    contact = update.message.contact

    if contact:
        phone_number = contact.phone_number
        chat_id = update.effective_chat.id
        users_collection.update_one(
            {'chat_id': chat_id},
            {'$set': {'phone_number': phone_number}}
        )
        update.message.reply_text("Thank you! Your phone number has been registered.")
    else:
        update.message.reply_text("Please share your contact number by pressing the button.")


def chat_handler(update: Update, context: CallbackContext):
    user_message = update.message.text
    chat_id = update.effective_chat.id

    # Get chat history for this user
    user_history = chat_history[chat_id]

    # Create context-aware prompt
    context_messages = "\n".join([
        f"{'User' if i % 2 == 0 else 'Assistant'}: {msg}"
        for i, msg in enumerate(user_history[-MAX_HISTORY_LENGTH:])
    ])

    full_prompt = f"""Previous conversation:
    {context_messages}

    User: {user_message}

    Please provide a response that takes into account the conversation history above."""

    # Generate response using Gemini API
    response = model.generate_content(full_prompt)
    bot_response = response.text

    # Update chat history
    user_history.append(user_message)
    user_history.append(bot_response)

    # Trim history if too long
    if len(user_history) > MAX_HISTORY_LENGTH * 2:
        user_history = user_history[-MAX_HISTORY_LENGTH * 2:]

    chat_history[chat_id] = user_history

    # Save chat history to MongoDB
    conversation_entry = {
        'chat_id': chat_id,
        'timestamp': datetime.utcnow(),
        'user_message': user_message,
        'bot_response': bot_response,
        'context': context_messages
    }
    chats_collection.insert_one(conversation_entry)

    # Reply to user
    update.message.reply_text(bot_response)

def image_handler(update: Update, context: CallbackContext):
    chat_id = update.effective_chat.id
    photo = update.message.photo[-1]
    file = photo.get_file()
    file_name = f"{file.file_id}.jpg"

    # Download image
    image_bytes = file.download_as_bytearray()

    # Open image
    image = Image.open(io.BytesIO(image_bytes))

    # Generate description using Gemini API
    response = model.generate_content(["Describe this image.", image])
    description = response.text

    # Save file metadata
    files_collection.insert_one({
        'chat_id': chat_id,
        'timestamp': datetime.utcnow(),
        'file_type': 'image',
        'file_name': file_name,
        'description': description
    })

    # Reply to user
    update.message.reply_text(description)

def clear_history(update: Update, context: CallbackContext):
    chat_id = update.effective_chat.id
    chat_history[chat_id] = []
    update.message.reply_text("Conversation history has been cleared.")

def document_handler(update: Update, context: CallbackContext):
    chat_id = update.effective_chat.id
    document = update.message.document

    if document.mime_type == 'application/pdf':
        file = document.get_file()
        file_name = document.file_name

        # Download the file
        file_bytes = file.download_as_bytearray()

        # Read PDF from bytes
        pdf_reader = PyPDF2.PdfReader(io.BytesIO(file_bytes))
        text = ''

        # Use new method to get the number of pages and extract text
        for page_num in range(len(pdf_reader.pages)):
            page = pdf_reader.pages[page_num]
            page_text = page.extract_text()
            if page_text:
                text += page_text

        # Generate description using Gemini API
        response = model.generate_content(f"Summarize the following document: {text}")
        description = response.text

        # Save file metadata
        files_collection.insert_one({
            'chat_id': chat_id,
            'timestamp': datetime.utcnow(),
            'file_type': 'document',
            'file_name': file_name,
            'description': description
        })

        # Reply to user
        update.message.reply_text(description)
    else:
        update.message.reply_text("Unsupported file type.")

def websearch_command(update: Update, context: CallbackContext):
    # Get the query from the message text after '/websearch'
    query = ' '.join(context.args)  # This gets all text after the command

    if not query:
        update.message.reply_text("Please provide a search query. Usage: /websearch your query here")
        return

    chat_id = update.effective_chat.id

    # Inform user that search is in progress
    update.message.reply_text("🔍 Searching the web for: " + query)

    try:
        # 1. Perform web search using SerpAPI
        params = {
            "q": query,
            "hl": "en",
            "gl": "us",
            "api_key": SERPAPI_API_KEY,
            "num": 5,
            "sort": "date"
        }

        search = GoogleSearch(params)
        results = search.get_dict()

        if 'organic_results' not in results or not results['organic_results']:
            update.message.reply_text("No search results found.")
            return

        # 2. Process and format search results
        search_results = []
        for item in results['organic_results'][:5]:
            search_results.append({
                'title': item.get('title', ''),
                'link': item.get('link', ''),
                'snippet': item.get('snippet', ''),
                'date': item.get('date', '')
            })

        # 3. Prepare search results for Gemini
        formatted_results = "\n\n".join([
            f"Title: {result['title']}\n"
            f"Summary: {result['snippet']}\n"
            f"URL: {result['link']}"
            for result in search_results
        ])

        # 4. Generate summary using Gemini
        prompt = f"""Based on these web search results for '{query}':

{formatted_results}

Please provide:
1. A comprehensive summary of the information
2. Key points or findings
3. Any relevant dates or timeline
"""

        # 5. Get Gemini's response
        response = model.generate_content(prompt)
        summary = response.text

        # 6. Format final response
        final_response = f"🔍 Search Results for: {query}\n\n"
        final_response += f"📝 AI Summary:\n{summary}\n\n"
        final_response += "🔗 Sources:\n"
        for result in search_results:
            final_response += f"• {result['title']}\n  {result['link']}\n"

        # 7. Send response in chunks if too long
        if len(final_response) > 4096:
            for i in range(0, len(final_response), 4096):
                update.message.reply_text(final_response[i:i + 4096])
        else:
            update.message.reply_text(final_response)

        # 8. Save to database
        conversation_entry = {
            'chat_id': chat_id,
            'timestamp': datetime.utcnow(),
            'query': query,
            'search_results': search_results,
            'summary': summary
        }
        chats_collection.insert_one(conversation_entry)

    except Exception as e:
        logging.error(f"Error in websearch: {str(e)}")
        update.message.reply_text(f"An error occurred while processing your search: {str(e)}")

def help_command(update: Update, context: CallbackContext):
    help_text = (
        "Here are the available commands and how to use the bot:\n\n"
        "/start - Register yourself with the bot and share your contact number.\n"
        "/help - Display this help message.\n"
        "/clear - clear chat history.\n"
        "/websearch - Perform a web search and get an AI-generated summary with top web links.\n\n"
        "Other interactions:\n"
        "- Send any text message to chat with the AI.\n"
        "- Send an image (JPG, PNG) to get an AI description of its content.\n"
        "- Send a PDF file to get an AI-generated summary.\n"
    )
    update.message.reply_text(help_text)

def main():

    updater = Updater(TELEGRAM_TOKEN, use_context=True)
    dp = updater.dispatcher

    # Start command handler
    dp.add_handler(CommandHandler('start', start))
    dp.add_handler(CommandHandler('help', help_command))
    dp.add_handler(CommandHandler('clear', clear_history))

    # Contact handler
    dp.add_handler(MessageHandler(Filters.contact, contact_handler))

    # Chat handler
    dp.add_handler(MessageHandler(Filters.text & ~Filters.command, chat_handler))

    # Image handler
    dp.add_handler(MessageHandler(Filters.photo, image_handler))

    # Document handler
    dp.add_handler(MessageHandler(Filters.document, document_handler))

    # Web search conversation handler
    dp.add_handler(CommandHandler('websearch', websearch_command, pass_args=True))
    # Start the bot
    updater.start_polling()
    updater.idle()

if __name__ == '__main__':
    main()
