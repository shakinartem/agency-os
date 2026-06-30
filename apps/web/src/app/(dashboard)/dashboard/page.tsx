import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Users, MessageSquare, Send, AlertTriangle, CheckCircle, XCircle, HelpCircle } from "lucide-react";

const mockStats = {
  newLeads: 12,
  activeDialogs: 8,
  scheduledPosts: 5,
  errors: 2,
};

const services = [
  { name: "CRM", status: "healthy" },
  { name: "AI Dialogs", status: "healthy" },
  { name: "Content Farm", status: "degraded" },
  { name: "Autoposter", status: "healthy" },
  { name: "Reports", status: "healthy" },
];

const statusIcon: Record<string, React.ReactNode> = {
  healthy: <CheckCircle className="h-4 w-4 text-emerald-600" />,
  degraded: <HelpCircle className="h-4 w-4 text-amber-600" />,
  down: <XCircle className="h-4 w-4 text-red-600" />,
};

export default function DashboardPage() {
  const widgets = [
    { title: "New Leads", value: mockStats.newLeads, icon: Users, color: "text-blue-600" },
    { title: "Active Dialogs", value: mockStats.activeDialogs, icon: MessageSquare, color: "text-violet-600" },
    { title: "Scheduled Posts", value: mockStats.scheduledPosts, icon: Send, color: "text-amber-600" },
    { title: "Errors", value: mockStats.errors, icon: AlertTriangle, color: "text-red-600" },
  ];

  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-bold">Dashboard</h1>

      <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-4">
        {widgets.map((w) => (
          <Card key={w.title}>
            <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
              <CardTitle className="text-sm font-medium">{w.title}</CardTitle>
              <w.icon className={`h-4 w-4 ${w.color}`} />
            </CardHeader>
            <CardContent>
              <div className="text-2xl font-bold">{w.value}</div>
            </CardContent>
          </Card>
        ))}
      </div>

      <Card>
        <CardHeader>
          <CardTitle>Integration Health</CardTitle>
        </CardHeader>
        <CardContent>
          <div className="grid gap-3 md:grid-cols-5">
            {services.map((s) => (
              <div key={s.name} className="flex items-center gap-2 rounded-lg border p-3">
                {statusIcon[s.status] ?? <HelpCircle className="h-4 w-4" />}
                <div>
                  <p className="text-sm font-medium">{s.name}</p>
                  <Badge variant={s.status === "healthy" ? "success" : s.status === "degraded" ? "warning" : "destructive"} className="text-xs">
                    {s.status}
                  </Badge>
                </div>
              </div>
            ))}
          </div>
        </CardContent>
      </Card>
    </div>
  );
}
