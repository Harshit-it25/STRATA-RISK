import React from 'react';
import { ScreenType } from '../types';

interface BottomNavProps {
  activeScreen: ScreenType;
  onChangeScreen: (screen: ScreenType) => void;
}

export const BottomNav: React.FC<BottomNavProps> = ({
  activeScreen,
  onChangeScreen
}) => {
  const navItems: { id: ScreenType; label: string; icon: string; hasDot?: boolean }[] = [
    { id: 'overview', label: 'Overview', icon: 'dashboard' },
    { id: 'risk-map', label: 'Risk Map', icon: 'explore', hasDot: true },
    { id: 'compare', label: 'Compare', icon: 'history_toggle_off' },
    { id: 'validation', label: 'Validation', icon: 'verified_user' }
  ];

  return (
    <nav className="fixed bottom-0 w-full z-50 pb-safe bg-[#fbf8fc]/95 backdrop-blur-xl border-t border-[#f0edf1] shadow-[0_-1px_8px_rgba(0,0,0,0.03)]">
      <div className="h-16 max-w-lg mx-auto px-2 flex items-center justify-around">
        {navItems.map((item) => {
          const isActive = activeScreen === item.id;
          return (
            <button
              key={item.id}
              onClick={() => onChangeScreen(item.id)}
              aria-current={isActive ? 'page' : undefined}
              className={`flex-1 flex flex-col items-center justify-center h-14 min-w-[44px] gap-0.5 transition-colors cursor-pointer ${
                isActive
                  ? 'text-[#0051d5] font-semibold'
                  : 'text-[#45464d] hover:text-[#1b1b1e]'
              }`}
            >
              <div className="relative flex items-center justify-center">
                <span className="material-symbols-outlined text-[23px]">
                  {item.icon}
                </span>
                {item.hasDot && !isActive && (
                  <span className="absolute -top-0.5 -right-0.5 w-1.5 h-1.5 rounded-full bg-[#0051d5]" />
                )}
                {item.hasDot && isActive && (
                  <span className="absolute -top-0.5 -right-0.5 w-1.5 h-1.5 rounded-full bg-[#0051d5] animate-ping opacity-75" />
                )}
              </div>
              <span className="text-xs font-medium tracking-tight">
                {item.label}
              </span>
            </button>
          );
        })}
      </div>
    </nav>
  );
};
