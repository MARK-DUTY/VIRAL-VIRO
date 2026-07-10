// ViroFeed AI Personal - logica de la interfaz (flujo en 2 pasos)

const $ = (id) => document.getElementById(id);

const formCard = $("form-card");
const progressCard = $("progress-card");
const draftCard = $("draft-card");
const reviewCard = $("review-card");
const resultCard = $("result-card");
const errorCard = $("error-card");

const generateBtn = $("generate-btn");
const assembleBtn = $("assemble-btn");
const progressFill = $("progress-fill");
const progressMsg = $("progress-msg");
const progressTitle = $("progress-title");

let pollTimer = null;
let currentJob = null;       // job_id actual
let imageSourceChosen = "hybrid";
let activeTab = "url";        // "url" | "story"
let currentSceneCount = 0;    // cuantas escenas hay ahora (para "agregar escena")
const attempts = {};          // cuenta de regeneraciones por escena

function show(card) {
  [formCard, progressCard, draftCard, reviewCard, resultCard, errorCard].forEach((c) => c.classList.add("hidden"));
  card.classList.remove("hidden");
}

// ----------------------------------------------------------------------
//  Pestanas: Noticia (URL) / Mi historia
// ----------------------------------------------------------------------
function switchTab(tab) {
  activeTab = tab;
  $("tab-btn-url").classList.toggle("active", tab === "url");
  $("tab-btn-story").classList.toggle("active", tab === "story");
  $("tab-btn-youtube").classList.toggle("active", tab === "youtube");
  $("tab-url").classList.toggle("hidden", tab !== "url");
  $("tab-story").classList.toggle("hidden", tab !== "story");
  $("tab-youtube").classList.toggle("hidden", tab !== "youtube");
  // El estilo de guion aplica a Noticia y a YouTube (no al modo Historia)
  $("style-field").style.display = tab === "story" ? "none" : "";
  // El boton cambia segun el modo
  generateBtn.textContent = tab === "story" ? "✍️ Generar guion y prompts" : "🎬 Preparar video";
}

function setProgress(pct, msg) {
  progressFill.style.width = (pct || 0) + "%";
  if (msg) progressMsg.textContent = msg;
}

// Opciones compartidas (duracion, voz, subtitulos, etc.) para ambos modos
function sharedOptions() {
  imageSourceChosen = $("image_source").value;
  // El menu unico "media_plan" trae tipo + cantidad junto, ej: "video:12".
  // Lo separamos en media_type ("image"|"video"|"mixed") y n_images ("auto"|numero).
  const planRaw = $("media_plan") ? $("media_plan").value : "image:auto";
  const [planType, planCount] = planRaw.split(":");
  const opts = {
    duration: $("duration").value,
    n_images: planCount || "auto",
    media_type: planType || "image",
    aspect: $("aspect") ? $("aspect").value : "9:16",
    style: $("style").value,
    voice: $("voice").value,
    subtitle_color: $("subtitle_color").value,
    subtitle_position: $("subtitle_position").value,
    image_source: imageSourceChosen,
    cta: $("cta").value,
    use_avatar: $("use_avatar").checked,
  };

  // --- Avatar / estilo / podcast ---
  const podcast = $("podcast-toggle") && $("podcast-toggle").checked;
  if (podcast) {
    opts.podcast = true;
    opts.avatar_a_id = $("avatar-a-select") ? $("avatar-a-select").value : "";
    opts.avatar_b_id = $("avatar-b-select") ? $("avatar-b-select").value : "";
    opts.voice_a = $("voice-a") ? $("voice-a").value : "";
    opts.voice_b = $("voice-b") ? $("voice-b").value : "";
  } else {
    opts.avatar_id = $("avatar-select") ? $("avatar-select").value : "";
    opts.style_key = $("style-key") ? $("style-key").value : "";
  }
  return opts;
}

// Muestra un aviso cuando el usuario elige un video largo (2 min o mas),
// porque en su PC (sin tarjeta grafica) tardara varios minutos en armarse.
function refreshLongVideoWarning() {
  const warn = $("long-video-warning");
  if (!warn) return;
  const secs = parseInt($("duration").value, 10) || 0;
  warn.classList.toggle("hidden", secs < 120);
}

// El boton principal decide segun la pestana activa
function onGenerate() {
  if (activeTab === "story") {
    startDraft();
  } else if (activeTab === "youtube") {
    startYoutube();
  } else {
    startPrepare();
  }
}

// Convierte el texto de un campo (con un enlace por renglon) en una lista limpia
function parseLinks(value) {
  return (value || "")
    .split(/[\r\n]+/)
    .map((s) => s.trim())
    .filter((s) => s.length > 0);
}

// ----------------------------------------------------------------------
//  PASO 1 (URL): preparar
// ----------------------------------------------------------------------
async function startPrepare() {
  const urls = parseLinks($("url").value);
  if (urls.length === 0) {
    alert("Pega la URL de una noticia primero.");
    return;
  }

  const payload = { urls, url: urls.join("\n"), ...sharedOptions() };

  generateBtn.disabled = true;
  progressTitle.textContent = urls.length > 1 ? "Leyendo las noticias..." : "Preparando tu video...";
  show(progressCard);
  setProgress(3, "Iniciando...");

  try {
    const resp = await fetch("/api/prepare", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
    const data = await resp.json();
    if (!resp.ok) { showError(data.error || "Error desconocido"); return; }
    currentJob = data.job_id;
    pollStatus();
  } catch (e) {
    showError("No pude contactar al programa. ¿Sigue abierta la ventana negra?\n" + e);
  }
}

// ----------------------------------------------------------------------
//  PASO 1 (YOUTUBE): preparar desde un link de video de YouTube
// ----------------------------------------------------------------------
async function startYoutube() {
  const urls = parseLinks($("youtube_url").value);
  if (urls.length === 0) {
    alert("Pega el enlace de un video de YouTube primero.");
    return;
  }

  const payload = { urls, url: urls.join("\n"), ...sharedOptions() };

  generateBtn.disabled = true;
  progressTitle.textContent = urls.length > 1 ? "Leyendo los videos de YouTube..." : "Leyendo el video de YouTube...";
  show(progressCard);
  setProgress(3, "Iniciando...");

  try {
    const resp = await fetch("/api/prepare_youtube", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
    const data = await resp.json();
    if (!resp.ok) { showError(data.error || "Error desconocido"); return; }
    currentJob = data.job_id;
    pollStatus();
  } catch (e) {
    showError("No pude contactar al programa. ¿Sigue abierta la ventana negra?\n" + e);
  }
}
async function startDraft() {
  const story = $("story").value.trim();
  if (story.length < 30) {
    alert("Escribe tu historia con un poco mas de detalle (al menos unas frases).");
    return;
  }

  const payload = {
    story,
    ...sharedOptions(),
  };

  generateBtn.disabled = true;
  progressTitle.textContent = "Escribiendo el guion y los prompts...";
  show(progressCard);
  setProgress(5, "Iniciando...");

  try {
    const resp = await fetch("/api/draft_story", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
    const data = await resp.json();
    if (!resp.ok) { showError(data.error || "Error desconocido"); return; }
    currentJob = data.job_id;
    pollStatus();
  } catch (e) {
    showError("No pude contactar al programa. ¿Sigue abierta la ventana negra?\n" + e);
  }
}

// ----------------------------------------------------------------------
//  Sondeo de estado (sirve para preparar y para ensamblar)
// ----------------------------------------------------------------------
function pollStatus() {
  if (pollTimer) clearInterval(pollTimer);
  pollTimer = setInterval(async () => {
    try {
      const resp = await fetch(`/api/status/${currentJob}`);
      const job = await resp.json();
      setProgress(job.percent, job.message);

      if (job.status === "error") {
        clearInterval(pollTimer);
        showError(job.error || "Error durante el proceso");
        return;
      }
      if (job.phase === "draft" && job.status === "draft_ready") {
        clearInterval(pollTimer);
        renderDraft(job.draft);
        return;
      }
      if (job.phase === "review" && job.status === "ready") {
        clearInterval(pollTimer);
        renderReview(job.review);
        return;
      }
      if (job.phase === "done" && job.status === "done") {
        clearInterval(pollTimer);
        showResult(job.result);
        return;
      }
    } catch (e) {
      clearInterval(pollTimer);
      showError("Se perdio la conexion con el programa.\n" + e);
    }
  }, 1500);
}

// ----------------------------------------------------------------------
//  MODO HISTORIA - Pantalla de borrador (guion + prompts editables)
// ----------------------------------------------------------------------
function renderDraft(draft) {
  generateBtn.disabled = false;
  showWarning("draft-warning", draft.warning);
  const grid = $("draft-grid");
  grid.innerHTML = "";

  draft.scenes.forEach((scene) => {
    const card = document.createElement("div");
    card.className = "draft-scene";
    card.innerHTML = `
      <div class="draft-head">
        <span class="draft-num">Escena ${scene.index + 1}</span>
        <span class="scene-saved hidden" id="dsaved-${scene.index}">✔ Guardado</span>
      </div>
      <label class="scene-label">🎬 Diálogo (lo que se narra)</label>
      <textarea class="scene-dialogue" id="dtext-${scene.index}" rows="2">${escapeHtml(scene.text)}</textarea>
      <label class="scene-label">🖼️ Prompt de la imagen (en inglés)</label>
      <textarea class="scene-prompt" id="dprompt-${scene.index}" rows="3" spellcheck="false">${escapeHtml(scene.image_prompt)}</textarea>
    `;
    grid.appendChild(card);
  });

  // Guardar automaticamente cuando el usuario termina de editar
  grid.querySelectorAll(".scene-dialogue, .scene-prompt").forEach((ta) => {
    const i = parseInt(ta.id.split("-")[1], 10);
    ta.addEventListener("change", () => saveDraftScene(i));
  });

  show(draftCard);
}

async function saveDraftScene(i) {
  const text = $(`dtext-${i}`).value.trim();
  const prompt = $(`dprompt-${i}`).value.trim();
  if (!prompt) { alert("La descripción de la imagen no puede quedar vacía."); return; }
  try {
    const resp = await fetch("/api/update_prompt", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ job_id: currentJob, index: i, prompt, text }),
    });
    const data = await resp.json();
    if (!resp.ok) { alert(data.error || "No se pudo guardar"); return; }
    const saved = $(`dsaved-${i}`);
    if (saved) {
      saved.classList.remove("hidden");
      setTimeout(() => saved.classList.add("hidden"), 1500);
    }
  } catch (e) {
    alert("Error al guardar: " + e);
  }
}

