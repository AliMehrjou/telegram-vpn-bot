import asyncio
import json
import os
from datetime import datetime, timedelta

from aiogram import Router, F
from aiogram.filters import CommandStart, CommandObject
from aiogram.types import (
    Message,
    CallbackQuery,
    InlineKeyboardMarkup,
    InlineKeyboardButton,
)
from aiogram.utils.deep_linking import create_start_link
from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.context import FSMContext
from sqlalchemy import text
from sqlalchemy import update
from sqlalchemy import select
from database.connection import async_session
from database.models import User, Config, Plan
from sqlalchemy import select, func
from bot.keyboards.reply import get_main_menu_kb
from bot.keyboards.inline import get_plans_kb, get_payment_receipt_kb, get_force_join_kb
from config import ADMIN_IDS, SPONSOR_CHANNEL_ID, SPONSOR_CHANNEL_LINK, SUPPORT_ADMIN_USERNAME, CARD_NUMBER,ADMIN_NAME
import math
import time

router = Router()


class PaymentState(StatesGroup):
    waiting_for_service_name = State()
    waiting_for_receipt = State()


# ════════════════════════════════════════════════════════
# هلپر: شمارش رفرال (فراخوانی پس از تایید عضویت در کانال)
# ════════════════════════════════════════════════════════

async def _process_referral(user_id: int, bot) -> None:
    """
    رفرال را دقیقاً یک‌بار ثبت می‌کند.
    فلگ is_referral_counted مانع از دوباره‌شماری می‌شود،
    بنابراین می‌توان این تابع را در هر نقطه‌ای از کد فراخواند بدون نگرانی.
    """
    async with async_session() as session:
        user = await session.scalar(
            select(User).where(User.telegram_id == user_id).with_for_update()
        )
        if not user or not user.invited_by or user.is_referral_counted:
            return  # یا رفرال ندارد یا قبلاً شمرده شده

        referrer = await session.scalar(
            select(User).where(User.telegram_id == user.invited_by).with_for_update()
        )
        if not referrer:
            return

        referrer.invite_count += 1
        user.is_referral_counted = True

        if referrer.invite_count % 5 == 0:
            reward_conf = await session.scalar(
                select(Config).where(
                    Config.type == "reward_invite",
                    Config.user_id.is_(None),
                    Config.is_used == False
                ).with_for_update().limit(1)
            )
            if reward_conf:
                reward_conf.user_id = referrer.id
                reward_conf.is_used = True
                reward_conf.status = "active"
                reward_conf.name = f"🎁 جایزه {referrer.invite_count} دعوت"
                reward_conf.expire_date = datetime.utcnow() + timedelta(days=1)
                session.add(reward_conf)
                try:
                    await bot.send_message(
                        chat_id=referrer.telegram_id,
                        text=(
                            f"🎉 **تبریک!**\n\n"
                            f"تعداد زیرمجموعه‌های شما به **{referrer.invite_count}** نفر رسید!\n"
                            f"این کانفیگ **۱ روزه نامحدود** به عنوان هدیه تقدیم شما:\n\n"
                            f"`{reward_conf.config_string}`\n\n"
                            f"💡 _این سرویس به بخش «سرویس‌های من» اضافه شد._"
                        ),
                        parse_mode="Markdown"
                    )
                except Exception:
                    pass
            else:
                for admin in ADMIN_IDS:
                    try:
                        await bot.send_message(
                            chat_id=admin,
                            text="🚨 **اتمام موجودی جوایز دعوت!**\nموجودی انبار `reward_invite` خالی است.",
                            parse_mode="Markdown"
                        )
                    except Exception:
                        pass

        session.add(referrer)
        session.add(user)
        await session.commit()


# ════════════════════════════════════════════════════════
# /start
# ════════════════════════════════════════════════════════

