import { lazy, Suspense } from 'react';
import type { PlaySession } from './usePlaySession';
import { BoltIcon, BookOpenIcon, BriefcaseIcon, EyeIcon, FireIcon, FlagIcon, MapIcon, NewspaperIcon, UserIcon, XMarkIcon } from '@heroicons/react/24/outline';
import { LocationMap } from '../../components/LocationMap';
import type { InventoryItem } from '../../api/client';

// The affinity graph pulls in a heavy graph library; load it only when the
// Codex drawer is opened.
const CodexGraph = lazy(() => import('../../components/CodexGraph').then((m) => ({ default: m.CodexGraph })));

type Props = Pick<PlaySession, 'playState' | 'activeDrawer' | 'setActiveDrawer' | 'locations' | 'affinityGraph' | 'protagonist' | 'quests' | 'journal' | 'handleTravelTo' | 'handlePreviewTravel' | 'travelPreview' | 'previewLoading' | 'handleItemAction' | 'handleContinueJourney' | 'handleAbandonJourney'>;

export function PlayInspector({ playState, activeDrawer, setActiveDrawer, locations, affinityGraph, protagonist, quests, journal, handleTravelTo, handlePreviewTravel, travelPreview, previewLoading, handleItemAction, handleContinueJourney, handleAbandonJourney }: Props) {
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
                {activeDrawer === 'quests' && <FlagIcon   className="w-5 h-5 text-[var(--accent-sage)]" />}
                {activeDrawer === 'journal' && <NewspaperIcon   className="w-5 h-5 text-[var(--ink-soft)]" />}
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
                  {!protagonist?.inventory?.length ? (
                    <p className="text-xs font-bold text-[var(--ink-soft)] text-center py-6">No items in inventory.</p>
                  ) : (
                    protagonist.inventory.map((item: InventoryItem) => (
                      <div key={item.instance_id} className="p-4 rounded-2xl bg-[var(--bg-surface)] border border-[var(--line)] shadow-sm space-y-2">
                        <div className="flex items-center justify-between">
                          <span className="font-bold text-[15px] text-[var(--ink-main)]">{item.name}</span>
                          <span className="px-2 py-0.5 rounded-full font-mono text-[10px] font-bold bg-[var(--bg-subtle)] text-[var(--accent-sage)] border border-[var(--line)]">{item.quantity > 1 ? `×${item.quantity}` : item.category}</span>
                        </div>
                        {item.description && <p className="text-[13px] text-[var(--ink-soft)] leading-relaxed">{item.description}</p>}
                        {Object.keys(item.attributes || {}).length > 0 && (
                          <div className="grid grid-cols-2 gap-1 text-[11px] font-mono">
                            {Object.entries(item.attributes).map(([key, value]) => <div key={key}><span className="text-[var(--ink-faint)]">{key}:</span> {String(value)}</div>)}
                          </div>
                        )}
                        {(item.abilities || []).map((ability: any, index: number) => (
                          <div key={ability.name || index} className="rounded-lg border border-[var(--line)] bg-[var(--bg-subtle)] p-2 text-[11px]">
                            <div className="font-bold text-[var(--periwinkle-dark)]">{ability.name || String(ability)}</div>
                            {ability.effect && <div className="text-[var(--ink-soft)]">{ability.effect}</div>}
                          </div>
                        ))}
                        <div className="flex gap-2 text-[10px] font-mono text-[var(--ink-faint)]">
                          <span>{item.condition}</span>{item.equipped && <span>equipped</span>}{item.charges !== null && item.charges !== undefined && <span>{item.charges} charges</span>}
                        </div>
                        <div className="flex flex-wrap gap-1 pt-1">
                          {(['Inspect', 'Use'] as const).map((verb) => (
                            <button key={verb} type="button" onClick={() => handleItemAction(verb, item)} className="rounded-lg border border-[var(--line)] px-2 py-1 text-[10px] font-bold">{verb}</button>
                          ))}
                          <button type="button" onClick={() => handleItemAction(item.equipped ? 'Unequip' : 'Equip', item)} className="rounded-lg border border-[var(--line)] px-2 py-1 text-[10px] font-bold">{item.equipped ? 'Unequip' : 'Equip'}</button>
                          <button type="button" onClick={() => {
                            const important = item.tags?.some((tag) => ['important', 'key_item', 'quest'].includes(tag));
                            if (!important || window.confirm(`Drop ${item.name}?`)) handleItemAction('Drop', item);
                          }} className="rounded-lg border border-[var(--danger)] px-2 py-1 text-[10px] font-bold text-[var(--danger)]">Drop</button>
                        </div>
                      </div>
                    ))
                  )}
                </div>
              )}

              {/* 2. Map Drawer */}
              {activeDrawer === 'map' && (
                <div className="space-y-4">
                  {playState?.active_journey?.status === 'interrupted' && (
                    <div className="rounded-xl border border-[var(--warn)] bg-[var(--bg-surface)] p-3 text-xs space-y-2">
                      <div className="font-bold">Journey interrupted on the way to {playState.active_journey.destination}</div>
                      <button type="button" onClick={handleContinueJourney} className="rounded-lg bg-[var(--periwinkle-dark)] px-3 py-2 font-bold text-white">Continue journey</button>
                      <button type="button" onClick={handleAbandonJourney} className="ml-2 rounded-lg border border-[var(--line)] px-3 py-2 font-bold">Abandon</button>
                    </div>
                  )}
                  <LocationMap locations={locations} currentLocation={protagonist?.location} onPreview={handlePreviewTravel} travelPreview={travelPreview} previewLoading={previewLoading} onTravel={handleTravelTo} />
                </div>
              )}

              {/* 3. Codex Drawer */}
              {activeDrawer === 'codex' && (
                <div className="space-y-6">
                  <div className="h-64 rounded-2xl border-2 border-[var(--line)] overflow-hidden shadow-inner bg-[var(--bg-surface)]">
                    <Suspense fallback={<div className="h-full flex items-center justify-center text-xs text-[var(--ink-soft)]">Loading graph…</div>}>
                      <CodexGraph nodes={affinityGraph.nodes} edges={affinityGraph.edges} />
                    </Suspense>
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

              {/* 7. Quest Board */}
              {activeDrawer === 'quests' && (
                <div className="space-y-3">
                  {quests.length === 0 ? (
                    <p className="text-xs font-bold text-[var(--ink-soft)] text-center py-6">No quests discovered yet.</p>
                  ) : (
                    quests.map((q: any) => (
                      <div key={q.quest_id} className="p-4 rounded-2xl bg-[var(--bg-surface)] border border-[var(--line)] shadow-sm space-y-1.5">
                        <div className="flex items-center justify-between gap-2">
                          <span className="text-[14px] font-bold text-[var(--ink-main)] font-[var(--font-display)]">{q.title}</span>
                          <span className="px-2 py-0.5 rounded-full font-mono text-[10px] font-bold bg-[var(--bg-subtle)] text-[var(--accent-sage)] border border-[var(--line)]">{q.status}</span>
                        </div>
                        {q.hint && <p className="text-[13px] text-[var(--ink-soft)] font-medium leading-relaxed">{q.hint}</p>}
                        <p className="text-[11px] font-mono text-[var(--ink-faint)]">
                          {q.location_hint ? `📍 ${q.location_hint} · ` : ''}
                          {q.deadline_tick !== null && q.deadline_tick !== undefined ? `deadline tick ${q.deadline_tick} · ` : ''}
                          known: {q.source?.kind || 'unknown'}
                        </p>
                      </div>
                    ))
                  )}
                </div>
              )}

              {/* 8. Consequence Journal */}
              {activeDrawer === 'journal' && (
                <div className="space-y-3">
                  {journal.length === 0 ? (
                    <p className="text-xs font-bold text-[var(--ink-soft)] text-center py-6">Nothing has happened that you know of yet.</p>
                  ) : (
                    journal.map((entry: any) => (
                      <div key={entry.quest_id} className="p-4 rounded-2xl bg-[var(--bg-surface)] border border-[var(--line)] shadow-sm space-y-1.5">
                        <div className="flex items-center justify-between gap-2">
                          <span className="text-[14px] font-bold text-[var(--ink-main)] font-[var(--font-display)]">{entry.title}</span>
                          <span className="px-2 py-0.5 rounded-full font-mono text-[10px] font-bold bg-[var(--bg-subtle)] text-[var(--ink-soft)] border border-[var(--line)]">{entry.status}</span>
                        </div>
                        {entry.hint && <p className="text-[13px] text-[var(--ink-soft)] font-medium leading-relaxed">{entry.hint}</p>}
                        <p className="text-[11px] font-mono text-[var(--ink-faint)]">
                          tick {entry.discovered_at_tick ?? '?'} · via {entry.source?.kind || 'unknown'}
                          {entry.resolution ? ` · ${entry.resolution}` : ''}
                        </p>
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

          <button
            onClick={() => setActiveDrawer(activeDrawer === 'quests' ? null : 'quests')}
            title="Quest Board"
            className={`p-2.5 rounded-2xl transition-all ${
              activeDrawer === 'quests' ? 'bg-[var(--bg-subtle)] text-[var(--periwinkle-dark)] border border-[var(--line-2)] shadow-sm' : 'text-[var(--ink-main)]/70 hover:text-[var(--ink-main)] hover:bg-[var(--bg-subtle)] border border-transparent'
            }`}
          >
            <FlagIcon className="w-5 h-5" />
          </button>

          <button
            onClick={() => setActiveDrawer(activeDrawer === 'journal' ? null : 'journal')}
            title="Consequence Journal"
            className={`p-2.5 rounded-2xl transition-all ${
              activeDrawer === 'journal' ? 'bg-[var(--bg-subtle)] text-[var(--periwinkle-dark)] border border-[var(--line-2)] shadow-sm' : 'text-[var(--ink-main)]/70 hover:text-[var(--ink-main)] hover:bg-[var(--bg-subtle)] border border-transparent'
            }`}
          >
            <NewspaperIcon className="w-5 h-5" />
          </button>
        </div>
      </div>
  </>);
}
