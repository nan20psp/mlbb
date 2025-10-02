import os
import json
import random
import asyncio
from datetime import datetime
from typing import Dict, List, Optional, Any
from dataclasses import dataclass
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, ContextTypes, MessageHandler, filters
from dotenv import load_dotenv

# Load environment variables
load_dotenv()
BOT_TOKEN = os.getenv("BOT_TOKEN", "7927660379:AAGtm-CvAunvvANaaYvzlmRVjjBgJcmEh58")
ADMIN_ID = int(os.getenv("ADMIN_ID", "7669567524"))

# Constants
DB_FILE = "database.json"
GAME_TYPES = ["MLBBbal", "MLBBph", "PUPG"]
PAYMENT_METHODS = ["Wave", "KPay"]

@dataclass
class User:
    user_id: int
    balance: int = 0
    history: List[Dict] = None
    approved: bool = False
    
    def __post_init__(self):
        if self.history is None:
            self.history = []

@dataclass
class StockItem:
    game_type: str
    amount: str
    codes: List[str]
    price: int

@dataclass
class PaymentInfo:
    phone: str
    name: str

class DatabaseManager:
    def __init__(self, db_file: str):
        self.db_file = db_file
        self.db = self._load_db()
    
    def _load_db(self) -> Dict[str, Any]:
        """Load database from file or create default structure"""
        if not os.path.exists(self.db_file):
            return self._create_default_db()
        
        with open(self.db_file, "r", encoding='utf-8') as f:
            data = json.load(f)
        
        return self._migrate_db(data)
    
    def _create_default_db(self) -> Dict[str, Any]:
        """Create default database structure"""
        return {
            "users": {},
            "stock": {game: {} for game in GAME_TYPES},
            "receipts": {},
            "topup_requests": {},
            "prices": {game: {} for game in GAME_TYPES},
            "payment": {
                "Wave": {"phone": "09673585480", "name": "Nine Nine"},
                "KPay": {"phone": "09678786528", "name": "Ma May Phoo Wai"}
            },
            "sales_total": 0,
            "pending_registrations": {}
        }
    
    def _migrate_db(self, data: Dict) -> Dict:
        """Migrate old database structure to new one"""
        # Migration logic here (simplified)
        if "PUBG" in data.get("stock", {}):
            data["stock"]["PUPG"] = data["stock"].pop("PUBG")
        if "PUBG" in data.get("prices", {}):
            data["prices"]["PUPG"] = data["prices"].pop("PUBG")
        
        # Ensure all required keys exist
        for key in ["users", "stock", "prices", "payment", "sales_total", "pending_registrations"]:
            if key not in data:
                data[key] = self._create_default_db()[key]
        
        return data
    
    def save_db(self):
        """Save database to file"""
        with open(self.db_file, "w", encoding='utf-8') as f:
            json.dump(self.db, f, indent=2, ensure_ascii=False)
    
    def get_user(self, user_id: int) -> User:
        """Get user or create new one"""
        if str(user_id) not in self.db["users"]:
            self.db["users"][str(user_id)] = {
                "balance": 0,
                "history": [],
                "approved": False
            }
            self.save_db()
        
        user_data = self.db["users"][str(user_id)]
        return User(
            user_id=user_id,
            balance=user_data["balance"],
            history=user_data["history"],
            approved=user_data.get("approved", False)
        )
    
    def update_user(self, user: User):
        """Update user in database"""
        self.db["users"][str(user.user_id)] = {
            "balance": user.balance,
            "history": user.history,
            "approved": user.approved
        }
        self.save_db()
    
    def get_stock(self, game_type: str, amount: str) -> List[str]:
        """Get stock for specific game type and amount"""
        return self.db["stock"].get(game_type, {}).get(amount, [])
    
    def update_stock(self, game_type: str, amount: str, codes: List[str]):
        """Update stock for specific game type and amount"""
        if game_type not in self.db["stock"]:
            self.db["stock"][game_type] = {}
        self.db["stock"][game_type][amount] = codes
        self.save_db()
    
    def get_price(self, game_type: str, amount: str) -> int:
        """Get price for specific game type and amount"""
        return self.db["prices"].get(game_type, {}).get(amount, 0)