// Aprobar el borrador -> generar voz + imagenes
async function generateFromDraft() {
  progressTitle.textContent = "Generando voz e imágenes...";
  show(progressCard);
  setProgress(5, "Iniciando...");
  try {
    const resp = await fetch("/api/generate_from_draft", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ job_id: currentJob }),
    });
    const data = await resp.json();
    if (!resp.ok) { showError(data.error || "Error al generar"); return; }
    pollStatus();
  } catch (e) {
    showError("No pude contactar al programa.\n" + e);
  }
}

// ----------------------------------------------------------------------
//  Pantalla de revision de imagenes
// ----------------------------------------------------------------------
function imgUrl(file) {
  return `/preview/${currentJob}/${encodeURIComponent(file)}?t=${Date.now()}`;
}

function renderReview(review) {
  generateBtn.disabled = false;
  showWarning("review-warning", review.warning);
  currentSceneCount = review.scenes.length;   // para el selector de "agregar escena"
  resetAddSceneForm();
  const grid = $("scenes-grid");
  grid.innerHTML = "";

  // Inicializar los controles de voz y avatar segun el estado actual del trabajo
  if ($("review-avatar")) $("review-avatar").checked = !!review.use_avatar;
  if ($("review-voice")) $("review-voice").value = "";  // por defecto: mantener la voz actual

  review.scenes.forEach((scene) => {
    const card = document.createElement("div");
    card.className = "scene-card";
    card.id = `scene-${scene.index}`;

    const isVid = !!scene.is_video;
    // Vista previa: <video> si la escena es un videoclip, si no <img>.
    const mediaEl = isVid
      ? `<video class="scene-img" id="img-${scene.index}" src="${imgUrl(scene.image_file)}" muted loop autoplay playsinline></video>`
      : `<img class="scene-img" id="img-${scene.index}" src="${imgUrl(scene.image_file)}" alt="escena ${scene.index + 1}">`;

    // Cuanto durara esta escena en el video (para que el usuario lo sepa).
    const durTxt = scene.duration ? `⏱️ ~${scene.duration}s` : "";
    // Etiqueta de quien habla (modo podcast).
    const speakerTxt = scene.speaker_name ? ` · 🎙️ ${escapeHtml(scene.speaker_name)}` : "";

    // Bloque "usar audio de mi video" (solo si la escena es un video).
    const ownAudioBlock = scene.can_own_audio ? `
      <div class="own-audio-box" id="ownaudio-${scene.index}">
        <label class="own-audio-toggle">
          <input type="checkbox" id="ownaudio-chk-${scene.index}" ${scene.use_own_audio ? "checked" : ""}>
          <span>🎧 Usar el <strong>audio de mi video</strong> en esta escena (el avatar NO habla aquí)</span>
        </label>
        <div class="own-audio-extra ${scene.use_own_audio ? "" : "hidden"}" id="ownaudio-extra-${scene.index}">
          <span class="own-audio-dur" id="ownaudio-dur-${scene.index}">Esta escena durará lo que dure tu video${scene.own_audio_duration ? ` (~${scene.own_audio_duration}s)` : ""}.</span>
          <label class="own-audio-vol">
            <span>Volumen de tu video: <strong id="ownaudio-vollbl-${scene.index}">${Math.round((scene.own_audio_volume || 1) * 100)}%</strong></span>
            <input type="range" min="0" max="150" value="${Math.round((scene.own_audio_volume || 1) * 100)}" id="ownaudio-vol-${scene.index}">
          </label>
        </div>
      </div>` : "";

    // Bloque "recortar video" (solo si la escena es un video): dos barritas,
    // inicio y fin, para quedarse solo con un trozo del clip.
    const trimMax = (scene.media_duration && scene.media_duration > 0) ? scene.media_duration : 30;
    const tStart = scene.trim_start || 0;
    const tEnd = (scene.trim_end && scene.trim_end > 0) ? scene.trim_end : trimMax;
    const trimBlock = isVid ? `
      <div class="trim-box" id="trim-${scene.index}">
        <div class="trim-head">✂️ Recortar video (deja solo el trozo que quieres)</div>
        <label class="trim-row">
          <span>Inicio: <strong id="trim-slbl-${scene.index}">${tStart.toFixed(1)}s</strong></span>
          <input type="range" min="0" max="${trimMax}" step="0.1" value="${tStart}" id="trim-start-${scene.index}">
        </label>
        <label class="trim-row">
          <span>Fin: <strong id="trim-elbl-${scene.index}">${tEnd.toFixed(1)}s</strong></span>
          <input type="range" min="0" max="${trimMax}" step="0.1" value="${tEnd}" id="trim-end-${scene.index}">
        </label>
        <div class="trim-actions">
          <button class="btn-mini" data-trimapply="${scene.index}">✂️ Aplicar recorte</button>
          <button class="btn-mini" data-trimreset="${scene.index}">↺ Video completo</button>
          <span class="trim-status" id="trim-status-${scene.index}"></span>
        </div>
      </div>` : "";

    // Bloque "línea de tiempo de la escena": los pedazos que se muestran uno
    // tras otro (ej: 4s video + 2s meme + 2s foto). Cada pedazo se ve/reproduce
    // aquí mismo (los videos con su recorte), y se puede ajustar y reordenar.
    const hasClips = scene.clips && scene.clips.length;
    const sceneDur = scene.duration ? scene.duration : "?";
    let clipsBlock;
    if (hasClips) {
      const totalSecs = scene.clips.reduce((a, c) => a + (parseFloat(c.seconds) || 0), 0) || 1;
      const bar = scene.clips.map((c) => {
        const pct = (((parseFloat(c.seconds) || 0) / totalSecs) * 100).toFixed(1);
        return `<div class="tl-seg" style="width:${pct}%">${c.is_video ? "🎞️" : "🖼️"} ${c.seconds}s</div>`;
      }).join("");
      const cards = scene.clips.map((c, k) => {
        const prev = c.is_video
          ? `<video class="clip-prev" data-tstart="${c.trim_start || 0}" data-tend="${c.trim_end || 0}" src="${imgUrl(c.file)}" muted playsinline loop autoplay></video>`
          : `<img class="clip-prev" src="${imgUrl(c.file)}" alt="pedazo ${k + 1}">`;
        const cmax = (c.media_duration && c.media_duration > 0) ? c.media_duration : 30;
        const cts = c.trim_start || 0;
        const cte = (c.trim_end && c.trim_end > 0) ? c.trim_end : cmax;
        const trimC = c.is_video ? `
          <div class="clip-trim">
            <label>Del <strong id="ctlbl-s-${scene.index}-${k}">${cts.toFixed(1)}s</strong>
              <input type="range" min="0" max="${cmax}" step="0.1" value="${cts}" id="cts-${scene.index}-${k}"></label>
            <label>al <strong id="ctlbl-e-${scene.index}-${k}">${cte.toFixed(1)}s</strong>
              <input type="range" min="0" max="${cmax}" step="0.1" value="${cte}" id="cte-${scene.index}-${k}"></label>
            <button class="btn-mini" data-cliptrim="${scene.index}-${k}">✂️ Aplicar y ver recorte</button>
          </div>` : "";
        return `
          <div class="clip-card">
            <div class="clip-prev-wrap"><span class="clip-badge">${k + 1}</span>${prev}</div>
            <label class="clip-secs">dura <input type="number" min="0.3" step="0.5" value="${c.seconds}" id="clipsec-${scene.index}-${k}" class="clip-secinput"> s</label>
            ${trimC}
            <div class="clip-card-actions">
              <button class="btn-mini" data-clipleft="${scene.index}-${k}" title="Mover a la izquierda">◀</button>
              <button class="btn-mini" data-clipright="${scene.index}-${k}" title="Mover a la derecha">▶</button>
              <button class="btn-mini btn-danger" data-clipdel="${scene.index}-${k}">🗑️</button>
            </div>
          </div>`;
      }).join("");
      clipsBlock = `
        <div class="clips-box">
          <div class="clips-head">🎞️ Línea de tiempo de la escena · dura ~${sceneDur}s</div>
          <div class="tl-bar">${bar}</div>
          <div class="clip-cards">${cards}</div>
          <p class="clips-hint">Los segundos son aprox.: se reparten dentro del tiempo de la escena. Cada video se ve <strong>recortado</strong> en su preview.</p>
          <div class="clips-actions">
            <input type="file" accept="image/*,video/*" class="hidden" id="clipfile-${scene.index}">
            <button class="btn-mini" data-clipadd="${scene.index}">➕ Agregar pedazo</button>
            <span class="clip-status" id="clipstatus-${scene.index}"></span>
          </div>
        </div>`;
    } else {
      clipsBlock = `
        <div class="clips-box">
          <div class="clips-head">🎞️ Partir esta escena en pedazos (opcional) · dura ~${sceneDur}s</div>
          <p class="clips-hint">Ahorita esta escena muestra un solo fondo. Agrega pedazos para partirla: ej. 4s video + 2s meme + 2s foto. Cada uno lo verás y podrás recortarlo aquí mismo.</p>
          <div class="clips-actions">
            <input type="file" accept="image/*,video/*" class="hidden" id="clipfile-${scene.index}">
            <button class="btn-mini" data-clipadd="${scene.index}">➕ Agregar pedazo</button>
            <span class="clip-status" id="clipstatus-${scene.index}"></span>
          </div>
        </div>`;
    }

    // Todas las escenas tienen las MISMAS opciones, asi puedes cambiar
    // libremente cualquier escena entre foto y video.
    card.innerHTML = `
      <div class="scene-img-wrap">
        ${mediaEl}
        <span class="scene-badge" id="badge-${scene.index}">${scene.source}</span>
        <span class="scene-dur" id="dur-${scene.index}">${durTxt}</span>
        <div class="scene-loading hidden" id="loading-${scene.index}">Generando...</div>
      </div>
      <label class="scene-label">🎬 Escena ${scene.index + 1}${speakerTxt} · Diálogo (lo que se narra)</label>
      <textarea class="scene-dialogue" id="dialogue-${scene.index}" rows="3"
        title="Edita lo que se dice en esta escena">${escapeHtml(scene.text)}</textarea>
      <div class="scene-play-row">
        <button class="btn-mini btn-play" data-act="play" data-i="${scene.index}">▶️ Escuchar esta escena</button>
        <span class="scene-play-status" id="playstatus-${scene.index}"></span>
        <audio id="playaudio-${scene.index}" preload="none"></audio>
      </div>
      ${ownAudioBlock}
      ${trimBlock}
      ${clipsBlock}
      <span class="scene-saved hidden" id="saved-${scene.index}">✔ Guardado</span>
      <label class="scene-label">🔎 Descripción (en inglés) · para imagen IA o para buscar foto/video</label>
      <textarea class="scene-prompt" id="prompt-${scene.index}" rows="2" spellcheck="false"
        title="Describe lo que quieres (en inglés).">${escapeHtml(scene.image_prompt)}</textarea>
      <div class="scene-actions">
        <button class="btn-mini btn-ai" data-act="ai" data-i="${scene.index}">🎨 Imagen con IA</button>
        <button class="btn-mini" data-act="stock" data-i="${scene.index}">🖼️ Otra foto real</button>
        <button class="btn-mini" data-act="video" data-i="${scene.index}">🎞️ Otro video real</button>
        <button class="btn-mini" data-act="upload" data-i="${scene.index}">⬆️ Subir foto/video</button>
        <button class="btn-mini btn-danger" data-act="delete" data-i="${scene.index}">🗑️ Eliminar</button>
      </div>
      <div class="paste-zone" data-i="${scene.index}" tabindex="0" title="Haz clic aquí y pega (Ctrl+V) una imagen o video del portapapeles">
        📋 Pegar imagen/video (Ctrl+V)
      </div>
      <input type="file" accept="image/*,video/*" class="hidden" id="file-${scene.index}">
    `;
    grid.appendChild(card);
  });

  // Conectar botones
  grid.querySelectorAll(".btn-mini").forEach((btn) => {
    const i = parseInt(btn.dataset.i, 10);
    const act = btn.dataset.act;
    if (act === "ai") {
      btn.addEventListener("click", () => regenerate(i, "ai"));
    } else if (act === "stock") {
      btn.addEventListener("click", () => regenerate(i, "stock"));
    } else if (act === "video") {
      btn.addEventListener("click", () => regenerate(i, "video"));
    } else if (act === "upload") {
      btn.addEventListener("click", () => $(`file-${i}`).click());
    } else if (act === "delete") {
      btn.addEventListener("click", () => deleteScene(i));
    } else if (act === "play") {
      btn.addEventListener("click", () => previewScene(i));
    }
  });

  // Controles de "usar audio de mi video" por escena
  review.scenes.forEach((scene) => {
    const i = scene.index;
    const chk = $(`ownaudio-chk-${i}`);
    if (chk) chk.addEventListener("change", () => toggleSceneOwnAudio(i, chk.checked));
    const vol = $(`ownaudio-vol-${i}`);
    if (vol) {
      vol.addEventListener("input", () => {
        const lbl = $(`ownaudio-vollbl-${i}`);
        if (lbl) lbl.textContent = vol.value + "%";
      });
      vol.addEventListener("change", () => setSceneOwnAudioVolume(i, parseInt(vol.value, 10) / 100));
    }
    // Controles de recorte de video (inicio / fin)
    const ts = $(`trim-start-${i}`);
    const te = $(`trim-end-${i}`);
    if (ts && te) {
      ts.addEventListener("input", () => {
        const lbl = $(`trim-slbl-${i}`);
        if (lbl) lbl.textContent = parseFloat(ts.value).toFixed(1) + "s";
      });
      te.addEventListener("input", () => {
        const lbl = $(`trim-elbl-${i}`);
        if (lbl) lbl.textContent = parseFloat(te.value).toFixed(1) + "s";
      });
    }
    const applyBtn = document.querySelector(`[data-trimapply="${i}"]`);
    if (applyBtn) applyBtn.addEventListener("click", () => {
      const s = parseFloat($(`trim-start-${i}`).value) || 0;
      const e = parseFloat($(`trim-end-${i}`).value) || 0;
      setSceneTrim(i, s, e);
    });
    const resetBtn = document.querySelector(`[data-trimreset="${i}"]`);
    if (resetBtn) resetBtn.addEventListener("click", () => {
      const startEl = $(`trim-start-${i}`);
      const endEl = $(`trim-end-${i}`);
      if (startEl) startEl.value = 0;
      if (endEl) endEl.value = endEl.max;
      const sl = $(`trim-slbl-${i}`); if (sl) sl.textContent = "0.0s";
      const el = $(`trim-elbl-${i}`); if (el) el.textContent = parseFloat(endEl.max).toFixed(1) + "s";
      setSceneTrim(i, 0, 0);
    });

    // Controles de PEDAZOS (mini-clips) de la escena
    const clipAddBtn = document.querySelector(`[data-clipadd="${i}"]`);
    if (clipAddBtn) clipAddBtn.addEventListener("click", () => $(`clipfile-${i}`).click());
    const clipFile = $(`clipfile-${i}`);
    if (clipFile) clipFile.addEventListener("change", () => uploadSceneClip(i, clipFile.files[0], 2));
    (scene.clips || []).forEach((c, k) => {
      const del = document.querySelector(`[data-clipdel="${i}-${k}"]`);
      if (del) del.addEventListener("click", () => removeSceneClip(i, k));
      const sec = $(`clipsec-${i}-${k}`);
      if (sec) sec.addEventListener("change", () => setSceneClipSeconds(i, k, parseFloat(sec.value) || 2));
      // Reordenar el pedazo
      const left = document.querySelector(`[data-clipleft="${i}-${k}"]`);
      if (left) left.addEventListener("click", () => moveSceneClip(i, k, "left"));
      const right = document.querySelector(`[data-clipright="${i}-${k}"]`);
      if (right) right.addEventListener("click", () => moveSceneClip(i, k, "right"));
      // Sliders de recorte del pedazo (solo video): actualizar etiquetas
      const cts = $(`cts-${i}-${k}`);
      const cte = $(`cte-${i}-${k}`);
      if (cts) cts.addEventListener("input", () => {
        const l = $(`ctlbl-s-${i}-${k}`); if (l) l.textContent = parseFloat(cts.value).toFixed(1) + "s";
      });
      if (cte) cte.addEventListener("input", () => {
        const l = $(`ctlbl-e-${i}-${k}`); if (l) l.textContent = parseFloat(cte.value).toFixed(1) + "s";
      });
      const trimBtn = document.querySelector(`[data-cliptrim="${i}-${k}"]`);
      if (trimBtn) trimBtn.addEventListener("click", () => {
        const s = cts ? parseFloat(cts.value) || 0 : 0;
        const e = cte ? parseFloat(cte.value) || 0 : 0;
        setSceneClipTrim(i, k, s, e);
      });
    });
  });

  // Preparar el preview RECORTADO de cada video (que reproduzca solo su trozo).
  grid.querySelectorAll("video.clip-prev").forEach((v) => setupTrimPreview(v));
  // Guardar el dialogo automaticamente cuando el usuario termina de editar
  grid.querySelectorAll(".scene-dialogue").forEach((ta) => {
    const i = parseInt(ta.id.split("-")[1], 10);
    ta.addEventListener("change", () => saveDialogue(i));
  });
  grid.querySelectorAll('input[type="file"]').forEach((inp) => {
    const i = parseInt(inp.id.split("-")[1], 10);
    inp.addEventListener("change", () => uploadImage(i, inp.files[0]));
  });

  // Conectar zonas de paste (clipboard) para cada escena
  grid.querySelectorAll(".paste-zone").forEach((zone) => {
    const i = parseInt(zone.dataset.i, 10);
    zone.addEventListener("click", () => {
      // Al hacer clic en la zona, intenta leer del clipboard
      pasteFromClipboard(i);
    });
  });

  show(reviewCard);
}

