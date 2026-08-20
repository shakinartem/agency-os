"use client";

import { useQuery } from "@tanstack/react-query";
import { Activity, AlertTriangle, BarChart3, BrainCircuit, CircleDollarSign, Clock3, Eye, FlaskConical, Gauge, MousePointerClick, Target, TrendingUp } from "lucide-react";
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

interface LearningRow {
  dimension: string;
  name: string;
  publications: number;
  metric_value: number;
  lift_vs_baseline: number | null;
  confidence: "low" | "medium" | "high";
  action: "explore" | "scale_cautiously" | "reduce_and_retest" | "keep_testing";
}

interface Learning {
  status: "learning" | "insufficient_data" | "disabled";
  publications: number;
  primary_metric: string;
  primary_metric_label: string;
  baseline: number;
  exploration_share: number;
  by_content_type: LearningRow[];
  by_rubric: LearningRow[];
  by_platform: LearningRow[];
  recommendations: {
    winners: LearningRow[];
    watch: LearningRow[];
    guidance: string[];
  };
}

interface EconomicsBucket {
  requests: number;
  input_tokens: number;
  output_tokens: number;
  total_tokens: number;
  average_latency_ms: number | null;
  known_cost_usd: number;
  priced_requests: number;
  unpriced_requests: number;
}

