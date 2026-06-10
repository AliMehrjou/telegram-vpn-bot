import asyncio
from typing import List, Tuple
from aiogram.types import Message
from aiogram.exceptions import TelegramRetryAfter, TelegramForbiddenError
import logging

async def broadcast_message(msg_to_send: Message, users: List[int]) -> Tuple[int, int]:
    """
    Broadcasts a message to a list of users, respecting Telegram's rate limits.
    Returns a tuple of (success_count, failure_count)
    """
    success_count = 0
    failure_count = 0

    for user_id in users:
        try:
            await msg_to_send.copy_to(chat_id=user_id)
            success_count += 1
            
        except TelegramRetryAfter as e:
            # Respect Flood limits
            logging.warning(f"Rate limited by Telegram. Sleeping for {e.retry_after} seconds.")
            await asyncio.sleep(e.retry_after)
            try:
                await msg_to_send.copy_to(chat_id=user_id)
                success_count += 1
            except Exception:
                failure_count += 1
                
        except TelegramForbiddenError:
            # User has blocked the bot
            failure_count += 1
            
        except Exception as e:
            # Other errors (e.g., account deleted)
            logging.error(f"Failed to send to {user_id}: {e}")
            failure_count += 1

        # Safe delay to stay below 30 messages/sec limits
        await asyncio.sleep(0.05)

    return success_count, failure_count