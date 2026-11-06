import {Workspace} from '@/components/workspace';
import {notFound} from 'next/navigation';
export default async function Page({params}:{params:Promise<{slug?:string[]}>}){const {slug=[]}=await params;const sections=['command','workflows','agents','rooms','customers','inbox','tasks','calendar','knowledge','approvals','analytics','activity','team','integrations','settings'];if(slug.length&&( !sections.includes(slug[0]) || slug.length>2 || (slug.length===2&&slug[0]!=='workflows')))notFound();return <Workspace/>}
