"use client";

import React, { useState } from 'react';
import { Plus, FileText, Link as LinkIcon } from 'lucide-react';
import { Source } from '@/lib/api';
import AddSourceModal from './AddSourceModal';

interface SourceLibraryProps {
  sources: Source[];
  onSourceAdded: (source: Source, chunks?: any[]) => void;
}

export default function SourceLibrary({ sources, onSourceAdded }: SourceLibraryProps) {
  const [isModalOpen, setIsModalOpen] = useState(false);

  return (
    <div className="flex flex-col h-full overflow-hidden">
      <div className="p-6 pb-2 flex items-center justify-between">
        <h2 className="text-xs font-semibold uppercase tracking-wider text-brand-muted">Source Library</h2>
      </div>
      
      <div className="flex-1 overflow-y-auto p-4 space-y-1">
        {sources.length === 0 ? (
          <div className="text-sm text-brand-muted p-2">
            No sources added yet.
          </div>
        ) : (
          sources.map((source) => (
            <div 
              key={source.id}
              className="flex items-center gap-3 px-3 py-2 rounded-md hover:bg-black/5 transition-colors group cursor-default"
            >
              <div className="flex-shrink-0 text-brand-muted group-hover:text-brand-text transition-colors">
                {source.source_type === 'pdf' ? (
                  <FileText className="w-4 h-4" />
                ) : (
                  <LinkIcon className="w-4 h-4" />
                )}
              </div>
              <div className="flex-1 min-w-0">
                <p className="text-sm text-brand-text truncate font-medium">
                  {source.title}
                </p>
              </div>
            </div>
          ))
        )}
      </div>

      <div className="p-4 border-t border-brand-border">
        <button
          onClick={() => setIsModalOpen(true)}
          className="w-full flex items-center justify-center gap-2 px-4 py-2 text-sm font-medium text-brand-primary bg-brand-primary/10 hover:bg-brand-primary/20 rounded-md transition-colors"
        >
          <Plus className="w-4 h-4" />
          Add Source
        </button>
      </div>

      <AddSourceModal 
        isOpen={isModalOpen} 
        onClose={() => setIsModalOpen(false)} 
        onSourceAdded={onSourceAdded}
      />
    </div>
  );
}
