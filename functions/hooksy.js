// ─────────────────────────────────────────────────────────────────────────
// Cloudflare Pages Function — endpoint: https://<proyecto>.pages.dev/hooksy
// Se despliega SOLO desde el repo (Cloudflare Pages conectado a GitHub).
// Recibe el payload de Hooksy, extrae las corridas de Adidas (Runtastic),
// calcula distancia (GPS) y FC media, y dispara un repository_dispatch a GitHub.
//
// Variables de entorno a cargar en el proyecto de Pages (Settings → Env vars):
//   GH_DISPATCH_PAT = PAT fine-grained de GitHub (Contents: write, solo este repo)
//   WEBHOOK_SECRET  = cadena secreta (protege el endpoint)
// En Hooksy, URL:  https://<proyecto>.pages.dev/hooksy?key=EL_WEBHOOK_SECRET
// ─────────────────────────────────────────────────────────────────────────
const OWNER = "Joteiro";
const REPO = "speedrun-ea60fb";

export async function onRequestGet() {
  return new Response("OK — endpoint de Hooksy. Usar POST.", { status: 200 });
}

export async function onRequestPost(context) {
  const { request, env } = context;

  // Protección por secreto en la URL (?key=...)
  if (env.WEBHOOK_SECRET) {
    const key = new URL(request.url).searchParams.get("key");
    if (key !== env.WEBHOOK_SECRET) {
      return new Response("forbidden", { status: 403 });
    }
  }

  let body;
  try {
    body = await request.json();
  } catch {
    return new Response("bad json", { status: 400 });
  }

  const data = body?.data || {};
  const sessions = data.exercise_sessions || [];
  const distSamples = data.distance || [];
  const hrSamples = data.heart_rate || [];
  const ms = (s) => new Date(s).getTime();

  const runs = sessions.filter(
    (s) => s.label === "running" && (s.source || "").includes("runtastic")
  );

  const enviadas = [];
  const revisadas = [];
  let error = null;

  for (const s of runs) {
    const a = ms(s.start_time), b = ms(s.end_time);
    const distKm = distSamples
      .filter((x) => (x.source || "").includes("runtastic") &&
                     ms(x.start_time) >= a && ms(x.start_time) <= b)
      .reduce((acc, x) => acc + (x.value || 0), 0);
    const hrs = hrSamples
      .filter((x) => ms(x.start_time) >= a && ms(x.start_time) <= b)
      .map((x) => x.value);
    const fc = hrs.length ? Math.round(hrs.reduce((p, c) => p + c, 0) / hrs.length) : null;

    revisadas.push({ start: s.start_time, distKm: +distKm.toFixed(3), fc });
    if (distKm < 1) continue;

    const payload = {
      date: s.start_time.slice(0, 10),
      dist: +distKm.toFixed(2),
      fc,
      start: s.start_time,
      end: s.end_time,
    };

    const res = await fetch(`https://api.github.com/repos/${OWNER}/${REPO}/dispatches`, {
      method: "POST",
      headers: {
        Authorization: `Bearer ${env.GH_DISPATCH_PAT}`,
        Accept: "application/vnd.github+json",
        "Content-Type": "application/json",
        "User-Agent": "cloudflare-pages-hooksy",
      },
      body: JSON.stringify({ event_type: "nueva_corrida", client_payload: payload }),
    });
    if (!res.ok) {
      error = `GitHub dispatch ${res.status}: ${await res.text()}`;
      break;
    }
    enviadas.push(payload);
  }

  return new Response(
    JSON.stringify({
      corridas_enviadas: enviadas.length,
      enviadas,
      error,
      debug: {
        tiene_token: Boolean(env.GH_DISPATCH_PAT),
        total_sessions: sessions.length,
        running_adidas: runs.length,
        distance_samples: distSamples.length,
        revisadas,
      },
    }, null, 2),
    { status: 200, headers: { "Content-Type": "application/json" } }
  );
}
