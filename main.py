import os
import json
import random
import asyncio
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, ContextTypes, MessageHandler, filters
from dotenv import load_dotenv

# ---------------- Load Environment Variables ----------------
load_dotenv()
BOT_TOKEN = os.getenv("BOT_TOKEN", "7927660379:AAGtm-CvAunvvANaaYvzlmRVjjBgJcmEh58")
ADMIN_ID = int(os.getenv("ADMIN_ID", "5821905026"))

# Render အတွက် file path သတ်မှတ်ခြင်း
DB_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "database.json")

# ---------------- Database Functions ----------------
def load_db():
    try:
        if not os.path.exists(DB_FILE):
            print("Creating new database file...")
            default_db = {
                "users": {},
                "stock": {
                    "MLBBbal": {},
                    "MLBBph": {},
                    "PUPG": {}
                },
                "receipts": {},
                "topup_requests": {},
                "prices": {
                    "MLBBbal": {},
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
                "pending_registrations": {},
                "cleanup_done": True
            }
            save_db(default_db)
            return default_db
            
        with open(DB_FILE, "r", encoding='utf-8') as f:
            data = json.load(f)
        
        # Database structure migration
        data = migrate_database_structure(data)
        
        # Ensure all expected keys exist
        required_keys = {
            "stock": {"MLBBbal": {}, "MLBBph": {}, "PUPG": {}},
            "prices": {"MLBBbal": {}, "MLBBph": {}, "PUPG": {}},
            "topup_requests": {},
            "users": {},
            "payment": {
                "Wave": {"phone": "09673585480", "name": "Nine Nine"},
                "KPay": {"phone": "09678786528", "name": "Ma May Phoo Wai"}
            },
            "sales_total": 0,
            "pending_registrations": {},
            "receipts": {}
        }
        
        for key, default_value in required_keys.items():
            if key not in data:
                data[key] = default_value.copy() if isinstance(default_value, dict) else default_value
        
        return data
        
    except Exception as e:
        print(f"Error loading database: {e}")
        # Return default database if loading fails
        return create_default_db()

def migrate_database_structure(data):
    """Migrate old database structure to new one"""
    # Update old structure if needed
    if "stock" in data and isinstance(data["stock"], dict) and "mlbb" in data["stock"]:
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

    # Migrate PUBG to PUPG in existing structure
    if "stock" in data and "PUBG" in data["stock"]:
        data["stock"]["PUPG"] = data["stock"].pop("PUBG")
    if "prices" in data and "PUBG" in data["prices"]:
        data["prices"]["PUPG"] = data["prices"].pop("PUBG")

    # Clear old codes from MLBBph and PUPG (one-time cleanup)
    if "cleanup_done" not in data:
        if "MLBBph" in data["stock"]:
            data["stock"]["MLBBph"] = {}
        if "PUPG" in data["stock"]:
            data["stock"]["PUPG"] = {}
        data["cleanup_done"] = True

    return data

def create_default_db():
    """Create a default database structure"""
    return {
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
        "pending_registrations": {},
        "cleanup_done": True
    }

def save_db(db):
    try:
        # Ensure directory exists
        os.makedirs(os.path.dirname(DB_FILE), exist_ok=True)
        
        with open(DB_FILE, "w", encoding='utf-8') as f:
            json.dump(db, f, indent=2, ensure_ascii=False)
    except Exception as e:
        print(f"Error saving database: {e}")

# Load database at startup
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
    return sorted(amounts, key=lambda x: int(x) if x.isdigit() else x)

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
        InlineKeyboardButton("📋 အကောင့်ဖွင့်ရန်", callback_data="register")
    ], [InlineKeyboardButton("💵 ဘေလင့်ကြည့်ရန်", callback_data="balance")],
                [InlineKeyboardButton("💰 ဘေလင့်ဖြည့်ရန်", callback_data="topup")],
                [InlineKeyboardButton("🛒 အိုင်တီယူရန်", callback_data="buy")],
                [InlineKeyboardButton("ℹ️ အကူအညီ", callback_data="help")]]
    
    if update.message:
        await update.message.reply_text(
            f"👋 ကြိုဆိုပါတယ် {user.first_name}! ကျေးဇူးပြု၍အောက်ပါမှရွေးချယ်ပါ!",
            reply_markup=InlineKeyboardMarkup(keyboard))
    else:
        await update.callback_query.edit_message_text(
            f"👋 ကြိုဆိုပါတယ် {user.first_name}! ကျေးဇူးပြု၍အောက်ပါမှရွေးချယ်ပါ!",
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
                InlineKeyboardButton("🏠 မူလစာမျက်နှာသို့", callback_data="start")
            ]]
            await query.edit_message_text(
                "✅ အကောင့်ဖွင့်ပြီးဖြစ်ပါသည်။",
                reply_markup=InlineKeyboardMarkup(keyboard))
            return
        elif uid in db["pending_registrations"]:
            keyboard = [[
                InlineKeyboardButton("🏠 မူလစာမျက်နှာသို့", callback_data="start")
            ]]
            await query.edit_message_text(
                "⏳ အကောင့်ဖွင့်တောင်းခံချက်ကို စောင့်ဆိုင်းနေပါသည်။ Admin မှ အတည်ပြုပေးမည်ဖြစ်ပါသည်။",
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
            InlineKeyboardButton("✅ အတည်ပြုရန်",
                                 callback_data=f"approve_reg_{uid}"),
            InlineKeyboardButton("❌ ငြင်းပယ်ရန်",
                                 callback_data=f"reject_reg_{uid}")
        ]]
        try:
            await context.bot.send_message(
                chat_id=ADMIN_ID,
                text=f"📥 အကောင့်ဖွင့်တောင်းခံချက်အသစ်:\n"
                f"🆔 သုံးစွဲသူ ID: {uid}\n"
                f"📝 အမည်: {query.from_user.first_name}\n"
                f"👤 Username: @{query.from_user.username or 'မရှိ'}",
                reply_markup=InlineKeyboardMarkup(keyboard))
        except Exception as e:
            print(f"Error sending message to admin: {e}")

        keyboard = [[
            InlineKeyboardButton("🏠 မူလစာမျက်နှာသို့", callback_data="start")
        ]]
        await query.edit_message_text(
            "📝 အကောင့်ဖွင့်တောင်းခံချက်ကို Admin ထံပို့ပြီးပါပြီ။ အတည်ပြုခံရပါက သတင်းပို့ပေးပါမည်။",
            reply_markup=InlineKeyboardMarkup(keyboard))

    elif data == "balance":
        if not is_user_approved(uid):
            keyboard = [[
                InlineKeyboardButton("🏠 မူလစာမျက်နှာသို့", callback_data="start")
            ]]
            await query.edit_message_text(
                "⚠️ သင့်အကောင့်ကို Admin မှ အတည်ပြုရပါမည်။",
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
                [InlineKeyboardButton("💰 ဘေလင့်ဖြည့်ရန်", callback_data="topup")])
        keyboard.append(
            [InlineKeyboardButton("🏠 မူလစာမျက်နှာသို့", callback_data="start")])
        await query.edit_message_text(
            f"💵 ဘေလင့်လက်ကျန်: {user['balance']} MMK",
            reply_markup=InlineKeyboardMarkup(keyboard))

    elif data == "topup":
        if not is_user_approved(uid):
            keyboard = [[
                InlineKeyboardButton("🏠 မူလစာမျက်နှာသို့", callback_data="start")
            ]]
            await query.edit_message_text(
                "⚠️ သင့်အကောင့်ကို Admin မှ အတည်ပြုရပါမည်။",
                reply_markup=InlineKeyboardMarkup(keyboard))
            return

        keyboard = [
            [InlineKeyboardButton("📱 Wave", callback_data="topup_wave")],
            [InlineKeyboardButton("📱 Kpay", callback_data="topup_kpay")],
            [InlineKeyboardButton("🏠 မူလစာမျက်နှာသို့", callback_data="start")]
        ]
        await query.edit_message_text(
            "💰 ဘေလင့်ဖြည့်ရန် ငွေလွှဲနည်းလမ်းရွေးချယ်ပါ:",
            reply_markup=InlineKeyboardMarkup(keyboard))

    elif data.startswith("topup_"):
        payment_method = data.split("_")[1].title()
        if payment_method not in db["payment"]:
            await query.edit_message_text("⚠️ ငွေလွှဲနည်းလမ်းမရှိပါ။")
            return
            
        payment_info = db["payment"][payment_method]

        context.user_data['topup_method'] = payment_method
        keyboard = [[
            InlineKeyboardButton(f"📋 {payment_info['phone']}",
                                 callback_data=f"copy_{payment_info['phone']}")
        ], [InlineKeyboardButton("🏠 မူလစာမျက်နှာသို့", callback_data="topup")]]

        await query.edit_message_text(
            f"💰 {payment_method} ဘေလင့်ဖြည့်ရန်:\n\n"
            f"📱 ဖုန်းနံပါတ်: {payment_info['phone']}\n"
            f"👤 အမည်: {payment_info['name']}\n\n"
            f"📋 ဖုန်းနံပါတ်ကို ကူးယူရန် အောက်ပါခလုတ်ကိုနှိပ်ပါ:\n\n"
            f"💵 ငွေလွှဲပြီးနောက် အောက်ပါအချက်များပို့ပေးပါ:\n"
            f"• ငွေလွှဲသူ ID (ဘေလင့်ဖြည့်ရန်)\n"
            f"• ငွေလွှဲသည့်ပမာဏ\n"
            f"ကျေးဇူးပြု၍အတိအကျပို့ပေးပါ။\n\n"
            f"⚠️ သတိပြုရန်: ငွေလွှဲသူ ID မှားယွင်းပါက ငွေမရရှိနိုင်ပါ\n\n"
            f"📸 ငွေလွှဲပြီးသည့်ဓာတ်ပုံ ပို့ပေးပါ\n"
            f"ℹ️ KPay ငွေလွှဲပါက KPay အမည်ကိုလည်းပို့ပေးပါ",
            reply_markup=InlineKeyboardMarkup(keyboard))

    elif data.startswith("copy_"):
        phone_number = data.split("_", 1)[1]
        # Send the phone number as a separate message for easier copying
        try:
            await context.bot.send_message(chat_id=query.from_user.id,
                                           text=phone_number)
            await query.answer(
                f"📋 {phone_number} ကူးယူပြီးပါပြီ! ကျေးဇူးပြု၍ငွေလွှဲပြီးဓာတ်ပုံပို့ပေးပါ!",
                show_alert=True)
        except Exception as e:
            print(f"Error sending copy message: {e}")

    elif data == "help":
        keyboard = [[
            InlineKeyboardButton("🏠 မူလစာမျက်နှာသို့", callback_data="start")
        ]]
        await query.edit_message_text(
            "ℹ️ အသုံးပြုနည်း:\n\n"
            "1️⃣ အကောင့်ဖွင့်ရန်\n"
            "2️⃣ ဘေလင့်ကြည့်ရန်\n"
            "3️⃣ ဘေလင့်ဖြည့်ရန်\n"
            "4️⃣ အိုင်တီယူရန်\n\n"
            "📋 လမ်းညွှန်ချက်များ:\n"
            "• Admin မှ အတည်ပြုပြီးမှသာ အိုင်တီဝယ်ယူနိုင်မည်\n"
            "• ဝယ်ယူပြီးနောက် ကုဒ်များရရှိမည်\n"
            "• ငွေလွှဲသူ ID ဖြင့် အိုင်တီဝယ်ယူနိုင်သည်\n"
            "• ဘေလင့်လက်ကျန်ဖြင့်လည်း ဝယ်ယူနိုင်သည်",
            reply_markup=InlineKeyboardMarkup(keyboard))

    elif data == "buy":
        if not is_user_approved(uid):
            keyboard = [[
                InlineKeyboardButton("🏠 မူလစာမျက်နှာသို့", callback_data="start")
            ]]
            await query.edit_message_text(
                "⚠️ သင့်အကောင့်ကို Admin မှ အတည်ပြုရပါမည်။",
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
                            f"🎮 {game_name} ({total_codes})",
                            callback_data=f"select_{game_type}")
                    ])
                    available_games.append(game_type)

        if not available_games:
            keyboard = [[
                InlineKeyboardButton("🏠 မူလစာမျက်နှာသို့", callback_data="start")
            ]]
            await query.edit_message_text(
                "⚠️ လက်ရှိမှာရနိုင်သောအိုင်တီမရှိပါ။",
                reply_markup=InlineKeyboardMarkup(keyboard))
            return

        keyboard.append(
            [InlineKeyboardButton("🏠 မူလစာမျက်နှာသို့", callback_data="start")])
        await query.edit_message_text(
            "🎮 ဂိမ်းရွေးချယ်ရန်:",
            reply_markup=InlineKeyboardMarkup(keyboard))

    elif data.startswith("select_"):
        game_type = data.split("_")[1]
        amounts = get_available_amounts(game_type)

        if not amounts:
            keyboard = [[
                InlineKeyboardButton("🏠 မူလစာမျက်နှာသို့", callback_data="buy")
            ]]
            await query.edit_message_text(
                "⚠️ ဤဂိမ်းအတွက်ရနိုင်သောအိုင်တီမရှိပါ။",
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
                    f"💳 {amount} {unit} - {price} MMK ({codes_count})",
                    callback_data=f"amount_{game_type}_{amount}")
            ])

        keyboard.append(
            [InlineKeyboardButton("🏠 မူလစာမျက်နှာသို့", callback_data="buy")])
        await query.edit_message_text(
            f"🎮 {game_name}\n💳 ပမာဏရွေးချယ်ရန်:",
            reply_markup=InlineKeyboardMarkup(keyboard))

    elif data.startswith("amount_"):
        parts = data.split("_")
        game_type = parts[1]
        amount = parts[2]

        if amount not in db["stock"].get(
                game_type, {}) or not db["stock"][game_type][amount]:
            keyboard = [[
                InlineKeyboardButton("🏠 မူလစာမျက်နှာသို့",
                                     callback_data=f"select_{game_type}")
            ]]
            await query.edit_message_text(
                "⚠️ ဤပမာဏအတွက်ရနိုင်သောအိုင်တီမရှိပါ။",
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
            InlineKeyboardButton("🏠 မူလစာမျက်နှာသို့",
                                 callback_data=f"select_{game_type}")
        ]]

        game_name = get_game_display_name(game_type)
        unit = "Coin" if "MLBB" in game_type else "UC"
        await query.edit_message_text(
            f"🎮 {game_name}\n"
            f"💳 {amount} {unit}\n"
            f"💵 ဈေးနှုန်း: {price} MMK/အိုင်တီ\n"
            f"💰 ဘေလင့်လက်ကျန်: {user['balance']} MMK\n"
            f"📊 ရနိုင်သောအရေအတွက်: {max_quantity} ခု\n\n"
            f"📝 ဝယ်ယူမည့်အရေအတွက်ရိုက်ထည့်ပါ (1 to {max_quantity}):",
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
                InlineKeyboardButton("💰 ဘေလင့်ဖြည့်ရန်", callback_data="topup")
            ],
                        [
                            InlineKeyboardButton(
                                "🏠 မူလစာမျက်နှာသို့",
                                callback_data=
                                f"quantity_{game_type}_{amount}_{quantity}")
                        ]]
            await query.edit_message_text(
                "⚠️ ဘေလင့်လက်ကျန်မလုံလောက်ပါ။",
                reply_markup=InlineKeyboardMarkup(keyboard))
            return

        if len(db["stock"][game_type][amount]) < quantity:
            keyboard = [[
                InlineKeyboardButton("🏠 မူလစာမျက်နှာသို့", callback_data="buy")
            ]]
            await query.edit_message_text(
                "⚠️ လက်ရှိမှာရနိုင်သောအိုင်တီမလုံလောက်ပါ။",
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

        codes_text = "\n".join([f"🔑 {code}" for code in codes])
        keyboard = [[
            InlineKeyboardButton("🏠 မူလစာမျက်နှာသို့", callback_data="start")
        ]]
        await query.edit_message_text(
            f"✅ အိုင်တီဝယ်ယူမှုအောင်မြင်ပါသည်!\n\n"
            f"🎮 {game_name}\n"
            f"💳 {amount} {unit} x {quantity}\n"
            f"💵 စုစုပေါင်းဈေးနှုန်း: {total_price} MMK\n\n"
            f"🔑 အိုင်တီကုဒ်များ:\n{codes_text}\n\n"
            f"💰 ဘေလင့်လက်ကျန်: {user['balance']} MMK",
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
                "🏠 မူလစာမျက်နှာသို့",
                callback_data=f"quantity_{game_type}_{amount}_{quantity}")
        ]]
        await query.edit_message_text(
            "📄 ငွေလွှဲသူIDဖြင့်ဝယ်ယူရန်:\n\n"
            "1️⃣ ငွေလွှဲပြီးသည့်ဓာတ်ပုံပို့ပေးပါ\n"
            "2️⃣ ငွေလွှဲသူ ID (ဘေလင့်ဖြည့်ရန်) ရိုက်ထည့်ပေးပါ\n\n"
            "⚠️ သတိပြုရန်: ငွေလွှဲသူ ID မှားယွင်းပါက အိုင်တီမရနိုင်ပါ",
            reply_markup=InlineKeyboardMarkup(keyboard))

    # Admin approval handlers
    elif data.startswith("message_topup_"):
        if uid != ADMIN_ID:
            await query.edit_message_text(
                "⚠️ Admin မဟုတ်ပါက ဤလုပ်ဆောင်ချက်ကိုသုံးခွင့်မရှိပါ။")
            return

        receipt_id = data.split("_")[2]
        if receipt_id not in db["topup_requests"]:
            await query.edit_message_text("⚠️ ဘေလင့်ဖြည့်တောင်းခံချက်မရှိပါ။")
            return

        request = db["topup_requests"][receipt_id]
        user_id = request["user_id"]
        context.user_data['admin_messaging'] = {'user_id': user_id}
        await query.edit_message_text("💬 သုံးစွဲသူထံမက်ဆေ့ပို့ရန် စာရိုက်ထည့်ပါ:")

    elif data.startswith("message_") and not data.startswith("message_topup_"):
        if uid != ADMIN_ID:
            await query.edit_message_text(
                "⚠️ Admin မဟုတ်ပါက ဤလုပ်ဆောင်ချက်ကိုသုံးခွင့်မရှိပါ။")
            return

        receipt_id = data.split("_")[1]
        if receipt_id not in db["receipts"]:
            await query.edit_message_text("⚠️ ငွေလွှဲသူIDမရှိပါ။")
            return

        receipt = db["receipts"][receipt_id]
        user_id = receipt["user_id"]
        context.user_data['admin_messaging'] = {'user_id': user_id}
        await query.edit_message_text("💬 သုံးစွဲသူထံမက်ဆေ့ပို့ရန် စာရိုက်ထည့်ပါ:")

    elif data.startswith("approve_topup_") or data.startswith("reject_topup_"):
        if uid != ADMIN_ID:
            await query.edit_message_text(
                "⚠️ Admin မဟုတ်ပါက ဤလုပ်ဆောင်ချက်ကိုသုံးခွင့်မရှိပါ။")
            return

        action, _, receipt_id = data.split("_")
        if receipt_id not in db["topup_requests"]:
            await query.edit_message_text("⚠️ ဘေလင့်ဖြည့်တောင်းခံချက်မရှိပါ။")
            return

        request = db["topup_requests"][receipt_id]
        user_id = request["user_id"]
        amount = request["amount"]
        user = get_user(user_id)

        if action == "approve":
            user["balance"] += amount
            request["status"] = "approved"
            save_db(db)
            try:
                await context.bot.send_message(
                    user_id,
                    f"✅ ဘေလင့်ဖြည့်မှုအောင်မြင်ပါသည်!\n💰 ဖြည့်သွင်းငွေ: {amount} MMK\n💵 ဘေလင့်လက်ကျန်: {user['balance']} MMK"
                )
            except Exception as e:
                print(f"Error sending approval message: {e}")
            await query.edit_message_text(
                f"✅ ဘေလင့်ဖြည့်တောင်းခံချက် {receipt_id} အတည်ပြုပြီးပါပြီ")
        else:
            request["status"] = "rejected"
            save_db(db)
            try:
                await context.bot.send_message(user_id,
                                               "❌ ဘေလင့်ဖြည့်တောင်းခံချက်ပယ်ဖျက်ခံရပါသည်။")
            except Exception as e:
                print(f"Error sending rejection message: {e}")
            await query.edit_message_text(
                f"❌ ဘေလင့်ဖြည့်တောင်းခံချက် {receipt_id} ပယ်ဖျက်ပြီးပါပြီ")

    elif data.startswith("approve_reg_") or data.startswith("reject_reg_"):
        if uid != ADMIN_ID:
            await query.edit_message_text(
                "⚠️ Admin မဟုတ်ပါက ဤလုပ်ဆောင်ချက်ကိုသုံးခွင့်မရှိပါ။")
            return

        action, _, user_id = data.split("_")
        user_id = int(user_id)

        if user_id not in db["pending_registrations"]:
            await query.edit_message_text("⚠️ အကောင့်ဖွင့်တောင်းခံချက်မရှိပါ။")
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

            try:
                await context.bot.send_message(
                    user_id,
                    "✅ သင့်အကောင့်အတည်ပြုပြီးပါပြီ! ယခုအခါ bot ကိုအသုံးပြုနိုင်ပါပြီ!"
                )
            except Exception as e:
                print(f"Error sending approval message: {e}")
            await query.edit_message_text(
                f"✅ သုံးစွဲသူ {user_id} ၏ အကောင့်ဖွင့်တောင်းခံချက်အတည်ပြုပြီးပါပြီ")
        else:
            del db["pending_registrations"][user_id]
            save_db(db)
            try:
                await context.bot.send_message(
                    user_id, "❌ သင့်အကောင့်ဖွင့်တောင်းခံချက်ပယ်ဖျက်ခံရပါသည်။")
            except Exception as e:
                print(f"Error sending rejection message: {e}")
            await query.edit_message_text(
                f"❌ သုံးစွဲသူ {user_id} ၏ အကောင့်ဖွင့်တောင်းခံချက်ပယ်ဖျက်ပြီးပါပြီ")

    elif data.startswith("approve_") or data.startswith("reject_"):
        if uid != ADMIN_ID:
            await query.edit_message_text(
                "⚠️ Admin မဟုတ်ပါက ဤလုပ်ဆောင်ချက်ကိုသုံးခွင့်မရှိပါ။")
            return

        action, receipt_id = data.split("_")
        if receipt_id not in db["receipts"]:
            await query.edit_message_text("⚠️ ငွေလွှဲသူIDမရှိပါ။")
            return

        receipt = db["receipts"][receipt_id]
        user_id = receipt["user_id"]
        game_type = receipt["game_type"]
        amount = receipt["amount"]
        quantity = receipt["quantity"]
        user = get_user(user_id)

        if action == "approve":
            if len(db["stock"][game_type].get(amount, [])) < quantity:
                await query.edit_message_text("⚠️ လက်ရှိမှာရနိုင်သောအိုင်တီမလုံလောက်ပါ။")
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

            codes_text = "\n".join([f"🔑 {code}" for code in codes])
            try:
                await context.bot.send_message(
                    user_id, f"✅ ငွေလွှဲသူIDဖြင့်အိုင်တီဝယ်ယူမှုအောင်မြင်ပါသည်!\n\n"
                    f"🎮 {game_name}\n"
                    f"💳 {amount} {unit} x {quantity}\n\n"
                    f"🔑 အိုင်တီကုဒ်များ:\n{codes_text}")
            except Exception as e:
                print(f"Error sending codes: {e}")
            await query.edit_message_text(f"✅ ငွေလွှဲသူID {receipt_id} အတည်ပြုပြီးပါပြီ")
        else:
            receipt["status"] = "rejected"
            save_db(db)
            try:
                await context.bot.send_message(
                    user_id, "❌ သင့်ငွေလွှဲသူIDဖြင့်အိုင်တီဝယ်ယူမှုပယ်ဖျက်ခံရပါသည်။")
            except Exception as e:
                print(f"Error sending rejection: {e}")
            await query.edit_message_text(f"❌ ငွေလွှဲသူID {receipt_id} ပယ်ဖျက်ပြီးပါပြီ")

    # Admin addstock interactive handlers
    elif data.startswith("addstock_"):
        if uid != ADMIN_ID:
            await query.edit_message_text(
                "⚠️ Admin မဟုတ်ပါက ဤလုပ်ဆောင်ချက်ကိုသုံးခွင့်မရှိပါ။")
            return

        game_type = data.split("_")[1]
        context.user_data['addstock_game'] = game_type

        keyboard = [[
            InlineKeyboardButton("🏠 မူလစာမျက်နှာသို့", callback_data="start")
        ]]
        game_name = get_game_display_name(game_type)
        unit = "Coin" if "MLBB" in game_type else "UC"
        await query.edit_message_text(
            f"🎮 {game_name} အိုင်တီထည့်ရန်:\n\n"
            f"📝 ဖော်မတ်: <amount> <price> <code1> <code2> ...\n"
            f"ဥပမာ: 1000 2500 CODE123 CODE456\n\n"
            f"🔢 {unit} ပမာဏ, ဈေးနှုန်း, အိုင်တီကုဒ်များရိုက်ထည့်ပါ:",
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
                "📄 ငွေလွှဲဓာတ်ပုံလက်ခံရရှိပါပြီ။ ကျေးဇူးပြု၍အောက်ပါအချက်များပို့ပေးပါ:\n\n"
                "📝 ဖော်မတ်: <ငွေလွှဲသူ ID (ဘေလင့်ဖြည့်ရန်)> <ငွေလွှဲပမာဏ>\n"
                "ဥပမာ: 123456 50000\n\n"
                "⚠️ သတိပြုရန်: ငွေလွှဲသူ ID မှားယွင်းပါက ငွေမရရှိနိုင်ပါ")
            return

        # Handle receipt purchase photos
        elif 'buying_game' in context.user_data and context.user_data.get(
                'receipt_step') == 'photo':
            context.user_data['receipt_photo_sent'] = True
            context.user_data[
                'receipt_photo_message_id'] = update.message.message_id
            context.user_data['receipt_step'] = 'id'

            await update.message.reply_text(
                "📄 ငွေလွှဲဓာတ်ပုံလက်ခံရရှိပါပြီ။ ကျေးဇူးပြု၍ ငွေလွှဲသူ ID (ဘေလင့်ဖြည့်ရန်) ရိုက်ထည့်ပေးပါ:\n\n"
                "ဥပမာ: 123456\n\n"
                "⚠️ သတိပြုရန်: ငွေလွှဲသူ ID မှားယွင်းပါက အိုင်တီမရနိုင်ပါ")
            return

    # Handle text messages
    if update.message.text:
        text = update.message.text.strip()

        # Handle admin message sending
        if uid == ADMIN_ID and 'admin_messaging' in context.user_data:
            target_user = context.user_data['admin_messaging']['user_id']
            try:
                await context.bot.send_message(target_user,
                                               f"📨 Admin မှ မက်ဆေ့:\n{text}")
                await update.message.reply_text(
                    f"✅ သုံးစွဲသူ {target_user} ထံ မက်ဆေ့ပို့ပြီးပါပြီ")
            except Exception as e:
                await update.message.reply_text(f"❌ မက်ဆေ့ပို့ရာတွင်အမှားတစ်ခုဖြစ်နေသည်: {e}")
            del context.user_data['admin_messaging']
            return

        # Handle quantity selection
        if 'selecting_quantity' in context.user_data:
            try:
                quantity = int(text)
                selection = context.user_data['selecting_quantity']

                if quantity < 1 or quantity > selection['max_quantity']:
                    await update.message.reply_text(
                        f"⚠️ အရေအတွက်သည် 1 မှ {selection['max_quantity']} အတွင်းရှိရပါမည်"
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
                            f"💵 ဘေလင့်ဖြင့်ဝယ်ယူရန် ({total_price} MMK)",
                            callback_data=
                            f"buy_balance_{game_type}_{amount}_{quantity}")
                    ])
                else:
                    keyboard.append([
                        InlineKeyboardButton("💰 ဘေလင့်ဖြည့်ရန်",
                                             callback_data="topup")
                    ])

                keyboard.append([
                    InlineKeyboardButton(
                        "📄 ငွေလွှဲသူIDဖြင့်ဝယ်ယူရန်",
                        callback_data=
                        f"buy_receipt_{game_type}_{amount}_{quantity}")
                ])
                keyboard.append([
                    InlineKeyboardButton(
                        "🏠 မူလစာမျက်နှာသို့",
                        callback_data=f"amount_{game_type}_{amount}")
                ])

                game_name = get_game_display_name(game_type)
                unit = "Coin" if "MLBB" in game_type else "UC"
                await update.message.reply_text(
                    f"🎮 {game_name}\n"
                    f"💳 {amount} {unit} x {quantity}\n"
                    f"💵 စုစုပေါင်းဈေးနှုန်း: {total_price} MMK\n"
                    f"💰 ဘေလင့်လက်ကျန်: {user['balance']} MMK\n\n"
                    f"💰 ငွေပေးချေမှုနည်းလမ်းရွေးချယ်ရန်:",
                    reply_markup=InlineKeyboardMarkup(keyboard))
                del context.user_data['selecting_quantity']
                return
            except ValueError:
                await update.message.reply_text("⚠️ နံပါတ်တစ်ခုရိုက်ထည့်ပေးပါ။")
                return

        # Handle admin addstock
        if uid == ADMIN_ID and 'addstock_game' in context.user_data:
            try:
                parts = text.split()
                if len(parts) < 3:
                    await update.message.reply_text(
                        "⚠️ ဖော်မတ်: <amount> <price> <code1>")
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
                    f"✅ {game_name} {amount} {unit}\n"
                    f"💵 ဈေးနှုန်း: {price} MMK\n"
                    f"📦 အိုင်တီ: {len(codes)} ခု ထည့်သွင်းပြီးပါပြီ")
                del context.user_data['addstock_game']
                return
            except ValueError:
                await update.message.reply_text("⚠️ ဈေးနှုန်းကိန်းဂဏန်းမဟုတ်ပါ။")
                return
            except Exception as e:
                await update.message.reply_text(f"⚠️ ဖော်မတ်မှားယွင်းနေပါသည်: {e}")
                return

        # Handle topup with receipt ID and amount
        if context.user_data.get('topup_photo_sent'):
            try:
                parts = text.split()
                if len(parts) != 2:
                    await update.message.reply_text(
                        "⚠️ ဖော်မတ်: <ငွေလွှဲသူ ID> <ငွေလွှဲပမာဏ>")
                    return

                receipt_id = parts[0]
                amount = int(parts[1])

                if not validate_receipt_id(receipt_id):
                    await update.message.reply_text(
                        "⚠️ ငွေလွှဲသူ ID သည် ၅-၆ လုံးဂဏန်းဖြစ်ရပါမည်")
                    return

                if amount < 1000:
                    await update.message.reply_text(
                        "⚠️ ငွေလွှဲပမာဏသည် 1000 MMK ထက်မနည်းရပါ"
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
                        "✅ အတည်ပြုရန်",
                        callback_data=f"approve_topup_{receipt_id}"),
                    InlineKeyboardButton(
                        "💬 မက်ဆေ့ပို့ရန်",
                        callback_data=f"message_topup_{receipt_id}"),
                    InlineKeyboardButton(
                        "❌ ပယ်ဖျက်ရန်",
                        callback_data=f"reject_topup_{receipt_id}")
                ]]

                try:
                    await context.bot.forward_message(
                        chat_id=ADMIN_ID,
                        from_chat_id=update.message.chat.id,
                        message_id=photo_message_id)

                    await context.bot.send_message(
                        chat_id=ADMIN_ID,
                        text=f"📥 ဘေလင့်ဖြည့်တောင်းခံချက်အသစ်:\n"
                        f"🆔 သုံးစွဲသူ: {uid}\n"
                        f"💰 နည်းလမ်း: {payment_method}\n"
                        f"📄 ငွေလွှဲသူ ID: {receipt_id}\n"
                        f"💵 ပမာဏ: {amount} MMK",
                        reply_markup=InlineKeyboardMarkup(keyboard))

                    await update.message.reply_text("⏳ Admin ထံတောင်းခံချက်ပို့ပြီးပါပြီ...")
                except Exception as e:
                    await update.message.reply_text(f"❌ Admin ထံပို့ရာတွင်အမှားတစ်ခုဖြစ်နေသည်: {e}")

                # Clear user data
                for key in ['topup_method', 'topup_photo_sent', 'topup_photo_message_id']:
                    context.user_data.pop(key, None)
                return
            except ValueError:
                await update.message.reply_text("⚠️ ငွေလွှဲပမာဏကိန်းဂဏန်းမဟုတ်ပါ။")
                return
            except Exception as e:
                await update.message.reply_text(f"⚠️ ဖော်မတ်မှားယွင်းနေပါသည်: {e}")
                return

        # Handle receipt purchase with receipt ID
        if 'buying_game' in context.user_data and context.user_data.get(
                'receipt_step') == 'id':
            if not validate_receipt_id(text):
                await update.message.reply_text(
                    "⚠️ ငွေလွှဲသူ ID သည် ၅-၆ လုံးဂဏန်းဖြစ်ရပါမည်")
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
                InlineKeyboardButton("✅ အတည်ပြုရန်",
                                     callback_data=f"approve_{text}"),
                InlineKeyboardButton("💬 မက်ဆေ့ပို့ရန်",
                                     callback_data=f"message_{text}"),
                InlineKeyboardButton("❌ ပယ်ဖျက်ရန်",
                                     callback_data=f"reject_{text}")
            ]]

            try:
                await context.bot.forward_message(
                    chat_id=ADMIN_ID,
                    from_chat_id=update.message.chat.id,
                    message_id=photo_message_id)

                await context.bot.send_message(
                    chat_id=ADMIN_ID,
                    text=f"📥 အိုင်တီဝယ်ယူတောင်းခံချက်အသစ်:\n"
                    f"🆔 သုံးစွဲသူ: {uid}\n"
                    f"🎮 ဂိမ်း: {game_name}\n"
                    f"💳 {amount} {unit} x {quantity}\n"
                    f"📄 ငွေလွှဲသူ ID: {text}",
                    reply_markup=InlineKeyboardMarkup(keyboard))
                await update.message.reply_text("⏳ Admin ထံတောင်းခံချက်ပို့ပြီးပါပြီ...")
            except Exception as e:
                await update.message.reply_text(f"❌ Admin ထံပို့ရာတွင်အမှားတစ်ခုဖြစ်နေသည်: {e}")

            # Clear user data
            for key in ['buying_game', 'buying_amount', 'buying_quantity', 
                       'receipt_photo_sent', 'receipt_photo_message_id', 'receipt_step']:
                context.user_data.pop(key, None)
            return