@router.message(CommandStart())
async def cmd_start(message: Message, command: CommandObject, bot):
    user_id = message.from_user.id

    async with async_session() as session:
        user = await session.scalar(select(User).where(User.telegram_id == user_id))

        if not user:
            new_user = User(
                telegram_id=user_id,
                username=message.from_user.username,
            )
            # اینجا آیدی معرف فقط تو دیتابیس ثبت میشه، اما امتیازی لحاظ نمیشه
            args = command.args
            if args and args.isdigit() and int(args) != user_id:
                new_user.invited_by = int(args)
            
            session.add(new_user)
            await session.commit()
            user = new_user 

    # 🔴 اصلاح اصلی: پیش‌فرض باید False باشه تا کسی نتونه جوین اجباری رو دور بزنه
    is_member = False  
    try:
        channel_id = int(SPONSOR_CHANNEL_ID) if str(SPONSOR_CHANNEL_ID).lstrip('-').isdigit() else SPONSOR_CHANNEL_ID
        member = await bot.get_chat_member(chat_id=channel_id, user_id=user_id)
        # فقط در صورتی که واقعا عضو باشه، True میشه
        is_member = member.status not in ["left", "kicked", "banned"]
    except Exception as e:
        # اگه ربات ادمین کانال نباشه ارور میده، ولی دیگه الکی کاربر رو تایید نمی‌کنه
        pass 

    if not is_member:
        kb = get_force_join_kb(SPONSOR_CHANNEL_LINK)
        return await message.answer(
            "👋 سلام! برای استفاده از ربات و ثبت شدن به عنوان زیرمجموعه، ابتدا باید در کانال اسپانسر ما عضو شوید:",
            reply_markup=kb
        )

    # ✅ فقط در صورتی که کاربر عضو کانال باشه کد به اینجا می‌رسه
    # این تابع خودش چک می‌کنه که رفرال قبلاً ثبت نشده باشه (user.is_referral_counted)
    await _process_referral(user_id, bot)

    await message.answer(
        "👋 سلام! به ربات توزیع کانفیگ خوش آمدید. لطفا از منوی زیر یکی از گزینه‌ها را انتخاب کنید:",
        reply_markup=get_main_menu_kb(),
    )
# ════════════════════════════════════════════════════════
# بررسی عضویت کانال
# ════════════════════════════════════════════════════════

@router.callback_query(F.data == "check_join")
async def check_join_callback(call: CallbackQuery, bot):
    user_id = call.from_user.id
    try:
        channel_id = int(SPONSOR_CHANNEL_ID) if str(SPONSOR_CHANNEL_ID).lstrip('-').isdigit() else SPONSOR_CHANNEL_ID
        member = await bot.get_chat_member(chat_id=channel_id, user_id=user_id)

        if member.status in ["left", "kicked", "banned"]:
            return await call.answer(
                "❌ شما هنوز عضو کانال نشده‌اید! لطفا ابتدا وارد کانال شوید.",
                show_alert=True,
            )
            
        # ✅ کاربر عضو شده! رفرال را ثبت کن
        await _process_referral(user_id, bot)

        # نمایش پیام موفقیت آمیز
        await call.message.delete()
        await call.message.answer(
            "✅ عضویت شما تایید شد! خیلی خوش آمدید. هم اکنون می‌توانید با منو کار کنید:",
            reply_markup=get_main_menu_kb(),
        )
        
    except Exception as e:
        await call.answer("خطا در بررسی عضویت. لطفا دقایقی دیگر سامانه را چک کنید.", show_alert=True)

# ════════════════════════════════════════════════════════
# زیرمجموعه‌گیری
# ════════════════════════════════════════════════════════

@router.message(F.text == "🤝 زیرمجموعه‌گیری (دریافت جایزه)")
async def referral_menu(message: Message, bot):
    user_id = message.from_user.id
    invite_link = await create_start_link(bot, str(user_id), encode=False)

    async with async_session() as session:
        user = await session.scalar(select(User).where(User.telegram_id == user_id))
        if not user:
            return await message.answer("خطا در یافتن اطلاعات شما.")

        invite_count = user.invite_count
        purchase_count = user.purchase_invite_count

    text = (
        f"🎁 **سیستم جایزه و زیرمجموعه‌گیری**\n\n"
        f"لینک اختصاصی شما:\n`{invite_link}`\n\n"
        f"📊 **آمار فعلی شما:**\n"
        f"👥 تعداد دعوت‌شده‌ها: **{invite_count}** نفر\n"
        f"🛒 خریدهای موفق زیرمجموعه: **{purchase_count}** نفر\n\n"
        f"💡 **شرایط دریافت جایزه:**\n"
        f"🔹 با دعوت هر ۵ نفر به ربات، **یک کانفیگ نامحدود ۱ روزه** هدیه بگیرید.\n"
        f"🔹 با هر ۱۰ خرید موفق توسط زیرمجموعه‌هایتان، **یک کانفیگ نامحدود ۱ ماهه تک‌کاربره** دریافت کنید!"
    )
    await message.answer(text, parse_mode="Markdown")


# ════════════════════════════════════════════════════════
# کانفیگ رایگان
# ════════════════════════════════════════════════════════

# تابع کمکی برای خواندن محدودیت از تنظیمات
def get_free_limit_days():
    file_path = "bot_settings.json"
    try:
        # اگر فایل وجود نداشت، یکی با مقدار پیش‌فرض ۱ روز می‌سازیم
        if not os.path.exists(file_path):
            with open(file_path, "w", encoding="utf-8") as f:
                json.dump({"free_limit_days": 1.0}, f)
            return 1.0
        
        # خواندن امن فایل
        with open(file_path, "r", encoding="utf-8") as f:
            data = json.load(f)
            val = float(data.get("free_limit_days", 1.0))
            return val if val > 0 else 1.0
    except Exception:
        # در صورت هرگونه خرابی فایل، پیش‌فرض ۱ روز را برگردان
        return 1.0

