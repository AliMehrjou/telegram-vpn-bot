import json
import os

from aiogram import Router, F
from aiogram.filters import Command
from aiogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton
from sqlalchemy import select, func
from database.connection import async_session
from database.models import Config, Plan, User
from utils.broadcaster import broadcast_message
from config import ADMIN_IDS, SUB_LINK_TUTORIAL_URL
from aiogram.types import CallbackQuery
from aiogram.types import CallbackQuery
from sqlalchemy import select, update
from datetime import datetime, timedelta

router = Router()

# This filter protects all endpoints in this router ensuring only ADMIN_ID can trigger them
router.message.filter(F.from_user.id.in_(ADMIN_IDS))
router.callback_query.filter(F.from_user.id.in_(ADMIN_IDS))

@router.message(Command("add_config"))
async def add_config_cmd(message: Message):
    parts = message.text.split(maxsplit=1)
    if len(parts) < 2:
        return await message.answer(
            "❌ فرمت نامعتبر است.\n\n"
            "✅ استفاده صحیح:\n`/add_config [متن کانفیگ]`\n\n"
            "💡 **نکته:** برای افزودن گروهی، کانفیگ‌ها را در خطوط جداگانه (با Enter) در یک پیام ارسال کنید.", 
            parse_mode="Markdown"
        )

    # جدا کردن متن بر اساس خطوط (Enter)
    configs_text = parts[1].strip().split('\n')
    added_count = 0
    
    async with async_session() as session:
        for line in configs_text:
            config_string = line.strip()
            if config_string:  # اگر خط خالی نبود
                new_config = Config(config_string=config_string, type="free")
                session.add(new_config)
                added_count += 1
                
        if added_count > 0:
            await session.commit()

    await message.answer(
        f"✅ تعداد **{added_count}** کانفیگ رایگان جدید با موفقیت به دیتابیس اضافه شد.", 
        parse_mode="Markdown"
    )

@router.message(Command("add_plan"))
async def add_plan_cmd(message: Message):
    parts = message.text.split(maxsplit=1)
    if len(parts) < 2:
        return await message.answer("❌ فرمت نامعتبر است.\nمثال: `/add_plan Name:Plan1|Price:50000|Days:30|GB:50`", parse_mode="Markdown")

    try:
        raw_data = parts[1].strip()
        pairs = raw_data.split("|")
        data_dict = {}
        for pair in pairs:
            k, v = pair.split(":")
            data_dict[k.strip()] = v.strip()

        name = data_dict["Name"]
        price = float(data_dict["Price"])
        days = int(data_dict["Days"])
        gb = float(data_dict["GB"]) if data_dict["GB"] not in "نامحدود" else data_dict["GB"]

        async with async_session() as session:
            new_plan = Plan(name=name, price=price, duration_days=days, volume_gb=gb)
            session.add(new_plan)
            await session.commit()

        await message.answer(f"✅ پلن اشتراکی جدید ({name}) با موفقیت ایجاد شد.")
        
    except Exception as e:
        await message.answer(f"❌ خطا در پردازش اطلاعات:\n{e}\n\nاطمینان حاصل کنید جداکننده‌ها به درستی قرار دارند.")

@router.message(Command("sendall"))
async def sendall_cmd(message: Message):
    msg_to_send = message.reply_to_message
    
    if not msg_to_send:
        return await message.answer("❌ لطفا این دستور را بر روی یک پیام ریپلای (Reply) کنید تا آن را ارسال کنم.")

    loading_msg = await message.answer("⏳ در حال دریافت لیست کاربران...")

    async with async_session() as session:
        result = await session.execute(select(User.telegram_id))
        users = result.scalars().all()

    if not users:
        return await loading_msg.edit_text("❌ هیچ کاربری در سیستم برای ارسال یافت نشد.")

    await loading_msg.edit_text(f"🚀 در حال انجام عملیات ارسال به {len(users)} کاربر...\nلطفا شکیبا باشید.")

    # Call the broadcaster utility function
    success, failed = await broadcast_message(msg_to_send, users)

    await message.answer(
        f"📊 **گزارش پایانی پخش پیام:**\n\n"
        f"✅ موفق: {success}\n"
        f"❌ ناموفق: {failed}\n"
        f"👥 کل کاربران: {len(users)}",
        parse_mode="Markdown"
    )

