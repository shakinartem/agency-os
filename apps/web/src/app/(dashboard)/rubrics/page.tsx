"use client";

import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { api } from "@/lib/api";
import { useProject } from "@/context/ProjectContext";
import { Archive, Layers3, RefreshCcw, Sparkles, Target } from "lucide-react";

interface Rubric {
  id: string;
  project_id: string;
  generation_run_id?: string;
  name: string;
  description?: string;
  goal?: string;
  content_types?: string[];
  platforms?: string[];
  origin: string;
  metadata_json?: {
    audience_stage?: string;
    rationale?: string;
    topic_examples?: string[];
    success_metric?: string;
    critic?: Record<string, unknown>;
  };
  active: boolean;
}

interface GenerationRun {
  id: string;
  status: string;
  current_stage?: string;
}

const availablePlatforms = ["telegram", "vk", "instagram", "dzen"];

export default function RubricsPage() {
  const { current } = useProject();
  const queryClient = useQueryClient();
  const [goal, setGoal] = useState("Построить систему контента, которая усиливает экспертность, формирует спрос и приводит к целевому действию");
  const [count, setCount] = useState(8);
  const [platforms, setPlatforms] = useState<string[]>(["telegram"]);
  const [useResearch, setUseResearch] = useState(true);
  const [lastRun, setLastRun] = useState<string | null>(null);

  const { data: rubrics = [], isLoading } = useQuery({
    queryKey: ["strategy-rubrics", current?.id],
    queryFn: () => api.get<Rubric[]>(`/strategy/rubrics?project_id=${current?.id}`),
    enabled: Boolean(current?.id),
    refetchInterval: 5000,
  });

  const { data: runs = [] } = useQuery({
    queryKey: ["factory-runs", current?.id],
    queryFn: () => api.get<GenerationRun[]>(`/factory/runs?project_id=${current?.id}`),
    enabled: Boolean(current?.id),
    refetchInterval: 3000,
  });

  const generate = useMutation({
    mutationFn: () => api.post<GenerationRun>("/strategy/rubrics/generate", {
      project_id: current?.id,
      goal,
      platforms,
      count,
      use_research: useResearch,
    }),
    onSuccess: (run) => {
      setLastRun(run.id);
      queryClient.invalidateQueries({ queryKey: ["factory-runs"] });
    },
  });

  const archive = useMutation({
    mutationFn: (id: string) => api.post(`/strategy/rubrics/${id}/archive`),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["strategy-rubrics"] }),
  });

  const lastRunState = runs.find((run) => run.id === lastRun);
  const togglePlatform = (platform: string) => setPlatforms((prev) => prev.includes(platform) ? prev.filter((p) => p !== platform) : [...prev, platform]);

  return (
    <div className="space-y-6">
      <div>
        <div className="flex items-center gap-2 text-sm font-medium text-primary"><Layers3 className="h-4 w-4" /> Strategy engine</div>
        <h1 className="mt-1 text-3xl font-bold tracking-tight">Рубрикатор</h1>
        <p className="mt-2 max-w-3xl text-sm text-muted-foreground">Не список случайных тем, а переиспользуемая система контент-направлений. AI строит её вокруг задач аудитории, проверяет overlap и сохраняет lineage, чтобы потом связать рубрики с реальной эффективностью контента.</p>
      </div>

      <Card>
        <CardHeader><CardTitle className="flex items-center gap-2"><Target className="h-4 w-4" /> Цель стратегии</CardTitle></CardHeader>
        <CardContent className="space-y-4">
          <textarea value={goal} onChange={(e) => setGoal(e.target.value)} className="min-h-28 w-full resize-y rounded-xl border bg-background p-4 text-sm outline-none focus:ring-2 focus:ring-primary/30" />
          <div className="flex flex-wrap items-center gap-2">
            {availablePlatforms.map((platform) => (
              <button key={platform} onClick={() => togglePlatform(platform)} className={`rounded-lg border px-3 py-2 text-xs font-medium ${platforms.includes(platform) ? "bg-primary text-primary-foreground" : "bg-background"}`}>{platform}</button>
            ))}
            <label className="ml-2 flex items-center gap-2 text-xs text-muted-foreground"><input type="checkbox" checked={useResearch} onChange={(e) => setUseResearch(e.target.checked)} /> live research</label>
            <label className="flex items-center gap-2 text-xs text-muted-foreground">рубрик <input type="number" min={3} max={20} value={count} onChange={(e) => setCount(Number(e.target.value))} className="w-16 rounded-md border bg-background px-2 py-1" /></label>
            <button
              onClick={() => generate.mutate()}
              disabled={!current || !goal.trim() || platforms.length === 0 || generate.isPending}
              className="ml-auto inline-flex items-center gap-2 rounded-lg bg-primary px-4 py-2 text-sm font-semibold text-primary-foreground disabled:opacity-50"
            >
              <Sparkles className="h-4 w-4" /> {generate.isPending ? "Запускаю…" : rubrics.length ? "Пересобрать стратегию" : "Сгенерировать рубрикатор"}
            </button>
          </div>
          {!current && <p className="text-xs text-amber-600">Сначала выберите проект.</p>}
          {lastRunState && <div className="flex items-center gap-2 text-xs text-muted-foreground"><RefreshCcw className={`h-3.5 w-3.5 ${["queued", "running"].includes(lastRunState.status) ? "animate-spin" : ""}`} /> {lastRunState.current_stage || lastRunState.status} · {lastRunState.status}</div>}
          {generate.isError && <p className="text-xs text-red-600">Generation failed: {(generate.error as Error).message}</p>}
        </CardContent>
      </Card>

      <div className="grid gap-4 lg:grid-cols-2 2xl:grid-cols-3">
        {rubrics.map((rubric) => (
          <Card key={rubric.id} className="overflow-hidden">
            <CardHeader className="pb-3">
              <div className="flex items-start justify-between gap-3">
                <div>
                  <CardTitle className="text-base">{rubric.name}</CardTitle>
                  <p className="mt-1 text-xs text-muted-foreground">{rubric.goal || "Без отдельной цели"}</p>
                </div>
                <Badge variant="secondary">{rubric.metadata_json?.audience_stage || rubric.origin}</Badge>
              </div>
            </CardHeader>
            <CardContent className="space-y-4">
              <p className="text-sm leading-6 text-foreground/85">{rubric.description || "—"}</p>
              {rubric.metadata_json?.rationale && <div className="rounded-lg bg-muted/40 p-3 text-xs"><span className="font-semibold">Почему существует: </span>{rubric.metadata_json.rationale}</div>}
              <div>
                <p className="mb-2 text-xs font-semibold">Примеры тем</p>
                <div className="space-y-1.5">
                  {(rubric.metadata_json?.topic_examples || []).slice(0, 4).map((topic, index) => <p key={index} className="rounded-md border px-2 py-1.5 text-xs">{topic}</p>)}
                </div>
              </div>
              <div className="flex flex-wrap gap-1.5">{(rubric.content_types || []).map((type) => <Badge key={type} variant="secondary">{type}</Badge>)}</div>
              <div className="flex items-end justify-between gap-3 border-t pt-3 text-xs text-muted-foreground">
                <div>
                  <p>{(rubric.platforms || []).join(", ")}</p>
                  {rubric.metadata_json?.success_metric && <p className="mt-1">metric: {rubric.metadata_json.success_metric}</p>}
                </div>
                <button onClick={() => archive.mutate(rubric.id)} disabled={archive.isPending} className="inline-flex items-center gap-1 rounded-md border px-2 py-1.5 hover:bg-muted"><Archive className="h-3.5 w-3.5" /> archive</button>
              </div>
            </CardContent>
          </Card>
        ))}
        {!isLoading && rubrics.length === 0 && <div className="lg:col-span-2 2xl:col-span-3 rounded-xl border border-dashed p-10 text-center text-sm text-muted-foreground">Активных рубрик пока нет. Сформулируйте цель стратегии и запустите AI-рубрикатор.</div>}
      </div>
    </div>
  );
}
