"use client";

import { useQuery } from "@tanstack/react-query";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Table, TableHeader, TableBody, TableRow, TableHead, TableCell } from "@/components/ui/table";
import { Badge } from "@/components/ui/badge";
import { MessageSquare } from "lucide-react";
import { api } from "@/lib/api";

interface Conversation {
  id: string;
  lead_id: string;
  source: string;
  status: string;
  last_message?: string;
  ai_summary?: string;
  created_at?: string;
}

export default function DialogsPage() {
  const { data: conversations = [], isLoading } = useQuery({
    queryKey: ["conversations"],
    queryFn: () => api.get<Conversation[]>("/conversations"),
  });

  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-bold">AI Dialogs</h1>

      <Card>
        <CardHeader>
          <CardTitle>Conversations</CardTitle>
        </CardHeader>
        <CardContent>
          {isLoading ? (
            <p className="text-sm text-muted-foreground">Loading…</p>
          ) : (
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>ID</TableHead>
                  <TableHead>Lead</TableHead>
                  <TableHead>Source</TableHead>
                  <TableHead>Status</TableHead>
                  <TableHead>Last message</TableHead>
                  <TableHead>Intent</TableHead>
                  <TableHead>Created</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {conversations.map((c) => (
                  <TableRow key={c.id}>
                    <TableCell className="font-mono text-xs">{c.id}</TableCell>
                    <TableCell>{c.lead_id}</TableCell>
                    <TableCell>{c.source}</TableCell>
                    <TableCell><Badge>{c.status}</Badge></TableCell>
                    <TableCell className="max-w-[200px] truncate">{c.last_message ?? "—"}</TableCell>
                    <TableCell>{c.ai_summary ?? "—"}</TableCell>
                    <TableCell>{c.created_at ? new Date(c.created_at).toLocaleDateString() : "—"}</TableCell>
                  </TableRow>
                ))}
                {conversations.length === 0 && (
                  <TableRow>
                    <TableCell colSpan={7} className="text-center text-sm text-muted-foreground">No conversations.</TableCell>
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