@router.message(Command("users_count"))
async def users_count_cmd(message: Message):
    # پیام در حال پردازش (اختیاری، برای زمانی که دیتابیس بزرگ است)
    loading_msg = await message.answer("⏳ در حال دریافت آمار کاربران...")

    async with async_session() as session:
        # استفاده از func.count برای شمارش بهینه در سطح دیتابیس
        # فرض بر این است که جدول User یک ستون id (یا telegram_id) به عنوان Primary Key دارد
        result = await session.execute(select(func.count(User.telegram_id)))
        total_users = result.scalar() or 0

    await loading_msg.edit_text(
        f"📊 **آمار کاربران ربات:**\n\n"
        f"👥 تعداد کل کاربران ثبت‌شده: **{total_users}** نفر",
        parse_mode="Markdown"
    )



# ════════════════════════════════════════════════════════
# تایید رسید خرید جدید
# ════════════════════════════════════════════════════════
@router.callback_query(F.data.startswith("approve_receipt:"))
async def approve_receipt_cmd(call: CallbackQuery, bot):
    # فرمت آپدیت شده: approve_receipt:{config_id}:{user_id}:{plan_id}
    data_parts = call.data.split(":")
    if len(data_parts) != 4:
        return await call.answer("خطا در خواندن اطلاعات.", show_alert=True)
        
    config_id = int(data_parts[1])
    buyer_id = int(data_parts[2])
    plan_id = int(data_parts[3])

    async with async_session() as session:
        # دریافت اطلاعات در انتظار تاییدِ کاربر
        config = await session.scalar(select(Config).where(Config.id == config_id))
        buyer = await session.scalar(select(User).where(User.telegram_id == buyer_id))
        plan = await session.scalar(select(Plan).where(Plan.id == plan_id))
        
        if not config or not buyer or not plan:
            return await call.answer("❌ اطلاعات کاربر، سرویس یا پلن یافت نشد.", show_alert=True)

        if config.status != "pending":
            return await call.answer("⚠️ این رسید قبلا بررسی شده است.", show_alert=True)

        # ۱. جستجو برای یک کانفیگ آماده در انبار این پلن (pool) با اعمال قفل
        pool_config = await session.scalar(
            select(Config).where(
                Config.type == f"pool_{plan_id}",
                Config.user_id == None,
                Config.is_used == False
            ).with_for_update().limit(1)
        )

        if not pool_config:
            # اگر انبار خالی بود، عملیات متوقف می‌شود تا ادمین کانفیگ اضافه کند
            return await call.answer(
                f"❌ موجودی انبار پلن «{plan.name}» تمام شده است!\nابتدا با دستور /add_vip کانفیگ جدید اضافه کنید.", 
                show_alert=True
            )

        # ۲. انتقال کانفیگ از انبار به سرویس در انتظار تایید کاربر
        config.status = "active"
        config.expire_date = datetime.utcnow() + timedelta(days=plan.duration_days)
        config.config_string = pool_config.config_string # انتقال متن کانفیگ
        
        # ۳. حذف کانفیگ خام از انبار (برای جلوگیری از شلوغی دیتابیس)
        await session.delete(pool_config)
        
        # ۴. بررسی سیستم زیرمجموعه‌گیری و جایزه خرید
        if buyer.invited_by:
            # قفل کردن ردیف کاربر معرف
            referrer = await session.scalar(
                select(User).where(User.telegram_id == buyer.invited_by).with_for_update()
            )
            if referrer:
                referrer.purchase_invite_count += 1
                
                # بررسی رسیدن به ضریب ۱۰ برای اهدای کانفیگ ۱ ماهه
                if referrer.purchase_invite_count % 10 == 0:
                    reward_conf = await session.scalar(
                        select(Config).where(
                            Config.type == "reward_purchase", 
                            Config.user_id.is_(None), 
                            Config.is_used == False
                        ).with_for_update().limit(1)
                    )
                    
                    if reward_conf:
                        reward_conf.user_id = referrer.id
                        reward_conf.is_used = True
                        reward_conf.status = "active"
                        reward_conf.name = f"🎁 جایزه ۱۰ خرید (توسط زیرمجموعه)"
                        reward_conf.expire_date = datetime.utcnow() + timedelta(days=30)
                        
                        session.add(reward_conf) # ثبت صریح

                        reward_text = (
                            f"🛍 **مژده!**\n\n"
                            f"۱۰ نفر از زیرمجموعه‌های شما خرید موفق داشتند!\n"
                            f"این کانفیگ **۱ ماهه نامحدود تک‌کاربره** هدیه شما:\n\n"
                            f"`{reward_conf.config_string}`\n\n"
                            f"💡 _این سرویس به لیست «سرویس‌های من» اضافه شد._"
                        )
                        try:
                            await bot.send_message(
                                chat_id=referrer.telegram_id, 
                                text=reward_text, 
                                parse_mode="Markdown"
                            )
                        except Exception:
                            pass
                    else:
                        # ارسال هشدار به ادمین‌ها
                        for admin in ADMIN_IDS:
                            try:
                                await bot.send_message(
                                    chat_id=admin, 
                                    text=f"🚨 **اتمام موجودی جوایز خرید!**\nزیرمجموعه‌های یک کاربر به ضریب {referrer.purchase_invite_count} خرید رسیدند اما انبار `reward_purchase` خالی است!"
                                )
                            except Exception:
                                pass
                
                session.add(referrer) # ثبت صریح
        
        await session.commit()

        # ۵. بررسی موجودی انبار پس از کسر این کانفیگ و ارسال آلارم در صورت اتمام
        remaining_configs = await session.scalar(
            select(func.count(Config.id)).where(
                Config.type == f"pool_{plan_id}",
                Config.user_id == None,
                Config.is_used == False
            )
        )

        if remaining_configs == 0:
            for admin in ADMIN_IDS:
                try:
                    await bot.send_message(
                        chat_id=admin,
                        text=(
                            f"🚨 **هشدار اتمام موجودی انبار!**\n\n"
                            f"مدیر گرامی، با تایید آخرین رسید، موجودی کانفیگ‌های پلن **{plan.name}** "
                            f"(آیدی پلن: `{plan_id}`) به **۰** رسید.\n"
                            f"لطفا هرچه سریع‌تر با دستور زیر انبار را شارژ کنید:\n\n"
                            f"`/add_vip {plan_id} [متن کانفیگ جدید]`"
                        ),
                        parse_mode="Markdown"
                    )
                except Exception:
                    pass

    # ۶. ساخت دکمه شیشه‌ای (لینک را از تنظیمات یا Config کلاس خودت بخوان)
    # توجه: حواست باشه متغیر Config رباتت با مدل دیتابیس (Config) تداخل نام نداشته باشه.
    # فرض می‌کنیم متغیری به نام SUB_LINK_TUTORIAL_URL در فضای سراسری داری یا از فایل تنظیمات می‌خوانی.
    tutorial_keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(
                text="📖 آموزش اتصال و اضافه کردن ساب‌لینک", 
                url=SUB_LINK_TUTORIAL_URL  # مطمئن شو این متغیر تعریف شده باشه
            )
        ]
    ])

    # ارسال اتوماتیک کانفیگ و آیدی اختصاصی به کاربر خریدار
    try:
        await bot.send_message(
            chat_id=buyer_id, 
            text=(
                f"✅ <b>پرداخت شما توسط مدیریت تایید شد!</b>\n\n"
                f"📦 <b>نام سرویس:</b> {config.name}\n"
                f"🆔 <b>شناسه یکتای کانفیگ:</b> <code>{config.id}</code>\n\n"
                f"🔗 <b>لینک اتصال شما:</b>\n"
                f"<code>{config.config_string}</code>\n\n"
                f"💡 <i>برای مشاهده جزئیات، می‌توانید به بخش «سرویس‌های من» مراجعه کنید.</i>\n\n"  # کاما حذف شد و به جایش \n آمد
                f"👇 <i>جهت راهنمایی برای اتصال، روی دکمه زیر کلیک کنید:</i>"
            ), 
            parse_mode="HTML",
            reply_markup=tutorial_keyboard
        )
    except Exception as e:
        # برای عیب‌یابی در کنسول در صورت بروز خطای مجدد
        print(f"Error sending message to buyer: {e}")

    # ۷. آپدیت پیام رسید برای ادمین
    await call.message.edit_caption(
        caption=(
            f"{call.message.caption}\n\n"
            f"✅ **نتیجه: تایید و ارسال شد.**\n"
            f"🆔 شناسه اختصاص یافته: `{config.id}`"
        ),
        reply_markup=None
    )
    await call.answer("رسید تایید و کانفیگ اتوماتیک ارسال شد.")
