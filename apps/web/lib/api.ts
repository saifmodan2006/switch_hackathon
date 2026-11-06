export interface Entity { id:string; title?:string; name?:string; status?:string; created_at:string; updated_at?:string; [key:string]:any }
let csrf = '';
export function setCsrf(value:string) { csrf=value; }
export async function api<T=any>(path:string, method='GET', body?:unknown):Promise<T> {
 const form = body instanceof FormData;
 const response = await fetch('/api/v1'+path,{method,credentials:'include',headers:{...(!form?{'Content-Type':'application/json'}:{}),...(method!=='GET'?{'X-CSRF-Token':csrf}:{})},body:body===undefined?undefined:form?body:JSON.stringify(body)});
 if(!response.ok){ const error=await response.json().catch(()=>({detail:'Service unavailable'})); throw new Error(typeof error.detail==='string'?error.detail:error.detail?.map((x:any)=>x.msg).join(', ')||'Request failed'); }
 return response.json();
}
