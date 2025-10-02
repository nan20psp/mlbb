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
ADMIN_ID = int(os.getenv("ADMIN_ID", "7669567524"))

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
            "sales_total": 0
        }
    with open(DB_FILE, "r") as f:
        data = json.load(f)

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
        save_db(data)

    # Migrate PUBG to PUPG in existing structure
    if "stock" in data and "PUBG" in data["stock"]:
        data["stock"]["PUPG"] = data["stock"].pop("PUBG")
    if "prices" in data and "PUBG" in data["prices"]:
        data["prices"]["PUPG"] = data["prices"].pop("PUBG")

    # Ensure all expected keys exist
    if "stock" not in data:
        data["stock"] = {"MLBBbal": {}, "MLBBph": {}, "PUPG": {}}
    if "prices" not in data:
        data["prices"] = {"MLBBbal": {}, "MLBBph": {}, "PUPG": {}}
    if "topup_requests" not in data: data["topup_requests"] = {}
    if "users" not in data: data["users"] = {}
    if "payment" not in data:
        data["payment"] = {
            "Wave": {
                "phone": "09673585480",
                "name": "Nine Nine"
            },
            "Kpay": {
                "phone": "09678786528",
                "name": "Ma May Phoo Wai"
            }
        }
    if "sales_total" not in data: data["sales_total"] = 0
    if "pending_registrations" not in data: data["pending_registrations"] = {}

    # Clear old codes from MLBBph and PUPG (one-time cleanup)
    if "cleanup_done" not in data:
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
def get_user(uid):
    if uid not in db["users"]:
        db["users"][uid] = {"balance": 0, "history": [], "approved": False}
        save_db(db)
    return db["users"][uid]


def is_user_approved(uid):
    return uid in db["users"] and db["users"][uid].get("approved", False)


def generate_receipt_id():
    while True:
        rid = str(random.randint(10000, 999999))
        if rid not in db["receipts"] and rid not in db["topup_requests"]:
            return rid


def validate_receipt_id(rid):
    return rid.isdigit() and 5 <= len(rid) <= 6


def get_available_amounts(game_type):
    """Get available amounts for a game type that have stock"""
    amounts = []
    if game_type in db["stock"]:
        for amount, codes in db["stock"][game_type].items():
            if codes:  # Only include amounts that have codes
                amounts.append(amount)
    return sorted(amounts)


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
    keyboard = [[
        InlineKeyboardButton("ðŸ“Œ á€¡á€€á€±á€¬á€„á€·á€ºá€–á€½á€„á€·á€ºá€›á€”á€º", callback_data="register")
    ], [InlineKeyboardButton("ðŸ’° á€œá€€á€ºá€€á€»á€”á€ºá€„á€½á€±", callback_data="balance")],
                [InlineKeyboardButton("ðŸ’³ á€„á€½á€±á€–á€¼á€Šá€·á€ºá€›á€”á€º", callback_data="topup")],
                [InlineKeyboardButton("ðŸ›’ á€€á€¯á€’á€ºá€á€šá€ºá€›á€”á€º", callback_data="buy")],
                [InlineKeyboardButton("â„¹ï¸ á€¡á€€á€°á€¡á€Šá€®", callback_data="help")]]
    if update.message:
        await update.message.reply_text(
            f"ðŸ‘‹ á€™á€„á€ºá€¹á€‚á€œá€¬á€•á€« {user.first_name}! á€€á€¼á€­á€¯á€†á€­á€¯á€•á€«á€á€šá€º!",
            reply_markup=InlineKeyboardMarkup(keyboard))
    else:
        await update.callback_query.edit_message_text(
            f"ðŸ‘‹ á€™á€„á€ºá€¹á€‚á€œá€¬á€•á€« {user.first_name}! á€€á€¼á€­á€¯á€†á€­á€¯á€•á€«á€á€šá€º!",
            reply_markup=InlineKeyboardMarkup(keyboard))