# ════════════════════════════════════════════════════════
# رد رسید
# ════════════════════════════════════════════════════════
@router.callback_query(F.data.startswith("reject_receipt:"))
async def reject_receipt_cmd(call: CallbackQuery, bot):
    # فرمت ارسال شده از سمت کاربر: reject_receipt:{config_id}:{user_id}
    data_parts = call.data.split(":")
    config_id = int(data_parts[1])
    buyer_id = int(data_parts[2])

    async with async_session() as session:
        config = await session.scalar(select(Config).where(Config.id == config_id))
        # پاک کردن رکورد در انتظار تایید از دیتابیس (تا بخش سرویس های من شلوغ نشود)
        if config and config.status == "pending":
            await session.delete(config)
            await session.commit()

    try:
        await bot.send_message(
            chat_id=buyer_id,
            text="❌ **کاربر گرامی، رسید ارسالی شما توسط مدیریت رد شد.**\nدر صورت بروز مشکل با پشتیبانی در ارتباط باشید.",
            parse_mode="Markdown"
        )
    except Exception:
        pass

    await call.message.edit_caption(
        caption=f"{call.message.caption}\n\n❌ **نتیجه: رد شد.**",
        reply_markup=None
    )
    await call.answer("رسید رد شد.")

# ════════════════════════════════════════════════════════
# تایید رسید تمدید سرویس
# ════════════════════════════════════════════════════════
@router.callback_query(F.data.startswith("approve_extend:"))
async def approve_extend_cmd(call: CallbackQuery, bot):
    # فرمت: approve_extend:{config_id}:{user_id}:{plan_id}
    data_parts = call.data.split(":")
    config_id = int(data_parts[1])
    user_id = int(data_parts[2])
    plan_id = int(data_parts[3])

    async with async_session() as session:
        config = await session.scalar(select(Config).where(Config.id == config_id))
        plan = await session.scalar(select(Plan).where(Plan.id == plan_id))
        
        if not config or not plan:
            return await call.answer("❌ اطلاعات سرویس یا پلن در دیتابیس یافت نشد.", show_alert=True)

        config.status = "active"
        config.total_traffic_gb = (config.total_traffic_gb or 0) + plan.volume_gb
        
        current_expire = config.expire_date or datetime.utcnow()
        if current_expire < datetime.utcnow():
            current_expire = datetime.utcnow()
        config.expire_date = current_expire + timedelta(days=plan.duration_days)
        
        await session.commit()

    # TODO: ارسال درخواست API به پنل برای تمدید واقعی کانفیگ در سرور

    try:
        await bot.send_message(
            chat_id=user_id, 
            text=f"✅ **تمدید سرویس با موفقیت انجام شد!**\n\n📦 نام سرویس: {config.name}\n🔋 حجم اضافه شده: {plan.volume_gb} گیگابایت\n\nوضعیت جدید در «سرویس های من» قابل مشاهده است.", 
            parse_mode="Markdown"
        )
    except Exception:
        pass

    await call.message.edit_caption(
        caption=f"{call.message.caption}\n\n✅ **نتیجه: تمدید تایید شد.**",
        reply_markup=None
    )
    await call.answer("تمدید با موفقیت اعمال شد.")

