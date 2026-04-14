import os
import secrets
from datetime import datetime, timezone
import firebase_admin
from firebase_admin import credentials, db
from dotenv import load_dotenv

load_dotenv()

# Setup paths
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
SERVICE_ACCOUNT_PATH = os.path.join(BASE_DIR, "serviceAccountKey.json")
DB_URL = os.getenv("FIREBASE_DATABASE_URL", "https://error-ai-8d6d8-default-rtdb.firebaseio.com/")

# Global App Initialization
if not firebase_admin._apps:
    cred = credentials.Certificate(SERVICE_ACCOUNT_PATH)
    firebase_admin.initialize_app(cred, {
        'databaseURL': DB_URL
    })

def init_db():
    """
    Seeds initial settings and admins if they don't exist in Firebase.
    """
    settings_ref = db.reference('/settings')
    if not settings_ref.get():
        settings_ref.set({
            "pricing_html": "Contact @DARKVENDOR07 for pricing",
            "contact_username": "@DARKVENDOR07",
            "default_daily_limit": 100,
            "total_requests": 0
        })
    
    # Root admin seeding
    initial_admin_id = 8139017482
    admin_ref = db.reference(f'/admins/{initial_admin_id}')
    if not admin_ref.get():
        admin_ref.set(True)

def get_db():
    """
    Stub for FastAPI dependency injection if needed.
    Firebase Admin handles connection pooling internally.
    """
    return db

# --- ADMIN FUNCTIONS ---

def is_user_admin(telegram_id: int) -> bool:
    return db.reference(f'/admins/{telegram_id}').get() is not None

def add_new_admin(telegram_id: int):
    db.reference(f'/admins/{telegram_id}').set(True)

def remove_existing_admin(telegram_id: int):
    if telegram_id == 8139017482: # Protect root admin
        return False
    db.reference(f'/admins/{telegram_id}').delete()
    return True

# --- SETTINGS FUNCTIONS ---

def get_settings():
    data = db.reference('/settings').get()
    if data:
        # Convert to a simple object compatibility layer
        class SettingsObj:
            def __init__(self, d):
                self.pricing_html = d.get('pricing_html')
                self.contact_username = d.get('contact_username')
                self.default_daily_limit = d.get('default_daily_limit')
        return SettingsObj(data)
    return None

def update_settings(pricing=None, contact=None, limit=None):
    ref = db.reference('/settings')
    updates = {}
    if pricing is not None: updates['pricing_html'] = pricing
    if contact is not None: updates['contact_username'] = contact
    if limit is not None: updates['default_daily_limit'] = limit
    if updates:
        ref.update(updates)

def get_global_usage_stat():
    return db.reference('/settings/total_requests').get() or 0

# --- API KEY FUNCTIONS ---

def generate_api_key(db_session, telegram_user_id: int) -> str:
    # db_session parameter kept for interface compatibility
    settings = db.reference('/settings').get()
    raw_key = secrets.token_urlsafe(32)
    new_key = f"errorai-{raw_key}"
    
    key_data = {
        "key": new_key,
        "telegram_user_id": telegram_user_id,
        "persona_context": None,
        "system_prompt": None,
        "usage_count": 0,
        "daily_usage": 0,
        "usage_limit": 5000,
        "daily_limit": settings.get('default_daily_limit', 100) if settings else 100,
        "last_reset": datetime.now(timezone.utc).isoformat(),
        "created_at": datetime.now(timezone.utc).isoformat(),
        "is_active": True
    }
    
    db.reference(f'/api_keys/{new_key}').set(key_data)
    return new_key

def verify_api_key(db_session, api_key: str):
    data = db.reference(f'/api_keys/{api_key}').get()
    if data and data.get('is_active'):
        # Compatibility object
        class KeyObj:
            def __init__(self, d):
                for k, v in d.items(): setattr(self, k, v)
                self.id = d.get('key') # Use key as stable ID
        return KeyObj(data)
    return None

