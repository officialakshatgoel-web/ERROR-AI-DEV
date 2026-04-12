import os
from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.context import FSMContext
from dotenv import load_dotenv

from database import (
    SessionLocal, 
    generate_api_key, 
    get_all_keys, 
    revoke_key, 
    is_user_admin, 
    add_new_admin, 
    remove_existing_admin, 
    get_all_users_with_stats, 
    update_user_instructions,
    update_custom_rules,
    update_settings,
    APIKey
)

load_dotenv()

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")

if not TELEGRAM_BOT_TOKEN:
    print("Warning: TELEGRAM_BOT_TOKEN is not set.")

bot = Bot(token=TELEGRAM_BOT_TOKEN)
dp = Dispatcher()

# --- FSM STATES ---
class InstructionStates(StatesGroup):
    waiting_for_profile = State()
    waiting_for_behavior = State()

@dp.message(Command("start"))
async def send_welcome(message: types.Message):
    user_id = message.from_user.id
    admin_info = ""
    if is_user_admin(user_id):
        admin_info = (
            "\n\n👑 *Admin Commands*:\n"
            "/add_admin <id> - Add new admin\n"
            "/del_admin <id> - Remove admin\n"
            "/list_users - View all users & usage\n"
            "/set_price <text> - Update Pricing on Web\n"
            "/set_contact <user> - Update Contact on Web\n"
            "/set_limit <num> - Default Daily Quota\n"
            "/user_limit <id> <num> - Custom Limit for User\n"
            "/admin_stats - Full system stats\n"
            "/backup - Get Database Backup"
        )

        
    await message.answer(
        f"Welcome to the Error AI Bot! 🤖\n\n"
        "Commands:\n"
        "/generate_key - Get a new API Key\n"
        "/list_keys - See your active keys & usage\n"
        "/instructions - ⚙️ Set Custom AI Instructions (About you & Behavior)\n"
        "/stats - Your usage stats\n"
        "/revoke <key> - Deactivate a key" + admin_info,
        parse_mode="Markdown"
    )

# --- CUSTOM INSTRUCTIONS FSM ---

@dp.message(Command("instructions"))
async def start_instructions(message: types.Message, state: FSMContext):
    await message.answer(
        "📝 *Custom Instructions (1/2)*\n\n"
        "What would you like the AI to know about you to provide better responses?\n"
        "(e.g. Your profession, interests, or location)",
        parse_mode="Markdown"
    )
    await state.set_state(InstructionStates.waiting_for_profile)

@dp.message(InstructionStates.waiting_for_profile)
async def process_profile(message: types.Message, state: FSMContext):
    await state.update_data(profile=message.text)
    await message.answer(
        "📝 *Custom Instructions (2/2)*\n\n"
        "How would you like the AI to respond?\n"
        "(e.g. 'Be formal', 'Use code examples', 'Be funny')",
        parse_mode="Markdown"
    )
    await state.set_state(InstructionStates.waiting_for_behavior)

@dp.message(InstructionStates.waiting_for_behavior)
async def process_behavior(message: types.Message, state: FSMContext):
    data = await state.get_data()
    profile = data.get('profile')
    behavior = message.text
    
    user_id = message.from_user.id
    db = SessionLocal()
    try:
        success = update_user_instructions(db, user_id, profile=profile, behavior=behavior)
        if success:
            await message.answer(
                "✅ *Custom Instructions Saved!*\n\n"
                "*About You:* " + profile + "\n"
                "*AI Behavior:* " + behavior,
                parse_mode="Markdown"
            )
        else:
            await message.answer("❌ Error: You need to generate an API Key first.")
    finally:
        db.close()
        await state.clear()

@dp.message(Command("add_admin"))
async def handle_add_admin(message: types.Message):
    if not is_user_admin(message.from_user.id): return
    try:
        new_admin_id = int(message.text.split()[1])
        add_new_admin(new_admin_id)
        await message.answer(f"✅ User {new_admin_id} is now an admin.")
    except Exception:
        await message.answer("Usage: /add_admin <telegram_id>")

@dp.message(Command("del_admin"))
async def handle_del_admin(message: types.Message):
    if not is_user_admin(message.from_user.id): return
    try:
        target_id = int(message.text.split()[1])
        success = remove_existing_admin(target_id)
        if success:
            await message.answer(f"✅ User {target_id} removed from admins.")
        else:
            await message.answer("❌ Cannot remove this admin (it might be the root admin).")
    except Exception:
        await message.answer("Usage: /del_admin <telegram_id>")

@dp.message(Command("list_users"))
async def handle_list_users(message: types.Message):
    if not is_user_admin(message.from_user.id): return
    users = get_all_users_with_stats()
    if not users:
        await message.answer("No users found.")
        return
        
    text = "👤 *Registered Users*:\n\n"
    for u in users:
        text += f"ID: `{u.telegram_user_id}`\nTotal Usage: {u.total_usage} reqs | Keys: {u.key_count}\n\n"
    
    # Split text if too long for one message
    if len(text) > 4000:
        for i in range(0, len(text), 4000):
            await message.answer(text[i:i+4000], parse_mode="Markdown")
    else:
        await message.answer(text, parse_mode="Markdown")

