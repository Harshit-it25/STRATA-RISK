/**
 * @license
 * SPDX-License-Identifier: Apache-2.0
 */

import React, { useState } from 'react';
import { Header } from './components/Header';
import { BottomNav } from './components/BottomNav';
import { OverviewScreen } from './components/OverviewScreen';
import { RiskMapScreen } from './components/RiskMapScreen';
import { CompareScreen } from './components/CompareScreen';
import { ValidationScreen } from './components/ValidationScreen';
import { EthicsModal } from './components/EthicsModal';
import { SectorSelectorModal } from './components/SectorSelectorModal';
import { LayersModal } from './components/LayersModal';
import { UserProfileModal } from './components/UserProfileModal';
import { BackendStatusBanner } from './components/BackendStatusBanner';
import { BackendProvider, useBackend } from './context/BackendContext';
import { ScreenType, OverlayLayers } from './types';

function AppContent() {
  const [activeScreen, setActiveScreen] = useState<ScreenType>('overview');
  const [focusedZoneKey, setFocusedZoneKey] = useState<string>('market');

  const { selectedSector, setSelectedSector } = useBackend();

  // Modals state
  const [isEthicsOpen, setIsEthicsOpen] = useState<boolean>(false);
  const [isSectorSelectorOpen, setIsSectorSelectorOpen] = useState<boolean>(false);
  const [isLayersModalOpen, setIsLayersModalOpen] = useState<boolean>(false);
  const [isProfileModalOpen, setIsProfileModalOpen] = useState<boolean>(false);

  // Layers state
  const [layers, setLayers] = useState<OverlayLayers>({
    densityHeatmap: true,
    transitArteries: true,
    sensorNodes: true,
    confidenceBands: true,
    topographicGrid: true
  });

  const handleToggleLayer = (key: keyof OverlayLayers) => {
    setLayers((prev) => ({
      ...prev,
      [key]: !prev[key]
    }));
  };

  const handleNavigateToRiskMap = (zoneKey?: string) => {
    if (zoneKey) {
      setFocusedZoneKey(zoneKey);
    }
    setActiveScreen('risk-map');
    window.scrollTo({ top: 0, behavior: 'smooth' });
  };

  return (
    <div className="min-h-screen bg-[#fbf8fc] text-[#1b1b1e] flex flex-col font-sans selection:bg-[#0051d5] selection:text-white">
      {/* Top Fixed Header */}
      <Header
        activeScreen={activeScreen}
        onOpenEthics={() => setIsEthicsOpen(true)}
        onOpenProfile={() => setIsProfileModalOpen(true)}
      />

      {/* Main Screen Container with padding for fixed header and bottom nav */}
      <main className="flex-1 w-full pt-16 flex flex-col">
        {/* API Connection Health Indicator */}
        <BackendStatusBanner />

        {activeScreen === 'overview' && (
          <OverviewScreen
            onNavigateToRiskMap={handleNavigateToRiskMap}
            onOpenEthics={() => setIsEthicsOpen(true)}
          />
        )}

        {activeScreen === 'risk-map' && (
          <RiskMapScreen
            selectedSector={selectedSector}
            onOpenSectorPicker={() => setIsSectorSelectorOpen(true)}
            onOpenLayersModal={() => setIsLayersModalOpen(true)}
            layers={layers}
            initialZoneKey={focusedZoneKey}
          />
        )}

        {activeScreen === 'compare' && <CompareScreen />}

        {activeScreen === 'validation' && (
          <ValidationScreen onOpenEthics={() => setIsEthicsOpen(true)} />
        )}
      </main>

      {/* Bottom Fixed Navigation Bar */}
      <BottomNav
        activeScreen={activeScreen}
        onChangeScreen={(screen) => {
          setActiveScreen(screen);
          window.scrollTo({ top: 0, behavior: 'smooth' });
        }}
      />

      {/* Global Modals */}
      <EthicsModal
        isOpen={isEthicsOpen}
        onClose={() => setIsEthicsOpen(false)}
      />

      <SectorSelectorModal
        isOpen={isSectorSelectorOpen}
        selectedSector={selectedSector}
        onSelectSector={setSelectedSector}
        onClose={() => setIsSectorSelectorOpen(false)}
      />

      <LayersModal
        isOpen={isLayersModalOpen}
        layers={layers}
        onToggleLayer={handleToggleLayer}
        onClose={() => setIsLayersModalOpen(false)}
      />

      <UserProfileModal
        isOpen={isProfileModalOpen}
        onClose={() => setIsProfileModalOpen(false)}
      />
    </div>
  );
}

export default function App() {
  return (
    <BackendProvider>
      <AppContent />
    </BackendProvider>
  );
}
