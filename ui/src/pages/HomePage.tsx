import React from 'react';
import { useNavigate } from 'react-router-dom';
import { motion } from 'motion/react';
import { PlayIcon, SparklesIcon, BookOpenIcon, GlobeAltIcon, ArrowRightIcon } from '@heroicons/react/24/outline';
import { api } from '../api/client';

interface HomePageProps {
  onOpenBuilder?: () => void;
}

export const HomePage: React.FC<HomePageProps> = ({ onOpenBuilder }) => {
  const navigate = useNavigate();

  const handleDemo = async () => {
    try {
      const worlds = await api.worlds.list();
      if (worlds.length > 0) {
        navigate(`/worlds/${worlds[0].name}/play`);
      } else {
        navigate('/worlds');
      }
    } catch {
      navigate('/worlds');
    }
  };

  const containerVariants = {
    hidden: { opacity: 0 },
    show: {
      opacity: 1,
      transition: { staggerChildren: 0.1, delayChildren: 0.1 },
    },
  };

  const itemVariants = {
    hidden: { opacity: 0, y: 20 },
    show: { 
      opacity: 1, 
      y: 0, 
      transition: { type: 'spring' as const, stiffness: 100, damping: 20 } 
    },
  };

  return (
    <div className="min-h-[calc(100vh-70px)] flex flex-col items-center px-6 md:px-12 pt-20 pb-24 max-w-[1200px] mx-auto w-full relative overflow-hidden bg-noise">
      
      {/* Decorative Background Blurs */}
      <div className="absolute top-0 right-0 w-96 h-96 bg-[var(--accent-sage)] opacity-10 blur-[100px] rounded-full pointer-events-none -z-10" />
      <div className="absolute bottom-40 left-0 w-96 h-96 bg-[var(--accent-peach)] opacity-10 blur-[100px] rounded-full pointer-events-none -z-10" />

      <motion.div 
        variants={containerVariants} 
        initial="hidden" 
        animate="show"
        className="w-full flex flex-col gap-16"
      >
        
        {/* Hero Section */}
        <div className="flex flex-col lg:flex-row items-center lg:items-start justify-between gap-12 w-full">
          {/* Left: Text & CTAs */}
          <motion.div variants={itemVariants} className="flex-1 max-w-2xl space-y-8 z-10">
            <h1 className="text-[3.5rem] md:text-[5rem] leading-[1.05] font-bold tracking-tight text-[var(--ink-main)]">
              Interactive <br className="hidden md:block"/> storytelling, <br/> <span className="bg-gradient-to-r from-[var(--periwinkle-dark)] to-[var(--sakura-dark)] bg-clip-text text-transparent">reimagined.</span>
            </h1>
            
            <p className="text-[var(--ink-soft)] text-lg md:text-xl font-medium leading-relaxed max-w-lg">
              A private, local storytelling engine that keeps your canon on track. Build rich worlds, generate scenes, and weave continuous narratives.
            </p>

            <div className="flex flex-wrap items-center gap-4 pt-4">
              <button
                onClick={handleDemo}
                className="pill-btn pill-btn-primary"
              >
                <PlayIcon className="w-5 h-5" />
                <span>Try Live Demo</span>
              </button>

              <button
                onClick={() => {
                  if (onOpenBuilder) onOpenBuilder();
                  else navigate('/worlds?action=create');
                }}
                className="pill-btn pill-btn-secondary"
              >
                <SparklesIcon className="w-5 h-5 text-[var(--periwinkle-dark)]" />
                <span>Build World</span>
              </button>
            </div>
          </motion.div>

          {/* Right: Asymmetric Visual */}
          <motion.div variants={itemVariants} className="flex-1 w-full max-w-md lg:max-w-none relative h-[400px]">
            <div className="absolute inset-0 bg-white/40 backdrop-blur-3xl rounded-3xl border border-[var(--line)] shadow-lg transform rotate-2 hover:rotate-0 transition-transform duration-700 ease-out flex flex-col overflow-hidden">
               {/* Faux UI Header */}
               <div className="h-12 border-b border-[var(--line)] flex items-center px-6 gap-2 bg-white/60">
                 <div className="w-3 h-3 rounded-full bg-[var(--danger)]" />
                 <div className="w-3 h-3 rounded-full bg-[var(--warn)]" />
                 <div className="w-3 h-3 rounded-full bg-[var(--ok)]" />
               </div>
               {/* Faux UI Body */}
               <div className="flex-1 p-8 flex flex-col gap-4 bg-[var(--bg-main)]/50">
                  <div className="w-3/4 h-6 bg-[var(--line-2)] rounded-lg animate-pulse" />
                  <div className="w-full h-4 bg-[var(--line)] rounded-md" />
                  <div className="w-5/6 h-4 bg-[var(--line)] rounded-md" />
                  <div className="mt-auto self-end w-1/3 h-10 bg-[rgba(var(--periwinkle-rgb),0.2)] border border-[var(--periwinkle)] rounded-xl" />
               </div>
            </div>
            
            <div className="absolute -bottom-6 -left-6 bg-white p-5 rounded-2xl shadow-xl border border-[var(--line)] flex items-center gap-4 transform -rotate-3 z-20">
              <div className="w-12 h-12 rounded-full bg-[rgba(var(--sakura-rgb),0.2)] flex items-center justify-center">
                <GlobeAltIcon className="w-6 h-6 text-[var(--sakura-dark)]" />
              </div>
              <div>
                <div className="text-sm font-bold text-[var(--ink-main)]">World Canon</div>
                <div className="text-xs font-medium text-[var(--ink-soft)]">Synchronized</div>
              </div>
            </div>
          </motion.div>
        </div>

        {/* Bento Grid */}
        <motion.div variants={itemVariants} className="w-full pt-16">
          <div className="grid grid-cols-1 md:grid-cols-3 gap-6 auto-rows-[220px]">
            
            {/* Cell 1: Large feature */}
            <div className="md:col-span-2 bg-[var(--bg-surface)] rounded-3xl border border-[var(--line)] p-8 flex flex-col justify-between group hover:border-[var(--line-2)] hover:shadow-md transition-all">
              <div className="w-12 h-12 rounded-2xl bg-[rgba(var(--periwinkle-rgb),0.15)] text-[var(--periwinkle-dark)] flex items-center justify-center mb-4">
                <BookOpenIcon className="w-6 h-6" />
              </div>
              <div>
                <h3 className="text-2xl font-bold text-[var(--ink-main)] mb-2">Lore Management</h3>
                <p className="text-[var(--ink-soft)] font-medium max-w-md">Maintain perfect consistency across chapters with an automated codex and relationship graphs.</p>
              </div>
            </div>

            {/* Cell 2: Actionable feature */}
            <div 
              onClick={() => navigate('/worlds')}
              className="bg-[rgba(var(--sakura-rgb),0.12)] rounded-3xl border border-[rgba(var(--sakura-rgb),0.3)] p-8 flex flex-col justify-between cursor-pointer group hover:bg-[rgba(var(--sakura-rgb),0.22)] transition-all"
            >
              <h3 className="text-xl font-bold text-[var(--sakura-dark)] group-hover:translate-x-1 transition-transform">Explore <br/> Your Worlds</h3>
              <div className="w-10 h-10 rounded-full bg-white flex items-center justify-center shadow-sm self-end text-[var(--sakura-dark)] group-hover:-rotate-45 transition-transform">
                <ArrowRightIcon className="w-5 h-5" />
              </div>
            </div>

            {/* Cell 3: Local Privacy */}
            <div className="bg-[var(--bg-surface)] rounded-3xl border border-[var(--line)] p-8 flex flex-col justify-between group hover:border-[var(--line-2)] hover:shadow-md transition-all">
              <div className="space-y-2">
                <div className="w-full h-2 bg-[var(--line)] rounded-full overflow-hidden">
                  <div className="w-full h-full bg-[var(--periwinkle)]" />
                </div>
                <div className="w-full h-2 bg-[var(--line)] rounded-full overflow-hidden">
                  <div className="w-3/4 h-full bg-[var(--periwinkle)]" />
                </div>
              </div>
              <div>
                <h3 className="text-lg font-bold text-[var(--ink-main)]">100% Local Privacy</h3>
                <p className="text-sm text-[var(--ink-soft)] font-medium mt-1">Your worlds stay on your machine.</p>
              </div>
            </div>

            {/* Cell 4: Custom Models */}
            <div className="md:col-span-2 bg-[var(--bg-main)] rounded-3xl border border-[var(--line)] p-8 flex items-center justify-between group hover:border-[var(--line-2)] hover:shadow-md transition-all relative overflow-hidden">
              <div className="z-10">
                <h3 className="text-2xl font-bold text-[var(--ink-main)] mb-2">Bring Your Own Models</h3>
                <p className="text-[var(--ink-soft)] font-medium max-w-sm">Connect OpenAI, Anthropic, or local LLMs through Ollama. Total control over inference.</p>
              </div>
              {/* Decorative graphic */}
              <div className="absolute right-0 top-0 bottom-0 w-1/3 bg-gradient-to-l from-[var(--bg-surface)] to-transparent opacity-80" />
              <div className="absolute -right-12 -top-12 w-64 h-64 border border-[var(--line-2)] rounded-full opacity-30" />
              <div className="absolute -right-24 -top-24 w-96 h-96 border border-[var(--line)] rounded-full opacity-30" />
            </div>

          </div>
        </motion.div>

      </motion.div>
    </div>
  );
};
