import Link from 'next/link';

export default function Home() {
  return (
    <div className="min-h-screen flex flex-col items-center justify-center p-8">
      <main className="flex flex-col items-center gap-8 max-w-2xl text-center">
        <h1 className="text-4xl font-bold tracking-tight sm:text-6xl">Trade Nexus</h1>
        <p className="text-lg text-foreground/70">
          AI orchestrator connecting Lona and Live Engine with ML capabilities for autonomous
          trading.
        </p>
        <div className="flex gap-4">
          <Link
            href="/dashboard"
            className="rounded-full bg-foreground text-background px-6 py-3 text-sm font-medium hover:bg-foreground/90 transition-colors"
          >
            Get Started
          </Link>
          <Link
            href="https://github.com/iamtxena/trade-nexus"
            target="_blank"
            rel="noopener noreferrer"
            className="rounded-full border border-foreground/20 px-6 py-3 text-sm font-medium hover:bg-foreground/5 transition-colors"
          >
            GitHub
          </Link>
        </div>
      </main>
    </div>
  );
}