@router.message(Command("help_admin"))
async def help_admin_cmd(message: Message):
    help_text = (
        "🛠 <b>راهنمای پنل مدیریت ربات</b>\n\n"
        "در اینجا لیست تمامی دستورات ادمین و نحوه استفاده از آن‌ها قرار دارد:\n\n"
        
        "🔹 <b>افزودن کانفیگ رایگان</b>\n"
        "<code>/add_config [متن کانفیگ]</code>\n"
        "💡 نکته: برای افزودن گروهی، کانفیگ‌ها را در خطوط جداگانه بفرستید.\n\n"

        "🔹 <b>تنظیم محدودیت زمانی کانفیگ رایگان</b> 🆕\n"
        "فرمت: \n<code>/set_free_limit [تعداد روز]</code>\n"
        "مثال: \n<code>/set_free_limit 1</code> (هر ۲۴ ساعت) \nیا \n<code>/set_free_limit 0.5</code> (هر ۱۲ ساعت)\n\n"
        
        "🔹 <b>افزودن پلن اشتراکی جدید</b>\n"
        "<code>/add_plan Name:[نام]|Price:[قیمت]|Days:[روز]|GB:[حجم]</code>\n\n"

        "🔹 <b>مشاهده لیست پلن‌ها (جهت دریافت آیدی)</b>\n"
        "فرمت: \n<code>/plans_list</code>\n"
        "توضیح: آیدی پلن‌ها برای شارژ انبار کانفیگ استفاده می‌شود.\n\n"
        
        "🔹 <b>شارژ انبار (اضافه کردن کانفیگ به پلن خاص)</b>\n"
        "فرمت: \n<code>/add_vip [آیدی_پلن] [متن_کانفیگ]</code>\n"
        "توضیح: کانفیگ‌ها در انبار ذخیره شده و پس از تایید رسید، به‌صورت خودکار به کاربر تحویل داده می‌شوند.\n\n"
        
        "🔹 <b>نظارت روی یک ساب خاص (رهگیری کانفیگ)</b>\n"
        "فرمت: \n<code>/sub_info [ID یا نام کانفیگ]</code>\n"
        "توضیح: نشان می‌دهد کانفیگ دست چه کسی است، کی خریداری شده و چقدر اعتبار دارد.\n\n"

        "🔹 <b>مشاهده تمام ساب‌های یک کاربر</b>\n"
        "فرمت: \n<code>/user_subs [آیدی تلگرام کاربر]</code>\n"
        "توضیح: لیست تمام سرویس‌های فعال یا در انتظار تاییدِ یک کاربر را نشان می‌دهد.\n\n"
        
        "🔹 <b>ارسال پیام همگانی (Broadcast)</b>\n"
        "<code>/sendall</code> (ریپلای روی یک پیام)\n\n"
        
        "🔹 <b>ارسال پیام به کاربر خاص</b>\n"
        "<code>/send_message [آیدی کاربر] [متن پیام]</code>\n\n"
        
        "🔹 <b>مشاهده آمار کاربران</b>\n"
        "<code>/users_count</code>\n\n"
        
        "💡 <b>سیستم هوشمند رسیدها:</b>\n"
        "• <b>موجودی انبار:</b> هنگام ارسال رسید جدید توسط کاربر، موجودی انبار آن پلن به شما نمایش داده می‌شود.\n"
        "• <b>تایید رسید:</b> کانفیگ به‌صورت خودکار کسر و تحویل داده می‌شود. اگر انبار خالی شود ربات هشدار می‌دهد.\n"
        "• <b>رد رسید:</b> رکورد از دیتابیس پاک شده و به کاربر اطلاع داده می‌شود."

        "🔹 <b>افزودن کانفیگ جایزه (زیرمجموعه‌گیری)</b> 🆕\n"
        "فرمت: \n<code>/add_reward [invite/purchase] [متن کانفیگ]</code>\n"
        "▫️ <code>invite</code>: شارژ انبار جوایز ۵ دعوت (۱ روزه)\n"
        "▫️ <code>purchase</code>: شارژ انبار جوایز ۱۰ خرید (۱ ماهه)\n\n"
    )

    await message.answer(help_text, parse_mode="HTML")

