"""
Scheduler Jobs Module

This module contains all scheduled job functions and the scheduler management.
Includes resume journey checks for users who paused mid-journey.
"""

import pytz
from datetime import datetime, timedelta
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.interval import IntervalTrigger
import logging

logger = logging.getLogger(__name__)

from app.services.scheduler.helper import (
    get_step_display_name,
    is_user_in_journey,
    JOURNEY_ORDER,
    STEP_DISPLAY_NAMES,
)
import app.services.crm.sessions as crm_sessions
from app.services.whatsapp.client import _send_whatsapp_buttons

# Global scheduler instance
_scheduler = None
_sending_resume_messages = False


def send_resume_journey_template(user_id: str, user_name: str, last_question: str):
    """
    Send a resume journey message with an interactive button to a user who paused mid-journey.
    
    Message format:
    "Hey {name}😊, it looks like you paused your progress at {step_name}.
    
    Tap the button below to resume✅."
    
    Parameters:
    - user_name: User's first name
    - last_question: The last question/step the user was on
    """
    logger.info("📤 SENDING RESUME JOURNEY MESSAGE to %s (User: %s, Last Question: %s)", user_id, user_name, last_question)
    
    # Create the message text
    step_name = get_step_display_name(last_question)
    message_text = f"Hey {user_name}😊, it looks like you paused your progress at {step_name}.\n\nTap the button below to resume✅."
    
    # Create the interactive button
    buttons = [
        {
            "type": "reply",
            "reply": {
                "id": "resume_journey",
                "title": "Resume"
            }
        }
    ]
    
    try:
        # Send the interactive button message
        _send_whatsapp_buttons(
            user_id=user_id,
            body_text=message_text,
            buttons=buttons
        )
        
        logger.info("✅ Resume journey message with button sent successfully!")
        return True
        
    except Exception as e:
        logger.error("❌ Message send failed: %s", e)
        return False


def get_active_journey_users(min_time: datetime, max_time: datetime) -> dict:
    """
    Fetch users who were active within the specified time window and are still in the journey.
    Uses aggregation to join conversation_history (has resume_intervals_sent) with user_info
    (has last_question in user_profile).
    """
    try:
        # Ensure Mongo is initialized
        crm_sessions._init_mongo_if_needed()

        # Ensure times are timezone-aware (IST)
        ist = pytz.timezone('Asia/Kolkata')
        if min_time.tzinfo is None:
            min_time = ist.localize(min_time)
        else:
            min_time = min_time.astimezone(ist)

        if max_time.tzinfo is None:
            max_time = ist.localize(max_time)
        else:
            max_time = max_time.astimezone(ist)

        min_time_iso = min_time.isoformat()
        max_time_iso = max_time.isoformat()

        # ✅ FIX: Query conversation_history for recent updates
        # (where resume_intervals_sent and last_updated are stored)
        query = {
            "last_updated": {
                "$gte": min_time_iso,
                "$lte": max_time_iso
            }
        }

        projection = {
            "user_id": 1,
            "last_updated": 1,
            "resume_intervals_sent": 1,
            "_id": 0
        }

        cursor = crm_sessions._sessions_collection.find(query, projection)
        conv_hist_list = list(cursor)

        users = {}

        # For each conversation_history record, load user_info to get last_question and user_name
        for conv_doc in conv_hist_list:
            user_id = conv_doc.get("user_id")
            if not user_id:
                continue

            # ✅ Load user_info to get last_question, user_name, and other details
            user_doc = crm_sessions._users_collection.find_one(
                {"user_id": user_id},
                {
                    "user_profile.last_question": 1,
                    "user_profile.user_name": 1,
                    "product": 1,
                    "active_product": 1,
                    "_id": 0
                }
            )

            if not user_doc:
                logger.debug("⚠️ No user_info found for user_id: %s", user_id)
                continue

            # Extract last_question and user_name from user_profile
            user_profile = user_doc.get("user_profile", {})
            last_question = user_profile.get("last_question")
            user_name = user_profile.get("user_name", "there")  # user_name is stored in user_profile, not top level

            # Validate: Check if user is on free_form
            # Users on free_form might have a stale last_question from previous journeys but should not be disturbed
            product = user_doc.get("product") or user_doc.get("active_product")
            if product == "free_form":
                logger.debug("ℹ️ User %s is on free_form, skipping resume", user_id)
                continue

            # Validate: check if user is in journey
            if not last_question or last_question == "post_plan_qna":
                logger.debug("ℹ️ User %s not in journey (last_question: %s)", user_id, last_question)
                continue

            # User is in journey - add to results
            users[user_id] = {
                "user_id": user_id,
                "user_name": user_name,
                "last_question": last_question,
                "last_updated": conv_doc.get("last_updated"),
                "resume_intervals_sent": conv_doc.get("resume_intervals_sent", {})
            }

        logger.info("✅ Found %d users in journey within time window", len(users))
        return users

    except Exception as e:
        logger.error("⚠️ Error fetching active journey users: %s", e)
        return {}


