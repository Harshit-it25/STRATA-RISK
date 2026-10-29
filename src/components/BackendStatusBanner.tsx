import React, { useState } from 'react';
import { useBackend } from '../context/BackendContext';

export const BackendStatusBanner: React.FC = () => {
  const {
    isBackendOnline,
    isConnecting,
    backendUrl,
    backendError,
    retryConnection,
    updateBackendUrl
  } = useBackend();

  const [showConfig, setShowConfig] = useState(false);
  const [inputUrl, setInputUrl] = useState(backendUrl);

  const handleSaveUrl = (e: React.FormEvent) => {
    e.preventDefault();
    if (inputUrl.trim()) {
      updateBackendUrl(inputUrl.trim());
      setShowConfig(false);
    }
  };

  if (isBackendOnline && !showConfig) {
    return (
      <div className="w-full max-w-lg mx-auto px-4 pt-2">
        <div className="flex items-center justify-between px-3 py-1.5 rounded-lg bg-[#dcfce7]/70 border border-[#bbf7d0] text-xs font-mono text-[#15803d]">
          <div className="flex items-center gap-2">
            <span className="w-2 h-2 rounded-full bg-[#16a34a] animate-pulse"></span>
            <span className="font-semibold">FastAPI Connected</span>
            <span className="text-[11px] text-[#15803d]/80 hidden xs:inline">
              ({backendUrl})
            </span>
          </div>
          <button
            onClick={() => setShowConfig(true)}
            className="text-[11px] text-[#15803d] hover:underline cursor-pointer font-sans font-medium"
          >
            Configure
          </button>
        </div>
      </div>
    );
  }

  return (
    <div className="w-full max-w-lg mx-auto px-4 pt-2">
      <div className="p-3 rounded-xl bg-[#fff7ed] border border-[#ffedd5] shadow-2xs flex flex-col gap-2 text-xs">
        <div className="flex items-start justify-between gap-2">
          <div className="flex items-start gap-2">
            <span className="material-symbols-outlined text-[18px] text-[#ea580c] mt-0.5 flex-shrink-0">
              {isConnecting ? 'sync' : 'cloud_off'}
            </span>
            <div className="flex flex-col">
              <span className="font-semibold text-[#9a3412] font-headline">
                {isConnecting
                  ? 'Connecting to FastAPI Service...'
                  : 'FastAPI Backend Offline'}
              </span>
              <p className="text-[#9a3412]/90 text-[11px] mt-0.5 leading-snug">
                {backendError || `Service unavailable at ${backendUrl}.`}
              </p>
            </div>
          </div>

          <div className="flex items-center gap-1.5 flex-shrink-0">
            <button
              onClick={() => retryConnection()}
              disabled={isConnecting}
              className="px-2.5 py-1 bg-[#ea580c] hover:bg-[#c2410c] text-white rounded text-[11px] font-semibold transition-colors disabled:opacity-50 cursor-pointer flex items-center gap-1"
            >
              <span className={`material-symbols-outlined text-[13px] ${isConnecting ? 'animate-spin' : ''}`}>
                refresh
              </span>
              <span>{isConnecting ? 'Retrying' : 'Retry'}</span>
            </button>
            <button
              onClick={() => setShowConfig(!showConfig)}
              className="p-1 text-[#ea580c] hover:bg-[#ffedd5] rounded cursor-pointer"
              title="Configure API URL"
            >
              <span className="material-symbols-outlined text-[16px]">settings</span>
            </button>
          </div>
        </div>

        {/* Quick Launch instruction helper */}
        <div className="text-[11px] text-[#9a3412]/80 bg-[#fffbeb] p-2 rounded-lg border border-[#fef3c7] font-mono leading-relaxed">
          <span className="font-bold text-[#b45309]">To launch local backend:</span>
          <br />
          <code>uvicorn backend.main:app --port 8000 --reload</code>
        </div>

        {/* URL Configuration dropdown */}
        {showConfig && (
          <form onSubmit={handleSaveUrl} className="pt-1 flex gap-2">
            <input
              type="text"
              value={inputUrl}
              onChange={(e) => setInputUrl(e.target.value)}
              placeholder="http://localhost:8000"
              className="flex-1 px-2.5 py-1 text-xs bg-white border border-[#fed7aa] rounded font-mono text-[#1b1b1e] focus:outline-none focus:ring-1 focus:ring-[#ea580c]"
            />
            <button
              type="submit"
              className="px-3 py-1 bg-[#1b1b1e] text-white rounded text-xs font-semibold hover:bg-[#303033] cursor-pointer"
            >
              Save
            </button>
            <button
              type="button"
              onClick={() => setShowConfig(false)}
              className="px-2 py-1 text-xs text-[#9a3412] hover:bg-[#ffedd5] rounded cursor-pointer"
            >
              Cancel
            </button>
          </form>
        )}
      </div>
    </div>
  );
};