// Guardar el dialogo editado de una escena
async function saveDialogue(i) {
  const text = $(`dialogue-${i}`).value.trim();
  if (!text) return;
  try {
    const resp = await fetch("/api/update_scene", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ job_id: currentJob, index: i, text }),
    });
    const data = await resp.json();
    if (!resp.ok) { alert(data.error || "No se pudo guardar el dialogo"); return; }
    const saved = $(`saved-${i}`);
    if (saved) {
      saved.classList.remove("hidden");
      setTimeout(() => saved.classList.add("hidden"), 1500);
    }
  } catch (e) {
    alert("Error al guardar el dialogo: " + e);
  }
}

// Eliminar una escena completa (imagen + dialogo)
async function deleteScene(i) {
  if (!confirm("¿Eliminar esta escena por completo (imagen y dialogo)?")) return;
  try {
    const resp = await fetch("/api/delete_scene", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ job_id: currentJob, index: i }),
    });
    const data = await resp.json();
    if (!resp.ok) { alert(data.error || "No se pudo eliminar la escena"); return; }
    // Re-dibujar la lista (los numeros de escena se reordenan)
    renderReview(data.review);
  } catch (e) {
    alert("Error al eliminar la escena: " + e);
  }
}

// ----------------------------------------------------------------------
//  Agregar una escena NUEVA (dialogo + imagen/video)
// ----------------------------------------------------------------------
function resetAddSceneForm() {
  const form = $("add-scene-form");
  if (form) form.classList.add("hidden");
  if ($("add-scene-text")) $("add-scene-text").value = "";
  if ($("add-scene-desc")) $("add-scene-desc").value = "";
  if ($("add-scene-status")) $("add-scene-status").textContent = "";
}

