from datetime import datetime

class DateConfig:
    """
    Centralized configuration for date ranges used in DatePickers.
    """
    START_YEAR_OFFSET = -5  # 5 years in the past
    END_YEAR_OFFSET = 30    # 30 years in the future
    
    @classmethod
    def get_date_range(cls):
        """
        Returns a dictionary with 'first_date' and 'last_date' based on offsets.
        """
        now = datetime.now()
        return {
            "first_date": datetime(now.year + cls.START_YEAR_OFFSET, 1, 1),
            "last_date": datetime(now.year + cls.END_YEAR_OFFSET, 12, 31)
        }

class AppConfig:
    """
    General application settings.
    """
    APP_NAME = "CARDI Log"
    VERSION = "3.0"