@router.message(Command("sub_info"))
async def sub_info_cmd(message: Message):
    parts = message.text.split(maxsplit=1)
    if len(parts) < 2:
        return await message.answer("❌ فرمت نامعتبر است. استفاده:\n<code>/sub_info [شناسه یا نام کانفیگ]</code>", parse_mode="HTML")

    query_val = parts[1].strip()

    async with async_session() as session:
        # جستجو بر اساس ID دیتابیس (اگر ورودی عدد بود) یا نام کانفیگ
        if query_val.isdigit():
            stmt = select(Config).where(Config.id == int(query_val)).limit(1)
        else:
            stmt = select(Config).where(Config.name == query_val).limit(1)

        config = await session.scalar(stmt)

        if not config:
            return await message.answer("❌ کانفیگی با این مشخصات در دیتابیس یافت نشد.")

        # پیدا کردن صاحب کانفیگ
        user = await session.scalar(select(User).where(User.id == config.user_id)) if config.user_id else None

        # محاسبه روزهای باقیمانده
        days_left = "نامشخص"
        if config.expire_date:
            delta = config.expire_date - datetime.utcnow()
            days_left = max(0, delta.days)

        # اطلاعات خریدار (تبدیل به HTML)
        if user:
            username_text = f"@{user.username}" if user.username else "ندارد"
            owner_info = f"آیدی عددی: <code>{user.telegram_id}</code>\nیوزرنیم: {username_text}"
        else:
            owner_info = "بدون صاحب (هنوز به کاربری اختصاص نیافته)"
            
        # تاریخ خرید / ایجاد
        created_date = config.created_at.strftime('%Y-%m-%d %H:%M') if config.created_at else "نامشخص"
        expire_date_str = config.expire_date.strftime('%Y-%m-%d %H:%M') if config.expire_date else "ندارد"

        # 🔴 فرمت دهی با HTML برای جلوگیری از ارور آندرلاین و کاراکترهای خاص
        info_text = (
            f"🔍 <b>اطلاعات دقیق سرویس:</b>\n\n"
            f"🆔 <b>شناسه دیتابیس:</b> {config.id}\n"
            f"🏷 <b>نام کانفیگ:</b> {config.name or 'ندارد'}\n"
            f"🟢 <b>وضعیت:</b> {config.status}\n"
            f"نوع سرویس: {config.type}\n"
            f"──────────────\n"
            f"👤 <b>اطلاعات صاحب سرویس (دست کیه):</b>\n{owner_info}\n"
            f"──────────────\n"
            f"📅 <b>تاریخ ایجاد / خرید:</b> {created_date}\n"
            f"⏳ <b>اعتبار باقیمانده:</b> {days_left} روز\n"
            f"🛑 <b>تاریخ انقضا:</b> {expire_date_str}\n"
            f"──────────────\n"
            f"📊 <b>ترافیک کل:</b> {config.total_traffic_gb} GB\n"
            f"📉 <b>ترافیک مصرفی:</b> {config.used_traffic_gb} GB\n"
        )

        await message.answer(info_text, parse_mode="HTML")