// Llena el menu de "¿donde colocarla?" segun cuantas escenas hay ahora.
function buildAddScenePositions() {
  const sel = $("add-scene-pos");
  if (!sel) return;
  sel.innerHTML = "";
  const end = document.createElement("option");
  end.value = String(currentSceneCount);
  end.textContent = "Al final (después de la última)";
  sel.appendChild(end);
  const start = document.createElement("option");
  start.value = "0";
  start.textContent = "Al inicio (antes de la escena 1)";
  sel.appendChild(start);
  for (let i = 1; i <= currentSceneCount; i++) {
    const o = document.createElement("option");
    o.value = String(i);
    o.textContent = `Después de la escena ${i}`;
    sel.appendChild(o);
  }
  sel.value = String(currentSceneCount); // por defecto: al final
}

function toggleAddSceneForm() {
  const form = $("add-scene-form");
  if (!form) return;
  if (form.classList.contains("hidden")) {
    buildAddScenePositions();
    form.classList.remove("hidden");
    $("add-scene-text").focus();
  } else {
    form.classList.add("hidden");
  }
}

async function submitAddScene() {
  const text = $("add-scene-text").value.trim();
  const desc = $("add-scene-desc").value.trim();
  const posVal = parseInt($("add-scene-pos").value, 10);
  const status = $("add-scene-status");
  const btn = $("add-scene-confirm");

  if (!text) {
    status.style.color = "#ff8a8a";
    status.textContent = "Escribe el diálogo que se va a narrar en la escena nueva.";
    return;
  }
  btn.disabled = true;
  status.style.color = "";
  status.textContent = "Creando la escena (buscando imagen/video)... espera unos segundos.";
  try {
    const resp = await fetch("/api/add_scene", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        job_id: currentJob,
        text,
        image_desc: desc,
        position: isNaN(posVal) ? null : posVal,
      }),
    });
    const data = await resp.json();
    btn.disabled = false;
    if (!resp.ok) {
      status.style.color = "#ff8a8a";
      status.textContent = data.error || "No se pudo agregar la escena.";
      return;
    }
    resetAddSceneForm();
    renderReview(data.review);  // vuelve a dibujar con la escena nueva incluida
  } catch (e) {
    btn.disabled = false;
    status.style.color = "#ff8a8a";
    status.textContent = "Error de conexión: " + e;
  }
}

