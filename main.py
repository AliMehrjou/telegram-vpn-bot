import asyncio
import logging
from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.client.session.aiohttp import AiohttpSession

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from tasks import check_expiring_configs

# پراکسی رو از کانفیگ می‌خونیم تا تو سورس اصلی لو نره
from config import BOT_TOKEN, PROXY_URL 
from database.connection import engine
from database.models import Base
from bot.middlewares.force_join import ForceJoinMiddleware
from bot.handlers.admin_handlers import router as admin_router
from bot.handlers.user_handlers import router as user_router

async def init_models():
    """Initializes Database Models asynchronously."""
    async with engine.begin() as conn:
        # Executes CREATE TABLE for all declarative models (Base.metadata)
        await conn.run_sync(Base.metadata.create_all)
    logging.info("Database and tables initialized successfully.")

async def main():
    """Main application runner."""
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    )
    
    if not BOT_TOKEN:
        logging.error("BOT_TOKEN is not correctly populated. Check your .env file.")
        return

    # 💡 ایجاد سشن فقط در صورتی که پراکسی تنظیم شده باشه
    session = None
    if PROXY_URL:
        session = AiohttpSession(proxy=PROXY_URL)
        logging.info("Running with proxy configured.")

    # Initialize Bot instance with HTML parse mode
    bot = Bot(
        token=BOT_TOKEN, 
        default=DefaultBotProperties(parse_mode=ParseMode.HTML), 
        session=session
    )
    dp = Dispatcher()

    # ✅ تغییر اصلی: ساخت یک نمونه از میدلور و اعمالش روی پیام‌ها و کال‌بک‌ها
    force_join_mw = ForceJoinMiddleware()
    dp.message.middleware(force_join_mw)
    dp.callback_query.middleware(force_join_mw)

    # Include Routers (Admin first to ensure high-priority commands match first)
    dp.include_router(admin_router)
    dp.include_router(user_router)

    # Time scheduler
    scheduler = AsyncIOScheduler(timezone='Asia/Tehran')
    scheduler.add_job(
        check_expiring_configs, 
        trigger='cron', 
        hour=10, 
        minute=0, 
        args=[bot]
    )
    scheduler.start()
    logging.info("⏳ Scheduler started successfully!")

    # Database initialization
    await init_models()

    # ⚠️ پاک کردن آپدیت‌های اسپم در زمان خاموشی و جلوگیری از تداخل
    logging.info("Clearing pending updates and webhooks to avoid conflicts...")
    await bot.delete_webhook(drop_pending_updates=True)

    logging.info("Starting up Bot... Polling begins!")
    try:
        await dp.start_polling(bot)
    finally:
        await bot.session.close()
        logging.info("Bot session closed successfully.")

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        logging.info("Bot execution has been stopped manually.")