@router.message(Command("user_subs"))
async def user_subs_cmd(message: Message):
    parts = message.text.split(maxsplit=1)
    if len(parts) < 2:
        return await message.answer("❌ فرمت نامعتبر است. استفاده:\n<code>/user_subs [آیدی تلگرام کاربر]</code>", parse_mode="HTML")

    telegram_id = parts[1].strip()
    if not telegram_id.isdigit():
        return await message.answer("❌ آیدی تلگرام باید عدد باشد.")

    async with async_session() as session:
        # پیدا کردن کاربر
        user = await session.scalar(select(User).where(User.telegram_id == int(telegram_id)))
        if not user:
            return await message.answer("❌ کاربری با این آیدی تلگرام در ربات ثبت نام نکرده است.")

        # پیدا کردن تمام کانفیگ های این کاربر
        result = await session.execute(select(Config).where(Config.user_id == user.id))
        configs = result.scalars().all()

        if not configs:
            return await message.answer(f"❌ کاربر <code>{telegram_id}</code> هیچ سرویسی خریداری نکرده است.", parse_mode="HTML")

        # 🔴 تبدیل به HTML
        response = f"📋 <b>لیست سرویس‌های کاربر <code>{telegram_id}</code>:</b>\n\n"
        for c in configs:
            days_left = max(0, (c.expire_date - datetime.utcnow()).days) if c.expire_date else "نامشخص"
            status_emoji = "🟢" if c.status == "active" else "🟡" if c.status == "pending" else "🔴"
            
            response += (
                f"{status_emoji} <b>نام:</b> {c.name or 'بدون نام'} | <b>ID:</b> {c.id}\n"
                f"   ⏳ باقیمانده: {days_left} روز | 📊 حجم: {c.total_traffic_gb}GB\n"
                f"   ─\n"
            )

        await message.answer(response, parse_mode="HTML")
        
