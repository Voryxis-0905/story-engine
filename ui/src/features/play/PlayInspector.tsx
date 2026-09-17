import type { PlaySession } from './usePlaySession';
import { BoltIcon, BookOpenIcon, BriefcaseIcon, EyeIcon, FireIcon, MapIcon, UserIcon, XMarkIcon } from '@heroicons/react/24/outline';
import { LocationMap } from '../../components/LocationMap';
import { CodexGraph } from '../../components/CodexGraph';

type Props = Pick<PlaySession, 'playState' | 'activeDrawer' | 'setActiveDrawer' | 'locations' | 'affinityGraph' | 'protagonist'>;

export function PlayInspector({ playState, activeDrawer, setActiveDrawer, locations, affinityGraph, protagonist }: Props) {
  return (<>
      {/* RIGHT ICON STRIP & SLIDE-IN DRAWERS */}
      <div className="flex z-20 h-full shrink-0">
        {/* Active Drawer Panel */}
        {activeDrawer && (
          <div className="w-96 glass-panel rounded-none border-y-0 border-r-0 p-6 flex flex-col h-full animate-slide-in-right shadow-[var(--shadow-md)]">
            <div className="flex items-center justify-between pb-4 border-b border-[var(--line-2)] mb-6">
              <h3 className="text-[15px] font-bold text-[var(--ink-main)] uppercase tracking-wider font-mono flex items-center gap-2">
                {activeDrawer === 'inventory' && <BriefcaseIcon   className="w-5 h-5 text-[var(--accent-peach)]" />}
                {activeDrawer === 'map' && <MapIcon   className="w-5 h-5 text-[var(--accent-sage)]" />}
                {activeDrawer === 'codex' && <BookOpenIcon   className="w-5 h-5 text-[var(--gold-dark)]" />}
                {activeDrawer === 'status' && <UserIcon   className="w-5 h-5 text-[var(--ok)]" />}
                {activeDrawer === 'skills' && <BoltIcon   className="w-5 h-5 text-[var(--warn)]" />}
                {activeDrawer === 'foreshadowing' && <EyeIcon   className="w-5 h-5 text-[var(--danger)]" />}
                <span>{activeDrawer}</span>
              </h3>
              <button
                onClick={() => setActiveDrawer(null)}
                className="p-1.5 rounded-lg text-[var(--ink-soft)] hover:text-[var(--ink-main)] hover:bg-[var(--bg-subtle)] transition-colors"
              >
                <XMarkIcon className="w-5 h-5" />
              </button>
            </div>

            <div className="flex-1 overflow-y-auto space-y-4">
              {/* 1. Inventory Drawer */}
              {activeDrawer === 'inventory' && (
                <div className="space-y-3">
                  {playState?.unlocked_cards?.filter((c: any) => c.type === 'item').length === 0 ? (
                    <p className="text-xs font-bold text-[var(--ink-soft)] text-center py-6">No items in inventory.</p>
                  ) : (
                    playState?.unlocked_cards?.filter((c: any) => c.type === 'item').map((item: any) => (
                      <div key={item.id} className="p-4 rounded-2xl bg-[var(--bg-surface)] border border-[var(--line)] shadow-sm space-y-1.5">
                        <div className="flex items-center justify-between">
                          <span className="font-bold text-[15px] text-[var(--ink-main)]">{item.name}</span>
                          <span className="px-2 py-0.5 rounded-full font-mono text-[10px] font-bold bg-[var(--bg-subtle)] text-[var(--accent-sage)] border border-[var(--line)]">{item.rarity || 'Common'}</span>
                        </div>
                        <p className="text-[13px] text-[var(--ink-soft)] font-medium leading-relaxed">{item.content}</p>
                      </div>
                    ))
                  )}
                </div>
              )}

              {/* 2. Map Drawer */}
              {activeDrawer === 'map' && (
                <div className="space-y-4">
                  <LocationMap locations={locations} />
                </div>
              )}

              {/* 3. Codex Drawer */}
              {activeDrawer === 'codex' && (
                <div className="space-y-6">
                  <div className="h-64 rounded-2xl border-2 border-[var(--line)] overflow-hidden shadow-inner bg-[var(--bg-surface)]">
                    <CodexGraph nodes={affinityGraph.nodes} edges={affinityGraph.edges} />
                  </div>

                  <div className="space-y-3">
                    <h4 className="text-[11px] font-mono uppercase font-bold text-[var(--ink-soft)] pl-1">Unlocked Lore Cards</h4>
                    {playState?.unlocked_cards?.map((card: any) => (
                      <div key={card.id} className="p-4 rounded-2xl bg-[var(--bg-surface)] border border-[var(--line)] shadow-sm space-y-1.5">
                        <div className="flex items-center justify-between">
                          <span className="font-bold text-[14px] text-[var(--ink-main)] font-[var(--font-display)]">{card.name}</span>
                          <span className="px-2 py-0.5 rounded-full font-mono text-[10px] font-bold bg-[rgba(var(--sakura-rgb),0.15)] text-[var(--accent-peach)] border border-[rgba(var(--sakura-rgb),0.3)]">{card.type}</span>
                        </div>
                        <p className="text-[13px] text-[var(--ink-soft)] font-medium leading-relaxed">{card.content}</p>
                      </div>
                    ))}
                  </div>
                </div>
              )}

              {/* 4. Status Drawer */}
              {activeDrawer === 'status' && protagonist && (
                <div className="space-y-4">
                  <div className="p-5 rounded-2xl bg-[var(--bg-surface)] border border-[var(--line)] shadow-sm space-y-4">
                    <div className="text-xl font-bold text-[var(--ink-main)] font-[var(--font-display)]">{protagonist.name}</div>
                    <div className="grid grid-cols-2 gap-3 text-[13px] font-mono font-bold">
                      <div className="p-3 rounded-xl bg-[var(--bg-subtle)] border border-[var(--line)]">
                        <span className="text-[var(--ink-soft)] block uppercase text-[10px] tracking-wider mb-1">Realm</span>
                        <span className="text-[var(--accent-sage)]">{protagonist.power_stat?.realm || 'Mortal'}</span>
                      </div>
                      <div className="p-3 rounded-xl bg-[var(--bg-subtle)] border border-[var(--line)]">
                        <span className="text-[var(--ink-soft)] block uppercase text-[10px] tracking-wider mb-1">EXP</span>
                        <span className="text-[var(--accent-peach)]">{protagonist.power_stat?.exp || 0}</span>
                      </div>
                    </div>
                  </div>

                  {/* Knowledge Flags */}
                  {protagonist.knowledge_flags?.length > 0 && (
                    <div className="space-y-2 pt-2">
                      <h4 className="text-[11px] font-mono uppercase font-bold text-[var(--ink-soft)] pl-1">Knowledge Flags</h4>
                      {protagonist.knowledge_flags.map((flag: string) => (
                        <div key={flag} className="p-2.5 rounded-xl bg-[var(--bg-surface)] border border-[var(--line)] text-[12px] text-[var(--ink-main)] font-mono font-bold shadow-sm">
                          ◆ {flag}
                        </div>
                      ))}
                    </div>
                  )}
                </div>
              )}

              {/* 5. Skills Drawer */}
              {activeDrawer === 'skills' && (
                <div className="space-y-3">
                  {protagonist?.power_stat?.known_skills?.map((skill: string) => (
                    <div key={skill} className="p-3.5 rounded-2xl bg-[var(--bg-surface)] border border-[var(--line)] shadow-sm text-[14px] font-bold text-[var(--ink-main)] flex items-center gap-3">
                      <FireIcon   className="w-5 h-5 text-[var(--gold-dark)]" />
                      <span>{skill}</span>
                    </div>
                  ))}
                </div>
              )}

              {/* 6. Foreshadowing Drawer */}
              {activeDrawer === 'foreshadowing' && (
                <div className="space-y-3">
                  {playState?.foreshadowing_tracker?.length === 0 ? (
                    <p className="text-xs font-bold text-[var(--ink-soft)] text-center py-6">No active foreshadowings.</p>
                  ) : (
                    playState?.foreshadowing_tracker?.map((f: any, i: number) => (
                      <div key={i} className="p-4 rounded-2xl bg-[var(--bg-surface)] border border-[var(--line)] shadow-sm space-y-1.5">
                        <div className="text-[14px] font-bold text-[var(--danger)] font-[var(--font-display)]">{f.title || f.id}</div>
                        <p className="text-[13px] text-[var(--ink-soft)] font-medium leading-relaxed">{f.description || JSON.stringify(f)}</p>
                      </div>
                    ))
                  )}
                </div>
              )}
            </div>
          </div>
        )}

        {/* Right Vertical Icon Strip */}
        <div className="w-16 glass-panel border-y-0 border-r-0 flex flex-col items-center py-6 space-y-5 z-10 shadow-sm">
          <button
            onClick={() => setActiveDrawer(activeDrawer === 'inventory' ? null : 'inventory')}
            title="Inventory"
            className={`p-2.5 rounded-2xl transition-all ${
              activeDrawer === 'inventory' ? 'bg-[var(--bg-subtle)] text-[var(--periwinkle-dark)] border border-[var(--line-2)] shadow-sm' : 'text-[var(--ink-main)]/70 hover:text-[var(--ink-main)] hover:bg-[var(--bg-subtle)] border border-transparent'
            }`}
          >
            <BriefcaseIcon className="w-5 h-5" />
          </button>

          <button
            onClick={() => setActiveDrawer(activeDrawer === 'map' ? null : 'map')}
            title="World Map"
            className={`p-2.5 rounded-2xl transition-all ${
              activeDrawer === 'map' ? 'bg-[var(--bg-subtle)] text-[var(--periwinkle-dark)] border border-[var(--line-2)] shadow-sm' : 'text-[var(--ink-main)]/70 hover:text-[var(--ink-main)] hover:bg-[var(--bg-subtle)] border border-transparent'
            }`}
          >
            <MapIcon className="w-5 h-5" />
          </button>

          <button
            onClick={() => setActiveDrawer(activeDrawer === 'codex' ? null : 'codex')}
            title="Codex & Affinity Graph"
            className={`p-2.5 rounded-2xl transition-all ${
              activeDrawer === 'codex' ? 'bg-[var(--bg-subtle)] text-[var(--periwinkle-dark)] border border-[var(--line-2)] shadow-sm' : 'text-[var(--ink-main)]/70 hover:text-[var(--ink-main)] hover:bg-[var(--bg-subtle)] border border-transparent'
            }`}
          >
            <BookOpenIcon className="w-5 h-5" />
          </button>

          <button
            onClick={() => setActiveDrawer(activeDrawer === 'status' ? null : 'status')}
            title="Protagonist Status"
            className={`p-2.5 rounded-2xl transition-all ${
              activeDrawer === 'status' ? 'bg-[var(--bg-subtle)] text-[var(--periwinkle-dark)] border border-[var(--line-2)] shadow-sm' : 'text-[var(--ink-main)]/70 hover:text-[var(--ink-main)] hover:bg-[var(--bg-subtle)] border border-transparent'
            }`}
          >
            <UserIcon className="w-5 h-5" />
          </button>

          <button
            onClick={() => setActiveDrawer(activeDrawer === 'skills' ? null : 'skills')}
            title="Known Skills"
            className={`p-2.5 rounded-2xl transition-all ${
              activeDrawer === 'skills' ? 'bg-[var(--bg-subtle)] text-[var(--periwinkle-dark)] border border-[var(--line-2)] shadow-sm' : 'text-[var(--ink-main)]/70 hover:text-[var(--ink-main)] hover:bg-[var(--bg-subtle)] border border-transparent'
            }`}
          >
            <BoltIcon className="w-5 h-5" />
          </button>

          <button
            onClick={() => setActiveDrawer(activeDrawer === 'foreshadowing' ? null : 'foreshadowing')}
            title="Foreshadowing Tracker"
            className={`p-2.5 rounded-2xl transition-all ${
              activeDrawer === 'foreshadowing' ? 'bg-[var(--bg-subtle)] text-[var(--periwinkle-dark)] border border-[var(--line-2)] shadow-sm' : 'text-[var(--ink-main)]/70 hover:text-[var(--ink-main)] hover:bg-[var(--bg-subtle)] border border-transparent'
            }`}
          >
            <EyeIcon className="w-5 h-5" />
          </button>
        </div>
      </div>
  </>);
}
