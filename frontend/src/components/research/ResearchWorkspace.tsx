"use client";

import React, { useState } from 'react';
import { RAGQueryResponse, ResearchQueryResponse, SourceRef, askQuestion, ResearchDiscoveryResponse, runResearchDiscovery, runResearch } from '@/lib/api';

import ResearchInput from './ResearchInput';
import AskView from './AskView';
import ResearchBrief from './ResearchBrief';
import DiscoveryView from './DiscoveryView';
import EvidencePanel from '../evidence/EvidencePanel';
import { AlertCircle, RotateCcw } from 'lucide-react';

type Mode = 'idle' | 'ask' | 'discovering' | 'directions_ready' | 'research';

export default function ResearchWorkspace({ chunkCache }: { chunkCache?: Record<string, string> }) {
  const [mode, setMode] = useState<Mode>('idle');
  const [isProcessing, setIsProcessing] = useState(false);
  const [error, setError] = useState<string | null>(null);
  
  const [askData, setAskData] = useState<RAGQueryResponse | null>(null);
  const [discoveryData, setDiscoveryData] = useState<ResearchDiscoveryResponse | null>(null);
  const [researchData, setResearchData] = useState<ResearchQueryResponse | null>(null);
  
  const [selectedSource, setSelectedSource] = useState<SourceRef | null>(null);
  const [currentWebSearch, setCurrentWebSearch] = useState<boolean>(false);

  const handleAsk = async (query: string) => {
    setIsProcessing(true);
    setError(null);
    setMode('ask');
    setAskData(null);
    setSelectedSource(null);
    
    try {
      const result = await askQuestion(query, 5);
      setAskData(result);
    } catch (err: any) {
      setError(err.message || "An error occurred while answering.");
    } finally {
      setIsProcessing(false);
    }
  };

  const handleResearchDiscovery = async (topic: string, webSearch: boolean) => {
    setIsProcessing(true);
    setError(null);
    setMode('discovering');
    setDiscoveryData(null);
    setResearchData(null);
    setSelectedSource(null);
    setCurrentWebSearch(webSearch);
    
    try {
      const result = await runResearchDiscovery(topic, webSearch);
      setDiscoveryData(result);
      setMode('directions_ready');
    } catch (err: any) {
      setError(err.message || "An error occurred during discovery.");
      setMode('idle');
    } finally {
      setIsProcessing(false);
    }
  };

  const handleResearchExecute = async (query: string) => {
    setIsProcessing(true);
    setError(null);
    setMode('research');
    setResearchData(null);
    setSelectedSource(null);
    
    try {
      const result = await runResearch(query, currentWebSearch);
      setResearchData(result);
    } catch (err: any) {
      setError(err.message || "An error occurred during research.");
    } finally {
      setIsProcessing(false);
    }
  };

  const resetWorkspace = () => {
    setMode('idle');
    setAskData(null);
    setDiscoveryData(null);
    setResearchData(null);
    setError(null);
    setSelectedSource(null);
  };

  return (
    <div className="flex-1 flex flex-col h-full relative">
      
      {/* Scrollable Content Area */}
      <div className="flex-1 overflow-y-auto w-full">
        <div className="min-h-full flex flex-col p-6 md:p-12 pb-32">
          
          {/* Header Actions when not idle */}
          {mode !== 'idle' && (
            <div className="mb-8">
              <button 
                onClick={resetWorkspace}
                className="flex items-center gap-2 text-sm font-medium text-brand-muted hover:text-brand-text transition-colors bg-white px-3 py-1.5 border border-brand-border rounded shadow-sm inline-flex"
              >
                <RotateCcw className="w-4 h-4" /> Start New
              </button>
            </div>
          )}

          {/* Error State */}
          {error && !isProcessing && (
            <div className="w-full max-w-3xl mx-auto bg-brand-error/10 border border-brand-error/20 p-6 rounded-xl flex items-start gap-4 mb-8 text-brand-error">
              <AlertCircle className="w-6 h-6 flex-shrink-0 mt-0.5" />
              <div>
                <h3 className="font-semibold text-lg mb-1">Failed to complete request</h3>
                <p className="text-sm opacity-90">{error}</p>
              </div>
            </div>
          )}

          {/* Idle / Input State */}
          {mode === 'idle' && (
            <div className="flex-1 flex flex-col justify-center max-w-5xl mx-auto w-full">
              <ResearchInput 
                onAsk={handleAsk} 
                onResearch={handleResearchDiscovery} 
                isProcessing={isProcessing} 
              />
            </div>
          )}

          {/* Loading State */}
          {isProcessing && (mode === 'ask' || mode === 'discovering' || mode === 'research') && (
            <div className="w-full max-w-3xl mx-auto mt-12 flex flex-col items-center">
              <div className="w-12 h-12 border-4 border-brand-primary/20 border-t-brand-primary rounded-full animate-spin mb-4"></div>
              <p className="text-brand-primary font-serif font-medium text-lg">
                {mode === 'ask' && 'Synthesizing answer...'}
                {mode === 'discovering' && 'Discovering research directions...'}
                {mode === 'research' && 'Investigating sources and compiling brief...'}
              </p>
              <p className="text-sm text-brand-muted mt-2">This may take a moment depending on the evidence.</p>
            </div>
          )}

          {/* Success States */}
          {!isProcessing && mode === 'ask' && askData && (
            <AskView 
              answer={askData.answer} 
              sources={askData.sources} 
              onCitationClick={setSelectedSource} 
            />
          )}

          {!isProcessing && mode === 'directions_ready' && discoveryData && (
            <DiscoveryView
              topic={discoveryData.topic}
              questions={discoveryData.questions}
              onSelect={handleResearchExecute}
            />
          )}

          {!isProcessing && mode === 'research' && researchData && (
            <ResearchBrief 
              data={researchData} 
              onCitationClick={setSelectedSource} 
            />
          )}

        </div>
      </div>

      {/* Evidence Panel Overlays */}
      <EvidencePanel 
        sourceRef={selectedSource} 
        chunkText={selectedSource ? (chunkCache && chunkCache[selectedSource.chunk_id]) : undefined}
        onClose={() => setSelectedSource(null)} 
      />

    </div>
  );
}
