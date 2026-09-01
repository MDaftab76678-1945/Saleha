"""
Saleha Skills: DateTime Skill (Built-in Skill)

Instant, deterministic date and time calculations without calling an LLM:
- Current date, time, and UTC timestamp
- Difference between two dates
- Day of the week lookup
- Adding / subtracting days from a date
"""

import re
from datetime import datetime, date, timedelta, timezone

from saleha.core.skill_base import Skill, SkillResult


class DateTimeSkill(Skill):
    name = "datetime_helper"
    description = "Provides current date/time, date differences, day of week, and timestamp conversions instantly without LLM."

    def can_handle(self, task: str) -> bool:
        task_lower = task.lower()
        if any(kw in task_lower for kw in ["function", "class", "script", "program", "code", "write", "likho"]):
            return False

        # Match current date/time requests
        if any(p in task_lower for p in ["today's date", "what is today's date", "what is the date today", "current time", "current date", "current timestamp", "aaj ki date", "aaj konsa din"]):
            return True

        # Match date difference: "days between 2026-01-01 and 2026-08-24"
        if re.search(r"days?\s+between\s+\d{4}-\d{2}-\d{2}\s+and\s+\d{4}-\d{2}-\d{2}", task_lower):
            return True

        # Match day of week: "what day is 2026-08-24" or "day of week for 2026-08-24"
        if re.search(r"(?:day\s+(?:of\s+week\s+)?(?:is|for|of)|konsa\s+din)\s+(\d{4}-\d{2}-\d{2})", task_lower):
            return True

        # Match timestamp conversion: "timestamp 1700000000 to date"
        if re.search(r"timestamp\s+(\d+)\s+(?:to\s+date|in\s+date)", task_lower):
            return True

        return False

    def execute(self, task: str) -> SkillResult:
        task_lower = task.lower()

        # 1. Current date / time
        if any(p in task_lower for p in ["today's date", "what is today's date", "what is the date today", "current date", "aaj ki date"]):
            now = datetime.now()
            day_name = now.strftime("%A")
            return SkillResult(success=True, output=f"Today is {day_name}, {now.strftime('%Y-%m-%d')} (Local time: {now.strftime('%H:%M:%S')})")

        if any(p in task_lower for p in ["current time", "what time is it", "abhi kya time"]):
            now = datetime.now()
            return SkillResult(success=True, output=f"Current Time: {now.strftime('%H:%M:%S')} (Date: {now.strftime('%Y-%m-%d')})")

        if "current timestamp" in task_lower or "timestamp now" in task_lower:
            ts = int(datetime.now(timezone.utc).timestamp())
            return SkillResult(success=True, output=f"Current UTC Timestamp: {ts}")

        # 2. Days between two dates
        diff_match = re.search(r"days?\s+between\s+(\d{4}-\d{2}-\d{2})\s+and\s+(\d{4}-\d{2}-\d{2})", task_lower)
        if diff_match:
            d1_str, d2_str = diff_match.groups()
            try:
                d1 = datetime.strptime(d1_str, "%Y-%m-%d").date()
                d2 = datetime.strptime(d2_str, "%Y-%m-%d").date()
                diff = abs((d2 - d1).days)
                return SkillResult(success=True, output=f"Days between {d1_str} and {d2_str}: {diff} days")
            except Exception as e:
                return SkillResult(success=False, output="", error=f"Date parse error: {e}")

        # 3. Day of week
        day_match = re.search(r"(?:day\s+(?:of\s+week\s+)?(?:is|for|of)|konsa\s+din)\s+(\d{4}-\d{2}-\d{2})", task_lower)
        if day_match:
            d_str = day_match.group(1)
            try:
                d = datetime.strptime(d_str, "%Y-%m-%d").date()
                day_name = d.strftime("%A")
                return SkillResult(success=True, output=f"{d_str} is a {day_name}")
            except Exception as e:
                return SkillResult(success=False, output="", error=f"Date parse error: {e}")

        # 4. Timestamp to date
        ts_match = re.search(r"timestamp\s+(\d+)\s+(?:to\s+date|in\s+date)", task_lower)
        if ts_match:
            ts = int(ts_match.group(1))
            try:
                dt = datetime.fromtimestamp(ts, timezone.utc)
                return SkillResult(success=True, output=f"Timestamp {ts} in UTC is: {dt.strftime('%Y-%m-%d %H:%M:%S UTC')}")
            except Exception as e:
                return SkillResult(success=False, output="", error=f"Timestamp error: {e}")

        return SkillResult(success=False, output="", error="Could not process datetime request.")

