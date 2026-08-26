"use client";

import React, { useState } from 'react';
import { Plus, FileText, Link as LinkIcon, Trash2 } from 'lucide-react';
import { Source, deleteSource } from '@/lib/api';
import AddSourceModal from './AddSourceModal';

interface SourceLibraryProps {
  sources: Source[];
  onSourceAdded: (source: Source, chunks?: any[]) => void;
  onSourceRemoved: (sourceId: string) => void;
}

export default function SourceLibrary({ sources, onSourceAdded, onSourceRemoved }: SourceLibraryProps) {
  const [isModalOpen, setIsModalOpen] = useState(false);
  const [sourceToDelete, setSourceToDelete] = useState<Source | null>(null);
  const [isDeleting, setIsDeleting] = useState(false);
  const [deleteError, setDeleteError] = useState<string | null>(null);

  const handleDeleteConfirm = async () => {
    if (!sourceToDelete) return;
    
    setIsDeleting(true);
    setDeleteError(null);
    try {
      await deleteSource(sourceToDelete.id);
      onSourceRemoved(sourceToDelete.id);
      setSourceToDelete(null);
    } catch (err: any) {
      setDeleteError(err.message || 'Failed to delete source.');
    } finally {
      setIsDeleting(false);
    }
  };

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
              className="flex items-center justify-between gap-3 px-3 py-2 rounded-md hover:bg-black/5 transition-colors group cursor-default"
            >
              <div className="flex items-center gap-3 min-w-0 flex-1">
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
              
              <button
                onClick={() => {
                  setSourceToDelete(source);
                  setDeleteError(null);
                }}
                className="opacity-0 group-hover:opacity-100 p-1.5 text-brand-muted hover:text-red-500 hover:bg-red-50 rounded transition-all focus:opacity-100 flex-shrink-0"
                title="Remove source"
              >
                <Trash2 className="w-4 h-4" />
              </button>
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

      {/* Delete Confirmation Modal */}
      {sourceToDelete && (
        <div className="fixed inset-0 z-[60] flex items-center justify-center bg-black/40 backdrop-blur-sm p-4">
          <div className="bg-brand-bg border border-brand-border rounded-lg shadow-xl w-full max-w-sm overflow-hidden flex flex-col">
            <div className="p-5">
              <h3 className="text-lg font-serif font-semibold text-brand-text mb-2">
                Remove this source?
              </h3>
              <p className="text-sm text-brand-muted">
                This will permanently remove the source and its indexed documents, pages, chunks, and embeddings. This cannot be undone.
              </p>
              
              {deleteError && (
                <div className="mt-4 p-3 bg-red-50 text-red-600 text-sm rounded-md border border-red-100">
                  {deleteError}
                </div>
              )}
            </div>
            
            <div className="px-5 py-4 bg-black/5 flex justify-end gap-3 border-t border-brand-border">
              <button
                onClick={() => setSourceToDelete(null)}
                disabled={isDeleting}
                className="px-4 py-2 text-sm font-medium text-brand-text bg-transparent hover:bg-black/5 rounded-md transition-colors disabled:opacity-50"
              >
                Cancel
              </button>
              <button
                onClick={handleDeleteConfirm}
                disabled={isDeleting}
                className="px-4 py-2 text-sm font-medium text-white bg-red-600 hover:bg-red-700 rounded-md transition-colors disabled:opacity-50 flex items-center gap-2"
              >
                {isDeleting ? 'Removing...' : 'Remove source'}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
