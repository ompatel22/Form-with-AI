import React from 'react';

const LanguageSwitcher = ({ currentLanguage, onLanguageChange, translations }) => {
  const handleToggle = () => {
    const newLanguage = currentLanguage === 'en' ? 'gu' : 'en';
    onLanguageChange(newLanguage);
  };

  const buttonText = currentLanguage === 'en' 
    ? 'ગુજરાતી' // "Gujarati" in Gujarati
    : 'English';

  return (
    <div className="flex items-center gap-2">
      <span className="text-sm text-gray-300">
        {translations?.language_switch || 'Language:'}
      </span>
      <button
        onClick={handleToggle}
        className="px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-500 transition-colors shadow-md text-sm font-medium"
        title={translations?.language_switch || 'Switch Language'}
      >
        {buttonText}
      </button>
      <div className="flex items-center text-xs text-gray-400">
        <div className={`w-2 h-2 rounded-full mr-1 ${currentLanguage === 'en' ? 'bg-green-400' : 'bg-gray-400'}`}></div>
        <span className="mr-2">EN</span>
        <div className={`w-2 h-2 rounded-full mr-1 ${currentLanguage === 'gu' ? 'bg-green-400' : 'bg-gray-400'}`}></div>
        <span>ગુ</span>
      </div>
    </div>
  );
};

export default LanguageSwitcher;