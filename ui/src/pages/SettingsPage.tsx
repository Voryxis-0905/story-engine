import React, { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { ChevronLeftIcon, ChevronDownIcon, CheckCircleIcon, KeyIcon, CpuChipIcon, AdjustmentsHorizontalIcon, ArrowPathIcon, ShieldCheckIcon, UserIcon, Squares2X2Icon, ChatBubbleLeftRightIcon, GlobeAltIcon } from '@heroicons/react/24/outline';
import { api } from '../api/client';

type SettingSection = 'card' | 'module' | 'scenes' | 'models' | null;

export const SettingsPage: React.FC = () => {
  const navigate = useNavigate();
  const [activeSection, setActiveSection] = useState<SettingSection>(null);

  // Form states
  const [provider, setProvider] = useState('openrouter');
  const [apiKey, setApiKey] = useState('');
  const [modelName, setModelName] = useState('deepseek/deepseek-chat');
  const [baseUrl, setBaseUrl] = useState('');
  const [temperature, setTemperature] = useState(0.7);
  const [loading, setLoading] = useState(false);
  const [testing, setTesting] = useState(false);
  const [testResult, setTestResult] = useState<{ status: 'ok' | 'error'; message: string } | null>(null);
  const [saveSuccess, setSaveSuccess] = useState(false);

  useEffect(() => {
    loadConfig();
  }, []);

  const loadConfig = async () => {
    setLoading(true);
    try {
      const cfg = await api.config.get();
      if (cfg) {
        setProvider(cfg.llm_provider || 'openrouter');
        setApiKey(cfg.api_key || cfg.api_key_masked || '');
        setModelName(cfg.model_name || cfg.model || 'deepseek/deepseek-chat');
        setBaseUrl(cfg.base_url || '');
        setTemperature(cfg.temperature ?? 0.7);
      }
    } catch {
      // fallbacks
    } finally {
      setLoading(false);
    }
  };

  const handleSave = async (e: React.FormEvent) => {
    e.preventDefault();
    setLoading(true);
    setSaveSuccess(false);
    try {
      await api.config.update({
        llm_provider: provider,
        api_key: apiKey,
        model_name: modelName,
        base_url: baseUrl,
        temperature,
      });
      setSaveSuccess(true);
      setTimeout(() => setSaveSuccess(false), 3000);
    } catch (err: any) {
      alert(`Save failed: ${err.message}`);
    } finally {
      setLoading(false);
    }
  };

  const handleTestConnection = async () => {
    setTesting(true);
    setTestResult(null);
    try {
      // Read current values directly from DOM inputs if available to avoid any React batch state lag
      const keyEl = document.querySelector('input[type="password"]') as HTMLInputElement | null;
      const effectiveKey = keyEl && keyEl.value ? keyEl.value.trim() : apiKey;

      await api.config.update({
        llm_provider: provider,
        api_key: effectiveKey,
        model_name: modelName,
        base_url: baseUrl,
        temperature,
      });

      const res = await api.config.testConnection();
      setTestResult({
        status: res.ok || res.status === 'ok' ? 'ok' : 'error',
        message: res.message || 'LLM connection successful!',
      });
    } catch (err: any) {
      setTestResult({
        status: 'error',
        message: err.message || 'Failed to connect to LLM provider',
      });
    } finally {
      setTesting(false);
    }
  };

  return (
    <div className="w-full min-h-[calc(100vh-70px)] px-6 md:px-10 py-10 space-y-6 animate-fade-in">
      {/* Title Header */}
      <div className="flex items-center justify-between">
        <button
          onClick={() => navigate('/')}
          className="flex items-center gap-2 text-2xl font-bold text-[var(--ink-main)] hover:text-[var(--periwinkle-dark)] transition-colors cursor-pointer font-[var(--font-display)]"
        >
          <ChevronLeftIcon className="w-6 h-6" />
          <span>Settings</span>
        </button>
      </div>

      {/* List of Settings Category Cards */}
      <div className="space-y-5">
        {/* Card 1: Character Cards */}
        <div
          onClick={() => setActiveSection(activeSection === 'card' ? null : 'card')}
          className={`story-card p-7 md:p-8 rounded-3xl cursor-pointer relative overflow-hidden transition-all group ${
            activeSection === 'card' ? 'border-2 border-[var(--periwinkle)] bg-[var(--bg-surface)] shadow-lg' : 'border border-[var(--line)] bg-[var(--bg-surface)] hover:border-[var(--line-2)] hover:shadow-md'
          }`}
        >
          <div className="flex items-center justify-between relative z-10">
            <div className="space-y-1.5">
              <h3 className="text-xl font-bold text-[var(--ink-main)] font-[var(--font-display)] flex items-center gap-3">
                <span>Character Cards</span>
                <ChevronDownIcon className={`w-5 h-5 text-[var(--ink-soft)] transition-transform duration-300 ${activeSection === 'card' ? 'rotate-180 text-[var(--periwinkle-dark)]' : ''}`} />
              </h3>
              <p className="text-sm text-[var(--ink-soft)] font-medium">Use character presets & Persona prompt</p>
            </div>
            <span className="px-3.5 py-1 rounded-full text-xs font-mono font-bold bg-[rgba(var(--sakura-rgb),0.15)] text-[var(--sakura-dark)] border border-[var(--sakura)]">
              Active Preset
            </span>
          </div>
          <UserIcon className="w-28 h-28 text-[var(--sakura)] opacity-10 absolute -right-4 -bottom-6 pointer-events-none group-hover:scale-105 transition-transform duration-500" />
          
          {activeSection === 'card' && (
            <div className="mt-6 pt-6 border-t border-[var(--line)] space-y-4 animate-fade-in relative z-10">
              <p className="font-semibold text-[var(--periwinkle-dark)] font-[var(--font-display)] text-sm">Active Character Preset:</p>
              <div className="p-5 rounded-2xl bg-[var(--bg-subtle)] border border-[var(--line-2)] font-mono text-[13px] text-[var(--ink-soft)] font-medium shadow-inner">
                Name: <span className="text-[var(--ink-main)] font-bold">Lin Feng (Dragon Sovereign)</span> • System Prompt: Sonder Engine Deterministic Narrative Mode
              </div>
            </div>
          )}
        </div>

        {/* Card 2: Modules (LLM Provider & Credentials) */}
        <div
          className={`story-card p-7 md:p-8 rounded-3xl relative overflow-hidden transition-all group ${
            activeSection === 'module' ? 'border-2 border-[var(--periwinkle)] bg-[var(--bg-surface)] shadow-lg' : 'border border-[var(--line)] bg-[var(--bg-surface)] hover:border-[var(--line-2)] hover:shadow-md'
          }`}
        >
          <div
            onClick={() => setActiveSection(activeSection === 'module' ? null : 'module')}
            className="flex items-center justify-between cursor-pointer relative z-10"
          >
            <div className="space-y-1.5">
              <h3 className="text-xl font-bold text-[var(--ink-main)] font-[var(--font-display)] flex items-center gap-3">
                <span>Modules</span>
                <ChevronDownIcon className={`w-5 h-5 text-[var(--ink-soft)] transition-transform duration-300 ${activeSection === 'module' ? 'rotate-180 text-[var(--periwinkle-dark)]' : ''}`} />
              </h3>
              <p className="text-sm text-[var(--ink-soft)] font-medium">Cognition, vision, speech synthesis, API Keys, etc.</p>
            </div>
          </div>
          <Squares2X2Icon className="w-32 h-32 text-[var(--periwinkle)] opacity-10 absolute -right-4 -bottom-6 pointer-events-none group-hover:scale-105 transition-transform duration-500" />

          {activeSection === 'module' && (
            <form onSubmit={handleSave} className="mt-6 pt-6 border-t border-[var(--line)] space-y-6 animate-fade-in relative z-10">
              {saveSuccess && (
                <div className="p-4 rounded-2xl bg-[rgba(var(--ok-rgb),0.1)] border border-[rgba(var(--ok-rgb),0.3)] text-[var(--ok)] text-sm font-medium flex items-center gap-2 shadow-sm">
                  <CheckCircleIcon className="w-5 h-5" />
                  <span>Module configuration saved successfully!</span>
                </div>
              )}

              <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                <div>
                  <label className="block text-xs font-mono uppercase font-bold tracking-wider text-[var(--ink-soft)] mb-2 flex items-center gap-2">
                    <CpuChipIcon className="w-4 h-4 text-[var(--periwinkle-dark)]" />
                    <span>LLM Provider</span>
                  </label>
                  <select
                    value={provider}
                    onChange={(e) => setProvider(e.target.value)}
                    className="w-full px-5 py-3.5 rounded-2xl bg-[var(--bg-subtle)] border-2 border-transparent text-[var(--ink-main)] font-medium text-[14px] focus:outline-none focus:border-[var(--periwinkle)] cursor-pointer hover:bg-[var(--line)] transition-colors"
                  >
                    <option value="openrouter">OpenRouter (Unified Multi-Model Gateway)</option>
                    <option value="gemini">Google Gemini (Flash 2.0 / Pro 1.5)</option>
                    <option value="openai">OpenAI (GPT-4o / GPT-4o-mini)</option>
                    <option value="custom">Custom Provider (Local / Compatible Endpoint)</option>
                  </select>
                </div>

                <div>
                  <label className="block text-xs font-mono uppercase font-bold tracking-wider text-[var(--ink-soft)] mb-2 flex items-center gap-2">
                    <KeyIcon className="w-4 h-4 text-[var(--sakura-dark)]" />
                    <span>API Key Credentials</span>
                  </label>
                  <input
                    type="password"
                    value={apiKey}
                    onChange={(e) => setApiKey(e.target.value)}
                    placeholder="sk-..."
                    className="w-full px-5 py-3.5 rounded-2xl bg-[var(--bg-subtle)] border-2 border-transparent text-[var(--ink-main)] font-medium text-[14px] font-mono focus:outline-none focus:border-[var(--periwinkle)] transition-colors placeholder:text-[var(--ink-faint)] focus:bg-[var(--bg-subtle)]"
                  />
                </div>

                <div>
                  <label className="block text-xs font-mono uppercase font-bold tracking-wider text-[var(--ink-soft)] mb-2">
                    Model Name
                  </label>
                  <input
                    type="text"
                    value={modelName}
                    onChange={(e) => setModelName(e.target.value)}
                    placeholder="e.g. deepseek/deepseek-chat or gpt-4o-mini"
                    className="w-full px-5 py-3.5 rounded-2xl bg-[var(--bg-subtle)] border-2 border-transparent text-[var(--ink-main)] font-medium text-[14px] font-mono focus:outline-none focus:border-[var(--periwinkle)] transition-colors focus:bg-[var(--bg-subtle)]"
                  />
                </div>

                <div>
                  <div className="flex items-center justify-between mb-2">
                    <label className="text-xs font-mono uppercase font-bold tracking-wider text-[var(--ink-soft)] flex items-center gap-2">
                      <AdjustmentsHorizontalIcon className="w-4 h-4 text-[var(--gold-dark)]" />
                      <span>Creativity Temperature</span>
                    </label>
                    <span className="text-xs font-mono text-[var(--periwinkle-dark)] font-bold">{temperature}</span>
                  </div>
                  <input
                    type="range"
                    min="0"
                    max="1.2"
                    step="0.05"
                    value={temperature}
                    onChange={(e) => setTemperature(parseFloat(e.target.value))}
                    className="w-full accent-[var(--periwinkle-dark)] cursor-pointer h-2 bg-[var(--line-2)] rounded-lg appearance-none mt-3"
                  />
                </div>

                {provider === 'custom' && (
                  <div className="col-span-1 md:col-span-2">
                    <label className="block text-xs font-mono uppercase font-bold tracking-wider text-[var(--ink-soft)] mb-2 flex items-center gap-2">
                      <GlobeAltIcon className="w-4 h-4 text-[var(--periwinkle-dark)]" />
                      <span>Custom Provider Base URL</span>
                    </label>
                    <input
                      type="text"
                      value={baseUrl}
                      onChange={(e) => setBaseUrl(e.target.value)}
                      placeholder="http://localhost:11434/v1 or https://api.custom.com/v1"
                      className="w-full px-5 py-3.5 rounded-2xl bg-[var(--bg-subtle)] border-2 border-transparent text-[var(--ink-main)] font-medium text-[14px] font-mono focus:outline-none focus:border-[var(--periwinkle)] transition-colors placeholder:text-[var(--ink-faint)]"
                    />
                  </div>
                )}
              </div>

              <div className="pt-6 border-t border-[var(--line)] flex flex-wrap items-center justify-between gap-4">
                <button
                  type="button"
                  onClick={handleTestConnection}
                  disabled={testing}
                  className="pill-btn pill-btn-secondary px-6 py-3 text-[14px] flex items-center justify-center gap-2 disabled:opacity-50 shadow-sm"
                >
                  {testing ? <ArrowPathIcon className="w-5 h-5 animate-spin text-[var(--periwinkle-dark)]" /> : <ShieldCheckIcon className="w-5 h-5 text-[var(--ok)]" />}
                  <span>Test Connection</span>
                </button>

                <button
                  type="submit"
                  disabled={loading}
                  className="pill-btn pill-btn-primary px-8 py-3.5 text-[15px] flex items-center justify-center gap-2 shadow-md disabled:opacity-50"
                >
                  {loading ? 'Saving...' : 'Save Configuration'}
                </button>
              </div>

              {testResult && (
                <div className={`p-4 rounded-2xl text-sm font-medium shadow-sm font-mono flex items-center gap-2 ${
                  testResult.status === 'ok' ? 'bg-[rgba(var(--ok-rgb),0.1)] border border-[rgba(var(--ok-rgb),0.3)] text-[var(--ok)]' : 'bg-[rgba(var(--danger-rgb),0.12)] border border-[rgba(var(--danger-rgb),0.3)] text-[var(--danger)]'
                }`}>
                  {testResult.message}
                </div>
              )}
            </form>
          )}
        </div>

        {/* Card 3: Scenes */}
        <div
          onClick={() => setActiveSection(activeSection === 'scenes' ? null : 'scenes')}
          className={`story-card p-7 md:p-8 rounded-3xl cursor-pointer relative overflow-hidden transition-all group ${
            activeSection === 'scenes' ? 'border-2 border-[var(--periwinkle)] bg-[var(--bg-surface)] shadow-lg' : 'border border-[var(--line)] bg-[var(--bg-surface)] hover:border-[var(--line-2)] hover:shadow-md'
          }`}
        >
          <div className="flex items-center justify-between relative z-10">
            <div className="space-y-1.5">
              <h3 className="text-xl font-bold text-[var(--ink-main)] font-[var(--font-display)] flex items-center gap-3">
                <span>Scenes</span>
                <ChevronDownIcon className={`w-5 h-5 text-[var(--ink-soft)] transition-transform duration-300 ${activeSection === 'scenes' ? 'rotate-180 text-[var(--periwinkle-dark)]' : ''}`} />
              </h3>
              <p className="text-sm text-[var(--ink-soft)] font-medium">Customize the virtual environment for your characters.</p>
            </div>
          </div>
          <ChatBubbleLeftRightIcon className="w-28 h-28 text-[var(--gold)] opacity-10 absolute -right-4 -bottom-6 pointer-events-none group-hover:scale-105 transition-transform duration-500" />
          
          {activeSection === 'scenes' && (
            <div className="mt-6 pt-6 border-t border-[var(--line)] space-y-4 animate-fade-in relative z-10">
              <p className="font-semibold text-[var(--periwinkle-dark)] font-[var(--font-display)] text-sm">Spatial Map & Boundary Check:</p>
              <div className="p-5 rounded-2xl bg-[var(--bg-subtle)] border border-[var(--line-2)] text-[13px] text-[var(--ink-soft)] font-medium shadow-inner">
                Normalized coordinates (0-100), Fog of war rendering, Zone prefix matching.
              </div>
            </div>
          )}
        </div>

        {/* Card 4: Engine Models */}
        <div
          onClick={() => setActiveSection(activeSection === 'models' ? null : 'models')}
          className={`story-card p-7 md:p-8 rounded-3xl cursor-pointer relative overflow-hidden transition-all group ${
            activeSection === 'models' ? 'border-2 border-[var(--periwinkle)] bg-[var(--bg-surface)] shadow-lg' : 'border border-[var(--line)] bg-[var(--bg-surface)] hover:border-[var(--line-2)] hover:shadow-md'
          }`}
        >
          <div className="flex items-center justify-between relative z-10">
            <div className="space-y-1.5">
              <h3 className="text-xl font-bold text-[var(--ink-main)] font-[var(--font-display)] flex items-center gap-3">
                <span>Engine Models</span>
                <ChevronDownIcon className={`w-5 h-5 text-[var(--ink-soft)] transition-transform duration-300 ${activeSection === 'models' ? 'rotate-180 text-[var(--periwinkle-dark)]' : ''}`} />
              </h3>
              <p className="text-sm text-[var(--ink-soft)] font-medium">Live2D, VRM, Spine, MMD, Sonder Engine Psychology, etc.</p>
            </div>
          </div>
          <CpuChipIcon className="w-28 h-28 text-[var(--periwinkle-dark)] opacity-10 absolute -right-4 -bottom-6 pointer-events-none group-hover:scale-105 transition-transform duration-500" />
          
          {activeSection === 'models' && (
            <div className="mt-6 pt-6 border-t border-[var(--line)] space-y-4 animate-fade-in relative z-10">
              <p className="font-semibold text-[var(--periwinkle-dark)] font-[var(--font-display)] text-sm">Psychology Runtime Modules:</p>
              <div className="p-5 rounded-2xl bg-[var(--bg-subtle)] border border-[var(--line-2)] text-[13px] text-[var(--ink-soft)] font-medium shadow-inner">
                Hedonic state, stress tracking, cognitive absorption, Theory of Mind per-observer calls.
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
};
