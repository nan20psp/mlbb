import os
import json
import random
import asyncio
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, ContextTypes, MessageHandler, filters
from dotenv import load_dotenv

# ---------------- Load .env ----------------
load_dotenv()
BOT_TOKEN = os.getenv("BOT_TOKEN", "7927660379:AAGtm-CvAunvvANaaYvzlmRVjjBgJcmEh58")
ADMIN_ID = int(os.getenv("ADMIN_ID", "5821905026"))

# ---------------- Database ----------------
DB_FILE = "database.json"


def load_db():
    if not os.path.exists(DB_FILE):
        return {
            "users": {},
            "stock": {
                "MLBBbal":
                {},  # {"1000": ["code1", "code2"], "2000": ["code3"]}
                "MLBBph": {},
                "PUPG": {}
            },
            "receipts": {},
            "topup_requests": {},
            "prices": {
                "MLBBbal": {},  # {"1000": 2000, "2000": 4000}
                "MLBBph": {},
                "PUPG": {}
            },
            "payment": {
                "Wave": {
                    "phone": "09673585480",
                    "name": "Nine Nine"
                },
                "KPay": {
                    "phone": "09678786528",
                    "name": "Ma May Phoo Wai"
                }
            },
            "sales_total": 0,
            "pending_registrations": {}
        }
    with open(DB_FILE, "r") as f:
        try:
            data = json.load(f)
        except json.JSONDecodeError:
            # If the file is corrupted or empty, return a default structure
            return load_db()

    # --- Data Migration and Integrity Checks ---
    # This section ensures that old database formats are updated to the new one
    # and that all necessary keys are present.

    # Update old structure if needed
    if "stock" in data and isinstance(data["stock"],
                                      dict) and "mlbb" in data["stock"]:
        new_stock = {"MLBBbal": {}, "MLBBph": {}, "PUPG": {}}
        new_prices = {"MLBBbal": {}, "MLBBph": {}, "PUPG": {}}

        # Migrate MLBB codes assuming they are for MLBBbal
        mlbb_codes = data["stock"].get("mlbb", [])
        if mlbb_codes:
            new_stock["MLBBbal"]["1000"] = mlbb_codes
            if "price" in data and data["price"] > 0:
                new_prices["MLBBbal"]["1000"] = data["price"]
            else:
                new_prices["MLBBbal"]["1000"] = 1000

        # Migrate PUBG codes to PUPG
        pubg_codes = data["stock"].get("pubg", [])
        if pubg_codes:
            new_stock["PUPG"]["60"] = pubg_codes
            if "price" in data and data["price"] > 0:
                new_prices["PUPG"]["60"] = data["price"]
            else:
                new_prices["PUPG"]["60"] = 1000

        data["stock"] = new_stock
        data["prices"] = new_prices
        save_db(data) # Save immediately after a big migration

    # Migrate PUBG to PUPG in existing structure
    if "stock" in data and "PUBG" in data["stock"]:
        data["stock"]["PUPG"] = data["stock"].pop("PUBG")
    if "prices" in data and "PUBG" in data["prices"]:
        data["prices"]["PUPG"] = data["prices"].pop("PUBG")

    # Ensure all expected top-level keys exist
    defaults = {
        "users": {},
        "stock": {"MLBBbal": {}, "MLBBph": {}, "PUPG": {}},
        "receipts": {},
        "topup_requests": {},
        "prices": {"MLBBbal": {}, "MLBBph": {}, "PUPG": {}},
        "payment": {
            "Wave": {"phone": "09673585480", "name": "Nine Nine"},
            "KPay": {"phone": "09678786528", "name": "Ma May Phoo Wai"}
        },
        "sales_total": 0,
        "pending_registrations": {}
    }
    for key, default_value in defaults.items():
        if key not in data:
            data[key] = default_value

    # One-time cleanup of old test data, checking keys safely
    if "cleanup_done" not in data:
        if "stock" in data:
            if "MLBBph" in data["stock"]:
                data["stock"]["MLBBph"] = {}
            if "PUPG" in data["stock"]:
                data["stock"]["PUPG"] = {}
        data["cleanup_done"] = True

    return data


def save_db(db):
    with open(DB_FILE, "w") as f:
        json.dump(db, f, indent=2)


db = load_db()


# ---------------- Helpers ----------------
def get_user(uid_str):
    uid = str(uid_str) # Ensure user IDs are always strings for JSON consistency
    if uid not in db["users"]:
        db["users"][uid] = {"balance": 0, "history": [], "approved": False}
        save_db(db)
    return db["users"][uid]


def is_user_approved(uid_str):
    uid = str(uid_str)
    return uid in db["users"] and db["users"][uid].get("approved", False)


def generate_receipt_id():
    while True:
        rid = str(random.randint(100000, 999999))
        if rid not in db["receipts"] and rid not in db["topup_requests"]:
            return rid


def validate_receipt_id(rid):
    return rid.isdigit() and 5 <= len(rid) <= 7 # Allow slightly longer IDs


def get_available_amounts(game_type):
    """Get available amounts for a game type that have stock"""
    amounts = []
    if game_type in db["stock"]:
        for amount, codes in db["stock"][game_type].items():
            if codes:  # Only include amounts that have codes
                amounts.append(amount)
    # Sort amounts numerically, not alphabetically (e.g., 100 before 1000)
    return sorted(amounts, key=lambda x: int(x))


def get_game_display_name(game_type):
    names = {
        "MLBBbal": "Mobile Legends (Bal)",
        "MLBBph": "Mobile Legends (PH)",
        "PUPG": "PUPG Mobile"
    }
    return names.get(game_type, game_type)


# ---------------- User Commands ----------------
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    uid_str = str(user.id)
    # Ensure user exists in DB on start
    get_user(uid_str)

    keyboard = [[
        InlineKeyboardButton("ðŸ“Œ á€¡á€€á€±á€¬á€„á€·á€ºá€–á€½á€„á€·á€ºá€›á€”á€º", callback_data="register")
    ], [InlineKeyboardButton("ðŸ’° á€œá€€á€ºá€€á€»á€”á€ºá€„á€½á€±", callback_data="balance")],
                [InlineKeyboardButton("ðŸ’³ á€„á€½á€±á€–á€¼á€Šá€·á€ºá€›á€”á€º", callback_data="topup")],
                [InlineKeyboardButton("ðŸ›’ á€€á€¯á€’á€ºá€á€šá€ºá€›á€”á€º", callback_data="buy")],
                [InlineKeyboardButton("â„¹ï¸ á€¡á€€á€°á€¡á€Šá€®", callback_data="help")]]
    
    welcome_text = f"ðŸ‘‹ á€™á€„á€ºá€¹á€‚á€œá€¬á€•á€« {user.first_name}! á€€á€¼á€­á€¯á€†á€­á€¯á€•á€«á€á€šá€º!"
    
    if update.message:
        await update.message.reply_text(
            welcome_text, reply_markup=InlineKeyboardMarkup(keyboard))
    elif update.callback_query:
        try:
            await update.callback_query.edit_message_text(
                welcome_text, reply_markup=InlineKeyboardMarkup(keyboard))
        except Exception as e:
            # If edit fails (e.g., message is old), send a new one
            await context.bot.send_message(chat_id=user.id, text=welcome_text, reply_markup=InlineKeyboardMarkup(keyboard))


