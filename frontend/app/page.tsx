import { auth } from '@clerk/nextjs/server';
import { redirect } from 'next/navigation';
import Link from 'next/link';
import { SignInButton, SignUpButton } from '@clerk/nextjs';

export default async function LandingPage() {
  const { userId } = await auth();

  if (userId) {
    redirect('/dashboard');
  }

  return (
    <div className="min-h-screen bg-background flex flex-col">
      {/* Nav */}
      <header className="border-b border-[var(--border)] bg-white/80 backdrop-blur-sm sticky top-0 z-50">
        <div className="max-w-6xl mx-auto px-6 h-16 flex items-center justify-between">
          <div className="flex items-center gap-2">
            <div className="w-8 h-8 rounded-lg bg-primary-500 flex items-center justify-center text-white font-bold text-sm">
              S
            </div>
            <span className="font-semibold text-[var(--foreground)]">Solo Agent OS</span>
          </div>
          <div className="flex items-center gap-3">
            <SignInButton mode="modal">
              <button className="text-sm font-medium text-[var(--muted)] hover:text-[var(--foreground)] transition-colors px-4 py-2">
                Sign In
              </button>
            </SignInButton>
            <SignUpButton mode="modal">
              <button className="text-sm font-medium bg-primary-500 text-white px-4 py-2 rounded-lg hover:bg-primary-600 transition-colors">
                Get Started
              </button>
            </SignUpButton>
          </div>
        </div>
      </header>

      {/* Hero */}
      <main className="flex-1">
        <section className="max-w-6xl mx-auto px-6 pt-24 pb-20 text-center">
          <div className="inline-flex items-center gap-2 bg-accent-100 text-accent-700 text-xs font-medium px-3 py-1.5 rounded-full mb-6">
            <span className="w-1.5 h-1.5 rounded-full bg-accent-400 animate-pulse" />
            AI agents working 24/7 for your business
          </div>
          <h1 className="text-5xl md:text-6xl font-bold text-[var(--foreground)] leading-tight mb-6 text-balance">
            You stay the expert.{' '}
            <span className="text-primary-500">Agents handle</span>{' '}
            everything else.
          </h1>
          <p className="text-xl text-[var(--muted)] max-w-2xl mx-auto mb-10 text-balance">
            Solo Agent OS is an autonomous business brain built for solo professionals.
            Your AI team handles leads, research, and marketing — while you focus on closing deals.
          </p>
          <div className="flex flex-col sm:flex-row items-center justify-center gap-4">
            <SignUpButton mode="modal">
              <button className="w-full sm:w-auto bg-primary-500 text-white px-8 py-3.5 rounded-xl font-semibold text-base hover:bg-primary-600 transition-colors shadow-lg shadow-primary-500/20">
                Start Free — No Credit Card Needed
              </button>
            </SignUpButton>
            <SignInButton mode="modal">
              <button className="w-full sm:w-auto border border-[var(--border)] text-[var(--foreground)] px-8 py-3.5 rounded-xl font-semibold text-base hover:bg-[var(--muted-bg)] transition-colors">
                Sign In to Dashboard
              </button>
            </SignInButton>
          </div>
          <p className="text-sm text-[var(--muted)] mt-4">
            Trusted by 500+ solo agents, consultants, and recruiters
          </p>
        </section>

        {/* Feature Cards */}
        <section className="max-w-6xl mx-auto px-6 pb-24">
          <div className="grid md:grid-cols-3 gap-6">
            {/* Card 1 */}
            <div className="bg-white border border-[var(--border)] rounded-2xl p-8 hover:shadow-card-hover transition-shadow">
              <div className="w-12 h-12 rounded-xl bg-primary-50 flex items-center justify-center mb-5">
                <svg className="w-6 h-6 text-primary-500" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                  <path strokeLinecap="round" strokeLinejoin="round" d="M16 7a4 4 0 11-8 0 4 4 0 018 0zM12 14a7 7 0 00-7 7h14a7 7 0 00-7-7z" />
                </svg>
              </div>
              <h3 className="text-lg font-semibold text-[var(--foreground)] mb-2">Front Desk</h3>
              <p className="text-[var(--muted)] text-sm leading-relaxed">
                Never miss an inquiry. Your AI front desk qualifies leads, answers questions,
                and schedules viewings 24/7 — even while you sleep.
              </p>
              <ul className="mt-4 space-y-2">
                {['Instant lead qualification', 'Auto WhatsApp & email replies', 'Viewing scheduler'].map((item) => (
                  <li key={item} className="flex items-center gap-2 text-sm text-[var(--muted)]">
                    <span className="w-1.5 h-1.5 rounded-full bg-accent-400 flex-shrink-0" />
                    {item}
                  </li>
                ))}
              </ul>
            </div>

            {/* Card 2 */}
            <div className="bg-white border border-[var(--border)] rounded-2xl p-8 hover:shadow-card-hover transition-shadow">
              <div className="w-12 h-12 rounded-xl bg-primary-50 flex items-center justify-center mb-5">
                <svg className="w-6 h-6 text-primary-500" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                  <path strokeLinecap="round" strokeLinejoin="round" d="M9.663 17h4.673M12 3v1m6.364 1.636l-.707.707M21 12h-1M4 12H3m3.343-5.657l-.707-.707m2.828 9.9a5 5 0 117.072 0l-.548.547A3.374 3.374 0 0014 18.469V19a2 2 0 11-4 0v-.531c0-.895-.356-1.754-.988-2.386l-.548-.547z" />
                </svg>
              </div>
              <h3 className="text-lg font-semibold text-[var(--foreground)] mb-2">Research</h3>
              <p className="text-[var(--muted)] text-sm leading-relaxed">
                Always market-ready. Your research agent indexes every listing and keeps
                a living knowledge base of market data, comparable properties, and buyer trends.
              </p>
              <ul className="mt-4 space-y-2">
                {['Listing knowledge base', 'Market comparable analysis', 'Buyer profile matching'].map((item) => (
                  <li key={item} className="flex items-center gap-2 text-sm text-[var(--muted)]">
                    <span className="w-1.5 h-1.5 rounded-full bg-accent-400 flex-shrink-0" />
                    {item}
                  </li>
                ))}
              </ul>
            </div>

            {/* Card 3 */}
            <div className="bg-white border border-[var(--border)] rounded-2xl p-8 hover:shadow-card-hover transition-shadow">
              <div className="w-12 h-12 rounded-xl bg-primary-50 flex items-center justify-center mb-5">
                <svg className="w-6 h-6 text-primary-500" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                  <path strokeLinecap="round" strokeLinejoin="round" d="M11 5.882V19.24a1.76 1.76 0 01-3.417.592l-2.147-6.15M18 13a3 3 0 100-6M5.436 13.683A4.001 4.001 0 017 6h1.832c4.1 0 7.625-1.234 9.168-3v14c-1.543-1.766-5.067-3-9.168-3H7a3.988 3.988 0 01-1.564-.317z" />
                </svg>
              </div>
              <h3 className="text-lg font-semibold text-[var(--foreground)] mb-2">Marketing</h3>
              <p className="text-[var(--muted)] text-sm leading-relaxed">
                Auto-generate content. Your marketing agent drafts Instagram captions,
                email campaigns, and WhatsApp broadcasts — you just approve and publish.
              </p>
              <ul className="mt-4 space-y-2">
                {['Instagram & Facebook posts', 'Email drip campaigns', 'WhatsApp broadcasts'].map((item) => (
                  <li key={item} className="flex items-center gap-2 text-sm text-[var(--muted)]">
                    <span className="w-1.5 h-1.5 rounded-full bg-accent-400 flex-shrink-0" />
                    {item}
                  </li>
                ))}
              </ul>
            </div>
          </div>
        </section>

        {/* Social proof */}
        <section className="bg-primary-500 py-20">
          <div className="max-w-6xl mx-auto px-6 text-center">
            <h2 className="text-3xl font-bold text-white mb-4">
              One person. Six AI agents. Unlimited leverage.
            </h2>
            <p className="text-primary-200 max-w-xl mx-auto mb-10">
              Stop being the bottleneck in your own business. Let the agents handle the grind.
            </p>
            <SignUpButton mode="modal">
              <button className="bg-white text-primary-500 px-8 py-3.5 rounded-xl font-semibold hover:bg-primary-50 transition-colors">
                Launch Your Agent OS Today
              </button>
            </SignUpButton>
          </div>
        </section>
      </main>

      {/* Footer */}
      <footer className="border-t border-[var(--border)] bg-white py-8">
        <div className="max-w-6xl mx-auto px-6 flex flex-col sm:flex-row items-center justify-between gap-4">
          <div className="flex items-center gap-2">
            <div className="w-6 h-6 rounded-md bg-primary-500 flex items-center justify-center text-white font-bold text-xs">
              S
            </div>
            <span className="text-sm font-medium text-[var(--foreground)]">Solo Agent OS</span>
          </div>
          <p className="text-sm text-[var(--muted)]">
            © {new Date().getFullYear()} Solo Agent OS. Built for solo professionals.
          </p>
          <div className="flex items-center gap-4 text-sm text-[var(--muted)]">
            <Link href="/privacy" className="hover:text-[var(--foreground)] transition-colors">Privacy</Link>
            <Link href="/terms" className="hover:text-[var(--foreground)] transition-colors">Terms</Link>
          </div>
        </div>
      </footer>
    </div>
  );
}
