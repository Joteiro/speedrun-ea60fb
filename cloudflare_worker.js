// ─────────────────────────────────────────────────────────────────────────
// Cloudflare Worker — receptor de Hooksy (reemplaza a Pipedream).
// Recibe el payload de Apple Health, extrae las corridas de Adidas (Runtastic),
// calcula distancia (GPS) y FC media, y dispara un repository_dispatch a GitHub.
//
// Deploy:
//   1. Cloudflare → Workers & Pages → Create → Worker → pegá este código → Deploy.
//   2. Worker → Settings → Variables and Secrets (como "Secret"):
//        GH_DISPATCH_PAT = PAT fine-grained de GitHub (Contents: write, solo el repo)
//        WEBHOOK_SECRET  = una cadena secreta cualquiera (protege el endpoint)
//   3. En Hooksy poné como URL:  https://TU-WORKER.workers.dev/?key=EL_WEBHOOK_SECRET
// ─────────────────────────────────────────────────────────────────────────
const OWNER = "Joteiro";
const REPO = "speedrun-ea60fb";

export default {
  async fetch(request, env) {
    if (request.method !== "POST") {
      return new Response("OK — este endpoint espera POST de Hooksy.", { status: 200 });
    }
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

    // Solo corridas de Adidas Running (Runtastic)
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
      if (distKm < 1) continue; // ignora tests/tramos muy cortos

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
          "User-Agent": "cloudflare-hooksy",
        },
        body: JSON.stringify({ event_type: "nueva_corrida", client_payload: payload }),
      });
      if (!res.ok) {
        error = `GitHub dispatch ${res.status}: ${await res.text()}`;
        console.error(error);
        break;
      }
      enviadas.push(payload);
    }

    // Siempre 200 (para que Hooksy no reintente en loop); el detalle va en el body.
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
  },
};
