"use client";

import { useQuery } from "@tanstack/react-query";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Puzzle, CheckCircle, XCircle, HelpCircle } from "lucide-react";
import { api } from "@/lib/api";

interface Integration {
  id: string;
  service_name: string;
  enabled: boolean;
  health_status: string;
  last_sync_at?: string;
  last_error?: string;
}

const statusIcon: Record<string, React.ReactNode> = {
  healthy: <CheckCircle className="h-5 w-5 text-emerald-600" />,
  degraded: <HelpCircle className="h-5 w-5 text-amber-600" />,
  down: <XCircle className="h-5 w-5 text-red-600" />,
};

export default function IntegrationsPage() {
  const { data: integrations = [], isLoading, refetch } = useQuery({
    queryKey: ["integrations"],
    queryFn: () => api.get<Integration[]>("/integrations"),
  });

  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-bold">Integrations</h1>

      {isLoading ? (
        <p className="text-sm text-muted-foreground">Loading…</p>
      ) : (
        <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
          {integrations.map((intg) => (
            <Card key={intg.id}>
              <CardHeader className="flex flex-row items-center justify-between space-y-0">
                <CardTitle className="text-base">{intg.service_name}</CardTitle>
                {statusIcon[intg.health_status] ?? <HelpCircle className="h-5 w-5" />}
              </CardHeader>
              <CardContent className="space-y-2">
                <div className="flex items-center justify-between">
                  <span className="text-sm text-muted-foreground">Status</span>
                  <Badge variant={intg.health_status === "healthy" ? "success" : intg.health_status === "degraded" ? "warning" : "destructive"}>
                    {intg.health_status}
                  </Badge>
                </div>
                <div className="flex items-center justify-between">
                  <span className="text-sm text-muted-foreground">Enabled</span>
                  <Badge variant={intg.enabled ? "success" : "secondary"}>{intg.enabled ? "Yes" : "No"}</Badge>
                </div>
                {intg.last_sync_at && (
                  <p className="text-xs text-muted-foreground">Last sync: {new Date(intg.last_sync_at).toLocaleString()}</p>
                )}
                {intg.last_error && <p className="text-xs text-destructive">Error: {intg.last_error}</p>}
                <div className="flex gap-2 pt-2">
                  <Button size="sm" variant="secondary" onClick={() => api.post(`/integrations/${intg.id}/healthcheck`).then(() => refetch())}>
                    Healthcheck
                  </Button>
                  <Button size="sm" onClick={() => api.post(`/integrations/${intg.id}/sync`).then(() => refetch())}>
                    Sync
                  </Button>
                </div>
              </CardContent>
            </Card>
          ))}
          {integrations.length === 0 && (
            <Card>
              <CardContent className="py-8 text-center text-sm text-muted-foreground">
                <Puzzle className="mx-auto mb-2 h-8 w-8" />
                No integrations configured.
              </CardContent>
            </Card>
          )}
        </div>
      )}
    </div>
  );
}