user_locks = {}

def get_user_lock(user_id: int) -> asyncio.Lock:
    if user_id not in user_locks:
        user_locks[user_id] = asyncio.Lock()
    return user_locks[user_id]


@router.message(F.text == "🎁 دریافت کانفیگ رایگان")
async def get_free_config(message: Message):
    user_id = message.from_user.id
    
    # ۱. دریافت قفل اختصاصی این کاربر
    lock = get_user_lock(user_id)
    
    # اگر کاربر در حال اسپم کردن باشد و پردازش درخواست قبلی‌اش تمام نشده باشد، 
    # این شرط جلوی اجرای کدهای اضافی را می‌گیرد و درخواست را لغو می‌کند.
    if lock.locked():
        # می‌توانید به جای نادیده گرفتن، یک پیام هشدار هم بفرستید
        # return await message.answer("⚠️ در حال پردازش درخواست شما...")
        return 

    # ۲. ورود به منطقه امن (جلوگیری قطعی از Race Condition)
    async with lock:
        now = datetime.utcnow()
        limit_days = get_free_limit_days()

        async with async_session() as session:
            # ۳. ایجاد یک بلوک تراکنش یکپارچه برای اعمال درست .with_for_update()
            async with session.begin():
                user = await session.scalar(
                    select(User).where(User.telegram_id == user_id).with_for_update()
                )
                
                if not user:
                    return await message.answer("❌ خطا در یافتن اطلاعات شما در دیتابیس.")

                # ۴. بررسی بسیار دقیق محدودیت زمانی
                if user.last_free_config_date:
                    time_passed_seconds = (now - user.last_free_config_date).total_seconds()
                    limit_seconds = limit_days * 86400 # هر روز ۸۶۴۰۰ ثانیه است
                    
                    if time_passed_seconds < limit_seconds:
                        remaining = limit_seconds - time_passed_seconds
                        hours, remainder = divmod(remaining, 3600)
                        minutes, _ = divmod(remainder, 60)
                        
                        return await message.answer(
                            f"⏳ **محدودیت دریافت کانفیگ!**\n\n"
                            f"شما قبلاً سهمیه کانفیگ رایگان خود را دریافت کرده‌اید.\n"
                            f"لطفاً `{int(hours)}` ساعت و `{int(minutes)}` دقیقه دیگر مجدداً تلاش کنید.",
                            parse_mode="Markdown"
                        )

                # ۵. گرفتن کانفیگ از انبار با قفل کردن ردیف
                config_obj = await session.scalar(
                    select(Config)
                    .where(Config.type == "free", Config.user_id.is_(None), Config.is_used == False)
                    .with_for_update()
                    .limit(1)
                )

                if not config_obj:
                    return await message.answer("😔 متاسفانه در حال حاضر موجودی کانفیگ رایگان به اتمام رسیده است.")

                # ۶. تخصیص کانفیگ و ثبت زمان دقیق
                config_string = config_obj.config_string
                await session.delete(config_obj) 
                
                user.last_free_config_date = now
                session.add(user) # اجبار به آپدیت وضعیت کاربر
                
                # توجه: نیازی به await session.commit() نیست چون session.begin() با اتمام بلوک، آن را خودکار کامیت می‌کند
            
    # ۷. ارسال پیام به کاربر (خارج از قفل و سشن دیتابیس برای جلوگیری از باز ماندن کانکشن)
    await message.answer(
        f"🎁 **کانفیگ سرور رایگان شما:**\n\n`{config_string}`\n\n"
        f"💡 _برای کپی کردن روی متن کانفیگ کلیک کنید._",
        parse_mode="Markdown"
    )

# ════════════════════════════════════════════════════════
# خرید کانفیگ
# ════════════════════════════════════════════════════════

@router.message(F.text == "💰 خرید کانفیگ")
async def buy_config(message: Message):
    async with async_session() as session:
        result = await session.execute(select(Plan))
        plans = result.scalars().all()

        if not plans:
            return await message.answer("لیست پلن‌های خرید در حال حاضر خالی است.")

        await message.answer(
            "🔽 لطفا پلن مورد نظر خود را جهت خرید انتخاب کنید:",
            reply_markup=get_plans_kb(plans),
        )


# ════════════════════════════════════════════════════════
# سرویس‌های من
# ════════════════════════════════════════════════════════

