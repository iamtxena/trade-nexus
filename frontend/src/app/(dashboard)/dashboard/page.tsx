import { Badge } from '@/components/ui/badge';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import {
  Activity,
  ArrowRight,
  Bot,
  Brain,
  Fingerprint,
  LineChart,
  ShieldCheck,
  TrendingUp,
  Users,
  Wallet,
  Zap,
} from 'lucide-react';
import Link from 'next/link';

const stats = [
  {
    label: 'Active Strategies',
    value: '—',
    change: null,
    icon: LineChart,
    color: 'text-chart-1',
    bgColor: 'bg-chart-1/10',
  },
  {
    label: 'Running Agents',
    value: '—',
    change: null,
    icon: Bot,
    color: 'text-chart-2',
    bgColor: 'bg-chart-2/10',
  },
  {
    label: 'Portfolio Value',
    value: '—',
    change: null,
    icon: Wallet,
    color: 'text-chart-3',
    bgColor: 'bg-chart-3/10',
  },
  {
    label: 'Today P&L',
    value: '—',
    change: null,
    icon: TrendingUp,
    color: 'text-chart-4',
    bgColor: 'bg-chart-4/10',
  },
];

const sections = [
  {
    href: '/strategist',
    title: 'Strategist',
    description:
      'AI-powered strategy generation. Describe your trading thesis and get backtested strategies.',
    icon: Brain,
    status: 'Ready',
    statusColor: 'bg-emerald-500',
  },
  {
    href: '/strategies',
    title: 'Strategies',
    description: 'View, manage, and monitor your trading strategies and their performance.',
    icon: LineChart,
    status: 'Coming Soon',
    statusColor: 'bg-amber-500',
  },
  {
    href: '/validation',
    title: 'Validation',
    description: 'Review canonical validation artifacts, comments, and trader verdicts.',
    icon: ShieldCheck,
    status: 'Ready',
    statusColor: 'bg-emerald-500',
  },
  {
    href: '/shared-validation',
    title: 'Shared Validation',
    description: 'View runs shared to you, then comment or decide based on granted permissions.',
    icon: Users,
    status: 'Ready',
    statusColor: 'bg-emerald-500',
  },
  {
    href: '/bots',
    title: 'Bots',
    description: 'Register runtime bots, generate one-time keys, and rotate/revoke credentials.',
    icon: Fingerprint,
    status: 'Ready',
    statusColor: 'bg-emerald-500',
  },
  {
    href: '/agents',
    title: 'Agents',
    description: 'Autonomous trading agents that execute strategies with risk management.',
    icon: Bot,
    status: 'Coming Soon',
    statusColor: 'bg-amber-500',
  },
  {
    href: '/portfolio',
    title: 'Portfolio',
    description: 'Track your portfolio performance, allocations, and risk metrics.',
    icon: Wallet,
    status: 'Coming Soon',
    statusColor: 'bg-amber-500',
  },
];

export default function DashboardPage() {
  return (
    <div className="space-y-8">
      {/* Header */}
      <div>
        <h1 className="text-2xl font-semibold tracking-tight">Dashboard</h1>
        <p className="mt-1 text-sm text-muted-foreground">Your autonomous trading command center</p>
      </div>

      {/* Stats Grid */}
      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        {stats.map((stat) => (
          <Card key={stat.label} className="border-border/50 py-4">
            <CardContent className="flex items-center gap-4">
              <div
                className={`flex size-10 items-center justify-center rounded-lg ${stat.bgColor}`}
              >
                <stat.icon className={`size-5 ${stat.color}`} />
              </div>
              <div className="min-w-0 flex-1">
                <p className="truncate text-xs text-muted-foreground">{stat.label}</p>
                <p className="text-xl font-semibold tabular-nums">{stat.value}</p>
              </div>
            </CardContent>
          </Card>
        ))}
      </div>

      {/* Quick Actions */}
      <div>
        <div className="mb-4 flex items-center gap-2">
          <Zap className="size-4 text-primary" />
          <h2 className="text-lg font-medium">Quick Actions</h2>
        </div>
        <div className="grid gap-4 sm:grid-cols-2">
          {sections.map((section) => (
            <Link key={section.href} href={section.href} className="group">
              <Card className="border-border/50 transition-all duration-300 hover:border-primary/30 hover:shadow-md hover:shadow-primary/5">
                <CardHeader>
                  <div className="flex items-start justify-between">
                    <div className="flex size-10 items-center justify-center rounded-lg bg-secondary">
                      <section.icon className="size-5 text-foreground/80" />
                    </div>
                    <Badge variant="secondary" className="gap-1.5 text-[11px] font-normal">
                      <span className={`size-1.5 rounded-full ${section.statusColor}`} />
                      {section.status}
                    </Badge>
                  </div>
                  <CardTitle className="flex items-center gap-2 text-base">
                    {section.title}
                    <ArrowRight className="size-3.5 text-muted-foreground opacity-0 transition-all duration-300 group-hover:translate-x-0.5 group-hover:opacity-100" />
                  </CardTitle>
                  <CardDescription>{section.description}</CardDescription>
                </CardHeader>
              </Card>
            </Link>
          ))}
        </div>
      </div>

      {/* System Status */}
      <Card className="border-border/50">
        <CardHeader>
          <CardTitle className="flex items-center gap-2 text-base">
            <Activity className="size-4 text-primary" />
            System Status
          </CardTitle>
        </CardHeader>
        <CardContent>
          <div className="grid gap-3 sm:grid-cols-3">
            {[
              { label: 'Lona Gateway', status: 'Connected', ok: true },
              { label: 'Market Data', status: 'Standby', ok: true },
              { label: 'AI Engine', status: 'Ready', ok: true },
            ].map((service) => (
              <div
                key={service.label}
                className="flex items-center gap-3 rounded-lg bg-secondary/50 px-4 py-3"
              >
                <div
                  className={`size-2 rounded-full ${
                    service.ok ? 'bg-emerald-500' : 'bg-destructive'
                  }`}
                />
                <div>
                  <p className="text-sm font-medium">{service.label}</p>
                  <p className="text-xs text-muted-foreground">{service.status}</p>
                </div>
              </div>
            ))}
          </div>
        </CardContent>
      </Card>
    </div>
  );
}
