import React, { useState, useEffect } from 'react';
import FormBuilder from './FormBuilder.jsx';
import QRCode from 'qrcode';

const API_URL = import.meta.env.VITE_BACKEND_URL || "http://127.0.0.1:8000";

// Helper to bypass the ngrok browser warning page.
const fetchWithNgrokHeader = (url, options = {}) => {
  const headers = {
    ...options.headers,
    'ngrok-skip-browser-warning': 'true',
  };
  return fetch(url, { ...options, headers });
};

export default function FormManager({ onFormSelected, onClose }) {
  const [forms, setForms] = useState([]);
  const [templates, setTemplates] = useState([]);
  const [loading, setLoading] = useState(true);
  const [showFormBuilder, setShowFormBuilder] = useState(false);
  const [activeTab, setActiveTab] = useState('forms'); // 'forms' or 'templates'
  const [showQrModal, setShowQrModal] = useState(false);
  const [qrCodeDataUrl, setQrCodeDataUrl] = useState('');
  const [qrCodeShareUrl, setQrCodeShareUrl] = useState('');

  useEffect(() => {
    loadForms();
    loadTemplates();
  }, []);

  const loadForms = async () => {
    try {
      const response = await fetchWithNgrokHeader(`${API_URL}/forms`);
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
      const response = await fetchWithNgrokHeader(`${API_URL}/forms/templates/list`);
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
      const response = await fetchWithNgrokHeader(`${API_URL}/forms/${formId}`);
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
      
      const response = await fetchWithNgrokHeader(url, { method: 'POST' });
      
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

  const showQrCodeForForm = (formId) => {
    const shareUrl = `${window.location.origin}/forms/${formId}/fill`;
    setQrCodeShareUrl(shareUrl);
    QRCode.toDataURL(shareUrl, { width: 256, margin: 2 })
      .then(url => {
        setQrCodeDataUrl(url);
        setShowQrModal(true);
      })
      .catch(err => {
        console.error('Error generating QR code:', err);
        alert('Could not generate QR code.');
      });
  };

  const deleteForm = async (formId) => {
    if (!confirm('Are you sure you want to delete this form? This action cannot be undone.')) {
      return;
    }

    try {
      const response = await fetchWithNgrokHeader(`${API_URL}/forms/${formId}`, { method: 'DELETE' });
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
    <div className="min-h-screen bg-gradient-to-br from-gray-900 via-gray-800 to-gray-900 p-4 md:p-8">
      {showQrModal && (
        <div 
          className="fixed inset-0 bg-black bg-opacity-75 flex items-center justify-center z-50 backdrop-blur-sm" 
          onClick={() => setShowQrModal(false)}
        >
          <div 
            className="bg-gray-800 border border-gray-700 rounded-2xl shadow-2xl w-full max-w-md transform transition-all" 
            onClick={(e) => e.stopPropagation()}
          >
            {/* Header */}
            <div className="p-6 border-b border-gray-700 flex justify-between items-center">
              <h3 className="text-xl font-bold text-white">Scan to Open Form</h3>
              <button
                onClick={() => setShowQrModal(false)}
                className="text-gray-400 hover:text-white text-2xl transition-colors"
              >
                &times;
              </button>
            </div>

            {/* Content */}
            <div className="p-8 text-center">
              <p className="text-gray-300 mb-6">Scan the code below with your mobile device to open the form instantly.</p>
              <div className="p-2 bg-white inline-block rounded-lg shadow-lg">
                {qrCodeDataUrl && <img src={qrCodeDataUrl} alt="Form QR Code" className="rounded-md" />}
              </div>
              <div className="mt-6">
                <p className="text-xs text-gray-400 mb-2">Or copy the shareable link:</p>
                <div className="bg-gray-900 p-3 rounded-lg text-sm text-gray-300 font-mono break-all text-left relative">
                  {qrCodeShareUrl}
                  <button
                    onClick={() => {
                      navigator.clipboard.writeText(qrCodeShareUrl);
                      alert('Link copied to clipboard!');
                    }}
                    className="absolute top-1/2 right-2 -translate-y-1/2 p-1.5 bg-gray-700 rounded-md hover:bg-gray-600"
                    title="Copy link"
                  >
                    <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" strokeWidth={1.5} stroke="currentColor" className="w-5 h-5 text-gray-300">
                      <path strokeLinecap="round" strokeLinejoin="round" d="M8.25 7.5V6.108c0-1.135.845-2.098 1.976-2.192.373-.03.748-.03 1.125 0 1.131.094 1.976 1.057 1.976 2.192V7.5M8.25 7.5h7.5M8.25 7.5c-1.036 0-1.875.84-1.875 1.875v8.25c0 1.035.84 1.875 1.875 1.875h7.5c1.035 0 1.875-.84 1.875-1.875v-8.25c0-1.036-.84-1.875-1.875-1.875M16.5 7.5h-7.5" />
                    </svg>
                  </button>
                </div>
              </div>
            </div>
          </div>
        </div>
      )}

      <div className="max-w-7xl mx-auto">
        {/* Header */}
        <div className="text-center mb-8">
          <h1 className="text-4xl md:text-5xl font-bold text-white mb-4 tracking-tight">
            AI-Powered Form Builder
          </h1>
          <p className="text-xl text-gray-300 mb-8">
            Create intelligent forms with conversational AI assistance
          </p>
          
          <div className="bg-gradient-to-r from-blue-600/20 to-purple-600/20 border border-blue-500/30 rounded-xl p-6 backdrop-blur-sm">
            <div className="flex items-center justify-center gap-8 text-sm text-gray-300">
              <div className="flex items-center gap-2">
                <div className="w-3 h-3 bg-green-500 rounded-full"></div>
                <span>Voice Recognition</span>
              </div>
              <div className="flex items-center gap-2">
                <div className="w-3 h-3 bg-blue-500 rounded-full"></div>
                <span>AI Conversation</span>
              </div>
              <div className="flex items-center gap-2">
                <div className="w-3 h-3 bg-purple-500 rounded-full"></div>
                <span>Smart Validation</span>
              </div>
            </div>
          </div>
        </div>

        {/* Modern Tab Navigation */}
        <div className="bg-gray-800 rounded-xl border border-gray-700 mb-8">
          <div className="flex p-2">
            <button
              onClick={() => setActiveTab('forms')}
              className={`flex-1 px-6 py-3 font-medium rounded-lg transition-all duration-300 ${
                activeTab === 'forms'
                  ? 'bg-blue-600 text-white shadow-lg'
                  : 'text-gray-400 hover:text-white hover:bg-gray-700'
              }`}
            >
              <div className="flex items-center justify-center gap-2">
                <span>📋</span>
                <span>My Forms ({forms.length})</span>
              </div>
            </button>
            <button
              onClick={() => setActiveTab('templates')}
              className={`flex-1 px-6 py-3 font-medium rounded-lg transition-all duration-300 ${
                activeTab === 'templates'
                  ? 'bg-purple-600 text-white shadow-lg'
                  : 'text-gray-400 hover:text-white hover:bg-gray-700'
              }`}
            >
              <div className="flex items-center justify-center gap-2">
                <span>🎯</span>
                <span>Templates ({templates.length})</span>
              </div>
            </button>
          </div>
        </div>

        {/* Content */}
        <div className="min-h-[60vh]">
          {activeTab === 'forms' && (
            <div>
              {/* Enhanced Create Form Button */}
              <div className="mb-8">
                <button
                  onClick={() => setShowFormBuilder(true)}
                  className="bg-gradient-to-r from-blue-600 to-blue-700 text-white px-8 py-4 rounded-xl hover:from-blue-500 hover:to-blue-600 transition-all duration-300 shadow-lg hover:shadow-xl font-semibold text-lg flex items-center gap-3"
                >
                  <span className="text-xl">+</span>
                  Create New AI-Powered Form
                </button>
              </div>

              {/* Enhanced Forms List */}
              {loading ? (
                <div className="text-center py-16">
                  <div className="inline-block animate-spin rounded-full h-12 w-12 border-b-2 border-blue-500"></div>
                  <p className="mt-4 text-gray-300 text-lg">Loading your AI forms...</p>
                </div>
              ) : forms.length === 0 ? (
                <div className="text-center py-16 bg-gray-800 rounded-xl border border-gray-700">
                  <div className="text-8xl mb-6">🚀</div>
                  <h3 className="text-2xl font-semibold text-white mb-3">Ready to Build Your First AI Form?</h3>
                  <p className="text-gray-400 mb-6 text-lg">Create intelligent forms with conversational AI that understands natural language</p>
                  <button
                    onClick={() => setShowFormBuilder(true)}
                    className="bg-gradient-to-r from-green-600 to-green-700 text-white px-8 py-3 rounded-xl hover:from-green-500 hover:to-green-600 transition-all duration-300 shadow-lg hover:shadow-xl font-semibold"
                  >
                    🎯 Create Your First Form
                  </button>
                </div>
              ) : (
                <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-6">
                  {forms.map((form) => (
                    <div key={form.id} className="bg-gray-800 border border-gray-700 rounded-xl p-6 hover:border-blue-500/50 hover:shadow-xl hover:shadow-blue-500/10 transition-all duration-300 group">
                      <div className="flex items-start justify-between mb-4">
                        <h3 className="text-xl font-semibold text-white group-hover:text-blue-300 transition-colors">{form.title}</h3>
                        <span className="text-xs bg-gray-700 text-gray-300 px-2 py-1 rounded-full">
                          {form.field_count} fields
                        </span>
                      </div>
                      
                      {form.description && (
                        <p className="text-gray-400 text-sm mb-4 line-clamp-3">{form.description}</p>
                      )}
                      
                      <div className="flex items-center gap-4 text-xs text-gray-500 mb-6">
                        <span className="flex items-center gap-1">
                          <span>📅</span>
                          {new Date(form.created_at * 1000).toLocaleDateString()}
                        </span>
                        <span className="flex items-center gap-1">
                          <span className={form.is_active ? "🟢" : "🔴"}></span>
                          {form.is_active ? "Active" : "Inactive"}
                        </span>
                      </div>
                      
                      <div className="flex gap-3">
                        <button
                          onClick={() => handleFormSelect(form.id)}
                          className="flex-1 bg-blue-600 text-white px-4 py-3 rounded-lg hover:bg-blue-500 transition-all duration-300 font-medium shadow-md hover:shadow-lg"
                        >
                          🤖 Use with AI
                        </button>
                        <button
                          onClick={() => {
                            const shareUrl = `${window.location.origin}/forms/${form.id}/fill`;
                            navigator.clipboard.writeText(shareUrl);
                            alert('Shareable link copied to clipboard!');
                          }}
                          className="px-4 py-3 bg-gray-700 text-gray-300 rounded-lg hover:bg-gray-600 transition-colors"
                          title="Copy shareable link"
                        >
                          🔗
                        </button>
                        <button
                          onClick={() => showQrCodeForForm(form.id)}
                          className="px-4 py-3 bg-gray-700 text-gray-300 rounded-lg hover:bg-gray-600 transition-colors"
                          title="Show QR Code"
                        >
                          <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" strokeWidth={1.5} stroke="currentColor" className="w-5 h-5">
                            <path strokeLinecap="round" strokeLinejoin="round" d="M3.75 4.875c0-1.036.84-1.875 1.875-1.875h4.5c1.036 0 1.875.84 1.875 1.875v4.5c0 1.036-.84 1.875-1.875 1.875h-4.5A1.875 1.875 0 013.75 9.375v-4.5zM3.75 14.625c0-1.036.84-1.875 1.875-1.875h4.5c1.036 0 1.875.84 1.875 1.875v4.5c0 1.036-.84 1.875-1.875 1.875h-4.5a1.875 1.875 0 01-1.875-1.875v-4.5zM13.5 4.875c0-1.036.84-1.875 1.875-1.875h4.5c1.036 0 1.875.84 1.875 1.875v4.5c0 1.036-.84 1.875-1.875 1.875h-4.5a1.875 1.875 0 01-1.875-1.875v-4.5z" />
                            <path strokeLinecap="round" strokeLinejoin="round" d="M13.5 14.625v4.5a1.875 1.875 0 001.875 1.875h4.5a1.875 1.875 0 001.875-1.875v-4.5a1.875 1.875 0 00-1.875-1.875h-4.5a1.875 1.875 0 00-1.875 1.875z" />
                          </svg>
                        </button>
                        <button
                          onClick={() => deleteForm(form.id)}
                          className="px-4 py-3 bg-red-600/20 text-red-400 border border-red-600/30 rounded-lg hover:bg-red-600/30 transition-colors"
                          title="Delete form"
                        >
                          🗑️
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
              {/* <div className="mb-8 text-center">
                <h3 className="text-2xl font-semibold text-white mb-3">Professional Form Templates</h3>
                <p className="text-gray-400 text-lg">Start with AI-powered templates and customize to your needs</p>
              </div> */}

              <div className="grid grid-cols-1 md:grid-cols-2 gap-8">
                {templates.map((template) => (
                  <div key={template.id} className="bg-gray-800 border border-gray-700 rounded-xl p-8 hover:border-purple-500/50 hover:shadow-xl hover:shadow-purple-500/10 transition-all duration-300 group">
                    <div className="text-center mb-6">
                      <div className="text-4xl mb-3">
                        {template.id === 'student_registration' ? '🎓' : 
                         template.id === 'feedback_survey' ? '📊' : '📋'}
                      </div>
                      <h3 className="text-xl font-semibold text-white group-hover:text-purple-300 transition-colors mb-2">
                        {template.title}
                      </h3>
                      <p className="text-gray-400 mb-4">{template.description}</p>
                      <div className="inline-flex items-center gap-2 bg-gray-700 px-3 py-1 rounded-full text-sm text-gray-300">
                        <span>📝</span>
                        <span>{template.field_count} AI-powered fields</span>
                      </div>
                    </div>
                    
                    <button
                      onClick={() => {
                        const customTitle = prompt('Enter a title for your new form (or leave blank to use template title):');
                        if (customTitle !== null) {
                          createFromTemplate(template.id, customTitle.trim());
                        }
                      }}
                      className="w-full bg-gradient-to-r from-purple-600 to-purple-700 text-white px-6 py-3 rounded-lg hover:from-purple-500 hover:to-purple-600 transition-all duration-300 font-medium shadow-md hover:shadow-lg"
                    >
                      🚀 Create from Template
                    </button>
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>

        {/* Enhanced Footer */}
        <div className="mt-12 pt-8 border-t border-gray-700 text-center">
          <div className="text-sm text-gray-400 mb-4">
            {activeTab === 'forms' 
              ? `${forms.length} intelligent forms ready for AI assistance`
              : `${templates.length} professional templates available`
            }
          </div>
        </div>
      </div>
    </div>
  );
}