async def callback_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data
    uid = query.from_user.id

    if data == "start":
        await start(update, context)
        return

    if data == "register":
        if is_user_approved(uid):
            keyboard = [[
                InlineKeyboardButton("ðŸ”™ á€•á€¼á€”á€ºá€žá€½á€¬á€¸á€›á€”á€º", callback_data="start")
            ]]
            await query.edit_message_text(
                "âœ… á€¡á€€á€±á€¬á€„á€·á€ºá€–á€½á€„á€·á€ºá€•á€¼á€®á€¸á€•á€«á€•á€¼á€®á‹",
                reply_markup=InlineKeyboardMarkup(keyboard))
            return
        elif str(uid) in db["pending_registrations"]:
            keyboard = [[
                InlineKeyboardButton("ðŸ”™ á€•á€¼á€”á€ºá€žá€½á€¬á€¸á€›á€”á€º", callback_data="start")
            ]]
            await query.edit_message_text(
                "â³ á€¡á€€á€±á€¬á€„á€·á€ºá€–á€½á€„á€·á€ºá€á€±á€¬á€„á€ºá€¸á€†á€­á€¯á€™á€¾á€¯ á€…á€±á€¬á€„á€·á€ºá€†á€­á€¯á€„á€ºá€¸á€”á€±á€•á€«á€žá€Šá€ºá‹ Admin á€™á€¾ á€œá€€á€ºá€á€¶á€•á€±á€¸á€›á€”á€º á€…á€±á€¬á€„á€·á€ºá€•á€«á‹",
                reply_markup=InlineKeyboardMarkup(keyboard))
            return

        # Create registration request
        db["pending_registrations"][str(uid)] = {
            "user_id": uid,
            "username": query.from_user.first_name,
            "status": "pending"
        }
        save_db(db)

        # Send to admin
        keyboard = [[
            InlineKeyboardButton("âœ… á€œá€€á€ºá€á€¶á€›á€”á€º",
                                 callback_data=f"approve_reg_{uid}"),
            InlineKeyboardButton("âŒ á€„á€¼á€„á€ºá€¸á€•á€šá€ºá€›á€”á€º",
                                 callback_data=f"reject_reg_{uid}")
        ]]
        await context.bot.send_message(
            chat_id=ADMIN_ID,
            text=f"ðŸ“¥ á€¡á€€á€±á€¬á€„á€·á€ºá€–á€½á€„á€·á€ºá€á€±á€¬á€„á€ºá€¸á€†á€­á€¯á€™á€¾á€¯:\n"
            f"ðŸ‘¤ á€¡á€žá€¯á€¶á€¸á€•á€¼á€¯á€žá€° ID: {uid}\n"
            f"ðŸ“ á€¡á€™á€Šá€º: {query.from_user.first_name}\n"
            f"ðŸ‘¤ Username: @{query.from_user.username or 'á€™á€›á€¾á€­'}",
            reply_markup=InlineKeyboardMarkup(keyboard))

        keyboard = [[
            InlineKeyboardButton("ðŸ”™ á€•á€¼á€”á€ºá€žá€½á€¬á€¸á€›á€”á€º", callback_data="start")
        ]]
        await query.edit_message_text(
            "ðŸ“ á€¡á€€á€±á€¬á€„á€·á€ºá€–á€½á€„á€·á€ºá€á€±á€¬á€„á€ºá€¸á€†á€­á€¯á€™á€¾á€¯ Admin á€‘á€¶á€•á€­á€¯á€·á€•á€¼á€®á€¸á€•á€«á€•á€¼á€®á‹ á€…á€±á€¬á€„á€·á€ºá€†á€­á€¯á€„á€ºá€¸á€•á€«á‹",
            reply_markup=InlineKeyboardMarkup(keyboard))

    elif data == "balance":
        if not is_user_approved(uid):
            keyboard = [[
                InlineKeyboardButton("ðŸ”™ á€•á€¼á€”á€ºá€žá€½á€¬á€¸á€›á€”á€º", callback_data="start")
            ]]
            await query.edit_message_text(
                "âš ï¸ á€¡á€€á€±á€¬á€„á€·á€ºá€™á€¾ Admin á€œá€€á€ºá€á€¶á€á€¼á€„á€ºá€¸á€™á€›á€¾á€­á€•á€«á‹ á€¡á€€á€±á€¬á€„á€·á€ºá€–á€½á€„á€·á€ºá€›á€›á€¾á€­á€•á€«á‹",
                reply_markup=InlineKeyboardMarkup(keyboard))
            return

        user = get_user(uid)
        keyboard = []
        # Check if user has enough for any available product
        can_buy = False
        for game_type in db["prices"]:
            for amount, price in db["prices"][game_type].items():
                if amount in db["stock"].get(
                        game_type, {}) and db["stock"][game_type][amount]:
                    if user['balance'] >= price:
                        can_buy = True
                        break

        if not can_buy:
            keyboard.append(
                [InlineKeyboardButton("ðŸ’³ á€„á€½á€±á€–á€¼á€Šá€·á€ºá€›á€”á€º", callback_data="topup")])
        keyboard.append(
            [InlineKeyboardButton("ðŸ”™ á€•á€¼á€”á€ºá€žá€½á€¬á€¸á€›á€”á€º", callback_data="start")])
        await query.edit_message_text(
            f"ðŸ’° á€œá€€á€ºá€€á€»á€”á€ºá€„á€½á€±: {user['balance']} MMK",
            reply_markup=InlineKeyboardMarkup(keyboard))

    elif data == "topup":
        if not is_user_approved(uid):
            keyboard = [[
                InlineKeyboardButton("ðŸ”™ á€•á€¼á€”á€ºá€žá€½á€¬á€¸á€›á€”á€º", callback_data="start")
            ]]
            await query.edit_message_text(
                "âš ï¸ á€¡á€€á€±á€¬á€„á€·á€ºá€™á€¾ Admin á€œá€€á€ºá€á€¶á€á€¼á€„á€ºá€¸á€™á€›á€¾á€­á€•á€«á‹ á€¡á€€á€±á€¬á€„á€·á€ºá€–á€½á€„á€·á€ºá€›á€›á€¾á€­á€•á€«á‹",
                reply_markup=InlineKeyboardMarkup(keyboard))
            return

        keyboard = [
            [InlineKeyboardButton("ðŸ“± Wave", callback_data="topup_Wave")],
            [InlineKeyboardButton("ðŸ“± KPay", callback_data="topup_KPay")],
            [InlineKeyboardButton("ðŸ”™ á€•á€¼á€”á€ºá€žá€½á€¬á€¸á€›á€”á€º", callback_data="start")]
        ]
        await query.edit_message_text(
            "ðŸ’³ á€„á€½á€±á€–á€¼á€Šá€·á€ºá€™á€Šá€·á€ºá€”á€Šá€ºá€¸á€œá€™á€ºá€¸á€›á€½á€±á€¸á€•á€«:",
            reply_markup=InlineKeyboardMarkup(keyboard))

    elif data.startswith("topup_"):
        payment_method = data.split("_")[1] # Wave or KPay
        payment_info = db["payment"].get(payment_method)
        if not payment_info:
            await query.edit_message_text("Payment method not found.")
            return

        context.user_data['topup_method'] = payment_method
        # The copy button logic is clever, let's keep it.
        await query.edit_message_text(
            f"ðŸ’³ {payment_method} á€„á€½á€±á€–á€¼á€Šá€·á€ºá€›á€”á€º:\n\n"
            f"ðŸ“± á€–á€¯á€”á€ºá€¸á€”á€¶á€•á€«á€á€º: `{payment_info['phone']}`\n"
            f"ðŸ‘¤ á€¡á€™á€Šá€º: {payment_info['name']}\n\n"
            f"ðŸ“‹ á€–á€¯á€”á€ºá€¸á€”á€¶á€•á€«á€á€º á€€á€°á€¸á€šá€°á€›á€„á€º á€¡á€±á€¬á€€á€ºá€€ á€á€œá€¯á€á€ºá€”á€¾á€­á€•á€ºá€•á€« á€€á€¼á€Šá€·á€ºá€•á€«á€•á€¼á€®á€¸á‹\n\n"
            f"ðŸ’° á€œá€½á€¾á€²á€•á€¼á€®á€¸á€›á€„á€º á€•á€¼á€±á€…á€¬á€•á€¯á€¶á€¡á€›á€„á€ºá€•á€­á€¯á€·á€•á€«á‹ á€•á€¼á€®á€¸á€›á€„á€º:\n"
            f"â€¢ á€•á€¼á€±á€…á€¬ ID (á€”á€±á€¬á€€á€ºá€†á€¯á€¶á€¸ á…á€œá€¯á€¶á€¸ á€žá€­á€¯á€·á€™á€Ÿá€¯á€á€º á†á€œá€¯á€¶á€¸)\n"
            f"â€¢ á€œá€½á€¾á€²á€á€²á€·á€„á€½á€±á€•á€™á€¬á€\n"
            f"á€›á€±á€¸á€•á€¼á€®á€¸á€•á€­á€¯á€·á€•á€«á‹\n\n"
            f"âš ï¸ á€žá€á€­á€•á€±á€¸á€á€»á€€á€º: á€•á€¼á€±á€…á€¬ ID á€”á€¾á€„á€·á€º á€•á€™á€¬á€á€™á€¾á€¬á€¸á€›á€±á€¸á€™á€­á€›á€„á€º á€„á€½á€±á€†á€¯á€¶á€¸á€•á€«á€™á€Šá€º\n\n"
            f"â° á€„á€½á€±á€œá€½á€¾á€²á€•á€¼á€®á€¸ á…á€™á€­á€”á€…á€ºá€¡á€á€½á€„á€ºá€¸á€•á€­á€¯á€·á€•á€«\n",
            parse_mode='MarkdownV2')

    elif data == "help":
        keyboard = [[
            InlineKeyboardButton("ðŸ”™ á€•á€¼á€”á€ºá€žá€½á€¬á€¸á€›á€”á€º", callback_data="start")
        ]]
        await query.edit_message_text(
            "â„¹ï¸ á€¡á€žá€¯á€¶á€¸á€•á€¼á€¯á€”á€Šá€ºá€¸:\n\n"
            "1ï¸âƒ£ á€¡á€€á€±á€¬á€„á€·á€ºá€–á€½á€„á€·á€ºá€•á€«\n"
            "2ï¸âƒ£ á€œá€€á€ºá€€á€»á€”á€ºá€„á€½á€±á€€á€¼á€Šá€·á€ºá€•á€«\n"
            "3ï¸âƒ£ á€„á€½á€±á€–á€¼á€Šá€·á€ºá€•á€«\n"
            "4ï¸âƒ£ á€€á€¯á€’á€ºá€á€šá€ºá€šá€°á€•á€«\n\n"
            "ðŸ“Œ á€œá€±á€·á€œá€¬á€›á€”á€º:\n"
            "â€¢ Admin á€™á€¾ á€œá€€á€ºá€á€¶á€•á€¼á€®á€¸á€™á€¾ á€€á€¯á€’á€ºá€›á€›á€¾á€­á€•á€«á€™á€Šá€º\n"
            "â€¢ á€á€šá€ºá€šá€°á€™á€¾á€¯á€™á€¾á€á€ºá€á€™á€ºá€¸á€žá€­á€™á€ºá€¸á€†á€Šá€ºá€¸á€•á€«á€™á€Šá€º\n"
            "â€¢ á€•á€¼á€±á€…á€¬á€”á€²á€·á€á€šá€ºá€›á€„á€º Admin á€œá€€á€ºá€á€¶á€•á€¼á€®á€¸á€™á€¾ á€€á€¯á€’á€ºá€›á€›á€¾á€­á€™á€Šá€º\n"
            "â€¢ á€œá€€á€ºá€€á€»á€”á€ºá€„á€½á€±á€”á€²á€·á€á€šá€ºá€›á€„á€º á€á€»á€€á€ºá€á€»á€„á€ºá€¸á€›á€›á€¾á€­á€™á€Šá€º",
            reply_markup=InlineKeyboardMarkup(keyboard))

    elif data == "buy":
        if not is_user_approved(uid):
            keyboard = [[
                InlineKeyboardButton("ðŸ”™ á€•á€¼á€”á€ºá€žá€½á€¬á€¸á€›á€”á€º", callback_data="start")
            ]]
            await query.edit_message_text(
                "âš ï¸ á€¡á€€á€±á€¬á€„á€·á€ºá€™á€¾ Admin á€œá€€á€ºá€á€¶á€á€¼á€„á€ºá€¸á€™á€›á€¾á€­á€•á€«á‹ á€¡á€€á€±á€¬á€„á€·á€ºá€–á€½á€„á€·á€ºá€›á€›á€¾á€­á€•á€«á‹",
                reply_markup=InlineKeyboardMarkup(keyboard))
            return

        # Show available game types
        keyboard = []
        available_games = False

        for game_type in ["MLBBbal", "MLBBph", "PUPG"]:
            # Check if there is any stock for this game type at all
            total_codes = sum(len(codes) for codes in db["stock"].get(game_type, {}).values())
            if total_codes > 0:
                game_name = get_game_display_name(game_type)
                keyboard.append([
                    InlineKeyboardButton(
                        f"ðŸŽ® {game_name} ({total_codes})",
                        callback_data=f"select_{game_type}")
                ])
                available_games = True

        if not available_games:
            keyboard = [[
                InlineKeyboardButton("ðŸ”™ á€•á€¼á€”á€ºá€žá€½á€¬á€¸á€›á€”á€º", callback_data="start")
            ]]
            await query.edit_message_text(
                "âš ï¸ á€œá€±á€¬á€œá€±á€¬á€†á€šá€º á€€á€¯á€’á€ºá€™á€›á€¾á€­á€•á€«á‹",
                reply_markup=InlineKeyboardMarkup(keyboard))
            return

        keyboard.append(
            [InlineKeyboardButton("ðŸ”™ á€•á€¼á€”á€ºá€žá€½á€¬á€¸á€›á€”á€º", callback_data="start")])
        await query.edit_message_text(
            "ðŸŽ® á€‚á€­á€™á€ºá€¸á€¡á€™á€»á€­á€¯á€¸á€¡á€…á€¬á€¸á€›á€½á€±á€¸á€•á€«:",
            reply_markup=InlineKeyboardMarkup(keyboard))

    elif data.startswith("select_"):
        game_type = data.split("_")[1]
        amounts = get_available_amounts(game_type)

        if not amounts:
            keyboard = [[
                InlineKeyboardButton("ðŸ”™ á€•á€¼á€”á€ºá€žá€½á€¬á€¸á€›á€”á€º", callback_data="buy")
            ]]
            await query.edit_message_text(
                "âš ï¸ á€’á€®á€‚á€­á€™á€ºá€¸á€¡á€á€½á€€á€º á€€á€¯á€’á€ºá€™á€›á€¾á€­á€•á€«á‹",
                reply_markup=InlineKeyboardMarkup(keyboard))
            return

        keyboard = []
        game_name = get_game_display_name(game_type)

        for amount in amounts:
            codes_count = len(db["stock"][game_type][amount])
            price = db["prices"][game_type].get(amount, "N/A")
            unit = "Coin" if "MLBB" in game_type else "UC"
            keyboard.append([
                InlineKeyboardButton(
                    f"ðŸ’Ž {amount} {unit} - {price} MMK ({codes_count})",
                    callback_data=f"amount_{game_type}_{amount}")
            ])

        keyboard.append(
            [InlineKeyboardButton("ðŸ”™ á€•á€¼á€”á€ºá€žá€½á€¬á€¸á€›á€”á€º", callback_data="buy")])
        await query.edit_message_text(
            f"ðŸŽ® {game_name}\nðŸ’Ž á€¡á€›á€±á€¡á€á€½á€€á€ºá€›á€½á€±á€¸á€•á€«:",
            reply_markup=InlineKeyboardMarkup(keyboard))

    elif data.startswith("amount_"):
        parts = data.split("_")
        game_type = parts[1]
        amount = parts[2]

        if amount not in db["stock"].get(
                game_type, {}) or not db["stock"][game_type][amount]:
            keyboard = [[
                InlineKeyboardButton("ðŸ”™ á€•á€¼á€”á€ºá€žá€½á€¬á€¸á€›á€”á€º",
                                     callback_data=f"select_{game_type}")
            ]]
            await query.edit_message_text(
                "âš ï¸ á€’á€®á€•á€™á€¬á€á€¡á€á€½á€€á€º á€€á€¯á€’á€ºá€™á€›á€¾á€­á€•á€«á‹",
                reply_markup=InlineKeyboardMarkup(keyboard))
            return

        price = db["prices"][game_type].get(amount, 0)
        user = get_user(uid)
        max_quantity = len(db["stock"][game_type][amount])

        # Store selection data for text input
        context.user_data['selecting_quantity'] = {
            'game_type': game_type,
            'amount': amount,
            'price': price,
            'max_quantity': max_quantity
        }

        keyboard = [[
            InlineKeyboardButton("ðŸ”™ á€•á€¼á€”á€ºá€žá€½á€¬á€¸á€›á€”á€º",
                                 callback_data=f"select_{game_type}")
        ]]

        game_name = get_game_display_name(game_type)
        unit = "Coin" if "MLBB" in game_type else "UC"
        await query.edit_message_text(
            f"ðŸŽ® {game_name}\n"
            f"ðŸ’Ž {amount} {unit}\n"
            f"ðŸ’° á€…á€»á€±á€¸á€”á€¾á€¯á€”á€ºá€¸: {price} MMK/á€€á€¯á€’á€º\n"
            f"ðŸ’³ á€œá€€á€ºá€€á€»á€”á€ºá€„á€½á€±: {user['balance']} MMK\n"
            f"ðŸ“¦ á€›á€›á€¾á€­á€”á€­á€¯á€„á€ºá€žá€±á€¬ á€€á€¯á€’á€º: {max_quantity} á€á€¯\n\n"
            f"ðŸ“ á€œá€­á€¯á€á€»á€„á€ºá€žá€±á€¬ á€€á€¯á€’á€ºá€¡á€›á€±á€¡á€á€½á€€á€º á€›á€±á€¸á€•á€­á€¯á€·á€•á€« (1 á€™á€¾ {max_quantity} á€¡á€á€½á€„á€ºá€¸):",
            reply_markup=InlineKeyboardMarkup(keyboard))
    
    # FIX 1: This entire block is unreachable because the `amount_` callback
    # asks for text input, which is handled by `handle_message`.
    # It has been removed.
    # elif data.startswith("quantity_"):
    #    ... (REMOVED) ...

    elif data.startswith("buy_balance_"):
        parts = data.split("_")
        game_type = parts[2]
        amount = parts[3]
        quantity = int(parts[4])

        user = get_user(uid)
        price = db["prices"][game_type].get(amount, 0)
        total_price = price * quantity

        if user["balance"] < total_price:
            keyboard = [[
                InlineKeyboardButton("ðŸ’³ á€„á€½á€±á€–á€¼á€Šá€·á€ºá€›á€”á€º", callback_data="topup")
            ],
                        [
                            InlineKeyboardButton(
                                "ðŸ”™ á€•á€¼á€”á€ºá€žá€½á€¬á€¸á€›á€”á€º",
                                callback_data=
                                f"select_{game_type}")
                        ]]
            await query.edit_message_text(
                "âš ï¸ á€œá€€á€ºá€€á€»á€”á€ºá€„á€½á€±á€™á€œá€¯á€¶á€œá€±á€¬á€€á€ºá€•á€«á‹",
                reply_markup=InlineKeyboardMarkup(keyboard))
            return

        # Double-check stock before processing
        if len(db["stock"].get(game_type, {}).get(amount, [])) < quantity:
            keyboard = [[
                InlineKeyboardButton("ðŸ”™ á€•á€¼á€”á€ºá€žá€½á€¬á€¸á€›á€”á€º", callback_data="buy")
            ]]
            await query.edit_message_text(
                "âš ï¸ á€œá€¯á€¶á€œá€±á€¬á€€á€ºá€žá€±á€¬ á€€á€¯á€’á€ºá€™á€›á€¾á€­á€•á€«á‹ á€¡á€±á€¬á€€á€ºá€•á€«á€¡á€á€»á€€á€ºá€¡á€œá€€á€º á€›á€±á€¬á€„á€ºá€¸á€…á€¬á€¸á€›á€”á€º á€á€»á€á€¯á€¸á€•á€«á‹",
                reply_markup=InlineKeyboardMarkup(keyboard))
            return

        # Get codes
        codes = []
        for _ in range(quantity):
            if db["stock"][game_type][amount]:
                codes.append(db["stock"][game_type][amount].pop(0))

        user["balance"] -= total_price
        db["sales_total"] += total_price
        game_name = get_game_display_name(game_type)
        unit = "Coin" if "MLBB" in game_type else "UC"

        user["history"].append({
            "type": "balance_purchase",
            "codes": codes,
            "game": game_name,
            "amount": amount,
            "quantity": quantity,
            "total_price": total_price,
            "timestamp": asyncio.get_event_loop().time()
        })
        save_db(db)

        codes_text = "\n".join([f"`{code}`" for code in codes]) # Use code formatting for easy copy
        keyboard = [[
            InlineKeyboardButton("ðŸ”™ á€•á€¼á€”á€ºá€žá€½á€¬á€¸á€›á€”á€º", callback_data="start")
        ]]
        await query.edit_message_text(
            f"âœ… á€á€šá€ºá€šá€°á€™á€¾á€¯á€¡á€±á€¬á€„á€ºá€™á€¼á€„á€ºá€•á€«á€•á€¼á€®!\n\n"
            f"ðŸŽ® {game_name}\n"
            f"ðŸ’Ž {amount} {unit} x {quantity}\n"
            f"ðŸ’° á€…á€¯á€…á€¯á€•á€±á€«á€„á€ºá€¸: {total_price} MMK\n\n"
            f"ðŸ”‘ á€€á€¯á€’á€ºá€™á€»á€¬á€¸:\n{codes_text}\n\n"
            f"ðŸ’³ á€œá€€á€ºá€€á€»á€”á€ºá€„á€½á€±: {user['balance']} MMK",
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode='MarkdownV2')

    elif data.startswith("buy_receipt_"):
        parts = data.split("_")
        game_type = parts[2]
        amount = parts[3]
        quantity = int(parts[4])

        context.user_data['buying_game'] = game_type
        context.user_data['buying_amount'] = amount
        context.user_data['buying_quantity'] = quantity
        context.user_data['receipt_step'] = 'photo'

        keyboard = [[
            InlineKeyboardButton(
                "ðŸ”™ á€•á€¼á€”á€ºá€žá€½á€¬á€¸á€›á€”á€º",
                callback_data=f"select_{game_type}")
        ]]
        await query.edit_message_text(
            "ðŸ“„ á€•á€¼á€±á€…á€¬á€”á€²á€·á€á€šá€ºá€šá€°á€›á€”á€º:\n\n"
            "1ï¸âƒ£ á€•á€¼á€±á€…á€¬á€•á€¯á€¶á€¡á€›á€„á€ºá€•á€­á€¯á€·á€•á€«\n"
            "2ï¸âƒ£ á€•á€¼á€®á€¸á€›á€„á€º á€•á€¼á€±á€…á€¬ ID (á€”á€±á€¬á€€á€ºá€†á€¯á€¶á€¸ á…á€œá€¯á€¶á€¸ á€žá€­á€¯á€·á€™á€Ÿá€¯á€á€º á†á€œá€¯á€¶á€¸) á€›á€±á€¸á€•á€­á€¯á€·á€•á€«\n\n"
            "âš ï¸ á€žá€á€­á€•á€±á€¸á€á€»á€€á€º: á€•á€¼á€±á€…á€¬ ID á€™á€¾á€¬á€¸á€›á€±á€¸á€™á€­á€›á€„á€º á€„á€½á€±á€†á€¯á€¶á€¸á€•á€«á€™á€Šá€º",
            reply_markup=InlineKeyboardMarkup(keyboard))

    # Admin approval handlers
    elif data.startswith("message_topup_"):
        if uid != ADMIN_ID: return
        receipt_id = data.split("_")[2]
        if receipt_id not in db["topup_requests"]:
            await query.edit_message_text("âš ï¸ á€„á€½á€±á€–á€¼á€Šá€·á€ºá€á€±á€¬á€„á€ºá€¸á€†á€­á€¯á€™á€¾á€¯á€™á€á€½á€±á€·á€•á€«á‹")
            return
        request = db["topup_requests"][receipt_id]
        user_id = request["user_id"]
        context.user_data['admin_messaging'] = {'user_id': user_id}
        await query.edit_message_text(f"ðŸ’¬ Replying to user {user_id}. Send your message:")

    elif data.startswith("message_") and not data.startswith("message_topup_"):
        if uid != ADMIN_ID: return
        receipt_id = data.split("_")[1]
        if receipt_id not in db["receipts"]:
            await query.edit_message_text("âš ï¸ á€•á€¼á€±á€…á€¬á€™á€á€½á€±á€·á€•á€«á‹")
            return
        receipt = db["receipts"][receipt_id]
        user_id = receipt["user_id"]
        context.user_data['admin_messaging'] = {'user_id': user_id}
        await query.edit_message_text(f"ðŸ’¬ Replying to user {user_id}. Send your message:")

    elif data.startswith("approve_topup_") or data.startswith("reject_topup_"):
        if uid != ADMIN_ID: return
        action, _, receipt_id = data.partition("_topup_")
        if receipt_id not in db["topup_requests"]:
            await query.edit_message_text("âš ï¸ Top-up request not found or already processed.")
            return

        request = db["topup_requests"].pop(receipt_id) # Remove after processing
        user_id = request["user_id"]
        amount = request["amount"]
        user = get_user(user_id)

        if action == "approve":
            user["balance"] += amount
            await context.bot.send_message(
                user_id,
                f"âœ… Your top-up of {amount} MMK has been approved!\nNew Balance: {user['balance']} MMK"
            )
            await query.edit_message_text(f"âœ… Approved top-up for {user_id} by {amount} MMK.")
        else: # reject
            await context.bot.send_message(user_id, f"âŒ Your top-up request ({receipt_id}) has been rejected. Please contact an admin if you think this is a mistake.")
            await query.edit_message_text(f"âŒ Rejected top-up for {user_id}.")
        save_db(db)

    elif data.startswith("approve_reg_") or data.startswith("reject_reg_"):
        if uid != ADMIN_ID: return
        action, _, user_id_str = data.partition("_reg_")
        user_id = int(user_id_str)

        if user_id_str not in db["pending_registrations"]:
            await query.edit_message_text("âš ï¸ Registration request not found or already processed.")
            return

        request_info = db["pending_registrations"].pop(user_id_str) # Remove after processing
        
        if action == "approve":
            user = get_user(user_id)
            user["approved"] = True
            await context.bot.send_message(user_id, "âœ… Your registration has been approved! You can now use the bot.")
            await query.edit_message_text(f"âœ… Approved registration for {request_info.get('username', user_id)} ({user_id}).")
        else: # reject
            # Optional: remove user entry if you don't want to keep unapproved users
            if user_id_str in db["users"]:
                del db["users"][user_id_str]
            await context.bot.send_message(user_id, "âŒ Your registration has been rejected.")
            await query.edit_message_text(f"âŒ Rejected registration for {request_info.get('username', user_id)} ({user_id}).")
        save_db(db)

    elif data.startswith("approve_") or data.startswith("reject_"):
        if uid != ADMIN_ID: return
        action, receipt_id = data.split("_", 1)
        if receipt_id not in db["receipts"]:
            await query.edit_message_text("âš ï¸ Receipt not found or already processed.")
            return

        receipt = db["receipts"].pop(receipt_id) # Remove after processing
        user_id = receipt["user_id"]
        game_type = receipt["game_type"]
        amount = receipt["amount"]
        quantity = receipt["quantity"]
        user = get_user(user_id)

        if action == "approve":
            if len(db["stock"].get(game_type, {}).get(amount, [])) < quantity:
                await query.edit_message_text("âš ï¸ Not enough stock to approve this request!")
                db["receipts"][receipt_id] = receipt # Put it back
                return

            codes = [db["stock"][game_type][amount].pop(0) for _ in range(quantity)]
            total_price = db["prices"][game_type].get(amount, 0) * quantity
            db["sales_total"] += total_price
            game_name = get_game_display_name(game_type)
            unit = "Coin" if "MLBB" in game_type else "UC"

            user["history"].append({
                "type": "receipt_purchase",
                "codes": codes,
                "receipt": receipt_id,
                "game": game_name,
                "amount": amount,
                "quantity": quantity,
                "timestamp": asyncio.get_event_loop().time()
            })
            
            codes_text = "\n".join([f"`{code}`" for code in codes])
            await context.bot.send_message(
                user_id, f"âœ… Your purchase has been approved!\n\n"
                f"ðŸŽ® {game_name}\n"
                f"ðŸ’Ž {amount} {unit} x {quantity}\n\n"
                f"ðŸ”‘ Your codes:\n{codes_text}",
                parse_mode='MarkdownV2')
            await query.edit_message_text(f"âœ… Approved receipt {receipt_id} for user {user_id}.")
        else: # reject
            await context.bot.send_message(user_id, f"âŒ Your purchase with receipt ID {receipt_id} has been rejected.")
            await query.edit_message_text(f"âŒ Rejected receipt {receipt_id} for user {user_id}.")
        save_db(db)


    elif data.startswith("addstock_"):
        if uid != ADMIN_ID: return
        game_type = data.split("_")[1]
        context.user_data['addstock_game'] = game_type
        game_name = get_game_display_name(game_type)
        unit = "Coin" if "MLBB" in game_type else "UC"
        await query.edit_message_text(
            f"ðŸŽ® Adding stock for {game_name}.\n\n"
            f"ðŸ“ Send message in format:\n`<amount> <price> <code1> <code2> ...`\n\n"
            f"Example: `1000 2500 CODE123 CODE456`\n\n"
            f"ðŸ’¡ Send the {unit} amount, price per code, and then all the codes separated by spaces.",
            parse_mode='MarkdownV2')


