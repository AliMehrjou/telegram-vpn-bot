from typing import Callable, Dict, Any, Awaitable
from aiogram import BaseMiddleware
from aiogram.types import Message, CallbackQuery, TelegramObject
from config import SPONSOR_CHANNEL_ID, SPONSOR_CHANNEL_LINK
from bot.keyboards.inline import get_force_join_kb
import logging

class ForceJoinMiddleware(BaseMiddleware):
    async def __call__(
        self,
        handler: Callable[[TelegramObject, Dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: Dict[str, Any]
    ) -> Any:
        
        # در Aiogram 3 بهترین راه برای گرفتن یوزر از هر نوع ایونتی استفاده از دیتاست
        user = data.get("event_from_user")
        if not user:
            return await handler(event, data)

        # استثناها: اجازه عبور به دستور /start و دکمه تایید عضویت
        if isinstance(event, Message):
            if event.text and event.text.startswith('/start'):
                return await handler(event, data)
        elif isinstance(event, CallbackQuery):
            if event.data == "check_join":
                return await handler(event, data)

        bot = data.get('bot')
        
        if not bot or not SPONSOR_CHANNEL_ID or not SPONSOR_CHANNEL_LINK:
            return await handler(event, data)

        try:
            try:
                channel_id = int(SPONSOR_CHANNEL_ID)
            except ValueError:
                channel_id = SPONSOR_CHANNEL_ID 
                
            member = await bot.get_chat_member(chat_id=channel_id, user_id=user.id)
            if member.status in ['left', 'kicked', 'banned']:
                raise ValueError("Not a member")
            
        except Exception as e:
            logging.info(f"User {user.id} is not in sponsor channel: {e}")
            
            kb = get_force_join_kb(SPONSOR_CHANNEL_LINK)
            msg_text = "⛔️ برای استفاده از امکانات ربات باید ابتدا در کانال اسپانسر ما عضو شوید:"
            
            # هندل کردن واکنش بر اساس نوع ایونت
            if isinstance(event, Message):
                await event.answer(msg_text, reply_markup=kb)
            elif isinstance(event, CallbackQuery):
                await event.message.answer(msg_text, reply_markup=kb)
                await event.answer() # بستن حالت لودینگ دکمه شیشه‌ای
                
            return  # متوقف کردن زنجیره (Block propagation)

        # اگر عضو بود، درخواست رو به هندلر اصلی پاس بده
        return await handler(event, data)