import React, { useState, useEffect } from 'react';

const DynamicFormRenderer = ({ formSchema, formData, onChange, onSubmit }) => {
  const [visibleFields, setVisibleFields] = useState(new Set());

  // Calculate which conditional fields should be visible
  useEffect(() => {
    const newVisibleFields = new Set();
    
    if (formSchema && formSchema.fields) {
      formSchema.fields.forEach(field => {
        // Add main fields
        newVisibleFields.add(field.name);
        
        // Check conditional fields
        if (field.conditional_fields && formData[field.name]) {
          const selectedValue = formData[field.name];
          const conditionalFieldsForValue = field.conditional_fields[selectedValue];
          
          if (conditionalFieldsForValue) {
            conditionalFieldsForValue.forEach(conditionalField => {
              newVisibleFields.add(conditionalField.name);
            });
          }
        }
      });
    }
    
    setVisibleFields(newVisibleFields);
  }, [formSchema, formData]);

  if (!formSchema || !formSchema.fields) {
    return (
      <div className="flex-1 bg-gradient-to-b from-gray-700 to-gray-800 p-8 rounded-l-2xl border-r border-gray-700">
        <div className="flex items-center justify-center h-full">
          <div className="text-center">
            <div className="text-6xl mb-4">📋</div>
            <p className="text-gray-300 text-xl">No form selected</p>
          </div>
        </div>
      </div>
    );
  }

  const handleFieldChange = (fieldName, value) => {
    onChange(fieldName, value);
  };

  const renderField = (field) => {
    const value = formData[field.name] || '';
    const isRequired = field.validation?.required;

    // Helper to get label with required indicator
    const getFieldLabel = () => (
      <label className="block text-sm font-medium text-gray-200 mb-3">
        {field.label} {isRequired && <span className="text-red-400">*</span>}
        {field.description && (
          <span className="block text-xs text-gray-400 font-normal mt-1">
            {field.description}
          </span>
        )}
      </label>
    );

    switch (field.type) {
      case 'short_answer':
        return (
          <div key={field.name} className="mb-6">
            {getFieldLabel()}
            <input
              type="text"
              value={value}
              onChange={(e) => handleFieldChange(field.name, e.target.value)}
              placeholder={field.placeholder || `Enter ${field.label.toLowerCase()}`}
              className="w-full p-4 bg-gray-700 text-white border border-gray-600 rounded-xl focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent placeholder-gray-400 transition-all"
              required={isRequired}
            />
          </div>
        );

      case 'paragraph':
        return (
          <div key={field.name} className="mb-6">
            {getFieldLabel()}
            <textarea
              value={value}
              onChange={(e) => handleFieldChange(field.name, e.target.value)}
              placeholder={field.placeholder || `Enter ${field.label.toLowerCase()}`}
              rows={4}
              className="w-full p-4 bg-gray-700 text-white border border-gray-600 rounded-xl focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent placeholder-gray-400 resize-none transition-all"
              required={isRequired}
            />
          </div>
        );

      case 'email':
        return (
          <div key={field.name} className="mb-6">
            {getFieldLabel()}
            <input
              type="email"
              value={value}
              onChange={(e) => handleFieldChange(field.name, e.target.value)}
              placeholder={field.placeholder || "Enter your email address"}
              className="w-full p-4 bg-gray-700 text-white border border-gray-600 rounded-xl focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent placeholder-gray-400 transition-all"
              required={isRequired}
            />
          </div>
        );

      case 'phone':
        return (
          <div key={field.name} className="mb-6">
            {getFieldLabel()}
            <input
              type="tel"
              value={value}
              onChange={(e) => handleFieldChange(field.name, e.target.value)}
              placeholder={field.placeholder || "Enter your phone number"}
              className="w-full p-4 bg-gray-700 text-white border border-gray-600 rounded-xl focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent placeholder-gray-400 transition-all"
              required={isRequired}
            />
          </div>
        );

      case 'number':
        return (
          <div key={field.name} className="mb-6">
            {getFieldLabel()}
            <input
              type="number"
              value={value}
              onChange={(e) => handleFieldChange(field.name, e.target.value)}
              placeholder={field.placeholder || "Enter a number"}
              min={field.validation?.min_value}
              max={field.validation?.max_value}
              className="w-full p-4 bg-gray-700 text-white border border-gray-600 rounded-xl focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent placeholder-gray-400 transition-all"
              required={isRequired}
            />
          </div>
        );

case 'date':
      // Convert MM/DD/YYYY to YYYY-MM-DD for date input
      const displayValue = value
        ? (() => {
            const [month, day, year] = value.split('/');
            return `${year}-${month.padStart(2, '0')}-${day.padStart(2, '0')}`;
          })()
        : '';
      return (
        <input
          type="date"
          name={field.name}
          value={displayValue}
          onChange={(e) => {
            // Convert YYYY-MM-DD back to MM/DD/YYYY for formData
            const dateValue = e.target.value;
            if (dateValue) {
              const [year, month, day] = dateValue.split('-');
              handleFieldChange(field.name, `${month}/${day}/${year}`);
            } else {
              handleFieldChange(field.name, '');
            }
          }}
          required={field.validation?.required}
          className="w-full p-3 border border-gray-600 bg-gray-700 text-white placeholder-gray-400 rounded-lg focus:ring-2 focus:ring-blue-400 focus:border-blue-400 transition-shadow shadow-sm hover:shadow-md"
        />
      );
       
      case 'time':
        return (
          <div key={field.name} className="mb-6">
            {getFieldLabel()}
            <input
              type="time"
              value={value}
              onChange={(e) => handleFieldChange(field.name, e.target.value)}
              className="w-full p-4 bg-gray-700 text-white border border-gray-600 rounded-xl focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent transition-all"
              required={isRequired}
            />
          </div>
        );

      case 'url':
        return (
          <div key={field.name} className="mb-6">
            {getFieldLabel()}
            <input
              type="url"
              value={value}
              onChange={(e) => handleFieldChange(field.name, e.target.value)}
              placeholder={field.placeholder || "Enter a URL"}
              className="w-full p-4 bg-gray-700 text-white border border-gray-600 rounded-xl focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent placeholder-gray-400 transition-all"
              required={isRequired}
            />
          </div>
        );

      case 'password':
        return (
          <div key={field.name} className="mb-6">
            {getFieldLabel()}
            <input
              type="password"
              value={value}
              onChange={(e) => handleFieldChange(field.name, e.target.value)}
              placeholder={field.placeholder || "Enter password"}
              className="w-full p-4 bg-gray-700 text-white border border-gray-600 rounded-xl focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent placeholder-gray-400 transition-all"
              required={isRequired}
            />
          </div>
        );

      case 'dropdown':
        return (
          <div key={field.name} className="mb-6">
            {getFieldLabel()}
            <select
              value={value}
              onChange={(e) => handleFieldChange(field.name, e.target.value)}
              className="w-full p-4 bg-gray-700 text-white border border-gray-600 rounded-xl focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent transition-all"
              required={isRequired}
            >
              <option value="">Select an option...</option>
              {field.options?.map((option, index) => (
                <option key={index} value={option}>
                  {option}
                </option>
              ))}
            </select>
            <p className="text-xs text-gray-400 mt-2">
              Or speak your choice: just say one of the available options
            </p>
          </div>
        );

      case 'multiple_choice':
        return (
          <div key={field.name} className="mb-6">
            {getFieldLabel()}
            <div className="space-y-3">
              {field.options?.map((option, index) => (
                <label key={index} className="flex items-center cursor-pointer group">
                  <input
                    type="radio"
                    name={field.name}
                    value={option}
                    checked={value === option}
                    onChange={(e) => handleFieldChange(field.name, e.target.value)}
                    className="mr-3 text-blue-500 bg-gray-700 border-gray-600 focus:ring-blue-500 focus:ring-2"
                    required={isRequired}
                  />
                  <span className="text-gray-200 group-hover:text-white transition-colors">{option}</span>
                </label>
              ))}
            </div>
            <p className="text-xs text-gray-400 mt-2">
              Or speak your choice: just say one of the available options
            </p>
          </div>
        );

      case 'checkboxes':
        return (
          <div key={field.name} className="mb-6">
            {getFieldLabel()}
            <div className="space-y-3">
              {field.options?.map((option, index) => {
                // FIXED: Handle both comma-separated string and array formats consistently
                let checkedValues = [];
                if (typeof value === 'string' && value) {
                  checkedValues = value.split(',').map(s => s.trim()).filter(s => s);
                } else if (Array.isArray(value)) {
                  checkedValues = value;
                }
                
                return (
                  <label key={index} className="flex items-center cursor-pointer group">
                    <input
                      type="checkbox"
                      name={`${field.name}[]`}
                      value={option}
                      checked={checkedValues.includes(option)}
                      onChange={(e) => {
                        let newValues = [...checkedValues];
                        if (e.target.checked) {
                          if (!newValues.includes(option)) {
                            newValues.push(option);
                          }
                        } else {
                          newValues = newValues.filter(v => v !== option);
                        }
                        // Always store as comma-separated string for consistency with backend
                        handleFieldChange(field.name, newValues.join(', '));
                      }}
                      className="mr-3 text-blue-500 bg-gray-700 border-gray-600 focus:ring-blue-500 focus:ring-2"
                    />
                    <span className="text-gray-200 group-hover:text-white transition-colors">{option}</span>
                  </label>
                );
              })}
            </div>
            <p className="text-xs text-gray-400 mt-2">
              Multiple selections allowed. Or speak: "fever and headache" or "fever, cough, nausea"
            </p>

          </div>
        );

      case 'linear_scale':
        const scaleMin = field.scale_min || 1;
        const scaleMax = field.scale_max || 5;
        const scaleOptions = [];
        for (let i = scaleMin; i <= scaleMax; i++) {
          scaleOptions.push(i);
        }
        return (
          <div key={field.name} className="mb-6">
            {getFieldLabel()}
            <div className="space-y-4">
              <div className="flex items-center justify-between text-sm text-gray-400">
                <span>{field.scale_min_label || scaleMin}</span>
                <span>{field.scale_max_label || scaleMax}</span>
              </div>
              <div className="flex items-center justify-between">
                {scaleOptions.map((option) => (
                  <label key={option} className="flex flex-col items-center cursor-pointer group">
                    <input
                      type="radio"
                      name={field.name}
                      value={option}
                      checked={value == option}
                      onChange={(e) => handleFieldChange(field.name, e.target.value)}
                      className="sr-only"
                      required={isRequired}
                    />
                    <div className={`w-12 h-12 rounded-full border-2 flex items-center justify-center text-lg font-medium transition-all ${
                      value == option
                        ? 'bg-blue-600 border-blue-600 text-white scale-110'
                        : 'bg-gray-700 border-gray-600 text-gray-300 group-hover:border-gray-500 group-hover:scale-105'
                    }`}>
                      {option}
                    </div>
                  </label>
                ))}
              </div>
            </div>
            <p className="text-xs text-gray-400 mt-2">
              Or speak: "I rate it {scaleMin}" to "I rate it {scaleMax}"
            </p>
          </div>
        );

      default:
        return (
          <div key={field.name} className="mb-6">
            {getFieldLabel()}
            <input
              type="text"
              value={value}
              onChange={(e) => handleFieldChange(field.name, e.target.value)}
              placeholder={field.placeholder || `Enter ${field.label.toLowerCase()}`}
              className="w-full p-4 bg-gray-700 text-white border border-gray-600 rounded-xl focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent placeholder-gray-400 transition-all"
              required={isRequired}
            />
          </div>
        );
    }
  };

  // Get all fields including conditional ones (from first file logic)
  const getAllFields = () => {
    const allFields = [];
    
    // Sort fields by order first
    const sortedFields = [...formSchema.fields].sort((a, b) => (a.order || 0) - (b.order || 0));
    
    sortedFields.forEach(field => {
      // Add main field
      allFields.push(field);
      
      // Add conditional fields if they should be visible
      if (field.conditional_fields && formData[field.name]) {
        const selectedValue = formData[field.name];
        const conditionalFieldsForValue = field.conditional_fields[selectedValue];
        
        if (conditionalFieldsForValue) {
          conditionalFieldsForValue.forEach(conditionalField => {
            allFields.push({
              ...conditionalField,
              isConditional: true,
              parentField: field.name,
              parentValue: selectedValue
            });
          });
        }
      }
    });
    
    return allFields;
  };

  return (
    <div className="flex-1 bg-gradient-to-b from-gray-700 to-gray-800 p-8 rounded-l-2xl border-r border-gray-700">
      <div className="max-w-2xl mx-auto">
        <div className="mb-8">
          <h2 className="text-3xl font-bold text-white mb-4 tracking-tight">
            {formSchema.title}
          </h2>
          {formSchema.description && (
            <p className="text-gray-300 text-lg leading-relaxed">
              {formSchema.description}
            </p>
          )}
        </div>

        <form onSubmit={onSubmit} className="space-y-8">
          {getAllFields().map((field) => (
            <div 
              key={field.id || field.name}
              className={field.isConditional ? 'ml-6 pl-4 border-l-2 border-blue-500/30 bg-gray-700/30 rounded-r-lg p-4' : ''}
            >
              {field.isConditional && (
                <div className="text-xs text-blue-400 mb-2 font-medium">
                  ↳ Shown because "{field.parentValue}" was selected
                </div>
              )}
              {renderField(field)}
            </div>
          ))}

          <div className="flex gap-4 pt-8 border-t border-gray-600">
            <button
              type="submit"
              className="flex-1 py-4 px-8 bg-gradient-to-r from-green-600 to-green-500 text-white rounded-xl hover:from-green-500 hover:to-green-400 transition-all duration-200 font-semibold text-lg shadow-lg hover:shadow-xl transform hover:scale-105"
            >
              Submit Form 🚀
            </button>
          </div>
        </form>

        {/* Voice instructions
        <div className="mt-8 p-6 bg-blue-500/10 border border-blue-500/20 rounded-xl">
          <h3 className="text-blue-300 font-semibold mb-2 flex items-center">
            🎙️ Voice Instructions
          </h3>
          <p className="text-blue-300 text-sm leading-relaxed">
            You can fill this form using voice! Just speak naturally to the AI assistant. 
            For multiple selections (checkboxes), say something like "fever and headache" or "option 1, option 2".
          </p>
        </div> */}
      </div>
    </div>
  );
};

export default DynamicFormRenderer;