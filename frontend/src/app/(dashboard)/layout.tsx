'use client';

import { Button } from '@/components/ui/button';
import { ScrollArea } from '@/components/ui/scroll-area';
import { Separator } from '@/components/ui/separator';
import { Sheet, SheetContent, SheetTitle, SheetTrigger } from '@/components/ui/sheet';
import { cn } from '@/lib/utils';
import { UserButton } from '@clerk/nextjs';
import {
  Activity,
  Bot,
  Brain,
  LayoutDashboard,
  LineChart,
  Menu,
  ShieldCheck,
  Wallet,
} from 'lucide-react';
import Link from 'next/link';
import { usePathname } from 'next/navigation';
import { useState } from 'react';

const navItems = [
  { href: '/dashboard', label: 'Dashboard', icon: LayoutDashboard },
  { href: '/strategist', label: 'Strategist', icon: Brain },
  { href: '/strategies', label: 'Strategies', icon: LineChart },
  { href: '/validation', label: 'Validation', icon: ShieldCheck },
  { href: '/agents', label: 'Agents', icon: Bot },
  { href: '/portfolio', label: 'Portfolio', icon: Wallet },
];

function SidebarContent({ pathname }: { pathname: string }) {
  return (
    <div className="flex h-full flex-col">
      {/* Logo */}
      <div className="flex items-center gap-3 px-5 py-6">
        <div className="flex size-9 items-center justify-center rounded-lg bg-primary/15">
          <Activity className="size-5 text-primary" />
        </div>
        <div>
          <h1 className="text-base font-semibold tracking-tight">Trade Nexus</h1>
          <p className="text-[11px] text-muted-foreground">Autonomous Trading</p>
        </div>
      </div>

      <Separator className="bg-sidebar-border" />

      {/* Navigation */}
      <ScrollArea className="flex-1 px-3 py-4">
        <nav className="flex flex-col gap-1">
          {navItems.map((item) => {
            const isActive = pathname === item.href;
            return (
              <Link
                key={item.href}
                href={item.href}
                className={cn(
                  'group flex items-center gap-3 rounded-lg px-3 py-2.5 text-sm font-medium transition-all duration-200',
                  isActive
                    ? 'bg-sidebar-accent text-sidebar-accent-foreground shadow-sm'
                    : 'text-muted-foreground hover:bg-sidebar-accent/50 hover:text-sidebar-foreground',
                )}
              >
                <item.icon
                  className={cn(
                    'size-[18px] shrink-0 transition-colors duration-200',
                    isActive
                      ? 'text-primary'
                      : 'text-muted-foreground group-hover:text-sidebar-foreground',
                  )}
                />
                {item.label}
              </Link>
            );
          })}
        </nav>
      </ScrollArea>

      {/* Footer */}
      <Separator className="bg-sidebar-border" />
      <div className="flex items-center gap-3 px-5 py-4">
        <div className="flex size-2 rounded-full bg-emerald-500 animate-pulse" />
        <span className="text-xs text-muted-foreground">System Online</span>
      </div>
    </div>
  );
}

export default function DashboardLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  const pathname = usePathname();
  const [mobileOpen, setMobileOpen] = useState(false);

  return (
    <div className="flex h-dvh overflow-hidden bg-background">
      {/* Desktop Sidebar */}
      <aside className="hidden w-60 shrink-0 border-r border-sidebar-border bg-sidebar md:flex md:flex-col">
        <SidebarContent pathname={pathname} />
      </aside>

      {/* Mobile Sidebar */}
      <Sheet open={mobileOpen} onOpenChange={setMobileOpen}>
        <div className="flex flex-1 flex-col overflow-hidden">
          {/* Top Header */}
          <header className="flex h-14 items-center justify-between border-b border-border bg-background/80 px-4 backdrop-blur-sm md:px-6">
            <div className="flex items-center gap-3">
              <SheetTrigger asChild>
                <Button variant="ghost" size="icon" className="md:hidden" aria-label="Open menu">
                  <Menu className="size-5" />
                </Button>
              </SheetTrigger>
              <span className="text-sm font-medium text-muted-foreground md:hidden">
                Trade Nexus
              </span>
            </div>

            <div className="flex items-center gap-3">
              <div className="hidden items-center gap-2 rounded-full bg-secondary px-3 py-1.5 md:flex">
                <div className="size-1.5 rounded-full bg-emerald-500" />
                <span className="text-xs text-muted-foreground">Live</span>
              </div>
              <UserButton
                afterSignOutUrl="/"
                appearance={{
                  elements: {
                    avatarBox: 'size-8',
                  },
                }}
              />
            </div>
          </header>

          {/* Main Content */}
          <main className="flex-1 overflow-y-auto">
            <div className="mx-auto max-w-7xl p-4 md:p-6">{children}</div>
          </main>
        </div>

        <SheetContent side="left" className="w-60 bg-sidebar p-0 border-sidebar-border">
          <SheetTitle className="sr-only">Navigation</SheetTitle>
          <SidebarContent pathname={pathname} />
        </SheetContent>
      </Sheet>
    </div>
  );
}
