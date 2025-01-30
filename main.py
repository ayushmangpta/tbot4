import logging
from PIL import Image
import io
from datetime import datetime
import PyPDF2
import dotenv as dotenv
import requests
import os
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

    # Generate response using Gemini API
    response = model.generate_content(user_message)
    bot_response = response.text

    # Save chat history
    conversation_entry = {
        'chat_id': chat_id,
        'timestamp': datetime.utcnow(),
        'user_message': user_message,
        'bot_response': bot_response
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

def document_handler(update: Update, context: CallbackContext):
    chat_id = update.effective_chat.id
    document = update.message.document

    if document.mime_type == 'application/pdf':
        file = document.get_file()
        file_name = document.file_name

        # Download file
        file_bytes = file.download_as_bytearray()

        # Extract text from PDF
        pdf_reader = PyPDF2.PdfReader(io.BytesIO(file_bytes))
        text = ''
        for page_num in range(pdf_reader.getNumPages()):
            text += pdf_reader.getPage(page_num).extractText()

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
    update.message.reply_text("Please enter your web search query:")
    return 'WEBSEARCH'

def websearch_query_handler(update: Update, context: CallbackContext):
    query = update.message.text
    chat_id = update.effective_chat.id

    # Perform web search using SerpAPI
    params = {
        "q": query,
        "hl": "en",
        "gl": "us",
        "api_key": SERPAPI_API_KEY
    }

    search = GoogleSearch(params)
    results = search.get_dict()

    # Extract top results
    search_results = []
    if 'organic_results' in results:
        for item in results['organic_results'][:3]:
            title = item.get('title')
            link = item.get('link')
            snippet = item.get('snippet', '')
            search_results.append({'title': title, 'link': link, 'snippet': snippet})
    else:
        update.message.reply_text("No results found.")
        return -1

    # Generate summary using Gemini API
    combined_results = "\n".join([f"{item['title']}: {item['snippet']}" for item in search_results])
    prompt = f"Please summarize the following search results for '{query}':\n{combined_results}"
    response = model.generate_content(prompt)
    summary = response.text

    # Reply to user
    response_text = f"Summary:\n{summary}\n\nTop links:\n"
    for item in search_results:
        response_text += f"{item['title']}: {item['link']}\n"

    update.message.reply_text(response_text)

    # Save conversation
    conversation_entry = {
        'chat_id': chat_id,
        'timestamp': datetime.utcnow(),
        'user_query': query,
        'bot_response': summary,
        'search_results': search_results
    }
    chats_collection.insert_one(conversation_entry)

    return -1

def help_command(update: Update, context: CallbackContext):
    help_text = (
        "Here are the available commands and how to use the bot:\n\n"
        "/start - Register yourself with the bot and share your contact number.\n"
        "/help - Display this help message.\n"
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

    # Contact handler
    dp.add_handler(MessageHandler(Filters.contact, contact_handler))

    # Chat handler
    dp.add_handler(MessageHandler(Filters.text & ~Filters.command, chat_handler))

    # Image handler
    dp.add_handler(MessageHandler(Filters.photo, image_handler))

    # Document handler
    dp.add_handler(MessageHandler(Filters.document, document_handler))

    # Web search conversation handler
    websearch_conv_handler = ConversationHandler(
        entry_points=[CommandHandler('websearch', websearch_command)],
        states={
            'WEBSEARCH': [MessageHandler(Filters.text & ~Filters.command, websearch_query_handler)]
        },
        fallbacks=[],
        allow_reentry=True
    )
    dp.add_handler(websearch_conv_handler)
    # Start the bot
    updater.start_polling()
    updater.idle()

if __name__ == '__main__':
    main()
