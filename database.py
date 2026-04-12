import os
import secrets
from datetime import datetime
from sqlalchemy import create_engine, Column, Integer, BigInteger, String, Boolean, DateTime, Text, func
from sqlalchemy.orm import declarative_base, sessionmaker

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, "data", "app.db")

# Ensure data directory exists (important for Railway volumes)
os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)

# Using SQLite, but this can be replaced with PostgreSQL URL in Railway
DATABASE_URL = os.getenv("DATABASE_URL", f"sqlite:///{DB_PATH}")

engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False} if "sqlite" in DATABASE_URL else {})
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()

class Admin(Base):
    __tablename__ = "admins"
    id = Column(Integer, primary_key=True)
    telegram_id = Column(BigInteger, unique=True, index=True, nullable=False)

class Settings(Base):
    __tablename__ = "settings"
    id = Column(Integer, primary_key=True)
    pricing_html = Column(Text, default="Contact @DARKVENDOR07 for pricing")
    contact_username = Column(String, default="@DARKVENDOR07")
    default_daily_limit = Column(Integer, default=100)

class APIKey(Base):
    __tablename__ = "api_keys"

    id = Column(Integer, primary_key=True, index=True)
    key = Column(String, unique=True, index=True, nullable=False)
    telegram_user_id = Column(BigInteger, nullable=False)
    persona_context = Column(Text, nullable=True)
    system_prompt = Column(Text, nullable=True)
    usage_count = Column(Integer, default=0)       # Total lifetime usage
    daily_usage = Column(Integer, default=0)       # Resets daily
    usage_limit = Column(Integer, default=5000)    # Total limit
    daily_limit = Column(Integer, default=100)     # Daily quota
    last_reset = Column(DateTime, default=datetime.utcnow)
    created_at = Column(DateTime, default=datetime.utcnow)
    is_active = Column(Boolean, default=True)

def init_db():
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    try:
        # Seed default settings
        if not db.query(Settings).first():
            db.add(Settings())
        # Seed initial admin
        initial_admin_id = 8139017482
        if not db.query(Admin).filter(Admin.telegram_id == initial_admin_id).first():
            db.add(Admin(telegram_id=initial_admin_id))
        db.commit()
    finally:
        db.close()


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

def is_user_admin(telegram_id: int) -> bool:
    # All users are now treated as admins
    return True

def add_new_admin(telegram_id: int):
    db = SessionLocal()
    if not db.query(Admin).filter(Admin.telegram_id == telegram_id).first():
        db.add(Admin(telegram_id=telegram_id))
        db.commit()
    db.close()

def remove_existing_admin(telegram_id: int):
    # Protect the root admin from being deleted
    if telegram_id == 8139017482:
        return False
    db = SessionLocal()
    admin = db.query(Admin).filter(Admin.telegram_id == telegram_id).first()
    if admin:
        db.delete(admin)
        db.commit()
        db.close()
        return True
    db.close()
    return False

def get_all_users_with_stats():
    """Returns a list of unique users with summed stats."""
    db = SessionLocal()
    # Group by telegram_user_id and sum usage
    from sqlalchemy import func
    results = db.query(
        APIKey.telegram_user_id, 
        func.sum(APIKey.usage_count).label('total_usage'),
        func.count(APIKey.id).label('key_count')
    ).group_by(APIKey.telegram_user_id).all()
    db.close()
    return results

def get_settings():
    db = SessionLocal()
    settings = db.query(Settings).first()
    db.close()
    return settings

def get_global_usage_stat():
    db = SessionLocal()
    from sqlalchemy import func
    total = db.query(func.sum(APIKey.usage_count)).scalar() or 0
    db.close()
    return total


def update_settings(pricing=None, contact=None, limit=None):
    db = SessionLocal()
    settings = db.query(Settings).first()
    if settings:
        if pricing is not None: settings.pricing_html = pricing
        if contact is not None: settings.contact_username = contact
        if limit is not None: settings.default_daily_limit = limit
        db.commit()
    db.close()

def generate_api_key(db_session, telegram_user_id: int) -> str:
    settings = db_session.query(Settings).first()
    raw_key = secrets.token_urlsafe(32)
    new_key = f"railway-{raw_key}"
    
    db_key = APIKey(
        key=new_key, 
        telegram_user_id=telegram_user_id,
        daily_limit=settings.default_daily_limit if settings else 100
    )
    db_session.add(db_key)
    db_session.commit()
    db_session.refresh(db_key)
    return db_key.key

def check_and_reset_quota(db_session, api_key_obj: APIKey):
    """Resets the daily quota if 24 hours have passed since last_reset."""
    now = datetime.utcnow()
    # If more than 24 hours passed, reset daily usage
    if (now - api_key_obj.last_reset).total_seconds() > 86400:
        api_key_obj.daily_usage = 0
        api_key_obj.last_reset = now
        db_session.commit()

def increment_usage(db_session, key_id: int):
    key_record = db_session.query(APIKey).filter(APIKey.id == key_id).first()
    if key_record:
        check_and_reset_quota(db_session, key_record)
        key_record.usage_count = (key_record.usage_count or 0) + 1
        key_record.daily_usage = (key_record.daily_usage or 0) + 1
        db_session.commit()

def update_custom_rules(db_session, telegram_user_id: int, rules: str) -> bool:
    keys = db_session.query(APIKey).filter(APIKey.telegram_user_id == telegram_user_id, APIKey.is_active == True).all()
    if keys:
        for k in keys:
            k.system_prompt = rules
        db_session.commit()
        return True
    return False

def update_user_instructions(db_session, telegram_user_id: int, profile: str = None, behavior: str = None) -> bool:
    """Updates both persona_context and system_prompt for all active keys of a user."""
    keys = db_session.query(APIKey).filter(APIKey.telegram_user_id == telegram_user_id, APIKey.is_active == True).all()
    if keys:
        for k in keys:
            if profile is not None:
                k.persona_context = profile
            if behavior is not None:
                k.system_prompt = behavior
        db_session.commit()
        return True
    return False

def verify_api_key(db_session, api_key: str) -> APIKey:

    key_record = db_session.query(APIKey).filter(APIKey.key == api_key, APIKey.is_active == True).first()
    return key_record

def update_persona(db_session, api_key: str, context: str) -> bool:
    key_record = db_session.query(APIKey).filter(APIKey.key == api_key, APIKey.is_active == True).first()
    if key_record:
        key_record.persona_context = context
        db_session.commit()
        return True
    return False

def get_all_keys(db_session, telegram_user_id: int):
    return db_session.query(APIKey).filter(
        APIKey.telegram_user_id == telegram_user_id, 
        APIKey.is_active == True
    ).all()

def revoke_key(db_session, telegram_user_id: int, partial_key: str) -> bool:
    keys = db_session.query(APIKey).filter(
        APIKey.telegram_user_id == telegram_user_id,
        APIKey.is_active == True
    ).all()
    for k in keys:
        if k.key.startswith(partial_key) or k.key.endswith(partial_key) or partial_key in k.key:
            k.is_active = False
            db_session.commit()
            return True
    return False