def _build_config_status(config) -> tuple[str, str]:
    """وضعیت و ایموجی مناسب یک کانفیگ را برمی‌گرداند."""
    if config.status == "pending":
        return "⏳", "در انتظار تایید"
    if config.status == "disabled" or config.is_used:
        return "🔴", "خاموش"
    return "🟢", "فعال"


@router.message(F.text == "سرویس های من")
async def my_services(message: Message):
    user_telegram_id = message.from_user.id

    async with async_session() as session:
        user = await session.scalar(
            select(User).where(User.telegram_id == user_telegram_id)
        )
        if not user:
            return await message.answer("❌ شما هنوز در سیستم ثبت نام نکرده‌اید.")

        result = await session.execute(select(Config).where(Config.user_id == user.id))
        configs = result.scalars().all()

        if not configs:
            return await message.answer("📦 شما در حال حاضر هیچ سرویس فعالی ندارید.")

        builder = InlineKeyboardBuilder()
        for idx, config in enumerate(configs, start=1):
            emoji, status_text = _build_config_status(config)
            builder.button(
                text=f"{emoji} سرویس {idx} ({status_text})",
                callback_data=f"show_config:{config.id}",
            )

        builder.adjust(1)
        await message.answer(
            "👇 **لیست سرویس‌های شما:**\nبرای مشاهده جزئیات و مدیریت، روی سرویس مورد نظر کلیک کنید:",
            reply_markup=builder.as_markup(),
            parse_mode="Markdown",
        )


@router.callback_query(F.data == "back_to_services")
async def back_to_services_list(call: CallbackQuery):
    user_telegram_id = call.from_user.id

    async with async_session() as session:
        user = await session.scalar(
            select(User).where(User.telegram_id == user_telegram_id)
        )
        if not user:
            return await call.answer("خطا در سیستم رخ داده است.", show_alert=True)

        result = await session.execute(select(Config).where(Config.user_id == user.id))
        configs = result.scalars().all()

        if not configs:
            return await call.message.edit_text(
                "📦 شما در حال حاضر هیچ سرویس فعالی ندارید."
            )

        builder = InlineKeyboardBuilder()
        for idx, config in enumerate(configs, start=1):
            emoji, status_text = _build_config_status(config)
            builder.button(
                text=f"{emoji} سرویس {idx} ({status_text})",
                callback_data=f"show_config:{config.id}",
            )

        builder.adjust(1)
        await call.message.edit_text(
            "👇 **لیست سرویس‌های شما:**\nبرای مشاهده جزئیات و مدیریت، روی سرویس مورد نظر کلیک کنید:",
            reply_markup=builder.as_markup(),
            parse_mode="Markdown",
        )


