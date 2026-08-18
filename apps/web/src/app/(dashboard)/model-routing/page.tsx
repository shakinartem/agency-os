"use client";

import { useQuery } from "@tanstack/react-query";
import { Activity, BrainCircuit, Clock3, Coins, FlaskConical, ShieldCheck } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { useProject } from "@/context/ProjectContext";
import { api } from "@/lib/api";

interface Candidate {
  model: string;
  samples: number;
  quality_samples: number;
  performance_samples: number;
  priced_samples: number;
  average_quality: number | null;
  average_performance_proxy: number | null;
  average_latency_ms: number | null;
  average_cost_usd: number | null;
  quality_gate_passed: boolean;
  eligible: boolean;
  confidence: "low" | "medium" | "high";
  score: number | null;
}

interface StageReport {
  recommended_model: string;
  routing_ready: boolean;
  candidate_count: number;
  eligible_count: number;
  candidates: Candidate[];
}

interface RouterReport {
  project_id: string;
  mode: "off" | "shadow" | "active";
  default_model: string;
  configured_candidates: string[];
  minimum_samples_per_model: number;
  quality_floor: number;
  exploration_rate: number;
  performance_metric: string | null;
  stages: Record<string, StageReport>;
  generated_at: string;
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
          Router сравнивает модели только после минимальной выборки и quality gate. Downstream performance используется как шумный prior,
          а не как доказательство причинности. В shadow mode рекомендации видны здесь, но production продолжает работать на default model.
        </p>
      </div>

      {!current && <div className="rounded-xl border border-dashed p-8 text-center text-sm text-muted-foreground">Выберите проект.</div>}
      {isLoading && current && <p className="text-sm text-muted-foreground">Считаю evidence по моделям…</p>}
      {isError && <p className="text-sm text-red-600">Не удалось загрузить Model Router: {(error as Error).message}</p>}