function setSceneLoading(i, on) {
  const loading = $(`loading-${i}`);
  if (loading) loading.classList.toggle("hidden", !on);
  const img = $(`img-${i}`);
  if (img) img.classList.toggle("is-loading", on);
  document.querySelectorAll(`#scene-${i} .btn-mini`).forEach((b) => (b.disabled = on));
}

// Reemplaza la vista previa de una escena por una NUEVA foto o videoclip.
// Si cambia el tipo (p. ej. subiste un video donde habia foto), crea el
// elemento correcto (<img> o <video>) en su lugar.
function setSceneMedia(i, file, isVideo) {
  const old = $(`img-${i}`);
  if (!old) return;
  const url = imgUrl(file);
  let el;
  if (isVideo) {
    el = document.createElement("video");
    el.muted = true;
    el.loop = true;
    el.autoplay = true;
    el.setAttribute("playsinline", "");
    el.onloadeddata = () => setSceneLoading(i, false);
  } else {
    el = document.createElement("img");
    el.alt = "escena " + (i + 1);
    el.onload = () => setSceneLoading(i, false);
  }
  el.className = "scene-img" + (old.classList.contains("is-loading") ? " is-loading" : "");
  el.id = `img-${i}`;
  el.onerror = () => setSceneLoading(i, false);
  el.src = url;
  old.replaceWith(el);
}

async function regenerate(i, mode) {
  attempts[i] = (attempts[i] || 0) + 1;
  const prompt = $(`prompt-${i}`).value.trim();
  setSceneLoading(i, true);
  try {
    const resp = await fetch("/api/regenerate_image", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ job_id: currentJob, index: i, mode, prompt, attempt: attempts[i] }),
    });
    const data = await resp.json();
    if (!resp.ok) { alert(data.error || "No se pudo regenerar la imagen"); setSceneLoading(i, false); return; }
    // Dejamos el girito hasta que el NUEVO medio se vea (asi notas el cambio).
    setSceneMedia(i, data.image_file, data.is_video);
    $(`badge-${i}`).textContent = data.source;
  } catch (e) {
    alert("Error al regenerar: " + e);
    setSceneLoading(i, false);
  }
}

async function uploadImage(i, file) {
  if (!file) return;
  setSceneLoading(i, true);
  try {
    const fd = new FormData();
    fd.append("job_id", currentJob);
    fd.append("index", i);
    fd.append("image", file);
    const resp = await fetch("/api/upload_image", { method: "POST", body: fd });
    const data = await resp.json();
    if (!resp.ok) { alert(data.error || "No se pudo subir la imagen"); setSceneLoading(i, false); return; }
    setSceneMedia(i, data.image_file, data.is_video);
    $(`badge-${i}`).textContent = data.source;
  } catch (e) {
    alert("Error al subir: " + e);
    setSceneLoading(i, false);
  }
}

// ----------------------------------------------------------------------
//  Musica de fondo (3 opciones: automatica / propia / sin musica)
// ----------------------------------------------------------------------
function currentMusicMode() {
  const el = document.querySelector('input[name="music-mode"]:checked');
  return el ? el.value : "auto";
}

function setupMusicControls() {
  const fileInput = $("music-file");
  const vol = $("music-volume");
  const volLabel = $("music-vol-label");
  const status = $("music-status");
  const ownBox = $("music-own");
  const volBox = $("music-vol-box");

  function refresh() {
    const mode = currentMusicMode();
    ownBox.classList.toggle("hidden", mode !== "own");
    volBox.classList.toggle("hidden", mode === "off");
  }

  document.querySelectorAll('input[name="music-mode"]').forEach((r) => {
    r.addEventListener("change", refresh);
  });
  refresh();

  vol.addEventListener("input", () => { volLabel.textContent = vol.value + "%"; });

  fileInput.addEventListener("change", async () => {
    const file = fileInput.files[0];
    if (!file) return;
    status.textContent = "Subiendo música...";
    try {
      const fd = new FormData();
      fd.append("job_id", currentJob);
      fd.append("music", file);
      const resp = await fetch("/api/upload_music", { method: "POST", body: fd });
      const data = await resp.json();
      if (!resp.ok) { status.textContent = "❌ " + (data.error || "No se pudo subir"); return; }
      status.textContent = "✔ Música lista: " + data.music_file;
    } catch (e) {
      status.textContent = "❌ Error al subir la música.";
    }
  });
}

