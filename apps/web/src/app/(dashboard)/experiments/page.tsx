"use client";

import { useMemo, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { FlaskConical, Pause, Play, ShieldCheck, SquareCheckBig } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { useProject } from "@/context/ProjectContext";
import { api } from "@/lib/api";

interface ArmReport {
  id: string; key: string; name: string; model: string | null; candidate_prompt_version: string;
  observations: number; valid_samples: number; failed_samples: number; candidate_wins: number; control_wins: number; ties: number;
  candidate_win_rate: number | null; average_quality_delta: number | null; average_candidate_quality: number | null;
  average_control_quality: number | null; average_candidate_latency_ms: number | null; average_candidate_cost_usd: number | null;
  failure_rate: number; confidence: "low" | "medium" | "high";
  decision: "collecting" | "promising" | "inconclusive" | "reject" | "reject_reliability";
}

interface ExperimentReport {
  id: string; name: string; hypothesis: string | null; stage_family: string; content_types: string[];
  status: "draft" | "shadow" | "paused" | "completed"; sample_rate: number; min_samples: number;
  control_prompt_version: string; compatible_with_current_prompt: boolean; recommendation: string | null;
  started_at: string | null; completed_at: string | null; arms: ArmReport[];
}

interface ExperimentsPayload {
  project_id: string; current_prompt_version: string; auto_promotion: boolean; max_shadow_sample_rate: number; experiments: ExperimentReport[];
}
interface RouterReport { configured_candidates: string[]; default_model: string; }

const stages = [
  ["draft", "Draft"], ["evaluate", "Critic / Final QA"], ["revise", "Revision"], ["humanize", "Humanizer"],
  ["adapt", "Platform adaptation"], ["batch_plan", "Batch planning"], ["strategy_write", "Strategy writer"], ["strategy_review", "Strategy critic"],
] as const;

function pct(value: number | null) { return value == null ? "—" : `${(value * 100).toFixed(1)}%`; }
function decisionBadge(decision: ArmReport["decision"]) {
  if (decision === "promising") return <Badge>promising</Badge>;
  if (decision.startsWith("reject")) return <Badge variant="destructive">{decision}</Badge>;
  if (decision === "inconclusive") return <Badge variant="secondary">inconclusive</Badge>;
  return <Badge variant="outline">collecting</Badge>;
}

export default function ExperimentsPage() {
  const { current } = useProject();
  const queryClient = useQueryClient();
  const [name, setName] = useState("");
  const [hypothesis, setHypothesis] = useState("");
  const [stage, setStage] = useState("draft");
  const [sampleRate, setSampleRate] = useState("0.05");
  const [minSamples, setMinSamples] = useState("20");
  const [candidateModel, setCandidateModel] = useState("");
  const [systemAppend, setSystemAppend] = useState("");
  const [promptAppend, setPromptAppend] = useState("");

  const experiments = useQuery({
    queryKey: ["prompt-experiments", current?.id],
    queryFn: () => api.get<ExperimentsPayload>(`/model-routing/experiments?project_id=${current?.id}`),
    enabled: Boolean(current?.id), refetchInterval: 15000,
  });
  const router = useQuery({
    queryKey: ["model-routing", current?.id],
    queryFn: () => api.get<RouterReport>(`/model-routing/report?project_id=${current?.id}`),
    enabled: Boolean(current?.id),
  });
  const models = useMemo(() => router.data?.configured_candidates || [], [router.data]);

  const createExperiment = useMutation({
    mutationFn: async () => {
      if (!current) throw new Error("Project is not selected");
      return api.post("/model-routing/experiments", {
        project_id: current.id, name, hypothesis: hypothesis || null, stage_family: stage, content_types: [],
        sample_rate: Number(sampleRate), min_samples: Number(minSamples),
        arms: [{ key: "candidate-a", name: "Candidate A", model: candidateModel || null, system_append: systemAppend || null, prompt_append: promptAppend || null }],
      });
    },
    onSuccess: () => {
      setName(""); setHypothesis(""); setSystemAppend(""); setPromptAppend("");
      queryClient.invalidateQueries({ queryKey: ["prompt-experiments", current?.id] });
    },
  });
  const action = useMutation({
    mutationFn: ({ id, verb }: { id: string; verb: "start" | "pause" | "complete" }) => api.post(`/model-routing/experiments/${id}/${verb}`),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["prompt-experiments", current?.id] }),
  });
  const canCreate = Boolean(current && name.trim() && (candidateModel || systemAppend.trim() || promptAppend.trim()) && !createExperiment.isPending);

  return <div className="space-y-6">
    <div>
      <div className="flex items-center gap-2 text-sm font-medium text-primary"><FlaskConical className="h-4 w-4" /> Experiments</div>
      <h1 className="mt-1 text-3xl font-bold tracking-tight">Prompt × Model Experiment Registry</h1>
      <p className="mt-2 max-w-4xl text-sm text-muted-foreground">Production остаётся control. Candidate arm запускается только в shadow, сравнивается blinded judge и никогда не попадает в пользовательский output. Experiment evidence хранится отдельно от Model Router, поэтому prompt improvement не приписывается модели.</p>
    </div>

    {!current && <div className="rounded-xl border border-dashed p-8 text-center text-sm text-muted-foreground">Выберите проект.</div>}
    {current && <Card>
      <CardHeader><CardTitle>Новый shadow experiment</CardTitle></CardHeader>
      <CardContent className="space-y-4">
        <div className="grid gap-4 md:grid-cols-2">
          <div><label className="mb-1 block text-xs text-muted-foreground">Название</label><Input value={name} onChange={(e) => setName(e.target.value)} placeholder="Shorter CTA instruction" /></div>
          <div><label className="mb-1 block text-xs text-muted-foreground">Stage</label><select className="h-10 w-full rounded-md border bg-background px-3 text-sm" value={stage} onChange={(e) => setStage(e.target.value)}>{stages.map(([value, label]) => <option key={value} value={value}>{label}</option>)}</select></div>
        </div>
        <div><label className="mb-1 block text-xs text-muted-foreground">Hypothesis</label><Input value={hypothesis} onChange={(e) => setHypothesis(e.target.value)} placeholder="Explicit factual restraint improves quality without material cost increase" /></div>
        <div className="grid gap-4 md:grid-cols-3">
          <div><label className="mb-1 block text-xs text-muted-foreground">Candidate model</label><select className="h-10 w-full rounded-md border bg-background px-3 text-sm" value={candidateModel} onChange={(e) => setCandidateModel(e.target.value)}><option value="">same as routed control</option>{models.map((m) => <option key={m} value={m}>{m}</option>)}</select></div>
          <div><label className="mb-1 block text-xs text-muted-foreground">Shadow sample rate</label><Input type="number" min="0.01" max="0.25" step="0.01" value={sampleRate} onChange={(e) => setSampleRate(e.target.value)} /></div>
          <div><label className="mb-1 block text-xs text-muted-foreground">Min valid samples</label><Input type="number" min="5" max="500" value={minSamples} onChange={(e) => setMinSamples(e.target.value)} /></div>
        </div>
        <div className="grid gap-4 md:grid-cols-2">
          <div><label className="mb-1 block text-xs text-muted-foreground">System prompt delta</label><textarea className="min-h-28 w-full rounded-md border bg-background p-3 text-sm" value={systemAppend} onChange={(e) => setSystemAppend(e.target.value)} placeholder="Candidate-only instruction appended to the system prompt" /></div>
          <div><label className="mb-1 block text-xs text-muted-foreground">User prompt delta</label><textarea className="min-h-28 w-full rounded-md border bg-background p-3 text-sm" value={promptAppend} onChange={(e) => setPromptAppend(e.target.value)} placeholder="Candidate-only instruction appended to the task prompt" /></div>
        </div>
        <div className="flex flex-wrap items-center justify-between gap-3 rounded-lg border bg-muted/30 p-3 text-xs text-muted-foreground">
          <span>Current control cohort: <strong className="text-foreground">{experiments.data?.current_prompt_version || "loading…"}</strong></span>
          <span>Max shadow rate: {((experiments.data?.max_shadow_sample_rate || 0.25) * 100).toFixed(0)}% · auto-promotion disabled</span>
        </div>
        {createExperiment.isError && <p className="text-sm text-red-600">{(createExperiment.error as Error).message}</p>}
        <Button disabled={!canCreate} onClick={() => createExperiment.mutate()}>Create draft</Button>
      </CardContent>
    </Card>}

    {experiments.isLoading && current && <p className="text-sm text-muted-foreground">Загружаю registry…</p>}
    {experiments.isError && <p className="text-sm text-red-600">Не удалось загрузить experiments: {(experiments.error as Error).message}</p>}

    <div className="space-y-4">
      {experiments.data?.experiments.map((experiment) => <Card key={experiment.id}>
        <CardHeader className="pb-3"><div className="flex flex-wrap items-start justify-between gap-3">
          <div><div className="flex flex-wrap items-center gap-2"><CardTitle>{experiment.name}</CardTitle><Badge variant={experiment.status === "shadow" ? "default" : "outline"}>{experiment.status}</Badge>{!experiment.compatible_with_current_prompt && <Badge variant="destructive">prompt cohort changed</Badge>}</div><p className="mt-2 max-w-3xl text-sm text-muted-foreground">{experiment.hypothesis || "Без зафиксированной гипотезы"}</p><div className="mt-2 flex flex-wrap gap-3 text-xs text-muted-foreground"><span>stage: {experiment.stage_family}</span><span>sample: {(experiment.sample_rate * 100).toFixed(0)}%</span><span>min: {experiment.min_samples}</span><span>control: {experiment.control_prompt_version}</span></div></div>
          <div className="flex gap-2">
            {(experiment.status === "draft" || experiment.status === "paused") && <Button size="sm" disabled={!experiment.compatible_with_current_prompt || action.isPending} onClick={() => action.mutate({ id: experiment.id, verb: "start" })}><Play className="mr-1 h-4 w-4" /> Start</Button>}
            {experiment.status === "shadow" && <Button size="sm" variant="outline" disabled={action.isPending} onClick={() => action.mutate({ id: experiment.id, verb: "pause" })}><Pause className="mr-1 h-4 w-4" /> Pause</Button>}
            {(experiment.status === "shadow" || experiment.status === "paused") && <Button size="sm" variant="secondary" disabled={action.isPending} onClick={() => action.mutate({ id: experiment.id, verb: "complete" })}><SquareCheckBig className="mr-1 h-4 w-4" /> Complete</Button>}
          </div>
        </div></CardHeader>
        <CardContent className="space-y-3">
          {experiment.recommendation && <div className="flex items-center gap-2 rounded-lg border bg-muted/30 p-3 text-sm"><ShieldCheck className="h-4 w-4" /><span>Best promising arm: <strong>{experiment.recommendation}</strong>. Это recommendation для отдельного rollout decision, не auto-promotion.</span></div>}
          <div className="overflow-x-auto"><table className="w-full min-w-[980px] text-sm"><thead><tr className="border-b text-left text-xs text-muted-foreground"><th className="pb-2">Arm</th><th className="pb-2">Model</th><th className="pb-2 text-right">Valid</th><th className="pb-2 text-right">Win rate</th><th className="pb-2 text-right">Δ quality</th><th className="pb-2 text-right">Candidate quality</th><th className="pb-2 text-right">Latency</th><th className="pb-2 text-right">Cost</th><th className="pb-2 text-right">Decision</th></tr></thead><tbody>{experiment.arms.map((arm) => <tr key={arm.id} className="border-b last:border-0"><td className="py-3"><div className="font-medium">{arm.name}</div><div className="text-xs text-muted-foreground">{arm.candidate_prompt_version}</div></td><td className="py-3">{arm.model || "control model"}</td><td className="py-3 text-right tabular-nums">{arm.valid_samples}/{experiment.min_samples}</td><td className="py-3 text-right tabular-nums">{pct(arm.candidate_win_rate)}</td><td className="py-3 text-right tabular-nums">{arm.average_quality_delta == null ? "—" : `${arm.average_quality_delta >= 0 ? "+" : ""}${arm.average_quality_delta.toFixed(3)}`}</td><td className="py-3 text-right tabular-nums">{pct(arm.average_candidate_quality)}</td><td className="py-3 text-right tabular-nums">{arm.average_candidate_latency_ms == null ? "—" : `${arm.average_candidate_latency_ms} ms`}</td><td className="py-3 text-right tabular-nums">{arm.average_candidate_cost_usd == null ? "unpriced" : `$${arm.average_candidate_cost_usd.toFixed(6)}`}</td><td className="py-3 text-right">{decisionBadge(arm.decision)}</td></tr>)}</tbody></table></div>
        </CardContent>
      </Card>)}
      {experiments.data && experiments.data.experiments.length === 0 && <div className="rounded-xl border border-dashed p-10 text-center text-sm text-muted-foreground">Экспериментов пока нет. Создай draft, зафиксируй гипотезу, затем запусти shadow.</div>}
    </div>
  </div>;
}