# ---------------- Message Handler ----------------
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # Ignore messages from channels or groups unless it's the admin
    if update.effective_chat.id != update.effective_user.id and update.effective_user.id != ADMIN_ID:
        return

    uid = update.message.from_user.id
    
    # Handle photos first
    if update.message.photo:
        # Handle topup photos
        if 'topup_method' in context.user_data:
            context.user_data['topup_photo_sent'] = True
            context.user_data['topup_photo_message_id'] = update.message.message_id
            await update.message.reply_text(
                "ðŸ“„ Photo received. Now, please send the transaction ID and the amount in one message.\n\n"
                "Format: `<Transaction ID> <Amount>`\n"
                "Example: `987654 50000`",
                parse_mode='MarkdownV2')
            return

        # Handle receipt purchase photos
        elif 'buying_game' in context.user_data and context.user_data.get('receipt_step') == 'photo':
            context.user_data['receipt_photo_sent'] = True
            context.user_data['receipt_photo_message_id'] = update.message.message_id
            context.user_data['receipt_step'] = 'id'
            await update.message.reply_text(
                "ðŸ“„ Photo received. Now, please send the transaction ID for this purchase.",
            )
            return

    # Handle text messages
    if not update.message.text:
        return

    text = update.message.text.strip()

    # Handle admin replying to a user
    if uid == ADMIN_ID and 'admin_messaging' in context.user_data:
        target_user = context.user_data['admin_messaging']['user_id']
        try:
            await context.bot.send_message(target_user, f"ðŸ“© A message from the Admin:\n\n{text}")
            await update.message.reply_text(f"âœ… Message sent to user {target_user}.")
        except Exception as e:
            await update.message.reply_text(f"âŒ Could not send message to {target_user}. Error: {e}")
        del context.user_data['admin_messaging']
        return

    # Handle user typing quantity for a purchase
    if 'selecting_quantity' in context.user_data:
        try:
            quantity = int(text)
            selection = context.user_data['selecting_quantity']

            if not 1 <= quantity <= selection['max_quantity']:
                await update.message.reply_text(f"âš ï¸ Invalid quantity. Please enter a number between 1 and {selection['max_quantity']}.")
                return

            # This logic is what the old `quantity_` callback was for.
            # It's correctly placed here.
            game_type = selection['game_type']
            amount = selection['amount']
            price = selection['price']
            total_price = price * quantity
            user = get_user(uid)

            keyboard = []
            if user["balance"] >= total_price:
                keyboard.append([
                    InlineKeyboardButton(f"ðŸ’° Pay with Balance ({total_price} MMK)",
                        callback_data=f"buy_balance_{game_type}_{amount}_{quantity}")
                ])
            else:
                keyboard.append([InlineKeyboardButton("ðŸ’³ Top-Up Balance", callback_data="topup")])

            keyboard.append([InlineKeyboardButton("ðŸ“„ Pay with New Receipt",
                    callback_data=f"buy_receipt_{game_type}_{amount}_{quantity}")])
            keyboard.append([InlineKeyboardButton("ðŸ”™ Cancel", callback_data=f"select_{game_type}")])

            game_name = get_game_display_name(game_type)
            unit = "Coin" if "MLBB" in game_type else "UC"
            await update.message.reply_text(
                f"ðŸŽ® {game_name}\n"
                f"ðŸ’Ž {amount} {unit} x {quantity}\n"
                f"ðŸ’° Total Price: {total_price} MMK\n"
                f"ðŸ’³ Your Balance: {user['balance']} MMK\n\n"
                f"Please choose your payment method:",
                reply_markup=InlineKeyboardMarkup(keyboard))
            
            del context.user_data['selecting_quantity'] # Clean up state
            return
        except ValueError:
            await update.message.reply_text("âš ï¸ That doesn't look like a valid number. Please try again.")
            return

    # Handle admin adding stock via text
    if uid == ADMIN_ID and 'addstock_game' in context.user_data:
        try:
            parts = text.split()
            if len(parts) < 3:
                await update.message.reply_text("âš ï¸ Invalid format. Usage: `<amount> <price> <code1> <code2> ...`", parse_mode='MarkdownV2')
                return

            game_type = context.user_data['addstock_game']
            amount = parts[0]
            price = int(parts[1])
            codes = parts[2:]

            if game_type not in db["stock"]: db["stock"][game_type] = {}
            if amount not in db["stock"][game_type]: db["stock"][game_type][amount] = []
            db["stock"][game_type][amount].extend(codes)

            if game_type not in db["prices"]: db["prices"][game_type] = {}
            db["prices"][game_type][amount] = price
            save_db(db)

            game_name = get_game_display_name(game_type)
            await update.message.reply_text(f"âœ… Success!\nAdded {len(codes)} codes for {game_name} ({amount}) at {price} MMK each.")
            del context.user_data['addstock_game']
            return
        except ValueError:
            await update.message.reply_text("âš ï¸ The price must be a valid number.")
            return
        except Exception as e:
            await update.message.reply_text(f"An error occurred: {e}")
            return

    # Handle user submitting topup details (ID and amount)
    if context.user_data.get('topup_photo_sent'):
        try:
            parts = text.split()
            if len(parts) != 2:
                await update.message.reply_text("âš ï¸ Invalid format. Please send: `<Transaction ID> <Amount>`", parse_mode='MarkdownV2')
                return

            receipt_id = parts[0]
            amount = int(parts[1])

            if not validate_receipt_id(receipt_id):
                await update.message.reply_text("âš ï¸ The transaction ID seems invalid. It should be 5-7 digits.")
                return

            if amount < 1000:
                await update.message.reply_text("âš ï¸ Minimum top-up amount is 1000 MMK.")
                return

            payment_method = context.user_data['topup_method']
            photo_message_id = context.user_data['topup_photo_message_id']
            # We use the user-provided receipt ID now
            db["topup_requests"][receipt_id] = {
                "user_id": uid, "status": "pending", "amount": amount, "payment_method": payment_method
            }
            save_db(db)

            keyboard = [[
                InlineKeyboardButton("âœ… Approve", callback_data=f"approve_topup_{receipt_id}"),
                InlineKeyboardButton("ðŸ’¬ Message User", callback_data=f"message_topup_{receipt_id}"),
                InlineKeyboardButton("âŒ Reject", callback_data=f"reject_topup_{receipt_id}")
            ]]

            # Forward the photo to the admin
            await context.bot.forward_message(
                chat_id=ADMIN_ID, from_chat_id=update.message.chat.id, message_id=photo_message_id
            )
            # Send the details in a separate message
            await context.bot.send_message(
                chat_id=ADMIN_ID,
                text=f"ðŸ“¥ New Top-Up Request:\n\n"
                f"ðŸ‘¤ User: {update.message.from_user.first_name} (`{uid}`)\n"
                f"ðŸ’³ Method: {payment_method}\n"
                f"ðŸ“„ Transaction ID: `{receipt_id}`\n"
                f"ðŸ’° Amount: {amount} MMK",
                reply_markup=InlineKeyboardMarkup(keyboard),
                parse_mode='MarkdownV2'
            )
            await update.message.reply_text("â³ Your top-up request has been submitted and is pending admin approval. Thank you!")
            
            # Clean up user_data
            for key in ['topup_method', 'topup_photo_sent', 'topup_photo_message_id']:
                if key in context.user_data: del context.user_data[key]
            return
        except ValueError:
            await update.message.reply_text("âš ï¸ The amount must be a valid number.")
            return
        except Exception as e:
            await update.message.reply_text(f"An error occurred: {e}")
            return

    # Handle user submitting receipt ID for a purchase
    if 'buying_game' in context.user_data and context.user_data.get('receipt_step') == 'id':
        receipt_id = text
        if not validate_receipt_id(receipt_id):
            await update.message.reply_text("âš ï¸ Invalid transaction ID. It should be 5-7 digits long. Please send a valid ID.")
            return

        game_type = context.user_data['buying_game']
        amount = context.user_data['buying_amount']
        quantity = context.user_data['buying_quantity']
        photo_message_id = context.user_data['receipt_photo_message_id']

        db["receipts"][receipt_id] = {
            "user_id": uid, "status": "pending", "game_type": game_type, "amount": amount, "quantity": quantity
        }
        save_db(db)

        game_name = get_game_display_name(game_type)
        unit = "Coin" if "MLBB" in game_type else "UC"
        keyboard = [[
            InlineKeyboardButton("âœ… Approve", callback_data=f"approve_{receipt_id}"),
            InlineKeyboardButton("ðŸ’¬ Message User", callback_data=f"message_{receipt_id}"),
            InlineKeyboardButton("âŒ Reject", callback_data=f"reject_{receipt_id}")
        ]]

        await context.bot.forward_message(
            chat_id=ADMIN_ID, from_chat_id=update.message.chat.id, message_id=photo_message_id
        )
        await context.bot.send_message(
            chat_id=ADMIN_ID,
            text=f"ðŸ“¥ New Purchase via Receipt:\n\n"
            f"ðŸ‘¤ User: {update.message.from_user.first_name} (`{uid}`)\n"
            f"ðŸŽ® Game: {game_name}\n"
            f"ðŸ’Ž Item: {amount} {unit} x {quantity}\n"
            f"ðŸ“„ Transaction ID: `{receipt_id}`",
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode='MarkdownV2'
        )
        await update.message.reply_text("â³ Your purchase request has been submitted and is pending admin approval. Thank you!")

        # Clean up user_data
        for key in ['buying_game', 'buying_amount', 'buying_quantity', 'receipt_photo_sent', 'receipt_photo_message_id', 'receipt_step']:
            if key in context.user_data: del context.user_data[key]
        return