      {current && data && (
        <>
          <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-5">
            <Card><CardContent className="p-4"><p className="text-xs text-muted-foreground">Mode</p><div className="mt-2"><ModeBadge mode={data.mode} /></div></CardContent></Card>
            <Card><CardContent className="p-4"><p className="text-xs text-muted-foreground">Default model</p><p className="mt-2 truncate font-semibold">{data.default_model}</p></CardContent></Card>
            <Card><CardContent className="p-4"><p className="text-xs text-muted-foreground">Candidates</p><p className="mt-2 text-2xl font-bold">{data.configured_candidates.length}</p></CardContent></Card>
            <Card><CardContent className="p-4"><p className="text-xs text-muted-foreground">Min samples / model</p><p className="mt-2 text-2xl font-bold">{data.minimum_samples_per_model}</p></CardContent></Card>
            <Card><CardContent className="p-4"><p className="text-xs text-muted-foreground">Exploration</p><p className="mt-2 text-2xl font-bold">{(data.exploration_rate * 100).toFixed(0)}%</p></CardContent></Card>
          </div>

          {data.mode === "shadow" && (
            <Card className="border-amber-200 bg-amber-50/50">
              <CardContent className="flex gap-3 p-5 text-sm">
                <FlaskConical className="mt-0.5 h-5 w-5 shrink-0 text-amber-700" />
                <div><strong>Shadow mode безопасно включён.</strong> Router записывает evidence и показывает, куда бы направил трафик, но фактически использует {data.default_model}. Переключать `MODEL_ROUTER_MODE=active` стоит только после появления минимум двух eligible моделей на нужном stage.</div>
              </CardContent>
            </Card>
          )}

          <div className="grid gap-4 md:grid-cols-3">
            <Card><CardContent className="flex gap-3 p-5"><ShieldCheck className="h-5 w-5 text-muted-foreground" /><div><p className="text-xs text-muted-foreground">Quality floor</p><p className="mt-1 text-xl font-bold">{pct(data.quality_floor)}</p></div></CardContent></Card>
            <Card><CardContent className="flex gap-3 p-5"><Activity className="h-5 w-5 text-muted-foreground" /><div><p className="text-xs text-muted-foreground">Performance proxy</p><p className="mt-1 text-sm font-semibold">{data.performance_metric || "ещё нет данных"}</p></div></CardContent></Card>
            <Card><CardContent className="flex gap-3 p-5"><Coins className="h-5 w-5 text-muted-foreground" /><div><p className="text-xs text-muted-foreground">Pricing rule</p><p className="mt-1 text-sm font-semibold">Unknown ≠ free</p></div></CardContent></Card>
          </div>

          <div className="space-y-4">
            {Object.entries(data.stages).map(([stage, report]) => (
              <Card key={stage}>
                <CardHeader className="pb-3">
                  <div className="flex flex-wrap items-center justify-between gap-3">
                    <div>
                      <CardTitle>{stageNames[stage] || stage}</CardTitle>
                      <p className="mt-1 text-xs text-muted-foreground">Recommended: <strong className="text-foreground">{report.recommended_model}</strong></p>
                    </div>
                    <div className="flex items-center gap-2">
                      <Badge variant={report.routing_ready ? "default" : "outline"}>{report.routing_ready ? "routing ready" : "collecting evidence"}</Badge>
                      <Badge variant="secondary">{report.eligible_count}/{report.candidate_count} eligible</Badge>
                    </div>
                  </div>
                </CardHeader>
                <CardContent>
                  <div className="overflow-x-auto">
                    <table className="w-full min-w-[900px] text-sm">
                      <thead>
                        <tr className="border-b text-left text-xs text-muted-foreground">
                          <th className="pb-2 font-medium">Model</th>
                          <th className="pb-2 text-right font-medium">Samples</th>
                          <th className="pb-2 text-right font-medium">Quality</th>
                          <th className="pb-2 text-right font-medium">Perf proxy</th>
                          <th className="pb-2 text-right font-medium">Latency</th>
                          <th className="pb-2 text-right font-medium">Cost / req</th>
                          <th className="pb-2 text-right font-medium">Score</th>
                          <th className="pb-2 text-right font-medium">Confidence</th>
                        </tr>
                      </thead>
                      <tbody>
                        {report.candidates.map((candidate) => (
                          <tr key={candidate.model} className="border-b last:border-0">
                            <td className="py-3">
                              <div className="flex items-center gap-2">
                                <span className="font-medium">{candidate.model}</span>
                                {candidate.model === report.recommended_model && <Badge variant="secondary">recommended</Badge>}
                                {!candidate.quality_gate_passed && candidate.samples > 0 && <Badge variant="outline">quality gate</Badge>}
                              </div>
                            </td>
                            <td className="py-3 text-right tabular-nums">{candidate.samples}</td>
                            <td className="py-3 text-right tabular-nums">{pct(candidate.average_quality)}</td>
                            <td className="py-3 text-right tabular-nums">{pct(candidate.average_performance_proxy)}</td>
                            <td className="py-3 text-right tabular-nums">{candidate.average_latency_ms == null ? "—" : `${candidate.average_latency_ms} ms`}</td>
                            <td className="py-3 text-right tabular-nums">{money(candidate.average_cost_usd)}</td>
                            <td className="py-3 text-right tabular-nums">{candidate.score == null ? "—" : candidate.score.toFixed(4)}</td>
                            <td className="py-3 text-right"><Badge variant="outline">{candidate.confidence}</Badge></td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                </CardContent>
              </Card>
            ))}
          </div>

          <Card>
            <CardContent className="grid gap-4 p-5 text-sm md:grid-cols-3">
              <div className="flex gap-2"><ShieldCheck className="mt-0.5 h-4 w-4 shrink-0 text-muted-foreground" /><span><strong>Quality first.</strong> Дешёвая модель ниже floor не может выиграть за счёт цены.</span></div>
              <div className="flex gap-2"><Clock3 className="mt-0.5 h-4 w-4 shrink-0 text-muted-foreground" /><span><strong>Cost/latency second.</strong> Они оптимизируются только среди моделей с достаточной доказательной базой.</span></div>
              <div className="flex gap-2"><FlaskConical className="mt-0.5 h-4 w-4 shrink-0 text-muted-foreground" /><span><strong>Exploration deterministic.</strong> Retry одного run/stage не перескакивает между моделями.</span></div>
            </CardContent>
          </Card>
        </>
      )}
    </div>
  );
}