@router.callback_query(F.data.startswith("show_config:"))
async def show_config_detail(call: CallbackQuery):
    config_id = int(call.data.split(":")[1])

    async with async_session() as session:
        config = await session.scalar(select(Config).where(Config.id == config_id))

        if not config:
            return await call.answer(
                "❌ این سرویس یافت نشد یا حذف شده است.", show_alert=True
            )

        # ─── سرویس در انتظار تایید ───
        if config.status == "pending":
            text = (
                f"⏳ **سرویس در انتظار تایید پرداخت**\n\n"
                f"📦 **نام محصول:** {config.name or 'سرویس اختصاصی'}\n"
                f"🔋 **ترافیک کل:** {config.total_traffic_gb} گیگابایت\n\n"
                f"✍️ رسید پرداخت این سرویس توسط مدیریت در حال بررسی است. "
                f"به محض تایید، لینک اتصال و مشخصات کامل سرور در همین بخش فعال خواهد شد."
            )
            kb = InlineKeyboardMarkup(
                inline_keyboard=[
                    [InlineKeyboardButton(text="📞 ارتباط با پشتیبانی", callback_data="contact_admin_action")],
                    [InlineKeyboardButton(text="🏠 بازگشت به لیست سرویس‌ها", callback_data="back_to_services")],
                ]
            )
            return await call.message.edit_text(text=text, reply_markup=kb, parse_mode="Markdown")

        # ─── محاسبه روزهای باقی‌مانده ───
        days_remaining = 0
        if config.expire_date:
            delta = config.expire_date - datetime.utcnow()
            days_remaining = max(delta.days, 0)

        # NOTE: مقادیر ترافیک واقعی نیاز به اتصال به پنل مرزبان/سنایی دارند
        total_traffic = str(config.total_traffic_gb) + " گیگابایت " if config.total_traffic_gb else "نامحدود"
        config_link = config.config_string if config.config_string else "❌ کانفیگی یافت نشد"
        #used_traffic = "۰"
        #remaining_traffic = total_traffic
        #usage_percent = "۰"

        text = (
            f"🌍 **موقعیت سرویس:** VIP01\n"
            f"📦 **نام محصول:** {config.name or 'سرویس اختصاصی'}\n\n"
            f"🔋 **ترافیک کل:** {total_traffic}\n"
            f"🆔 **شناسه سرویس:** `{config.id}`\n"
            f"📆 **اعتبار باقی‌مانده:** {days_remaining} روز\n"
            f"🔗 **لینک اتصال شما (کانفیگ):**\n\n"
            f"`{config_link}`\n\n"
            #f"📥 **حجم مصرفی:** {used_traffic} گیگابایت\n"
            #f"💢 **حجم باقی‌مانده:** {remaining_traffic} گیگابایت ({usage_percent}%)\n\n"
            #f"📆 **تاریخ اتمام:** {days_remaining} روز دیگر\n"
            #f"📊 **آخرین زمان اتصال:** متصل نشده\n\n"
            #f"💡 _برای قطع دسترسی دیگران کافیست روی گزینه «تغییر لینک» کلیک کنید._"
        )

        kb = InlineKeyboardMarkup(
            inline_keyboard=[
            #    [InlineKeyboardButton(text="♻️ بروزرسانی اطلاعات", callback_data=f"update_conf:{config_id}")],
            #    [
            #        InlineKeyboardButton(text="🔗 لینک اشتراک", callback_data=f"sub_link:{config_id}"),
            #        InlineKeyboardButton(text="🔰 دریافت کانفیگ", callback_data=f"get_conf:{config_id}"),
            #   ],
            #    [
            #        InlineKeyboardButton(text="⚙️ تغییر لینک", callback_data=f"change_link:{config_id}"),
            #        InlineKeyboardButton(text="⏳ تمدید سرویس", callback_data=f"extend_conf:{config_id}"),
            #    ],
            #    [
            #        InlineKeyboardButton(text="❌ بازگشت وجه", callback_data=f"refund_conf:{config_id}"),
            #        InlineKeyboardButton(text="🔴 خاموش کردن", callback_data=f"disable_conf:{config_id}"),
            #    ],
                [InlineKeyboardButton(text="🏠 بازگشت به لیست سرویس‌ها", callback_data="back_to_services")],
            ]
        )

        await call.message.edit_text(text=text, reply_markup=kb, parse_mode="Markdown")


# ════════════════════════════════════════════════════════
# ارتباط با پشتیبانی (callback از داخل جزئیات سرویس)
# ════════════════════════════════════════════════════════

@router.callback_query(F.data == "contact_admin_action")
async def contact_admin_action_callback(call: CallbackQuery):
    text = (
        "👨‍💻 **ارتباط با پشتیبانی**\n\n"
        "برای پیگیری وضعیت سرویس یا هرگونه مشکل، "
        "مستقیماً با ادمین در ارتباط باشید:\n\n"
        f"🆔 **{SUPPORT_ADMIN_USERNAME}**"
    )
    await call.message.answer(text, parse_mode="Markdown")
    await call.answer()


# ════════════════════════════════════════════════════════
# ارتباط با ادمین (دکمه متنی منو)
# ════════════════════════════════════════════════════════

@router.message(F.text == "📞 ارتباط با ادمین")
async def contact_admin(message: Message):
    text = (
        "👨‍💻 **ارتباط با پشتیبانی**\n\n"
        "در صورت بروز هرگونه مشکل در پرداخت، دریافت کانفیگ یا سوالات دیگر، "
        "می‌توانید مستقیماً با ادمین در ارتباط باشید:\n\n"
        f"🆔 **{SUPPORT_ADMIN_USERNAME}**"
    )
    await message.answer(text=text, parse_mode="Markdown")


# ════════════════════════════════════════════════════════
# بازگشت به منوی اصلی
# ════════════════════════════════════════════════════════

@router.callback_query(F.data == "back_to_main")
async def back_to_main_callback(call: CallbackQuery):
    await call.message.delete()
    await call.message.answer(
        "شما به منوی اصلی بازگشتید. لطفا انتخاب کنید:",
        reply_markup=get_main_menu_kb(),
    )


# ════════════════════════════════════════════════════════
# تمدید سرویس – لیست صفحه‌بندی‌شده
# ════════════════════════════════════════════════════════

