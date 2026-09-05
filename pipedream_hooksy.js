// ─────────────────────────────────────────────────────────────────────────
// Pipedream — paso de código Node.js
// Recibe el payload de Hooksy, extrae las corridas de Adidas (Runtastic),
// calcula distancia (GPS) y FC media, y dispara un repository_dispatch a
// GitHub para que el repo las ingeste.
//
// Setup en Pipedream:
//   1. Trigger: "HTTP / Webhook"  ->  "New Requests"  (pegá su URL en Hooksy)
//   2. Env var del proyecto: GH_DISPATCH_PAT = un PAT fine-grained de GitHub
//      con permiso "Contents: Read and write" SOLO sobre el repo speedrun-ea60fb.
//   3. Este código como paso "Run custom code" (Node.js).
// ─────────────────────────────────────────────────────────────────────────
export default defineComponent({
  async run({ steps, $ }) {
    const OWNER = "Joteiro";
    const REPO = "speedrun-ea60fb";

    const body = steps.trigger.event.body || {};
    const data = body.data || {};
    const sessions = data.exercise_sessions || [];
    const distSamples = data.distance || [];
    const hrSamples = data.heart_rate || [];
    const ms = (s) => new Date(s).getTime();

    // Solo corridas de Adidas Running (Runtastic)
    const runs = sessions.filter(
      (s) => s.label === "running" && (s.source || "").includes("runtastic")
    );

    const enviadas = [];
    for (const s of runs) {
      const a = ms(s.start_time);
      const b = ms(s.end_time);

      // Distancia GPS de Adidas dentro de la ventana de la corrida
      const distKm = distSamples
        .filter((x) => (x.source || "").includes("runtastic") &&
                       ms(x.start_time) >= a && ms(x.start_time) <= b)
        .reduce((acc, x) => acc + (x.value || 0), 0);

      if (distKm < 1) continue; // ignora tests/tramos muy cortos

      // FC media (de Oura) dentro de la ventana; si no hay, la rellena el repo
      const hrs = hrSamples
        .filter((x) => ms(x.start_time) >= a && ms(x.start_time) <= b)
        .map((x) => x.value);
      const fc = hrs.length
        ? Math.round(hrs.reduce((p, c) => p + c, 0) / hrs.length)
        : null;

      const payload = {
        date: s.start_time.slice(0, 10),
        dist: +distKm.toFixed(2),
        fc,
        start: s.start_time,
        end: s.end_time,
      };

      const res = await fetch(
        `https://api.github.com/repos/${OWNER}/${REPO}/dispatches`,
        {
          method: "POST",
          headers: {
            Authorization: `Bearer ${process.env.GH_DISPATCH_PAT}`,
            Accept: "application/vnd.github+json",
            "Content-Type": "application/json",
            "User-Agent": "pipedream-hooksy",
          },
          body: JSON.stringify({
            event_type: "nueva_corrida",
            client_payload: payload,
          }),
        }
      );
      if (!res.ok) {
        throw new Error(`GitHub dispatch ${res.status}: ${await res.text()}`);
      }
      enviadas.push(payload);
    }

    return { corridas_enviadas: enviadas.length, enviadas };
  },
});