class BotService:
    def __init__(self, db_manager: DatabaseManager):
        self.db = db_manager
    
    @staticmethod
    def get_game_display_name(game_type: str) -> str:
        """Get display name for game type"""
        names = {
            "MLBBbal": "Mobile Legends (Bal)",
            "MLBBph": "Mobile Legends (PH)", 
            "PUPG": "PUPG Mobile"
        }
        return names.get(game_type, game_type)
    
    @staticmethod
    def get_game_unit(game_type: str) -> str:
        """Get unit for game type"""
        return "Coin" if "MLBB" in game_type else "UC"
    
    def generate_receipt_id(self) -> str:
        """Generate unique receipt ID"""
        while True:
            rid = str(random.randint(10000, 999999))
            if rid not in self.db.db["receipts"] and rid not in self.db.db["topup_requests"]:
                return rid
    
    def validate_receipt_id(self, receipt_id: str) -> bool:
        """Validate receipt ID format"""
        return receipt_id.isdigit() and 5 <= len(receipt_id) <= 6
    
    def get_available_games(self) -> List[str]:
        """Get list of available games with stock"""
        available_games = []
        for game_type in GAME_TYPES:
            total_codes = sum(
                len(codes) 
                for codes in self.db.db["stock"].get(game_type, {}).values()
            )
            if total_codes > 0:
                available_games.append(game_type)
        return available_games
    
    def get_available_amounts(self, game_type: str) -> List[str]:
        """Get available amounts for a game type that have stock"""
        amounts = []
        if game_type in self.db.db["stock"]:
            for amount, codes in self.db.db["stock"][game_type].items():
                if codes:  # Only include amounts with available codes
                    amounts.append(amount)
        return sorted(amounts)

class KeyboardManager:
    """Manage all bot keyboards"""
    
    @staticmethod
    def main_menu() -> InlineKeyboardMarkup:
        """Main menu keyboard"""
        keyboard = [
            [InlineKeyboardButton("📋 အကောင့်ဖွင့်ရန်", callback_data="register")],
            [InlineKeyboardButton("💰 လက်ကျန်ငွေ", callback_data="balance")],
            [InlineKeyboardButton("💳 ငွေဖြည့်ရန်", callback_data="topup")],
            [InlineKeyboardButton("🛒 ကုဒ်ဝယ်ရန်", callback_data="buy")],
            [InlineKeyboardButton("ℹ️ အကူအညီ", callback_data="help")]
        ]
        return InlineKeyboardMarkup(keyboard)
    
    @staticmethod
    def back_button(target: str = "start") -> InlineKeyboardMarkup:
        """Back button keyboard"""
        keyboard = [[InlineKeyboardButton("🔙 ပြန်သွားရန်", callback_data=target)]]
        return InlineKeyboardMarkup(keyboard)
    
    @staticmethod
    def payment_methods() -> InlineKeyboardMarkup:
        """Payment methods keyboard"""
        keyboard = [
            [InlineKeyboardButton("📱 Wave", callback_data="topup_wave")],
            [InlineKeyboardButton("📱 Kpay", callback_data="topup_kpay")],
            [InlineKeyboardButton("🔙 ပြန်သွားရန်", callback_data="start")]
        ]
        return InlineKeyboardMarkup(keyboard)
    
    @staticmethod
    def game_selection(available_games: List[str], bot_service: BotService) -> InlineKeyboardMarkup:
        """Game selection keyboard"""
        keyboard = []
        for game_type in available_games:
            total_codes = sum(
                len(codes) 
                for codes in bot_service.db.db["stock"].get(game_type, {}).values()
            )
            game_name = bot_service.get_game_display_name(game_type)
            keyboard.append([
                InlineKeyboardButton(
                    f"🎮 {game_name} ({total_codes})", 
                    callback_data=f"select_{game_type}"
                )
            ])
        keyboard.append([InlineKeyboardButton("🔙 ပြန်သွားရန်", callback_data="start")])
        return InlineKeyboardMarkup(keyboard)
    
    @staticmethod
    def amount_selection(game_type: str, amounts: List[str], bot_service: BotService) -> InlineKeyboardMarkup:
        """Amount selection keyboard"""
        keyboard = []
        for amount in amounts:
            codes_count = len(bot_service.db.get_stock(game_type, amount))
            price = bot_service.db.get_price(game_type, amount)
            unit = bot_service.get_game_unit(game_type)
            keyboard.append([
                InlineKeyboardButton(
                    f"💎 {amount} {unit} - {price} MMK ({codes_count})",
                    callback_data=f"amount_{game_type}_{amount}"
                )
            ])
        keyboard.append([
            InlineKeyboardButton("🔙 ပြန်သွားရန်", callback_data="buy")
        ])
        return InlineKeyboardMarkup(keyboard)

