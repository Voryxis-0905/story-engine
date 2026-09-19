import type { PlaySession } from './usePlaySession';
import { ChevronLeftIcon, ChevronRightIcon, ClockIcon, GlobeAltIcon } from '@heroicons/react/24/outline';

type Props = Pick<PlaySession, 'sidebarOpen' | 'setSidebarOpen' | 'protagonist' | 'arc' | 'clock' | 'calendar'>;

export function PlaySidebar({ sidebarOpen, setSidebarOpen, protagonist, arc, clock, calendar }: Props) {
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
      {/* LEFT SIDEBAR */}
      <aside
        className={`glass-panel rounded-none border-y-0 border-l-0 transition-all duration-300 flex flex-col z-20 h-full shrink-0 ${
          sidebarOpen ? 'w-72' : 'w-12'
        }`}
      >
        {/* Toggle Button Header */}
        <div className="p-3 border-b border-[var(--line-2)] flex items-center justify-between shrink-0 bg-[var(--bg-surface)] sticky top-0 z-10">
          {sidebarOpen && (
            <span className="text-xs font-mono uppercase tracking-wider text-[var(--periwinkle-dark)] font-bold">
              World State
            </span>
          )}
          <button
            onClick={() => setSidebarOpen(!sidebarOpen)}
            className="p-1.5 rounded-lg text-[var(--ink-soft)] hover:text-[var(--ink-main)] hover:bg-[var(--bg-subtle)] transition-colors mx-auto"
            title={sidebarOpen ? "Collapse sidebar" : "Expand sidebar"}
          >
            {sidebarOpen ? <ChevronLeftIcon className="w-5 h-5" /> : <ChevronRightIcon className="w-5 h-5" />}
          </button>
        </div>

        {sidebarOpen && (
          <div className="p-4 flex-1 overflow-y-auto space-y-6">
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
          </div>
        )}
      </aside>


  </>);
}