// ----------------------------------------------------------------------
//  PASO 2: ensamblar el video final
// ----------------------------------------------------------------------
async function startAssemble() {
  const mode = currentMusicMode();

  // Si eligio su propia musica pero no subio archivo, avisamos
  if (mode === "own") {
    const status = $("music-status").textContent || "";
    if (!status.startsWith("✔")) {
      if (!confirm("Elegiste 'Mi propia música' pero no veo un archivo subido. Si continúas, el programa pondrá música automática. ¿Seguir así?")) {
        return;
      }
    }
  }

  progressTitle.textContent = "Generando el video final...";
  show(progressCard);
  setProgress(5, "Preparando ensamblaje...");

  const payload = {
    job_id: currentJob,
    music_mode: mode,
    music_volume: parseInt($("music-volume").value, 10) / 100,
    voice: $("review-voice") ? $("review-voice").value : "",
    use_avatar: $("review-avatar") ? $("review-avatar").checked : false,
  };

  try {
    const resp = await fetch("/api/assemble", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
    const data = await resp.json();
    if (!resp.ok) { showError(data.error || "Error al ensamblar"); return; }
    pollStatus();
  } catch (e) {
    showError("No pude contactar al programa.\n" + e);
  }
}

// ----------------------------------------------------------------------
//  Resultado final
// ----------------------------------------------------------------------
function showResult(result) {
  const video = $("result-video");
  video.src = `/video/${encodeURIComponent(result.video_file)}`;
  $("download-link").href = `/download/${encodeURIComponent(result.video_file)}`;

  const titlesList = $("titles-list");
  titlesList.innerHTML = "";
  (result.titles || []).forEach((t) => {
    const li = document.createElement("li");
    li.textContent = t;
    titlesList.appendChild(li);
  });

  $("hashtags-text").textContent = (result.hashtags || []).map((h) => "#" + h).join("  ");
  $("narration-text").textContent = result.narration || "";
  show(resultCard);
}

function showError(msg) {
  generateBtn.disabled = false;
  $("error-msg").textContent = msg;
  show(errorCard);
}

function escapeHtml(s) {
  return (s || "").replace(/[&<>"']/g, (c) => (
    { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]
  ));
}

// Muestra (u oculta) un aviso amarillo. Se usa para "necesito mas informacion"
// cuando el guion no alcanzo la duracion pedida por falta de material.
function showWarning(elId, msg) {
  const el = $(elId);
  if (!el) return;
  if (msg && msg.trim()) {
    el.textContent = msg;
    el.classList.remove("hidden");
  } else {
    el.textContent = "";
    el.classList.add("hidden");
  }
}

// ----------------------------------------------------------------------
//  Escuchar una MUESTRA de la voz seleccionada (antes de generar el video)
// ----------------------------------------------------------------------
async function previewVoice() {
  const btn = $("voice-preview-btn");
  const status = $("voice-preview-status");
  const audio = $("voice-preview-audio");
  const voice = $("voice") ? $("voice").value : "";

  // Si esta sonando, lo paramos (el boton sirve para reproducir/parar).
  if (audio && !audio.paused) {
    audio.pause();
    audio.currentTime = 0;
    status.textContent = "";
    btn.textContent = "🔊 Escuchar esta voz";
    return;
  }

  btn.disabled = true;
  status.textContent = "Generando muestra...";
  try {
    const resp = await fetch("/api/preview_voice", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ voice }),
    });
    const data = await resp.json();
    if (!resp.ok) {
      status.textContent = "❌ " + (data.error || "No se pudo generar la muestra.");
      return;
    }
    status.textContent = "▶️ Sonando: " + data.voice;
    audio.src = data.audio_url + "?t=" + Date.now();
    btn.textContent = "⏹️ Detener";
    audio.onended = () => {
      btn.textContent = "🔊 Escuchar esta voz";
      status.textContent = "";
    };
    await audio.play();
  } catch (e) {
    status.textContent = "❌ No pude contactar al programa. ¿Sigue abierta la ventana negra?";
  } finally {
    btn.disabled = false;
  }
}

// ----------------------------------------------------------------------
//  CLIPBOARD PASTE: pegar screenshots directamente en una escena
// ----------------------------------------------------------------------

// Variable para rastrear cual escena recibira la imagen pegada.
// Se activa al hacer clic/focus en una paste-zone o scene-card.
let pasteTargetScene = null;

// Intenta leer una imagen o video del clipboard via la API moderna (navigator.clipboard)
async function pasteFromClipboard(i) {
  try {
    if (!navigator.clipboard || !navigator.clipboard.read) {
      alert("Tu navegador no soporta leer el portapapeles. Usa Ctrl+V directamente sobre la zona de la escena.");
      return;
    }
    const items = await navigator.clipboard.read();
    for (const item of items) {
      // Buscar imagen o video en el clipboard
      const mediaType = item.types.find((t) => t.startsWith("image/") || t.startsWith("video/"));
      if (mediaType) {
        const blob = await item.getType(mediaType);
        const isVideo = mediaType.startsWith("video/");
        const ext = mediaType.split("/")[1] || (isVideo ? "mp4" : "png");
        const prefix = isVideo ? "video" : "screenshot";
        const file = new File([blob], `${prefix}_${Date.now()}.${ext}`, { type: mediaType });
        uploadImage(i, file);
        return;
      }
    }
    alert("No hay imagen ni video en el portapapeles. Toma un screenshot (Win+Shift+S o PrtSc) o copia un video y luego pega aquí.");
  } catch (e) {
    // Si el navegador no permite la API, indicamos usar Ctrl+V
    alert("No pude acceder al portapapeles. Haz clic en la zona de paste de la escena y presiona Ctrl+V.");
  }
}

// Listener GLOBAL de paste: detecta Ctrl+V en cualquier momento
// y sube la imagen o video a la escena que tenga el foco (pasteTargetScene).
document.addEventListener("paste", function (e) {
  // Si el usuario esta escribiendo en un textarea/input, no interceptamos
  const tag = (e.target.tagName || "").toLowerCase();
  if (tag === "textarea" || tag === "input") return;

  const items = e.clipboardData && e.clipboardData.items;
  if (!items) return;

  for (let i = 0; i < items.length; i++) {
    const type = items[i].type;
    if (type.startsWith("image/") || type.startsWith("video/")) {
      e.preventDefault();
      const blob = items[i].getAsFile();
      if (!blob) return;

      // Determinar la escena destino
      let targetIndex = pasteTargetScene;

      // Si no hay escena seleccionada, buscar la primera visible
      if (targetIndex === null) {
        const firstCard = document.querySelector(".scene-card");
        if (firstCard) {
          targetIndex = parseInt(firstCard.id.replace("scene-", ""), 10);
        }
      }

      if (targetIndex === null) {
        alert("Primero haz clic en la escena donde quieres pegar la imagen o video.");
        return;
      }

      const isVideo = type.startsWith("video/");
      const ext = type.split("/")[1] || (isVideo ? "mp4" : "png");
      const prefix = isVideo ? "video" : "screenshot";
      const file = new File([blob], `${prefix}_${Date.now()}.${ext}`, { type: type });
      uploadImage(targetIndex, file);

      // Feedback visual
      const zone = document.querySelector(`.paste-zone[data-i="${targetIndex}"]`);
      if (zone) {
        zone.classList.add("paste-success");
        setTimeout(() => zone.classList.remove("paste-success"), 1500);
      }
      return;
    }
  }
});

// Al hacer clic o focus en una scene-card o paste-zone, marcarla como destino
document.addEventListener("click", function (e) {
  const card = e.target.closest(".scene-card");
  if (card) {
    pasteTargetScene = parseInt(card.id.replace("scene-", ""), 10);
    // Resaltar visualmente la zona activa
    document.querySelectorAll(".paste-zone").forEach((z) => z.classList.remove("paste-active"));
    const zone = card.querySelector(".paste-zone");
    if (zone) zone.classList.add("paste-active");
  }
});

// ----------------------------------------------------------------------
//  ▶️ Escuchar el dialogo de UNA escena (con la voz que le toca)
// ----------------------------------------------------------------------
async function previewScene(i) {
  const btn = document.querySelector(`#scene-${i} .btn-play`);
  const status = $(`playstatus-${i}`);
  const audio = $(`playaudio-${i}`);
  if (!audio) return;

  // Si ya esta sonando, lo detenemos (el boton sirve para play/stop).
  if (!audio.paused) {
    audio.pause();
    audio.currentTime = 0;
    if (btn) btn.textContent = "▶️ Escuchar esta escena";
    if (status) status.textContent = "";
    return;
  }

  const text = $(`dialogue-${i}`) ? $(`dialogue-${i}`).value.trim() : "";
  if (!text) { if (status) status.textContent = "Esta escena no tiene diálogo."; return; }

  if (status) status.textContent = "Generando audio...";
  if (btn) btn.disabled = true;
  try {
    const resp = await fetch("/api/preview_scene", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ job_id: currentJob, index: i, text }),
    });
    const data = await resp.json();
    if (!resp.ok) { if (status) status.textContent = "❌ " + (data.error || "No se pudo"); return; }
    audio.src = data.audio_url + "?t=" + Date.now();
    if (btn) btn.textContent = "⏹️ Detener";
    if (status) status.textContent = "▶️ " + data.voice;
    audio.onended = () => {
      if (btn) btn.textContent = "▶️ Escuchar esta escena";
      if (status) status.textContent = "";
    };
    await audio.play();
  } catch (e) {
    if (status) status.textContent = "❌ Error de conexión";
  } finally {
    if (btn) btn.disabled = false;
  }
}

