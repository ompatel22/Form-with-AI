import React from 'react';

export default function DynamicFormRenderer({ formSchema, formData, onChange, onSubmit }) {
  if (!formSchema || !formSchema.fields) {
    return (
      <div className="p-6 text-center text-gray-500">
        No form schema provided
      </div>
    );
  }

  const handleFieldChange = (fieldName, value) => {
    onChange(fieldName, value);
  };

  const renderField = (field) => {
    const value = formData[field.name] || '';

    switch (field.type) {
      case 'short_answer':
        return (
          <input
            type="text"
            name={field.name}
            value={value}
            onChange={(e) => handleFieldChange(field.name, e.target.value)}
            placeholder={field.placeholder || `Enter ${field.label.toLowerCase()}...`}
            required={field.validation?.required}
            className="w-full p-3 border border-gray-600 bg-gray-700 text-white placeholder-gray-400 rounded-lg focus:ring-2 focus:ring-blue-400 focus:border-blue-400 transition-shadow shadow-sm hover:shadow-md"
          />
        );

      case 'paragraph':
        return (
          <textarea
            name={field.name}
            value={value}
            onChange={(e) => handleFieldChange(field.name, e.target.value)}
            placeholder={field.placeholder || `Enter ${field.label.toLowerCase()}...`}
            required={field.validation?.required}
            rows={4}
            className="w-full p-3 border border-gray-600 bg-gray-700 text-white placeholder-gray-400 rounded-lg focus:ring-2 focus:ring-blue-400 focus:border-blue-400 transition-shadow shadow-sm hover:shadow-md"
          />
        );

      case 'email':
        return (
          <input
            type="email"
            name={field.name}
            value={value}
            onChange={(e) => handleFieldChange(field.name, e.target.value)}
            placeholder={field.placeholder || "Enter email address..."}
            required={field.validation?.required}
            className="w-full p-3 border border-gray-600 bg-gray-700 text-white placeholder-gray-400 rounded-lg focus:ring-2 focus:ring-blue-400 focus:border-blue-400 transition-shadow shadow-sm hover:shadow-md"
          />
        );

      case 'phone':
        return (
          <input
            type="tel"
            name={field.name}
            value={value}
            onChange={(e) => handleFieldChange(field.name, e.target.value)}
            placeholder={field.placeholder || "Enter phone number..."}
            required={field.validation?.required}
            className="w-full p-3 border border-gray-600 bg-gray-700 text-white placeholder-gray-400 rounded-lg focus:ring-2 focus:ring-blue-400 focus:border-blue-400 transition-shadow shadow-sm hover:shadow-md"
          />
        );

      case 'number':
        return (
          <input
            type="number"
            name={field.name}
            value={value}
            onChange={(e) => handleFieldChange(field.name, e.target.value)}
            placeholder={field.placeholder || "Enter number..."}
            required={field.validation?.required}
            min={field.validation?.min_value}
            max={field.validation?.max_value}
            className="w-full p-3 border border-gray-600 bg-gray-700 text-white placeholder-gray-400 rounded-lg focus:ring-2 focus:ring-blue-400 focus:border-blue-400 transition-shadow shadow-sm hover:shadow-md"
          />
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
        return (
          <input
            type="date"
            name={field.name}
            value={value}
            onChange={(e) => handleFieldChange(field.name, e.target.value)}
            required={field.validation?.required}
            className="w-full p-3 border border-gray-600 bg-gray-700 text-white placeholder-gray-400 rounded-lg focus:ring-2 focus:ring-blue-400 focus:border-blue-400 transition-shadow shadow-sm hover:shadow-md"
          />
        );

      case 'time':
        return (
          <input
            type="time"
            name={field.name}
            value={value}
            onChange={(e) => handleFieldChange(field.name, e.target.value)}
            required={field.validation?.required}
            className="w-full p-3 border border-gray-600 bg-gray-700 text-white placeholder-gray-400 rounded-lg focus:ring-2 focus:ring-blue-400 focus:border-blue-400 transition-shadow shadow-sm hover:shadow-md"
          />
        );

      case 'url':
        return (
          <input
            type="url"
            name={field.name}
            value={value}
            onChange={(e) => handleFieldChange(field.name, e.target.value)}
            placeholder={field.placeholder || "https://example.com"}
            required={field.validation?.required}
            className="w-full p-3 border border-gray-600 bg-gray-700 text-white placeholder-gray-400 rounded-lg focus:ring-2 focus:ring-blue-400 focus:border-blue-400 transition-shadow shadow-sm hover:shadow-md"
          />
        );

      case 'dropdown':
        return (
          <select
            name={field.name}
            value={value}
            onChange={(e) => handleFieldChange(field.name, e.target.value)}
            required={field.validation?.required}
            className="w-full p-3 border border-gray-600 bg-gray-700 text-white placeholder-gray-400 rounded-lg focus:ring-2 focus:ring-blue-400 focus:border-blue-400 transition-shadow shadow-sm hover:shadow-md"
          >
            <option value="">Select an option...</option>
            {field.options?.map((option, index) => (
              <option key={index} value={option}>
                {option}
              </option>
            ))}
          </select>
        );

      case 'multiple_choice':
        return (
          <div className="space-y-3">
            {field.options?.map((option, index) => (
              <label key={index} className="flex items-center cursor-pointer group">
                <input
                  type="radio"
                  name={field.name}
                  value={option}
                  checked={value === option}
                  onChange={(e) => handleFieldChange(field.name, e.target.value)}
                  required={field.validation?.required}
                  className="mr-3 text-blue-500 bg-gray-700 border-gray-600 focus:ring-blue-500 focus:ring-2"
                />
                <span className="text-gray-200 group-hover:text-white transition-colors">{option}</span>
              </label>
            ))}
          </div>
        );

      case 'checkboxes':
        const checkedValues = Array.isArray(value) ? value : (value ? [value] : []);
        return (
          <div className="space-y-3">
            {field.options?.map((option, index) => (
              <label key={index} className="flex items-center cursor-pointer group">
                <input
                  type="checkbox"
                  name={`${field.name}[]`}
                  value={option}
                  checked={checkedValues.includes(option)}
                  onChange={(e) => {
                    let newValues = [...checkedValues];
                    if (e.target.checked) {
                      newValues.push(option);
                    } else {
                      newValues = newValues.filter(v => v !== option);
                    }
                    handleFieldChange(field.name, newValues);
                  }}
                  className="mr-3 text-blue-500 bg-gray-700 border-gray-600 focus:ring-blue-500 focus:ring-2"
                />
                <span className="text-gray-200 group-hover:text-white transition-colors">{option}</span>
              </label>
            ))}
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
                    checked={parseInt(value) === option}
                    onChange={(e) => handleFieldChange(field.name, parseInt(e.target.value))}
                    required={field.validation?.required}
                    className="mb-2 text-blue-500 bg-gray-700 border-gray-600 focus:ring-blue-500 focus:ring-2"
                  />
                  <span className="text-sm text-gray-300 group-hover:text-white transition-colors">{option}</span>
                </label>
              ))}
            </div>
          </div>
        );

      case 'password':
        return (
          <div>
            <input
              type="password"
              name={field.name}
              value={value}
              onChange={(e) => handleFieldChange(field.name, e.target.value)}
              placeholder="Enter your password (type manually for security)..."
              required={field.validation?.required}
              className="w-full p-3 border border-gray-600 bg-gray-700 text-white rounded-lg focus:ring-2 focus:ring-blue-400 focus:border-blue-400 transition-shadow shadow-sm hover:shadow-md"
            />
            <p className="text-xs text-yellow-400 mt-1">
              💡 For security, please type your password manually rather than speaking it
            </p>
          </div>
        );

      case 'file_upload':
        return (
          <input
            type="file"
            name={field.name}
            onChange={(e) => {
              const file = e.target.files[0];
              handleFieldChange(field.name, file ? file.name : '');
            }}
            required={field.validation?.required}
            accept={field.allowed_file_types ? field.allowed_file_types.join(',') : undefined}
            className="w-full p-3 border border-gray-600 bg-gray-700 text-white rounded-lg focus:ring-2 focus:ring-blue-400 focus:border-blue-400 transition-shadow shadow-sm hover:shadow-md file:mr-4 file:py-2 file:px-4 file:rounded file:border-0 file:text-sm file:font-semibold file:bg-blue-600/20 file:text-blue-300 hover:file:bg-blue-600/30"
          />
        );

      default:
        return (
          <div className="p-3 bg-gray-700 border border-gray-600 rounded-lg text-gray-300">
            Unsupported field type: {field.type}
          </div>
        );
    }
  };

  // Sort fields by order
  const sortedFields = [...formSchema.fields].sort((a, b) => (a.order || 0) - (b.order || 0));

  return (
    <div className="flex-1 bg-gradient-to-b from-gray-700 to-gray-800 p-10 rounded-l-2xl">
      <div className="mb-8">
        <h2 className="text-2xl font-semibold text-white mb-2">
          {formSchema.title}
        </h2>
        {formSchema.description && (
          <p className="text-gray-300">{formSchema.description}</p>
        )}
      </div>
      
      <form onSubmit={onSubmit} className="space-y-6">
        {sortedFields.map((field) => (
          <div key={field.id || field.name}>
            <label className="block text-sm font-medium text-gray-200 mb-2">
              {field.label}
              {field.validation?.required && (
                <span className="text-red-400 ml-1">*</span>
              )}
              {!field.validation?.required && (
                <span className="text-gray-400 ml-1">(optional)</span>
              )}
            </label>
            
            {field.description && (
              <p className="text-sm text-gray-400 mb-2">{field.description}</p>
            )}
            
            {renderField(field)}
          </div>
        ))}
        
        <button
          type="submit"
          className="w-full bg-blue-600 text-white p-3 rounded-lg hover:bg-blue-500 transition-all duration-300 shadow-md hover:shadow-lg font-medium"
        >
          Submit Form
        </button>
      </form>
    </div>
  );
}