interface Economics extends EconomicsBucket {
  project_id: string;
  traced_steps: number;
  pricing_complete: boolean;
  pricing_configured_for_any: boolean;
  by_stage: Record<string, EconomicsBucket>;
  by_model: Record<string, EconomicsBucket>;
  by_provider: Record<string, EconomicsBucket>;
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

function formatLearningMetric(value: number, metric: string) {
  if (metric === "ctr") return `${(value * 100).toFixed(2)}%`;
  if (metric.includes("per_1000")) return value.toFixed(2);
  return value.toFixed(1);
}

function LearningCard({ row, metric }: { row: LearningRow; metric: string }) {
  const lift = row.lift_vs_baseline == null ? "—" : `${row.lift_vs_baseline >= 0 ? "+" : ""}${(row.lift_vs_baseline * 100).toFixed(0)}%`;
  const actionLabel = {
    explore: "Нужна выборка",
    scale_cautiously: "Аккуратно масштабировать",
    reduce_and_retest: "Снизить долю и перетестировать",
    keep_testing: "Продолжать тест",
  }[row.action];
  return (
    <div className="rounded-xl border bg-card p-4">
      <div className="flex items-start justify-between gap-3">
        <div>
          <p className="text-xs text-muted-foreground">{row.dimension}</p>
          <p className="mt-1 font-semibold">{row.name}</p>
        </div>
        <span className="rounded-full border px-2 py-1 text-[11px] text-muted-foreground">{row.confidence}</span>
      </div>
      <div className="mt-4 grid grid-cols-3 gap-3 text-xs">
        <div><p className="text-muted-foreground">Публикации</p><p className="mt-1 font-semibold tabular-nums">{row.publications}</p></div>
        <div><p className="text-muted-foreground">Метрика</p><p className="mt-1 font-semibold tabular-nums">{formatLearningMetric(row.metric_value, metric)}</p></div>
        <div><p className="text-muted-foreground">vs baseline</p><p className="mt-1 font-semibold tabular-nums">{lift}</p></div>
      </div>
      <p className="mt-4 text-xs font-medium">{actionLabel}</p>
    </div>
  );
}

function EconomicsTable({ title, rows }: { title: string; rows: Record<string, EconomicsBucket> }) {
  const entries = Object.entries(rows).sort((a, b) => b[1].known_cost_usd - a[1].known_cost_usd || b[1].requests - a[1].requests);
  return (
    <div>
      <p className="mb-2 text-sm font-semibold">{title}</p>
      {!entries.length && <p className="text-sm text-muted-foreground">Provider traces ещё не накоплены.</p>}
      {!!entries.length && (
        <div className="overflow-x-auto rounded-xl border">
          <table className="w-full min-w-[680px] text-sm">
            <thead><tr className="border-b bg-muted/30 text-left text-xs text-muted-foreground"><th className="p-3 font-medium">Сегмент</th><th className="p-3 text-right font-medium">Requests</th><th className="p-3 text-right font-medium">Tokens</th><th className="p-3 text-right font-medium">Avg latency</th><th className="p-3 text-right font-medium">Known cost</th><th className="p-3 text-right font-medium">Unpriced</th></tr></thead>
            <tbody>
              {entries.map(([name, row]) => (
                <tr key={name} className="border-b last:border-0">
                  <td className="p-3 font-medium">{name}</td>
                  <td className="p-3 text-right tabular-nums">{row.requests}</td>
                  <td className="p-3 text-right tabular-nums">{row.total_tokens.toLocaleString()}</td>
                  <td className="p-3 text-right tabular-nums">{row.average_latency_ms == null ? "—" : `${row.average_latency_ms} ms`}</td>
                  <td className="p-3 text-right tabular-nums">${row.known_cost_usd.toFixed(4)}</td>
                  <td className="p-3 text-right tabular-nums">{row.unpriced_requests}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}

export default function PerformancePage() {
  const { current } = useProject();
  const summaryQuery = useQuery({
    queryKey: ["content-performance", current?.id],
    queryFn: () => api.get<Summary>(`/performance/summary?project_id=${current?.id}`),
    enabled: Boolean(current?.id),
    refetchInterval: 15000,
  });
  const learningQuery = useQuery({
    queryKey: ["content-performance-learning", current?.id],
    queryFn: () => api.get<Learning>(`/performance/learning?project_id=${current?.id}`),
    enabled: Boolean(current?.id),
    refetchInterval: 15000,
  });
  const economicsQuery = useQuery({
    queryKey: ["generation-economics", current?.id],
    queryFn: () => api.get<Economics>(`/performance/economics?project_id=${current?.id}`),
    enabled: Boolean(current?.id),
    refetchInterval: 15000,
  });

  const data = summaryQuery.data;
  const learning = learningQuery.data;
  const economics = economicsQuery.data;
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
        <p className="mt-2 max-w-3xl text-sm text-muted-foreground">Autoposter возвращает snapshots публикаций. Factory берёт только последний snapshot каждой публикации, связывает результат с форматом и рубрикой и использует историю как осторожный prior для следующих batch-планов.</p>
      </div>

      {!current && <div className="rounded-xl border border-dashed p-8 text-center text-sm text-muted-foreground">Выберите проект.</div>}
      {summaryQuery.isLoading && current && <p className="text-sm text-muted-foreground">Загружаю performance…</p>}
      {summaryQuery.isError && <p className="text-sm text-red-600">Не удалось загрузить performance: {(summaryQuery.error as Error).message}</p>}

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

          {learning && (
            <Card>
              <CardHeader>
                <div className="flex items-start justify-between gap-4">
                  <div>
                    <div className="flex items-center gap-2"><BrainCircuit className="h-5 w-5" /><CardTitle>Learning policy</CardTitle></div>
                    <p className="mt-2 text-sm text-muted-foreground">Primary signal: {learning.primary_metric_label || learning.primary_metric}. Baseline: {formatLearningMetric(learning.baseline, learning.primary_metric)}.</p>
                  </div>
                  <div className="rounded-full border px-3 py-1 text-xs text-muted-foreground">{learning.status}</div>
                </div>
              </CardHeader>
              <CardContent className="space-y-5">
                {learning.status === "insufficient_data" && (
                  <div className="flex gap-3 rounded-xl border border-dashed p-4 text-sm"><AlertTriangle className="mt-0.5 h-4 w-4 shrink-0" /><div><p className="font-medium">Система пока не оптимизирует контент по истории</p><p className="mt-1 text-muted-foreground">Маленькая выборка слишком легко создаёт ложного «победителя». До sample gate новые batch-планы остаются исследовательскими.</p></div></div>
                )}
                {learning.status === "learning" && (
                  <div className="flex gap-3 rounded-xl border p-4 text-sm"><FlaskConical className="mt-0.5 h-4 w-4 shrink-0" /><div><p className="font-medium">Exploration защищён</p><p className="mt-1 text-muted-foreground">Минимум {Math.round(learning.exploration_share * 100)}% будущего batch остаётся под новые гипотезы. История влияет на allocation, но не блокирует discovery.</p></div></div>
                )}

                {!!learning.recommendations.guidance.length && (
                  <div className="space-y-2">
                    <p className="text-xs font-medium uppercase tracking-wide text-muted-foreground">Рекомендации</p>
                    {learning.recommendations.guidance.map((line) => <div key={line} className="rounded-lg bg-muted/40 px-3 py-2 text-sm">{line}</div>)}
                  </div>
                )}

                {!!learning.recommendations.winners.length && (
                  <div className="space-y-3">
                    <p className="text-sm font-semibold">Кандидаты на осторожное масштабирование</p>
                    <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-3">{learning.recommendations.winners.map((row) => <LearningCard key={`${row.dimension}-${row.name}`} row={row} metric={learning.primary_metric} />)}</div>
                  </div>
                )}

                {!!learning.recommendations.watch.length && (
                  <div className="space-y-3">
                    <p className="text-sm font-semibold">Нужен другой angle перед повтором</p>
                    <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-3">{learning.recommendations.watch.map((row) => <LearningCard key={`${row.dimension}-${row.name}`} row={row} metric={learning.primary_metric} />)}</div>
                  </div>
                )}
              </CardContent>
            </Card>
          )}

          {economics && (
            <Card>
              <CardHeader>
                <div className="flex items-start justify-between gap-4">
                  <div>
                    <div className="flex items-center gap-2"><CircleDollarSign className="h-5 w-5" /><CardTitle>Generation economics</CardTitle></div>
                    <p className="mt-2 max-w-3xl text-sm text-muted-foreground">Стоимость считается только для запросов, где тариф модели явно задан в окружении. Неоценённые вызовы остаются `unpriced`, а не превращаются в фиктивный $0.</p>
                  </div>
                  <span className="rounded-full border px-3 py-1 text-xs text-muted-foreground">{economics.pricing_complete ? "pricing complete" : "partial pricing"}</span>
                </div>
              </CardHeader>
              <CardContent className="space-y-5">
                <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-5">
                  <div className="rounded-xl border p-4"><Activity className="h-4 w-4 text-muted-foreground" /><p className="mt-3 text-xs text-muted-foreground">Provider requests</p><p className="mt-1 text-2xl font-bold tabular-nums">{economics.requests}</p></div>
                  <div className="rounded-xl border p-4"><Gauge className="h-4 w-4 text-muted-foreground" /><p className="mt-3 text-xs text-muted-foreground">Total tokens</p><p className="mt-1 text-2xl font-bold tabular-nums">{economics.total_tokens.toLocaleString()}</p></div>
                  <div className="rounded-xl border p-4"><Clock3 className="h-4 w-4 text-muted-foreground" /><p className="mt-3 text-xs text-muted-foreground">Avg latency</p><p className="mt-1 text-2xl font-bold tabular-nums">{economics.average_latency_ms == null ? "—" : `${economics.average_latency_ms} ms`}</p></div>
                  <div className="rounded-xl border p-4"><CircleDollarSign className="h-4 w-4 text-muted-foreground" /><p className="mt-3 text-xs text-muted-foreground">Known cost</p><p className="mt-1 text-2xl font-bold tabular-nums">${economics.known_cost_usd.toFixed(4)}</p></div>
                  <div className="rounded-xl border p-4"><AlertTriangle className="h-4 w-4 text-muted-foreground" /><p className="mt-3 text-xs text-muted-foreground">Unpriced requests</p><p className="mt-1 text-2xl font-bold tabular-nums">{economics.unpriced_requests}</p></div>
                </div>
                {!economics.pricing_configured_for_any && economics.requests > 0 && (
                  <div className="rounded-xl border border-dashed p-4 text-sm text-muted-foreground">Укажи `LLM_INPUT_COST_PER_1M_USD` и `LLM_OUTPUT_COST_PER_1M_USD` для выбранной модели — после этого новые traces начнут сохранять известную стоимость. Старые вызовы намеренно не пересчитываются задним числом по потенциально другому тарифу.</div>
                )}
                <EconomicsTable title="По этапу pipeline" rows={economics.by_stage} />
                <EconomicsTable title="По модели" rows={economics.by_model} />
              </CardContent>
            </Card>
          )}

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