async def callback_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data
    uid = query.from_user.id

    if data == "start":
        await start(update, context)
        return

    if data == "register":
        if uid in db["users"] and db["users"][uid].get("approved", False):
            keyboard = [[
                InlineKeyboardButton("ðŸ”™ á€•á€¼á€”á€ºá€žá€½á€¬á€¸á€›á€”á€º", callback_data="start")
            ]]
            await query.edit_message_text(
                "âœ… á€¡á€€á€±á€¬á€„á€·á€ºá€–á€½á€„á€·á€ºá€•á€¼á€®á€¸á€•á€«á€•á€¼á€®á‹",
                reply_markup=InlineKeyboardMarkup(keyboard))
            return
        elif uid in db["pending_registrations"]:
            keyboard = [[
                InlineKeyboardButton("ðŸ”™ á€•á€¼á€”á€ºá€žá€½á€¬á€¸á€›á€”á€º", callback_data="start")
            ]]
            await query.edit_message_text(
                "â³ á€¡á€€á€±á€¬á€„á€·á€ºá€–á€½á€„á€·á€ºá€á€±á€¬á€„á€ºá€¸á€†á€­á€¯á€™á€¾á€¯ á€…á€±á€¬á€„á€·á€ºá€†á€­á€¯á€„á€ºá€¸á€”á€±á€•á€«á€žá€Šá€ºá‹ Admin á€™á€¾ á€œá€€á€ºá€á€¶á€•á€±á€¸á€›á€”á€º á€…á€±á€¬á€„á€·á€ºá€•á€«á‹",
                reply_markup=InlineKeyboardMarkup(keyboard))
            return

        # Create registration request
        db["pending_registrations"][uid] = {
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
                "âš ï¸ á€¡á€€á€±á€¬á€„á€·á€ºá€™á€¾ Admin á€œá€€á€ºá€á€¶á€á€¼á€„á€ºá€¸á€™á€›á€¾á€­á€•á€«á‹",
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
                "âš ï¸ á€¡á€€á€±á€¬á€„á€·á€ºá€™á€¾ Admin á€œá€€á€ºá€á€¶á€á€¼á€„á€ºá€¸á€™á€›á€¾á€­á€•á€«á‹",
                reply_markup=InlineKeyboardMarkup(keyboard))
            return

        keyboard = [
            [InlineKeyboardButton("ðŸ“± Wave", callback_data="topup_wave")],
            [InlineKeyboardButton("ðŸ“± Kpay", callback_data="topup_kpay")],
            [InlineKeyboardButton("ðŸ”™ á€•á€¼á€”á€ºá€žá€½á€¬á€¸á€›á€”á€º", callback_data="start")]
        ]
        await query.edit_message_text(
            "ðŸ’³ á€„á€½á€±á€–á€¼á€Šá€·á€ºá€™á€Šá€·á€ºá€”á€Šá€ºá€¸á€œá€™á€ºá€¸á€›á€½á€±á€¸á€•á€«:",
            reply_markup=InlineKeyboardMarkup(keyboard))

    elif data.startswith("topup_"):
        payment_method = data.split("_")[1].title()
        payment_info = db["payment"][payment_method]

        context.user_data['topup_method'] = payment_method
        keyboard = [[
            InlineKeyboardButton(f"ðŸ“‹ {payment_info['phone']}",
                                 callback_data=f"copy_{payment_info['phone']}")
        ], [InlineKeyboardButton("ðŸ”™ á€•á€¼á€”á€ºá€žá€½á€¬á€¸á€›á€”á€º", callback_data="topup")]]

        await query.edit_message_text(
            f"ðŸ’³ {payment_method} á€„á€½á€±á€–á€¼á€Šá€·á€ºá€›á€”á€º:\n\n"
            f"ðŸ“± á€–á€¯á€”á€ºá€¸á€”á€¶á€•á€«á€á€º: {payment_info['phone']}\n"
            f"ðŸ‘¤ á€¡á€™á€Šá€º: {payment_info['name']}\n\n"
            f"ðŸ“‹ á€–á€¯á€”á€ºá€¸á€”á€¶á€•á€«á€á€ºá€€á€°á€¸á€šá€°á€›á€”á€º á€¡á€±á€¬á€€á€ºá€€ á€á€œá€¯á€á€ºá€”á€¾á€­á€•á€ºá€•á€«:\n\n"
            f"ðŸ’° á€œá€½á€¾á€²á€•á€¼á€®á€¸á€›á€„á€º á€•á€¼á€±á€…á€¬á€•á€¯á€¶á€¡á€›á€„á€ºá€•á€­á€¯á€·á€•á€«á‹ á€•á€¼á€®á€¸á€›á€„á€º:\n"
            f"â€¢ á€•á€¼á€±á€…á€¬ ID (á€”á€±á€¬á€€á€ºá€†á€¯á€¶á€¸ á…á€œá€¯á€¶á€¸ á€žá€­á€¯á€·á€™á€Ÿá€¯á€á€º á†á€œá€¯á€¶á€¸)\n"
            f"â€¢ á€œá€½á€¾á€²á€á€²á€·á€„á€½á€±á€•á€™á€¬á€\n"
            f"á€›á€±á€¸á€•á€¼á€®á€¸á€•á€­á€¯á€·á€•á€«á‹\n\n"
            f"âš ï¸ á€žá€á€­á€•á€±á€¸á€á€»á€€á€º: á€•á€¼á€±á€…á€¬ ID á€”á€¾á€„á€·á€º á€•á€™á€¬á€á€™á€¾á€¬á€¸á€›á€±á€¸á€™á€­á€›á€„á€º á€„á€½á€±á€†á€¯á€¶á€¸á€•á€«á€™á€Šá€º\n\n"
            f"â° á€„á€½á€±á€œá€½á€¾á€²á€•á€¼á€®á€¸ á…á€™á€­á€”á€…á€ºá€¡á€á€½á€„á€ºá€¸á€•á€­á€¯á€·á€•á€«\n"
            f"â„¹ï¸ KPay á€„á€½á€±á€œá€½á€¾á€²á€žá€°á€€á€­á€¯ á€™á€­á€™á€­á€¡á€€á€±á€¬á€„á€·á€ºá€›á€²á€· KPay á€¡á€™á€Šá€ºá€‘á€Šá€·á€ºá€›á€±á€¸á€•á€±á€¸á€•á€«",
            reply_markup=InlineKeyboardMarkup(keyboard))

    elif data.startswith("copy_"):
        phone_number = data.split("_", 1)[1]
        # Send the phone number as a separate message for easier copying
        await context.bot.send_message(chat_id=query.from_user.id,
                                       text=phone_number)
        await query.answer(
            f"ðŸ“‹ {phone_number} á€•á€­á€¯á€·á€•á€¼á€®á€¸á€•á€«á€•á€¼á€®! á€¡á€•á€±á€«á€ºá€€ á€‚á€á€”á€ºá€¸á€€á€­á€¯ á€€á€°á€¸á€šá€°á€•á€«!",
            show_alert=True)

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
                "âš ï¸ á€¡á€€á€±á€¬á€„á€·á€ºá€™á€¾ Admin á€œá€€á€ºá€á€¶á€á€¼á€„á€ºá€¸á€™á€›á€¾á€­á€•á€«á‹",
                reply_markup=InlineKeyboardMarkup(keyboard))
            return

        # Show available game types
        keyboard = []
        available_games = []

        for game_type in ["MLBBbal", "MLBBph", "PUPG"]:
            amounts = get_available_amounts(game_type)
            if amounts:
                total_codes = sum(
                    len(codes)
                    for codes in db["stock"].get(game_type, {}).values())
                if total_codes > 0:
                    game_name = get_game_display_name(game_type)
                    keyboard.append([
                        InlineKeyboardButton(
                            f"ðŸŽ® {game_name} ({total_codes})",
                            callback_data=f"select_{game_type}")
                    ])
                    available_games.append(game_type)

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
            price = db["prices"][game_type].get(amount, 0)
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
            f"ðŸ“ á€œá€­á€¯á€á€»á€„á€ºá€žá€±á€¬ á€€á€¯á€’á€ºá€¡á€›á€±á€¡á€á€½á€€á€º á€›á€±á€¸á€•á€­á€¯á€·á€•á€« (1 to {max_quantity}):",
            reply_markup=InlineKeyboardMarkup(keyboard))

    elif data.startswith("quantity_"):
        parts = data.split("_")
        game_type = parts[1]
        amount = parts[2]
        quantity = int(parts[3])

        price = db["prices"][game_type].get(amount, 0)
        total_price = price * quantity
        user = get_user(uid)

        keyboard = []
        if user["balance"] >= total_price:
            keyboard.append([
                InlineKeyboardButton(
                    f"ðŸ’° á€œá€€á€ºá€€á€»á€”á€ºá€„á€½á€±á€”á€²á€·á€á€šá€ºá€›á€”á€º ({total_price} MMK)",
                    callback_data=f"buy_balance_{game_type}_{amount}_{quantity}"
                )
            ])
        else:
            keyboard.append(
                [InlineKeyboardButton("ðŸ’³ á€„á€½á€±á€–á€¼á€Šá€·á€ºá€›á€”á€º", callback_data="topup")])

        keyboard.append([
            InlineKeyboardButton(
                "ðŸ“„ á€•á€¼á€±á€…á€¬á€”á€²á€·á€á€šá€ºá€›á€”á€º",
                callback_data=f"buy_receipt_{game_type}_{amount}_{quantity}")
        ])
        keyboard.append([
            InlineKeyboardButton("ðŸ”™ á€•á€¼á€”á€ºá€žá€½á€¬á€¸á€›á€”á€º",
                                 callback_data=f"amount_{game_type}_{amount}")
        ])

        game_name = get_game_display_name(game_type)
        unit = "Coin" if "MLBB" in game_type else "UC"
        await query.edit_message_text(
            f"ðŸŽ® {game_name}\n"
            f"ðŸ’Ž {amount} {unit} x {quantity}\n"
            f"ðŸ’° á€…á€¯á€…á€¯á€•á€±á€«á€„á€ºá€¸: {total_price} MMK\n"
            f"ðŸ’³ á€œá€€á€ºá€€á€»á€”á€ºá€„á€½á€±: {user['balance']} MMK\n\n"
            f"ðŸ’³ á€„á€½á€±á€•á€±á€¸á€á€»á€±á€™á€¾á€¯á€”á€Šá€ºá€¸á€œá€™á€ºá€¸á€›á€½á€±á€¸á€•á€«:",
            reply_markup=InlineKeyboardMarkup(keyboard))

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
                                f"quantity_{game_type}_{amount}_{quantity}")
                        ]]
            await query.edit_message_text(
                "âš ï¸ á€œá€€á€ºá€€á€»á€”á€ºá€„á€½á€±á€™á€œá€¯á€¶á€œá€±á€¬á€€á€ºá€•á€«á‹",
                reply_markup=InlineKeyboardMarkup(keyboard))
            return

        if len(db["stock"][game_type][amount]) < quantity:
            keyboard = [[
                InlineKeyboardButton("ðŸ”™ á€•á€¼á€”á€ºá€žá€½á€¬á€¸á€›á€”á€º", callback_data="buy")
            ]]
            await query.edit_message_text(
                "âš ï¸ á€œá€¯á€¶á€œá€±á€¬á€€á€ºá€žá€±á€¬ á€€á€¯á€’á€ºá€™á€›á€¾á€­á€•á€«á‹",
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
            "type": "balance",
            "codes": codes,
            "game": game_name,
            "amount": amount,
            "quantity": quantity,
            "total_price": total_price
        })
        save_db(db)

        codes_text = "\n".join([f"ðŸ”‘ {code}" for code in codes])
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
            reply_markup=InlineKeyboardMarkup(keyboard))

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
                callback_data=f"quantity_{game_type}_{amount}_{quantity}")
        ]]
        await query.edit_message_text(
            "ðŸ“„ á€•á€¼á€±á€…á€¬á€”á€²á€·á€á€šá€ºá€šá€°á€›á€”á€º:\n\n"
            "1ï¸âƒ£ á€•á€¼á€±á€…á€¬á€•á€¯á€¶á€¡á€›á€„á€ºá€•á€­á€¯á€·á€•á€«\n"
            "2ï¸âƒ£ á€•á€¼á€®á€¸á€›á€„á€º á€•á€¼á€±á€…á€¬ ID (á€”á€±á€¬á€€á€ºá€†á€¯á€¶á€¸ á…á€œá€¯á€¶á€¸ á€žá€­á€¯á€·á€™á€Ÿá€¯á€á€º á†á€œá€¯á€¶á€¸) á€›á€±á€¸á€•á€­á€¯á€·á€•á€«\n\n"
            "âš ï¸ á€žá€á€­á€•á€±á€¸á€á€»á€€á€º: á€•á€¼á€±á€…á€¬ ID á€™á€¾á€¬á€¸á€›á€±á€¸á€™á€­á€›á€„á€º á€„á€½á€±á€†á€¯á€¶á€¸á€•á€«á€™á€Šá€º",
            reply_markup=InlineKeyboardMarkup(keyboard))

    # Admin approval handlers
    elif data.startswith("message_topup_"):
        if uid != ADMIN_ID:
            await query.edit_message_text(
                "âš ï¸ Admin á€žá€¬á€œá€»á€¾á€„á€º á€’á€®á€¡á€›á€¬á€€á€­á€¯á€œá€¯á€•á€ºá€”á€­á€¯á€„á€ºá€•á€«á€žá€Šá€ºá‹")
            return

        receipt_id = data.split("_")[2]
        if receipt_id not in db["topup_requests"]:
            await query.edit_message_text("âš ï¸ á€„á€½á€±á€–á€¼á€Šá€·á€ºá€á€±á€¬á€„á€ºá€¸á€†á€­á€¯á€™á€¾á€¯á€™á€á€½á€±á€·á€•á€«á‹")
            return

        request = db["topup_requests"][receipt_id]
        user_id = request["user_id"]
        context.user_data['admin_messaging'] = {'user_id': user_id}
        await query.edit_message_text("ðŸ’¬ á€¡á€žá€¯á€¶á€¸á€•á€¼á€¯á€žá€°á€‘á€¶á€•á€­á€¯á€·á€œá€­á€¯á€žá€±á€¬á€…á€¬á€€á€­á€¯ á€›á€±á€¸á€•á€«:")

    elif data.startswith("message_") and not data.startswith("message_topup_"):
        if uid != ADMIN_ID:
            await query.edit_message_text(
                "âš ï¸ Admin á€žá€¬á€œá€»á€¾á€„á€º á€’á€®á€¡á€›á€¬á€€á€­á€¯á€œá€¯á€•á€ºá€”á€­á€¯á€„á€ºá€•á€«á€žá€Šá€ºá‹")
            return

        receipt_id = data.split("_")[1]
        if receipt_id not in db["receipts"]:
            await query.edit_message_text("âš ï¸ á€•á€¼á€±á€…á€¬á€™á€á€½á€±á€·á€•á€«á‹")
            return

        receipt = db["receipts"][receipt_id]
        user_id = receipt["user_id"]
        context.user_data['admin_messaging'] = {'user_id': user_id}
        await query.edit_message_text("ðŸ’¬ á€¡á€žá€¯á€¶á€¸á€•á€¼á€¯á€žá€°á€‘á€¶á€•á€­á€¯á€·á€œá€­á€¯á€žá€±á€¬á€…á€¬á€€á€­á€¯ á€›á€±á€¸á€•á€«:")

    elif data.startswith("approve_topup_") or data.startswith("reject_topup_"):
        if uid != ADMIN_ID:
            await query.edit_message_text(
                "âš ï¸ Admin á€žá€¬á€œá€»á€¾á€„á€º á€’á€®á€¡á€›á€¬á€€á€­á€¯á€œá€¯á€•á€ºá€”á€­á€¯á€„á€ºá€•á€«á€žá€Šá€ºá‹")
            return

        action, _, receipt_id = data.split("_")
        if receipt_id not in db["topup_requests"]:
            await query.edit_message_text("âš ï¸ á€„á€½á€±á€–á€¼á€Šá€·á€ºá€á€±á€¬á€„á€ºá€¸á€†á€­á€¯á€™á€¾á€¯á€™á€á€½á€±á€·á€•á€«á‹")
            return

        request = db["topup_requests"][receipt_id]
        user_id = request["user_id"]
        amount = request["amount"]
        user = get_user(user_id)

        if action == "approve":
            user["balance"] += amount
            request["status"] = "approved"
            save_db(db)
            await context.bot.send_message(
                user_id,
                f"âœ… á€„á€½á€±á€–á€¼á€Šá€·á€ºá€™á€¾á€¯ á€œá€€á€ºá€á€¶á€•á€¼á€®á€¸á€•á€«á€•á€¼á€®!\nðŸ’° á€„á€½á€±á€•á€™á€¬á€: {amount} MMK\nðŸ’³ á€œá€€á€ºá€€á€»á€”á€ºá€„á€½á€±: {user['balance']} MMK"
            )
            await query.edit_message_text(
                f"âœ… á€„á€½á€±á€–á€¼á€Šá€·á€ºá€™á€¾á€¯ {receipt_id} á€œá€€á€ºá€á€¶á€•á€¼á€®á€¸")
        else:
            request["status"] = "rejected"
            save_db(db)
            await context.bot.send_message(user_id,
                                           "âŒ á€„á€½á€±á€–á€¼á€Šá€·á€ºá€™á€¾á€¯ á€„á€¼á€„á€ºá€¸á€•á€šá€ºá€á€¶á€›á€•á€«á€žá€Šá€ºá‹")
            await query.edit_message_text(
                f"âŒ á€„á€½á€±á€–á€¼á€Šá€·á€ºá€™á€¾á€¯ {receipt_id} á€„á€¼á€„á€ºá€¸á€•á€šá€ºá€•á€¼á€®á€¸")

    elif data.startswith("approve_reg_") or data.startswith("reject_reg_"):
        if uid != ADMIN_ID:
            await query.edit_message_text(
                "âš ï¸ Admin á€žá€¬á€œá€»á€¾á€„á€º á€’á€®á€¡á€›á€¬á€€á€­á€¯á€œá€¯á€•á€ºá€”á€­á€¯á€„á€ºá€•á€«á€žá€Šá€ºá‹")
            return

        action, _, user_id = data.split("_")
        user_id = int(user_id)

        if user_id not in db["pending_registrations"]:
            await query.edit_message_text("âš ï¸ á€¡á€€á€±á€¬á€„á€·á€ºá€–á€½á€„á€·á€ºá€á€±á€¬á€„á€ºá€¸á€†á€­á€¯á€™á€¾á€¯á€™á€á€½á€±á€·á€•á€«á‹"
                                          )
            return

        if action == "approve":
            # Create approved user account
            db["users"][user_id] = {
                "balance": 0,
                "history": [],
                "approved": True
            }
            del db["pending_registrations"][user_id]
            save_db(db)

            await context.bot.send_message(
                user_id,
                "âœ… á€¡á€€á€±á€¬á€„á€·á€ºá€–á€½á€„á€·á€ºá€™á€¾á€¯ á€œá€€á€ºá€á€¶á€•á€¼á€®á€¸á€•á€«á€•á€¼á€®! á€šá€á€¯ bot á€€á€­á€¯ á€¡á€žá€¯á€¶á€¸á€•á€¼á€¯á€”á€­á€¯á€„á€ºá€•á€«á€•á€¼á€®á‹"
            )
            await query.edit_message_text(
                f"âœ… á€¡á€žá€¯á€¶á€¸á€•á€¼á€¯á€žá€° {user_id} á á€¡á€€á€±á€¬á€„á€·á€ºá€–á€½á€„á€·á€ºá€™á€¾á€¯ á€œá€€á€ºá€á€¶á€•á€¼á€®á€¸")
        else:
            del db["pending_registrations"][user_id]
            save_db(db)
            await context.bot.send_message(
                user_id, "âŒ á€¡á€€á€±á€¬á€„á€·á€ºá€–á€½á€„á€·á€ºá€™á€¾á€¯ á€„á€¼á€„á€ºá€¸á€•á€šá€ºá€á€¶á€›á€•á€«á€žá€Šá€ºá‹")
            await query.edit_message_text(
                f"âŒ á€¡á€žá€¯á€¶á€¸á€•á€¼á€¯á€žá€° {user_id} á á€¡á€€á€±á€¬á€„á€·á€ºá€–á€½á€„á€·á€ºá€™á€¾á€¯ á€„á€¼á€„á€ºá€¸á€•á€šá€ºá€•á€¼á€®á€¸")

    elif data.startswith("approve_") or data.startswith("reject_"):
        if uid != ADMIN_ID:
            await query.edit_message_text(
                "âš ï¸ Admin á€žá€¬á€œá€»á€¾á€„á€º á€’á€®á€¡á€›á€¬á€€á€­á€¯á€œá€¯á€•á€ºá€”á€­á€¯á€„á€ºá€•á€«á€žá€Šá€ºá‹")
            return

        action, receipt_id = data.split("_")
        if receipt_id not in db["receipts"]:
            await query.edit_message_text("âš ï¸ á€•á€¼á€±á€…á€¬á€™á€á€½á€±á€·á€•á€«á‹")
            return

        receipt = db["receipts"][receipt_id]
        user_id = receipt["user_id"]
        game_type = receipt["game_type"]
        amount = receipt["amount"]
        quantity = receipt["quantity"]
        user = get_user(user_id)

        if action == "approve":
            if len(db["stock"][game_type].get(amount, [])) < quantity:
                await query.edit_message_text("âš ï¸ á€œá€¯á€¶á€œá€±á€¬á€€á€ºá€žá€±á€¬ á€€á€¯á€’á€ºá€™á€›á€¾á€­á€•á€«á‹")
                return

            codes = []
            for _ in range(quantity):
                if db["stock"][game_type][amount]:
                    codes.append(db["stock"][game_type][amount].pop(0))

            total_price = db["prices"][game_type].get(amount, 0) * quantity
            db["sales_total"] += total_price
            game_name = get_game_display_name(game_type)
            unit = "Coin" if "MLBB" in game_type else "UC"

            user["history"].append({
                "type": "receipt",
                "codes": codes,
                "receipt": receipt_id,
                "game": game_name,
                "amount": amount,
                "quantity": quantity
            })
            receipt["status"] = "approved"
            save_db(db)

            codes_text = "\n".join([f"ðŸ”‘ {code}" for code in codes])
            await context.bot.send_message(
                user_id, f"âœ… á€•á€¼á€±á€…á€¬á€”á€²á€·á€á€šá€ºá€šá€°á€™á€¾á€¯ á€œá€€á€ºá€á€¶á€•á€¼á€®á€¸á€•á€«á€•á€¼á€®!\n\n"
                f"ðŸŽ® {game_name}\n"
                f"ðŸ’Ž {amount} {unit} x {quantity}\n\n"
                f"ðŸ”‘ á€€á€¯á€’á€ºá€™á€»á€¬á€¸:\n{codes_text}")
            await query.edit_message_text(f"âœ… á€•á€¼á€±á€…á€¬ {receipt_id} á€œá€€á€ºá€á€¶á€•á€¼á€®á€¸")
        else:
            receipt["status"] = "rejected"
            save_db(db)
            await context.bot.send_message(
                user_id, "âŒ á€•á€¼á€±á€…á€¬á€”á€²á€·á€á€šá€ºá€šá€°á€™á€¾á€¯ á€„á€¼á€„á€ºá€¸á€•á€šá€ºá€á€¶á€›á€•á€«á€žá€Šá€ºá‹")
            await query.edit_message_text(f"âŒ á€•á€¼á€±á€…á€¬ {receipt_id} á€„á€¼á€„á€ºá€¸á€•á€šá€ºá€•á€¼á€®á€¸")

    # Admin addstock interactive handlers
    elif data.startswith("addstock_"):
        if uid != ADMIN_ID:
            await query.edit_message_text(
                "âš ï¸ Admin á€žá€¬á€œá€»á€¾á€„á€º á€’á€®á€¡á€›á€¬á€€á€­á€¯á€œá€¯á€•á€ºá€”á€­á€¯á€„á€ºá€•á€«á€žá€Šá€ºá‹")
            return

        game_type = data.split("_")[1]
        context.user_data['addstock_game'] = game_type

        keyboard = [[
            InlineKeyboardButton("ðŸ”™ á€•á€¼á€”á€ºá€žá€½á€¬á€¸á€›á€”á€º", callback_data="start")
        ]]
        game_name = get_game_display_name(game_type)
        unit = "Coin" if "MLBB" in game_type else "UC"
        await query.edit_message_text(
            f"ðŸŽ® {game_name} á€¡á€á€½á€€á€º á€€á€¯á€’á€ºá€‘á€Šá€·á€ºá€›á€”á€º:\n\n"
            f"ðŸ“ á€–á€±á€¬á€ºá€™á€á€º: <amount> <price> <code1> <code2> ...\n"
            f"á€¥á€•á€™á€¬: 1000 2500 CODE123 CODE456\n\n"
            f"ðŸ’¡ {unit} á€•á€™á€¬á€, á€…á€»á€±á€¸á€”á€¾á€¯á€”á€ºá€¸, á€•á€¼á€®á€¸á€›á€„á€º á€€á€¯á€’á€ºá€™á€»á€¬á€¸á€•á€­á€¯á€·á€•á€«:",
            reply_markup=InlineKeyboardMarkup(keyboard))


