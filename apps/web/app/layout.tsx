import type {Metadata} from 'next';
import './globals.css';
import {Providers} from '@/components/providers';
export const metadata:Metadata={title:'SwitchOps AI · Your business, in sync',description:'Your AI Workforce. Your Team. One Command Center.'};
export default function RootLayout({children}:{children:React.ReactNode}){return <html lang="en" suppressHydrationWarning><body><Providers>{children}</Providers></body></html>}
