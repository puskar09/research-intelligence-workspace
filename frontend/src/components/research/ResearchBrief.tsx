import React from 'react';
import { SourceRef, ResearchQueryResponse } from '@/lib/api';
import { BookOpen, HelpCircle, CheckCircle2, AlertCircle } from 'lucide-react';

interface ResearchBriefProps {
  data: ResearchQueryResponse;
  onCitationClick: (source: SourceRef) => void;
}

export default function ResearchBrief({ data, onCitationClick }: ResearchBriefProps) {
  const renderTextWithCitations = (text: string) => {
    // Extract unique cited indices to map correctly to the filtered sources array
    const extractCitedIndices = () => {
      const regex = /\[(\d+)\]/g;
      let match;
      const indices = new Set<number>();
      while ((match = regex.exec(text)) !== null) {
        indices.add(parseInt(match[1], 10));
      }
      return Array.from(indices).sort((a, b) => a - b);
    };
    
    const citedIndices = extractCitedIndices();

    const parts = text.split(/(\[\d+\])/g);
    
    return parts.map((part, index) => {
      const match = part.match(/\[(\d+)\]/);
      if (match) {
        const originalIndex = parseInt(match[1], 10);
        const sourceIndex = citedIndices.indexOf(originalIndex);
        const source = sourceIndex !== -1 ? data.sources[sourceIndex] : undefined;
        
        if (source) {
          return (
            <button
              key={index}
              onClick={() => onCitationClick(source)}
              className="inline-flex items-center justify-center px-1.5 py-0.5 mx-0.5 text-xs font-semibold text-brand-primary bg-brand-primary/10 hover:bg-brand-primary/20 rounded cursor-pointer transition-colors align-baseline"
              title={`View Source`}
            >
              {match[1]}
            </button>
          );
        }
      }
      return <span key={index}>{part}</span>;
    });
  };

  return (
    <div className="w-full max-w-4xl mx-auto flex flex-col gap-8 pb-12">
      
      {/* Header */}
      <div className="border-b-2 border-brand-primary pb-6 text-center">
        <div className="text-xs font-bold tracking-widest uppercase text-brand-muted mb-4">Research Brief</div>
        <h2 className="text-3xl font-serif text-brand-text mb-4 leading-tight">{data.original_query}</h2>
      </div>

      {/* Executive Summary */}
      <section className="bg-brand-evidence/30 border border-brand-border rounded-xl p-6 md:p-8 shadow-sm">
        <h3 className="text-sm font-semibold tracking-wider uppercase text-brand-primary mb-4 flex items-center gap-2">
          <BookOpen className="w-4 h-4" />
          Executive Summary
        </h3>
        <div className="text-base md:text-lg text-brand-text leading-relaxed font-serif whitespace-pre-wrap">
          {renderTextWithCitations(data.overall_summary)}
        </div>
      </section>

      {/* Sub Questions */}
      <section>
        <h3 className="text-sm font-semibold tracking-wider uppercase text-brand-muted mb-4 flex items-center gap-2">
          <HelpCircle className="w-4 h-4" />
          Research Directions
        </h3>
        <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
          {data.sub_questions.map((q, i) => (
            <div key={i} className="flex gap-3 bg-white border border-brand-border rounded-lg p-4 shadow-sm">
              <span className="text-brand-muted font-mono text-sm mt-0.5">{(i+1).toString().padStart(2, '0')}</span>
              <p className="text-sm text-brand-text font-medium leading-snug">{q}</p>
            </div>
          ))}
        </div>
      </section>

      {/* Key Findings */}
      <section>
        <h3 className="text-sm font-semibold tracking-wider uppercase text-brand-muted mb-6 mt-4">
          Key Findings
        </h3>
        
        <div className="space-y-6">
          {data.findings.map((finding, i) => (
            <div key={i} className="bg-white border border-brand-border rounded-xl overflow-hidden shadow-sm">
              <div className="bg-brand-bg px-5 py-4 border-b border-brand-border flex items-start justify-between gap-4">
                <div className="flex gap-3 items-start">
                  <span className="text-brand-primary font-mono text-sm font-bold mt-0.5">{(i+1).toString().padStart(2, '0')}</span>
                  <h4 className="text-base font-semibold text-brand-text">{finding.sub_question}</h4>
                </div>
                {finding.insufficient_evidence ? (
                  <span className="flex items-center gap-1.5 px-2 py-1 bg-brand-error/10 text-brand-error text-xs font-semibold rounded-md flex-shrink-0">
                    <AlertCircle className="w-3.5 h-3.5" /> Insufficient
                  </span>
                ) : (
                  <span className="flex items-center gap-1.5 px-2 py-1 bg-brand-success/10 text-brand-success text-xs font-semibold rounded-md flex-shrink-0">
                    <CheckCircle2 className="w-3.5 h-3.5" /> Answered
                  </span>
                )}
              </div>
              <div className="p-5 md:p-6 text-base text-brand-text leading-relaxed font-serif whitespace-pre-wrap">
                {renderTextWithCitations(finding.evidence)}
              </div>
            </div>
          ))}
        </div>
      </section>

    </div>
  );
}
