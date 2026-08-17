"use client";

import { useQuery } from "@tanstack/react-query";
import { Activity, BarChart3, Eye, MousePointerClick, Target, TrendingUp } from "lucide-react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { useProject } from "@/context/ProjectContext";
import { api } from "@/lib/api";

interface Summary {
  project_id: string;
  publications: number;
  totals: Record<string, number>;
  by_content_type: Record<string, Record<string, number>>;
  by_rubric: Record<string, Record<string, number>>;
}

const preferredMetrics = ["views", "impressions", "clicks", "leads", "conversions", "revenue"];

function Metric({ label, value, icon: Icon }: { label: string; value: number | undefined; icon: typeof Eye }) {
  return (
    <Card>
      <CardContent className="flex items-center justify-between p-4">
        <div><p className="text-xs text-muted-foreground">{label}</p><p className="mt-1 text-2xl font-bold">{value ?? 0}</p></div>
        <Icon className="h-5 w-5 text-muted-foreground" />
      </CardContent>
    </Card>
  );
}

function Breakdown({ title, rows }: { title: string; rows: Record<string, Record<string, number>> }) {
  const entries = Object.entries(rows);
  const metrics = preferredMetrics.filter((metric) => entries.some(([, values]) => values[metric] != null));
  return (
    <Card>
      <CardHeader><CardTitle>{title}</CardTitle></CardHeader>
      <CardContent>
        {!entries.length && <div className="rounded-xl border border-dashed p-8 text-center text-sm text-muted-foreground">Данных пока нет.</div>}
        {!!entries.length && (
          <div className="overflow-x-auto">
            <table className="w-full min-w-[620px] text-sm">
              <thead><tr className="border-b text-left text-xs text-muted-foreground"><th className="pb-2 font-medium">Сегмент</th>{metrics.map((metric) => <th key={metric} className="pb-2 text-right font-medium">{metric}</th>)}</tr></thead>
              <tbody>
                {entries.map(([name, values]) => (
                  <tr key={name} className="border-b last:border-0">
                    <td className="py-3 font-medium">{name}</td>
                    {metrics.map((metric) => <td key={metric} className="py-3 text-right tabular-nums">{values[metric] ?? 0}</td>)}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </CardContent>
    </Card>
  );
}

export default function PerformancePage() {
  const { current } = useProject();
  const { data, isLoading, isError, error } = useQuery({
    queryKey: ["content-performance", current?.id],
    queryFn: () => api.get<Summary>(`/performance/summary?project_id=${current?.id}`),
    enabled: Boolean(current?.id),
    refetchInterval: 15000,
  });

  const totals = data?.totals || {};
  const views = totals.views ?? totals.impressions ?? 0;
  const clicks = totals.clicks ?? 0;
  const leads = totals.leads ?? 0;
  const conversions = totals.conversions ?? 0;
  const ctr = views > 0 ? ((clicks / views) * 100).toFixed(2) : "0.00";
  const leadRate = clicks > 0 ? ((leads / clicks) * 100).toFixed(2) : "0.00";

  return (
    <div className="space-y-6">
      <div>
        <div className="flex items-center gap-2 text-sm font-medium text-primary"><BarChart3 className="h-4 w-4" /> Performance learning loop</div>
        <h1 className="mt-1 text-3xl font-bold tracking-tight">Что реально работает после публикации</h1>
        <p className="mt-2 max-w-3xl text-sm text-muted-foreground">Autoposter возвращает snapshots публикаций. Factory берёт только последний snapshot каждой публикации, поэтому повторные обновления метрик не раздувают totals. Эти данные связываются с форматом и рубрикой.</p>
      </div>

      {!current && <div className="rounded-xl border border-dashed p-8 text-center text-sm text-muted-foreground">Выберите проект.</div>}
      {isLoading && current && <p className="text-sm text-muted-foreground">Загружаю performance…</p>}
      {isError && <p className="text-sm text-red-600">Не удалось загрузить performance: {(error as Error).message}</p>}

      {current && data && (
        <>
          <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-5">
            <Metric label="Публикаций" value={data.publications} icon={Activity} />
            <Metric label="Просмотры" value={views} icon={Eye} />
            <Metric label="Клики" value={clicks} icon={MousePointerClick} />
            <Metric label="Лиды" value={leads} icon={Target} />
            <Metric label="Конверсии" value={conversions} icon={TrendingUp} />
          </div>

          <div className="grid gap-4 md:grid-cols-2">
            <Card><CardContent className="p-5"><p className="text-xs text-muted-foreground">CTR</p><p className="mt-2 text-3xl font-bold">{ctr}%</p><p className="mt-2 text-xs text-muted-foreground">clicks / views</p></CardContent></Card>
            <Card><CardContent className="p-5"><p className="text-xs text-muted-foreground">Click → lead</p><p className="mt-2 text-3xl font-bold">{leadRate}%</p><p className="mt-2 text-xs text-muted-foreground">leads / clicks</p></CardContent></Card>
          </div>

          <Breakdown title="По формату" rows={data.by_content_type || {}} />
          <Breakdown title="По рубрике" rows={data.by_rubric || {}} />

          <Card>
            <CardHeader><CardTitle>Все метрики</CardTitle></CardHeader>
            <CardContent className="flex flex-wrap gap-2">
              {Object.entries(totals).map(([key, value]) => <div key={key} className="rounded-full border bg-card px-3 py-1.5 text-xs"><span className="text-muted-foreground">{key}</span> <strong className="ml-1">{value}</strong></div>)}
              {!Object.keys(totals).length && <span className="text-sm text-muted-foreground">Autoposter ещё не прислал ни одного performance snapshot.</span>}
            </CardContent>
          </Card>
        </>
      )}
    </div>
  );
}
