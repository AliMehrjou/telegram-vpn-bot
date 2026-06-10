import datetime
from sqlalchemy import select
from aiogram import Bot
from database.connection import async_session
from database.models import Config

async def check_expiring_configs(bot: Bot):
    """
    این تابع روزانه اجرا می‌شود تا کاربرانی که ۳ روز تا پایان اشتراکشان مانده را پیدا کند.
    """
    # زمان فعلی و زمانی که ۳ روز دیگر است
    now = datetime.datetime.now()
    three_days_later = now + datetime.timedelta(days=3)

    async with async_session() as session:
        # جستجو برای کانفیگ‌هایی که زمان انقضایشان کمتر از ۳ روز است، فعال هستند و هنوز هشدار دریافت نکرده‌اند
        stmt = select(Config).where(
            Config.user_id.isnot(None),
            Config.expire_date <= three_days_later,
            Config.expire_date > now, # هنوز منقضی نشده باشد
            Config.is_notified == False
        )
        
        result = await session.execute(stmt)
        expiring_configs = result.scalars().all()

        for config in expiring_configs:
            try:
                # محاسبه دقیق روزهای باقیمانده
                days_left = (config.expire_date - now).days
                
                # متن پیام هشدار
                warning_text = (
                    f"⚠️ **هشدار پایان اشتراک**\n\n"
                    f"کاربر گرامی، از اشتراک کانفیگ شما تنها **{days_left} روز** باقی مانده است.\n"
                    f"برای جلوگیری از قطعی، لطفاً نسبت به تمدید سرویس خود از طریق منوی ربات اقدام نمایید."
                )
                
                # ارسال پیام به کاربر
                await bot.send_message(chat_id=config.user_id, text=warning_text, parse_mode="Markdown")
                
                # آپدیت کردن وضعیت هشدار در دیتابیس تا فردا دوباره پیام ندهد
                config.is_notified = True
                
            except Exception as e:
                # کاربر ربات را بلاک کرده یا خطای دیگری رخ داده است
                print(f"Failed to send reminder to user {config.user_id}: {e}")

        # ذخیره تغییرات در دیتابیس (تغییر is_notified)
        if expiring_configs:
            await session.commit()