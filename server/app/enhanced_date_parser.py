"""
Enhanced Date Parser for Human Language Date Recognition
Handles formats like "22nd December 2004", "December 22nd 2004", etc.
"""
import re
import calendar
import datetime as dt
from typing import Optional, Tuple, Dict, Any
import logging

logger = logging.getLogger(__name__)

class EnhancedDateParser:
    """Enhanced date parser for natural language date inputs"""
    
    def __init__(self):
        # Month mappings
        self.month_names = {month.lower(): idx for idx, month in enumerate(calendar.month_name[1:], 1)}
        self.month_abbrev = {month.lower(): idx for idx, month in enumerate(calendar.month_abbr[1:], 1)}
        self.all_months = {**self.month_names, **self.month_abbrev}
        
        # Relative date mappings for English and Gujarati
        self.relative_date_mappings = {
            "today": 0,
            "આજે": 0,
            "yesterday": -1,
            "ગઈકાલે": -1,
            "tomorrow": 1,
            "આવતીકાલે": 1,
        }
        
        # Ordinal suffixes
        self.ordinal_pattern = r'(\d{1,2})(st|nd|rd|th)?'
        
        # Comprehensive date patterns
        self.date_patterns = [
            # Natural language: "22nd December 2004", "December 22nd 2004"
            (r'(\d{1,2})(st|nd|rd|th)?\s+(january|february|march|april|may|june|july|august|september|october|november|december|jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)\s*,?\s*(\d{2,4})', 'day_month_year'),
            (r'(january|february|march|april|may|june|july|august|september|october|november|december|jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)\s+(\d{1,2})(st|nd|rd|th)?\s*,?\s*(\d{2,4})', 'month_day_year'),
            
            # Numeric formats: "01/01/2004", "01-01-2004", "1/1/04"
            (r'(\d{1,2})[/-](\d{1,2})[/-](\d{2,4})', 'numeric_slash'),
            
            # ISO format: "2004-01-01"
            (r'(\d{4})-(\d{1,2})-(\d{1,2})', 'iso'),
            
            # Short formats: "1 Jan 2004", "Jan 1 2004"
            (r'(\d{1,2})\s+(jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)\s*,?\s*(\d{2,4})', 'short_day_month_year'),
            (r'(jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)\s+(\d{1,2})\s*,?\s*(\d{2,4})', 'short_month_day_year'),
            
            # Special patterns: "22 December 2004" (without ordinals)
            (r'(\d{1,2})\s+(january|february|march|april|may|june|july|august|september|october|november|december|jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)\s*,?\s*(\d{2,4})', 'day_month_year_no_ordinal'),
            
            # Written out numbers: "twenty second December 2004"
            (r'(first|second|third|fourth|fifth|sixth|seventh|eighth|ninth|tenth|eleventh|twelfth|thirteenth|fourteenth|fifteenth|sixteenth|seventeenth|eighteenth|nineteenth|twentieth|twenty.first|twenty.second|twenty.third|twenty.fourth|twenty.fifth|twenty.sixth|twenty.seventh|twenty.eighth|twenty.ninth|thirtieth|thirty.first)\s+(january|february|march|april|may|june|july|august|september|october|november|december)\s*,?\s*(\d{2,4})', 'written_day_month_year'),
        ]
        
        # Written number to digit mapping
        self.written_numbers = {
            'first': 1, 'second': 2, 'third': 3, 'fourth': 4, 'fifth': 5,
            'sixth': 6, 'seventh': 7, 'eighth': 8, 'ninth': 9, 'tenth': 10,
            'eleventh': 11, 'twelfth': 12, 'thirteenth': 13, 'fourteenth': 14,
            'fifteenth': 15, 'sixteenth': 16, 'seventeenth': 17, 'eighteenth': 18,
            'nineteenth': 19, 'twentieth': 20, 'twenty first': 21, 'twenty-first': 21,
            'twenty second': 22, 'twenty-second': 22, 'twenty third': 23, 'twenty-third': 23,
            'twenty fourth': 24, 'twenty-fourth': 24, 'twenty fifth': 25, 'twenty-fifth': 25,
            'twenty sixth': 26, 'twenty-sixth': 26, 'twenty seventh': 27, 'twenty-seventh': 27,
            'twenty eighth': 28, 'twenty-eighth': 28, 'twenty ninth': 29, 'twenty-ninth': 29,
            'thirtieth': 30, 'thirty first': 31, 'thirty-first': 31
        }
    
    def parse_date(self, date_str: str) -> Optional[Tuple[int, int, int]]:
        """
        Parse date string and return (year, month, day) tuple
        Returns None if parsing fails
        """
        if not date_str or not date_str.strip():
            return None
        
        cleaned_str = date_str.strip().lower()
        logger.info(f"Parsing date: '{date_str}' -> cleaned: '{cleaned_str}'")
        
        # Check for relative dates first (e.g., "yesterday", "ગઈકાલે")
        for word, day_delta in self.relative_date_mappings.items():
            if word in cleaned_str:
                # Use timezone-aware UTC to get a consistent 'today'
                target_date = dt.datetime.now(dt.timezone.utc).date() + dt.timedelta(days=day_delta)
                logger.info(f"Parsed relative date '{word}' to {target_date}")
                # The rest of the validation will be handled by the calling function
                return (target_date.year, target_date.month, target_date.day)

        # Try each pattern
        for pattern, pattern_type in self.date_patterns:
            match = re.search(pattern, cleaned_str, re.IGNORECASE)
            if match:
                try:
                    groups = match.groups()
                    day, month, year = self._extract_date_components(groups, pattern_type)
                    
                    if day and month and year:
                        # Validate the date
                        is_valid, reason = self._validate_date_components(year, month, day)
                        if is_valid:
                            logger.info(f"Successfully parsed: {year}-{month:02d}-{day:02d}")
                            return (year, month, day)
                        else:
                            logger.warning(f"Invalid date components: {year}-{month}-{day}, Reason: {reason}")
                            continue
                
                except (ValueError, IndexError, KeyError) as e:
                    logger.warning(f"Error parsing with pattern {pattern_type}: {e}")
                    continue
        
        logger.warning(f"Failed to parse date: '{date_str}'")
        return None
    
    def _extract_date_components(self, groups: tuple, pattern_type: str) -> Tuple[Optional[int], Optional[int], Optional[int]]:
        """Extract day, month, year from regex groups based on pattern type"""
        day, month, year = None, None, None
        
        if pattern_type == 'day_month_year':
            day = int(groups[0])
            month = self.all_months[groups[2].lower()]
            year = int(groups[3])
            
        elif pattern_type == 'day_month_year_no_ordinal':
            day = int(groups[0])
            month = self.all_months[groups[1].lower()]
            year = int(groups[2])
            
        elif pattern_type == 'month_day_year':
            month = self.all_months[groups[0].lower()]
            day = int(groups[1])
            year = int(groups[3])
            
        elif pattern_type == 'numeric_slash':
            # Assume MM/DD/YYYY format
            month, day, year = int(groups[0]), int(groups[1]), int(groups[2])
            
        elif pattern_type == 'iso':
            year, month, day = int(groups[0]), int(groups[1]), int(groups[2])
            
        elif pattern_type == 'short_day_month_year':
            day = int(groups[0])
            month = self.all_months[groups[1].lower()]
            year = int(groups[2])
            
        elif pattern_type == 'short_month_day_year':
            month = self.all_months[groups[0].lower()]
            day = int(groups[1])
            year = int(groups[2])
            
        elif pattern_type == 'written_day_month_year':
            written_day = groups[0].lower().replace('-', ' ')
            day = self.written_numbers.get(written_day)
            month = self.all_months[groups[1].lower()]
            year = int(groups[2])
        
        # Handle two-digit years
        if year and year < 100:
            current_year = dt.datetime.now().year % 100
            century = 2000 if year <= current_year + 10 else 1900
            year += century
        
        return day, month, year
    
    def _validate_date_components(self, year: int, month: int, day: int) -> Tuple[bool, str]:
        """Validate that the date components form a valid date, returning a reason for failure."""
        try:
            # Basic range checks
            if not (1 <= month <= 12):
                return False, "invalid_month"
            if not (1 <= day <= 31):
                return False, "invalid_day"
            
            # More flexible year validation
            current_year = dt.datetime.now().year
            if not (current_year - 150 <= year <= current_year + 1):
                if year > current_year:
                    return False, "future_year"
                else:
                    return False, "past_year_too_early"
            
            # Check if the date actually exists (handles leap years, month lengths)
            parsed_date = dt.date(year, month, day)
            
            if parsed_date > dt.date.today():
                return False, "future_date"
            
            return True, "valid"
            
        except ValueError:
            return False, "invalid_date_combination"
    
    def format_date(self, year: int, month: int, day: int, format_type: str = "MM/dd/yyyy") -> str:
        """Format date components into specified format"""
        try:
            if format_type == "MM/dd/yyyy":
                return f"{month:02d}/{day:02d}/{year}"
            elif format_type == "yyyy-MM-dd":
                return f"{year}-{month:02d}-{day:02d}"
            elif format_type == "dd/MM/yyyy":
                return f"{day:02d}/{month:02d}/{year}"
            else:
                return f"{month:02d}/{day:02d}/{year}"  # Default
        except Exception:
            return f"{month:02d}/{day:02d}/{year}"
    
    def parse_and_format(self, date_str: str, format_type: str = "MM/dd/yyyy") -> Optional[str]:
        """Parse date string and return formatted date"""
        parsed = self.parse_date(date_str)
        if parsed:
            year, month, day = parsed
            return self.format_date(year, month, day, format_type)
        return None

    def parse_and_validate(self, date_str: str, format_type: str = "MM/dd/yyyy") -> Tuple[Optional[str], Optional[str]]:
        """
        Parse date string, validate it, and return formatted date or an error reason.
        Returns (formatted_date, None) on success, or (None, error_reason) on failure.
        """
        if not date_str or not date_str.strip():
            return None, "empty_input"

        parsed_components = self.parse_date(date_str)
        if parsed_components:
            year, month, day = parsed_components
            is_valid, reason = self._validate_date_components(year, month, day)
            if is_valid:
                return self.format_date(year, month, day, format_type), None
            else:
                return None, reason
        return None, "unrecognized_format"

# Global instance
enhanced_date_parser = EnhancedDateParser()