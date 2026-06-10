# vpn_bot_project/database/models.py
from sqlalchemy import Column, Integer, String, Boolean, DateTime, ForeignKey, BigInteger, Float
from sqlalchemy.orm import declarative_base, relationship
from datetime import datetime

Base = declarative_base()

class User(Base):
    __tablename__ = 'users'

    id = Column(Integer, primary_key=True, index=True)
    telegram_id = Column(BigInteger, unique=True, index=True, nullable=False)
    username = Column(String(255), nullable=True)
    balance = Column(Float, default=0.0)
    join_date = Column(DateTime, default=datetime.utcnow)
    last_free_config_date = Column(DateTime, nullable=True)
    is_referral_counted = Column(Boolean, default=False)
    # --- فیلدهای اضافه شده برای سیستم زیرمجموعه‌گیری ---
    invited_by = Column(BigInteger, nullable=True)      # آیدی تلگرام شخصی که این کاربر را دعوت کرده
    invite_count = Column(Integer, default=0)           # تعداد افرادی که این کاربر دعوت کرده
    purchase_invite_count = Column(Integer, default=0)  # تعداد خریدهای موفق زیرمجموعه‌ها

    # Relationships
    configs = relationship("Config", back_populates="user")

class Config(Base):
    __tablename__ = 'configs'

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(255), nullable=True) 
    
    # تغییر به nullable=True چون در ابتدا کانفیگی تولید نشده است
    config_string = Column(String(1000), nullable=True) 
    type = Column(String(50), default="free") 
    user_id = Column(Integer, ForeignKey('users.id'), nullable=True)
    is_used = Column(Boolean, default=False)
    
    # --- فیلد جدید برای مدیریت وضعیت سرویس ---
    # مقادیر استاندارد: 'active' (فعال)، 'pending' (در انتظار تایید)، 'disabled' (خاموش)
    status = Column(String(50), default="active", server_default="active")
    
    total_traffic_gb = Column(Float, default=0.0)   
    used_traffic_gb = Column(Float, default=0.0)    
    location = Column(String(100), default="VIP01") 
    last_connection = Column(DateTime, nullable=True) 
    
    created_at = Column(DateTime, default=datetime.utcnow)
    expire_date = Column(DateTime, nullable=True)
    is_notified = Column(Boolean, default=False, server_default="0")

    # Relationships
    user = relationship("User", back_populates="configs")

    
class Plan(Base):
    __tablename__ = 'plans'

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(255), nullable=False)
    price = Column(Float, nullable=False)
    duration_days = Column(Integer, nullable=False)
    volume_gb = Column(Float, nullable=False)