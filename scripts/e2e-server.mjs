import {spawn,spawnSync} from 'node:child_process';
import {fileURLToPath} from 'node:url';
import path from 'node:path';
import fs from 'node:fs';
const root=path.resolve(path.dirname(fileURLToPath(import.meta.url)),'..');
fs.mkdirSync(path.join(root,'.data'),{recursive:true});
const python=path.join(root,'.venv',process.platform==='win32'?'Scripts/python.exe':'bin/python');
const env={...process.env,E2E:'1',PYTHONPATH:[path.join(root,'services/api'),path.join(root,'services')].join(path.delimiter),DATABASE_URL:'sqlite+aiosqlite:///./.data/e2e.db',ENVIRONMENT:'test',API_INTERNAL_URL:'http://127.0.0.1:8011',FRONTEND_URL:'http://127.0.0.1:3011',BACKEND_URL:'http://127.0.0.1:8011'};
let migration=spawnSync(python,['-m','alembic','upgrade','head'],{cwd:root,env,stdio:'inherit'});
if(migration.status!==0)process.exit(migration.status||1);
const api=spawn(python,['-m','uvicorn','app.main:app','--host','127.0.0.1','--port','8011'],{cwd:root,env,stdio:'inherit'});
const web=spawn(process.execPath,[path.join(root,'apps/web/node_modules/next/dist/bin/next'),'dev','--port','3011','--hostname','127.0.0.1'],{cwd:path.join(root,'apps/web'),env,stdio:'inherit'});
function stop(){api.kill();web.kill()}
process.on('exit',stop);process.on('SIGTERM',()=>{stop();process.exit()});process.on('SIGINT',()=>{stop();process.exit()});
api.on('exit',code=>{if(code)process.exit(code)});web.on('exit',code=>{if(code)process.exit(code)});