// ----------------------------------------------------------------------
//  🎧 Usar el AUDIO PROPIO del video en una escena (Opcion A)
// ----------------------------------------------------------------------
async function toggleSceneOwnAudio(i, on) {
  const extra = $(`ownaudio-extra-${i}`);
  const vol = $(`ownaudio-vol-${i}`) ? parseInt($(`ownaudio-vol-${i}`).value, 10) / 100 : 1;
  try {
    const resp = await fetch("/api/scene_audio", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ job_id: currentJob, index: i, use_own_audio: on, volume: vol }),
    });
    const data = await resp.json();
    if (!resp.ok) {
      alert(data.error || "No se pudo cambiar el audio de la escena.");
      const chk = $(`ownaudio-chk-${i}`);
      if (chk) chk.checked = !on;
      return;
    }
    if (extra) extra.classList.toggle("hidden", !on);
    if (on && data.own_audio_duration) {
      const durlbl = $(`ownaudio-dur-${i}`);
      if (durlbl) durlbl.textContent = `Esta escena durará lo que dure tu video (~${data.own_audio_duration}s).`;
      const durbadge = $(`dur-${i}`);
      if (durbadge) durbadge.textContent = `⏱️ ~${data.own_audio_duration}s`;
    }
  } catch (e) {
    alert("Error: " + e);
  }
}

async function setSceneOwnAudioVolume(i, val) {
  try {
    await fetch("/api/scene_audio", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ job_id: currentJob, index: i, use_own_audio: true, volume: val }),
    });
  } catch (e) { /* silencioso */ }
}

// Recortar el video de una escena (dejar solo del segundo X al Y)
async function setSceneTrim(i, start, end) {
  const status = $(`trim-status-${i}`);
  if (status) status.textContent = "Guardando recorte...";
  try {
    const resp = await fetch("/api/scene_trim", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ job_id: currentJob, index: i, start, end }),
    });
    const data = await resp.json();
    if (!resp.ok) { if (status) status.textContent = "❌ " + (data.error || "No se pudo"); return; }
    const finTxt = data.trim_end > 0 ? `${data.trim_end}s` : "el final";
    if (status) status.textContent = `✔ Usando del ${data.trim_start}s a ${finTxt} (${data.effective_duration}s)`;
    // Si la escena usa su propio audio, su duración cambió: actualizamos el sello.
    const durbadge = $(`dur-${i}`);
    if (durbadge && data.effective_duration && $(`ownaudio-chk-${i}`) && $(`ownaudio-chk-${i}`).checked) {
      durbadge.textContent = `⏱️ ~${data.effective_duration}s`;
    }
  } catch (e) {
    if (status) status.textContent = "❌ Error de conexión";
  }
}

// ----------------------------------------------------------------------
//  Pedazos (mini-clips) dentro de una escena
// ----------------------------------------------------------------------
async function uploadSceneClip(i, file, seconds) {
  if (!file) return;
  const status = $(`clipstatus-${i}`);
  if (status) status.textContent = "Subiendo pedazo...";
  try {
    const fd = new FormData();
    fd.append("job_id", currentJob);
    fd.append("index", i);
    fd.append("seconds", seconds || 2);
    fd.append("file", file);
    const resp = await fetch("/api/scene_clip_add", { method: "POST", body: fd });
    const data = await resp.json();
    if (!resp.ok) { if (status) status.textContent = "❌ " + (data.error || "No se pudo"); return; }
    renderReview(data.review);
  } catch (e) {
    if (status) status.textContent = "❌ Error de conexión";
  }
}

async function removeSceneClip(i, k) {
  try {
    const resp = await fetch("/api/scene_clip_remove", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ job_id: currentJob, index: i, clip_index: k }),
    });
    const data = await resp.json();
    if (!resp.ok) { alert(data.error || "No se pudo quitar el pedazo"); return; }
    renderReview(data.review);
  } catch (e) {
    alert("Error: " + e);
  }
}

async function setSceneClipSeconds(i, k, seconds) {
  try {
    await fetch("/api/scene_clip_seconds", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ job_id: currentJob, index: i, clip_index: k, seconds }),
    });
  } catch (e) { /* silencioso */ }
}

// Recortar un pedazo de video (usar solo del segundo X al Y) y volver a dibujar
// para que el preview muestre ese trozo.
async function setSceneClipTrim(i, k, start, end) {
  try {
    const resp = await fetch("/api/scene_clip_trim", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ job_id: currentJob, index: i, clip_index: k, start, end }),
    });
    const data = await resp.json();
    if (!resp.ok) { alert(data.error || "No se pudo recortar el pedazo"); return; }
    renderReview(data.review);
  } catch (e) {
    alert("Error: " + e);
  }
}

// Reordenar un pedazo (izquierda / derecha)
async function moveSceneClip(i, k, direction) {
  try {
    const resp = await fetch("/api/scene_clip_move", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ job_id: currentJob, index: i, clip_index: k, direction }),
    });
    const data = await resp.json();
    if (!resp.ok) { alert(data.error || "No se pudo mover el pedazo"); return; }
    renderReview(data.review);
  } catch (e) {
    alert("Error: " + e);
  }
}

// Hace que un <video> de preview reproduzca SOLO su trozo recortado, en loop.
// Asi ves EXACTAMENTE la parte del video que se usará (ej: del 2 al 4), aquí,
// antes de generar.
function setupTrimPreview(v) {
  if (!v) return;
  const start = parseFloat(v.dataset.tstart || "0") || 0;
  let end = parseFloat(v.dataset.tend || "0") || 0;
  const clampToStart = () => {
    try { if (start > 0) v.currentTime = start; } catch (e) { /* aún sin metadata */ }
  };
  v.addEventListener("loadedmetadata", () => {
    if (!end || end <= start) end = v.duration || 0;
    clampToStart();
    v.play().catch(() => {});
  });
  v.addEventListener("timeupdate", () => {
    const stop = (end && end > start) ? end : (v.duration || 0);
    if (stop && v.currentTime >= stop - 0.05) {
      v.currentTime = start;
      v.play().catch(() => {});
    }
  });
}

// ----------------------------------------------------------------------
//  Avatares: selectores de voz, podcast y gestor (crear/editar/borrar)
// ----------------------------------------------------------------------
function voicePickerHtml() {
  let html = "";
  (window.VF_VOICES || []).forEach((v) => {
    html += `<option value="${v.value}">${escapeHtml(v.label)}</option>`;
  });
  if ((window.VF_FOREIGN || []).length) {
    html += `<optgroup label="🌍 Acento extranjero (experimental)">`;
    window.VF_FOREIGN.forEach((v) => {
      html += `<option value="${v.value}">${escapeHtml(v.label)}</option>`;
    });
    html += `</optgroup>`;
  }
  return html;
}

function fillVoicePickers() {
  const html = voicePickerHtml();
  document.querySelectorAll(".voice-picker").forEach((sel) => {
    const prev = sel.value;
    sel.innerHTML = html;
    if (prev) sel.value = prev;
  });
}

function refreshPodcastUI() {
  const on = $("podcast-toggle") && $("podcast-toggle").checked;
  if ($("podcast-box")) $("podcast-box").classList.toggle("hidden", !on);
  if ($("single-avatar-box")) $("single-avatar-box").classList.toggle("hidden", on);
}

