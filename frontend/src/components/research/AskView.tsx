import React from 'react';
import { SourceRef } from '@/lib/api';
import { FileText } from 'lucide-react';

interface AskViewProps {
  answer: string;
  sources: SourceRef[];
  onCitationClick: (source: SourceRef) => void;
}

export default function AskView({ answer, sources, onCitationClick }: AskViewProps) {
  // The backend returns only the cited sources, preserving their original relative order.
  // We extract all unique cited indices from the answer, sort them, and use the 
  // index of the citation in that sorted list to map to the `sources` array.
  const extractCitedIndices = () => {
    const regex = /\[(\d+)\]/g;
    let match;
    const indices = new Set<number>();
    while ((match = regex.exec(answer)) !== null) {
      indices.add(parseInt(match[1], 10));
    }
    return Array.from(indices).sort((a, b) => a - b);
  };
  
  const citedIndices = extractCitedIndices();

  // Function to parse the answer and replace [1] with interactive buttons
  const renderAnswerWithCitations = () => {
    // Regex to match [1], [2], etc.
    const parts = answer.split(/(\[\d+\])/g);
    
    return parts.map((part, index) => {
      const match = part.match(/\[(\d+)\]/);
      if (match) {
        const originalIndex = parseInt(match[1], 10);
        const sourceIndex = citedIndices.indexOf(originalIndex);
        const source = sourceIndex !== -1 ? sources[sourceIndex] : undefined;
        
        if (source) {
          return (
            <button
              key={index}
              onClick={() => onCitationClick(source)}
              className="inline-flex items-center justify-center px-1.5 py-0.5 mx-0.5 text-xs font-semibold text-brand-primary bg-brand-primary/10 hover:bg-brand-primary/20 rounded cursor-pointer transition-colors align-baseline"
              title={`View Source: ${source.document_id}`}
            >
              {match[1]}
            </button>
          );
        }
      }
      // Return regular text
      return <span key={index}>{part}</span>;
    });
  };

  return (
    <div className="w-full max-w-3xl mx-auto bg-white border border-brand-border rounded-xl shadow-sm overflow-hidden flex flex-col">
      <div className="p-4 border-b border-brand-border bg-brand-bg flex items-center justify-between">
        <h3 className="text-sm font-semibold text-brand-text flex items-center gap-2">
          <FileText className="w-4 h-4 text-brand-primary" />
          Answer
        </h3>
        {sources.length > 0 && (
          <span className="text-xs font-medium text-brand-muted bg-white px-2 py-1 rounded border border-brand-border">
            {sources.length} {sources.length === 1 ? 'source' : 'sources'} cited
          </span>
        )}
      </div>
      <div className="p-6 md:p-8 text-base md:text-lg text-brand-text leading-relaxed whitespace-pre-wrap font-serif">
        {renderAnswerWithCitations()}
      </div>
    </div>
  );
}