def check_and_reset_quota(db_session, api_key_obj):
    """
    Checks if 24h passed and resets daily usage in Firebase.
    """
    last_reset = datetime.fromisoformat(api_key_obj.last_reset)
    now = datetime.now(timezone.utc)
    if (now - last_reset).total_seconds() > 86400:
        ref = db.reference(f'/api_keys/{api_key_obj.key}')
        ref.update({
            "daily_usage": 0,
            "last_reset": now.isoformat()
        })
        api_key_obj.daily_usage = 0 # Update local obj for immediate use

def increment_usage(db_session, key_id: str):
    """
    Thread-safe increment using Firebase Transactions.
    """
    key_ref = db.reference(f'/api_keys/{key_id}')
    settings_ref = db.reference('/settings')

    def update_key_transaction(current_val):
        if current_val is None: return current_val
        # Handle reset check inside transaction for absolute accuracy
        last_reset_str = current_val.get('last_reset')
        if last_reset_str:
            last_reset = datetime.fromisoformat(last_reset_str)
            if (datetime.now(timezone.utc) - last_reset).total_seconds() > 86400:
                current_val['daily_usage'] = 0
                current_val['last_reset'] = datetime.now(timezone.utc).isoformat()
        
        current_val['usage_count'] = (current_val.get('usage_count') or 0) + 1
        current_val['daily_usage'] = (current_val.get('daily_usage') or 0) + 1
        return current_val

    def update_global_stats(current_val):
        if current_val is None: return 1
        return current_val + 1

    key_ref.transaction(update_key_transaction)
    settings_ref.child('total_requests').transaction(update_global_stats)

# --- USER PREFERENCES ---

def update_user_instructions(db_session, telegram_user_id: int, profile: str = None, behavior: str = None) -> bool:
    all_keys = db.reference('/api_keys').get()
    if not all_keys: return False
    
    found = False
    for k_id, k_data in all_keys.items():
        if k_data.get('telegram_user_id') == telegram_user_id and k_data.get('is_active'):
            updates = {}
            if profile is not None: updates['persona_context'] = profile
            if behavior is not None: updates['system_prompt'] = behavior
            db.reference(f'/api_keys/{k_id}').update(updates)
            found = True
    return found

def update_persona(db_session, api_key: str, context: str) -> bool:
    ref = db.reference(f'/api_keys/{api_key}')
    if ref.get():
        ref.update({"persona_context": context})
        return True
    return False

def get_all_keys(db_session, telegram_user_id: int):
    all_keys = db.reference('/api_keys').get()
    if not all_keys: return []
    
    user_keys = []
    class KeyObj:
        def __init__(self, d):
            for k, v in d.items(): setattr(self, k, v)
    
    for k_id, k_data in all_keys.items():
        if k_data.get('telegram_user_id') == telegram_user_id and k_data.get('is_active'):
            user_keys.append(KeyObj(k_data))
    return user_keys

def get_all_users_with_stats():
    all_keys = db.reference('/api_keys').get()
    if not all_keys: return []
    
    user_stats = {}
    for k_id, k_data in all_keys.items():
        uid = k_data.get('telegram_user_id')
        if uid not in user_stats:
            user_stats[uid] = {"telegram_user_id": uid, "total_usage": 0, "key_count": 0}
        user_stats[uid]['total_usage'] += k_data.get('usage_count', 0)
        user_stats[uid]['key_count'] += 1
    
    class StatObj:
        def __init__(self, d):
            for k, v in d.items(): setattr(self, k, v)
            
    return [StatObj(v) for v in user_stats.values()]

def revoke_key(db_session, telegram_user_id: int, partial_key: str) -> bool:
    all_keys = db.reference('/api_keys').get()
    if not all_keys: return False
    
    for k_id, k_data in all_keys.items():
        if k_data.get('telegram_user_id') == telegram_user_id and k_data.get('is_active'):
            if partial_key in k_id:
                db.reference(f'/api_keys/{k_id}').update({"is_active": False})
                return True
    return False
