"use client";

import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { api } from "@/lib/api";
import { useProject } from "@/context/ProjectContext";
import { BookOpen, Check, ExternalLink, FileText, Gauge, Image as ImageIcon, Layers3, RefreshCcw, Search } from "lucide-react";

interface ContentItem {
  id: string;
  project_id: string;
  type: string;
  status: string;
  title: string;
  body?: string;
  task?: string;
  topic?: string;
  platforms?: string[];
  research_sources?: Array<{ id?: string; title?: string; url?: string; score?: number }>;
  knowledge_refs?: Array<{ chunk_id?: string; document_id?: string; document_name?: string; position?: number; rank?: number; excerpt?: string }>;
  quality_score?: number;
  current_version?: number;
  created_at?: string;
}

interface ContentDetail {
  content: ContentItem;
  versions: Array<{ id: string; version: number; stage: string; title?: string; body?: string; created_by?: string; created_at?: string }>;
  evaluations: Array<Record<string, unknown>>;
  variants: Array<{ id: string; platform: string; title?: string; body?: string; cta?: string; hashtags?: string[] }>;
  media: Array<{ id: string; status: string; url?: string; prompt?: string; quality_score?: number; mime_type?: string }>;
  runs: Array<Record<string, unknown>>;
}

const score = (value: unknown) => typeof value === "number" ? Math.round(value * 100) : "—";

