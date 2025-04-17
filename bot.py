
import os 
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes
import json
import os
from datetime import datetime, timedelta
import re
from asyncio import Lock

# File to store user data
USER_DATA_FILE = "user_data.json"
location_lock = Lock()

# Load user data from file
def load_user_data():
    if os.path.exists(USER_DATA_FILE):
        with open(USER_DATA_FILE, 'r') as f:
            return json.load(f)
    return {}

# Save user data to file
def save_user_data(data):
    with open(USER_DATA_FILE, 'w') as f:
        json.dump(data, f)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = str(update.effective_user.id)
    all_user_data = load_user_data()
    
    if user_id not in all_user_data:
        all_user_data[user_id] = {"latitude": None, "longitude": None}
        save_user_data(all_user_data)
    
    context.user_data['location'] = all_user_data[user_id]
    context.user_data['live_expiration'] = None
    
    await update.message.reply_text(
        "Hi! Please share your live location to get started.\n"
        "Note: For continuous tracking, please use the 'Share Live Location' feature in Telegram."
    )

async def handle_location(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        loc = update.message.location
        if not loc:
            await update.message.reply_text("Invalid location data received.")
            return
        
        user_id = str(update.effective_user.id)
        async with location_lock:
            if not context.user_data.get('location'):
                context.user_data['location'] = {"latitude": None, "longitude": None}
            
            context.user_data['location']["latitude"] = loc.latitude
            context.user_data['location']["longitude"] = loc.longitude
            
            is_live = loc.live_period is not None
            if is_live:
                context.user_data['live_expiration'] = (
                    datetime.now() + timedelta(seconds=loc.live_period)
                ).timestamp()
                await update.message.reply_text(
                    f"Live location received and tracking!\n"
                    f"Latitude: {loc.latitude}\n"
                    f"Longitude: {loc.longitude}\n"
                    f"Updates will continue for {loc.live_period} seconds."
                )
            else:
                context.user_data['live_expiration'] = None
                await update.message.reply_text(
                    f"One-time location received!\n"
                    f"Latitude: {loc.latitude}\n"
                    f"Longitude: {loc.longitude}"
                )
            
            # Save to persistent storage
            all_user_data = load_user_data()
            all_user_data[user_id] = context.user_data['location']
            save_user_data(all_user_data)
    except Exception as e:
        print(f"Error in handle_location: {e}")
        await update.message.reply_text("Failed to process location. Please try again.")

async def handle_edited_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        if update.edited_message and update.edited_message.location:
            loc = update.edited_message.location
            user_id = str(update.effective_user.id)
            
            async with location_lock:
                if not context.user_data.get('location'):
                    context.user_data['location'] = {"latitude": None, "longitude": None}
                
                context.user_data['location']["latitude"] = loc.latitude
                context.user_data['location']["longitude"] = loc.longitude
                
                # Save to persistent storage
                all_user_data = load_user_data()
                all_user_data[user_id] = context.user_data['location']
                save_user_data(all_user_data)
            
            await update.edited_message.reply_text(
                f"Live location updated!\n"
                f"Latitude: {loc.latitude}\n"
                f"Longitude: {loc.longitude}"
            )
    except Exception as e:
        print(f"Error in handle_edited_message: {e}")
        await update.edited_message.reply_text("Failed to process location update. Please try again.")

async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.lower()
    user_id = str(update.effective_user.id)
    
    if not context.user_data.get('location'):
        context.user_data['location'] = {"latitude": None, "longitude": None}
    
    location_pattern = re.compile(r"(where.*(am|i|my)|location)")
    if location_pattern.search(text):
        lat = context.user_data['location']["latitude"]
        lon = context.user_data['location']["longitude"]
        
        live_expiration = context.user_data.get('live_expiration')
        if live_expiration and datetime.now().timestamp() > live_expiration:
            async with location_lock:
                context.user_data['location'] = {"latitude": None, "longitude": None}
                context.user_data['live_expiration'] = None
                all_user_data = load_user_data()
                all_user_data[user_id] = context.user_data['location']
                save_user_data(all_user_data)
            await update.message.reply_text(
                "Your live location has expired. Please share your location again."
            )
            return
        
        if lat and lon:
            await update.message.reply_text(
                f"Your latest location:\n"
                f"Latitude: {lat}\n"
                f"Longitude: {lon}"
            )
        else:
            await update.message.reply_text(
                "I haven't received your location yet. Please share your location using the paperclip "
                "icon in Telegram and select 'Location'. For continuous tracking, use 'Share Live Location'."
            )
    else:
        await update.message.reply_text("Please ask about your location or share your live location.")

async def error_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    error_msg = f"Error occurred: {context.error}"
    print(error_msg)
    if update and update.message:
        await update.message.reply_text(
            "Sorry, something went wrong. Please try again or contact support."
        )

def main():
    bot_token = os.getenv("'7241324534:AAGr5nB2LOghe4itEpfhaPNvjhDYVuCtEyE'  # Replace this with your real bot token")
    app = Application.builder().token(bot_token).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.LOCATION, handle_location))
    app.add_handler(MessageHandler(filters.UpdateType.EDITED_MESSAGE, handle_edited_message))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))
    app.add_error_handler(error_handler)

    print("Bot is starting...")
    app.run_polling()
    print("Bot has stopped.")

if __name__ == "__main__":
    main()