# ---------------- Admin Commands ----------------
async def setbalance(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        return
    try:
        args = context.args
        if len(args) != 2:
            await update.message.reply_text(
                "အသုံးပြုနည်း: /setbalance <user_id> <amount>")
            return
            
        uid = int(args[0])
        amount = int(args[1])
        user = get_user(uid)
        user["balance"] = amount
        save_db(db)
        await update.message.reply_text(
            f"✅ သုံးစွဲသူ {uid} ၏ ဘေလင့်လက်ကျန်ကို {amount} MMK သတ်မှတ်ပြီးပါပြီ")
    except Exception as e:
        await update.message.reply_text(
            f"အမှား: {e}\nအသုံးပြုနည်း: /setbalance <user_id> <amount>")

async def addstock(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        return

    # Interactive version
    keyboard = [[
        InlineKeyboardButton("🎮 Mobile Legends (Bal)",
                             callback_data="addstock_MLBBbal")
    ],
                [
                    InlineKeyboardButton("🎮 Mobile Legends (PH)",
                                         callback_data="addstock_MLBBph")
                ],
                [
                    InlineKeyboardButton("🎮 PUPG Mobile",
                                         callback_data="addstock_PUPG")
                ]]
    await update.message.reply_text(
        "🎮 ဂိမ်းရွေးချယ်ရန်:",
        reply_markup=InlineKeyboardMarkup(keyboard))

async def delstock(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        return

    if len(context.args) < 3:
        await update.message.reply_text(
            "အသုံးပြုနည်း: /delstock <MLBBbal/MLBBph/PUPG> <amount> <code>")
        return

    try:
        game_type = context.args[0]
        amount = context.args[1]
        code_to_delete = context.args[2]

        if game_type not in ["MLBBbal", "MLBBph", "PUPG"]:
            await update.message.reply_text(
                "ဂိမ်းအမျိုးအစား: MLBBbal, MLBBph, သို့မဟုတ် PUPG")
            return

        if game_type not in db["stock"] or amount not in db["stock"][game_type]:
            await update.message.reply_text(
                "⚠️ ဤဂိမ်းနှင့်ပမာဏအတွက်အိုင်တီမရှိပါ။")
            return

        if code_to_delete in db["stock"][game_type][amount]:
            db["stock"][game_type][amount].remove(code_to_delete)
            save_db(db)

            game_name = get_game_display_name(game_type)
            unit = "Coin" if "MLBB" in game_type else "UC"
            await update.message.reply_text(
                f"✅ {game_name} {amount} {unit} ၏ အိုင်တီ {code_to_delete} ဖျက်ပြီးပါပြီ"
            )
        else:
            await update.message.reply_text("⚠️ ဤအိုင်တီမရှိပါ။")
    except Exception as e:
        await update.message.reply_text(
            f"အမှား: {e}\nအသုံးပြုနည်း: /delstock <MLBBbal/MLBBph/PUPG> <amount> <code>")

async def setprice(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        return
    if len(context.args) < 3:
        await update.message.reply_text(
            "အသုံးပြုနည်း: /setprice <MLBBbal/MLBBph/PUPG> <amount> <price>")
        return

    try:
        game_type = context.args[0]
        amount = context.args[1]
        price = int(context.args[2])

        if game_type not in ["MLBBbal", "MLBBph", "PUPG"]:
            await update.message.reply_text(
                "ဂိမ်းအမျိုးအစား: MLBBbal, MLBBph, သို့မဟုတ် PUPG")
            return

        if game_type not in db["prices"]:
            db["prices"][game_type] = {}

        db["prices"][game_type][amount] = price
        save_db(db)

        game_name = get_game_display_name(game_type)
        unit = "Coin" if "MLBB" in game_type else "UC"
        await update.message.reply_text(
            f"✅ {game_name} {amount} {unit} ၏ ဈေးနှုန်းကို {price} MMK သတ်မှတ်ပြီးပါပြီ"
        )
    except Exception as e:
        await update.message.reply_text(
            f"အမှား: {e}\nအသုံးပြုနည်း: /setprice <MLBBbal/MLBBph/PUPG> <amount> <price>")

async def setpayment(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        return
    try:
        if len(context.args) < 3:
            await update.message.reply_text(
                "အသုံးပြုနည်း: /setpayment <Wave/KPay> <phone> <name>")
            return
            
        method = context.args[0].title()
        phone = context.args[1]
        name = " ".join(context.args[2:])

        if method not in ["Wave", "Kpay"]:
            await update.message.reply_text(
                "ငွေလွှဲနည်းလမ်း: Wave သို့မဟုတ် KPay")
            return

        db["payment"][method] = {"phone": phone, "name": name}
        save_db(db)
        await update.message.reply_text(
            f"✅ {method} ငွေလွှဲအချက်အလက်များသတ်မှတ်ပြီးပါပြီ\n📱 ဖုန်းနံပါတ်: {phone}\n👤 အမည်: {name}"
        )
    except Exception as e:
        await update.message.reply_text(
            f"အမှား: {e}\nအသုံးပြုနည်း: /setpayment <Wave/KPay> <phone> <name>")

async def viewhistory(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        return
    try:
        if not context.args:
            await update.message.reply_text("အသုံးပြုနည်း: /viewhistory <user_id>")
            return
            
        uid = int(context.args[0])
        user = get_user(uid)
        if not user["history"]:
            await update.message.reply_text(
                f"သုံးစွဲသူ {uid} ၏ မှတ်တမ်းမရှိပါ။")
            return

        history_text = ""
        for i, h in enumerate(user["history"], 1):
            history_text += f"{i}. {h}\n"

        # Telegram message length limit
        if len(history_text) > 4000:
            history_text = history_text[:4000] + "\n... (ဆက်လက်ဖော်ပြရန်နေရာမလုံလောက်ပါ)"

        await update.message.reply_text(
            f"📜 သုံးစွဲသူ {uid} ၏ မှတ်တမ်း:\n{history_text}")
    except Exception as e:
        await update.message.reply_text(f"အမှား: {e}\nအသုံးပြုနည်း: /viewhistory <user_id>")

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
        [r for r in db["receipts"].values() if r.get("status") == "pending"])
    pending_topups = len(
        [r for r in db["topup_requests"].values() if r.get("status") == "pending"])
    pending_registrations = len(db.get("pending_registrations", {}))

    help_text = f"""
🔧 Admin Commands:

/setbalance <user_id> <amount> - သုံးစွဲသူဘေလင့်သတ်မှတ်ရန်
/addstock - အိုင်တီထည့်ရန် (အပြန်အလှန်စနစ်)
/delstock <MLBBbal/MLBBph/PUPG> <amount> <code> - အိုင်တီဖျက်ရန်
/setprice <MLBBbal/MLBBph/PUPG> <amount> <price> - ဈေးနှုန်းသတ်မှတ်ရန်
/setpayment <Wave/Kpay> <phone> <name> - ငွေလွှဲအချက်အလက်သတ်မှတ်ရန်
/viewhistory <user_id> - သုံးစွဲသူမှတ်တမ်းကြည့်ရန်
/admhelp - ဤအကူအညီစာမျက်နှာပြရန်

📊 စာရင်းဇယား:
🎮 MLBB Bal အိုင်တီ: {mlbbbal_count}
🎮 MLBB PH အိုင်တီ: {mlbbph_count}
🎮 PUPG အိုင်တီ: {pupg_count}
👥 သုံးစွဲသူ: {len(db["users"])}
📦 စုစုပေါင်းအမှာစာ: {total_orders}
💵 သုံးစွဲသူဘေလင့်စုစုပေါင်း: {total_user_balance:,} MMK
💰 စုစုပေါင်းရောင်းအား: {db.get('sales_total', 0):,} MMK
⏳ စောင့်ဆိုင်းငွေလွှဲသူID: {pending_receipts}
⏳ စောင့်ဆိုင်းဘေလင့်ဖြည့်: {pending_topups}
⏳ စောင့်ဆိုင်းအကောင့်ဖွင့်: {pending_registrations}

📝 ဥပမာများ:
/setprice MLBBbal 1000 2500
/setprice PUPG 60 1500
/delstock MLBBbal 1000 CODE123
/setpayment Kpay 09123456789 John Doe

🔧 စီမံခန့်ခွဲမှုလမ်းညွှန်ချက်များ:
• သုံးစွဲသူအကောင့်များကို Admin မှအတည်ပြုပေးရပါမည်
• အိုင်တီပမာဏများကိုဂရုတစိုက်ထည့်သွင်းပါ
• Admin မှသုံးစွဲသူများထံမက်ဆေ့ပို့နိုင်သည် (💬 ခလုတ်)
    """

    await update.message.reply_text(help_text)

# ---------------- Main Application ----------------
def main():
    # Check required environment variables
    if not BOT_TOKEN:
        print("Error: BOT_TOKEN environment variable is required!")
        return
    
    if ADMIN_ID == 0:
        print("Error: ADMIN_ID environment variable is required!")
        return
    
    try:
        app = Application.builder().token(BOT_TOKEN).build()
        
        # Add handlers
        app.add_handler(CommandHandler("start", start))
        app.add_handler(CommandHandler("setbalance", setbalance))
        app.add_handler(CommandHandler("addstock", addstock))
        app.add_handler(CommandHandler("delstock", delstock))
        app.add_handler(CommandHandler("setprice", setprice))
        app.add_handler(CommandHandler("setpayment", setpayment))
        app.add_handler(CommandHandler("viewhistory", viewhistory))
        app.add_handler(CommandHandler("admhelp", admhelp))
        app.add_handler(CallbackQueryHandler(callback_handler))
        app.add_handler(MessageHandler(filters.ALL & ~filters.COMMAND, handle_message))
        
        print("Bot is starting...")
        print(f"Database file: {DB_FILE}")
        print(f"Admin ID: {ADMIN_ID}")
        
        # Render ပေါ်မှာ web server မလိုအပ်ပါ - polling ကိုပဲသုံးပါ
        app.run_polling(drop_pending_updates=True, allowed_updates=Update.ALL_TYPES)
        
    except Exception as e:
        print(f"Error starting bot: {e}")

if __name__ == "__main__":
    main()