export default function ContentPage() {
  const { current } = useProject();
  const queryClient = useQueryClient();
  const [selectedId, setSelectedId] = useState<string | null>(null);

  const { data: items = [], isLoading } = useQuery({
    queryKey: ["content", current?.id],
    queryFn: () => api.get<ContentItem[]>(`/content${current?.id ? `?project_id=${current.id}` : ""}`),
    refetchInterval: 5000,
  });

  const { data: detail, isLoading: detailLoading } = useQuery({
    queryKey: ["content-detail", selectedId],
    queryFn: () => api.get<ContentDetail>(`/factory/content/${selectedId}/detail`),
    enabled: Boolean(selectedId),
    refetchInterval: selectedId ? 5000 : false,
  });

  const approve = useMutation({
    mutationFn: (id: string) => api.post(`/factory/content/${id}/approve`),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["content"] });
      queryClient.invalidateQueries({ queryKey: ["content-detail"] });
      queryClient.invalidateQueries({ queryKey: ["factory-runs"] });
      queryClient.invalidateQueries({ queryKey: ["factory-outbox"] });
    },
  });

  const regenerate = useMutation({
    mutationFn: (id: string) => api.post(`/factory/content/${id}/regenerate`),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["factory-runs"] }),
  });

  const latestEvaluation = detail?.evaluations?.[0];
  const selected = detail?.content;
  const actionable = selected && ["review", "final_review"].includes(selected.status);

  return (
    <div className="space-y-6">
      <div>
        <div className="flex items-center gap-2 text-sm font-medium text-primary"><FileText className="h-4 w-4" /> Review workspace</div>
        <h1 className="mt-1 text-3xl font-bold tracking-tight">Content</h1>
        <p className="mt-2 text-sm text-muted-foreground">Канонический материал, версии, first-party knowledge, внешние источники, QA, платформенные варианты и visual assets в одном месте. Ручные правки сохраняются как новая версия, а не стирают AI trace.</p>
      </div>

      <div className="grid gap-5 xl:grid-cols-[minmax(0,1fr)_minmax(420px,0.85fr)]">
        <div className="space-y-3">
          {isLoading && <p className="text-sm text-muted-foreground">Loading…</p>}
          {items.map((item) => (
            <Card key={item.id} className={`cursor-pointer overflow-hidden transition ${selectedId === item.id ? "ring-2 ring-primary/30" : "hover:border-primary/40"}`}>
              <button className="w-full text-left" onClick={() => setSelectedId(item.id)}>
                <CardHeader className="pb-3">
                  <div className="flex items-start justify-between gap-3">
                    <div className="min-w-0">
                      <CardTitle className="truncate text-base">{item.title}</CardTitle>
                      <p className="mt-1 text-xs text-muted-foreground">{item.type} · {(item.platforms || []).join(", ") || "canonical"}</p>
                    </div>
                    <Badge variant="secondary">{item.status}</Badge>
                  </div>
                </CardHeader>
                <CardContent>
                  <p className="line-clamp-5 whitespace-pre-wrap text-sm leading-6 text-foreground/85">{item.body || "Текст ещё не сформирован."}</p>
                  <div className="mt-4 flex flex-wrap gap-4 border-t pt-3 text-xs text-muted-foreground">
                    <span className="flex items-center gap-1"><Gauge className="h-3.5 w-3.5" /> score {item.quality_score != null ? Math.round(item.quality_score * 100) : "—"}</span>
                    <span className="flex items-center gap-1"><Layers3 className="h-3.5 w-3.5" /> v{item.current_version || 0}</span>
                    <span className="flex items-center gap-1"><BookOpen className="h-3.5 w-3.5" /> {item.knowledge_refs?.length || 0} knowledge</span>
                    <span className="flex items-center gap-1"><Search className="h-3.5 w-3.5" /> {item.research_sources?.length || 0} web sources</span>
                    {item.topic && <span className="truncate">{item.topic}</span>}
                  </div>
                </CardContent>
              </button>
            </Card>
          ))}
          {!isLoading && items.length === 0 && <div className="rounded-xl border border-dashed p-10 text-center text-sm text-muted-foreground">Контента пока нет. Запустите production run на экране Factory.</div>}
        </div>

        <div>
          {!selectedId && <div className="rounded-xl border border-dashed p-10 text-center text-sm text-muted-foreground">Выберите материал слева, чтобы открыть QA trace и review actions.</div>}
          {selectedId && detailLoading && <div className="rounded-xl border p-6 text-sm text-muted-foreground">Loading review data…</div>}
          {selected && (
            <div className="space-y-4 xl:sticky xl:top-20">
              <Card>
                <CardHeader>
                  <div className="flex items-start justify-between gap-3">
                    <div>
                      <CardTitle className="text-lg">{selected.title}</CardTitle>
                      <p className="mt-1 text-xs text-muted-foreground">v{selected.current_version} · {selected.type}</p>
                    </div>
                    <Badge variant="secondary">{selected.status}</Badge>
                  </div>
                </CardHeader>
                <CardContent className="space-y-4">
                  <div className="max-h-80 overflow-y-auto whitespace-pre-wrap rounded-lg bg-muted/40 p-4 text-sm leading-6">{selected.body || "—"}</div>
                  <div className="flex flex-wrap gap-2">
                    {actionable && (
                      <button
                        onClick={() => approve.mutate(selected.id)}
                        disabled={approve.isPending}
                        className="inline-flex items-center gap-2 rounded-lg bg-primary px-3 py-2 text-xs font-semibold text-primary-foreground disabled:opacity-50"
                      >
                        <Check className="h-4 w-4" /> Approve canonical
                      </button>
                    )}
                    <button
                      onClick={() => regenerate.mutate(selected.id)}
                      disabled={regenerate.isPending}
                      className="inline-flex items-center gap-2 rounded-lg border px-3 py-2 text-xs font-semibold hover:bg-muted disabled:opacity-50"
                    >
                      <RefreshCcw className="h-4 w-4" /> Regenerate as new run
                    </button>
                  </div>
                  {approve.isError && <p className="text-xs text-red-600">Approve failed: {(approve.error as Error).message}</p>}
                  {regenerate.isError && <p className="text-xs text-red-600">Regenerate failed: {(regenerate.error as Error).message}</p>}
                </CardContent>
              </Card>

              <Card>
                <CardHeader><CardTitle className="text-base">Quality</CardTitle></CardHeader>
                <CardContent>
                  {latestEvaluation ? (
                    <div className="grid grid-cols-2 gap-2 text-xs md:grid-cols-4">
                      {["overall", "factuality", "brand_voice", "clarity", "hook", "usefulness", "originality"].map((key) => (
                        <div key={key} className="rounded-lg border p-2"><p className="text-muted-foreground">{key}</p><p className="mt-1 text-lg font-semibold">{score(latestEvaluation[key])}</p></div>
                      ))}
                    </div>
                  ) : <p className="text-sm text-muted-foreground">No evaluation yet.</p>}
                </CardContent>
              </Card>

              <Card>
                <CardHeader><CardTitle className="flex items-center gap-2 text-base"><BookOpen className="h-4 w-4" /> Internal Knowledge</CardTitle></CardHeader>
                <CardContent className="space-y-2">
                  {(selected.knowledge_refs || []).map((ref, index) => (
                    <div key={`${ref.chunk_id}-${index}`} className="rounded-lg border p-3 text-xs">
                      <div className="flex items-center justify-between gap-3">
                        <p className="truncate font-medium">{ref.document_name || "Knowledge document"}</p>
                        <span className="shrink-0 text-muted-foreground">rank {ref.rank != null ? ref.rank.toFixed(3) : "—"}</span>
                      </div>
                      {ref.excerpt && <p className="mt-2 line-clamp-4 whitespace-pre-wrap leading-5 text-muted-foreground">{ref.excerpt}</p>}
                    </div>
                  ))}
                  {(selected.knowledge_refs || []).length === 0 && <p className="text-sm text-muted-foreground">No project knowledge chunks were retrieved for this run.</p>}
                  <p className="pt-1 text-[11px] text-muted-foreground">Private knowledge lineage is visible here for audit, but is intentionally excluded from the Autoposter package.</p>
                </CardContent>
              </Card>

              <Card>
                <CardHeader><CardTitle className="text-base">External Sources</CardTitle></CardHeader>
                <CardContent className="space-y-2">
                  {(selected.research_sources || []).map((source, index) => (
                    <a key={`${source.url}-${index}`} href={source.url} target="_blank" rel="noreferrer" className="flex items-start justify-between gap-3 rounded-lg border p-3 text-xs hover:bg-muted/50">
                      <div className="min-w-0"><p className="truncate font-medium">{source.title || source.url}</p><p className="mt-1 truncate text-muted-foreground">{source.url}</p></div>
                      <div className="flex shrink-0 items-center gap-2"><span>{source.score != null ? Math.round(source.score * 100) : "—"}</span><ExternalLink className="h-3.5 w-3.5" /></div>
                    </a>
                  ))}
                  {(selected.research_sources || []).length === 0 && <p className="text-sm text-muted-foreground">No live sources attached.</p>}
                </CardContent>
              </Card>

              <Card>
                <CardHeader><CardTitle className="text-base">Platform variants</CardTitle></CardHeader>
                <CardContent className="space-y-2">
                  {detail?.variants.map((variant) => (
                    <div key={variant.id} className="rounded-lg border p-3">
                      <div className="flex items-center justify-between"><Badge variant="secondary">{variant.platform}</Badge><span className="text-xs text-muted-foreground">{variant.hashtags?.length || 0} hashtags</span></div>
                      <p className="mt-3 line-clamp-5 whitespace-pre-wrap text-xs leading-5">{variant.body}</p>
                    </div>
                  ))}
                  {detail?.variants.length === 0 && <p className="text-sm text-muted-foreground">Variants have not been generated yet.</p>}
                </CardContent>
              </Card>

              <Card>
                <CardHeader><CardTitle className="flex items-center gap-2 text-base"><ImageIcon className="h-4 w-4" /> Media</CardTitle></CardHeader>
                <CardContent className="space-y-3">
                  {detail?.media.map((asset) => (
                    <div key={asset.id} className="rounded-lg border p-3">
                      <div className="flex items-center justify-between gap-2"><Badge variant="secondary">{asset.status}</Badge><span className="text-xs text-muted-foreground">score {asset.quality_score != null ? Math.round(asset.quality_score * 100) : "—"}</span></div>
                      {asset.url && <img src={asset.url} alt="Generated content asset" className="mt-3 max-h-64 w-full rounded-lg object-cover" />}
                      {asset.prompt && <p className="mt-2 line-clamp-3 text-xs text-muted-foreground">{asset.prompt}</p>}
                    </div>
                  ))}
                  {detail?.media.length === 0 && <p className="text-sm text-muted-foreground">No media generated yet.</p>}
                </CardContent>
              </Card>

              <Card>
                <CardHeader><CardTitle className="text-base">Version trace</CardTitle></CardHeader>
                <CardContent className="space-y-2">
                  {detail?.versions.slice(0, 12).map((version) => (
                    <div key={version.id} className="flex items-center justify-between rounded-lg border p-2 text-xs">
                      <span>v{version.version} · {version.stage}</span>
                      <span className="text-muted-foreground">{version.created_by || "AI"}</span>
                    </div>
                  ))}
                </CardContent>
              </Card>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
