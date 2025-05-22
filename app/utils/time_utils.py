from datetime import datetime
from typing import Literal

TimeOfDay = Literal["morning", "afternoon", "evening", "night"]

def get_time_of_day() -> TimeOfDay:
    """
    Determine the time of day based on the current server time.
    
    Returns:
        TimeOfDay: One of "morning", "afternoon", "evening", or "night"
        
    Time ranges:
        - morning: 5:00 - 11:59
        - afternoon: 12:00 - 16:59
        - evening: 17:00 - 20:59
        - night: 21:00 - 4:59
    """
    current_hour = datetime.utcnow().hour
    
    if 5 <= current_hour < 12:
        return "morning"
    elif 12 <= current_hour < 17:
        return "afternoon"
    elif 17 <= current_hour < 21:
        return "evening"
    else:  # 21:00 - 4:59
        return "night" 