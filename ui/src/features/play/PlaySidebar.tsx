import { useState } from 'react';
import type { PlaySession } from './usePlaySession';
import { ChevronLeftIcon, ChevronRightIcon, ClockIcon, GlobeAltIcon } from '@heroicons/react/24/outline';

type Props = Pick<PlaySession, 'sidebarOpen' | 'setSidebarOpen' | 'protagonist' | 'arc' | 'clock' | 'calendar'>;

export function PlaySidebar({ sidebarOpen, setSidebarOpen, protagonist, arc, clock, calendar }: Props) {
  const [mobileOpen, setMobileOpen] = useState(false);
  const gregorianMonths = ['January', 'February', 'March', 'April', 'May', 'June',
    'July', 'August', 'September', 'October', 'November', 'December'];
  const monthName = calendar?.kind === 'gregorian'
    ? gregorianMonths[Number(clock.month) - 1]
    : calendar?.months?.[Number(clock.month) - 1]?.name;
  const time = Number.isInteger(clock.second_of_day)
    ? `${String(Math.floor(clock.second_of_day / 3600)).padStart(2, '0')}:${String(Math.floor(clock.second_of_day % 3600 / 60)).padStart(2, '0')}`
    : Number.isInteger(clock.minute_of_day)
      ? `${String(Math.floor(clock.minute_of_day / 60)).padStart(2, '0')}:${String(clock.minute_of_day % 60).padStart(2, '0')}`
      : clock.time_of_day;
  const date = [clock.day != null ? `Day ${clock.day}` : null,
    monthName || (clock.month != null ? `Month ${clock.month}` : null),
    clock.year != null ? `${calendar?.year_label || 'Year'} ${clock.year}${calendar?.era ? ` ${calendar.era}` : ''}` : null]
    .filter(Boolean).join(' · ');
  return (<>
      {/*
        LEFT SIDEBAR - the World State panel.

        The desktop column and compact rail have independent open states, so
        each reports its actual visibility and resizing preserves the user's
        choice for that layout:

          - at `xl` and up it is the in-flow 288px column, exactly as before;
          - below `xl` the rail stays 48px and the content becomes an overlay
            anchored just right of the rail, so it can be opened and closed
            without taking a single pixel from the transcript.

        The bug this replaces: the rail was locked to 48px *and* the content
        was `hidden xl:block`, so below `xl` the toggle flipped `sidebarOpen`,
        the chevron turned and the label changed to "Collapse sidebar" - while
        nothing ever appeared. A control that reports a state it cannot reach
        is worse than no control: there was no way at all to read World State
        on a phone or a tablet.

        Why the overlay starts at `left-12` and not `left-0`: the rail owns the
        toggle, and a panel covering the rail would cover the only way to close
        it again. Leaving the rail clear is what makes the second click work.

        `max-w-[calc(100vw-7rem)]` is 100vw minus the rail (48px) minus the
        inspector's icon strip (64px). At 360px a bare `w-72` would run 40px
        under the strip; the clamp keeps the whole panel readable instead.

        The overlay is an `absolute` sibling of the rail, anchored to the play
        row rather than inside `.glass-panel`. This avoids the backdrop-filter
        stacking context trapping the overlay behind the map drawer. The play
        row already begins below the navbar, so no extra top offset is needed.

        `z-[75]` sits above the drawer overlay (70) and below the icon strip
        (80). The aside itself carries no `z-index`: a z-index here would open a
        stacking context and trap the panel's own layer, which is what made the
        mobile strip untappable in an earlier round.
      */}
      <aside
        className={`relative glass-panel rounded-none border-y-0 border-l-0 transition-all duration-300 flex flex-col h-full shrink-0 ${
          sidebarOpen ? 'w-12 xl:w-72' : 'w-12'
        }`}
      >
        {/* Toggle Button Header */}
        <div className="p-3 border-b border-[var(--line-2)] flex items-center justify-between shrink-0 bg-[var(--bg-surface)] sticky top-0 z-10">
          {sidebarOpen && (
            <span className="hidden xl:inline text-xs font-mono uppercase tracking-wider text-[var(--periwinkle-dark)] font-bold">
              World State
            </span>
          )}
          <button
            type="button"
            onClick={() => setMobileOpen((open) => !open)}
            aria-expanded={mobileOpen}
            aria-controls="mobile-world-state"
            className="xl:hidden shrink-0 p-1.5 rounded-lg text-[var(--ink-soft)] hover:text-[var(--ink-main)] hover:bg-[var(--bg-subtle)] transition-colors"
            title={mobileOpen ? "Collapse sidebar" : "Expand sidebar"}
            aria-label={mobileOpen ? "Collapse sidebar" : "Expand sidebar"}
          >
            {mobileOpen ? <ChevronLeftIcon className="w-5 h-5" /> : <ChevronRightIcon className="w-5 h-5" />}
          </button>
          <button
            type="button"
            onClick={() => setSidebarOpen(!sidebarOpen)}
            aria-expanded={sidebarOpen}
            className="hidden xl:block shrink-0 p-1.5 rounded-lg text-[var(--ink-soft)] hover:text-[var(--ink-main)] hover:bg-[var(--bg-subtle)] transition-colors"
            title={sidebarOpen ? "Collapse sidebar" : "Expand sidebar"}
            aria-label={sidebarOpen ? "Collapse sidebar" : "Expand sidebar"}
          >
            {sidebarOpen ? <ChevronLeftIcon className="w-5 h-5" /> : <ChevronRightIcon className="w-5 h-5" />}
          </button>
        </div>

        {sidebarOpen && (
          <section
            aria-label="World State"
            className="hidden xl:block p-4 flex-1 overflow-y-auto space-y-6"
          >
            {/* World Clock & Season */}
            <div className="p-4 rounded-xl bg-[var(--bg-surface)] border border-[var(--line)] space-y-2.5 shadow-sm">
              <div className="flex items-center gap-2 text-[var(--ink-soft)] text-xs font-bold uppercase tracking-wider">
                <ClockIcon  className="w-5 h-5 text-[var(--periwinkle-dark)]" />
                <span>Story Timeline</span>
              </div>
              <div className="text-sm font-bold text-[var(--ink-main)]">
                {[clock.season, time].filter(Boolean).join(' · ') || 'Time not set'}
              </div>
              <div className="text-xs text-[var(--ink-soft)] font-mono font-bold">
                {date || 'Date not set'}
              </div>
              <div className="text-xs text-[var(--periwinkle-dark)] flex items-center gap-1 font-bold">
                <GlobeAltIcon className="w-5 h-5" />
                <span>{protagonist?.location || 'Location not set'}</span>
              </div>
            </div>

            {/* Arc Progress Meter */}
            <div className="p-4 rounded-xl bg-[var(--bg-surface)] border border-[var(--line)] space-y-3 shadow-sm">
              <div className="flex items-center justify-between text-xs">
                <span className="font-bold text-[var(--ink-soft)] uppercase tracking-wider">Arc Checkpoint</span>
                <span className="px-2 py-0.5 rounded-full bg-[var(--bg-subtle)] text-[var(--periwinkle-dark)] border border-[var(--line)] font-mono font-bold text-[10px]">
                  {arc?.current_checkpoint_id || 'cp_0'}
                </span>
              </div>

              <div className="w-full h-2 rounded-full bg-[var(--line)] overflow-hidden">
                <div
                  className="h-full bg-gradient-to-r from-[var(--periwinkle)] to-[var(--sakura)] rounded-full transition-all duration-500 shadow-sm"
                  style={{
                    width: `${Math.min(100, (((arc?.current_index ?? 0) + 1) / (arc?.total_checkpoints || 1)) * 100)}%`
                  }}
                />
              </div>

              <div className="flex items-center justify-between text-xs font-mono font-bold text-[var(--ink-soft)]">
                <span>Index: {arc?.current_index ?? 0}</span>
                <span>Total: {arc?.total_checkpoints ?? 0}</span>
              </div>
            </div>

            {/* Protagonist Mini Card */}
            {protagonist && (
              <div className="p-4 rounded-xl bg-gradient-to-b from-[var(--bg-subtle)] to-[var(--bg-surface)] border border-[var(--line)] space-y-2 shadow-sm">
                <div className="flex items-center gap-3">
                  <div className="w-10 h-10 rounded-xl bg-gradient-to-br from-[var(--periwinkle)] to-[var(--periwinkle-dark)] shadow-[var(--shadow-sm)] flex items-center justify-center font-bold text-white text-lg font-[var(--font-display)]">
                    {protagonist.name.charAt(0)}
                  </div>
                  <div>
                    <h4 className="font-bold text-[var(--ink-main)] text-sm">{protagonist.name}</h4>
                    <span className="text-xs text-[var(--periwinkle-dark)] font-mono font-bold">{protagonist.power_stat?.realm || 'Mortal'}</span>
                  </div>
                </div>
                <div className="text-[10px] uppercase font-bold tracking-wider text-[var(--ink-soft)] pt-2 border-t border-[var(--line-2)] flex items-center justify-between font-mono">
                  <span>EXP: <span className="text-[var(--ink-main)]">{protagonist.power_stat?.exp || 0}</span></span>
                  <span className={protagonist.alive ? 'text-[var(--ok)]' : 'text-[var(--danger)]'}>
                    {protagonist.alive ? '● Alive' : '✕ Fallen'}
                  </span>
                </div>
              </div>
            )}
          </section>
        )}
      </aside>

      {mobileOpen && (
        <section
          id="mobile-world-state"
          aria-label="World State"
          className="absolute left-12 top-0 bottom-0 z-[75] w-72 max-w-[calc(100vw-7rem)] overflow-y-auto space-y-6 border-r border-[var(--line)] bg-[var(--bg-surface)] p-4 shadow-[var(--shadow-md)] xl:hidden"
        >
          <div className="p-4 rounded-xl bg-[var(--bg-surface)] border border-[var(--line)] space-y-2.5 shadow-sm">
            <div className="flex items-center gap-2 text-[var(--ink-soft)] text-xs font-bold uppercase tracking-wider">
              <ClockIcon className="w-5 h-5 text-[var(--periwinkle-dark)]" />
              <span>Story Timeline</span>
            </div>
            <div className="text-sm font-bold text-[var(--ink-main)]">
              {[clock.season, time].filter(Boolean).join(' · ') || 'Time not set'}
            </div>
            <div className="text-xs text-[var(--ink-soft)] font-mono font-bold">
              {date || 'Date not set'}
            </div>
            <div className="text-xs text-[var(--periwinkle-dark)] flex items-center gap-1 font-bold">
              <GlobeAltIcon className="w-5 h-5" />
              <span>{protagonist?.location || 'Location not set'}</span>
            </div>
          </div>

          <div className="p-4 rounded-xl bg-[var(--bg-surface)] border border-[var(--line)] space-y-3 shadow-sm">
            <div className="flex items-center justify-between text-xs">
              <span className="font-bold text-[var(--ink-soft)] uppercase tracking-wider">Arc Checkpoint</span>
              <span className="px-2 py-0.5 rounded-full bg-[var(--bg-subtle)] text-[var(--periwinkle-dark)] border border-[var(--line)] font-mono font-bold text-[10px]">
                {arc?.current_checkpoint_id || 'cp_0'}
              </span>
            </div>
            <div className="w-full h-2 rounded-full bg-[var(--line)] overflow-hidden">
              <div
                className="h-full bg-gradient-to-r from-[var(--periwinkle)] to-[var(--sakura)] rounded-full transition-all duration-500 shadow-sm"
                style={{ width: `${Math.min(100, (((arc?.current_index ?? 0) + 1) / (arc?.total_checkpoints || 1)) * 100)}%` }}
              />
            </div>
            <div className="flex items-center justify-between text-xs font-mono font-bold text-[var(--ink-soft)]">
              <span>Index: {arc?.current_index ?? 0}</span>
              <span>Total: {arc?.total_checkpoints ?? 0}</span>
            </div>
          </div>

          {protagonist && (
            <div className="p-4 rounded-xl bg-gradient-to-b from-[var(--bg-subtle)] to-[var(--bg-surface)] border border-[var(--line)] space-y-2 shadow-sm">
              <div className="flex items-center gap-3">
                <div className="w-10 h-10 rounded-xl bg-gradient-to-br from-[var(--periwinkle)] to-[var(--periwinkle-dark)] shadow-[var(--shadow-sm)] flex items-center justify-center font-bold text-white text-lg font-[var(--font-display)]">
                  {protagonist.name.charAt(0)}
                </div>
                <div>
                  <h4 className="font-bold text-[var(--ink-main)] text-sm">{protagonist.name}</h4>
                  <span className="text-xs text-[var(--periwinkle-dark)] font-mono font-bold">{protagonist.power_stat?.realm || 'Mortal'}</span>
                </div>
              </div>
              <div className="text-[10px] uppercase font-bold tracking-wider text-[var(--ink-soft)] pt-2 border-t border-[var(--line-2)] flex items-center justify-between font-mono">
                <span>EXP: <span className="text-[var(--ink-main)]">{protagonist.power_stat?.exp || 0}</span></span>
                <span className={protagonist.alive ? 'text-[var(--ok)]' : 'text-[var(--danger)]'}>
                  {protagonist.alive ? '● Alive' : '✕ Fallen'}
                </span>
              </div>
            </div>
          )}
        </section>
      )}


  </>);
}
