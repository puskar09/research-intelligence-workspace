"use client";

import React, { useState } from 'react';
import { Source } from '@/lib/api';
import SourceLibrary from '@/components/sources/SourceLibrary';
import ResearchWorkspace from '@/components/research/ResearchWorkspace';

export default function AppShell() {
  const [sources, setSources] = useState<Source[]>([]);
  const [chunkCache, setChunkCache] = useState<Record<string, string>>({});
  const [isSidebarOpen, setIsSidebarOpen] = useState(false);

  const handleSourceAdded = (source: Source, chunks?: any[]) => {
    setSources((prev) => [...prev, source]);
    if (chunks) {
      setChunkCache((prev) => {
        const next = { ...prev };
        chunks.forEach((c) => {
          next[c.id] = c.text;
        });
        return next;
      });
    }
  };

  const handleSourceRemoved = (sourceId: string) => {
    setSources((prev) => prev.filter((s) => s.id !== sourceId));
  };

  return (
    <div className="flex h-screen w-full bg-brand-bg text-brand-text font-sans overflow-hidden">
      {/* Mobile Sidebar Overlay */}
      {isSidebarOpen && (
        <div 
          className="fixed inset-0 z-40 bg-black/40 backdrop-blur-sm md:hidden"
          onClick={() => setIsSidebarOpen(false)}
        />
      )}

      {/* Sidebar */}
      <aside className={`fixed inset-y-0 left-0 z-50 w-72 border-r border-brand-border bg-brand-bg flex flex-col flex-shrink-0 transform transition-transform duration-300 md:static md:translate-x-0 ${isSidebarOpen ? 'translate-x-0' : '-translate-x-full'}`}>
        <div className="p-6 border-b border-brand-border flex items-center justify-between">
          <div>
            <h1 className="text-xl font-serif font-semibold text-brand-primary tracking-tight">Research Intelligence</h1>
            <p className="text-sm text-brand-muted mt-1">Workspace</p>
          </div>
          <button 
            className="md:hidden p-2 text-brand-muted hover:bg-black/5 rounded-md"
            onClick={() => setIsSidebarOpen(false)}
          >
            ✕
          </button>
        </div>
        <SourceLibrary sources={sources} onSourceAdded={handleSourceAdded} onSourceRemoved={handleSourceRemoved} />
      </aside>

      {/* Main Workspace */}
      <main className="flex-1 flex flex-col h-full overflow-hidden relative w-full">
        {/* Mobile Header */}
        <div className="md:hidden flex items-center p-4 border-b border-brand-border bg-brand-bg">
          <button 
            onClick={() => setIsSidebarOpen(true)}
            className="p-2 -ml-2 mr-3 text-brand-primary hover:bg-black/5 rounded-md"
          >
            <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><line x1="3" y1="12" x2="21" y2="12"></line><line x1="3" y1="6" x2="21" y2="6"></line><line x1="3" y1="18" x2="21" y2="18"></line></svg>
          </button>
          <h1 className="text-lg font-serif font-semibold text-brand-primary tracking-tight">Research Intelligence</h1>
        </div>
        <ResearchWorkspace chunkCache={chunkCache} />
      </main>
    </div>
  );
}
