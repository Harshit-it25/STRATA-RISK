import React from 'react';
import { ScreenType } from '../types';
import { useBackend } from '../context/BackendContext';

interface HeaderProps {
  activeScreen: ScreenType;
  onOpenEthics: () => void;
  onOpenProfile: () => void;
}

export const Header: React.FC<HeaderProps> = ({
  activeScreen,
  onOpenEthics,
  onOpenProfile
}) => {
  const { isBackendOnline, isConnecting } = useBackend();

  const getSubTitle = () => {
    switch (activeScreen) {
      case 'overview':
        return 'Overview';
      case 'risk-map':
        return 'Risk Map';
      case 'compare':
        return 'Compare';
      case 'validation':
        return 'Validation';
    }
  };

  return (
    <header className="fixed top-0 w-full z-50 pt-safe bg-[#fbf8fc]/90 backdrop-blur-xl shadow-[0_1px_8px_rgba(0,0,0,0.04)] border-b border-[#f0edf1]">
      <div className="h-16 px-4 max-w-lg mx-auto flex items-center justify-between gap-2">
        {/* Brand Logo & Name */}
        <div className="flex items-center gap-2.5 min-w-0">
          <img
            alt="Strata Risk Logo"
            className="h-8 w-auto object-contain flex-shrink-0"
            src="https://lh3.googleusercontent.com/aida/AEtjO1VzmedTBrRp1bXwkypHXkn_ASp4KME-S7WH03hKIm5Tn6RJE1JXwJuKcYM9R5IMgc1BLgoLskP2JqmxACcRrXKe0NXAvC4bQl5pJz8GWg_ePEcIimu_Nj5GKNULyjqqmGn4GxfC89mhZtC4yCR2HLcaVyNTb7XjKc15O0Jj0LZ3oTp5O3K6gfBQvVX_qFtEVchhLdEyQ4b5GMl110vI1vj-BGrihnUaCPljE7voK6En85Qq1dX3KWLQrRL-"
          />
          <div className="flex flex-col min-w-0">
            <div className="flex items-center gap-1.5">
              <span className="font-semibold text-lg tracking-tight text-[#1b1b1e] truncate font-headline">
                Strata Risk
              </span>
              <span className="hidden xs:inline-flex items-center px-1.5 py-0.5 rounded bg-[#f0edf1] text-[#45464d] text-xs font-mono">
                {isBackendOnline ? 'FastAPI' : 'Simulated'}
              </span>
            </div>
            <div className="flex items-center gap-1.5 truncate">
              <span className="text-xs text-[#45464d] truncate font-medium">
                {getSubTitle()}
              </span>
              <span className="hidden sm:inline-flex text-[10px] font-mono text-[#0051d5] bg-[#eef4ff] px-1.5 py-0.2 rounded border border-[#d0e1fd] truncate">
                Chicago Crime Data — Proxy Dataset
              </span>
            </div>
          </div>
        </div>

        {/* Right Action Icons & Badges */}
        <div className="flex items-center gap-1 flex-shrink-0">
          <div
            className={`inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-xs font-mono border transition-colors ${
              isBackendOnline
                ? 'bg-[#dcfce7] text-[#15803d] border-[#bbf7d0]'
                : 'bg-[#f6f2f7] text-[#45464d] border-[#e4e1e6]/60'
            }`}
          >
            <span
              className={`w-1.5 h-1.5 rounded-full ${
                isBackendOnline
                  ? 'bg-[#16a34a] animate-pulse'
                  : isConnecting
                  ? 'bg-[#f59e0b] animate-ping'
                  : 'bg-[#0051d5]'
              }`}
            ></span>
            <span className="hidden sm:inline">
              {isBackendOnline ? 'FastAPI • ' : 'Demo Mode • '}
            </span>
            <span>{isBackendOnline ? 'Live' : isConnecting ? 'Connecting' : 'Offline'}</span>
          </div>

          <button
            onClick={onOpenEthics}
            aria-label="Responsible Use and Model Ethics"
            className="w-10 h-10 flex items-center justify-center rounded-lg text-[#45464d] hover:text-[#1b1b1e] hover:bg-[#f0edf1] transition-colors cursor-pointer"
            title="Responsible AI & Model Ethics"
          >
            <span className="material-symbols-outlined text-[20px]">info</span>
          </button>

          <button
            onClick={onOpenProfile}
            aria-label="User Profile & Settings"
            className="w-8 h-8 rounded-full bg-[#000000] text-white flex items-center justify-center ml-0.5 hover:bg-[#303033] transition-colors shadow-sm cursor-pointer"
            title="Dispatcher Profile"
          >
            <span className="material-symbols-outlined text-white text-[18px]">person</span>
          </button>
        </div>
      </div>
    </header>
  );
};
