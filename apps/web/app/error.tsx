'use client';
export default function Error({reset}:{reset:()=>void}) {return <main className="fatal"><h1>Something interrupted your workspace.</h1><p>Your saved records are safe. Reload the view to reconnect.</p><button onClick={reset}>Try again</button></main>}
