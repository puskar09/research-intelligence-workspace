import React from 'react';
import { DiscoveryQuestion } from '@/lib/api';

interface DiscoveryViewProps {
  topic: string;
  questions: DiscoveryQuestion[];
  onSelect: (question: string) => void;
}

export default function DiscoveryView({ topic, questions, onSelect }: DiscoveryViewProps) {
  if (questions.length === 0) return null;

  return (
    <div className="w-full max-w-4xl mx-auto mt-8 animate-in fade-in slide-in-from-bottom-4 duration-500">
      <div className="mb-6">
        <h2 className="text-xl font-serif font-medium text-brand-primary mb-2">Research Directions</h2>
        <p className="text-sm text-brand-muted">Select a question below to begin your research on <span className="font-medium text-brand-text">"{topic}"</span>.</p>
      </div>

      <div className="flex flex-col gap-3">
        {questions.map((q, idx) => (
          <button
            key={q.id}
            onClick={() => onSelect(q.question)}
            className="group flex items-start gap-4 p-4 md:p-5 bg-white border border-brand-border rounded-xl shadow-sm hover:shadow-md hover:border-brand-accent/30 transition-all text-left w-full"
          >
            <div className="flex-shrink-0 mt-0.5">
              <span className="text-sm font-medium text-brand-muted/70 group-hover:text-brand-accent transition-colors">
                {String(idx + 1).padStart(2, '0')}
              </span>
            </div>
            <div className="flex-1">
              <h3 className="text-brand-text font-medium text-lg leading-snug mb-1.5 group-hover:text-brand-primary transition-colors">
                {q.question}
              </h3>
              <span className="inline-block px-2 py-0.5 rounded text-xs font-medium bg-brand-evidence text-brand-muted">
                {q.category}
              </span>
            </div>
          </button>
        ))}
      </div>
    </div>
  );
}
