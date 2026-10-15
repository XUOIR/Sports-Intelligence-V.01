import type { Metadata, Viewport } from 'next';
import './globals.css';
import '@/components/InterfacePolish.css';
export const metadata: Metadata = { title: 'Sports Intelligence | V0.1', description: 'A disciplined workspace for pre-game sports analytics and your wager ledger.', manifest: '/manifest.webmanifest', appleWebApp: { capable: true, title: 'Sports Intelligence', statusBarStyle: 'black-translucent' }, icons: { icon: '/icon.svg', apple: '/icon-192.png' } };
export const viewport: Viewport = { width: 'device-width', initialScale: 1, themeColor: '#000000' };
export default function Layout({ children }: {children: React.ReactNode}) { return <html lang="en"><body>{children}</body></html>; }