async def send_renew_list(context, user_telegram_id: int, page: int = 1):
    ITEMS_PER_PAGE = 5

    async with async_session() as session:
        user = await session.scalar(
            select(User).where(User.telegram_id == user_telegram_id)
        )
        if not user:
            msg = "❌ شما هنوز در سیستم ثبت نام نکرده‌اید."
            if isinstance(context, Message):
                await context.answer(msg)
            else:
                await context.answer(msg, show_alert=True)
            return

        result = await session.execute(select(Config).where(Config.user_id == user.id))
        configs = result.scalars().all()

        if not configs:
            msg = "📦 شما در حال حاضر هیچ سرویس فعالی برای تمدید ندارید."
            if isinstance(context, Message):
                await context.answer(msg)
            else:
                await context.message.edit_text(msg)
            return

        total_pages = math.ceil(len(configs) / ITEMS_PER_PAGE)
        start_idx = (page - 1) * ITEMS_PER_PAGE
        current_configs = configs[start_idx: start_idx + ITEMS_PER_PAGE]

        builder = InlineKeyboardBuilder()
        for config in current_configs:
            display_name = config.name or f"سرویس شماره {config.id}"
            builder.button(
                text=f"✨ {display_name}",
                callback_data=f"renew_select:{config.id}",
            )

        nav_buttons = []
        if page > 1:
            nav_buttons.append(
                InlineKeyboardButton(text="◀️ قبلی", callback_data=f"renew_page:{page - 1}")
            )
        if page < total_pages:
            nav_buttons.append(
                InlineKeyboardButton(text="بعدی ▶️", callback_data=f"renew_page:{page + 1}")
            )
        if nav_buttons:
            builder.row(*nav_buttons)

        builder.row(
            InlineKeyboardButton(text="🏠 بازگشت به منوی اصلی", callback_data="back_to_main")
        )

        sizes = [1] * len(current_configs)
        if nav_buttons:
            sizes.append(len(nav_buttons))
        sizes.append(1)
        builder.adjust(*sizes)

        text = "📌 سرویس خود را جهت تمدید انتخاب نمایید."
        if isinstance(context, Message):
            await context.answer(text, reply_markup=builder.as_markup())
        else:
            await context.message.edit_text(text, reply_markup=builder.as_markup())

"""
@router.message(F.text == "تمدید سرویس")
async def renew_service_menu(message: Message):
    await send_renew_list(message, message.from_user.id, page=1)


@router.callback_query(F.data.startswith("renew_page:"))
async def renew_page_callback(call: CallbackQuery):
    page = int(call.data.split(":")[1])
    await send_renew_list(call, call.from_user.id, page=page)


@router.callback_query(F.data.startswith("renew_select:"))
async def select_service_to_renew(call: CallbackQuery):
    # FIX: بدنه سه‌گانه تکراری حذف و فقط یک نسخه صحیح باقی ماند
    config_id = int(call.data.split(":")[1])

    async with async_session() as session:
        result = await session.execute(select(Plan))
        plans = result.scalars().all()

        if not plans:
            return await call.answer("لیست پلن‌های تمدید خالی است.", show_alert=True)

        builder = InlineKeyboardBuilder()
        for plan in plans:
            builder.button(
                text=f"{plan.name} - {plan.price} تومان",
                callback_data=f"extend_plan:{config_id}:{plan.id}",
            )
        builder.button(text="🔙 بازگشت به لیست", callback_data="back_to_main")
        builder.adjust(1)

        await call.message.edit_text(
            f"🔄 در حال تمدید سرویس شماره {config_id}\n\n"
            f"🔽 لطفا پلن مورد نظر برای تمدید را انتخاب کنید:",
            reply_markup=builder.as_markup(),
        )

"""
# ════════════════════════════════════════════════════════
# تمدید – انتخاب پلن از صفحه جزئیات سرویس
# ════════════════════════════════════════════════════════
'''
@router.callback_query(F.data.startswith("extend_conf:"))
async def extend_config_callback(call: CallbackQuery):
    config_id = int(call.data.split(":")[1])

    async with async_session() as session:
        result = await session.execute(select(Plan))
        plans = result.scalars().all()

        if not plans:
            return await call.answer(
                "لیست پلن‌های تمدید در حال حاضر خالی است.", show_alert=True
            )

        builder = InlineKeyboardBuilder()
        for plan in plans:
            builder.button(
                text=f"{plan.name} - {plan.price} تومان",
                callback_data=f"extend_plan:{config_id}:{plan.id}",
            )
        builder.button(text="🔙 بازگشت", callback_data=f"show_config:{config_id}")
        builder.adjust(1)

        await call.message.edit_text(
            "🔽 لطفا پلن مورد نظر خود را جهت **تمدید سرویس** انتخاب کنید:",
            reply_markup=builder.as_markup(),
            parse_mode="Markdown",
        )


@router.callback_query(F.data.startswith("extend_plan:"))
async def select_extend_plan_callback(call: CallbackQuery):
    _, config_id, plan_id = call.data.split(":")

    async with async_session() as session:
        plan = await session.scalar(select(Plan).where(Plan.id == int(plan_id)))
        if not plan:
            return await call.answer("پلن انتخابی یافت نشد.", show_alert=True)

    card_number = CARD_NUMBER
    admin_name = ADMIN_NAME

    payment_instruction = (
        f"💳 **درگاه پرداخت دستی (تمدید سرویس)**\n\n"
        f"📦 **پلن انتخابی:** {plan.name} — {plan.price} تومان\n\n"
        f"مبلغ مورد نظر را به شماره کارت زیر پرداخت نمایید:\n"
        f"`{card_number}`\n"
        f"به نام: {admin_name}\n\n"
        f"⚠️ پس از پرداخت موفقیت‌آمیز، روی دکمه ارسال رسید کلیک کنید."
    )

    kb = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="📸 ارسال رسید", callback_data=f"send_extend_receipt:{config_id}:{plan_id}")],
            [InlineKeyboardButton(text="🔙 انصراف", callback_data=f"show_config:{config_id}")],
        ]
    )

    await call.message.edit_text(
        text=payment_instruction, reply_markup=kb, parse_mode="Markdown"
    )


@router.callback_query(F.data.startswith("send_extend_receipt:"))
async def send_extend_receipt_callback(call: CallbackQuery, state: FSMContext):
    _, config_id, plan_id = call.data.split(":")

    await state.set_data({
        "plan_id": int(plan_id),
        "config_id": int(config_id),
        "request_time": time.time(),
    })
    await state.set_state(PaymentState.waiting_for_receipt)

    await call.message.answer(
        "📸 لطفا تصویر رسید پرداخت خود را جهت **تمدید** ارسال کنید.\n\n"
        "⏳ شما ۱ ساعت برای ارسال رسید فرصت دارید.",
        parse_mode="Markdown",
    )
    await call.answer()

'''
# ════════════════════════════════════════════════════════
# خرید جدید – انتخاب پلن
# ════════════════════════════════════════════════════════

