import { useCallback, useRef, useState } from "react";
import { FileText, UploadCloud, X } from "lucide-react";
import { cn } from "@/lib/utils";
import { Button } from "@/components/ui/button";

const ACCEPT = [".pptx", ".pdf"];
const MAX_MB = 40;

function prettySize(bytes) {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

/**
 * Drag-and-drop upload zone with a file-preview card after selection.
 * `onFile(file)` fires only for an accepted, size-valid file.
 */
export default function FileDropzone({ file, onFile, onClear, disabled }) {
  const inputRef = useRef(null);
  const [over, setOver] = useState(false);
  const [err, setErr] = useState("");

  const accept = useCallback((f) => {
    setErr("");
    const ext = "." + f.name.split(".").pop().toLowerCase();
    if (!ACCEPT.includes(ext)) {
      setErr(`Unsupported file type. Use ${ACCEPT.join(" or ")}.`);
      return;
    }
    if (f.size > MAX_MB * 1024 * 1024) {
      setErr(`File is too large (max ${MAX_MB} MB).`);
      return;
    }
    onFile(f);
  }, [onFile]);

  if (file) {
    return (
      <div className="flex items-center gap-3 rounded-lg border bg-card p-4">
        <div className="flex size-10 shrink-0 items-center justify-center rounded-md bg-primary/10 text-primary">
          <FileText className="size-5" />
        </div>
        <div className="min-w-0 flex-1">
          <p className="truncate text-sm font-medium">{file.name}</p>
          <p className="text-xs text-muted-foreground">
            {prettySize(file.size)} · {file.name.split(".").pop().toUpperCase()}
          </p>
        </div>
        <Button variant="ghost" size="icon" onClick={onClear} disabled={disabled}>
          <X />
          <span className="sr-only">Remove file</span>
        </Button>
      </div>
    );
  }

  return (
    <div>
      <button
        type="button"
        disabled={disabled}
        onClick={() => inputRef.current?.click()}
        onDragOver={(e) => {
          e.preventDefault();
          setOver(true);
        }}
        onDragLeave={() => setOver(false)}
        onDrop={(e) => {
          e.preventDefault();
          setOver(false);
          const f = e.dataTransfer.files?.[0];
          if (f) accept(f);
        }}
        className={cn(
          "flex w-full flex-col items-center gap-2 rounded-xl border-2 border-dashed px-6 py-12 text-center transition-colors",
          over ? "border-primary bg-primary/5" : "border-border hover:border-primary/50 hover:bg-muted/40",
          disabled && "pointer-events-none opacity-60"
        )}
      >
        <div className="flex size-12 items-center justify-center rounded-full bg-primary/10 text-primary">
          <UploadCloud className="size-6" />
        </div>
        <p className="text-sm font-medium">Drag &amp; drop your PPTX or PDF</p>
        <p className="text-xs text-muted-foreground">or click to browse · up to {MAX_MB} MB</p>
      </button>
      <input
        ref={inputRef}
        type="file"
        accept={ACCEPT.join(",")}
        hidden
        onChange={(e) => {
          const f = e.target.files?.[0];
          if (f) accept(f);
          e.target.value = "";
        }}
      />
      {err ? <p className="mt-2 text-xs text-destructive">{err}</p> : null}
    </div>
  );
}
