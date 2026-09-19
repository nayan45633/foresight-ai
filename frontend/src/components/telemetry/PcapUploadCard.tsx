'use client';

import React, { useState, useRef } from 'react';
import { telemetryApi } from '@/lib/api/telemetry';
import { ApiError } from '@/lib/api/client';
import { 
  UploadCloud, 
  FileText, 
  CheckCircle, 
  AlertCircle, 
  Loader2, 
  Clock, 
  Layers,
  ArrowRight
} from 'lucide-react';
import { PcapJobStatus, PcapUploadResponse } from '@/types/telemetry';

interface PcapUploadCardProps {
  onUploadSuccess?: () => void;
}

export const PcapUploadCard: React.FC<PcapUploadCardProps> = ({ onUploadSuccess }) => {
  const [dragActive, setDragActive] = useState(false);
  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [uploading, setUploading] = useState(false);
  const [jobStatus, setJobStatus] = useState<PcapJobStatus | null>(null);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);

  const handleDrag = (e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
    if (e.type === 'dragenter' || e.type === 'dragover') {
      setDragActive(true);
    } else if (e.type === 'dragleave') {
      setDragActive(false);
    }
  };

  const handleDrop = (e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
    setDragActive(false);
    if (e.dataTransfer.files && e.dataTransfer.files[0]) {
      handleFile(e.dataTransfer.files[0]);
    }
  };

  const handleFile = (file: File) => {
    const ext = file.name.substring(file.name.lastIndexOf('.')).toLowerCase();
    if (!['.pcap', '.pcapng', '.cap'].includes(ext)) {
      setErrorMessage(`Unsupported format '${ext}'. Please upload a .pcap or .pcapng file.`);
      setSelectedFile(null);
      return;
    }
    if (file.size > 50 * 1024 * 1024) {
      setErrorMessage('File size exceeds maximum 50 MB limit.');
      setSelectedFile(null);
      return;
    }
    setErrorMessage(null);
    setSelectedFile(file);
    setJobStatus(null);
  };

  const formatFileSize = (bytes: number) => {
    if (bytes < 1024) return `${bytes} B`;
    if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
    return `${(bytes / (1024 * 1024)).toFixed(2)} MB`;
  };

  const pollJobStatus = (jobId: string) => {
    const interval = setInterval(async () => {
      try {
        const data = await telemetryApi.getPcapStatus(jobId);
        setJobStatus(data as any);
        if (data.status === 'COMPLETED' || data.status === 'FAILED') {
          clearInterval(interval);
          setUploading(false);
          if (data.status === 'COMPLETED' && onUploadSuccess) {
            onUploadSuccess();
          }
          if (data.status === 'FAILED') {
            setErrorMessage(data.error_message || 'Packet parsing or flow reconstruction failed on the backend.');
          }
        }
      } catch (err: any) {
        clearInterval(interval);
        setUploading(false);
        setErrorMessage(err.message || 'Could not query ingestion job status.');
      }
    }, 1000);
  };

  const startUpload = async () => {
    if (!selectedFile) return;
    setUploading(true);
    setErrorMessage(null);

    try {
      const uploadResp = await telemetryApi.uploadPcap(selectedFile);
      setJobStatus({
        job_id: uploadResp.job_id,
        filename: uploadResp.filename,
        file_size_bytes: uploadResp.file_size_bytes,
        status: uploadResp.status,
        created_at: new Date().toISOString(),
        records_processed: 0,
        flows_generated: 0,
        records_rejected: 0,
        processing_duration_ms: 0,
      });

      // Poll until completion
      pollJobStatus(uploadResp.job_id);

    } catch (err: any) {
      setUploading(false);
      setErrorMessage(err.message || 'PCAP upload failed. Please verify file integrity.');
    }
  };

  return (
    <div className="glass-panel p-5 sm:p-6 rounded-2xl border border-glass-border">
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2 border-b border-white/[0.06] pb-4 mb-5">
        <div className="flex items-center gap-2.5">
          <UploadCloud className="w-5 h-5 text-cyan-400" />
          <h3 className="text-sm font-semibold text-white">
            Network Packet Capture (PCAP) Ingestion
          </h3>
        </div>
        <span className="text-[11px] font-mono text-slate-400 bg-slate-900/80 px-2.5 py-1 rounded-full border border-white/[0.06] self-start sm:self-auto">
          Max 50 MB • .pcap / .pcapng
        </span>
      </div>

      {/* Drag and Drop Zone */}
      <div
        onDragEnter={handleDrag}
        onDragLeave={handleDrag}
        onDragOver={handleDrag}
        onDrop={handleDrop}
        onClick={() => fileInputRef.current?.click()}
        className={`border border-dashed rounded-2xl p-7 text-center cursor-pointer transition-all duration-200 ${
          dragActive
            ? 'border-cyan-400/80 bg-cyan-950/25 shadow-glass-elevated'
            : 'border-white/[0.08] hover:border-white/[0.18] bg-slate-950/40 hover:bg-slate-900/30'
        }`}
      >
        <input
          ref={fileInputRef}
          type="file"
          accept=".pcap,.pcapng,.cap"
          className="hidden"
          onChange={(e) => e.target.files?.[0] && handleFile(e.target.files[0])}
        />

        <UploadCloud className="w-9 h-9 text-cyan-400/70 mx-auto mb-2.5" />
        <p className="text-sm font-medium text-slate-200">
          {selectedFile ? selectedFile.name : 'Drop PCAP file here or click to browse'}
        </p>
        <p className="text-xs text-slate-400 mt-1">
          {selectedFile
            ? `${formatFileSize(selectedFile.size)} • Ready for packet parsing`
            : 'Streams through Scapy packet engine & bidirectional flow reconstructor'}
        </p>
      </div>

      {/* Error Banner */}
      {errorMessage && (
        <div className="mt-4 p-3.5 rounded-xl bg-red-950/40 border border-red-800/60 flex items-center gap-2.5 text-xs text-red-300 font-mono">
          <AlertCircle className="w-4 h-4 text-red-400 shrink-0" />
          <span>{errorMessage}</span>
        </div>
      )}

      {/* Action Button */}
      {selectedFile && !jobStatus && (
        <div className="mt-4 flex justify-end">
          <button
            onClick={startUpload}
            disabled={uploading}
            className="px-5 py-2.5 rounded-xl bg-cyan-500 hover:bg-cyan-400 text-slate-950 font-semibold text-xs transition-all duration-200 flex items-center gap-2 shadow-sm disabled:opacity-50 active:scale-[0.98]"
          >
            {uploading ? (
              <>
                <Loader2 className="w-4 h-4 animate-spin" /> Ingesting & Parsing...
              </>
            ) : (
              <>
                Parse Packets & Reconstruct Flows <ArrowRight className="w-4 h-4" />
              </>
            )}
          </button>
        </div>
      )}

      {/* Job Status Banner */}
      {jobStatus && (
        <div className="mt-4 p-4 rounded-xl bg-slate-900/70 border border-white/[0.06] space-y-3 font-mono text-xs">
          <div className="flex items-center justify-between">
            <span className="text-slate-400">JOB ID: {jobStatus.job_id}</span>
            <span
              className={`px-2.5 py-0.5 rounded-full font-bold text-[10px] uppercase border ${
                jobStatus.status === 'COMPLETED'
                  ? 'bg-emerald-950/80 text-emerald-300 border-emerald-800'
                  : jobStatus.status === 'PROCESSING'
                  ? 'bg-cyan-950/80 text-cyan-300 border-cyan-800 animate-pulse'
                  : jobStatus.status === 'FAILED'
                  ? 'bg-red-950/80 text-red-300 border-red-800'
                  : 'bg-slate-800 text-slate-300 border-slate-700'
              }`}
            >
              {jobStatus.status}
            </span>
          </div>

          <div className="grid grid-cols-3 gap-2 text-center pt-2 border-t border-white/[0.06]">
            <div className="bg-slate-950/60 p-2.5 rounded-lg border border-white/[0.04]">
              <span className="text-[10px] text-slate-500 block">PACKETS</span>
              <span className="text-sm font-bold text-slate-200">
                {jobStatus.records_processed}
              </span>
            </div>
            <div className="bg-slate-950/60 p-2.5 rounded-lg border border-white/[0.04]">
              <span className="text-[10px] text-cyan-500 block">FLOWS</span>
              <span className="text-sm font-bold text-cyan-400">
                {jobStatus.flows_generated}
              </span>
            </div>
            <div className="bg-slate-950/60 p-2.5 rounded-lg border border-white/[0.04]">
              <span className="text-[10px] text-slate-500 block">LATENCY</span>
              <span className="text-sm font-bold text-slate-200">
                {jobStatus.processing_duration_ms > 0 ? `${jobStatus.processing_duration_ms}ms` : '...'}
              </span>
            </div>
          </div>

          {jobStatus.status === 'COMPLETED' && (
            <div className="flex items-center gap-1.5 text-emerald-400 text-[11px] pt-1">
              <CheckCircle className="w-3.5 h-3.5" />
              <span>Bidirectional flows reconstructed and synchronized into live telemetry engine.</span>
            </div>
          )}
        </div>
      )}
    </div>
  );
};
