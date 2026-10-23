import sys, time, json
from pathlib import Path
import httpx

API = "http://127.0.0.1:8000/api"
ref_audio = Path(sys.argv[1])
c = httpx.Client(timeout=900.0)


def step(name, method, url, **kw):
    t = time.time()
    r = c.request(method, API + url, **kw)
    ok = r.status_code < 400
    print(f"[{'OK ' if ok else 'ERR'}] {name:28} {time.time()-t:6.1f}s  {r.status_code}", flush=True)
    if not ok:
        print("      ", r.text[:800], flush=True)
        sys.exit(1)
    return r.json()


proj = step("create project", "POST", "/projects", json={"project_title": "e2e octopus"})
pid = proj["project"]["project_id"]
print("project:", pid, flush=True)
P = f"/projects/{pid}"
with ref_audio.open("rb") as f:
    step("upload reference audio", "POST", P + "/reference/audio/upload", files={"file": ("reference_audio.wav", f, "audio/wav")})
step("reference STT", "POST", P + "/reference/stt")
step("reference analysis", "POST", P + "/reference/analyze")
cands = step("script candidates", "POST", P + "/scripts/candidates", json={})
items = cands.get("candidates") or cands.get("script_candidates") or []
cid = items[0].get("candidate_id") or items[0].get("id")
step("select candidate", "POST", P + "/scripts/select", json={"candidate_id": cid})
step("finalize script", "POST", P + "/scripts/finalize", json={})
step("TTS", "POST", P + "/production/tts")
step("concepts + scenes", "POST", P + "/production/concepts")
state = step("stock images (all)", "POST", P + "/production/scenes/images", params={"model": "stock"})
scenes = state["video_scenes"]
print("scenes:", len(scenes), flush=True)
for sc in scenes:
    step(f"kenburns video scene {sc['scene_id']}", "POST", P + f"/production/scenes/{sc['scene_id']}/video",
         params={"model": "kenburns", "duration": 5})
step("render", "POST", P + "/production/render", json={})
print("DONE", pid)
