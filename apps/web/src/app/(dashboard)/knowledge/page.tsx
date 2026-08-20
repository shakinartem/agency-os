"use client";

import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { api } from "@/lib/api";
import { useProject } from "@/context/ProjectContext";
import { Archive, BookOpen, FileUp, RotateCcw, Search, Type } from "lucide-react";

interface KnowledgeDocument {
  id: string;
  project_id: string;
  name: string;
  source_type: string;
  mime_type?: string;
  checksum: string;
  status: string;
  char_count: number;
  chunk_count: number;
  metadata_json?: Record<string, unknown>;
  preview?: string;
  duplicate?: boolean;
  created_at?: string;
}

export default function KnowledgePage() {
  const { current } = useProject();
  const queryClient = useQueryClient();
  const [showArchived, setShowArchived] = useState(false);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [name, setName] = useState("");
  const [text, setText] = useState("");

  const { data: documents = [], isLoading } = useQuery({
    queryKey: ["knowledge", current?.id, showArchived],
    queryFn: () => api.get<KnowledgeDocument[]>(`/knowledge?project_id=${current?.id}&include_archived=${showArchived}`),
    enabled: Boolean(current?.id),
  });

  const { data: selected } = useQuery({
    queryKey: ["knowledge-document", selectedId],
    queryFn: () => api.get<KnowledgeDocument>(`/knowledge/${selectedId}`),
    enabled: Boolean(selectedId),
  });

  const invalidate = () => {
    queryClient.invalidateQueries({ queryKey: ["knowledge"] });
    queryClient.invalidateQueries({ queryKey: ["knowledge-document"] });
  };

  const addText = useMutation({
    mutationFn: () => api.post<KnowledgeDocument>("/knowledge/text", {
      project_id: current?.id,
      name,
      content: text,
      source_type: "text",
    }),
    onSuccess: (document) => {
      setName("");
      setText("");
      setSelectedId(document.id);
      invalidate();
    },
  });

  const upload = useMutation({
    mutationFn: async (file: File) => {
      const form = new FormData();
      form.append("project_id", current?.id || "");
      form.append("file", file);
      return api.postForm<KnowledgeDocument>("/knowledge/upload", form);
    },
    onSuccess: (document) => {
      setSelectedId(document.id);
      invalidate();
    },
  });

  const archive = useMutation({
    mutationFn: (id: string) => api.post(`/knowledge/${id}/archive`),
    onSuccess: invalidate,
  });

  const restore = useMutation({
    mutationFn: (id: string) => api.post(`/knowledge/${id}/restore`),
    onSuccess: invalidate,
  });

  return (
    <div className="space-y-6">
      <div>
        <div className="flex items-center gap-2 text-sm font-medium text-primary"><BookOpen className="h-4 w-4" /> Knowledge Base</div>
        <h1 className="mt-1 text-3xl font-bold tracking-tight">Материалы проекта</h1>
        <p className="mt-2 max-w-3xl text-sm text-muted-foreground">Собственные документы становятся первым источником фактов для генерации и стратегии. AI сохраняет lineage использованных чанков, но внутренние ссылки не уходят в Autoposter package.</p>
      </div>

      {!current && <div className="rounded-xl border border-dashed p-8 text-center text-sm text-muted-foreground">Выберите проект в верхней панели.</div>}

      {current && (
        <div className="grid gap-5 xl:grid-cols-[minmax(0,1fr)_420px]">
          <div className="space-y-5">
            <div className="grid gap-4 lg:grid-cols-2">
              <Card>
                <CardHeader><CardTitle className="flex items-center gap-2 text-base"><FileUp className="h-4 w-4" /> Загрузить документ</CardTitle></CardHeader>
                <CardContent className="space-y-3">
                  <label className="flex min-h-36 cursor-pointer flex-col items-center justify-center rounded-xl border border-dashed p-5 text-center hover:bg-muted/40">
                    <FileUp className="mb-3 h-7 w-7 text-muted-foreground" />
                    <span className="text-sm font-medium">Выберите файл</span>
                    <span className="mt-1 text-xs text-muted-foreground">TXT, Markdown, JSON, PDF, DOCX · до 10 MB</span>
                    <input
                      type="file"
                      accept=".txt,.md,.markdown,.json,.pdf,.docx"
                      className="hidden"
                      disabled={upload.isPending}
                      onChange={(event) => {
                        const file = event.target.files?.[0];
                        if (file) upload.mutate(file);
                        event.currentTarget.value = "";
                      }}
                    />
                  </label>
                  {upload.isPending && <p className="text-xs text-muted-foreground">Извлекаю текст и создаю чанки…</p>}
                  {upload.isError && <p className="text-xs text-red-600">{(upload.error as Error).message}</p>}
                </CardContent>
              </Card>

              <Card>
                <CardHeader><CardTitle className="flex items-center gap-2 text-base"><Type className="h-4 w-4" /> Добавить текст</CardTitle></CardHeader>
                <CardContent className="space-y-3">
                  <input value={name} onChange={(e) => setName(e.target.value)} placeholder="Название материала" className="w-full rounded-lg border bg-background px-3 py-2 text-sm outline-none focus:ring-2 focus:ring-primary/30" />
                  <textarea value={text} onChange={(e) => setText(e.target.value)} placeholder="Вставьте описание продукта, кейс, методологию, FAQ, правила продаж или другой first-party материал…" className="min-h-28 w-full resize-y rounded-lg border bg-background p-3 text-sm outline-none focus:ring-2 focus:ring-primary/30" />
                  <button onClick={() => addText.mutate()} disabled={!name.trim() || text.trim().length < 20 || addText.isPending} className="w-full rounded-lg bg-primary px-3 py-2 text-sm font-semibold text-primary-foreground disabled:opacity-50">{addText.isPending ? "Добавляю…" : "Добавить в Knowledge Base"}</button>
                  {addText.isError && <p className="text-xs text-red-600">{(addText.error as Error).message}</p>}
                </CardContent>
              </Card>
            </div>

            <Card>
              <CardHeader>
                <div className="flex items-center justify-between gap-3">
                  <CardTitle>Документы</CardTitle>
                  <label className="flex items-center gap-2 text-xs text-muted-foreground"><input type="checkbox" checked={showArchived} onChange={(e) => setShowArchived(e.target.checked)} /> показать архив</label>
                </div>
              </CardHeader>
              <CardContent className="space-y-2">
                {isLoading && <p className="text-sm text-muted-foreground">Loading…</p>}
                {documents.map((document) => (
                  <button key={document.id} onClick={() => setSelectedId(document.id)} className={`w-full rounded-xl border p-3 text-left transition ${selectedId === document.id ? "ring-2 ring-primary/30" : "hover:border-primary/40"}`}>
                    <div className="flex items-start justify-between gap-3">
                      <div className="min-w-0">
                        <p className="truncate text-sm font-semibold">{document.name}</p>
                        <p className="mt-1 text-xs text-muted-foreground">{document.source_type} · {document.chunk_count} chunks · {Math.round(document.char_count / 1000)}k chars</p>
                      </div>
                      <Badge variant="secondary">{document.status}</Badge>
                    </div>
                  </button>
                ))}
                {!isLoading && documents.length === 0 && <div className="rounded-xl border border-dashed p-8 text-center text-sm text-muted-foreground">Knowledge Base пуст. Добавьте материалы, на которые AI сможет опираться.</div>}
              </CardContent>
            </Card>
          </div>

          <div>
            {!selected && <div className="rounded-xl border border-dashed p-8 text-center text-sm text-muted-foreground">Выберите документ, чтобы посмотреть извлечённый текст и metadata.</div>}
            {selected && (
              <Card className="xl:sticky xl:top-20">
                <CardHeader>
                  <div className="flex items-start justify-between gap-3">
                    <div><CardTitle className="text-base">{selected.name}</CardTitle><p className="mt-1 text-xs text-muted-foreground">checksum {selected.checksum.slice(0, 12)}…</p></div>
                    <Badge variant="secondary">{selected.status}</Badge>
                  </div>
                </CardHeader>
                <CardContent className="space-y-4">
                  <div className="grid grid-cols-2 gap-2 text-xs">
                    <div className="rounded-lg border p-2"><p className="text-muted-foreground">Chunks</p><p className="mt-1 text-lg font-semibold">{selected.chunk_count}</p></div>
                    <div className="rounded-lg border p-2"><p className="text-muted-foreground">Characters</p><p className="mt-1 text-lg font-semibold">{selected.char_count.toLocaleString()}</p></div>
                  </div>
                  <div>
                    <p className="mb-2 flex items-center gap-1 text-xs font-semibold"><Search className="h-3.5 w-3.5" /> Извлечённый текст</p>
                    <div className="max-h-[55vh] overflow-y-auto whitespace-pre-wrap rounded-lg bg-muted/40 p-3 text-xs leading-5">{selected.preview || "—"}</div>
                  </div>
                  {selected.status === "active" ? (
                    <button onClick={() => archive.mutate(selected.id)} className="inline-flex items-center gap-2 rounded-lg border px-3 py-2 text-xs font-medium hover:bg-muted"><Archive className="h-3.5 w-3.5" /> Архивировать</button>
                  ) : (
                    <button onClick={() => restore.mutate(selected.id)} className="inline-flex items-center gap-2 rounded-lg border px-3 py-2 text-xs font-medium hover:bg-muted"><RotateCcw className="h-3.5 w-3.5" /> Восстановить</button>
                  )}
                </CardContent>
              </Card>
            )}
          </div>
        </div>
      )}
    </div>
  );
}
