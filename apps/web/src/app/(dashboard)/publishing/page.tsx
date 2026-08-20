"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { api } from "@/lib/api";
import { useProject } from "@/context/ProjectContext";
import { RefreshCcw, Send } from "lucide-react";

interface Delivery {
  id: string;
  content_item_id: string;
  destination: string;
  schema_version: string;
  payload: Record<string, unknown>;
  status: string;
  external_id?: string;
  error?: string;
  created_at?: string;
}

export default function PublishingPage() {
  const { current } = useProject();
  const queryClient = useQueryClient();
  const { data: deliveries = [], isLoading } = useQuery({
    queryKey: ["factory-outbox", current?.id],
    queryFn: () => api.get<Delivery[]>(`/factory/outbox${current?.id ? `?project_id=${current.id}` : ""}`),
    refetchInterval: 5000,
  });

  const sendDelivery = useMutation({
    mutationFn: (deliveryId: string) => api.post(`/factory/outbox/${deliveryId}/send`),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["factory-outbox"] }),
  });

  return (
    <div className="space-y-6">
      <div>
        <div className="flex items-center gap-2 text-sm font-medium text-primary"><Send className="h-4 w-4" /> Autoposter handoff</div>
        <h1 className="mt-1 text-3xl font-bold tracking-tight">Outbox</h1>
        <p className="mt-2 text-sm text-muted-foreground">Content Factory не публикует сама. Здесь лежат проверенные content-package/1.0 пакеты. Повторная отправка использует idempotency key, чтобы Autoposter мог безопасно дедуплицировать запрос.</p>
      </div>

      <Card>
        <CardHeader><CardTitle>Content packages</CardTitle></CardHeader>
        <CardContent className="space-y-3">
          {isLoading && <p className="text-sm text-muted-foreground">Loading…</p>}
          {deliveries.map((delivery) => {
            const canonical = (delivery.payload?.canonical || {}) as Record<string, unknown>;
            const variants = (delivery.payload?.variants || []) as Array<Record<string, unknown>>;
            const packageStatus = String(delivery.payload?.status || "");
            const canSend = packageStatus === "approved" && ["queued", "failed"].includes(delivery.status);
            return (
              <div key={delivery.id} className="rounded-xl border p-4">
                <div className="flex flex-wrap items-start justify-between gap-3">
                  <div>
                    <p className="text-sm font-semibold">{String(canonical.title || canonical.topic || delivery.content_item_id)}</p>
                    <p className="mt-1 text-xs text-muted-foreground">{delivery.schema_version} · {variants.map((v) => String(v.platform)).join(", ") || "no variants"}</p>
                  </div>
                  <div className="flex items-center gap-2">
                    <Badge variant="secondary">{delivery.status}</Badge>
                    {canSend && (
                      <button
                        onClick={() => sendDelivery.mutate(delivery.id)}
                        disabled={sendDelivery.isPending}
                        className="inline-flex items-center gap-1 rounded-lg border px-3 py-1.5 text-xs font-medium hover:bg-muted disabled:opacity-50"
                      >
                        {delivery.status === "failed" ? <RefreshCcw className="h-3.5 w-3.5" /> : <Send className="h-3.5 w-3.5" />}
                        {delivery.status === "failed" ? "Retry" : "Send"}
                      </button>
                    )}
                  </div>
                </div>
                <div className="mt-3 flex flex-wrap gap-4 text-xs text-muted-foreground">
                  <span>destination: {delivery.destination}</span>
                  <span>content: {delivery.content_item_id.slice(0, 8)}</span>
                  <span>package: {packageStatus || "unknown"}</span>
                  {delivery.external_id && <span>external: {delivery.external_id}</span>}
                </div>
                {delivery.error && <p className="mt-3 text-xs text-red-600">{delivery.error}</p>}
              </div>
            );
          })}
          {!isLoading && deliveries.length === 0 && <div className="rounded-xl border border-dashed p-8 text-center text-sm text-muted-foreground">Пакетов пока нет. Они появятся после прохождения production pipeline.</div>}
        </CardContent>
      </Card>
    </div>
  );
}
