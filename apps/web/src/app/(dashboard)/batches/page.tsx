"use client";

import { useMemo, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Boxes, CheckCircle2, Clock3, Layers3, Sparkles, TriangleAlert } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { useProject } from "@/context/ProjectContext";
import { api } from "@/lib/api";

interface Batch {
  id: string;
  project_id: string;
  objective: string;
  platforms?: string[];
  content_mix?: Record<string, number>;
  status: string;
  strategy_summary?: string;
  error?: string;
  created_at?: string;
}

interface BatchItem {
  id: string;
  position: number;
  content_type: string;
  topic: string;
  goal?: string;
  run_status?: string;
  content_item_id?: string;
  quality_score?: number;
}

interface BatchDetail {
  batch: Batch;
  counts: Record<string, number>;
  items: BatchItem[];
}

const platformOptions = ["telegram", "vk", "instagram", "dzen"];
const mixFields = [
  ["post", "Посты"],
  ["article", "Статьи"],
  ["commercial_proposal", "КП"],
  ["carousel", "Карусели"],
  ["video_script", "Видео"],
] as const;

export default function BatchesPage() {
  const { current } = useProject();
  const queryClient = useQueryClient();
  const [objective, setObjective] = useState("");
  const [platforms, setPlatforms] = useState<string[]>(["telegram"]);
  const [mix, setMix] = useState<Record<string, number>>({ post: 8, article: 2, commercial_proposal: 0, carousel: 0, video_script: 0 });
  const [useResearch, setUseResearch] = useState(true);
  const [useKnowledge, setUseKnowledge] = useState(true);
  const [generateMedia, setGenerateMedia] = useState(true);
  const [selectedId, setSelectedId] = useState<string | null>(null);

  const { data: batches = [] } = useQuery({
    queryKey: ["factory-batches", current?.id],
    queryFn: () => api.get<Batch[]>(`/factory/batches${current?.id ? `?project_id=${current.id}` : ""}`),
    refetchInterval: 4000,
  });

  const { data: detail } = useQuery({
    queryKey: ["factory-batch", selectedId],
    queryFn: () => api.get<BatchDetail>(`/factory/batches/${selectedId}`),
    enabled: Boolean(selectedId),
    refetchInterval: selectedId ? 3000 : false,
  });

  const createBatch = useMutation({
    mutationFn: () => api.post<Batch>("/factory/batches", {
      project_id: current?.id,
      objective,
      platforms,
      content_mix: Object.fromEntries(Object.entries(mix).filter(([, value]) => value > 0)),
      use_research: useResearch,
      use_knowledge: useKnowledge,
      generate_media: generateMedia,
      auto_export: false,
    }),
    onSuccess: (batch) => {
      setObjective("");
      setSelectedId(batch.id);
      queryClient.invalidateQueries({ queryKey: ["factory-batches"] });
    },
  });

  const totalRequested = useMemo(() => Object.values(mix).reduce((sum, value) => sum + Math.max(0, value || 0), 0), [mix]);
  const completed = detail?.items.filter((item) => item.run_status === "ready").length || 0;
  const needsReview = detail?.items.filter((item) => item.run_status === "awaiting_review").length || 0;
  const failed = detail?.items.filter((item) => item.run_status === "failed").length || 0;
  const progress = detail?.items.length ? Math.round((completed / detail.items.length) * 100) : 0;

  const togglePlatform = (platform: string) => {
    setPlatforms((prev) => prev.includes(platform) ? prev.filter((item) => item !== platform) : [...prev, platform]);
  };

  return (
    <div className="space-y-6">
      <div>
        <div className="flex items-center gap-2 text-sm font-medium text-primary"><Boxes className="h-4 w-4" /> Production Batches</div>
        <h1 className="mt-1 text-3xl font-bold tracking-tight">Серия контента из одной цели</h1>
        <p className="mt-2 max-w-3xl text-sm text-muted-foreground">Фабрика сначала строит и проверяет портфель тем с точным mix форматов, а затем запускает каждый материал отдельным production run. Один слабый материал не блокирует всю серию.</p>
      </div>

      <Card>
        <CardContent className="space-y-5 p-5">
          <textarea
            value={objective}
            onChange={(event) => setObjective(event.target.value)}
            placeholder="Например: подготовь контент на месяц для частных риэлторов Москвы — усиливаем понимание Intent Intelligence и ведём к диагностической встрече."
            className="min-h-28 w-full resize-y rounded-xl border bg-background p-4 text-sm outline-none focus:ring-2 focus:ring-primary/30"
          />

          <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-5">
            {mixFields.map(([key, label]) => (
              <label key={key} className="rounded-xl border p-3">
                <span className="text-xs text-muted-foreground">{label}</span>
                <input
                  type="number"
                  min={0}
                  max={100}
                  value={mix[key] || 0}
                  onChange={(event) => setMix((prev) => ({ ...prev, [key]: Math.max(0, Number(event.target.value) || 0) }))}
                  className="mt-2 w-full bg-transparent text-2xl font-semibold outline-none"
                />
              </label>
            ))}
          </div>

          <div className="flex flex-wrap items-center gap-2">
            {platformOptions.map((platform) => (
              <button key={platform} onClick={() => togglePlatform(platform)} className={`rounded-lg border px-3 py-2 text-xs font-medium ${platforms.includes(platform) ? "bg-primary text-primary-foreground" : "bg-background"}`}>
                {platform}
              </button>
            ))}
            <label className="ml-2 flex items-center gap-2 text-xs text-muted-foreground"><input type="checkbox" checked={useKnowledge} onChange={(event) => setUseKnowledge(event.target.checked)} /> Knowledge</label>
            <label className="flex items-center gap-2 text-xs text-muted-foreground"><input type="checkbox" checked={useResearch} onChange={(event) => setUseResearch(event.target.checked)} /> Research</label>
            <label className="flex items-center gap-2 text-xs text-muted-foreground"><input type="checkbox" checked={generateMedia} onChange={(event) => setGenerateMedia(event.target.checked)} /> Visuals</label>
            <span className="ml-auto text-xs text-muted-foreground">Всего: <strong className="text-foreground">{totalRequested}</strong> / 100</span>
            <button
              onClick={() => createBatch.mutate()}
              disabled={!current || !objective.trim() || !platforms.length || totalRequested < 1 || totalRequested > 100 || createBatch.isPending}
              className="inline-flex items-center gap-2 rounded-lg bg-primary px-4 py-2 text-sm font-semibold text-primary-foreground disabled:opacity-50"
            >
              <Sparkles className="h-4 w-4" /> {createBatch.isPending ? "Планирую…" : "Запустить серию"}
            </button>
          </div>
          {createBatch.isError && <p className="text-xs text-red-600">{(createBatch.error as Error).message}</p>}
        </CardContent>
      </Card>

      <div className="grid gap-5 xl:grid-cols-[0.8fr_1.2fr]">
        <Card>
          <CardHeader><CardTitle>Серии</CardTitle></CardHeader>
          <CardContent className="space-y-2">
            {batches.map((batch) => (
              <button key={batch.id} onClick={() => setSelectedId(batch.id)} className={`w-full rounded-xl border p-3 text-left transition ${selectedId === batch.id ? "ring-2 ring-primary/30" : "hover:border-primary/40"}`}>
                <div className="flex items-start justify-between gap-3">
                  <div className="min-w-0"><p className="line-clamp-2 text-sm font-medium">{batch.objective}</p><p className="mt-1 text-xs text-muted-foreground">{Object.entries(batch.content_mix || {}).map(([key, value]) => `${key}:${value}`).join(" · ")}</p></div>
                  <Badge variant="secondary">{batch.status}</Badge>
                </div>
                {batch.error && <p className="mt-2 line-clamp-2 text-xs text-red-600">{batch.error}</p>}
              </button>
            ))}
            {!batches.length && <div className="rounded-xl border border-dashed p-8 text-center text-sm text-muted-foreground">Серий пока нет.</div>}
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <div className="flex items-center justify-between gap-3"><CardTitle>Прогресс серии</CardTitle>{detail && <Badge variant="secondary">{detail.batch.status}</Badge>}</div>
          </CardHeader>
          <CardContent>
            {!detail && <div className="rounded-xl border border-dashed p-8 text-center text-sm text-muted-foreground">Выберите серию слева.</div>}
            {detail && (
              <div className="space-y-4">
                <div className="grid gap-3 sm:grid-cols-4">
                  {[
                    ["Готово", completed, CheckCircle2],
                    ["Review", needsReview, TriangleAlert],
                    ["Ошибки", failed, TriangleAlert],
                    ["Прогресс", `${progress}%`, Clock3],
                  ].map(([label, value, Icon]) => (
                    <div key={String(label)} className="rounded-xl border p-3"><div className="flex items-center justify-between"><span className="text-xs text-muted-foreground">{String(label)}</span><Icon className="h-4 w-4 text-muted-foreground" /></div><p className="mt-2 text-2xl font-bold">{String(value)}</p></div>
                  ))}
                </div>
                {detail.batch.strategy_summary && <div className="rounded-xl bg-muted/40 p-4 text-sm leading-6"><p className="mb-1 text-xs font-semibold uppercase tracking-wide text-muted-foreground">Strategy</p>{detail.batch.strategy_summary}</div>}
                <div className="space-y-2">
                  {detail.items.map((item) => (
                    <div key={item.id} className="grid gap-2 rounded-xl border p-3 md:grid-cols-[48px_110px_1fr_130px_70px] md:items-center">
                      <span className="text-xs text-muted-foreground">#{item.position}</span>
                      <Badge variant="secondary" className="w-fit">{item.content_type}</Badge>
                      <div className="min-w-0"><p className="truncate text-sm font-medium">{item.topic}</p>{item.goal && <p className="mt-1 truncate text-xs text-muted-foreground">{item.goal}</p>}</div>
                      <span className="text-xs text-muted-foreground">{item.run_status || "planned"}</span>
                      <span className="text-sm font-semibold">{item.quality_score != null ? Math.round(item.quality_score * 100) : "—"}</span>
                    </div>
                  ))}
                  {!detail.items.length && <div className="rounded-xl border border-dashed p-6 text-center text-sm text-muted-foreground"><Layers3 className="mx-auto mb-2 h-5 w-5" /> Planner ещё не создал child-runs.</div>}
                </div>
              </div>
            )}
          </CardContent>
        </Card>
      </div>
    </div>
  );
}
