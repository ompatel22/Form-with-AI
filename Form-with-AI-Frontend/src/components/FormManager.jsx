import React, { useState, useEffect } from 'react';
import FormBuilder from './FormBuilder.jsx';

const API_URL = 'http://127.0.0.1:8000';

export default function FormManager({ onFormSelected, onClose }) {
  const [forms, setForms] = useState([]);
  const [templates, setTemplates] = useState([]);
  const [loading, setLoading] = useState(true);
  const [showFormBuilder, setShowFormBuilder] = useState(false);
  const [activeTab, setActiveTab] = useState('forms'); // 'forms' or 'templates'

  useEffect(() => {
    loadForms();
    loadTemplates();
  }, []);

  const loadForms = async () => {
    try {
      const response = await fetch(`${API_URL}/forms`);
      if (response.ok) {
        const data = await response.json();
        setForms(data.forms || []);
      }
    } catch (error) {
      console.error('Error loading forms:', error);
    } finally {
      setLoading(false);
    }
  };

  const loadTemplates = async () => {
    try {
      const response = await fetch(`${API_URL}/forms/templates/list`);
      if (response.ok) {
        const data = await response.json();
        setTemplates(data.templates || []);
      }
    } catch (error) {
      console.error('Error loading templates:', error);
    }
  };

  const handleFormCreated = (newForm) => {
    setForms([newForm, ...forms]);
    setShowFormBuilder(false);
  };

  const handleFormSelect = async (formId) => {
    try {
      const response = await fetch(`${API_URL}/forms/${formId}`);
      if (response.ok) {
        const data = await response.json();
        onFormSelected(data.form);
      }
    } catch (error) {
      console.error('Error loading form:', error);
      alert('Error loading form. Please try again.');
    }
  };

  const createFromTemplate = async (templateId, customTitle) => {
    try {
      const url = customTitle 
        ? `${API_URL}/forms/templates/${templateId}?title_override=${encodeURIComponent(customTitle)}`
        : `${API_URL}/forms/templates/${templateId}`;
      
      const response = await fetch(url, { method: 'POST' });
      
      if (response.ok) {
        const data = await response.json();
        setForms([data.form, ...forms]);
        alert('Form created from template successfully!');
        setActiveTab('forms');
      }
    } catch (error) {
      console.error('Error creating from template:', error);
      alert('Error creating form from template. Please try again.');
    }
  };

  const deleteForm = async (formId) => {
    if (!confirm('Are you sure you want to delete this form? This action cannot be undone.')) {
      return;
    }

    try {
      const response = await fetch(`${API_URL}/forms/${formId}`, { method: 'DELETE' });
      if (response.ok) {
        setForms(forms.filter(form => form.id !== formId));
        alert('Form deleted successfully!');
      }
    } catch (error) {
      console.error('Error deleting form:', error);
      alert('Error deleting form. Please try again.');
    }
  };

  if (showFormBuilder) {
    return (
      <FormBuilder
        onClose={() => setShowFormBuilder(false)}
        onFormCreated={handleFormCreated}
      />
    );
  }

  return (
    <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center p-4 z-50">
      <div className="bg-white rounded-xl shadow-2xl max-w-6xl w-full max-h-[90vh] overflow-hidden">
        {/* Header */}
        <div className="p-6 border-b border-gray-200 bg-gradient-to-r from-blue-600 to-purple-600 text-white">
          <div className="flex items-center justify-between">
            <h2 className="text-2xl font-bold">Form Manager</h2>
            <button
              onClick={onClose}
              className="text-white hover:text-gray-200 text-2xl"
            >
              ×
            </button>
          </div>
          <p className="mt-2 opacity-90">Create new forms or select existing ones for conversational filling</p>
        </div>

        {/* Tabs */}
        <div className="flex border-b border-gray-200">
          <button
            onClick={() => setActiveTab('forms')}
            className={`px-6 py-3 font-medium transition-colors ${
              activeTab === 'forms'
                ? 'text-blue-600 border-b-2 border-blue-600 bg-blue-50'
                : 'text-gray-500 hover:text-gray-700'
            }`}
          >
            My Forms ({forms.length})
          </button>
          <button
            onClick={() => setActiveTab('templates')}
            className={`px-6 py-3 font-medium transition-colors ${
              activeTab === 'templates'
                ? 'text-blue-600 border-b-2 border-blue-600 bg-blue-50'
                : 'text-gray-500 hover:text-gray-700'
            }`}
          >
            Templates ({templates.length})
          </button>
        </div>

        {/* Content */}
        <div className="flex-1 overflow-y-auto p-6" style={{ maxHeight: '60vh' }}>
          {activeTab === 'forms' && (
            <div>
              {/* Create Form Button */}
              <div className="mb-6">
                <button
                  onClick={() => setShowFormBuilder(true)}
                  className="bg-blue-600 text-white px-6 py-3 rounded-lg hover:bg-blue-700 transition-colors shadow-md hover:shadow-lg"
                >
                  + Create New Form
                </button>
              </div>

              {/* Forms List */}
              {loading ? (
                <div className="text-center py-8">
                  <div className="inline-block animate-spin rounded-full h-8 w-8 border-b-2 border-blue-600"></div>
                  <p className="mt-2 text-gray-600">Loading forms...</p>
                </div>
              ) : forms.length === 0 ? (
                <div className="text-center py-12">
                  <div className="text-6xl mb-4">📋</div>
                  <h3 className="text-xl font-semibold text-gray-700 mb-2">No Forms Yet</h3>
                  <p className="text-gray-500 mb-4">Create your first form to get started</p>
                  <button
                    onClick={() => setShowFormBuilder(true)}
                    className="bg-blue-600 text-white px-6 py-2 rounded-lg hover:bg-blue-700 transition-colors"
                  >
                    Create Form
                  </button>
                </div>
              ) : (
                <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
                  {forms.map((form) => (
                    <div key={form.id} className="border border-gray-200 rounded-lg p-6 hover:shadow-lg transition-shadow">
                      <h3 className="text-lg font-semibold text-gray-800 mb-2">{form.title}</h3>
                      {form.description && (
                        <p className="text-gray-600 text-sm mb-4 line-clamp-2">{form.description}</p>
                      )}
                      <div className="text-sm text-gray-500 mb-4">
                        <p>{form.field_count} fields</p>
                        <p>Created {new Date(form.created_at * 1000).toLocaleDateString()}</p>
                      </div>
                      <div className="flex gap-2">
                        <button
                          onClick={() => handleFormSelect(form.id)}
                          className="flex-1 bg-blue-600 text-white px-4 py-2 rounded hover:bg-blue-700 transition-colors"
                        >
                          Use Form
                        </button>
                        <button
                          onClick={() => deleteForm(form.id)}
                          className="px-4 py-2 border border-red-300 text-red-600 rounded hover:bg-red-50 transition-colors"
                        >
                          Delete
                        </button>
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </div>
          )}

          {activeTab === 'templates' && (
            <div>
              <div className="mb-6">
                <h3 className="text-lg font-semibold text-gray-800 mb-2">Form Templates</h3>
                <p className="text-gray-600">Start with a pre-built template and customize as needed</p>
              </div>

              <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                {templates.map((template) => (
                  <div key={template.id} className="border border-gray-200 rounded-lg p-6 hover:shadow-lg transition-shadow">
                    <h3 className="text-lg font-semibold text-gray-800 mb-2">{template.title}</h3>
                    <p className="text-gray-600 text-sm mb-4">{template.description}</p>
                    <div className="text-sm text-gray-500 mb-4">
                      <p>{template.field_count} fields included</p>
                    </div>
                    <div className="flex gap-2">
                      <button
                        onClick={() => {
                          const customTitle = prompt('Enter a title for your new form (or leave blank to use template title):');
                          if (customTitle !== null) {
                            createFromTemplate(template.id, customTitle.trim());
                          }
                        }}
                        className="flex-1 bg-green-600 text-white px-4 py-2 rounded hover:bg-green-700 transition-colors"
                      >
                        Use Template
                      </button>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>

        {/* Footer */}
        <div className="p-6 border-t border-gray-200 bg-gray-50">
          <div className="flex justify-between items-center">
            <div className="text-sm text-gray-600">
              {activeTab === 'forms' 
                ? `${forms.length} forms available`
                : `${templates.length} templates available`
              }
            </div>
            <button
              onClick={onClose}
              className="px-6 py-2 border border-gray-300 rounded-lg text-gray-700 hover:bg-gray-100 transition-colors"
            >
              Close
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}