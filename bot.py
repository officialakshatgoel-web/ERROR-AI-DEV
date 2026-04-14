import os
from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.context import FSMContext
from dotenv import load_dotenv

from database import (
    generate_api_key, 
    get_all_keys, 
    revoke_key, 
    is_user_admin, 
    add_new_admin, 
    remove_existing_admin, 
    get_all_users_with_stats, 
    update_user_instructions,
    update_settings,
    update_user_limit,
    get_admin_stats
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
    admin_commands = (
        "\n\n👑 *Admin Commands*:\n"
        "/addadmin <id> - Add new admin\n"
        "/deladmin <id> - Remove admin\n"
        "/listusers - View all users & usage\n"
        "/setprice <text> - Update Pricing on Web\n"
        "/setcontact <user> - Update Contact on Web\n"
        "/setlimit <num> - Default Daily Quota\n"
        "/userlimit <id> <num> - Custom Limit for User\n"
        "/adminstats - Full system stats\n"
        "/backup - Get Database Backup"
    )

    await message.answer(
        f"🚀 *Error AI — Ultimate Setup Active*\n\n"
        f"Your API now runs on a powerful model combo:\n"
        f"🔹 *Dolphin 8B* — Uncensored & Blazing Fast\n"
        f"🔹 *Qwen 32B* — High-Accuracy Coding Engine\n\n"
        "The system automatically routes your requests to the best model for the task. ⚡️\n\n"
        "*Available Commands:*\n"
        "/generatekey - Get a new API Key\n"
        "/listkeys - See your active keys & usage\n"
        "/instructions - ⚙️ Set Custom AI Instructions\n"
        "/stats - Your usage stats\n"
        "/revoke <key> - Deactivate a key" + admin_commands,
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
    success = update_user_instructions(None, user_id, profile=profile, behavior=behavior)
    if success:
        await message.answer(
            "✅ *Custom Instructions Saved!*\n\n"
            "*About You:* " + profile + "\n"
            "*AI Behavior:* " + behavior,
            parse_mode="Markdown"
        )
    else:
        await message.answer("❌ Error: You need to generate an API Key first.")
        
    await state.clear()

@dp.message(Command("addadmin"))
async def handle_add_admin(message: types.Message):
    if not is_user_admin(message.from_user.id):
        await message.answer("❌ You are not authorized to use this command.")
        return
    try:
        new_admin_id = int(message.text.split()[1])
        add_new_admin(new_admin_id)
        await message.answer(f"✅ User {new_admin_id} is now an admin.")
    except Exception:
        await message.answer("Usage: /addadmin <telegram_id>")

@dp.message(Command("deladmin"))
async def handle_del_admin(message: types.Message):
    if not is_user_admin(message.from_user.id):
        await message.answer("❌ You are not authorized to use this command.")
        return
    try:
        target_id = int(message.text.split()[1])
        success = remove_existing_admin(target_id)
        if success:
            await message.answer(f"✅ User {target_id} removed from admins.")
        else:
            await message.answer("❌ Cannot remove this admin (it might be the root admin).")
    except Exception:
        await message.answer("Usage: /deladmin <telegram_id>")

@dp.message(Command("listusers"))
async def handle_list_users(message: types.Message):
    if not is_user_admin(message.from_user.id):
        await message.answer("❌ You are not authorized to use this command.")
        return
    users = get_all_users_with_stats()
    if not users:
        await message.answer("No users found.")
        return
        
    text = "👤 *Registered Users*:\n\n"
    for u in users:
        text += f"ID: `{u.telegram_user_id}`\nTotal Usage: {u.total_usage} reqs | Keys: {u.key_count}\n\n"
    
    if len(text) > 4000:
        for i in range(0, len(text), 4000):
            await message.answer(text[i:i+4000], parse_mode="Markdown")
    else:
        await message.answer(text, parse_mode="Markdown")

@dp.message(Command("setprice"))
async def handle_set_price(message: types.Message):
    if not is_user_admin(message.from_user.id):
        await message.answer("❌ You are not authorized to use this command.")
        return
    text = message.text.replace("/setprice", "").strip()
    update_settings(pricing=text)
    await message.answer("✅ Web pricing updated!")

@dp.message(Command("setcontact"))
async def handle_set_contact(message: types.Message):
    if not is_user_admin(message.from_user.id):
        await message.answer("❌ You are not authorized to use this command.")
        return
    text = message.text.replace("/setcontact", "").strip()
    update_settings(contact=text)
    await message.answer(f"✅ Web contact updated to {text}")

@dp.message(Command("setlimit"))
async def handle_set_limit(message: types.Message):
    if not is_user_admin(message.from_user.id):
        await message.answer("❌ You are not authorized to use this command.")
        return
    try:
        limit = int(message.text.split()[1])
        update_settings(limit=limit)
        await message.answer(f"✅ Default daily limit set to {limit}")
    except Exception:
        await message.answer("Usage: /setlimit <number>")

@dp.message(Command("userlimit"))
async def handle_user_limit(message: types.Message):
    if not is_user_admin(message.from_user.id):
        await message.answer("❌ You are not authorized to use this command.")
        return
    try:
        args = message.text.split()
        target_id = int(args[1])
        new_limit = int(args[2])
        
        updated = update_user_limit(target_id, new_limit)
        if updated:
            await message.answer(f"✅ Updated daily limit for User {target_id} to {new_limit}")
        else:
            await message.answer(f"❌ No active keys found for user {target_id}")
    except Exception:
        await message.answer("Usage: /userlimit <telegram_id> <limit>")

@dp.message(Command("backup"))
async def handle_backup(message: types.Message):
    if not is_user_admin(message.from_user.id):
        await message.answer("❌ You are not authorized to use this command.")
        return
    await message.answer("ℹ️ Cloud Database is securely hosted on Firebase. Native local backups are no longer needed via bot.")

@dp.message(Command("adminstats"))
async def handle_admin_stats(message: types.Message):
    if not is_user_admin(message.from_user.id):
        await message.answer("❌ You are not authorized to use this command.")
        return
    stats = get_admin_stats()
    
    await message.answer(
        f"📈 *System Wide Stats*\n\n"
        f"Total Keys: {stats['total_keys']}\n"
        f"Active Keys: {stats['active_keys']}\n"
        f"Total Requests Processed: {stats['total_requests']}",
        parse_mode="Markdown"
    )

@dp.message(Command("help"))
async def handle_help(message: types.Message):
    help_text = (
        "🛠️ *Error AI — Help Menu*\n\n"
        "*User Commands:*\n"
        "• `/start` — Initial message & quick links\n"
        "• `/generatekey` — Create a new API Key\n"
        "• `/listkeys` — View all your keys and usage\n"
        "• `/stats` — Your overall usage analytics\n"
        "• `/instructions` — Set global AI behavioral context\n"
        "• `/revoke <key>` — Deactivate a compromised key\n\n"
        "*Admin Commands:*\n"
        "• `/adminstats` — Global system health\n"
        "• `/listusers` — User database overview\n"
        "• `/setlimit <n>` — Change default daily quota\n"
        "• `/setprice <text>` — Update web pricing info\n"
        "• `/backup` — Export current database\n\n"
        "🔗 *Documentation:* [errorapi.dev/documentation](https://errorapi.dev/documentation)"
    )
    await message.answer(help_text, parse_mode="Markdown", disable_web_page_preview=True)

def get_progress_bar(current, total, length=10):
    if total <= 0: return "[░░░░░░░░░░]"
    filled = int(length * current / total)
    return "[" + "█" * min(filled, length) + "░" * max(0, length - filled) + "]"

@dp.message(Command("stats"))
async def handle_stats(message: types.Message):
    user_id = message.from_user.id
    keys = get_all_keys(None, telegram_user_id=user_id)
    total_requests = sum(k.usage_count for k in keys) if keys else 0
    active_keys_count = len(keys)
    
    await message.answer(
        f"📊 *Error AI — Your Stats*\n\n"
        f"• *Keys:* `{active_keys_count}` active\n"
        f"• *Total Lifetime Usage:* `{total_requests}` requests\n\n"
        "_Use /listkeys for a detailed breakdown._",
        parse_mode="Markdown"
    )

@dp.message(Command("generatekey"))
async def handle_generate_key(message: types.Message):
    user_id = message.from_user.id
    try:
        api_key = generate_api_key(None, telegram_user_id=user_id)
        await message.answer(
            f"✅ *New Key Generated*\n\n"
            f"`{api_key}`\n\n"
            "⚠️ *Security:* Never share this key. Use it as a Bearer token for OpenAI-compatible clients.",
            parse_mode="Markdown"
        )
    except Exception as e:
        print(f"Error generating key: {e}")
        await message.answer("❌ *Error:* Failed to generate API key.")

@dp.message(Command("listkeys"))
async def handle_list_keys(message: types.Message):
    user_id = message.from_user.id
    keys = get_all_keys(None, telegram_user_id=user_id)
    if not keys:
        await message.answer("❌ You have no active keys. Use /generatekey.")
        return
        
    text = "🔑 *Your API Keys*\n\n"
    for k in keys:
        prog = get_progress_bar(k.daily_usage, k.daily_limit)
        text += f"`{k.key[:15]}...`\n"
        text += f"Daily: {prog} {k.daily_usage}/{k.daily_limit}\n"
        text += f"Total: `{k.usage_count}` reqs\n\n"
        
    await message.answer(text, parse_mode="Markdown")

@dp.message(Command("revoke"))
async def handle_revoke_key(message: types.Message):
    parts = message.text.split()
    if len(parts) < 2:
        await message.answer("Usage: `/revoke <key_part>`", parse_mode="Markdown")
        return
        
    user_id = message.from_user.id
    success = revoke_key(None, user_id, parts[1])
    if success:
        await message.answer("✅ *Key Revoked:* Access for this key has been disabled.")
    else:
        await message.answer("❌ *Error:* Key not found or belongs to another user.")

async def start_bot():
    if TELEGRAM_BOT_TOKEN:
        print("Starting Telegram Bot...")
        await dp.start_polling(bot)
    else:
        print("Telegram Bot Token not provided, skipping bot startup.")


