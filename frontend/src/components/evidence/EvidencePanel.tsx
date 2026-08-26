import React from 'react';
import { X, FileText, Globe, ExternalLink } from 'lucide-react';
import { SourceRef } from '@/lib/api';

interface EvidencePanelProps {
  sourceRef: SourceRef | null;
  chunkText?: string;
  onClose: () => void;
}

export default function EvidencePanel({ sourceRef, chunkText, onClose }: EvidencePanelProps) {
  if (!sourceRef) return null;

  const isWeb = sourceRef.source_type === 'web';
  // Research mode returns text inline; Ask mode passes chunkText from local cache
  const evidenceText = sourceRef.text || chunkText || null;

  return (
    <div className="fixed inset-y-0 right-0 w-[85vw] sm:w-80 md:w-96 max-w-full bg-brand-evidence border-l border-brand-border shadow-2xl flex flex-col z-40 transform transition-transform duration-300">
      <div className="flex items-center justify-between p-4 border-b border-brand-border/50">
        <h3 className="text-sm font-semibold uppercase tracking-wider text-brand-primary">Supporting Evidence</h3>
        <button
          onClick={onClose}
          className="p-1 rounded-md text-brand-primary/60 hover:text-brand-primary hover:bg-black/5 transition-colors"
        >
          <X className="w-5 h-5" />
        </button>
      </div>

      <div className="p-5 flex-1 overflow-y-auto">
        {/* Source type badge */}
        <div className="mb-4 flex items-center gap-2">
          {isWeb ? (
            <span className="flex items-center gap-1.5 text-xs font-semibold px-2 py-1 bg-blue-50 text-blue-700 border border-blue-200 rounded-md">
              <Globe className="w-3.5 h-3.5" /> Web Source
            </span>
          ) : (
            <span className="flex items-center gap-1.5 text-xs font-semibold px-2 py-1 bg-brand-primary/5 text-brand-primary border border-brand-primary/20 rounded-md">
              <FileText className="w-3.5 h-3.5" /> Document
            </span>
          )}
        </div>

        {/* Source identifier */}
        <div className="mb-5">
          <div className="text-xs font-medium text-brand-primary/60 uppercase tracking-wide mb-1">Source</div>
          {isWeb && sourceRef.url ? (
            <a
              href={sourceRef.url}
              target="_blank"
              rel="noopener noreferrer"
              className="flex items-start gap-2 text-sm font-medium text-blue-600 hover:underline break-all"
            >
              <ExternalLink className="w-4 h-4 mt-0.5 flex-shrink-0" />
              {sourceRef.url}
            </a>
          ) : (
            <div className="flex items-start gap-2">
              <FileText className="w-4 h-4 mt-0.5 text-brand-primary flex-shrink-0" />
              <span className="text-sm font-medium text-brand-text truncate" title={sourceRef.document_id}>
                {sourceRef.document_id.split('-')[0]}... (doc_{sourceRef.document_id.substring(0, 4)})
              </span>
            </div>
          )}
        </div>

        {/* Page number (PDF only) */}
        {!isWeb && sourceRef.page_number && (
          <div className="mb-5">
            <div className="text-xs font-medium text-brand-primary/60 uppercase tracking-wide mb-1">Page</div>
            <div className="text-sm text-brand-text font-mono bg-white/50 px-2 py-1 rounded inline-block">
              {sourceRef.page_number}
            </div>
          </div>
        )}

        {/* Evidence text */}
        <div>
          <div className="text-xs font-medium text-brand-primary/60 uppercase tracking-wide mb-2">Retrieved Context</div>
          <div className="text-sm text-brand-text leading-relaxed font-serif bg-white/50 p-4 rounded-md border border-brand-border/30">
            {evidenceText || (
              <span className="text-brand-muted italic">
                Evidence text unavailable for this source.
              </span>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
