"use client";

import { useQuery } from "@tanstack/react-query";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Table, TableHeader, TableBody, TableRow, TableHead, TableCell } from "@/components/ui/table";
import { Badge } from "@/components/ui/badge";
import { BarChart3 } from "lucide-react";
import { api } from "@/lib/api";

interface Snapshot {
  id: string;
  project_id: string;
  period_start: string;
  period_end: string;
  metrics: Record<string, unknown>;
  created_at?: string;
}

export default function ReportsPage() {
  const { data: snapshots = [], isLoading } = useQuery({
    queryKey: ["reports"],
    queryFn: () => api.get<Snapshot[]>("/reports/snapshots"),
  });

  const metricCards = [
    { label: "Total Leads", value: 47, delta: "+12%" },
    { label: "Converted", value: 12, delta: "+5%" },
    { label: "Consultations", value: 23, delta: "+8%" },
    { label: "Publications", value: 31, delta: "+15%" },
  ];

  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-bold">Reports</h1>

      <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-4">
        {metricCards.map((m) => (
          <Card key={m.label}>
            <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
              <CardTitle className="text-sm font-medium">{m.label}</CardTitle>
              <BarChart3 className="h-4 w-4 text-muted-foreground" />
            </CardHeader>
            <CardContent>
              <div className="text-2xl font-bold">{m.value}</div>
              <p className="text-xs text-muted-foreground">{m.delta} vs last period</p>
            </CardContent>
          </Card>
        ))}
      </div>

      <Card>
        <CardHeader>
          <CardTitle>Snapshots</CardTitle>
        </CardHeader>
        <CardContent>
          {isLoading ? (
            <p className="text-sm text-muted-foreground">Loading…</p>
          ) : (
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Period</TableHead>
                  <TableHead>Metrics</TableHead>
                  <TableHead>Created</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {snapshots.map((s) => (
                  <TableRow key={s.id}>
                    <TableCell>{s.period_start} → {s.period_end}</TableCell>
                    <TableCell>
                      <pre className="max-w-md overflow-auto rounded bg-muted p-2 text-xs">{JSON.stringify(s.metrics)}</pre>
                    </TableCell>
                    <TableCell>{s.created_at ? new Date(s.created_at).toLocaleString() : "—"}</TableCell>
                  </TableRow>
                ))}
                {snapshots.length === 0 && (
                  <TableRow>
                    <TableCell colSpan={3} className="text-center text-sm text-muted-foreground">No snapshots.</TableCell>
                  </TableRow>
                )}
              </TableBody>
            </Table>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
