from aiogram.types import ReplyKeyboardMarkup, KeyboardButton

def get_main_menu_kb() -> ReplyKeyboardMarkup:
    """Returns the main menu ReplyKeyboardMarkup."""
    return ReplyKeyboardMarkup(
        keyboard=[
            
                [KeyboardButton(text="🎁 دریافت کانفیگ رایگان")]
                ,
                [KeyboardButton(text="💰 خرید کانفیگ")],
                #KeyboardButton(text="تمدید سرویس")],
                [KeyboardButton(text="سرویس های من")],
                [KeyboardButton(text="📞 ارتباط با ادمین"),
                KeyboardButton(text="🤝 زیرمجموعه‌گیری (دریافت جایزه)")]
            ]
        ,
        resize_keyboard=True,
        input_field_placeholder="انتخاب کنید..."
    )