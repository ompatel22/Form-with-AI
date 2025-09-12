"""
Enhanced Voice Interruption Handler
Manages voice commands to interrupt AI speech with better pattern matching
"""
import re
import logging
from typing import Dict, List, Optional, Set, Union
from enum import Enum
from .language_support import Language, language_support

logger = logging.getLogger(__name__)

class InterruptionType(Enum):
    STOP = "stop"
    PAUSE = "pause"
    CONTINUE = "continue"
    SKIP = "skip"

class VoiceInterruptionHandler:
    """Enhanced voice interruption handler with improved pattern matching"""
    
    def __init__(self):
        # Enhanced interruption commands with phonetic variations
        self.interruption_commands = {
            Language.ENGLISH: {
                InterruptionType.STOP: [
                    # Direct commands
                    "stop", "pause", "wait", "hold", "hold on", "wait a minute",
                    "stop talking", "pause please", "hold please", "one moment",
                    "wait wait", "stop stop", "pause pause", "enough", "that's enough",
                    
                    # Natural variations
                    "can you stop", "please stop", "stop it", "stop that",
                    "hold up", "hang on", "wait up", "wait there", "stop right there",
                    "just stop", "stop now", "pause that", "hold that",
                    
                    # Common expressions
                    "ok stop", "okay stop", "alright stop", "stop for a second",
                    "give me a moment", "just a moment", "one sec", "wait a sec"
                ],
                InterruptionType.SKIP: [
                    # Direct skip commands
                    "skip", "next", "skip this", "move on", "continue",
                    "skip audio", "next question", "go ahead", "proceed",
                    
                    # Natural variations
                    "let's move on", "can we skip this", "skip to next",
                    "go to next", "move to next", "skip it", "pass",
                    "next one", "move forward", "let's continue",
                    
                    # Common expressions
                    "ok next", "okay next", "alright next", "skip ahead",
                    "can we continue", "let's go ahead"
                ],
                InterruptionType.CONTINUE: [
                    "continue", "go on", "keep going", "resume", "proceed",
                    "carry on", "go ahead", "keep talking", "please continue",
                    "ok continue", "okay continue", "alright continue"
                ]
            },
            Language.GUJARATI: {
                InterruptionType.STOP: [
                    # Direct Gujarati commands
                    "બંધ કરો", "રોકો", "થોભો", "રાહ", "રાહ જુઓ", "એક મિનિટ",
                    "બોલવાનું બંધ કરો", "કૃપા કરીને રોકો", "થોભો પ્લીઝ", "એક ક્ષણ",
                    "રાહ રાહ", "બંધ બંધ", "રોકો રોકો", "બસ", "હવે બંધ કરો",
                    
                    # Natural variations
                    "તમે રોકો", "કૃપા કરીને થોભો", "બંધ કરી દો", "હવે બંધ",
                    "થોડો રોકો", "રાહ જો", "એક વાર રોકો", "ક્ષણ ભર રોકો",
                    
                    # Common expressions
                    "હા બંધ કરો", "બરાબર રોકો", "બસ કરો", "બહુ થયું"
                ],
                InterruptionType.SKIP: [
                    # Direct skip commands
                    "છોડો", "આગળ", "આ છોડો", "આગળ વધો", "ચાલુ રાખો",
                    "આવાજ છોડો", "આગળનો પ્રશ્ન", "આગળ બઢો", "આગળ જાઓ",
                    
                    # Natural variations
                    "આપણે આગળ વધીએ", "આ છોડી દો", "આગળ જઈએ",
                    "આગળનું કરીએ", "આ પસાર કરો", "આગળ વધવું છે",
                    
                    # Common expressions
                    "હા આગળ", "બરાબર આગળ", "ચાલો આગળ", "આગળ કરો"
                ],
                InterruptionType.CONTINUE: [
                    "ચાલુ રાખો", "આગળ વધો", "ચાલુ કરો", "ફરીથી શરૂ કરો", "આગળ બઢો",
                    "બોલતા રહો", "આગળ જાઓ", "બોલવાનું ચાલુ રાખો", "કૃપા કરીને ચાલુ રાખો",
                    "હા ચાલુ રાખો", "બરાબર ચાલુ કરો"
                ]
            }
        }
        
        # Phonetic variations for better matching (Gujarati in English script)
        self.phonetic_gujarati = {
            # Stop commands
            "band karo": "બંધ કરો",
            "roko": "રોકો", 
            "thobo": "થોભો",
            "rah": "રાહ",
            "rah juo": "રાહ જુઓ",
            "ek minute": "એક મિનિટ",
            "bas": "બસ",
            "bas karo": "બસ કરો",
            
            # Skip commands  
            "chodo": "છોડો",
            "agal": "આગળ",
            "agal vadho": "આગળ વધો",
            "chalu rakho": "ચાલુ રાખો",
            "agal jao": "આગળ જાઓ",
            
            # Continue commands
            "chalu karo": "ચાલુ કરો",
            "agal vadho": "આગળ વધો"
        }
        
        # Compiled regex patterns for faster matching
        self._compiled_patterns: Dict[Language, Dict[InterruptionType, List[re.Pattern]]] = {}
        self._phonetic_patterns: List[re.Pattern] = []
        self._compile_patterns()
    
    def _compile_patterns(self):
        """Compile regex patterns for all commands"""
        # Compile main language patterns
        for language, commands in self.interruption_commands.items():
            self._compiled_patterns[language] = {}
            for interrupt_type, phrases in commands.items():
                patterns = []
                for phrase in phrases:
                    # Create flexible patterns with word boundaries
                    escaped_phrase = re.escape(phrase)
                    # Allow for minor spacing and pronunciation variations
                    flexible_pattern = escaped_phrase.replace(r'\ ', r'\s*')
                    patterns.append(re.compile(rf'\b{flexible_pattern}\b', re.IGNORECASE))
                self._compiled_patterns[language][interrupt_type] = patterns
        
        # Compile phonetic patterns for Gujarati
        for phonetic, gujarati in self.phonetic_gujarati.items():
            escaped = re.escape(phonetic)
            flexible = escaped.replace(r'\ ', r'\s*')
            pattern = re.compile(rf'\b{flexible}\b', re.IGNORECASE)
            self._phonetic_patterns.append((pattern, gujarati))
    
    def _preprocess_text(self, text: str, language: Language = Language.ENGLISH) -> str:
        """Preprocess text for better matching"""
        if not text:
            return ""
        
        # Basic cleaning
        text = text.strip().lower()
        text = re.sub(r'\s+', ' ', text)  # Normalize spaces
        
        # Handle phonetic Gujarati if needed
        if language == Language.GUJARATI:
            for pattern, gujarati_text in self._phonetic_patterns:
                if pattern.search(text):
                    # Replace phonetic with actual Gujarati for better matching
                    text = text + " " + gujarati_text.lower()
        
        return text
    
    def detect_interruption(self, text: str, language: Language = Language.ENGLISH) -> Optional[InterruptionType]:
        """Enhanced interruption detection with preprocessing"""
        if not text or not text.strip():
            return None
        
        # Preprocess text
        processed_text = self._preprocess_text(text, language)
        
        # Quick early return for very short text
        if len(processed_text.strip()) < 2:
            return None
        
        # Check patterns for the specified language
        if language in self._compiled_patterns:
            for interrupt_type, patterns in self._compiled_patterns[language].items():
                for pattern in patterns:
                    if pattern.search(processed_text):
                        logger.info(f"✅ Detected {interrupt_type.value} command in {language.value}: '{text}'")
                        return interrupt_type
        
        # Check the other language as fallback
        other_language = Language.GUJARATI if language == Language.ENGLISH else Language.ENGLISH
        if other_language in self._compiled_patterns:
            for interrupt_type, patterns in self._compiled_patterns[other_language].items():
                for pattern in patterns:
                    if pattern.search(processed_text):
                        logger.info(f"✅ Detected {interrupt_type.value} command in {other_language.value}: '{text}'")
                        return interrupt_type
        
        # Check for partial matches (fuzzy matching for speech recognition errors)
        interruption = self._fuzzy_match_interruption(processed_text, language)
        if interruption:
            logger.info(f"✅ Fuzzy matched {interruption.value} command: '{text}'")
            return interruption
        
        return None
    
    def _fuzzy_match_interruption(self, text: str, language: Language) -> Optional[InterruptionType]:
        """Fuzzy matching for speech recognition errors"""
        text_words = set(text.split())
        
        # Define key words for each interruption type
        stop_words = {"stop", "pause", "wait", "hold", "બંધ", "રોકો", "થોભો", "રાહ", "બસ"}
        skip_words = {"skip", "next", "move", "છોડો", "આગળ", "continue"}
        continue_words = {"continue", "go", "resume", "ચાલુ", "આગળ"}
        
        # Count matches
        stop_matches = len(text_words.intersection(stop_words))
        skip_matches = len(text_words.intersection(skip_words))
        continue_matches = len(text_words.intersection(continue_words))
        
        # Return the type with most matches (if any)
        if stop_matches > 0 and stop_matches >= skip_matches and stop_matches >= continue_matches:
            return InterruptionType.STOP
        elif skip_matches > 0 and skip_matches > continue_matches:
            return InterruptionType.SKIP
        elif continue_matches > 0:
            return InterruptionType.CONTINUE
        
        return None
    
    def is_interruption_command(self, text: str, language: Language = Language.ENGLISH) -> bool:
        """Check if text contains any interruption command"""
        return self.detect_interruption(text, language) is not None
    
    def should_stop_audio(self, text: str, language: Language = Language.ENGLISH) -> bool:
        """Enhanced audio stopping logic"""
        interruption = self.detect_interruption(text, language)
        should_stop = interruption in [InterruptionType.STOP, InterruptionType.SKIP]
        
        if should_stop:
            logger.info(f"🔇 Audio should be stopped for: {interruption.value}")
        
        return should_stop
    
    def should_skip_question(self, text: str, language: Language = Language.ENGLISH) -> bool:
        """Check if text contains command to skip current question"""
        interruption = self.detect_interruption(text, language)
        should_skip = interruption == InterruptionType.SKIP
        
        if should_skip:
            logger.info(f"⏭️ Question should be skipped")
        
        return should_skip
    
    def should_continue_audio(self, text: str, language: Language = Language.ENGLISH) -> bool:
        """Check if text contains command to continue/resume audio"""
        interruption = self.detect_interruption(text, language)
        should_continue = interruption == InterruptionType.CONTINUE
        
        if should_continue:
            logger.info(f"▶️ Audio should continue")
        
        return should_continue
    
    def get_interruption_response(self, interruption_type: InterruptionType, language: Language) -> str:
        """Get appropriate response for interruption type"""
        responses = {
            Language.ENGLISH: {
                InterruptionType.STOP: "I've stopped. What would you like to do?",
                InterruptionType.SKIP: "Skipping to the next question.",
                InterruptionType.CONTINUE: "Continuing where we left off."
            },
            Language.GUJARATI: {
                InterruptionType.STOP: "હું રોકાઈ ગયો છું. તમે શું કરવા માંગો છો?",
                InterruptionType.SKIP: "આગલા પ્રશ્ન પર જઈ રહ્યો છું.",
                InterruptionType.CONTINUE: "જ્યાં છોડ્યું હતું ત્યાંથી ચાલુ કરું છું."
            }
        }
        
        return responses.get(language, responses[Language.ENGLISH]).get(
            interruption_type, 
            "I understand." if language == Language.ENGLISH else "હું સમજી ગયો."
        )
    
    def get_help_text(self, language: Language = Language.ENGLISH) -> str:
        """Get comprehensive help text for interruption commands"""
        if language == Language.GUJARATI:
            return (
                "તમે આ અવાજ આદેશોનો ઉપયોગ કરી શકો છો:\n\n"
                "🛑 રોકવા માટે:\n"
                "• 'બંધ કરો', 'રોકો', 'થોભો', 'રાહ જુઓ'\n"
                "• 'બસ કરો', 'હવે બંધ કરો'\n\n"
                "⏭️ છોડવા માટે:\n"
                "• 'છોડો', 'આગળ વધો', 'આગળનો પ્રશ્ન'\n"
                "• 'ચાલો આગળ', 'આગળ કરો'\n\n"
                "▶️ ચાલુ કરવા માટે:\n"
                "• 'ચાલુ રાખો', 'આગળ વધો'\n"
                "• 'બોલવાનું ચાલુ રાખો'"
            )
        else:
            return (
                "You can use these voice commands:\n\n"
                "🛑 To stop:\n"
                "• 'stop', 'pause', 'wait', 'hold on'\n"
                "• 'that's enough', 'stop talking'\n\n"
                "⏭️ To skip:\n"
                "• 'skip', 'next', 'move on'\n"
                "• 'skip this', 'next question'\n\n"
                "▶️ To continue:\n"
                "• 'continue', 'go ahead', 'keep going'\n"
                "• 'please continue', 'resume'"
            )
    
    def get_interruption_commands_list(self, language: Language = Language.ENGLISH) -> Dict[str, List[str]]:
        """Get organized list of interruption commands"""
        commands = {}
        if language in self.interruption_commands:
            for interrupt_type, phrases in self.interruption_commands[language].items():
                commands[interrupt_type.value] = phrases[:5]  # Return top 5 for each type
        return commands

# Global enhanced voice interruption handler instance
voice_interruption_handler = VoiceInterruptionHandler()