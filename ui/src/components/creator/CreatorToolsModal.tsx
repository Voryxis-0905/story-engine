import React, { useState, useEffect, useCallback } from 'react';
import { XMarkIcon, DocumentArrowDownIcon, SwatchIcon, TagIcon, BookOpenIcon, ArrowDownTrayIcon, ArrowPathIcon } from '@heroicons/react/24/outline';
import { api } from '../../api/client';
import { WORLD_RESTORED_EVENT } from '../../features/play/types';

interface CreatorToolsModalProps {
  worldName: string;
  isOpen: boolean;
  onClose: () => void;
}

type Tab = 'saves' | 'style' | 'traits' | 'canon' | 'export';

export const CreatorToolsModal: React.FC<CreatorToolsModalProps> = ({ worldName, isOpen, onClose }) => {
  const [activeTab, setActiveTab] = useState<Tab>('saves');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Saves tab state
  const [saves, setSaves] = useState<any[]>([]);
  const [saveLabel, setSaveLabel] = useState('');

  // Style card state
  const [styleCard, setStyleCard] = useState<any>(null);

  // Traits state
  const [traits, setTraits] = useState<any>(null);

  // Canon log state
  const [canonLog, setCanonLog] = useState<any[]>([]);

  // Export state
  const [exportData, setExportData] = useState<string | null>(null);

  const loadTabData = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      if (activeTab === 'saves') {
        const list = await api.creator.saves.list(worldName);
        setSaves(Array.isArray(list) ? list : (list as any)?.saves || []);
      } else if (activeTab === 'style') {
        const sc = await api.creator.styleCard.get(worldName);
        setStyleCard(sc || {});
      } else if (activeTab === 'traits') {
        const tr = await api.creator.traits.get(worldName);
        setTraits(tr || {});
      } else if (activeTab === 'canon') {
        const cl = await api.creator.canonLog.get(worldName);
        setCanonLog(Array.isArray(cl) ? cl : (cl as any)?.facts || []);
      } else if (activeTab === 'export') {
        const exp = await api.creator.export(worldName);
        setExportData(JSON.stringify(exp, null, 2));
      }
    } catch (e: any) {
      setError(e.message || 'Failed to load creator tool data');
    } finally {
      setLoading(false);
    }
  }, [activeTab, worldName]);

  useEffect(() => {
    if (isOpen && worldName) {
      loadTabData();
    }
  }, [isOpen, worldName, loadTabData]);

  const handleCreateSave = async () => {
    if (!saveLabel.trim()) return;
    setLoading(true);
    try {
      await api.creator.saves.create(worldName, saveLabel.trim());
      setSaveLabel('');
      await loadTabData();
    } catch (e: any) {
      setError(e.message || 'Failed to create save checkpoint');
    } finally {
      setLoading(false);
    }
  };

  const handleRestoreSave = async (saveId: string) => {
    if (!confirm('Restore world to this save point?')) return;
    setLoading(true);
    try {
      await api.creator.saves.restore(worldName, saveId);
      window.dispatchEvent(new CustomEvent(WORLD_RESTORED_EVENT, { detail: { worldName } }));
      alert('Save restored successfully!');
      onClose();
    } catch (e: any) {
      setError(e.message || 'Failed to restore save');
    } finally {
      setLoading(false);
    }
  };

  if (!isOpen) return null;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/80 backdrop-blur-md animate-fade-in">
      <div className="glass-panel w-full max-w-4xl bg-[#0d1322] border-white/10 rounded-2xl shadow-2xl overflow-hidden flex flex-col h-[80vh]">
        {/* Header */}
        <div className="px-6 py-4 border-b border-white/[0.08] flex items-center justify-between bg-white/[0.02]">
          <div className="flex items-center gap-3">
            <h2 className="text-lg font-bold text-white">Creator Tools — <span className="text-teal-400">{worldName}</span></h2>
          </div>
          <button onClick={onClose} className="p-1 rounded-lg text-slate-400 hover:text-white hover:bg-white/10">
            <XMarkIcon className="w-5 h-5" />
          </button>
        </div>

        {/* Modal Container */}
        <div className="flex flex-1 overflow-hidden">
          {/* Left Navigation */}
          <div className="w-48 bg-white/[0.02] border-r border-white/[0.06] p-3 space-y-1">
            <button
              onClick={() => setActiveTab('saves')}
              className={`w-full flex items-center gap-2 px-3 py-2 rounded-lg text-xs font-semibold uppercase tracking-wider transition-all ${
                activeTab === 'saves' ? 'bg-teal-500/15 text-teal-300 border border-teal-500/30' : 'text-slate-400 hover:text-slate-200'
              }`}
            >
              <DocumentArrowDownIcon className="w-4 h-4" />
              <span>Saves & Branch</span>
            </button>
            <button
              onClick={() => setActiveTab('style')}
              className={`w-full flex items-center gap-2 px-3 py-2 rounded-lg text-xs font-semibold uppercase tracking-wider transition-all ${
                activeTab === 'style' ? 'bg-teal-500/15 text-teal-300 border border-teal-500/30' : 'text-slate-400 hover:text-slate-200'
              }`}
            >
              <SwatchIcon className="w-4 h-4" />
              <span>Style Card</span>
            </button>
            <button
              onClick={() => setActiveTab('traits')}
              className={`w-full flex items-center gap-2 px-3 py-2 rounded-lg text-xs font-semibold uppercase tracking-wider transition-all ${
                activeTab === 'traits' ? 'bg-teal-500/15 text-teal-300 border border-teal-500/30' : 'text-slate-400 hover:text-slate-200'
              }`}
            >
              <TagIcon className="w-4 h-4" />
              <span>Traits</span>
            </button>
            <button
              onClick={() => setActiveTab('canon')}
              className={`w-full flex items-center gap-2 px-3 py-2 rounded-lg text-xs font-semibold uppercase tracking-wider transition-all ${
                activeTab === 'canon' ? 'bg-teal-500/15 text-teal-300 border border-teal-500/30' : 'text-slate-400 hover:text-slate-200'
              }`}
            >
              <BookOpenIcon className="w-4 h-4" />
              <span>Canon Log</span>
            </button>
            <button
              onClick={() => setActiveTab('export')}
              className={`w-full flex items-center gap-2 px-3 py-2 rounded-lg text-xs font-semibold uppercase tracking-wider transition-all ${
                activeTab === 'export' ? 'bg-teal-500/15 text-teal-300 border border-teal-500/30' : 'text-slate-400 hover:text-slate-200'
              }`}
            >
              <ArrowDownTrayIcon className="w-4 h-4" />
              <span>Export</span>
            </button>
          </div>

          {/* Right Content Area */}
          <div className="flex-1 p-6 overflow-y-auto">
            {error && <div className="p-3 mb-4 rounded bg-red-500/10 border border-red-500/30 text-red-400 text-sm">{error}</div>}

            {loading ? (
              <div className="flex items-center justify-center h-full text-slate-400 gap-2">
                <ArrowPathIcon className="w-6 h-6 animate-spin text-teal-400" />
                <span>Loading creator tools...</span>
              </div>
            ) : (
              <>
                {activeTab === 'saves' && (
                  <div className="space-y-6">
                    <div className="flex gap-2">
                      <input
                        type="text"
                        value={saveLabel}
                        onChange={(e) => setSaveLabel(e.target.value)}
                        placeholder="Save label (e.g. Before Boss Fight)"
                        className="flex-1 px-4 py-2 rounded-lg bg-white/[0.04] border border-white/10 text-white text-sm focus:outline-none focus:border-teal-400"
                      />
                      <button
                        onClick={handleCreateSave}
                        disabled={!saveLabel.trim()}
                        className="px-4 py-2 bg-teal-500 text-slate-950 font-bold text-sm rounded-lg hover:bg-teal-400 disabled:opacity-50"
                      >
                        Create Save
                      </button>
                    </div>

                    <div className="space-y-3">
                      <h4 className="text-xs font-mono uppercase text-slate-400">Available Checkpoints</h4>
                      {saves.length === 0 ? (
                        <p className="text-sm text-slate-500">No saves created yet.</p>
                      ) : (
                        saves.map((s: any) => (
                          <div key={s.id} className="p-4 rounded-xl bg-white/[0.03] border border-white/[0.08] flex items-center justify-between">
                            <div>
                              <div className="font-bold text-white text-sm">{s.label || s.id}</div>
                              <div className="text-xs text-slate-400 font-mono">{new Date(s.timestamp * 1000).toLocaleString()}</div>
                            </div>
                            <button
                              onClick={() => handleRestoreSave(s.id)}
                              className="px-3 py-1.5 rounded bg-teal-500/15 border border-teal-500/30 text-teal-300 text-xs font-semibold hover:bg-teal-500/30"
                            >
                              Restore
                            </button>
                          </div>
                        ))
                      )}
                    </div>
                  </div>
                )}

                {activeTab === 'style' && (
                  <div className="space-y-4">
                    <h3 className="text-sm font-bold text-white">Narrative Style Card</h3>
                    <pre className="p-4 rounded-xl bg-black/40 border border-white/10 text-xs font-mono text-teal-300 overflow-x-auto">
                      {JSON.stringify(styleCard, null, 2)}
                    </pre>
                  </div>
                )}

                {activeTab === 'traits' && (
                  <div className="space-y-4">
                    <h3 className="text-sm font-bold text-white">World & Entity Traits</h3>
                    <pre className="p-4 rounded-xl bg-black/40 border border-white/10 text-xs font-mono text-cyan-300 overflow-x-auto">
                      {JSON.stringify(traits, null, 2)}
                    </pre>
                  </div>
                )}

                {activeTab === 'canon' && (
                  <div className="space-y-4">
                    <h3 className="text-sm font-bold text-white">Canon Event Log</h3>
                    {canonLog.length === 0 ? (
                      <p className="text-sm text-slate-500">No canon entries recorded.</p>
                    ) : (
                      <div className="space-y-2">
                        {canonLog.map((c: any, i: number) => (
                          <div key={i} className="p-3 rounded bg-white/[0.03] border border-white/10 text-xs text-slate-300 font-serif">
                            {typeof c === 'string' ? c : JSON.stringify(c)}
                          </div>
                        ))}
                      </div>
                    )}
                  </div>
                )}

                {activeTab === 'export' && (
                  <div className="space-y-4">
                    <div className="flex items-center justify-between">
                      <h3 className="text-sm font-bold text-white">Exported World JSON Bundle</h3>
                      <button
                        onClick={() => {
                          const blob = new Blob([exportData || ''], { type: 'application/json' });
                          const url = URL.createObjectURL(blob);
                          const a = document.createElement('a');
                          a.href = url;
                          a.download = `${worldName}_export.json`;
                          a.click();
                        }}
                        className="px-3 py-1.5 bg-teal-500 text-slate-950 font-bold text-xs rounded hover:bg-teal-400"
                      >
                        Download File
                      </button>
                    </div>
                    <textarea
                      readOnly
                      value={exportData || ''}
                      rows={14}
                      className="w-full p-4 rounded-xl bg-black/50 border border-white/10 text-xs font-mono text-slate-300 resize-none focus:outline-none"
                    />
                  </div>
                )}
              </>
            )}
          </div>
        </div>
      </div>
    </div>
  );
};
