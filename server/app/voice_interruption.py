"""
Voice Interruption Handler
Manages voice commands to interrupt AI speech
"""
import re
import logging
from typing import Dict, List, Optional, Set
from enum import Enum
from .language_support import Language, language_support

logger = logging.getLogger(__name__)

class InterruptionType(Enum):
    STOP = "stop"
    PAUSE = "pause"
    CONTINUE = "continue"
    SKIP = "skip"

class VoiceInterruptionHandler:
    """Handles voice commands for interrupting AI speech"""
    
    def __init__(self):
        # Interruption commands in both languages
        self.interruption_commands = {
            Language.ENGLISH: {
                InterruptionType.STOP: [
                    "stop", "pause", "wait", "hold", "hold on", "wait a minute",
                    "stop talking", "pause please", "hold please", "one moment",
                    "wait wait", "stop stop", "pause pause"
                ],
                InterruptionType.SKIP: [
                    "skip", "next", "skip this", "move on", "continue",
                    "skip audio", "next question", "go ahead", "proceed"
                ],
                InterruptionType.CONTINUE: [
                    "continue", "go on", "keep going", "resume", "proceed",
                    "carry on", "go ahead", "keep talking"
                ]
            },
            Language.GUJARATI: {
                InterruptionType.STOP: [
                    "બંધ કરો", "રોકો", "થોભો", "રાહ", "રાહ જુઓ", "એક મિનિટ",
                    "બોલવાનું બંધ કરો", "કૃપા કરીને રોકો", "થોભો પ્લીઝ", "એક ક્ષણ",
                    "રાહ રાહ", "બંધ બંધ", "રોકો રોકો"
                ],
                InterruptionType.SKIP: [
                    "છોડો", "આગળ", "આ છોડો", "આગળ વધો", "ચાલુ રાખો",
                    "આવાજ છોડો", "આગળનો પ્રશ્ન", "આગળ વધો", "આગળ બઢો"
                ],
                InterruptionType.CONTINUE: [
                    "ચાલુ રાખો", "આગળ વધો", "ચાલુ કરો", "ફરીથી શરૂ કરો", "આગળ બઢો",
                    "બોલતા રહો", "આગળ જાઓ", "બોલવાનું ચાલુ રાખો"
                ]
            }
        }
        
        # Compiled regex patterns for faster matching
        self._compiled_patterns: Dict[Language, Dict[InterruptionType, List[re.Pattern]]] = {}
        self._compile_patterns()
    
    def _compile_patterns(self):
        """Compile regex patterns for all commands"""
        for language, commands in self.interruption_commands.items():
            self._compiled_patterns[language] = {}
            for interrupt_type, phrases in commands.items():
                patterns = []
                for phrase in phrases:
                    # Create flexible patterns that allow for minor variations
                    escaped_phrase = re.escape(phrase)
                    # Allow for minor spacing and pronunciation variations
                    flexible_pattern = escaped_phrase.replace(r'\ ', r'\s*')
                    patterns.append(re.compile(rf'\b{flexible_pattern}\b', re.IGNORECASE))
                self._compiled_patterns[language][interrupt_type] = patterns
    
    def detect_interruption(self, text: str, language: Language = Language.ENGLISH) -> Optional[InterruptionType]:
        """
        Detect interruption command in text
        Returns InterruptionType if found, None otherwise
        """
        if not text or not text.strip():
            return None
        
        text = text.strip().lower()
        
        # Check patterns for the specified language
        if language in self._compiled_patterns:
            for interrupt_type, patterns in self._compiled_patterns[language].items():
                for pattern in patterns:
                    if pattern.search(text):
                        logger.info(f"Detected {interrupt_type.value} command in {language.value}: '{text}'")
                        return interrupt_type
        
        # Also check the other language as fallback
        other_language = Language.GUJARATI if language == Language.ENGLISH else Language.ENGLISH
        if other_language in self._compiled_patterns:
            for interrupt_type, patterns in self._compiled_patterns[other_language].items():
                for pattern in patterns:
                    if pattern.search(text):
                        logger.info(f"Detected {interrupt_type.value} command in {other_language.value}: '{text}'")
                        return interrupt_type
        
        return None
    
    def is_interruption_command(self, text: str, language: Language = Language.ENGLISH) -> bool:
        """Check if text contains any interruption command"""
        return self.detect_interruption(text, language) is not None
    
    def get_interruption_commands_list(self, language: Language = Language.ENGLISH) -> List[str]:
        """Get list of all interruption commands for a language"""
        commands = []
        if language in self.interruption_commands:
            for interrupt_type, phrases in self.interruption_commands[language].items():
                commands.extend(phrases)
        return commands
    
    def get_help_text(self, language: Language = Language.ENGLISH) -> str:
        """Get help text explaining available interruption commands"""
        if language == Language.GUJARATI:
            return (
                "તમે આ અવાજ આદેશોનો ઉપયોગ કરી શકો છો:\n"
                "• 'બંધ કરો' અથવા 'રોકો' - AI ને બોલવાનું બંધ કરવા\n"
                "• 'છોડો' અથવા 'આગળ' - વર્તમાન પ્રશ્ન છોડવા\n"
                "• 'ચાલુ રાખો' - AI ને ફરીથી બોલવાનું શરૂ કરવા"
            )
        else:
            return (
                "You can use these voice commands:\n"
                "• 'stop' or 'pause' - to stop AI from speaking\n"
                "• 'skip' or 'next' - to skip current question\n"
                "• 'continue' - to resume AI speaking"
            )
    
    def should_stop_audio(self, text: str, language: Language = Language.ENGLISH) -> bool:
        """Check if text contains command to stop audio"""
        interruption = self.detect_interruption(text, language)
        return interruption in [InterruptionType.STOP, InterruptionType.SKIP]
    
    def should_skip_question(self, text: str, language: Language = Language.ENGLISH) -> bool:
        """Check if text contains command to skip current question"""
        interruption = self.detect_interruption(text, language)
        return interruption == InterruptionType.SKIP
    
    def should_continue_audio(self, text: str, language: Language = Language.ENGLISH) -> bool:
        """Check if text contains command to continue/resume audio"""
        interruption = self.detect_interruption(text, language)
        return interruption == InterruptionType.CONTINUE

# Global voice interruption handler instance
voice_interruption_handler = VoiceInterruptionHandler()