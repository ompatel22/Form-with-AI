import React, { useState, useEffect } from 'react';

const FIELD_TYPES = [
  { value: 'short_answer', label: '📝 Short Answer', icon: '📝' },
  { value: 'paragraph', label: '📄 Paragraph', icon: '📄' },
  { value: 'email', label: '📧 Email', icon: '📧' },
  { value: 'phone', label: '📞 Phone Number', icon: '📞' },
  { value: 'password', label: '🔒 Password', icon: '🔒' },
  { value: 'number', label: '🔢 Number', icon: '🔢' },
  { value: 'date', label: '📅 Date', icon: '📅' },
  { value: 'time', label: '⏰ Time', icon: '⏰' },
  { value: 'url', label: '🌐 URL', icon: '🌐' },
  { value: 'multiple_choice', label: '🔘 Multiple Choice', icon: '🔘' },
  { value: 'checkboxes', label: '☑️ Checkboxes', icon: '☑️' },
  { value: 'dropdown', label: '📋 Dropdown', icon: '📋' },
  { value: 'linear_scale', label: '📊 Linear Scale', icon: '📊' },
  { value: 'file_upload', label: '📎 File Upload', icon: '📎' },
];

export default function FormBuilder({ onClose, onFormCreated }) {
  const [formTitle, setFormTitle] = useState('');
  const [formDescription, setFormDescription] = useState('');
  const [fields, setFields] = useState([]);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [showConditionalBuilder, setShowConditionalBuilder] = useState(null); // fieldId for conditional builder

  const addField = (type) => {
    const newField = {
      id: Date.now().toString(),
      name: `field_${fields.length + 1}`,
      type: type,
      label: 'Untitled Question',
      description: '',
      placeholder: '',
      validation: {
        required: false
      },
      order: fields.length,
      options: type === 'multiple_choice' || type === 'checkboxes' || type === 'dropdown' ? ['Option 1'] : null,
      scale_min: type === 'linear_scale' ? 1 : null,
      scale_max: type === 'linear_scale' ? 5 : null,
      scale_min_label: type === 'linear_scale' ? 'Low' : null,
      scale_max_label: type === 'linear_scale' ? 'High' : null,
      conditional_fields: type === 'multiple_choice' || type === 'dropdown' ? {} : null
    };
    setFields([...fields, newField]);
  };

  const updateField = (fieldId, updates) => {
    setFields(fields.map(field => 
      field.id === fieldId ? { ...field, ...updates } : field
    ));
  };

  const removeField = (fieldId) => {
    setFields(fields.filter(field => field.id !== fieldId));
  };

  const addOption = (fieldId) => {
    updateField(fieldId, {
      options: [...(fields.find(f => f.id === fieldId)?.options || []), `Option ${(fields.find(f => f.id === fieldId)?.options?.length || 0) + 1}`]
    });
  };

  const updateOption = (fieldId, optionIndex, value) => {
    const field = fields.find(f => f.id === fieldId);
    const newOptions = [...field.options];
    newOptions[optionIndex] = value;
    updateField(fieldId, { options: newOptions });
  };

  const removeOption = (fieldId, optionIndex) => {
    const field = fields.find(f => f.id === fieldId);
    const newOptions = field.options.filter((_, index) => index !== optionIndex);
    updateField(fieldId, { options: newOptions });
  };

  const addConditionalField = (parentFieldId, optionValue) => {
    const newConditionalField = {
      id: Date.now().toString() + '_conditional',
      name: `conditional_${Date.now()}`,
      type: 'short_answer',
      label: 'Conditional Field',
      validation: { required: false },
      order: 0
    };

    const parentField = fields.find(f => f.id === parentFieldId);
    const updatedConditionalFields = { ...parentField.conditional_fields };
    
    if (!updatedConditionalFields[optionValue]) {
      updatedConditionalFields[optionValue] = [];
    }
    
    updatedConditionalFields[optionValue].push(newConditionalField);
    updateField(parentFieldId, { conditional_fields: updatedConditionalFields });
  };

  const updateConditionalField = (parentFieldId, optionValue, conditionalFieldId, updates) => {
    const parentField = fields.find(f => f.id === parentFieldId);
    const updatedConditionalFields = { ...parentField.conditional_fields };
    
    updatedConditionalFields[optionValue] = updatedConditionalFields[optionValue].map(cf => 
      cf.id === conditionalFieldId ? { ...cf, ...updates } : cf
    );
    
    updateField(parentFieldId, { conditional_fields: updatedConditionalFields });
  };

  const removeConditionalField = (parentFieldId, optionValue, conditionalFieldId) => {
    const parentField = fields.find(f => f.id === parentFieldId);
    const updatedConditionalFields = { ...parentField.conditional_fields };
    
    updatedConditionalFields[optionValue] = updatedConditionalFields[optionValue].filter(cf => cf.id !== conditionalFieldId);
    
    updateField(parentFieldId, { conditional_fields: updatedConditionalFields });
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    if (!formTitle.trim()) {
      alert('Please enter a form title');
      return;
    }
    if (fields.length === 0) {
      alert('Please add at least one field');
      return;
    }

    setIsSubmitting(true);
    try {
      const API = import.meta.env.VITE_BACKEND_URL || "http://127.0.0.1:8000";
      const response = await fetch(`${API}/forms`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          title: formTitle,
          description: formDescription,
          fields: fields.map(field => ({
            name: field.name,
            type: field.type,
            label: field.label,
            description: field.description || null,
            placeholder: field.placeholder || null,
            validation: field.validation,
            order: field.order,
            options: field.options,
            scale_min: field.scale_min,
            scale_max: field.scale_max,
            scale_min_label: field.scale_min_label,
            scale_max_label: field.scale_max_label
          }))
        }),
      });

      if (response.ok) {
        const result = await response.json();
        alert('Form created successfully!');
        onFormCreated(result.form);
        onClose();
      } else {
        throw new Error('Failed to create form');
      }
    } catch (error) {
      console.error('Error creating form:', error);
      alert('Error creating form. Please try again.');
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <div className="fixed inset-0 bg-black bg-opacity-75 flex items-center justify-center p-4 z-50">
      <div className="bg-gray-800 border border-gray-700 rounded-xl shadow-2xl max-w-5xl w-full max-h-[90vh] overflow-y-auto">
        <div className="p-6 border-b border-gray-700 bg-gradient-to-r from-blue-600/20 to-purple-600/20">
          <div className="flex items-center justify-between">
            <div>
              <h2 className="text-2xl font-bold text-white">🚀 Create AI-Powered Form</h2>
              <p className="text-gray-300 text-sm mt-1">Build intelligent forms with conversational AI assistance</p>
            </div>
            <button
              onClick={onClose}
              className="text-gray-400 hover:text-white text-2xl transition-colors"
            >
              ×
            </button>
          </div>
        </div>

        <form onSubmit={handleSubmit} className="p-6">
          {/* Form Title and Description */}
          <div className="mb-8 space-y-6">
            <div>
              <label className="block text-sm font-medium text-gray-200 mb-2">
                Form Title *
              </label>
              <input
                type="text"
                value={formTitle}
                onChange={(e) => setFormTitle(e.target.value)}
                placeholder="e.g., Customer Feedback Survey, Registration Form..."
                className="w-full p-4 border border-gray-600 bg-gray-700 text-white placeholder-gray-400 rounded-lg focus:ring-2 focus:ring-blue-400 focus:border-blue-400 transition-all"
                required
              />
            </div>
            <div>
              <label className="block text-sm font-medium text-gray-200 mb-2">
                Description
              </label>
              <textarea
                value={formDescription}
                onChange={(e) => setFormDescription(e.target.value)}
                placeholder="Briefly describe what this form is for..."
                rows={3}
                className="w-full p-4 border border-gray-600 bg-gray-700 text-white placeholder-gray-400 rounded-lg focus:ring-2 focus:ring-blue-400 focus:border-blue-400 transition-all"
              />
            </div>
          </div>

          {/* Enhanced Field Types */}
          <div className="mb-8">
            <h3 className="text-xl font-semibold text-white mb-4 flex items-center gap-2">
              <span>🔧</span>
              Add Form Fields
            </h3>
            <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-4 gap-3">
              {FIELD_TYPES.map((type) => (
                <button
                  key={type.value}
                  type="button"
                  onClick={() => addField(type.value)}
                  className="p-4 text-sm border border-gray-600 bg-gray-700 text-white rounded-lg hover:bg-gray-600 hover:border-blue-400 transition-all duration-200 group flex flex-col items-center gap-2"
                >
                  <span className="text-lg group-hover:scale-110 transition-transform">
                    {type.icon}
                  </span>
                  <span className="font-medium">{type.label.replace(/^.+\s/, '')}</span>
                </button>
              ))}
            </div>
          </div>

          {/* Fields */}
          <div className="space-y-4 mb-6">
            {fields.map((field, index) => (
              <div key={field.id} className="border border-gray-600 bg-gray-700 rounded-lg p-4">
                <div className="flex items-center justify-between mb-4">
                  <h4 className="font-semibold text-white">
                    {index + 1}. {FIELD_TYPES.find(t => t.value === field.type)?.label}
                  </h4>
                  <button
                    type="button"
                    onClick={() => removeField(field.id)}
                    className="text-red-400 hover:text-red-300"
                  >
                    Remove
                  </button>
                </div>

                <div className="grid grid-cols-1 md:grid-cols-2 gap-4 mb-4">
                  <div>
                    <label className="block text-sm font-medium text-gray-200 mb-1">
                      Field Name
                    </label>
                    <input
                      type="text"
                      value={field.name}
                      onChange={(e) => updateField(field.id, { name: e.target.value })}
                      className="w-full p-2 border border-gray-600 bg-gray-700 text-white rounded focus:ring-1 focus:ring-blue-400"
                    />
                  </div>
                  <div>
                    <label className="block text-sm font-medium text-gray-200 mb-1">
                      Question Label
                    </label>
                    <input
                      type="text"
                      value={field.label}
                      onChange={(e) => updateField(field.id, { label: e.target.value })}
                      className="w-full p-2 border border-gray-600 bg-gray-700 text-white rounded focus:ring-1 focus:ring-blue-400"
                    />
                  </div>
                </div>

                <div className="mb-4">
                  <label className="block text-sm font-medium text-gray-200 mb-1">
                    Description/Help Text
                  </label>
                  <input
                    type="text"
                    value={field.description}
                    onChange={(e) => updateField(field.id, { description: e.target.value })}
                    placeholder="Optional description..."
                    className="w-full p-2 border border-gray-600 bg-gray-700 text-white placeholder-gray-400 rounded focus:ring-1 focus:ring-blue-400"
                  />
                </div>

                {/* Options for choice fields */}
                {(field.type === 'multiple_choice' || field.type === 'checkboxes' || field.type === 'dropdown') && (
                  <div className="mb-4">
                    <label className="block text-sm font-medium text-gray-200 mb-2">
                      Options
                    </label>
                    {field.options?.map((option, optionIndex) => (
                      <div key={optionIndex} className="flex items-center gap-2 mb-2">
                        <input
                          type="text"
                          value={option}
                          onChange={(e) => updateOption(field.id, optionIndex, e.target.value)}
                          className="flex-1 p-2 border border-gray-600 bg-gray-700 text-white rounded focus:ring-1 focus:ring-blue-400"
                        />
                        {field.options.length > 1 && (
                          <button
                            type="button"
                            onClick={() => removeOption(field.id, optionIndex)}
                            className="text-red-400 hover:text-red-300"
                          >
                            ×
                          </button>
                        )}
                      </div>
                    ))}
                    <button
                      type="button"
                      onClick={() => addOption(field.id)}
                      className="text-blue-400 hover:text-blue-300 text-sm"
                    >
                      + Add Option
                    </button>
                  </div>
                )}

                {/* Scale settings */}
                {field.type === 'linear_scale' && (
                  <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-4">
                    <div>
                      <label className="block text-sm font-medium text-gray-200 mb-1">Min</label>
                      <input
                        type="number"
                        value={field.scale_min || 1}
                        onChange={(e) => updateField(field.id, { scale_min: parseInt(e.target.value) })}
                        className="w-full p-2 border border-gray-600 bg-gray-700 text-white rounded focus:ring-1 focus:ring-blue-400"
                      />
                    </div>
                    <div>
                      <label className="block text-sm font-medium text-gray-200 mb-1">Max</label>
                      <input
                        type="number"
                        value={field.scale_max || 5}
                        onChange={(e) => updateField(field.id, { scale_max: parseInt(e.target.value) })}
                        className="w-full p-2 border border-gray-600 bg-gray-700 text-white rounded focus:ring-1 focus:ring-blue-400"
                      />
                    </div>
                    <div>
                      <label className="block text-sm font-medium text-gray-200 mb-1">Min Label</label>
                      <input
                        type="text"
                        value={field.scale_min_label || ''}
                        onChange={(e) => updateField(field.id, { scale_min_label: e.target.value })}
                        className="w-full p-2 border border-gray-600 bg-gray-700 text-white rounded focus:ring-1 focus:ring-blue-400"
                      />
                    </div>
                    <div>
                      <label className="block text-sm font-medium text-gray-200 mb-1">Max Label</label>
                      <input
                        type="text"
                        value={field.scale_max_label || ''}
                        onChange={(e) => updateField(field.id, { scale_max_label: e.target.value })}
                        className="w-full p-2 border border-gray-600 bg-gray-700 text-white rounded focus:ring-1 focus:ring-blue-400"
                      />
                    </div>
                  </div>
                )}

                {/* Conditional Fields for Multiple Choice and Dropdown */}
                {(field.type === 'multiple_choice' || field.type === 'dropdown') && (
                  <div className="mt-6 p-4 bg-gray-600 rounded-lg">
                    <h5 className="font-semibold text-white mb-3 flex items-center gap-2">
                      <span>🔀</span>
                      Conditional Fields (Show different fields based on selection)
                    </h5>
                    
                    {field.options?.map((option, optionIndex) => (
                      <div key={optionIndex} className="mb-4 p-3 bg-gray-700 rounded border">
                        <div className="flex items-center justify-between mb-2">
                          <span className="text-sm font-medium text-gray-200">
                            When "{option}" is selected:
                          </span>
                          <button
                            type="button"
                            onClick={() => addConditionalField(field.id, option)}
                            className="text-blue-400 hover:text-blue-300 text-sm"
                          >
                            + Add Field
                          </button>
                        </div>
                        
                        {field.conditional_fields?.[option]?.map((conditionalField, cfIndex) => (
                          <div key={conditionalField.id} className="mt-2 p-3 bg-gray-800 rounded border border-gray-600">
                            <div className="flex items-center justify-between mb-2">
                              <span className="text-xs text-gray-400">Conditional Field #{cfIndex + 1}</span>
                              <button
                                type="button"
                                onClick={() => removeConditionalField(field.id, option, conditionalField.id)}
                                className="text-red-400 hover:text-red-300 text-xs"
                              >
                                Remove
                              </button>
                            </div>
                            
                            <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
                              <div>
                                <label className="block text-xs font-medium text-gray-300 mb-1">
                                  Field Type
                                </label>
                                <select
                                  value={conditionalField.type}
                                  onChange={(e) => updateConditionalField(field.id, option, conditionalField.id, { type: e.target.value })}
                                  className="w-full p-2 text-xs border border-gray-600 bg-gray-700 text-white rounded focus:ring-1 focus:ring-blue-400"
                                >
                                  <option value="short_answer">Short Answer</option>
                                  <option value="paragraph">Paragraph</option>
                                  <option value="email">Email</option>
                                  <option value="phone">Phone</option>
                                  <option value="number">Number</option>
                                  <option value="date">Date</option>
                                  <option value="time">Time</option>
                                </select>
                              </div>
                              <div>
                                <label className="block text-xs font-medium text-gray-300 mb-1">
                                  Field Name
                                </label>
                                <input
                                  type="text"
                                  value={conditionalField.name}
                                  onChange={(e) => updateConditionalField(field.id, option, conditionalField.id, { name: e.target.value })}
                                  className="w-full p-2 text-xs border border-gray-600 bg-gray-700 text-white rounded focus:ring-1 focus:ring-blue-400"
                                />
                              </div>
                            </div>
                            
                            <div className="mt-2">
                              <label className="block text-xs font-medium text-gray-300 mb-1">
                                Label
                              </label>
                              <input
                                type="text"
                                value={conditionalField.label}
                                onChange={(e) => updateConditionalField(field.id, option, conditionalField.id, { label: e.target.value })}
                                className="w-full p-2 text-xs border border-gray-600 bg-gray-700 text-white rounded focus:ring-1 focus:ring-blue-400"
                              />
                            </div>
                            
                            <div className="mt-2 flex items-center">
                              <input
                                type="checkbox"
                                id={`cf-required-${conditionalField.id}`}
                                checked={conditionalField.validation?.required || false}
                                onChange={(e) => updateConditionalField(field.id, option, conditionalField.id, { 
                                  validation: { ...conditionalField.validation, required: e.target.checked }
                                })}
                                className="mr-2"
                              />
                              <label htmlFor={`cf-required-${conditionalField.id}`} className="text-xs text-gray-300">
                                Required field
                              </label>
                            </div>
                          </div>
                        ))}
                        
                        {(!field.conditional_fields?.[option] || field.conditional_fields[option].length === 0) && (
                          <div className="text-xs text-gray-400 italic mt-2">
                            No conditional fields added yet. Click "Add Field" to add fields that show when this option is selected.
                          </div>
                        )}
                      </div>
                    ))}
                  </div>
                )}

                {/* Required toggle */}
                <div className="flex items-center">
                  <input
                    type="checkbox"
                    id={`required-${field.id}`}
                    checked={field.validation.required}
                    onChange={(e) => updateField(field.id, { 
                      validation: { ...field.validation, required: e.target.checked }
                    })}
                    className="mr-2"
                  />
                  <label htmlFor={`required-${field.id}`} className="text-sm text-gray-200">
                    Required field
                  </label>
                </div>
              </div>
            ))}
          </div>

          {/* Submit Button */}
          <div className="flex justify-end gap-4">
            <button
              type="button"
              onClick={onClose}
              className="px-6 py-2 border border-gray-600 bg-gray-700 text-gray-200 rounded-lg hover:bg-gray-600 transition-colors"
            >
              Cancel
            </button>
            <button
              type="submit"
              disabled={isSubmitting}
              className="px-6 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 disabled:opacity-50 transition-colors"
            >
              {isSubmitting ? 'Creating...' : 'Create Form'}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}