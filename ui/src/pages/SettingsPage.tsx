import React, { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { ChevronLeftIcon, CheckCircleIcon, KeyIcon, CpuChipIcon, AdjustmentsHorizontalIcon, ArrowPathIcon, ShieldCheckIcon, GlobeAltIcon } from '@heroicons/react/24/outline';
import { api } from '../api/client';

export const SettingsPage: React.FC = () => {
  const navigate = useNavigate();

  // Form states
  const [provider, setProvider] = useState('openrouter');
  const [apiKey, setApiKey] = useState('');
  const [apiKeyMasked, setApiKeyMasked] = useState<string | null>(null);
  const [hasApiKey, setHasApiKey] = useState(false);
  const [keySource, setKeySource] = useState('none');
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
        // The backend never returns the raw key; keep the input empty and show
        // the masked value as a hint instead.
        setApiKey('');
        setApiKeyMasked(cfg.api_key_masked ?? null);
        setHasApiKey(Boolean(cfg.has_api_key));
        setKeySource(cfg.api_key_source || 'none');
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

  const buildConfigPayload = () => {
    const trimmedKey = apiKey.trim();
    return {
      llm_provider: provider,
      model_name: modelName,
      base_url: baseUrl,
      temperature,
      ...(trimmedKey
        ? { api_key: trimmedKey, api_key_action: 'replace' as const }
        : { api_key_action: 'keep' as const }),
    };
  };

  const handleSave = async (e: React.FormEvent) => {
    e.preventDefault();
    setLoading(true);
    setSaveSuccess(false);
    try {
      const status = await api.config.update(buildConfigPayload());
      setApiKey('');
      setApiKeyMasked(status?.api_key_masked ?? null);
      setHasApiKey(Boolean(status?.has_api_key));
      setKeySource(status?.api_key_source || 'none');
      setSaveSuccess(true);
      setTimeout(() => setSaveSuccess(false), 3000);
    } catch (err: any) {
      alert(`Save failed: ${err.message}`);
    } finally {
      setLoading(false);
    }
  };

  const handleClearApiKey = async () => {
    setLoading(true);
    setSaveSuccess(false);
    try {
      const status = await api.config.update({ ...buildConfigPayload(), api_key_action: 'delete' });
      setApiKey('');
      setApiKeyMasked(status?.api_key_masked ?? null);
      setHasApiKey(Boolean(status?.has_api_key));
      setKeySource(status?.api_key_source || 'none');
    } catch (err: any) {
      alert(`Clear failed: ${err.message}`);
    } finally {
      setLoading(false);
    }
  };

  const handleTestConnection = async () => {
    setTesting(true);
    setTestResult(null);
    try {
      await api.config.update(buildConfigPayload());
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

      <div className="max-w-4xl">
        <div className="story-card p-7 md:p-8 rounded-3xl border border-[var(--line)] bg-[var(--bg-surface)]">
          <div className="flex items-center justify-between">
            <div className="space-y-1.5">
              <h3 className="text-xl font-bold text-[var(--ink-main)] font-[var(--font-display)]">AI Connection</h3>
              <p className="text-sm text-[var(--ink-soft)] font-medium">Choose the model and manage its connection.</p>
            </div>
          </div>

            <form onSubmit={handleSave} className="mt-6 pt-6 border-t border-[var(--line)] space-y-6">
              {saveSuccess && (
                <div className="p-4 rounded-2xl bg-[rgba(var(--ok-rgb),0.1)] border border-[rgba(var(--ok-rgb),0.3)] text-[var(--ok)] text-sm font-medium flex items-center gap-2 shadow-sm">
                  <CheckCircleIcon className="w-5 h-5" />
                  <span>AI connection saved successfully!</span>
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
                    placeholder={hasApiKey ? `Stored (${apiKeyMasked || 'set'}) — leave blank to keep` : 'sk-...'}
                    autoComplete="new-password"
                    className="w-full px-5 py-3.5 rounded-2xl bg-[var(--bg-subtle)] border-2 border-transparent text-[var(--ink-main)] font-medium text-[14px] font-mono focus:outline-none focus:border-[var(--periwinkle)] transition-colors placeholder:text-[var(--ink-faint)] focus:bg-[var(--bg-subtle)]"
                  />
                  <p className="mt-2 text-xs text-[var(--ink-faint)] font-mono">
                    {hasApiKey
                      ? `Key stored (source: ${keySource}). Leave blank to keep it, or type a new key to replace it.`
                      : 'No key stored yet.'}
                  </p>
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
                <div className="flex flex-wrap items-center gap-3">
                  <button
                    type="button"
                    onClick={handleTestConnection}
                    disabled={testing}
                    className="pill-btn pill-btn-secondary px-6 py-3 text-[14px] flex items-center justify-center gap-2 disabled:opacity-50 shadow-sm"
                  >
                    {testing ? <ArrowPathIcon className="w-5 h-5 animate-spin text-[var(--periwinkle-dark)]" /> : <ShieldCheckIcon className="w-5 h-5 text-[var(--ok)]" />}
                    <span>Test Connection</span>
                  </button>

                  {hasApiKey && (
                    <button
                      type="button"
                      onClick={handleClearApiKey}
                      disabled={loading || testing}
                      className="pill-btn pill-btn-secondary px-6 py-3 text-[14px] flex items-center justify-center gap-2 disabled:opacity-50 shadow-sm text-[var(--danger)]"
                    >
                      <span>Clear Stored Key</span>
                    </button>
                  )}
                </div>

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
        </div>
      </div>
    </div>
  );
};