async function refreshAvatarDropdowns() {
  try {
    const resp = await fetch("/api/avatars");
    const data = await resp.json();
    const avatars = data.avatars || [];
    const specs = [
      ["avatar-select", "— Ninguno (usar la voz de arriba) —"],
      ["avatar-a-select", "— Elegir voz manual —"],
      ["avatar-b-select", "— Elegir voz manual —"],
    ];
    specs.forEach(([id, placeholder]) => {
      const sel = $(id);
      if (!sel) return;
      const prev = sel.value;
      let html = `<option value="">${placeholder}</option>`;
      avatars.forEach((a) => {
        html += `<option value="${a.id}">${escapeHtml(a.name)} · ${a.accent} · ${a.gender}</option>`;
      });
      sel.innerHTML = html;
      sel.value = prev;
    });
  } catch (e) { /* silencioso */ }
}

function refreshAvatarCustomField() {
  const custom = $("avatar-style") && $("avatar-style").value === "custom";
  if ($("avatar-custom-field")) $("avatar-custom-field").style.display = custom ? "" : "none";
}

function clearAvatarEditor() {
  if ($("avatar-edit-id")) $("avatar-edit-id").value = "";
  if ($("avatar-name")) $("avatar-name").value = "";
  if ($("avatar-custom")) $("avatar-custom").value = "";
  if ($("avatar-editor-title")) $("avatar-editor-title").textContent = "➕ Nuevo avatar";
  if ($("avatar-status")) $("avatar-status").textContent = "";
  refreshAvatarCustomField();
}

function editAvatar(a) {
  if ($("avatar-edit-id")) $("avatar-edit-id").value = a.id;
  if ($("avatar-name")) $("avatar-name").value = a.name;
  if ($("avatar-voice")) $("avatar-voice").value = a.voice;
  if ($("avatar-style")) $("avatar-style").value = a.style;
  if ($("avatar-custom")) $("avatar-custom").value = a.custom_style || "";
  if ($("avatar-editor-title")) $("avatar-editor-title").textContent = "✏️ Editar: " + a.name;
  refreshAvatarCustomField();
  $("avatars-modal").scrollTop = $("avatars-modal").scrollHeight;
}

async function loadAvatarsList() {
  try {
    const resp = await fetch("/api/avatars");
    const data = await resp.json();
    const list = $("avatars-list");
    if (!list) return;
    list.innerHTML = "";
    const avatars = data.avatars || [];
    if (!avatars.length) {
      list.innerHTML = `<p class="hint">Aún no tienes avatares. Crea el primero abajo. 👇</p>`;
      return;
    }
    avatars.forEach((a) => {
      const row = document.createElement("div");
      row.className = "avatar-row";
      row.dataset.json = JSON.stringify(a);
      row.innerHTML = `
        <span>🧑 <strong>${escapeHtml(a.name)}</strong> · ${a.accent} · ${a.gender}</span>
        <span class="avatar-row-actions">
          <button class="btn-mini" data-edit="1">✏️ Editar</button>
          <button class="btn-mini btn-danger" data-del="${a.id}">🗑️</button>
        </span>`;
      list.appendChild(row);
    });
    list.querySelectorAll("[data-edit]").forEach((b) => {
      b.addEventListener("click", () => editAvatar(JSON.parse(b.closest(".avatar-row").dataset.json)));
    });
    list.querySelectorAll("[data-del]").forEach((b) => {
      b.addEventListener("click", () => deleteAvatar(b.dataset.del));
    });
  } catch (e) { /* silencioso */ }
}

async function saveAvatar() {
  const id = $("avatar-edit-id") ? $("avatar-edit-id").value : "";
  const status = $("avatar-status");
  const payload = {
    name: $("avatar-name").value.trim(),
    voice: $("avatar-voice").value,
    style: $("avatar-style").value,
    custom_style: $("avatar-custom").value.trim(),
  };
  if (!payload.name) { status.textContent = "Ponle un nombre a tu avatar."; return; }
  if (!payload.voice) { status.textContent = "Elige una voz."; return; }
  try {
    const url = id ? `/api/avatars/${id}` : "/api/avatars";
    const method = id ? "PUT" : "POST";
    const resp = await fetch(url, {
      method,
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
    const data = await resp.json();
    if (!resp.ok) { status.textContent = "❌ " + (data.error || "No se pudo guardar"); return; }
    status.textContent = "✔ Guardado";
    clearAvatarEditor();
    await loadAvatarsList();
    await refreshAvatarDropdowns();
  } catch (e) {
    status.textContent = "❌ Error de conexión";
  }
}

async function deleteAvatar(id) {
  if (!confirm("¿Borrar este avatar?")) return;
  try {
    await fetch(`/api/avatars/${id}`, { method: "DELETE" });
    await loadAvatarsList();
    await refreshAvatarDropdowns();
  } catch (e) { /* silencioso */ }
}

function openAvatarsModal() {
  clearAvatarEditor();
  loadAvatarsList();
  fillVoicePickers();
  $("avatars-modal").classList.remove("hidden");
}
function closeAvatarsModal() {
  $("avatars-modal").classList.add("hidden");
}

// ----------------------------------------------------------------------
//  Eventos
// ----------------------------------------------------------------------
$("tab-btn-url").addEventListener("click", () => switchTab("url"));
$("tab-btn-story").addEventListener("click", () => switchTab("story"));
$("tab-btn-youtube").addEventListener("click", () => switchTab("youtube"));

generateBtn.addEventListener("click", onGenerate);
assembleBtn.addEventListener("click", startAssemble);
$("generate-draft-btn").addEventListener("click", generateFromDraft);
$("redraft-btn").addEventListener("click", () => { switchTab("story"); show(formCard); });
$("cancel-review-btn").addEventListener("click", () => show(formCard));
$("new-btn").addEventListener("click", () => show(formCard));
$("retry-btn").addEventListener("click", () => show(formCard));

// Agregar escena nueva (pantalla de revision)
if ($("add-scene-btn")) $("add-scene-btn").addEventListener("click", toggleAddSceneForm);
if ($("add-scene-confirm")) $("add-scene-confirm").addEventListener("click", submitAddScene);
if ($("add-scene-cancel")) $("add-scene-cancel").addEventListener("click", resetAddSceneForm);

setupMusicControls();

// Boton "Escuchar voz" + reset de la muestra al cambiar de voz
if ($("voice-preview-btn")) {
  $("voice-preview-btn").addEventListener("click", previewVoice);
}
if ($("voice")) {
  $("voice").addEventListener("change", () => {
    const audio = $("voice-preview-audio");
    if (audio && !audio.paused) { audio.pause(); audio.currentTime = 0; }
    const btn = $("voice-preview-btn");
    if (btn) btn.textContent = "🔊 Escuchar esta voz";
    const status = $("voice-preview-status");
    if (status) status.textContent = "";
  });
}

// Aviso de video largo: revisar al cargar y cada vez que cambie la duracion
if ($("duration")) {
  $("duration").addEventListener("change", refreshLongVideoWarning);
  refreshLongVideoWarning();
}

// --- Avatares / estilo / podcast ---
if ($("podcast-toggle")) {
  $("podcast-toggle").addEventListener("change", refreshPodcastUI);
  refreshPodcastUI();
}
if ($("manage-avatars-btn")) $("manage-avatars-btn").addEventListener("click", openAvatarsModal);
if ($("close-avatars-btn")) $("close-avatars-btn").addEventListener("click", closeAvatarsModal);
if ($("save-avatar-btn")) $("save-avatar-btn").addEventListener("click", saveAvatar);
if ($("cancel-avatar-btn")) $("cancel-avatar-btn").addEventListener("click", clearAvatarEditor);
if ($("avatar-style")) $("avatar-style").addEventListener("change", refreshAvatarCustomField);

// Poblar los selectores de voz (podcast manual + editor de avatares) al cargar.
fillVoicePickers();