@router.callback_query(F.data.startswith("select_plan:"))
async def select_plan_callback(call: CallbackQuery, state: FSMContext):
    plan_id = int(call.data.split(":")[1])

    await state.set_data({"plan_id": plan_id})
    await state.set_state(PaymentState.waiting_for_service_name)

    await call.message.edit_text(
        "📝 **انتخاب نام سرویس**\n\n"
        "لطفاً یک نام دلخواه برای سرویس خود وارد کنید\n"
        "(مثلاً: گوشی من، لپ‌تاپ، اکانت علی و...):",
        parse_mode="Markdown",
    )


@router.message(PaymentState.waiting_for_service_name, F.text)
async def process_service_name(message: Message, state: FSMContext):
    service_name = message.text[:40].strip()

    data = await state.get_data()
    plan_id = data.get("plan_id")

    if not plan_id:
        await state.clear()
        return await message.answer(
            "❌ خطا در فرآیند. لطفا مجددا از منوی خرید اقدام کنید."
        )

    await state.update_data(service_name=service_name)

    card_number = CARD_NUMBER
    admin_name = ADMIN_NAME

    payment_instruction = (
        f"💳 **درگاه پرداخت دستی**\n\n"
        f"🏷 **نام انتخابی شما:** {service_name}\n\n"
        f"مبلغ مورد نظر را به شماره کارت زیر پرداخت نمایید:\n"
        f"`{card_number}`\n"
        f"به نام: {admin_name}\n\n"
        f"⚠️ پس از پرداخت موفقیت‌آمیز، روی دکمه ارسال رسید کلیک کنید."
    )

    await message.answer(
        text=payment_instruction,
        reply_markup=get_payment_receipt_kb(plan_id),
        parse_mode="Markdown",
    )


# FIX: تعریف تکراری این handler حذف شد؛ فقط یک نسخه صحیح با مدیریت service_name و config_id باقی ماند
@router.callback_query(F.data.startswith("send_receipt:"))
async def send_receipt_callback(call: CallbackQuery, state: FSMContext):
    plan_id = int(call.data.split(":")[1])

    data = await state.get_data()
    service_name = data.get("service_name")

    await state.set_data({
        "plan_id": plan_id,
        "service_name": service_name,
        "config_id": None,   # تمایز صریح از مسیر تمدید
        "request_time": time.time(),
    })
    await state.set_state(PaymentState.waiting_for_receipt)

    await call.message.answer(
        "📸 لطفا تصویر رسید پرداخت خود را ارسال کنید.\n\n"
        "⏳ شما ۱ ساعت برای ارسال رسید فرصت دارید."
    )
    await call.answer()


# ════════════════════════════════════════════════════════
# پردازش رسید (عکس)
# ════════════════════════════════════════════════════════

