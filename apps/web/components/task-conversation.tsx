'use client';
import {useState} from 'react';
import {useQuery,useQueryClient} from '@tanstack/react-query';
import {MessageSquare,Send} from '@/components/icons';
import {toast} from 'sonner';
import {api,type Entity} from '@/lib/api';
import {Button} from './ui/button';
export function TaskConversation({taskId,writable}:{taskId:string;writable:boolean}){
 const [text,setText]=useState(''),[busy,setBusy]=useState(false);const client=useQueryClient();
 const rows=useQuery<Entity[]>({queryKey:['comments',taskId],queryFn:()=>api('/resources/comments')});
 const comments=rows.data?.filter(x=>x.data.task_id===taskId&&x.status!=='cancelled')||[];
 async function send(e:React.FormEvent){e.preventDefault();setBusy(true);try{await api('/resources/comments','POST',{title:text.slice(0,190),data:{task_id:taskId,body:text}});setText('');client.invalidateQueries({queryKey:['comments',taskId]})}catch(e){toast.error((e as Error).message)}finally{setBusy(false)}}
 return <section className="task-comments"><h4><MessageSquare size={14}/>Team notes <span>{comments.length}</span></h4>{comments.length?comments.map(c=><article key={c.id}><p>{c.data.body}</p><small>{new Date(c.created_at).toLocaleString()}</small></article>):<p className="muted">No notes yet. Keep the next person in the loop.</p>}{writable&&<form onSubmit={send}><textarea value={text} onChange={e=>setText(e.target.value)} required maxLength={5000} rows={2} aria-label="Task comment" placeholder="Add a note for your team…"/><Button size="sm" disabled={busy}><Send size={13}/>Add note</Button></form>}</section>
}
