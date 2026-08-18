"use client";

import { useQuery } from "@tanstack/react-query";
import { Activity, BrainCircuit, Clock3, Coins, DatabaseZap, FlaskConical, ShieldCheck } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { useProject } from "@/context/ProjectContext";
import { api } from "@/lib/api";

interface Candidate {
  model: string;
  samples: number;
  live_samples: number;
  shadow_samples: number;
  quality_samples: number;
  performance_samples: number;
  priced_samples: number;
  average_quality: number | null;
  average_performance_proxy: number | null;
  average_latency_ms: number | null;
  average_cost_usd: number | null;
  quality_gate_passed: boolean;
  eligible: boolean;
  production_eligible: boolean;
  confidence: "low" | "medium" | "high";
  score: number | null;
}

interface StageReport {
  recommended_model: string;
  shadow_recommended_model: string;
  routing_ready: boolean;
  shadow_ready: boolean;
  candidate_count: number;
  eligible_count: number;
  production_eligible_count: number;
  candidates: Candidate[];
}

interface CacheInfo {
  state: "ready" | "stale" | "warming";
  fresh: boolean;
  ttl_seconds: number;
  refreshed_at: string | null;
  last_error: string | null;
}

interface RouterReport {
  project_id: string;
  mode: "off" | "shadow" | "active";
  default_model: string;
  configured_candidates: string[];
  minimum_samples_per_model: number;
  minimum_live_samples: number;
  minimum_downstream_samples: number;
  quality_floor: number;
  shadow_sample_rate: number;
  exploration_rate: number;
  performance_metric: string | null;
  stages: Record<string, StageReport>;
  generated_at: string;
  cache: CacheInfo;
}

const stageNames: Record<string, string> = {
  draft: "Draft",
  evaluate: "Critic / Final QA",
  revise: "Revision",
  humanize: "Humanizer",
  adapt: "Platform adaptation",
  batch_plan: "Batch planning",
  strategy_write: "Strategy writer",
  strategy_review: "Strategy critic",
};

function pct(value: number | null) {
  return value == null ? "—" : `${(value * 100).toFixed(1)}%`;
}

function money(value: number | null) {
  return value == null ? "unpriced" : `$${value.toFixed(6)}`;
}

function ModeBadge({ mode }: { mode: RouterReport["mode"] }) {
  if (mode === "active") return <Badge>ACTIVE</Badge>;
  if (mode === "shadow") return <Badge variant="secondary">SHADOW</Badge>;
  return <Badge variant="outline">OFF</Badge>;
}

function CacheBadge({ cache }: { cache: CacheInfo }) {
  if (cache.state === "ready") return <Badge>SNAPSHOT READY</Badge>;
  if (cache.state === "stale") return <Badge variant="secondary">STALE · REFRESH QUEUED</Badge>;
  return <Badge variant="outline">WARMING</Badge>;
}

