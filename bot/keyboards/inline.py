from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from typing import List
from database.models import Plan

def get_force_join_kb(channel_link: str) -> InlineKeyboardMarkup:
    """Returns the InlineKeyboardMarkup for forcing channel join."""
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="عضویت در کانال اسپانسر 📣", url=channel_link)],
            [InlineKeyboardButton(text="✅ بررسی عضویت", callback_data="check_join")]
        ]
    )

def get_plans_kb(plans: List[Plan]) -> InlineKeyboardMarkup:
    """Returns an InlineKeyboardMarkup with dynamically generated plan buttons."""
    keyboard = []
    for plan in plans:
        btn_text = f"{plan.name} | {plan.price:,.0f} تومان"
        keyboard.append([InlineKeyboardButton(text=btn_text, callback_data=f"select_plan:{plan.id}")])
    
    return InlineKeyboardMarkup(inline_keyboard=keyboard)

def get_payment_receipt_kb(plan_id: int) -> InlineKeyboardMarkup:
    """Returns an InlineKeyboardMarkup for the payment receipt submission."""
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="🧾 ارسال رسید", callback_data=f"send_receipt:{plan_id}")]
        ]
    )