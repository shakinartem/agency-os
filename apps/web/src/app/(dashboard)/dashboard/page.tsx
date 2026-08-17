"use client";

import { useMemo, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { api } from "@/lib/api";
import { useProject } from "@/context/ProjectContext";
import { Bot, CheckCircle2, Clock3, Factory, Sparkles, TriangleAlert } from "lucide-react";

interface Run {
  id: string;
  task: string;
  content_type: string;
  platforms?: string[];
  status: string;
  current_stage?: string;
  quality_score?: number;
  error?: string;
  created_at?: string;
}

const platformOptions = ["telegram", "vk", "instagram", "dzen"];

export default function DashboardPage() {
  const { current } = useProject();
  const queryClient = useQueryClient();
  const [task, setTask] = useState("");
  const [contentType, setContentType] = useState("post");
  const [platforms, setPlatforms] = useState<string[]>(["telegram"]);
  const [generateMedia, setGenerateMedia] = useState(true);

  const { data: runs = [] } = useQuery({
    queryKey: ["factory-runs", current?.id],
    queryFn: () => api.get<Run[]>(`/factory/runs${current?.id ? `?project_id=${current.id}` : ""}`),
    refetchInterval: 3000,
  });

  const createRun = useMutation({
    mutationFn: () => api.post<Run>("/factory/runs", {
      project_id: current?.id,
      task,
      content_type: contentType,
      platforms,
      use_research: true,
      generate_media: generateMedia,
      auto_export: false,
    }),
    onSuccess: () => {
      setTask("");
      queryClient.invalidateQueries({ queryKey: ["factory-runs"] });
    },
  });

  const stats = useMemo(() => ({
    active: runs.filter((r) => ["queued", "running"].includes(r.status)).length,
    review: runs.filter((r) => r.status === "awaiting_review").length,
    ready: runs.filter((r) => r.status === "ready").length,
    failed: runs.filter((r) => r.status === "failed").length,
  }), [runs]);

  const togglePlatform = (platform: string) => {
    setPlatforms((prev) => prev.includes(platform) ? prev.filter((p) => p !== platform) : [...prev, platform]);
  };

  return (
    <div className="space-y-6">
      <div>
        <div className="flex items-center gap-2 text-sm font-medium text-primary"><Factory className="h-4 w-4" /> Content Factory</div>
        <h1 className="mt-1 text-3xl font-bold tracking-tight">Что производим?</h1>
        <p className="mt-2 max-w-2xl text-sm text-muted-foreground">Дайте задачу высокого уровня. Фабрика создаст канонический материал, проверит качество, очеловечит, адаптирует под площадки, подготовит визуал и пакет для автопостера.</p>
      </div>

      <Card className="overflow-hidden">
        <CardContent className="p-5">
          <textarea
            value={task}
            onChange={(e) => setTask(e.target.value)}
            placeholder="Например: подготовь экспертный Telegram-пост для Qualive о том, почему скорость реакции на намерение клиента важнее количества лидов..."
            className="min-h-36 w-full resize-y rounded-xl border bg-background p-4 text-sm outline-none transition focus:ring-2 focus:ring-primary/30"
          />
          <div className="mt-4 flex flex-wrap items-center gap-3">
            <select value={contentType} onChange={(e) => setContentType(e.target.value)} className="rounded-lg border bg-background px-3 py-2 text-sm">
              <option value="post">Пост</option>
              <option value="article">Статья</option>
              <option value="commercial_proposal">Коммерческое предложение</option>
              <option value="carousel">Карусель</option>
              <option value="video_script">Сценарий видео</option>
            </select>

            {platformOptions.map((platform) => (
              <button key={platform} onClick={() => togglePlatform(platform)} className={`rounded-lg border px-3 py-2 text-xs font-medium transition ${platforms.includes(platform) ? "bg-primary text-primary-foreground" : "bg-background"}`}>
                {platform}
              </button>
            ))}

            <label className="flex items-center gap-2 text-xs text-muted-foreground">
              <input type="checkbox" checked={generateMedia} onChange={(e) => setGenerateMedia(e.target.checked)} />
              генерировать визуал
            </label>

            <button
              onClick={() => createRun.mutate()}
              disabled={!current || !task.trim() || platforms.length === 0 || createRun.isPending}
              className="ml-auto inline-flex items-center gap-2 rounded-lg bg-primary px-4 py-2 text-sm font-semibold text-primary-foreground disabled:cursor-not-allowed disabled:opacity-50"
            >
              <Sparkles className="h-4 w-4" /> {createRun.isPending ? "Запускаю…" : "Запустить производство"}
            </button>
          </div>
          {!current && <p className="mt-3 text-xs text-amber-600">Сначала выберите проект в верхней панели.</p>}
          {createRun.isError && <p className="mt-3 text-xs text-red-600">Не удалось запустить задачу: {(createRun.error as Error).message}</p>}
        </CardContent>
      </Card>

      <div className="grid gap-4 md:grid-cols-4">
        {[
          ["В производстве", stats.active, Clock3],
          ["Нужен review", stats.review, TriangleAlert],
          ["Готово", stats.ready, CheckCircle2],
          ["Ошибки", stats.failed, Bot],
        ].map(([label, value, Icon]) => (
          <Card key={label as string}>
            <CardContent className="flex items-center justify-between p-4">
              <div><p className="text-xs text-muted-foreground">{label as string}</p><p className="mt-1 text-2xl font-bold">{value as number}</p></div>
              <Icon className="h-5 w-5 text-muted-foreground" />
            </CardContent>
          </Card>
        ))}
      </div>

      <Card>
        <CardHeader><CardTitle>Production pipeline</CardTitle></CardHeader>
        <CardContent className="space-y-2">
          {runs.slice(0, 20).map((run) => (
            <div key={run.id} className="grid gap-3 rounded-xl border p-3 md:grid-cols-[1fr_140px_160px_80px] md:items-center">
              <div className="min-w-0">
                <p className="truncate text-sm font-medium">{run.task}</p>
                <p className="mt-1 text-xs text-muted-foreground">{run.content_type} · {(run.platforms || []).join(", ")}</p>
              </div>
              <Badge variant="secondary" className="w-fit">{run.current_stage || "queued"}</Badge>
              <span className="text-xs text-muted-foreground">{run.status}</span>
              <span className="text-sm font-semibold">{run.quality_score != null ? `${Math.round(run.quality_score * 100)}` : "—"}</span>
              {run.error && <p className="md:col-span-4 text-xs text-red-600">{run.error}</p>}
            </div>
          ))}
          {runs.length === 0 && <div className="rounded-xl border border-dashed p-8 text-center text-sm text-muted-foreground">Пока нет production runs. Создайте первую задачу выше.</div>}
        </CardContent>
      </Card>
    </div>
  );
}