export default function ModelRoutingPage() {
  const { current } = useProject();
  const { data, isLoading, isError, error } = useQuery({
    queryKey: ["model-routing", current?.id],
    queryFn: () => api.get<RouterReport>(`/model-routing/report?project_id=${current?.id}`),
    enabled: Boolean(current?.id),
    refetchInterval: 30000,
  });

  return (
    <div className="space-y-6">
      <div>
        <div className="flex items-center gap-2 text-sm font-medium text-primary">
          <BrainCircuit className="h-4 w-4" /> Model Router
        </div>
        <h1 className="mt-1 text-3xl font-bold tracking-tight">Какая модель должна делать каждый этап</h1>
        <p className="mt-2 max-w-4xl text-sm text-muted-foreground">
          Shadow evidence и live evidence разделены. Offline candidate сначала доказывает качество, цену и latency на blinded A/B trial,
          а полный production routing разрешается только после живой выборки и, для content stages, downstream outcomes.
        </p>
      </div>

      {!current && <div className="rounded-xl border border-dashed p-8 text-center text-sm text-muted-foreground">Выберите проект.</div>}
      {isLoading && current && <p className="text-sm text-muted-foreground">Загружаю materialized routing snapshot…</p>}
      {isError && <p className="text-sm text-red-600">Не удалось загрузить Model Router: {(error as Error).message}</p>}

      {current && data && (
        <>
          <Card>
            <CardContent className="flex flex-wrap items-center justify-between gap-4 p-5">
              <div className="flex items-start gap-3">
                <DatabaseZap className="mt-0.5 h-5 w-5 text-muted-foreground" />
                <div>
                  <div className="flex flex-wrap items-center gap-2"><strong>Materialized evidence</strong><CacheBadge cache={data.cache} /></div>
                  <p className="mt-1 text-xs text-muted-foreground">
                    Router не сканирует всю историю синхронно. TTL {data.cache.ttl_seconds}s; устаревший snapshot обслуживается stale-while-revalidate, а refresh ставится через durable task outbox.
                  </p>
                </div>
              </div>
              <div className="text-right text-xs text-muted-foreground">
                <div>Refreshed: {data.cache.refreshed_at ? new Date(data.cache.refreshed_at).toLocaleString() : "ещё не materialized"}</div>
                {data.cache.last_error && <div className="mt-1 max-w-xl text-red-600">Last refresh error: {data.cache.last_error}</div>}
              </div>
            </CardContent>
          </Card>

          <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-7">
            <Card><CardContent className="p-4"><p className="text-xs text-muted-foreground">Mode</p><div className="mt-2"><ModeBadge mode={data.mode} /></div></CardContent></Card>
            <Card><CardContent className="p-4"><p className="text-xs text-muted-foreground">Default model</p><p className="mt-2 truncate font-semibold">{data.default_model}</p></CardContent></Card>
            <Card><CardContent className="p-4"><p className="text-xs text-muted-foreground">Candidates</p><p className="mt-2 text-2xl font-bold">{data.configured_candidates.length}</p></CardContent></Card>
            <Card><CardContent className="p-4"><p className="text-xs text-muted-foreground">Min total</p><p className="mt-2 text-2xl font-bold">{data.minimum_samples_per_model}</p></CardContent></Card>
            <Card><CardContent className="p-4"><p className="text-xs text-muted-foreground">Min live</p><p className="mt-2 text-2xl font-bold">{data.minimum_live_samples}</p></CardContent></Card>
            <Card><CardContent className="p-4"><p className="text-xs text-muted-foreground">Min outcomes</p><p className="mt-2 text-2xl font-bold">{data.minimum_downstream_samples}</p></CardContent></Card>
            <Card><CardContent className="p-4"><p className="text-xs text-muted-foreground">Shadow / explore</p><p className="mt-2 text-xl font-bold">{(data.shadow_sample_rate * 100).toFixed(0)}% / {(data.exploration_rate * 100).toFixed(0)}%</p></CardContent></Card>
          </div>

          {data.mode === "shadow" && (
            <Card className="border-amber-200 bg-amber-50/50">
              <CardContent className="flex gap-3 p-5 text-sm">
                <FlaskConical className="mt-0.5 h-5 w-5 shrink-0 text-amber-700" />
                <div>
                  <strong>Shadow mode безопасно включён.</strong> Production всегда остаётся на {data.default_model}. На небольшой детерминированной доле run control и одна недоисследованная candidate-модель вызываются параллельно, после чего blinded judge сравнивает A/B. Candidate output никогда не попадает пользователю.
                </div>
              </CardContent>
            </Card>
          )}

          <div className="grid gap-4 md:grid-cols-3">
            <Card><CardContent className="flex gap-3 p-5"><ShieldCheck className="h-5 w-5 text-muted-foreground" /><div><p className="text-xs text-muted-foreground">Quality floor</p><p className="mt-1 text-xl font-bold">{pct(data.quality_floor)}</p></div></CardContent></Card>
            <Card><CardContent className="flex gap-3 p-5"><Activity className="h-5 w-5 text-muted-foreground" /><div><p className="text-xs text-muted-foreground">Performance proxy</p><p className="mt-1 text-sm font-semibold">{data.performance_metric || "ещё нет live данных"}</p></div></CardContent></Card>
            <Card><CardContent className="flex gap-3 p-5"><Coins className="h-5 w-5 text-muted-foreground" /><div><p className="text-xs text-muted-foreground">Pricing rule</p><p className="mt-1 text-sm font-semibold">Unknown ≠ free</p></div></CardContent></Card>
          </div>

          <div className="space-y-4">
            {Object.entries(data.stages).map(([stage, report]) => (
              <Card key={stage}>
                <CardHeader className="pb-3">
                  <div className="flex flex-wrap items-center justify-between gap-3">
                    <div>
                      <CardTitle>{stageNames[stage] || stage}</CardTitle>
                      <div className="mt-1 flex flex-wrap gap-x-4 gap-y-1 text-xs text-muted-foreground">
                        <span>Live recommendation: <strong className="text-foreground">{report.recommended_model}</strong></span>
                        <span>Shadow leader: <strong className="text-foreground">{report.shadow_recommended_model}</strong></span>
                      </div>
                    </div>
                    <div className="flex items-center gap-2">
                      <Badge variant={report.routing_ready ? "default" : "outline"}>{report.routing_ready ? "full routing ready" : "live gate pending"}</Badge>
                      <Badge variant={report.shadow_ready ? "secondary" : "outline"}>{report.shadow_ready ? "shadow comparison ready" : "collecting shadow evidence"}</Badge>
                    </div>
                  </div>
                </CardHeader>
                <CardContent>
                  <div className="overflow-x-auto">
                    <table className="w-full min-w-[1080px] text-sm">
                      <thead><tr className="border-b text-left text-xs text-muted-foreground"><th className="pb-2 font-medium">Model</th><th className="pb-2 text-right font-medium">Total</th><th className="pb-2 text-right font-medium">Shadow</th><th className="pb-2 text-right font-medium">Live</th><th className="pb-2 text-right font-medium">Quality</th><th className="pb-2 text-right font-medium">Perf proxy</th><th className="pb-2 text-right font-medium">Latency</th><th className="pb-2 text-right font-medium">Cost / req</th><th className="pb-2 text-right font-medium">Score</th><th className="pb-2 text-right font-medium">Status</th></tr></thead>
                      <tbody>
                        {report.candidates.map((candidate) => (
                          <tr key={candidate.model} className="border-b last:border-0">
                            <td className="py-3"><div className="flex items-center gap-2"><span className="font-medium">{candidate.model}</span>{candidate.model === report.recommended_model && <Badge variant="secondary">live leader</Badge>}{candidate.model === report.shadow_recommended_model && candidate.model !== report.recommended_model && <Badge variant="outline">shadow leader</Badge>}</div></td>
                            <td className="py-3 text-right tabular-nums">{candidate.samples}</td><td className="py-3 text-right tabular-nums">{candidate.shadow_samples}</td><td className="py-3 text-right tabular-nums">{candidate.live_samples}</td><td className="py-3 text-right tabular-nums">{pct(candidate.average_quality)}</td><td className="py-3 text-right tabular-nums">{pct(candidate.average_performance_proxy)}</td><td className="py-3 text-right tabular-nums">{candidate.average_latency_ms == null ? "—" : `${candidate.average_latency_ms} ms`}</td><td className="py-3 text-right tabular-nums">{money(candidate.average_cost_usd)}</td><td className="py-3 text-right tabular-nums">{candidate.score == null ? "—" : candidate.score.toFixed(4)}</td>
                            <td className="py-3 text-right">{candidate.production_eligible ? <Badge>production eligible</Badge> : candidate.eligible ? <Badge variant="secondary">shadow qualified</Badge> : <Badge variant="outline">{candidate.confidence}</Badge>}</td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                </CardContent>
              </Card>
            ))}
          </div>

          <Card><CardContent className="grid gap-4 p-5 text-sm md:grid-cols-3"><div className="flex gap-2"><ShieldCheck className="mt-0.5 h-4 w-4 shrink-0 text-muted-foreground" /><span><strong>Quality first.</strong> Дешёвая модель ниже floor не может выиграть за счёт цены.</span></div><div className="flex gap-2"><Clock3 className="mt-0.5 h-4 w-4 shrink-0 text-muted-foreground" /><span><strong>Shadow ≠ live.</strong> Offline judge открывает только путь к controlled exploration; полный routing требует живых outcomes.</span></div><div className="flex gap-2"><FlaskConical className="mt-0.5 h-4 w-4 shrink-0 text-muted-foreground" /><span><strong>Retry-stable.</strong> Shadow sampling, A/B order и live exploration детерминированы по run/stage.</span></div></CardContent></Card>
        </>
      )}
    </div>
  );
}