# ---------------- Admin Commands ----------------
async def setbalance(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID: return
    try:
        args = context.args
        uid = int(args[0])
        amount = int(args[1])
        user = get_user(uid)
        user["balance"] = amount
        save_db(db)
        await update.message.reply_text(f"âœ… User {uid}'s balance set to {amount} MMK.")
    except (IndexError, ValueError):
        await update.message.reply_text("Usage: /setbalance <user_id> <amount>")


async def addstock(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID: return
    keyboard = [[
        InlineKeyboardButton("ðŸŽ® Mobile Legends (Bal)", callback_data="addstock_MLBBbal")
    ], [
        InlineKeyboardButton("ðŸŽ® Mobile Legends (PH)", callback_data="addstock_MLBBph")
    ], [
        InlineKeyboardButton("ðŸŽ® PUPG Mobile", callback_data="addstock_PUPG")
    ]]
    await update.message.reply_text("ðŸŽ® Select game to add stock for:", reply_markup=InlineKeyboardMarkup(keyboard))


async def delstock(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID: return
    try:
        game_type, amount, code_to_delete = context.args[0], context.args[1], context.args[2]
        if game_type not in ["MLBBbal", "MLBBph", "PUPG"]:
            await update.message.reply_text("Invalid game type. Use MLBBbal, MLBBph, or PUPG.")
            return

        if code_to_delete in db["stock"].get(game_type, {}).get(amount, []):
            db["stock"][game_type][amount].remove(code_to_delete)
            save_db(db)
            await update.message.reply_text(f"âœ… Code `{code_to_delete}` removed from {game_type} ({amount}).", parse_mode='MarkdownV2')
        else:
            await update.message.reply_text("âš ï¸ Code not found in the specified stock.")
    except (IndexError, ValueError):
        await update.message.reply_text("Usage: /delstock <MLBBbal/MLBBph/PUPG> <amount> <code>")


async def setprice(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID: return
    try:
        game_type, amount, price_str = context.args[0], context.args[1], context.args[2]
        price = int(price_str)
        if game_type not in ["MLBBbal", "MLBBph", "PUPG"]:
            await update.message.reply_text("Invalid game type. Use MLBBbal, MLBBph, or PUPG.")
            return

        if game_type not in db["prices"]: db["prices"][game_type] = {}
        db["prices"][game_type][amount] = price
        save_db(db)
        await update.message.reply_text(f"âœ… Price for {game_type} ({amount}) set to {price} MMK.")
    except (IndexError, ValueError):
        await update.message.reply_text("Usage: /setprice <MLBBbal/MLBBph/PUPG> <amount> <price>")


async def setpayment(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID: return
    try:
        method = context.args[0].title()
        phone = context.args[1]
        name = " ".join(context.args[2:])
        if method not in ["Wave", "Kpay"]:
            await update.message.reply_text("Usage: Method must be `Wave` or `Kpay`.")
            return
        db["payment"][method] = {"phone": phone, "name": name}
        save_db(db)
        await update.message.reply_text(f"âœ… {method} payment info updated.")
    except IndexError:
        await update.message.reply_text("Usage: /setpayment <Wave/KPay> <phone> <name>")


async def viewhistory(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID: return
    try:
        uid = int(context.args[0])
        user = get_user(uid)
        if not user["history"]:
            await update.message.reply_text(f"User {uid} has no transaction history.")
            return

        history_text = f"ðŸ“œ History for User {uid}:\n\n"
        for i, h in enumerate(user["history"], 1):
            history_text += f"{i}. Type: {h.get('type', 'N/A')}, Game: {h.get('game', 'N/A')}, Qty: {h.get('quantity', 'N/A')}\n"
        await update.message.reply_text(history_text)
    except (IndexError, ValueError):
        await update.message.reply_text("Usage: /viewhistory <user_id>")


async def admhelp(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID: return
    
    mlbbbal_count = sum(len(codes) for codes in db["stock"].get("MLBBbal", {}).values())
    mlbbph_count = sum(len(codes) for codes in db["stock"].get("MLBBph", {}).values())
    pupg_count = sum(len(codes) for codes in db["stock"].get("PUPG", {}).values())
    total_orders = sum(len(u.get("history", [])) for u in db["users"].values())
    total_user_balance = sum(u.get("balance", 0) for u in db["users"].values())
    pending_receipts = len([r for r_id, r in db["receipts"].items() if r.get("status") == "pending"])
    pending_topups = len([r for r_id, r in db["topup_requests"].items() if r.get("status") == "pending"])
    pending_registrations = len(db.get("pending_registrations", {}))

    help_text = f"""
ðŸ”§ *Admin Panel* ðŸ”§

*Commands:*
`/setbalance <id> <amt>` \- Set user balance
`/addstock` \- Interactively add new codes
`/delstock <game> <amt> <code>` \- Delete one code
`/setprice <game> <amt> <price>` \- Set item price
`/setpayment <Wave/Kpay> <phone> <name>` \- Update payment info
`/viewhistory <id>` \- See a user's purchase history
`/admhelp` \- Show this panel

*ðŸ“Š Bot Statistics:*
ðŸŽ® MLBB Bal Stock: `{mlbbbal_count}`
ðŸŽ® MLBB PH Stock: `{mlbbph_count}`
ðŸŽ® PUPG Stock: `{pupg_count}`
ðŸ‘¥ Approved Users: `{len(db["users"])}`
ðŸ“¦ Total Orders: `{total_orders}`
ðŸ’° Total User Balance: `{total_user_balance:,}` MMK
ðŸ’µ Total Sales: `{db.get('sales_total', 0):,}` MMK

*â³ Pending Queues:*
ðŸ“„ Purchase Receipts: `{pending_receipts}`
ðŸ’³ Top\-Up Requests: `{pending_topups}`
ðŸ“Œ Registrations: `{pending_registrations}`
    """
    await update.message.reply_text(help_text, parse_mode='MarkdownV2')


# ---------------- Main ----------------
def main():
    app = Application.builder().token(BOT_TOKEN).build()
    
    # User handlers
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(callback_handler))
    app.add_handler(MessageHandler(filters.TEXT | filters.PHOTO & ~filters.COMMAND, handle_message))

    # Admin command handlers
    app.add_handler(CommandHandler("setbalance", setbalance))
    app.add_handler(CommandHandler("addstock", addstock))
    app.add_handler(CommandHandler("delstock", delstock))
    app.add_handler(CommandHandler("setprice", setprice))
    app.add_handler(CommandHandler("setpayment", setpayment))
    app.add_handler(CommandHandler("viewhistory", viewhistory))
    app.add_handler(CommandHandler("admhelp", admhelp))

    print("Bot is running...")
    app.run_polling()


if __name__ == "__main__":
    main()
