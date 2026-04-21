'use client';

import Link from 'next/link';
import { usePathname } from 'next/navigation';
import { useEffect } from 'react';

const NAV = [
  { label: 'Top Deals', href: '/dashboard' },
  { label: 'Pipeline', href: '/dashboard/pipeline' },
  { label: 'Buyers', href: '/dashboard/buyers' },
  { label: 'AMARA', href: '/' },
];

export default function DashboardLayout({ children }: { children: React.ReactNode }) {
  const pathname = usePathname();

  useEffect(() => {
    document.body.classList.add('dashboard-page');
    return () => document.body.classList.remove('dashboard-page');
  }, []);

  return (
    <div className="min-h-screen bg-zinc-950 text-zinc-100 flex flex-col">
      {/* Header */}
      <header className="border-b border-zinc-800 px-6 py-3 flex items-center justify-between">
        <div className="flex items-center gap-3">
          <span className="text-lg font-bold tracking-widest text-cyan-400">AMARA-AI</span>
          <span className="text-xs text-zinc-500 uppercase tracking-widest">Real Estate Intelligence</span>
        </div>
        <nav className="flex gap-1">
          {NAV.map(({ label, href }) => {
            const active = href === '/dashboard'
              ? pathname === '/dashboard'
              : pathname.startsWith(href);
            return (
              <Link
                key={href}
                href={href}
                className={`px-4 py-1.5 rounded text-sm transition-colors ${
                  active
                    ? 'bg-cyan-500/20 text-cyan-400 border border-cyan-500/40'
                    : 'text-zinc-400 hover:text-zinc-100 hover:bg-zinc-800'
                }`}
              >
                {label}
              </Link>
            );
          })}
        </nav>
      </header>

      <main className="flex-1 p-6">{children}</main>
    </div>
  );
}
