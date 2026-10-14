"""Start disposable browser QA with fake keys and no external integrations."""
import os
import subprocess
from pathlib import Path
import time

root=Path(__file__).resolve().parents[1]
env=os.environ.copy()
for key in ('SUPABASE_DB_URL','THE_ODDS_API_KEY','ESPORTS_API_KEY','OPENROUTER_API_KEY'):env[key]=''
env.update(ADMIN_API_TOKEN='local-qa-only-token-32-characters-long',DASHBOARD_PASSWORD='local-qa-password-only',
    BACKEND_URL='http://127.0.0.1:8001',ENABLE_SCHEDULER='false',NEXT_TELEMETRY_DISABLED='1',
    PYTHONPATH=str(root/'backend'),QA_FIXTURE='true',QA_MATCH_FEED='true',QA_MANUAL_ODDS='true',QA_PERFORMANCE='true')
node=Path(os.environ['USERPROFILE'])/'.cache/codex-runtimes/codex-primary-runtime/dependencies/node/bin/node.exe'
processes=[]
try:
    for command,cwd in [([str(root/'.venv/Scripts/python.exe'),'tests/qa_server.py'],root/'backend'),
        ([str(node),'node_modules/next/dist/bin/next','start','-p','3000','--hostname','127.0.0.1'],root/'frontend')]:
        processes.append(subprocess.Popen(command,cwd=cwd,env=env,creationflags=subprocess.CREATE_NO_WINDOW))
    print('Disposable QA: http://127.0.0.1:3000/ (no live credentials)',flush=True)
    while all(p.poll() is None for p in processes):time.sleep(1)
finally:
    for p in processes:
        if p.poll() is None:p.terminate()
    for p in processes:p.wait(timeout=10)