class MessageBuilder:
    """Build formatted messages for the bot"""
    
    @staticmethod
    def welcome_message(user_name: str) -> str:
        """Welcome message"""
        return f"👋 ကြိုဆိုပါတယ် {user_name}! ကျေးဇူးပြု၍ အကောင့်ဖွင့်ပါ!"
    
    @staticmethod
    def balance_message(balance: int) -> str:
        """Balance message"""
        return f"💰 လက်ကျန်ငွေ: {balance} MMK"
    
    @staticmethod
    def payment_info_message(method: str, payment_info: PaymentInfo) -> str:
        """Payment information message"""
        return (
            f"💳 {method} ငွေဖြည့်ရန်:\n\n"
            f"📱 ဖုန်းနံပါတ်: {payment_info.phone}\n"
            f"👤 အမည်: {payment_info.name}\n\n"
            f"📋 ဖုန်းနံပါတ်ကို ကူးယူပြီး ငွေဖြည့်ပါ။\n\n"
            f"⚠️ သတိပြုရန်: ငွေလွှဲပြီးနောက် ငွေလွှဲအတည်ပြုချက် (Screenshot) ပို့ပါ။\n"
            f"ငွေလွှဲပြီးနောက် အောက်ပါအချက်များကို ပို့ပေးပါ:\n"
            f"• ငွေလွှဲသူ ID (Transaction ID)\n"
            f"• ငွေလွှဲသည့်ပမာဏ\n\n"
            f"⏳ ငွေဖြည့်ပြီးနောက် 5-10 မိနစ်အတွင်း ငွေထည့်သွင်းပြီးကြောင်း အကြောင်းကြားပါမည်။"
        )
    
    @staticmethod
    def purchase_summary(game_type: str, amount: str, quantity: int, total_price: int, 
                        user_balance: int, max_quantity: int, bot_service: BotService) -> str:
        """Purchase summary message"""
        game_name = bot_service.get_game_display_name(game_type)
        unit = bot_service.get_game_unit(game_type)
        
        return (
            f"🎮 {game_name}\n"
            f"💎 {amount} {unit} x {quantity}\n"
            f"💰 စုစုပေါင်းကျသင့်ငွေ: {total_price} MMK\n"
            f"💵 လက်ကျန်ငွေ: {user_balance} MMK\n"
            f"📦 ရရှိနိုင်သောအရေအတွက်: {max_quantity} ခု\n\n"
            f"🔢 ဝယ်ယူလိုသောအရေအတွက် ရိုက်ထည့်ပါ (1 to {max_quantity}):"
        )