# ---------------- Receipt/Image text handler ----------------
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.message.from_user.id
    user = get_user(uid)

    # Handle photos
    if update.message.photo:
        # Handle topup photos
        if 'topup_method' in context.user_data:
            context.user_data['topup_photo_sent'] = True
            context.user_data[
                'topup_photo_message_id'] = update.message.message_id

            await update.message.reply_text(
                "ðŸ“„ á€•á€¼á€±á€…á€¬á€•á€¯á€¶á€›á€›á€¾á€­á€•á€¼á€®á€¸á‹ á€¡á€±á€¬á€€á€ºá€•á€«á€¡á€á€»á€€á€ºá€¡á€œá€€á€ºá€™á€»á€¬á€¸á€•á€­á€¯á€·á€•á€«:\n\n"
                "ðŸ“ á€–á€±á€¬á€ºá€™á€á€º: <á€•á€¼á€±á€…á€¬ ID (á€”á€±á€¬á€€á€ºá€†á€¯á€¶á€¸ á…á€œá€¯á€¶á€¸ á€žá€­á€¯á€·á€™á€Ÿá€¯á€á€º á†á€œá€¯á€¶á€¸)> <á€„á€½á€±á€•á€™á€¬á€>\n"
                "á€¥á€•á€™á€¬: 123456 50000\n\n"
                "âš ï¸ á€žá€á€­á€•á€±á€¸á€á€»á€€á€º: á€•á€¼á€±á€…á€¬ ID á€”á€¾á€„á€·á€º á€•á€™á€¬á€á€™á€¾á€¬á€¸á€›á€±á€¸á€™á€­á€›á€„á€º á€„á€½á€±á€†á€¯á€¶á€¸á€•á€«á€™á€Šá€º")
            return

        # Handle receipt purchase photos
        elif 'buying_game' in context.user_data and context.user_data.get(
                'receipt_step') == 'photo':
            context.user_data['receipt_photo_sent'] = True
            context.user_data[
                'receipt_photo_message_id'] = update.message.message_id
            context.user_data['receipt_step'] = 'id'

            await update.message.reply_text(
                "ðŸ“„ á€•á€¼á€±á€…á€¬á€•á€¯á€¶á€›á€›á€¾á€­á€•á€¼á€®á€¸á‹ á€šá€á€¯ á€•á€¼á€±á€…á€¬ ID (á€”á€±á€¬á€€á€ºá€†á€¯á€¶á€¸ á…á€œá€¯á€¶á€¸ á€žá€­á€¯á€·á€™á€Ÿá€¯á€á€º á†á€œá€¯á€¶á€¸) á€›á€±á€¸á€•á€­á€¯á€·á€•á€«:\n\n"
                "á€¥á€•á€™á€¬: 123456\n\n"
                "âš ï¸ á€žá€á€­á€•á€±á€¸á€á€»á€€á€º: á€•á€¼á€±á€…á€¬ ID á€™á€¾á€¬á€¸á€›á€±á€¸á€™á€­á€›á€„á€º á€„á€½á€±á€†á€¯á€¶á€¸á€•á€«á€™á€Šá€º")
            return

    # Handle text messages
    if update.message.text:
        text = update.message.text.strip()

        # Handle admin message sending
        if uid == ADMIN_ID and 'admin_messaging' in context.user_data:
            target_user = context.user_data['admin_messaging']['user_id']
            await context.bot.send_message(target_user,
                                           f"ðŸ“© Admin á€™á€¾ á€…á€¬:\n{text}")
            await update.message.reply_text(
                f"âœ… á€¡á€žá€¯á€¶á€¸á€•á€¼á€¯á€žá€° {target_user} á€‘á€¶ á€…á€¬á€•á€­á€¯á€·á€•á€¼á€®á€¸")
            del context.user_data['admin_messaging']
            return

        # Handle quantity selection
        if 'selecting_quantity' in context.user_data:
            try:
                quantity = int(text)
                selection = context.user_data['selecting_quantity']

                if quantity < 1 or quantity > selection['max_quantity']:
                    await update.message.reply_text(
                        f"âš ï¸ á€€á€¯á€’á€ºá€¡á€›á€±á€¡á€á€½á€€á€ºá€žá€Šá€º 1 á€™á€¾ {selection['max_quantity']} á€¡á€á€½á€„á€ºá€¸á€–á€¼á€…á€ºá€›á€™á€Šá€ºá‹"
                    )
                    return

                game_type = selection['game_type']
                amount = selection['amount']
                price = selection['price']
                total_price = price * quantity
                user = get_user(uid)

                keyboard = []
                if user["balance"] >= total_price:
                    keyboard.append([
                        InlineKeyboardButton(
                            f"ðŸ’° á€œá€€á€ºá€€á€»á€”á€ºá€„á€½á€±á€”á€²á€·á€á€šá€ºá€›á€”á€º ({total_price} MMK)",
                            callback_data=
                            f"buy_balance_{game_type}_{amount}_{quantity}")
                    ])
                else:
                    keyboard.append([
                        InlineKeyboardButton("ðŸ’³ á€„á€½á€±á€–á€¼á€Šá€·á€ºá€›á€”á€º",
                                             callback_data="topup")
                    ])

                keyboard.append([
                    InlineKeyboardButton(
                        "ðŸ“„ á€•á€¼á€±á€…á€¬á€”á€²á€·á€á€šá€ºá€›á€”á€º",
                        callback_data=
                        f"buy_receipt_{game_type}_{amount}_{quantity}")
                ])
                keyboard.append([
                    InlineKeyboardButton(
                        "ðŸ”™ á€•á€¼á€”á€ºá€žá€½á€¬á€¸á€›á€”á€º",
                        callback_data=f"amount_{game_type}_{amount}")
                ])

                game_name = get_game_display_name(game_type)
                unit = "Coin" if "MLBB" in game_type else "UC"
                await update.message.reply_text(
                    f"ðŸŽ® {game_name}\n"
                    f"ðŸ’Ž {amount} {unit} x {quantity}\n"
                    f"ðŸ’° á€…á€¯á€…á€¯á€•á€±á€«á€„á€ºá€¸: {total_price} MMK\n"
                    f"ðŸ’³ á€œá€€á€ºá€€á€»á€”á€ºá€„á€½á€±: {user['balance']} MMK\n\n"
                    f"ðŸ’³ á€„á€½á€±á€•á€±á€¸á€á€»á€±á€™á€¾á€¯á€”á€Šá€ºá€¸á€œá€™á€ºá€¸á€›á€½á€±á€¸á€•á€«:",
                    reply_markup=InlineKeyboardMarkup(keyboard))
                del context.user_data['selecting_quantity']
                return
            except ValueError:
                await update.message.reply_text("âš ï¸ á€€á€»á€±á€¸á€‡á€°á€¸á€•á€¼á€¯á á€‚á€á€”á€ºá€¸á€žá€¬á€›á€±á€¸á€•á€«á‹")
                return

        # Handle admin addstock
        if uid == ADMIN_ID and 'addstock_game' in context.user_data:
            try:
                parts = text.split()
                if len(parts) < 3:
                    await update.message.reply_text(
                        "âš ï¸ á€¡á€”á€Šá€ºá€¸á€†á€¯á€¶á€¸: <amount> <price> <code1>")
                    return

                game_type = context.user_data['addstock_game']
                amount = parts[0]
                price = int(parts[1])
                codes = parts[2:]

                # Update stock
                if game_type not in db["stock"]:
                    db["stock"][game_type] = {}
                if amount not in db["stock"][game_type]:
                    db["stock"][game_type][amount] = []
                db["stock"][game_type][amount].extend(codes)

                # Update price
                if game_type not in db["prices"]:
                    db["prices"][game_type] = {}
                db["prices"][game_type][amount] = price

                save_db(db)

                game_name = get_game_display_name(game_type)
                unit = "Coin" if "MLBB" in game_type else "UC"
                await update.message.reply_text(
                    f"âœ… {game_name} {amount} {unit}\n"
                    f"ðŸ’° á€…á€»á€±á€¸á€”á€¾á€¯á€”á€ºá€¸: {price} MMK\n"
                    f"ðŸ“¦ á€€á€¯á€’á€º: {len(codes)} á€á€¯ á€‘á€Šá€·á€ºá€•á€¼á€®á€¸")
                del context.user_data['addstock_game']
                return
            except ValueError:
                await update.message.reply_text("âš ï¸ á€…á€»á€±á€¸á€”á€¾á€¯á€”á€ºá€¸á€™á€¾á€¬á€¸á€šá€½á€„á€ºá€¸á€•á€«á€žá€Šá€ºá‹")
                return
            except:
                await update.message.reply_text("âš ï¸ á€–á€±á€¬á€ºá€™á€á€ºá€™á€¾á€¬á€¸á€šá€½á€„á€ºá€¸á€•á€«á€žá€Šá€ºá‹")
                return

        # Handle topup with receipt ID and amount
        if context.user_data.get('topup_photo_sent'):
            try:
                parts = text.split()
                if len(parts) != 2:
                    await update.message.reply_text(
                        "âš ï¸ á€–á€±á€¬á€ºá€™á€á€º: <á€•á€¼á€±á€…á€¬ ID> <á€„á€½á€±á€•á€™á€¬á€>")
                    return

                receipt_id = parts[0]
                amount = int(parts[1])

                if not validate_receipt_id(receipt_id):
                    await update.message.reply_text(
                        "âš ï¸ á€•á€¼á€±á€…á€¬ ID á€žá€Šá€º á…-á†á€œá€¯á€¶á€¸ á€‚á€á€”á€ºá€¸á€–á€¼á€…á€ºá€›á€™á€Šá€ºá‹")
                    return

                if amount < 1000:
                    await update.message.reply_text(
                        "âš ï¸ á€„á€½á€±á€•á€™á€¬á€á€™á€¾á€¬á€¸á€šá€½á€„á€ºá€¸á€•á€«á€žá€Šá€ºá‹ á€¡á€”á€Šá€ºá€¸á€†á€¯á€¶á€¸ áá€á€á€ MMK á€–á€¼á€…á€ºá€›á€™á€Šá€ºá‹"
                    )
                    return

                payment_method = context.user_data['topup_method']
                photo_message_id = context.user_data['topup_photo_message_id']

                db["topup_requests"][receipt_id] = {
                    "user_id": uid,
                    "status": "pending",
                    "amount": amount,
                    "payment_method": payment_method
                }
                save_db(db)

                keyboard = [[
                    InlineKeyboardButton(
                        "âœ… á€œá€€á€ºá€á€¶á€›á€”á€º",
                        callback_data=f"approve_topup_{receipt_id}"),
                    InlineKeyboardButton(
                        "ðŸ’¬ á€…á€¬á€•á€­á€¯á€·á€›á€”á€º",
                        callback_data=f"message_topup_{receipt_id}"),
                    InlineKeyboardButton(
                        "âŒ á€„á€¼á€„á€ºá€¸á€•á€šá€ºá€›á€”á€º",
                        callback_data=f"reject_topup_{receipt_id}")
                ]]

                await context.bot.forward_message(
                    chat_id=ADMIN_ID,
                    from_chat_id=update.message.chat.id,
                    message_id=photo_message_id)

                await context.bot.send_message(
                    chat_id=ADMIN_ID,
                    text=f"ðŸ“¥ á€„á€½á€±á€–á€¼á€Šá€·á€ºá€á€±á€¬á€„á€ºá€¸á€†á€­á€¯á€™á€¾á€¯:\n"
                    f"ðŸ‘¤ á€¡á€žá€¯á€¶á€¸á€•á€¼á€¯á€žá€°: {uid}\n"
                    f"ðŸ’³ á€”á€Šá€ºá€¸á€œá€™á€ºá€¸: {payment_method}\n"
                    f"ðŸ“„ á€•á€¼á€±á€…á€¬ ID: {receipt_id}\n"
                    f"ðŸ’° á€„á€½á€±á€•á€™á€¬á€: {amount} MMK",
                    reply_markup=InlineKeyboardMarkup(keyboard))

                await update.message.reply_text("â³ Admin á€™á€¾ á€…á€…á€ºá€†á€±á€¸á€”á€±á€•á€«á€žá€Šá€º...")

                # Clear user data
                del context.user_data['topup_method']
                del context.user_data['topup_photo_sent']
                del context.user_data['topup_photo_message_id']
                return
            except ValueError:
                await update.message.reply_text("âš ï¸ á€„á€½á€±á€•á€™á€¬á€á€™á€¾á€¬á€¸á€šá€½á€„á€ºá€¸á€•á€«á€žá€Šá€ºá‹")
                return
            except:
                await update.message.reply_text("âš ï¸ á€–á€±á€¬á€ºá€™á€á€ºá€™á€¾á€¬á€¸á€šá€½á€„á€ºá€¸á€•á€«á€žá€Šá€ºá‹")
                return

        # Handle receipt purchase with receipt ID
        if 'buying_game' in context.user_data and context.user_data.get(
                'receipt_step') == 'id':
            if not validate_receipt_id(text):
                await update.message.reply_text(
                    "âš ï¸ á€•á€¼á€±á€…á€¬ ID á€žá€Šá€º á…-á†á€œá€¯á€¶á€¸ á€‚á€á€”á€ºá€¸á€–á€¼á€…á€ºá€›á€™á€Šá€ºá‹")
                return

            game_type = context.user_data['buying_game']
            amount = context.user_data['buying_amount']
            quantity = context.user_data['buying_quantity']
            photo_message_id = context.user_data['receipt_photo_message_id']

            db["receipts"][text] = {
                "user_id": uid,
                "status": "pending",
                "game_type": game_type,
                "amount": amount,
                "quantity": quantity
            }
            save_db(db)

            game_name = get_game_display_name(game_type)
            unit = "Coin" if "MLBB" in game_type else "UC"
            keyboard = [[
                InlineKeyboardButton("âœ… á€œá€€á€ºá€á€¶á€›á€”á€º",
                                     callback_data=f"approve_{text}"),
                InlineKeyboardButton("ðŸ’¬ á€…á€¬á€•á€­á€¯á€·á€›á€”á€º",
                                     callback_data=f"message_{text}"),
                InlineKeyboardButton("âŒ á€„á€¼á€„á€ºá€¸á€•á€šá€ºá€›á€”á€º",
                                     callback_data=f"reject_{text}")
            ]]

            await context.bot.forward_message(
                chat_id=ADMIN_ID,
                from_chat_id=update.message.chat.id,
                message_id=photo_message_id)

            await context.bot.send_message(
                chat_id=ADMIN_ID,
                text=f"ðŸ“¥ á€€á€¯á€’á€ºá€á€šá€ºá€šá€°á€™á€¾á€¯:\n"
                f"ðŸ‘¤ á€¡á€žá€¯á€¶á€¸á€•á€¼á€¯á€žá€°: {uid}\n"
                f"ðŸŽ® á€‚á€­á€™á€ºá€¸: {game_name}\n"
                f"ðŸ’Ž {amount} {unit} x {quantity}\n"
                f"ðŸ“„ á€•á€¼á€±á€…á€¬ ID: {text}",
                reply_markup=InlineKeyboardMarkup(keyboard))
            await update.message.reply_text("â³ Admin á€™á€¾ á€…á€…á€ºá€†á€±á€¸á€”á€±á€•á€«á€žá€Šá€º...")

            # Clear user data
            del context.user_data['buying_game']
            del context.user_data['buying_amount']
            del context.user_data['buying_quantity']
            del context.user_data['receipt_photo_sent']
            del context.user_data['receipt_photo_message_id']
            del context.user_data['receipt_step']
            return


