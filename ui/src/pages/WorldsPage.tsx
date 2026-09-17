import React, { useEffect, useState } from 'react';
import { useNavigate, useSearchParams } from 'react-router-dom';
import { motion } from 'motion/react';
import { GlobeAltIcon, PlayIcon, TrashIcon, Cog6ToothIcon, SparklesIcon, MagnifyingGlassIcon, ArrowPathIcon } from '@heroicons/react/24/outline';
import { api } from '../api/client';
import type { World } from '../api/client';
import { WorldBuilderModal } from '../components/builder/WorldBuilderModal';
import { CreatorToolsModal } from '../components/creator/CreatorToolsModal';

export const WorldsPage: React.FC = () => {
  const navigate = useNavigate();
  const [searchParams, setSearchParams] = useSearchParams();
  const [worlds, setWorlds] = useState<World[]>([]);
  const [loading, setLoading] = useState(true);
  const [search, setSearch] = useState('');
  const [error, setError] = useState<string | null>(null);

  // Modals
  const [isBuilderOpen, setIsBuilderOpen] = useState(false);
  const [selectedWorldForCreator, setSelectedWorldForCreator] = useState<string | null>(null);

  useEffect(() => {
    loadWorlds();
    if (searchParams.get('action') === 'create') {
      setIsBuilderOpen(true);
    }
  }, [searchParams]);

  const loadWorlds = async () => {
    setLoading(true);
    setError(null);
    try {
      const list = await api.worlds.list();
      setWorlds(list || []);
    } catch (e: any) {
      setError(e.message || 'Failed to load worlds list');
    } finally {
      setLoading(false);
    }
  };

  const handleDeleteWorld = async (name: string, e: React.MouseEvent) => {
    e.stopPropagation();
    if (!confirm(`Are you sure you want to delete world "${name}"?`)) return;
    try {
      await api.worlds.delete(name);
      await loadWorlds();
    } catch (err: any) {
      alert(`Delete failed: ${err.message}`);
    }
  };

  const filteredWorlds = worlds.filter(w =>
    w.name.toLowerCase().includes(search.toLowerCase())
  );

  const containerVariants = {
    hidden: { opacity: 0 },
    show: {
      opacity: 1,
      transition: { staggerChildren: 0.05 },
    },
  };

  const cardVariants = {
    hidden: { opacity: 0, y: 15 },
    show: { opacity: 1, y: 0, transition: { type: 'spring' as const, stiffness: 120, damping: 20 } },
  };

  return (
    <div className="min-h-[calc(100vh-70px)] px-6 md:px-12 py-12 max-w-[1200px] mx-auto space-y-12">
      {/* Top Header Bar */}
      <motion.div initial={{ opacity: 0, y: -10 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.5 }} className="flex flex-col md:flex-row md:items-end justify-between gap-6 pb-8 border-b border-[var(--line)]">
        <div>
          <h1 className="text-[2.5rem] font-bold tracking-tight text-[var(--ink-main)] flex items-center gap-3">
            <GlobeAltIcon className="w-8 h-8 text-[var(--accent-sage)]" />
            <span>Worlds & Canons</span>
          </h1>
          <p className="text-[var(--ink-soft)] font-medium text-lg mt-2 max-w-lg">
            Manage your saved narrative environments.
          </p>
        </div>

        <button
          onClick={() => setIsBuilderOpen(true)}
          className="pill-btn pill-btn-primary px-8 py-3.5 text-[14px] flex items-center gap-2 shadow-sm"
        >
          <SparklesIcon className="w-5 h-5" />
          <span>Create New World</span>
        </button>
      </motion.div>

      {/* Search Bar */}
      <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }} transition={{ duration: 0.5, delay: 0.1 }} className="flex items-center justify-between gap-4">
        <div className="relative flex-1 max-w-md">
          <MagnifyingGlassIcon className="w-5 h-5 absolute left-4 top-1/2 -translate-y-1/2 text-[var(--ink-faint)]" />
          <input
            type="text"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            placeholder="Search worlds..."
            className="w-full pl-11 pr-4 py-3 rounded-full bg-[var(--bg-surface)] border border-[var(--line)] text-[var(--ink-main)] font-medium text-[15px] focus:outline-none focus:border-[var(--accent-sage)] focus:ring-4 focus:ring-[var(--accent-sage)]/10 transition-all placeholder:text-[var(--ink-faint)] shadow-sm"
          />
        </div>
        <div className="text-sm font-medium text-[var(--ink-soft)] bg-[var(--bg-surface)] px-4 py-2 rounded-full border border-[var(--line)] shadow-sm">
          Total: <span className="text-[var(--ink-main)] font-bold">{filteredWorlds.length}</span>
        </div>
      </motion.div>

      {error && (
        <div className="p-4 rounded-2xl bg-[var(--danger)]/10 border border-[var(--danger)]/30 text-[#C95C5C] text-sm font-bold flex items-center gap-2">
          <span>{error}</span>
        </div>
      )}

      {loading ? (
        <div className="flex items-center justify-center py-20 text-[var(--ink-soft)] font-bold gap-3">
          <ArrowPathIcon className="w-5 h-5 animate-spin text-[var(--accent-sage)]" />
          <span>Loading worlds...</span>
        </div>
      ) : filteredWorlds.length === 0 ? (
        <motion.div initial={{ opacity: 0, scale: 0.95 }} animate={{ opacity: 1, scale: 1 }} className="relative overflow-hidden rounded-[2rem] bg-[var(--bg-surface)] border border-[var(--line)] p-12 md:p-24 text-center space-y-6 shadow-sm">
          <div className="absolute top-0 right-0 w-64 h-64 bg-[var(--accent-peach)] opacity-10 blur-3xl rounded-full pointer-events-none" />
          <div className="absolute bottom-0 left-0 w-64 h-64 bg-[var(--accent-lavender)] opacity-10 blur-3xl rounded-full pointer-events-none" />
          
          <div className="relative z-10 w-20 h-20 mx-auto bg-[var(--bg-subtle)] rounded-full flex items-center justify-center border border-[var(--line)]">
            <GlobeAltIcon className="w-8 h-8 text-[var(--ink-soft)]" />
          </div>
          <div className="relative z-10 space-y-2">
            <h3 className="text-2xl font-bold tracking-tight text-[var(--ink-main)]">No Worlds Found</h3>
            <p className="text-[15px] text-[var(--ink-soft)] font-medium max-w-sm mx-auto">
              Initialize a new narrative environment using the World Builder to begin your story.
            </p>
          </div>
          <div className="relative z-10 pt-6 flex justify-center">
            <button
              onClick={() => setIsBuilderOpen(true)}
              className="pill-btn pill-btn-secondary px-8 py-3.5 text-[15px] flex items-center gap-2"
            >
              <SparklesIcon className="w-5 h-5" />
              <span>Initialize New World</span>
            </button>
          </div>
        </motion.div>
      ) : (
        <motion.div variants={containerVariants} initial="hidden" animate="show" className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
          {filteredWorlds.map((w) => (
            <motion.div
              variants={cardVariants}
              key={w.name}
              onClick={() => navigate(`/worlds/${w.name}/play`)}
              className="relative overflow-hidden bg-[var(--bg-surface)] border border-[var(--line)] rounded-3xl p-6 flex flex-col gap-6 shadow-sm hover:shadow-md transition-all duration-300 hover:-translate-y-1 hover:border-[var(--line-2)] cursor-pointer group"
            >
              {/* Header */}
              <div className="flex items-start justify-between z-10">
                <div>
                  <h3 className="text-xl font-bold tracking-tight text-[var(--ink-main)] group-hover:text-[var(--periwinkle-dark)] transition-colors pr-8">
                    {w.name}
                  </h3>
                  <span className="inline-block mt-2 px-3 py-1 rounded-full text-[11px] font-bold tracking-wide bg-[rgba(var(--periwinkle-rgb),0.15)] text-[var(--periwinkle-dark)] uppercase">
                    Active Canon
                  </span>
                </div>
              </div>
              
              {/* Body */}
              <p className="text-[14.5px] leading-relaxed text-[var(--ink-soft)] font-medium z-10 flex-1">
                Story scenes, narrative checkpoints, and spatial maps.
              </p>

              {/* Actions */}
              <div className="flex items-center justify-between pt-4 border-t border-[var(--line)] z-10">
                <div className="flex items-center gap-2">
                  <button
                    onClick={(e) => {
                      e.stopPropagation();
                      setSelectedWorldForCreator(w.name);
                    }}
                    title="Creator Tools"
                    className="p-2.5 rounded-full text-[var(--ink-soft)] hover:text-[#7BA05B] hover:bg-[var(--accent-sage)]/10 transition-colors"
                  >
                    <Cog6ToothIcon className="w-5 h-5" />
                  </button>
                  <button
                    onClick={(e) => handleDeleteWorld(w.name, e)}
                    title="Delete World"
                    className="p-2.5 rounded-full text-[var(--ink-soft)] hover:text-[#C95C5C] hover:bg-[var(--danger)]/10 transition-colors"
                  >
                    <TrashIcon className="w-5 h-5" />
                  </button>
                </div>
                <button
                  onClick={(e) => {
                    e.stopPropagation();
                    navigate(`/worlds/${w.name}/play`);
                  }}
                  className="pill-btn pill-btn-primary px-5 py-2 text-[14px] flex items-center gap-1.5 shadow-sm"
                >
                  <PlayIcon className="w-4 h-4" />
                  <span>Play</span>
                </button>
              </div>

              {/* Decorative Background */}
              <div className="absolute -right-8 -top-8 w-32 h-32 bg-[var(--bg-subtle)] rounded-full border border-[var(--line)] pointer-events-none opacity-50 group-hover:scale-110 group-hover:bg-[var(--accent-sage)]/5 transition-transform duration-700 ease-out" />
            </motion.div>
          ))}
        </motion.div>
      )}

      {/* Modals */}
      <WorldBuilderModal
        isOpen={isBuilderOpen}
        onClose={() => {
          setIsBuilderOpen(false);
          setSearchParams({});
        }}
        onSuccess={() => loadWorlds()}
      />

      {selectedWorldForCreator && (
        <CreatorToolsModal
          worldName={selectedWorldForCreator}
          isOpen={!!selectedWorldForCreator}
          onClose={() => setSelectedWorldForCreator(null)}
        />
      )}
    </div>
  );
};