class TelegramBot:
    def __init__(self):
        self.db_manager = DatabaseManager(DB_FILE)
        self.bot_service = BotService(self.db_manager)
        self.keyboard_manager = KeyboardManager()
        self.message_builder = MessageBuilder()
        self.app = None
    
    async def start(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /start command"""
        user = update.effective_user
        welcome_msg = self.message_builder.welcome_message(user.first_name)
        
        if update.message:
            await update.message.reply_text(
                welcome_msg, 
                reply_markup=self.keyboard_manager.main_menu()
            )
        else:
            await update.callback_query.edit_message_text(
                welcome_msg,
                reply_markup=self.keyboard_manager.main_menu()
            )
    
    async def handle_callback(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle callback queries"""
        query = update.callback_query
        await query.answer()
        data = query.data
        user_id = query.from_user.id
        
        # Route to appropriate handler
        if data == "start":
            await self.start(update, context)
        elif data == "register":
            await self.handle_register(update, context, user_id)
        elif data == "balance":
            await self.handle_balance(update, context, user_id)
        elif data == "topup":
            await self.handle_topup(update, context, user_id)
        elif data == "buy":
            await self.handle_buy(update, context, user_id)
        elif data == "help":
            await self.handle_help(update, context)
        elif data.startswith("topup_"):
            await self.handle_payment_method(update, context, data)
        elif data.startswith("select_"):
            await self.handle_game_selection(update, context, data)
        elif data.startswith("amount_"):
            await self.handle_amount_selection(update, context, data, user_id)
        elif data.startswith("buy_balance_"):
            await self.handle_balance_purchase(update, context, data, user_id)
        elif data.startswith("buy_receipt_"):
            await self.handle_receipt_purchase(update, context, data, user_id)
    
    async def handle_register(self, update: Update, context: ContextTypes.DEFAULT_TYPE, user_id: int):
        """Handle user registration"""
        query = update.callback_query
        
        # Check if user is already approved
        user = self.db_manager.get_user(user_id)
        if user.approved:
            await query.edit_message_text(
                "✅ အကောင့်ဖွင့်ပြီးသားဖြစ်ပါသည်။",
                reply_markup=self.keyboard_manager.back_button()
            )
            return
        
        # Check if pending registration exists
        if str(user_id) in self.db_manager.db["pending_registrations"]:
            await query.edit_message_text(
                "⏳ အကောင့်ဖွင့်ရန် တောင်းဆိုထားပြီးဖြစ်သည်။ Admin မှ အတည်ပြုပေးရန်စောင့်ဆိုင်းပါ။",
                reply_markup=self.keyboard_manager.back_button()
            )
            return
        
        # Create registration request
        self.db_manager.db["pending_registrations"][str(user_id)] = {
            "user_id": user_id,
            "username": query.from_user.first_name,
            "status": "pending"
        }
        self.db_manager.save_db()
        
        # Notify admin
        await self._notify_admin_registration(context, user_id, query)
        
        await query.edit_message_text(
            "📝 အကောင့်ဖွင့်ရန် တောင်းဆိုပြီးပါပြီ။ Admin မှ အတည်ပြုပေးပါမည်။",
            reply_markup=self.keyboard_manager.back_button()
        )
    
    async def handle_balance(self, update: Update, context: ContextTypes.DEFAULT_TYPE, user_id: int):
        """Handle balance check"""
        query = update.callback_query
        user = self.db_manager.get_user(user_id)
        
        if not user.approved:
            await query.edit_message_text(
                "❌ အကောင့်အတည်ပြုချက် မရှိသေးပါ။ Admin မှ အတည်ပြုပေးရန်စောင့်ဆိုင်းပါ။",
                reply_markup=self.keyboard_manager.back_button()
            )
            return
        
        balance_msg = self.message_builder.balance_message(user.balance)
        await query.edit_message_text(
            balance_msg,
            reply_markup=self.keyboard_manager.back_button("start")
        )
    
    async def handle_topup(self, update: Update, context: ContextTypes.DEFAULT_TYPE, user_id: int):
        """Handle topup menu"""
        query = update.callback_query
        user = self.db_manager.get_user(user_id)
        
        if not user.approved:
            await query.edit_message_text(
                "❌ အကောင့်အတည်ပြုချက် မရှိသေးပါ။",
                reply_markup=self.keyboard_manager.back_button()
            )
            return
        
        await query.edit_message_text(
            "💳 ငွေဖြည့်ရန် နည်းလမ်းရွေးချယ်ပါ:",
            reply_markup=self.keyboard_manager.payment_methods()
        )
    
    async def handle_payment_method(self, update: Update, context: ContextTypes.DEFAULT_TYPE, data: str):
        """Handle payment method selection"""
        query = update.callback_query
        method = data.split("_")[1].title()
        payment_info = self.db_manager.db["payment"][method]
        
        context.user_data['topup_method'] = method
        
        payment_msg = self.message_builder.payment_info_message(method, payment_info)
        
        keyboard = [
            [InlineKeyboardButton(f"📋 {payment_info['phone']}", callback_data=f"copy_{payment_info['phone']}")],
            [InlineKeyboardButton("🔙 ပြန်သွားရန်", callback_data="topup")]
        ]
        
        await query.edit_message_text(
            payment_msg,
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
    
    async def handle_buy(self, update: Update, context: ContextTypes.DEFAULT_TYPE, user_id: int):
        """Handle buy menu"""
        query = update.callback_query
        user = self.db_manager.get_user(user_id)
        
        if not user.approved:
            await query.edit_message_text(
                "❌ အကောင့်အတည်ပြုချက် မရှိသေးပါ။",
                reply_markup=self.keyboard_manager.back_button()
            )
            return
        
        available_games = self.bot_service.get_available_games()
        
        if not available_games:
            await query.edit_message_text(
                "❌ ရောင်းချရန် ကုဒ်မရှိပါ။",
                reply_markup=self.keyboard_manager.back_button()
            )
            return
        
        await query.edit_message_text(
            "🎮 ဂိမ်းရွေးချယ်ပါ:",
            reply_markup=self.keyboard_manager.game_selection(available_games, self.bot_service)
        )
    
    async def handle_game_selection(self, update: Update, context: ContextTypes.DEFAULT_TYPE, data: str):
        """Handle game selection"""
        query = update.callback_query
        game_type = data.split("_")[1]
        amounts = self.bot_service.get_available_amounts(game_type)
        
        if not amounts:
            await query.edit_message_text(
                "❌ ဤဂိမ်းအတွက် ကုဒ်မရှိပါ။",
                reply_markup=self.keyboard_manager.back_button("buy")
            )
            return
        
        await query.edit_message_text(
            f"🎮 {self.bot_service.get_game_display_name(game_type)}\n💎 ပမာဏရွေးချယ်ပါ:",
            reply_markup=self.keyboard_manager.amount_selection(game_type, amounts, self.bot_service)
        )
    
    async def handle_amount_selection(self, update: Update, context: ContextTypes.DEFAULT_TYPE, data: str, user_id: int):
        """Handle amount selection"""
        query = update.callback_query
        parts = data.split("_")
        game_type = parts[1]
        amount = parts[2]
        
        stock = self.db_manager.get_stock(game_type, amount)
        if not stock:
            await query.edit_message_text(
                "❌ ဤပမာဏအတွက် ကုဒ်မရှိပါ။",
                reply_markup=self.keyboard_manager.back_button(f"select_{game_type}")
            )
            return
        
        price = self.db_manager.get_price(game_type, amount)
        user = self.db_manager.get_user(user_id)
        max_quantity = len(stock)
        
        # Store selection data for text input
        context.user_data['selecting_quantity'] = {
            'game_type': game_type,
            'amount': amount,
            'price': price,
            'max_quantity': max_quantity
        }
        
        purchase_msg = self.message_builder.purchase_summary(
            game_type, amount, 1, price, user.balance, max_quantity, self.bot_service
        )
        
        await query.edit_message_text(
            purchase_msg,
            reply_markup=self.keyboard_manager.back_button(f"select_{game_type}")
        )
    
    async def handle_balance_purchase(self, update: Update, context: ContextTypes.DEFAULT_TYPE, data: str, user_id: int):
        """Handle purchase using balance"""
        query = update.callback_query
        parts = data.split("_")
        game_type = parts[2]
        amount = parts[3]
        quantity = int(parts[4])
        
        user = self.db_manager.get_user(user_id)
        price = self.db_manager.get_price(game_type, amount)
        total_price = price * quantity
        
        # Validate purchase
        if user.balance < total_price:
            await query.edit_message_text(
                "❌ လက်ကျန်ငွေ မလုံလောက်ပါ။",
                reply_markup=InlineKeyboardMarkup([[
                    InlineKeyboardButton("💳 ငွေဖြည့်ရန်", callback_data="topup"),
                    InlineKeyboardButton("🔙 ပြန်သွားရန်", callback_data=f"quantity_{game_type}_{amount}_{quantity}")
                ]])
            )
            return
        
        stock = self.db_manager.get_stock(game_type, amount)
        if len(stock) < quantity:
            await query.edit_message_text(
                "❌ ကုဒ်မလုံလောက်ပါ။",
                reply_markup=self.keyboard_manager.back_button("buy")
            )
            return
        
        # Process purchase
        codes = stock[:quantity]
        self.db_manager.update_stock(game_type, amount, stock[quantity:])
        
        user.balance -= total_price
        self.db_manager.db["sales_total"] += total_price
        
        # Add to history
        user.history.append({
            "type": "balance",
            "codes": codes,
            "game": self.bot_service.get_game_display_name(game_type),
            "amount": amount,
            "quantity": quantity,
            "total_price": total_price,
            "timestamp": datetime.now().isoformat()
        })
        
        self.db_manager.update_user(user)
        
        # Send codes to user
        codes_text = "\n".join([f"🔑 {code}" for code in codes])
        success_msg = (
            f"✅ ကုဒ်ဝယ်ယူမှု အောင်မြင်ပါသည်!\n\n"
            f"🎮 {self.bot_service.get_game_display_name(game_type)}\n"
            f"💎 {amount} {self.bot_service.get_game_unit(game_type)} x {quantity}\n"
            f"💰 ကျသင့်ငွေ: {total_price} MMK\n\n"
            f"🔑 ကုဒ်များ:\n{codes_text}\n\n"
            f"💵 လက်ကျန်ငွေ: {user.balance} MMK"
        )
        
        await query.edit_message_text(
            success_msg,
            reply_markup=self.keyboard_manager.back_button()
        )
    
    async def handle_receipt_purchase(self, update: Update, context: ContextTypes.DEFAULT_TYPE, data: str, user_id: int):
        """Handle purchase using receipt"""
        query = update.callback_query
        parts = data.split("_")
        game_type = parts[2]
        amount = parts[3]
        quantity = int(parts[4])
        
        context.user_data['buying_game'] = game_type
        context.user_data['buying_amount'] = amount
        context.user_data['buying_quantity'] = quantity
        context.user_data['receipt_step'] = 'photo'
        
        await query.edit_message_text(
            "📸 ငွေလွှဲအတည်ပြုချက် (Screenshot) ပို့ပေးပါ။\n\n"
            "ငွေလွှဲပြီးနောက် Screenshot ရိုက်ယူပြီး ဤဘော့သို့ ပို့ပေးပါ။",
            reply_markup=self.keyboard_manager.back_button(f"quantity_{game_type}_{amount}_{quantity}")
        )
    
    async def handle_help(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle help command"""
        help_text = (
            "ℹ️ အသုံးပြုနည်း:\n\n"
            "1️⃣ အကောင့်ဖွင့်ရန် - ပထမဆုံး အကောင့်ဖွင့်ရမည်\n"
            "2️⃣ ငွေဖြည့်ရန် - ဂိမ်းကုဒ်ဝယ်ယူရန် ငွေဖြည့်ပါ\n"
            "3️⃣ ကုဒ်ဝယ်ယူရန် - လိုချင်သောဂိမ်းကုဒ်ဝယ်ယူပါ\n\n"
            "📞 အကူအညီလိုပါက Admin ဆီသို့ ဆက်သွယ်ပါ။"
        )
        
        query = update.callback_query
        await query.edit_message_text(
            help_text,
            reply_markup=self.keyboard_manager.back_button()
        )
    
    async def _notify_admin_registration(self, context: ContextTypes.DEFAULT_TYPE, user_id: int, query):
        """Notify admin about new registration"""
        keyboard = [
            [
                InlineKeyboardButton("✅ အတည်ပြုရန်", callback_data=f"approve_reg_{user_id}"),
                InlineKeyboardButton("❌ ငြင်းပယ်ရန်", callback_data=f"reject_reg_{user_id}")
            ]
        ]
        
        await context.bot.send_message(
            chat_id=ADMIN_ID,
            text=(
                f"📝 အသစ်အကောင့်ဖွင့်ရန် တောင်းဆိုချက်:\n"
                f"👤 User ID: {user_id}\n"
                f"📛 အမည်: {query.from_user.first_name}\n"
                f"🔗 Username: @{query.from_user.username or 'N/A'}"
            ),
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
    
    async def handle_message(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle text messages and photos"""
        # Add message handling logic here
        pass
    
    def setup_handlers(self):
        """Setup bot handlers"""
        self.app.add_handler(CommandHandler("start", self.start))
        self.app.add_handler(CallbackQueryHandler(self.handle_callback))
        self.app.add_handler(MessageHandler(filters.ALL & ~filters.COMMAND, self.handle_message))
    
    def run(self):
        """Run the bot"""
        self.app = Application.builder().token(BOT_TOKEN).build()
        self.setup_handlers()
        self.app.run_polling()

if __name__ == "__main__":
    bot = TelegramBot()
    bot.run()
