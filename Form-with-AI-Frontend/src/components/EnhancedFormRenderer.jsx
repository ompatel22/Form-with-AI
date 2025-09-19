import React from "react";

const EnhancedFormRenderer = ({ 
  formSchema, 
  formData, 
  onChange, 
  onSubmit,
  currentLanguage,
  translations 
}) => {
  const isGujarati = currentLanguage === 'gu';

  const handleFieldChange = (fieldName, value) => {
    onChange(fieldName, value);
  };

  const getFieldLabel = (field) => {
    // For now, return the original label
    // In a full implementation, you'd have field-specific translations
    return field.label;
  };

  const getFieldPlaceholder = (field) => {
    if (isGujarati) {
      const gujaratiPlaceholders = {
        'full_name': 'તમારું પૂરું નામ દાખલ કરો',
        'email': 'તમારું ઈમેઇલ એડ્રેસ',
        'phone': 'તમારો ફોન નમ્બર',
        'dob': 'જન્મતારીખ (દિવસ/મહિનો/વર્ષ)'
      };
      return gujaratiPlaceholders[field.name] || field.label;
    }
    
    const englishPlaceholders = {
      'full_name': 'Enter your full name',
      'email': 'Enter your email address',
      'phone': 'Enter your phone number',
      'dob': 'Enter date of birth'
    };
    return englishPlaceholders[field.name] || `Enter ${field.label.toLowerCase()}`;
  };

  const renderField = (field) => {
    const fieldValue = formData[field.name] || '';
    const isRequired = field.validation?.required;

    switch (field.type) {
      case 'short_answer':
      case 'paragraph':
        return (
          <div key={field.name} className="mb-6">
            <label 
              className="block text-sm font-medium text-gray-200 mb-2"
              style={{ fontFamily: isGujarati ? 'Noto Sans Gujarati, sans-serif' : 'inherit' }}
            >
              {getFieldLabel(field)} {isRequired && <span className="text-red-400">*</span>}
            </label>
            {field.type === 'paragraph' ? (
              <textarea
                value={fieldValue}
                onChange={(e) => handleFieldChange(field.name, e.target.value)}
                placeholder={getFieldPlaceholder(field)}
                rows={4}
                className="w-full p-3 bg-gray-700 text-white border border-gray-600 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent placeholder-gray-400"
                style={{ fontFamily: isGujarati ? 'Noto Sans Gujarati, sans-serif' : 'inherit' }}
              />
            ) : (
              <input
                type="text"
                value={fieldValue}
                onChange={(e) => handleFieldChange(field.name, e.target.value)}
                placeholder={getFieldPlaceholder(field)}
                className="w-full p-3 bg-gray-700 text-white border border-gray-600 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent placeholder-gray-400"
                style={{ fontFamily: isGujarati ? 'Noto Sans Gujarati, sans-serif' : 'inherit' }}
              />
            )}
          </div>
        );

      case 'email':
        return (
          <div key={field.name} className="mb-6">
            <label 
              className="block text-sm font-medium text-gray-200 mb-2"
              style={{ fontFamily: isGujarati ? 'Noto Sans Gujarati, sans-serif' : 'inherit' }}
            >
              {getFieldLabel(field)} {isRequired && <span className="text-red-400">*</span>}
            </label>
            <input
              type="email"
              value={fieldValue}
              onChange={(e) => handleFieldChange(field.name, e.target.value)}
              placeholder={getFieldPlaceholder(field)}
              className="w-full p-3 bg-gray-700 text-white border border-gray-600 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent placeholder-gray-400"
            />
          </div>
        );

      case 'phone':
        return (
          <div key={field.name} className="mb-6">
            <label 
              className="block text-sm font-medium text-gray-200 mb-2"
              style={{ fontFamily: isGujarati ? 'Noto Sans Gujarati, sans-serif' : 'inherit' }}
            >
              {getFieldLabel(field)} {isRequired && <span className="text-red-400">*</span>}
            </label>
            <input
              type="tel"
              value={fieldValue}
              onChange={(e) => handleFieldChange(field.name, e.target.value)}
              placeholder={getFieldPlaceholder(field)}
              className="w-full p-3 bg-gray-700 text-white border border-gray-600 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent placeholder-gray-400"
            />
          </div>
        );

      case 'date':
        return (
          <div key={field.name} className="mb-6">
            <label 
              className="block text-sm font-medium text-gray-200 mb-2"
              style={{ fontFamily: isGujarati ? 'Noto Sans Gujarati, sans-serif' : 'inherit' }}
            >
              {getFieldLabel(field)} {isRequired && <span className="text-red-400">*</span>}
            </label>
            <input
              type="date"
              value={fieldValue}
              onChange={(e) => handleFieldChange(field.name, e.target.value)}
              className="w-full p-3 bg-gray-700 text-white border border-gray-600 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent"
            />
            <p className="text-xs text-gray-400 mt-1">
              {isGujarati 
                ? "અથવા બોલીને દાખલ કરો: '22મી ડિસેમ્બર 2004'" 
                : "Or speak naturally: '22nd December 2004'"}
            </p>
          </div>
        );

      case 'multiple_choice':
      case 'dropdown':
        return (
          <div key={field.name} className="mb-6">
            <label 
              className="block text-sm font-medium text-gray-200 mb-2"
              style={{ fontFamily: isGujarati ? 'Noto Sans Gujarati, sans-serif' : 'inherit' }}
            >
              {getFieldLabel(field)} {isRequired && <span className="text-red-400">*</span>}
            </label>
            {field.type === 'dropdown' ? (
              <select
                value={fieldValue}
                onChange={(e) => handleFieldChange(field.name, e.target.value)}
                className="w-full p-3 bg-gray-700 text-white border border-gray-600 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent"
                style={{ fontFamily: isGujarati ? 'Noto Sans Gujarati, sans-serif' : 'inherit' }}
              >
                <option value="">
                  {isGujarati ? 'પસંદ કરો...' : 'Select...'}
                </option>
                {field.options?.map((option, index) => (
                  <option key={index} value={option}>
                    {option}
                  </option>
                ))}
              </select>
            ) : (
              <div className="space-y-2">
                {field.options?.map((option, index) => (
                  <label key={index} className="flex items-center space-x-3 cursor-pointer">
                    <input
                      type="radio"
                      name={field.name}
                      value={option}
                      checked={fieldValue === option}
                      onChange={(e) => handleFieldChange(field.name, e.target.value)}
                      className="w-4 h-4 text-blue-600 bg-gray-700 border-gray-600 focus:ring-blue-500"
                    />
                    <span 
                      className="text-gray-200"
                      style={{ fontFamily: isGujarati ? 'Noto Sans Gujarati, sans-serif' : 'inherit' }}
                    >
                      {option}
                    </span>
                  </label>
                ))}
              </div>
            )}
            <p className="text-xs text-gray-400 mt-1">
              {isGujarati 
                ? "કેવળ ઉપલબ્ધ વિકલ્પોમાંથી પસંદ કરો" 
                : "Please choose only from available options"}
            </p>
          </div>
        );

      case 'checkboxes':
        return (
          <div key={field.name} className="mb-6">
            <label 
              className="block text-sm font-medium text-gray-200 mb-2"
              style={{ fontFamily: isGujarati ? 'Noto Sans Gujarati, sans-serif' : 'inherit' }}
            >
              {getFieldLabel(field)} {isRequired && <span className="text-red-400">*</span>}
            </label>
            <div className="space-y-2">
              {field.options?.map((option, index) => {
                // FIXED: Handle both comma-separated string and array formats
                let selectedOptions = [];
                if (typeof fieldValue === 'string' && fieldValue) {
                  selectedOptions = fieldValue.split(',').map(s => s.trim());
                } else if (Array.isArray(fieldValue)) {
                  selectedOptions = fieldValue;
                }
                
                const isChecked = selectedOptions.includes(option);
                
                return (
                  <label key={index} className="flex items-center space-x-3 cursor-pointer">
                    <input
                      type="checkbox"
                      checked={isChecked}
                      onChange={(e) => {
                        let newSelected = [...selectedOptions];
                        if (e.target.checked) {
                          if (!newSelected.includes(option)) {
                            newSelected.push(option);
                          }
                        } else {
                          newSelected = newSelected.filter(item => item !== option);
                        }
                        // Always store as comma-separated string for consistency with backend
                        handleFieldChange(field.name, newSelected.join(', '));
                      }}
                      className="w-4 h-4 text-blue-600 bg-gray-700 border-gray-600 rounded focus:ring-blue-500"
                    />
                    <span 
                      className="text-gray-200"
                      style={{ fontFamily: isGujarati ? 'Noto Sans Gujarati, sans-serif' : 'inherit' }}
                    >
                      {option}
                    </span>
                  </label>
                );
              })}
            </div>
            <p className="text-xs text-gray-400 mt-1">
              {isGujarati 
                ? "એક કરતાં વધુ વિકલ્પ પસંદ કરી શકાય" 
                : "Multiple selections allowed"}
            </p>

          </div>
        );

      case 'number':
        return (
          <div key={field.name} className="mb-6">
            <label 
              className="block text-sm font-medium text-gray-200 mb-2"
              style={{ fontFamily: isGujarati ? 'Noto Sans Gujarati, sans-serif' : 'inherit' }}
            >
              {getFieldLabel(field)} {isRequired && <span className="text-red-400">*</span>}
            </label>
            <input
              type="number"
              value={fieldValue}
              onChange={(e) => handleFieldChange(field.name, e.target.value)}
              placeholder={getFieldPlaceholder(field)}
              className="w-full p-3 bg-gray-700 text-white border border-gray-600 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent placeholder-gray-400"
            />
          </div>
        );

      case 'linear_scale':
        const scaleMin = field.scale_min || 1;
        const scaleMax = field.scale_max || 5;
        const scaleOptions = Array.from(
          { length: scaleMax - scaleMin + 1 }, 
          (_, i) => scaleMin + i
        );

        return (
          <div key={field.name} className="mb-6">
            <label 
              className="block text-sm font-medium text-gray-200 mb-2"
              style={{ fontFamily: isGujarati ? 'Noto Sans Gujarati, sans-serif' : 'inherit' }}
            >
              {getFieldLabel(field)} {isRequired && <span className="text-red-400">*</span>}
            </label>
            <div className="flex items-center justify-between">
              <span className="text-sm text-gray-400">
                {field.scale_min_label || scaleMin}
              </span>
              <div className="flex space-x-2">
                {scaleOptions.map(num => (
                  <label key={num} className="cursor-pointer">
                    <input
                      type="radio"
                      name={field.name}
                      value={num}
                      checked={fieldValue == num}
                      onChange={(e) => handleFieldChange(field.name, e.target.value)}
                      className="sr-only"
                    />
                    <div className={`w-10 h-10 rounded-full border-2 flex items-center justify-center text-sm font-medium transition-colors ${
                      fieldValue == num
                        ? 'bg-blue-600 border-blue-600 text-white'
                        : 'bg-gray-700 border-gray-600 text-gray-300 hover:border-gray-500'
                    }`}>
                      {num}
                    </div>
                  </label>
                ))}
              </div>
              <span className="text-sm text-gray-400">
                {field.scale_max_label || scaleMax}
              </span>
            </div>
          </div>
        );

      default:
        return (
          <div key={field.name} className="mb-6">
            <label 
              className="block text-sm font-medium text-gray-200 mb-2"
              style={{ fontFamily: isGujarati ? 'Noto Sans Gujarati, sans-serif' : 'inherit' }}
            >
              {getFieldLabel(field)} {isRequired && <span className="text-red-400">*</span>}
            </label>
            <input
              type="text"
              value={fieldValue}
              onChange={(e) => handleFieldChange(field.name, e.target.value)}
              placeholder={getFieldPlaceholder(field)}
              className="w-full p-3 bg-gray-700 text-white border border-gray-600 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent placeholder-gray-400"
              style={{ fontFamily: isGujarati ? 'Noto Sans Gujarati, sans-serif' : 'inherit' }}
            />
          </div>
        );
    }
  };

  return (
    <div className="flex-1 bg-gradient-to-b from-gray-700 to-gray-800 p-8 rounded-l-2xl border-r border-gray-700">
      <div className="max-w-2xl mx-auto">
        <div className="mb-8">
          <h2 
            className="text-2xl font-bold text-white mb-3"
            style={{ fontFamily: isGujarati ? 'Noto Sans Gujarati, sans-serif' : 'inherit' }}
          >
            {translations?.form_title || "Form"}: {formSchema.title}
          </h2>
          {formSchema.description && (
            <p 
              className="text-gray-300 leading-relaxed"
              style={{ fontFamily: isGujarati ? 'Noto Sans Gujarati, sans-serif' : 'inherit' }}
            >
              {formSchema.description}
            </p>
          )}
        </div>

        <form onSubmit={onSubmit} className="space-y-6">
          {formSchema.fields
            ?.sort((a, b) => (a.order || 0) - (b.order || 0))
            ?.map(renderField)}

          <div className="flex gap-4 pt-6 border-t border-gray-600">
            <button
              type="submit"
              className="flex-1 py-3 px-6 bg-green-600 text-white rounded-xl hover:bg-green-500 transition-colors font-medium shadow-lg hover:shadow-xl"
              style={{ fontFamily: isGujarati ? 'Noto Sans Gujarati, sans-serif' : 'inherit' }}
            >
              {translations?.submit || "Submit"} 📤
            </button>
          </div>
        </form>

        {/* Voice instructions */}
        <div className="mt-6 p-4 bg-blue-500/10 border border-blue-500/20 rounded-lg">
          <p 
            className="text-blue-300 text-sm"
            style={{ fontFamily: isGujarati ? 'Noto Sans Gujarati, sans-serif' : 'inherit' }}
          >
            💡 {isGujarati 
              ? "તમે ફોર્મ ભરવા માટે અવાજનો પણ ઉપયોગ કરી શકો છો! AI સાથે વાત કરો અને તે આપમેળે ફીલ્ડ ભરશે."
              : "You can also use voice to fill this form! Talk to the AI and it will automatically fill the fields."}
          </p>
        </div>
      </div>
    </div>
  );
};

export default EnhancedFormRenderer;