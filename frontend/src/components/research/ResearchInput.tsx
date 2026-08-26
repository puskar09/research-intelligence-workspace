import React, { useState } from 'react';
import { Search, Loader2 } from 'lucide-react';

interface ResearchInputProps {
  onAsk: (query: string) => void;
  onResearch: (query: string, webSearch: boolean) => void;
  isProcessing: boolean;
}

export default function ResearchInput({ onAsk, onResearch, isProcessing }: ResearchInputProps) {
  const [query, setQuery] = useState('');
  const [webSearch, setWebSearch] = useState(false);

  const handleAsk = () => {
    if (!query.trim() || isProcessing) return;
    onAsk(query);
  };

  const handleResearch = () => {
    if (!query.trim() || isProcessing) return;
    onResearch(query, webSearch);
  };

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      // Default to Ask on Enter
      handleAsk();
    }
  };

  return (
    <div className="w-full max-w-3xl mx-auto flex flex-col gap-4">
      <div className="text-center mb-2">
        <h2 className="text-3xl font-serif text-brand-primary mb-2">Research something.</h2>
        <p className="text-sm text-brand-muted">Ask a question across your sources, or investigate it with the web.</p>
      </div>

      <div className="relative group">
        <textarea
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          onKeyDown={handleKeyDown}
          placeholder="What do you want to investigate?"
          className="w-full min-h-[120px] p-5 pb-16 bg-white border border-brand-border rounded-xl text-lg text-brand-text resize-none focus:outline-none focus:ring-2 focus:ring-brand-primary/20 focus:border-brand-primary transition-all shadow-sm"
          disabled={isProcessing}
        />
        
        <div className="absolute bottom-3 left-4 flex items-center gap-2">
          <button
            type="button"
            role="switch"
            aria-checked={webSearch}
            disabled={isProcessing}
            onClick={() => setWebSearch(!webSearch)}
            className={`relative inline-flex h-5 w-9 shrink-0 cursor-pointer items-center justify-center rounded-full border-2 border-transparent transition-colors focus:outline-none focus:ring-2 focus:ring-brand-primary focus:ring-offset-2 disabled:cursor-not-allowed disabled:opacity-50 ${webSearch ? 'bg-brand-primary' : 'bg-brand-muted/30'}`}
          >
            <span
              aria-hidden="true"
              className={`pointer-events-none inline-block h-4 w-4 transform rounded-full bg-white shadow ring-0 transition duration-200 ease-in-out ${webSearch ? 'translate-x-4' : 'translate-x-0'}`}
            />
          </button>
          <span 
            className="text-sm text-brand-muted cursor-pointer hover:text-brand-text transition-colors select-none"
            onClick={() => !isProcessing && setWebSearch(!webSearch)}
          >
            Search the web
          </span>
        </div>

        <div className="absolute bottom-3 right-4 flex items-center gap-2">
          <button
            onClick={handleAsk}
            disabled={!query.trim() || isProcessing}
            className="px-4 py-2 text-sm font-medium text-brand-text bg-brand-bg border border-brand-border rounded-md hover:bg-black/5 disabled:opacity-50 transition-colors"
          >
            Ask
          </button>
          <button
            onClick={handleResearch}
            disabled={!query.trim() || isProcessing}
            className="px-4 py-2 text-sm font-medium text-white bg-brand-primary rounded-md hover:bg-brand-primary/90 disabled:opacity-50 transition-colors flex items-center gap-2 shadow-sm"
          >
            {isProcessing ? <Loader2 className="w-4 h-4 animate-spin" /> : <Search className="w-4 h-4" />}
            Research
          </button>
        </div>
      </div>
    </div>
  );
}