def check_and_send_resume_journey_messages(
    *,
    sessions_override=None,
    intervals_minutes_override=None,
):
    """
    Check active users and send resume journey template at specific intervals.
    Optimized to query only relevant users from MongoDB.

    Intervals: 5 mins, 3 hours, 8 hours (progressive based on inactivity).
    No time window restrictions - runs 24/7.

    Test overrides (keyword-only):
      sessions_override: dict of {user_id: session_data} to use instead of DB.
      intervals_minutes_override: list of intervals in minutes (e.g. [0.25] for 15s).
    When both are provided, DB is not queried and the given intervals are used.
    """
    global _sending_resume_messages

    # Prevent multiple simultaneous executions (skip when using test overrides so tests can run)
    if not (sessions_override is not None and intervals_minutes_override is not None):
        if _sending_resume_messages:
            logger.info("⏸️  Resume journey check already in progress, skipping this cycle")
            return

    _sending_resume_messages = True
    try:
        # Get current time in IST
        ist = pytz.timezone('Asia/Kolkata')
        current_time_ist = datetime.now(ist)

        if sessions_override is not None and intervals_minutes_override is not None:
            # Test path: use provided sessions and intervals
            sessions = sessions_override
            RESUME_INTERVALS_MINUTES = intervals_minutes_override
            logger.info("🧪 Test mode: using %d sessions, intervals %s", len(sessions), RESUME_INTERVALS_MINUTES)
        else:
            # Define the max lookback window (9 hours to cover the 8h interval + buffer)
            # and min lookback (4 minutes to cover 5 min interval + buffer)
            max_lookback = current_time_ist - timedelta(hours=9)
            min_lookback = current_time_ist - timedelta(minutes=4)

            # Fetch only potentially relevant users from MongoDB
            logger.info("🔍 Querying active journey users between %s and %s...", max_lookback.strftime('%H:%M'), min_lookback.strftime('%H:%M'))
            sessions = get_active_journey_users(max_lookback, min_lookback)

            if not sessions:
                logger.info("📭 No users found in the active time window")
                return

            RESUME_INTERVALS_MINUTES = [5, 180, 480]  # 5 minutes, 3 hours, 8 hours

        logger.info("🔍 Found %d potential users to check...", len(sessions))

        messages_sent = 0
        messages_skipped = 0
        
        for user_id, session_data in sessions.items():
            try:
                last_question = session_data.get("last_question")
                user_name = session_data.get("user_name", "Unknown")
                
                # Double check journey status (though query handles most of it)
                if not is_user_in_journey(last_question):
                    messages_skipped += 1
                    continue
                
                # Get last_updated timestamp
                last_updated_str = session_data.get("last_updated")
                if not last_updated_str:
                    messages_skipped += 1
                    continue
                
                # Parse timestamp
                try:
                    if isinstance(last_updated_str, str):
                        last_updated = datetime.fromisoformat(last_updated_str.replace('Z', '+00:00'))
                    else:
                        last_updated = last_updated_str
                    
                    if last_updated.tzinfo is None:
                        last_updated = ist.localize(last_updated)
                    
                    # Calculate time difference in minutes
                    time_diff_minutes = (current_time_ist - last_updated).total_seconds() / 60
                    
                    # Get the count of already sent intervals
                    resume_intervals_sent = session_data.get("resume_intervals_sent", {})
                    if isinstance(resume_intervals_sent, str):
                        resume_intervals_sent = {}
                    
                    # Determine which interval to check based on what's already been sent
                    # Logic: Send progressively - 5min first, then 3h, then 8h
                    intervals_sent_count = len([k for k, v in resume_intervals_sent.items() if v])
                    
                    if intervals_sent_count >= len(RESUME_INTERVALS_MINUTES):
                        # All intervals exhausted
                        messages_skipped += 1
                        continue
                    
                    # Get the next interval to check
                    target_interval_minutes = RESUME_INTERVALS_MINUTES[intervals_sent_count]
                    
                    # Check if enough time has passed for this interval (exact match, no tolerance)
                    if time_diff_minutes < target_interval_minutes:
                        messages_skipped += 1
                        continue
                    
                    # Check if this specific interval was already sent
                    interval_key = str(target_interval_minutes)
                    if resume_intervals_sent.get(interval_key):
                        messages_skipped += 1
                        continue
                    
                    # Format interval for display
                    if target_interval_minutes < 60:
                        interval_display = f"{target_interval_minutes:.0f}min"
                    else:
                        interval_display = f"{target_interval_minutes/60:.0f}h"

                    logger.info("📤 Sending resume template to %s (%s) - Interval: %s (inactive for %.1f min)", user_id, user_name, interval_display, time_diff_minutes)
                    logger.debug("   User Status: last_question=%s, intervals_sent=%s, time_diff=%.1f min vs threshold=%d min",
                                 last_question, resume_intervals_sent, time_diff_minutes, target_interval_minutes)
                    
                    success = send_resume_journey_template(
                        user_id=user_id,
                        user_name=user_name,
                        last_question=last_question
                    )
                    
                    if success:
                        # Update DB - mark this interval as sent
                        try:
                            crm_sessions._init_mongo_if_needed()
                            resume_intervals_sent[interval_key] = True
                            
                            # Update only the specific field
                            crm_sessions._sessions_collection.update_one(
                                {"user_id": user_id},
                                {"$set": {"resume_intervals_sent": resume_intervals_sent}}
                            )
                        except Exception as e:
                            logger.error("⚠️ Error updating DB for %s: %s", user_id, e)
                            
                        messages_sent += 1
                    else:
                        messages_skipped += 1
                
                except Exception as e:
                    logger.error("⚠️ Error processing user %s: %s", user_id, e)
                    messages_skipped += 1
                    continue
            
            except Exception as e:
                logger.error("❌ Error in loop for %s: %s", user_id, e)
                messages_skipped += 1
        
        if messages_sent > 0:
            logger.info("📊 Resume Journey Summary: %d sent, %d skipped", messages_sent, messages_skipped)
    
    except Exception as e:
        logger.error("❌ Error in check_and_send_resume_journey_messages: %s", e)
    finally:
        _sending_resume_messages = False