@dp.message(Command("set_price"))
async def handle_set_price(message: types.Message):
    if not is_user_admin(message.from_user.id): return
    text = message.text.replace("/set_price", "").strip()
    update_settings(pricing=text)
    await message.answer("✅ Web pricing updated!")

@dp.message(Command("set_contact"))
async def handle_set_contact(message: types.Message):
    if not is_user_admin(message.from_user.id): return
    text = message.text.replace("/set_contact", "").strip()
    update_settings(contact=text)
    await message.answer(f"✅ Web contact updated to {text}")

@dp.message(Command("set_limit"))
async def handle_set_limit(message: types.Message):
    if not is_user_admin(message.from_user.id): return
    try:
        limit = int(message.text.split()[1])
        update_settings(limit=limit)
        await message.answer(f"✅ Default daily limit set to {limit}")
    except Exception:
        await message.answer("Usage: /set_limit <number>")

@dp.message(Command("user_limit"))
async def handle_user_limit(message: types.Message):
    if not is_user_admin(message.from_user.id): return
    try:
        args = message.text.split()
        target_id = int(args[1])
        new_limit = int(args[2])
        
        db = SessionLocal()
        try:
            keys = db.query(APIKey).filter(APIKey.telegram_user_id == target_id).all()
            if not keys:
                await message.answer(f"❌ No keys found for user {target_id}")
                return
            for k in keys:
                k.daily_limit = new_limit
            db.commit()
            await message.answer(f"✅ Updated daily limit for User {target_id} to {new_limit}")
        finally:
            db.close()
    except Exception:
        await message.answer("Usage: /user_limit <telegram_id> <limit>")

from aiogram.types import FSInputFile

@dp.message(Command("backup"))
async def handle_backup(message: types.Message):
    if not is_user_admin(message.from_user.id): return
    from database import DB_PATH
    if os.path.exists(DB_PATH):
        await message.answer_document(
            FSInputFile(DB_PATH),
            caption="📂 *Error AI Database Backup*\n\nKeep this file safe!",
            parse_mode="Markdown"
        )
    else:
        await message.answer("❌ Database file not found.")

@dp.message(Command("admin_stats"))

async def handle_admin_stats(message: types.Message):
    if not is_user_admin(message.from_user.id): return
    db = SessionLocal()
    try:
        total_keys = db.query(APIKey).count()
        active_keys = db.query(APIKey).filter(APIKey.is_active == True).count()
        all_keys = db.query(APIKey).all()
        req_sum = sum(k.usage_count for k in all_keys)
        
        await message.answer(
            f"📈 *System Wide Stats*\n\n"
            f"Total Keys: {total_keys}\n"
            f"Active Keys: {active_keys}\n"
            f"Total Requests Processed: {req_sum}",
            parse_mode="Markdown"
        )
    finally:
        db.close()

@dp.message(Command("stats"))
async def handle_stats(message: types.Message):
    user_id = message.from_user.id
    db = SessionLocal()
    try:
        keys = get_all_keys(db, telegram_user_id=user_id)
        total_requests = sum(k.usage_count for k in keys) if keys else 0
        active_keys = len(keys)
        
        await message.answer(
            f"📊 *Your Statistics*:\n"
            f"Active Keys: {active_keys}\n"
            f"Total AI Requests: {total_requests}",
            parse_mode="Markdown"
        )
    finally:
        db.close()

@dp.message(Command("generate_key"))
async def handle_generate_key(message: types.Message):
    user_id = message.from_user.id
    db = SessionLocal()
    try:
        api_key = generate_api_key(db, telegram_user_id=user_id)
        await message.answer(
            f"Your AI API Key is:\n\n`{api_key}`\n\n"
            "Use it as a Bearer token in standard OpenAI clients!",
            parse_mode="Markdown"
        )
    except Exception as e:
        print(f"Error generating key: {e}")
        await message.answer("Error generating API key.")
    finally:
        db.close()

@dp.message(Command("list_keys"))
async def handle_list_keys(message: types.Message):
    user_id = message.from_user.id
    db = SessionLocal()
    try:
        keys = get_all_keys(db, telegram_user_id=user_id)
        if not keys:
            await message.answer("You have no active keys.")
            return
            
        text = "Your active keys:\n"
        for k in keys:
            text += f"`{k.key}` (Usage: {k.usage_count})\n"
        await message.answer(text, parse_mode="Markdown")
    finally:
        db.close()

@dp.message(Command("revoke"))
async def handle_revoke_key(message: types.Message):
    parts = message.text.split()
    if len(parts) < 2:
        await message.answer("Usage: /revoke <key_part>")
        return
        
    user_id = message.from_user.id
    db = SessionLocal()
    try:
        success = revoke_key(db, user_id, parts[1])
        if success:
            await message.answer("Key revoked successfully.")
        else:
            await message.answer("Key not found or not active.")
    finally:
        db.close()

async def start_bot():
    if TELEGRAM_BOT_TOKEN:
        print("Starting Telegram Bot...")
        await dp.start_polling(bot)
        print("Telegram Bot Token not provided, skipping bot startup.")


