"use client";

import React, { useState, useRef } from 'react';
import { X, FileText, Link as LinkIcon, UploadCloud, AlertCircle, CheckCircle2, Loader2 } from 'lucide-react';
import { Source, uploadPdf, ingestUrl } from '@/lib/api';

interface AddSourceModalProps {
  isOpen: boolean;
  onClose: () => void;
  onSourceAdded: (source: Source, chunks?: any[]) => void;
}

export default function AddSourceModal({ isOpen, onClose, onSourceAdded }: AddSourceModalProps) {
  const [activeTab, setActiveTab] = useState<'pdf' | 'url'>('pdf');
  const [url, setUrl] = useState('');
  const [file, setFile] = useState<File | null>(null);
  
  const [status, setStatus] = useState<'idle' | 'loading' | 'success' | 'error'>('idle');
  const [errorMessage, setErrorMessage] = useState('');
  const [successMessage, setSuccessMessage] = useState('');
  
  const fileInputRef = useRef<HTMLInputElement>(null);

  if (!isOpen) return null;

  const resetState = () => {
    setStatus('idle');
    setErrorMessage('');
    setSuccessMessage('');
    setUrl('');
    setFile(null);
  };

  const handleClose = () => {
    resetState();
    onClose();
  };

  const handleUrlSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!url.trim()) return;
    
    setStatus('loading');
    try {
      const res = await ingestUrl(url);
      setStatus('success');
      setSuccessMessage(`Added ${res.source.title}`);
      onSourceAdded(res.source, res.chunks);
      setTimeout(handleClose, 1500);
    } catch (err: any) {
      setStatus('error');
      setErrorMessage(err.message || 'Failed to ingest URL');
    }
  };

  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files && e.target.files.length > 0) {
      setFile(e.target.files[0]);
      setStatus('idle');
      setErrorMessage('');
    }
  };

  const handleFileUpload = async () => {
    if (!file) return;
    
    setStatus('loading');
    try {
      const res = await uploadPdf(file);
      setStatus('success');
      setSuccessMessage(`Added ${res.source.title}`);
      onSourceAdded(res.source, res.chunks);
      setTimeout(handleClose, 1500);
    } catch (err: any) {
      setStatus('error');
      setErrorMessage(err.message || 'Failed to upload PDF');
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/40 backdrop-blur-sm">
      <div className="bg-brand-bg w-full max-w-md rounded-xl shadow-2xl border border-brand-border overflow-hidden flex flex-col max-h-[90vh]">
        
        {/* Header */}
        <div className="flex items-center justify-between p-4 border-b border-brand-border bg-white">
          <h2 className="text-lg font-serif font-semibold text-brand-text">Add Source</h2>
          <button 
            onClick={handleClose}
            className="p-1.5 rounded-md text-brand-muted hover:text-brand-text hover:bg-black/5 transition-colors"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        {/* Tabs */}
        <div className="flex border-b border-brand-border bg-white">
          <button
            onClick={() => { setActiveTab('pdf'); setStatus('idle'); }}
            className={`flex-1 py-3 text-sm font-medium border-b-2 transition-colors ${
              activeTab === 'pdf' 
                ? 'border-brand-primary text-brand-primary' 
                : 'border-transparent text-brand-muted hover:text-brand-text'
            }`}
          >
            <span className="flex items-center justify-center gap-2">
              <FileText className="w-4 h-4" /> Upload PDF
            </span>
          </button>
          <button
            onClick={() => { setActiveTab('url'); setStatus('idle'); }}
            className={`flex-1 py-3 text-sm font-medium border-b-2 transition-colors ${
              activeTab === 'url' 
                ? 'border-brand-primary text-brand-primary' 
                : 'border-transparent text-brand-muted hover:text-brand-text'
            }`}
          >
            <span className="flex items-center justify-center gap-2">
              <LinkIcon className="w-4 h-4" /> Add URL
            </span>
          </button>
        </div>

        {/* Content */}
        <div className="p-6 bg-brand-bg overflow-y-auto">
          
          {/* Status Messages */}
          {status === 'error' && (
            <div className="mb-4 p-3 rounded-md bg-brand-error/10 border border-brand-error/20 flex items-start gap-3 text-brand-error">
              <AlertCircle className="w-5 h-5 flex-shrink-0 mt-0.5" />
              <div className="text-sm">{errorMessage}</div>
            </div>
          )}
          
          {status === 'success' && (
            <div className="mb-4 p-3 rounded-md bg-brand-success/10 border border-brand-success/20 flex items-center gap-3 text-brand-success">
              <CheckCircle2 className="w-5 h-5 flex-shrink-0" />
              <div className="text-sm font-medium">{successMessage}</div>
            </div>
          )}

          {/* URL Tab */}
          {activeTab === 'url' && (
            <form onSubmit={handleUrlSubmit} className="space-y-4">
              <div>
                <label htmlFor="url" className="block text-sm font-medium text-brand-text mb-1.5">
                  Web Page URL
                </label>
                <input
                  id="url"
                  type="url"
                  value={url}
                  onChange={(e) => setUrl(e.target.value)}
                  placeholder="https://example.com/article"
                  className="w-full px-3 py-2 bg-white border border-brand-border rounded-md text-brand-text focus:outline-none focus:ring-2 focus:ring-brand-primary/20 focus:border-brand-primary transition-all"
                  required
                  disabled={status === 'loading' || status === 'success'}
                />
              </div>
              <button
                type="submit"
                disabled={!url.trim() || status === 'loading' || status === 'success'}
                className="w-full flex items-center justify-center gap-2 px-4 py-2.5 bg-brand-primary text-white font-medium rounded-md hover:bg-brand-primary/90 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
              >
                {status === 'loading' ? (
                  <><Loader2 className="w-4 h-4 animate-spin" /> Ingesting...</>
                ) : (
                  'Add Source'
                )}
              </button>
            </form>
          )}

          {/* PDF Tab */}
          {activeTab === 'pdf' && (
            <div className="space-y-4">
              <div 
                className={`border-2 border-dashed rounded-lg p-8 text-center transition-colors ${
                  file ? 'border-brand-primary/50 bg-brand-primary/5' : 'border-brand-border bg-white hover:border-brand-primary/30 hover:bg-black/5'
                }`}
              >
                <input
                  type="file"
                  accept="application/pdf"
                  className="hidden"
                  ref={fileInputRef}
                  onChange={handleFileChange}
                  disabled={status === 'loading' || status === 'success'}
                />
                
                {file ? (
                  <div className="flex flex-col items-center">
                    <FileText className="w-8 h-8 text-brand-primary mb-3" />
                    <p className="text-sm font-medium text-brand-text mb-1 truncate max-w-[250px]">{file.name}</p>
                    <p className="text-xs text-brand-muted mb-4">{(file.size / 1024 / 1024).toFixed(2)} MB</p>
                    <button
                      onClick={() => setFile(null)}
                      disabled={status === 'loading' || status === 'success'}
                      className="text-xs font-medium text-brand-secondary hover:underline disabled:opacity-50"
                    >
                      Remove file
                    </button>
                  </div>
                ) : (
                  <div className="flex flex-col items-center" onClick={() => fileInputRef.current?.click()} role="button" tabIndex={0}>
                    <UploadCloud className="w-8 h-8 text-brand-muted mb-3" />
                    <p className="text-sm font-medium text-brand-text mb-1">Click to upload PDF</p>
                    <p className="text-xs text-brand-muted">or drag and drop here</p>
                  </div>
                )}
              </div>
              
              <button
                onClick={handleFileUpload}
                disabled={!file || status === 'loading' || status === 'success'}
                className="w-full flex items-center justify-center gap-2 px-4 py-2.5 bg-brand-primary text-white font-medium rounded-md hover:bg-brand-primary/90 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
              >
                {status === 'loading' ? (
                  <><Loader2 className="w-4 h-4 animate-spin" /> Uploading...</>
                ) : (
                  'Upload PDF'
                )}
              </button>
            </div>
          )}

        </div>
      </div>
    </div>
  );
}