def start_scheduler():
    """Start the background scheduler for resume journey reminders."""
    global _scheduler
    
    if _scheduler is not None and _scheduler.running:
        logger.info("⏰ Scheduler already running")
        return
    
    _scheduler = AsyncIOScheduler()
    
    # Remove any existing jobs first
    try:
        _scheduler.remove_job('check_resume_journey')
        logger.info("🗑️  Removed existing job")
    except:
        pass
    
    # Schedule the resume journey check to run every 5 minutes
    _scheduler.add_job(
        check_and_send_resume_journey_messages,
        trigger=IntervalTrigger(minutes=5, timezone='Asia/Kolkata'),
        id='check_resume_journey',
        name='Check and send resume journey templates',
        replace_existing=True
    )
    
    _scheduler.start()
    logger.info("⏰ Scheduler started:")
    logger.info("   - Resume journey check: every 5 minutes")


def stop_scheduler():
    """Stop the background scheduler."""
    global _scheduler
    
    if _scheduler is not None and _scheduler.running:
        # Remove jobs before shutting down
        try:
            _scheduler.remove_job('check_resume_journey')
            logger.info("🗑️  Removed resume journey check job")
        except:
            pass
        
        _scheduler.shutdown()
        logger.info("⏰ Scheduler stopped")
    else:
        logger.info("⏰ Scheduler is not running")