# ---------------- Admin Commands ----------------
async def setbalance(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        return
    try:
        args = context.args
        uid = int(args[0])
        amount = int(args[1])
        user = get_user(uid)
        user["balance"] = amount
        save_db(db)
        await update.message.reply_text(
            f"âœ… á€¡á€žá€¯á€¶á€¸á€•á€¼á€¯á€žá€° {uid} á á€œá€€á€ºá€€á€»á€”á€ºá€„á€½á€±á€€á€­á€¯ {amount} MMK á€žá€á€ºá€™á€¾á€á€ºá€•á€¼á€®á€¸")
    except:
        await update.message.reply_text(
            "á€¡á€žá€¯á€¶á€¸á€•á€¼á€¯á€”á€Šá€ºá€¸: /setbalance <user_id> <amount>")


async def addstock(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        return

    # Interactive version
    keyboard = [[
        InlineKeyboardButton("ðŸŽ® Mobile Legends (Bal)",
                             callback_data="addstock_MLBBbal")
    ],
                [
                    InlineKeyboardButton("ðŸŽ® Mobile Legends (PH)",
                                         callback_data="addstock_MLBBph")
                ],
                [
                    InlineKeyboardButton("ðŸŽ® PUPG Mobile",
                                         callback_data="addstock_PUPG")
                ]]
    await update.message.reply_text(
        "ðŸŽ® á€‚á€­á€™á€ºá€¸á€¡á€™á€»á€­á€¯á€¸á€¡á€…á€¬á€¸á€›á€½á€±á€¸á€•á€«:",
        reply_markup=InlineKeyboardMarkup(keyboard))


async def delstock(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        return

    if len(context.args) < 3:
        await update.message.reply_text(
            "á€¡á€žá€¯á€¶á€¸á€•á€¼á€¯á€”á€Šá€ºá€¸: /delstock <MLBBbal/MLBBph/PUPG> <amount> <code>")
        return

    try:
        game_type = context.args[0]
        amount = context.args[1]
        code_to_delete = context.args[2]

        if game_type not in ["MLBBbal", "MLBBph", "PUPG"]:
            await update.message.reply_text(
                "á€‚á€­á€™á€ºá€¸á€¡á€™á€»á€­á€¯á€¸á€¡á€…á€¬á€¸: MLBBbal, MLBBph, á€žá€­á€¯á€·á€™á€Ÿá€¯á€á€º PUPG")
            return

        if game_type not in db["stock"] or amount not in db["stock"][game_type]:
            await update.message.reply_text(
                "âš ï¸ á€’á€®á€‚á€­á€™á€ºá€¸á€¡á€™á€»á€­á€¯á€¸á€¡á€…á€¬á€¸ á€žá€­á€¯á€·á€™á€Ÿá€¯á€á€º á€•á€™á€¬á€á€™á€›á€¾á€­á€•á€«á‹")
            return

        if code_to_delete in db["stock"][game_type][amount]:
            db["stock"][game_type][amount].remove(code_to_delete)
            save_db(db)

            game_name = get_game_display_name(game_type)
            unit = "Coin" if "MLBB" in game_type else "UC"
            await update.message.reply_text(
                f"âœ… {game_name} {amount} {unit} á€™á€¾ á€€á€¯á€’á€º {code_to_delete} á€–á€»á€€á€ºá€•á€¼á€®á€¸"
            )
        else:
            await update.message.reply_text("âš ï¸ á€’á€®á€€á€¯á€’á€ºá€™á€á€½á€±á€·á€•á€«á‹")
    except:
        await update.message.reply_text(
            "á€¡á€žá€¯á€¶á€¸á€•á€¼á€¯á€”á€Šá€ºá€¸: /delstock <MLBBbal/MLBBph/PUPG> <amount> <code>")


async def setprice(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        return
    if len(context.args) < 3:
        await update.message.reply_text(
            "á€¡á€žá€¯á€¶á€¸á€•á€¼á€¯á€”á€Šá€ºá€¸: /setprice <MLBBbal/MLBBph/PUPG> <amount> <price>")
        return

    try:
        game_type = context.args[0]
        amount = context.args[1]
        price = int(context.args[2])

        if game_type not in ["MLBBbal", "MLBBph", "PUPG"]:
            await update.message.reply_text(
                "á€‚á€­á€™á€ºá€¸á€¡á€™á€»á€­á€¯á€¸á€¡á€…á€¬á€¸: MLBBbal, MLBBph, á€žá€­á€¯á€·á€™á€Ÿá€¯á€á€º PUPG")
            return

        if game_type not in db["prices"]:
            db["prices"][game_type] = {}

        db["prices"][game_type][amount] = price
        save_db(db)

        game_name = get_game_display_name(game_type)
        unit = "Coin" if "MLBB" in game_type else "UC"
        await update.message.reply_text(
            f"âœ… {game_name} {amount} {unit} á á€…á€»á€±á€¸á€”á€¾á€¯á€”á€ºá€¸á€€á€­á€¯ {price} MMK á€¡á€–á€¼á€…á€ºá€žá€á€ºá€™á€¾á€á€ºá€•á€¼á€®á€¸"
        )
    except:
        await update.message.reply_text(
            "á€¡á€žá€¯á€¶á€¸á€•á€¼á€¯á€”á€Šá€ºá€¸: /setprice <MLBBbal/MLBBph/PUPG> <amount> <price>")


async def setpayment(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        return
    try:
        method = context.args[0].title()
        phone = context.args[1]
        name = " ".join(context.args[2:])

        if method not in ["Wave", "Kpay"]:
            await update.message.reply_text(
                "á€„á€½á€±á€•á€±á€¸á€á€»á€±á€™á€¾á€¯á€”á€Šá€ºá€¸á€œá€™á€ºá€¸: Wave á€žá€­á€¯á€·á€™á€Ÿá€¯á€á€º KPay")
            return

        db["payment"][method] = {"phone": phone, "name": name}
        save_db(db)
        await update.message.reply_text(
            f"âœ… {method} á€•á€±á€¸á€á€»á€±á€™á€¾á€¯á€¡á€á€»á€€á€ºá€¡á€œá€€á€º á€•á€¼á€±á€¬á€„á€ºá€¸á€œá€²á€•á€¼á€®á€¸\nðŸ“± á€–á€¯á€”á€ºá€¸: {phone}\nðŸ‘¤ á€¡á€™á€Šá€º: {name}"
        )
    except:
        await update.message.reply_text(
            "á€¡á€žá€¯á€¶á€¸á€•á€¼á€¯á€”á€Šá€ºá€¸: /setpayment <Wave/KPay> <phone> <name>")


async def viewhistory(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        return
    try:
        uid = int(context.args[0])
        user = get_user(uid)
        if not user["history"]:
            await update.message.reply_text(
                f"á€¡á€žá€¯á€¶á€¸á€•á€¼á€¯á€žá€° {uid} á á€™á€¾á€á€ºá€á€™á€ºá€¸á€™á€›á€¾á€­á€•á€«")
            return

        history_text = ""
        for i, h in enumerate(user["history"], 1):
            history_text += f"{i}. {h}\n"

        await update.message.reply_text(
            f"ðŸ“œ á€¡á€žá€¯á€¶á€¸á€•á€¼á€¯á€žá€° {uid} á á€™á€¾á€á€ºá€á€™á€ºá€¸:\n{history_text}")
    except:
        await update.message.reply_text("á€¡á€žá€¯á€¶á€¸á€•á€¼á€¯á€”á€Šá€ºá€¸: /viewhistory <user_id>")


async def admhelp(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        return

    # Calculate stock counts
    mlbbbal_count = sum(
        len(codes) for codes in db["stock"].get("MLBBbal", {}).values())
    mlbbph_count = sum(
        len(codes) for codes in db["stock"].get("MLBBph", {}).values())
    pupg_count = sum(
        len(codes) for codes in db["stock"].get("PUPG", {}).values())

    # Calculate total orders
    total_orders = 0
    for user_data in db["users"].values():
        total_orders += len(user_data.get("history", []))

    # Calculate total user balance
    total_user_balance = sum(
        user_data.get("balance", 0) for user_data in db["users"].values())

    # Calculate pending counts (only pending status)
    pending_receipts = len(
        [r for r in db["receipts"].values() if r["status"] == "pending"])
    pending_topups = len(
        [r for r in db["topup_requests"].values() if r["status"] == "pending"])
    pending_registrations = len(db.get("pending_registrations", {}))

    help_text = f"""
ðŸ”§ Admin Commands:

/setbalance <user_id> <amount> - á€¡á€žá€¯á€¶á€¸á€•á€¼á€¯á€žá€°á€œá€€á€ºá€€á€»á€”á€ºá€„á€½á€±á€žá€á€ºá€™á€¾á€á€ºá€›á€”á€º
/addstock - á€€á€¯á€’á€ºá€™á€»á€¬á€¸á€‘á€Šá€·á€ºá€›á€”á€º (á€¡á€•á€¼á€”á€ºá€¡á€œá€¾á€”á€º)
/delstock <MLBBbal/MLBBph/PUPG> <amount> <code> - á€€á€¯á€’á€ºá€–á€»á€€á€ºá€›á€”á€º
/setprice <MLBBbal/MLBBph/PUPG> <amount> <price> - á€…á€»á€±á€¸á€”á€¾á€¯á€”á€ºá€¸á€žá€á€ºá€™á€¾á€á€ºá€›á€”á€º
/setpayment <Wave/Kpay> <phone> <name> - á€•á€±á€¸á€á€»á€±á€™á€¾á€¯á€¡á€á€»á€€á€ºá€¡á€œá€€á€ºá€•á€¼á€±á€¬á€„á€ºá€¸á€›á€”á€º
/viewhistory <user_id> - á€¡á€žá€¯á€¶á€¸á€•á€¼á€¯á€žá€°á€™á€¾á€á€ºá€á€™á€ºá€¸á€€á€¼á€Šá€·á€ºá€›á€”á€º
/admhelp - á€’á€®á€¡á€€á€°á€¡á€Šá€®á€…á€¬á€›á€„á€ºá€¸

ðŸ“Š á€œá€€á€ºá€›á€¾á€­á€¡á€á€¼á€±á€¡á€”á€±:
ðŸŽ® MLBB Bal á€€á€¯á€’á€º: {mlbbbal_count}
ðŸŽ® MLBB PH á€€á€¯á€’á€º: {mlbbph_count}
ðŸŽ® PUPG á€€á€¯á€’á€º: {pupg_count}
ðŸ‘¥ á€¡á€žá€¯á€¶á€¸á€•á€¼á€¯á€žá€°: {len(db["users"])}
ðŸ“¦ á€¡á€±á€¬á€ºá€’á€«á€…á€¯á€…á€¯á€•á€±á€«á€„á€ºá€¸: {total_orders}
ðŸ’° á€¡á€žá€¯á€¶á€¸á€•á€¼á€¯á€žá€°á€œá€€á€ºá€€á€»á€”á€ºá€„á€½á€±á€…á€¯á€…á€¯á€•á€±á€«á€„á€ºá€¸: {total_user_balance:,} MMK
ðŸ’µ á€›á€±á€¬á€„á€ºá€¸á€›á€„á€½á€±á€…á€¯á€…á€¯á€•á€±á€«á€„á€ºá€¸: {db.get('sales_total', 0):,} MMK
â³ á€„á€¶á€·á€›á€±á€¸á€•á€¼á€±á€…á€¬: {pending_receipts}
â³ á€„á€¶á€·á€›á€±á€¸á€„á€½á€±á€–á€¼á€Šá€·á€º: {pending_topups}
â³ á€„á€¶á€·á€›á€±á€¸á€¡á€€á€±á€¬á€„á€·á€ºá€–á€½á€„á€·á€º: {pending_registrations}

ðŸ’¡ á€¥á€•á€™á€¬á€™á€»á€¬á€¸:
/setprice MLBBbal 1000 2500
/setprice PUPG 60 1500
/delstock MLBBbal 1000 CODE123
/setpayment Kpay 09123456789 John Doe

ðŸ”§ á€¡á€„á€ºá€¹á€‚á€«á€›á€•á€ºá€™á€»á€¬á€¸:
â€¢ á€¡á€€á€±á€¬á€„á€·á€ºá€–á€½á€„á€·á€ºá€™á€¾á€¯ Admin á€œá€€á€ºá€á€¶á€™á€¾á€¯á€œá€­á€¯á€¡á€•á€ºá€žá€Šá€º
â€¢ á€€á€¯á€’á€ºá€¡á€›á€±á€¡á€á€½á€€á€ºá€›á€½á€±á€¸á€á€»á€šá€ºá€™á€¾á€¯ á€…á€¬á€•á€­á€¯á€·á€á€¼á€„á€ºá€¸á€–á€¼á€„á€·á€º
â€¢ Admin á€€á€­á€¯ á€…á€¬á€•á€­á€¯á€·á€”á€­á€¯á€„á€ºá€žá€Šá€º (ðŸ’¬ á€á€œá€¯á€á€º)
    """

    await update.message.reply_text(help_text)


# ---------------- Main ----------------
def main():
    app = Application.builder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("setbalance", setbalance))
    app.add_handler(CommandHandler("addstock", addstock))
    app.add_handler(CommandHandler("delstock", delstock))
    app.add_handler(CommandHandler("setprice", setprice))
    app.add_handler(CommandHandler("setpayment", setpayment))
    app.add_handler(CommandHandler("viewhistory", viewhistory))
    app.add_handler(CommandHandler("admhelp", admhelp))
    app.add_handler(CallbackQueryHandler(callback_handler))
    app.add_handler(
        MessageHandler(filters.ALL & ~filters.COMMAND, handle_message))
    app.run_polling()


if __name__ == "__main__":
    main()
