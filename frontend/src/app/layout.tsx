import type { Metadata } from 'next';
import './globals.css';
import { AuthProvider } from '@/context/AuthContext';

export const metadata: Metadata = {
  title: 'FORESIGHT AI — Network Attack Forecasting & Threat Intelligence',
  description: 'Autonomous AI-powered Network Attack Forecasting from Real Telemetry Streams',
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en" className="dark scroll-smooth">
      <body className="bg-background text-slate-100 antialiased selection:bg-cyan-500/30 selection:text-cyan-200">
        <AuthProvider>
          {children}
        </AuthProvider>
      </body>
    </html>
  );
}
