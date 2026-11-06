import type {Metadata} from 'next';
import './globals.css';
import './design-system.css';
import {GeistSans} from 'geist/font/sans';
import {Providers} from '@/components/providers';
export const metadata:Metadata={title:'SwitchOps AI · Your business, in sync',description:'Your AI Workforce. Your Team. One Command Center.',openGraph:{title:'SwitchOps AI',description:'Human judgment. Real agent collaboration.',images:['/opengraph-image.svg']},robots:{index:false,follow:false}};
export default function RootLayout({children}:{children:React.ReactNode}){return <html lang="en" className={GeistSans.variable} suppressHydrationWarning><body><a href="#workspace-content" className="skip-link">Skip to content</a><Providers>{children}</Providers></body></html>}