@router.message(Command("user_subs"))
async def user_subs_cmd(message: Message):
    parts = message.text.split(maxsplit=1)
    if len(parts) < 2:
        return await message.answer("❌ فرمت نامعتبر است. استفاده:\n`/user_subs [آیدی تلگرام کاربر]`", parse_mode="Markdown")

    telegram_id = parts[1].strip()
    if not telegram_id.isdigit():
        return await message.answer("❌ آیدی تلگرام باید عدد باشد.")

    async with async_session() as session:
        # پیدا کردن کاربر
        user = await session.scalar(select(User).where(User.telegram_id == int(telegram_id)))
        if not user:
            return await message.answer("❌ کاربری با این آیدی تلگرام در ربات ثبت نام نکرده است.")

        # پیدا کردن تمام کانفیگ های این کاربر
        result = await session.execute(select(Config).where(Config.user_id == user.id))
        configs = result.scalars().all()

        if not configs:
            return await message.answer(f"❌ کاربر `{telegram_id}` هیچ سرویسی خریداری نکرده است.", parse_mode="Markdown")

        response = f"📋 **لیست سرویس‌های کاربر `{telegram_id}`:**\n\n"
        for c in configs:
            days_left = max(0, (c.expire_date - datetime.utcnow()).days) if c.expire_date else "نامشخص"
            status_emoji = "🟢" if c.status == "active" else "🟡" if c.status == "pending" else "🔴"
            
            response += (
                f"{status_emoji} **نام:** {c.name or 'بدون نام'} | **ID:** {c.id}\n"
                f"   ⏳ باقیمانده: {days_left} روز | 📊 حجم: {c.total_traffic_gb}GB\n"
                f"   ─\n"
            )

        await message.answer(response, parse_mode="Markdown")

@router.message(Command("plans_list"))
async def plans_list_cmd(message: Message):
    async with async_session() as session:
        result = await session.execute(select(Plan))
        plans = result.scalars().all()
        
        if not plans:
            return await message.answer("❌ هیچ پلنی در دیتابیس ثبت نشده است.")
            
        text = "📋 **لیست پلن‌های موجود:**\n\n"
        for p in plans:
            text += f"🆔 **آیدی:** `{p.id}` | 🏷 **نام:** {p.name} | 🔋 **حجم:** {p.volume_gb}GB\n"
            
        text += "\n💡 از این آیدی‌ها برای اضافه کردن کانفیگ در دستور `/add_vip` استفاده کنید."
        await message.answer(text, parse_mode="Markdown")

@router.message(Command("add_vip"))
async def add_vip_cmd(message: Message):
    parts = message.text.split(maxsplit=2)
    if len(parts) < 3:
        return await message.answer(
            "❌ فرمت نامعتبر است.\n"
            "✅ استفاده صحیح: `/add_vip [آیدی_پلن] [متن_کانفیگ]`\n"
            "🔍 برای دیدن آیدی پلن‌ها: `/plans_list`\n\n"
            "💡 **نکته:** برای شارژ گروهی انبار، کانفیگ‌ها را در خطوط جداگانه (با Enter) بفرستید.", 
            parse_mode="Markdown"
        )

    plan_id_str = parts[1].strip()
    configs_text = parts[2].strip().split('\n')

    if not plan_id_str.isdigit():
        return await message.answer("❌ آیدی پلن باید یک عدد باشد.")

    plan_id = int(plan_id_str)
    added_count = 0

    async with async_session() as session:
        # بررسی اینکه آیا اصلا چنین پلنی داریم؟
        plan = await session.scalar(select(Plan).where(Plan.id == plan_id))
        if not plan:
            return await message.answer("❌ پلنی با این آیدی یافت نشد!")

        # ثبت گروهی کانفیگ‌ها در انبار این پلن
        for line in configs_text:
            config_string = line.strip()
            if config_string:  # نادیده گرفتن خطوط خالی
                new_config = Config(
                    config_string=config_string, 
                    type=f"pool_{plan_id}",
                    user_id=None, 
                    is_used=False
                )
                session.add(new_config)
                added_count += 1
                
        if added_count > 0:
            await session.commit()

    await message.answer(
        f"✅ تعداد **{added_count}** کانفیگ با موفقیت به انبار پلن **{plan.name}** اضافه شد.", 
        parse_mode="Markdown"
    )