@router.message(PaymentState.waiting_for_receipt, F.photo)
async def process_receipt_photo(message: Message, state: FSMContext, bot):
    user_id = message.from_user.id

    data = await state.get_data()
    plan_id = data.get("plan_id")
    config_id = data.get("config_id")
    service_name = data.get("service_name")
    request_time = data.get("request_time")

    if request_time and (time.time() - request_time) > 3600:
        await state.clear()
        return await message.answer(
            "❌ مهلت ۱ ساعته شما برای ارسال رسید به پایان رسیده است. لطفا مجددا اقدام کنید."
        )

    async with async_session() as session:
        user = await session.scalar(select(User).where(User.telegram_id == user_id))
        plan = await session.scalar(select(Plan).where(Plan.id == plan_id))

        if not user or not plan:
            await state.clear()
            return await message.answer(
                "❌ خطایی در ثبت اطلاعات رخ داد. مجددا تلاش کنید."
            )

        if config_id:
            # ─── مسیر ۱: تمدید سرویس ─── رکورد جدید ساخته نمی‌شود
            action_text = "تمدید سرویس"
            callback_approve = f"approve_extend:{config_id}:{user_id}:{plan_id}"
            callback_reject = f"reject_receipt:{config_id}:{user_id}"
            extra_info = f"\n⚙️ شماره سرویس جهت تمدید: `{config_id}`"
            pending_msg = (
                "✅ رسید تمدید شما با موفقیت برای مدیریت ارسال شد و در صف بررسی قرار گرفت."
            )
        else:
            # ─── مسیر ۲: خرید جدید ─── رکورد Pending ساخته می‌شود
            new_config = Config(
                user_id=user.id,
                name=service_name or plan.name,
                type="paid",
                status="pending",
                total_traffic_gb=plan.volume_gb,
                config_string=None,
            )
            session.add(new_config)
            await session.flush()
            config_id = new_config.id
            
            # --- محاسبه موجودی فعلی انبار برای این پلن ---
            available_configs = await session.scalar(
                select(func.count(Config.id)).where(
                    Config.type == f"pool_{plan_id}",
                    Config.user_id == None,
                    Config.is_used == False
                )
            )
            
            if available_configs == 0:
                stock_info = f"\n\n🚨 **هشدار مهم:** موجودی این پلن ۰ است! لطفاً قبل از تایید با دستور `/add_vip {plan_id} [کانفیگ]` انبار را شارژ کنید."
            else:
                stock_info = f"\n\n📦 موجودی انبار این پلن: **{available_configs} عدد**"
            # ---------------------------------------------

            await session.commit()

            action_text = "خرید سرویس جدید"
            callback_approve = f"approve_receipt:{config_id}:{user_id}:{plan_id}"
            callback_reject = f"reject_receipt:{config_id}:{user_id}"
            extra_info = (
                f"\n🏷 نام سرویس: **{service_name or '—'}**"
                f"\n⚙️ شماره شناسایی سرویس جدید: `{config_id}`"
                f"{stock_info}"
            )
            pending_msg = (
                "✅ رسید شما با موفقیت برای مدیریت ارسال شد.\n"
                "سرویس شما در وضعیت **در انتظار تایید** ایجاد شد. "
                "می‌توانید وضعیت آن را در بخش «سرویس‌های من» دنبال کنید."
            )

    admin_kb = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="✅ تایید و اعمال", callback_data=callback_approve),
                InlineKeyboardButton(text="❌ رد رسید", callback_data=callback_reject),
            ]
        ]
    )

    for admin in ADMIN_IDS:
        try:
            await bot.send_photo(
                chat_id=admin,
                photo=message.photo[-1].file_id,
                caption=(
                    f"🧾 **رسید جدید ({action_text})**\n\n"
                    f"👤 آیدی کاربر: `{user_id}`\n"
                    f"📦 پلن انتخابی: **{plan.name}**"
                    f"{extra_info}"
                ),
                reply_markup=admin_kb,
                parse_mode="Markdown",
            )
        except Exception as e:
            print(f"Failed to send receipt to admin {admin}: {e}")

    await state.clear()
    await message.answer(pending_msg, parse_mode="Markdown")


@router.message(PaymentState.waiting_for_receipt)
async def process_receipt_invalid(message: Message, state: FSMContext):
    data = await state.get_data()
    request_time = data.get("request_time")

    if request_time and (time.time() - request_time) > 3600:
        await state.clear()
        return await message.answer(
            "❌ مهلت ۱ ساعته شما به پایان رسیده است. لطفا مجددا اقدام کنید."
        )

    await message.answer(
        "⚠️ لطفا فقط **تصویر (عکس)** رسید را ارسال کنید.\n"
        "برای انصراف می‌توانید از دستور /start استفاده کنید.",
        parse_mode="Markdown",
    )