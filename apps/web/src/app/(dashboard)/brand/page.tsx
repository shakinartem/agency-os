"use client";

import { useEffect, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { api } from "@/lib/api";
import { useProject } from "@/context/ProjectContext";
import { BrainCircuit, Save } from "lucide-react";

interface BrandProfile {
  positioning?: string;
  audience?: { description?: string; [key: string]: unknown };
  products?: unknown[];
  tone_of_voice?: { description?: string; [key: string]: unknown };
  brand_rules?: string[];
  forbidden_claims?: string[];
  examples?: unknown[];
}

const lines = (value: string) => value.split("\n").map((line) => line.trim()).filter(Boolean);
const toText = (value: unknown[] | undefined) => (value || []).map((item) => typeof item === "string" ? item : JSON.stringify(item)).join("\n");

export default function BrandPage() {
  const { current } = useProject();
  const queryClient = useQueryClient();
  const [positioning, setPositioning] = useState("");
  const [audience, setAudience] = useState("");
  const [products, setProducts] = useState("");
  const [tone, setTone] = useState("");
  const [rules, setRules] = useState("");
  const [forbidden, setForbidden] = useState("");
  const [examples, setExamples] = useState("");

  const { data: profile, isLoading } = useQuery({
    queryKey: ["brand-profile", current?.id],
    queryFn: () => api.get<BrandProfile | null>(`/factory/brand/${current?.id}`),
    enabled: Boolean(current?.id),
  });

  useEffect(() => {
    if (!profile) return;
    setPositioning(profile.positioning || "");
    setAudience(String(profile.audience?.description || ""));
    setProducts(toText(profile.products));
    setTone(String(profile.tone_of_voice?.description || ""));
    setRules((profile.brand_rules || []).join("\n"));
    setForbidden((profile.forbidden_claims || []).join("\n"));
    setExamples(toText(profile.examples));
  }, [profile]);

  const save = useMutation({
    mutationFn: () => api.put<BrandProfile>(`/factory/brand/${current?.id}`, {
      positioning,
      audience: { description: audience },
      products: lines(products),
      tone_of_voice: { description: tone },
      brand_rules: lines(rules),
      forbidden_claims: lines(forbidden),
      examples: lines(examples),
    }),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["brand-profile"] }),
  });

  return (
    <div className="space-y-6">
      <div>
        <div className="flex items-center gap-2 text-sm font-medium text-primary"><BrainCircuit className="h-4 w-4" /> Brand Brain</div>
        <h1 className="mt-1 text-3xl font-bold tracking-tight">Контекст бренда</h1>
        <p className="mt-2 max-w-3xl text-sm text-muted-foreground">Это не декоративные настройки: контекст подмешивается в генерацию, critique, factuality/brand checks и построение рубрикатора. Чем лучше здесь данные, тем меньше универсального «AI-контента» на выходе.</p>
      </div>

      {!current && <div className="rounded-xl border border-dashed p-8 text-center text-sm text-muted-foreground">Выберите проект в верхней панели.</div>}
      {current && isLoading && <p className="text-sm text-muted-foreground">Loading…</p>}
      {current && !isLoading && (
        <div className="grid gap-4 xl:grid-cols-2">
          <Field title="Позиционирование" hint="Кто мы, для кого, какую ценность создаём и чем отличаемся." value={positioning} onChange={setPositioning} rows={7} />
          <Field title="Целевая аудитория" hint="Сегменты, боли, контекст покупки, критерии выбора, уровень осведомлённости." value={audience} onChange={setAudience} rows={7} />
          <Field title="Продукты / офферы" hint="Один продукт или оффер на строку." value={products} onChange={setProducts} rows={7} />
          <Field title="Tone of voice" hint="Как звучит бренд: уровень формальности, темп, характер, допустимая смелость." value={tone} onChange={setTone} rows={7} />
          <Field title="Правила бренда" hint="Одно правило на строку: что обязательно соблюдать в любом материале." value={rules} onChange={setRules} rows={8} />
          <Field title="Запрещённые утверждения" hint="Что нельзя обещать, утверждать или формулировать публично." value={forbidden} onChange={setForbidden} rows={8} />
          <div className="xl:col-span-2"><Field title="Примеры хорошего контента / голоса" hint="По одному примеру или короткой заметке на строку. Позже это заменим на полноценную knowledge base с файлами." value={examples} onChange={setExamples} rows={8} /></div>

          <div className="xl:col-span-2 flex items-center justify-end gap-3">
            {save.isSuccess && <span className="text-xs text-emerald-600">Сохранено</span>}
            {save.isError && <span className="text-xs text-red-600">{(save.error as Error).message}</span>}
            <button onClick={() => save.mutate()} disabled={save.isPending} className="inline-flex items-center gap-2 rounded-lg bg-primary px-4 py-2 text-sm font-semibold text-primary-foreground disabled:opacity-50"><Save className="h-4 w-4" /> {save.isPending ? "Сохраняю…" : "Сохранить Brand Brain"}</button>
          </div>
        </div>
      )}
    </div>
  );
}

function Field({ title, hint, value, onChange, rows }: { title: string; hint: string; value: string; onChange: (value: string) => void; rows: number }) {
  return (
    <Card>
      <CardHeader className="pb-3"><CardTitle className="text-base">{title}</CardTitle><p className="text-xs text-muted-foreground">{hint}</p></CardHeader>
      <CardContent><textarea value={value} onChange={(e) => onChange(e.target.value)} rows={rows} className="w-full resize-y rounded-xl border bg-background p-3 text-sm outline-none focus:ring-2 focus:ring-primary/30" /></CardContent>
    </Card>
  );
}