@router.message(Command("set_free_limit"))
async def set_free_limit_cmd(message: Message):
    parts = message.text.split()
    if len(parts) < 2:
        return await message.answer(
            "❌ فرمت نامعتبر است.\n"
            "✅ استفاده صحیح: `/set_free_limit [تعداد روز]`\n"
            "مثال: `/set_free_limit 1` یا `/set_free_limit 0.5`",
            parse_mode="Markdown"
        )
    
    try:
        days = float(parts[1])
        if days <= 0:
            return await message.answer("❌ عدد باید بزرگتر از صفر باشد.")
    except ValueError:
        return await message.answer("❌ لطفا یک عدد معتبر وارد کنید.")

    settings = {}
    file_path = "bot_settings.json"
    
    # خواندن امن فایل فعلی (در صورت وجود)
    if os.path.exists(file_path):
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                settings = json.load(f)
        except Exception:
            pass # اگر فایل خراب بود نادیده بگیر و از نو بساز
    
    settings["free_limit_days"] = days
    
    # ذخیره امن تنظیمات جدید
    try:
        with open(file_path, "w", encoding="utf-8") as f:
            json.dump(settings, f)
        await message.answer(f"✅ محدودیت دریافت کانفیگ رایگان با موفقیت روی **{days} روز** تنظیم شد.", parse_mode="Markdown")
    except Exception as e:
        await message.answer(f"❌ خطا در ذخیره تنظیمات: {e}")

@router.message(Command("add_reward"))
async def add_reward_cmd(message: Message):
    parts = message.text.split(maxsplit=2)
    if len(parts) < 3:
        return await message.answer(
            "❌ فرمت نامعتبر است.\n\n"
            "✅ استفاده صحیح:\n`/add_reward [invite/purchase] [متن کانفیگ‌ها]`\n\n"
            "مثال‌ها:\n"
            "▫️ `/add_reward invite vless://...` (برای جایزه ۵ زیرمجموعه - ۱ روزه)\n"
            "▫️ `/add_reward purchase vless://...` (برای جایزه ۱۰ خرید - ۱ ماهه)\n\n"
            "💡 **نکته:** می‌توانید چند کانفیگ را با Enter در خطوط جداگانه بفرستید.", 
            parse_mode="Markdown"
        )

    reward_type = parts[1].lower()
    if reward_type not in ["invite", "purchase"]:
        return await message.answer("❌ نوع جایزه باید دقیقاً `invite` یا `purchase` باشد.")

    configs_text = parts[2].strip().split('\n')
    added_count = 0
    db_type = f"reward_{reward_type}"

    async with async_session() as session:
        for line in configs_text:
            config_string = line.strip()
            if config_string:
                # این کانفیگ‌ها فعلاً به کسی اختصاص داده نمی‌شوند و خاموش هستند
                new_config = Config(
                    config_string=config_string, 
                    type=db_type, 
                    user_id=None, 
                    is_used=False
                )
                session.add(new_config)
                added_count += 1
                
        if added_count > 0:
            await session.commit()

    await message.answer(
        f"✅ تعداد **{added_count}** کانفیگ جایزه از نوع **{reward_type}** با موفقیت به انبار جوایز اضافه شد.", 
        parse_mode="Markdown"
    )


@router.message(Command("send_message"))
async def send_message_cmd(message: Message, bot):
    # جدا کردن متن به 3 قسمت: دستور، آیدی، متن پیام
    parts = message.text.split(maxsplit=2)
    if len(parts) < 3:
        return await message.answer(
            "❌ فرمت نامعتبر است.\n\n"
            "✅ استفاده صحیح:\n`/send_message [آیدی_تلگرام] [متن پیام]`",
            parse_mode="Markdown"
        )

    target_id_str = parts[1].strip()
    msg_text = parts[2].strip()

    if not target_id_str.isdigit():
        return await message.answer("❌ آیدی تلگرام باید یک عدد باشد.")

    target_id = int(target_id_str)

    try:
        # ارسال پیام به کاربر مورد نظر
        await bot.send_message(
            chat_id=target_id, 
            text=f"📩 **پیام جدید از طرف مدیریت:**\n\n{msg_text}", 
            parse_mode="Markdown"
        )
        await message.answer(f"✅ پیام شما با موفقیت به کاربر `{target_id}` ارسال شد.", parse_mode="Markdown")
    except Exception as e:
        await message.answer(
            f"❌ خطا در ارسال پیام!\n"
            f"ممکن است کاربر ربات را استارت نکرده باشد، ربات را بلاک کرده باشد، یا آیدی اشتباه باشد.\n\n"
            f"جزئیات خطا: `{e}`",
            parse_mode="Markdown"
        )