'use client';

import * as React from 'react';
import { useDropzone, Accept } from 'react-dropzone';
import { Upload, X, FileText, Image as ImageIcon } from 'lucide-react';
import { cn } from '@/lib/utils';

interface FileWithPreview extends File {
  preview?: string;
}

interface FileUploadProps {
  onFilesChange: (files: File[]) => void;
  accept?: Accept;
  maxFiles?: number;
  maxSize?: number; // bytes
  multiple?: boolean;
  label?: string;
  description?: string;
  className?: string;
  initialFiles?: FileWithPreview[];
}

export function FileUpload({
  onFilesChange,
  accept,
  maxFiles = 20,
  maxSize = 50 * 1024 * 1024, // 50MB
  multiple = true,
  label,
  description,
  className,
}: FileUploadProps) {
  const [files, setFiles] = React.useState<FileWithPreview[]>([]);
  const [uploadProgress, setUploadProgress] = React.useState<Record<string, number>>({});

  const onDrop = React.useCallback(
    (acceptedFiles: File[]) => {
      const newFiles = acceptedFiles.map((file) =>
        Object.assign(file, {
          preview: file.type.startsWith('image/')
            ? URL.createObjectURL(file)
            : undefined,
        })
      );
      const updated = multiple ? [...files, ...newFiles].slice(0, maxFiles) : newFiles.slice(0, 1);
      setFiles(updated);
      onFilesChange(updated);

      // Simulate upload progress for UX
      newFiles.forEach((file) => {
        const name = file.name;
        let progress = 0;
        const interval = setInterval(() => {
          progress += 20;
          setUploadProgress((prev) => ({ ...prev, [name]: progress }));
          if (progress >= 100) {
            clearInterval(interval);
          }
        }, 200);
      });
    },
    [files, maxFiles, multiple, onFilesChange]
  );

  const removeFile = (index: number) => {
    const updated = files.filter((_, i) => i !== index);
    setFiles(updated);
    onFilesChange(updated);
  };

  React.useEffect(() => {
    return () => {
      files.forEach((file) => {
        if (file.preview) URL.revokeObjectURL(file.preview);
      });
    };
  }, [files]);

  const { getRootProps, getInputProps, isDragActive } = useDropzone({
    onDrop,
    accept,
    maxFiles,
    maxSize,
    multiple,
  });

  return (
    <div className={cn('flex flex-col gap-3', className)}>
      {label && (
        <label className="text-sm font-medium text-[var(--foreground)]">{label}</label>
      )}
      <div
        {...getRootProps()}
        className={cn(
          'border-2 border-dashed rounded-xl p-6 text-center cursor-pointer transition-colors',
          isDragActive
            ? 'border-primary-400 bg-primary-50 dark:bg-primary-900/10'
            : 'border-[var(--border)] hover:border-primary-300 hover:bg-[var(--muted-bg)]'
        )}
      >
        <input {...getInputProps()} />
        <Upload className="w-8 h-8 text-[var(--muted)] mx-auto mb-2" />
        {isDragActive ? (
          <p className="text-sm text-primary-600 font-medium">Drop files here...</p>
        ) : (
          <>
            <p className="text-sm font-medium text-[var(--foreground)]">
              Drag & drop files here, or click to browse
            </p>
            {description && (
              <p className="text-xs text-[var(--muted)] mt-1">{description}</p>
            )}
          </>
        )}
      </div>

      {files.length > 0 && (
        <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 gap-3">
          {files.map((file, index) => (
            <div
              key={`${file.name}-${index}`}
              className="relative group rounded-lg border border-[var(--border)] overflow-hidden bg-[var(--muted-bg)]"
            >
              {file.preview ? (
                // eslint-disable-next-line @next/next/no-img-element
                <img
                  src={file.preview}
                  alt={file.name}
                  className="w-full h-24 object-cover"
                />
              ) : (
                <div className="w-full h-24 flex flex-col items-center justify-center gap-1">
                  {file.type === 'application/pdf' ? (
                    <FileText className="w-8 h-8 text-red-400" />
                  ) : (
                    <ImageIcon className="w-8 h-8 text-[var(--muted)]" />
                  )}
                  <span className="text-xs text-[var(--muted)] px-2 text-center truncate w-full">
                    {file.name}
                  </span>
                </div>
              )}

              {/* Progress overlay */}
              {uploadProgress[file.name] !== undefined && uploadProgress[file.name] < 100 && (
                <div className="absolute bottom-0 left-0 right-0 h-1 bg-[var(--border)]">
                  <div
                    className="h-full bg-primary-400 transition-all"
                    style={{ width: `${uploadProgress[file.name]}%` }}
                  />
                </div>
              )}

              {/* Remove button */}
              <button
                type="button"
                onClick={() => removeFile(index)}
                className="absolute top-1 right-1 w-5 h-5 rounded-full bg-black/60 text-white flex items-center justify-center opacity-0 group-hover:opacity-100 transition-opacity"
              >
                <X className="w-3 h-3" />
              </button>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
