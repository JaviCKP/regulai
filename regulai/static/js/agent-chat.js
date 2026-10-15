/* Authorized user projections only. Never insert document or inference content as HTML. */
(() => {
  let mode = null, revision = null, stream = null, run = null, cursor = 0, command = null;
  let documentReference = null, pendingExport = null, artifactKey = '', snapshotVersion = 0;
  let chosenRevision = null;
  const byId = id => document.getElementById(id);
  const csrf = () => document.querySelector('[name=csrfmiddlewaretoken]').value;
  const live = status => ['queued', 'active', 'outcome_unknown'].includes(status);
  const list = value => Array.isArray(value) ? value : [];
  const present = value => value !== null && value !== undefined && value !== '';
  const professional = () => run?.professional || byId('agentActivity')?.dataset.professional === 'true';
  const labels = {
    queued: 'En cola', active: 'En curso', outcome_unknown: 'Resultado por confirmar',
    completed: 'Finalizado', failed: 'No completado', interrupted: 'Interrumpido', cancelled: 'Cancelado',
    expired: 'Caducado', pending: 'Pendiente', passed: 'Superada', not_performed: 'No realizada',
    consulted: 'Consultado', not_consulted: 'No consultado', disabled: 'Deshabilitado', no_response: 'Sin respuesta',
    allow: 'Permitido', allowed: 'Permitido', block: 'Bloqueado', blocked: 'Bloqueado', unavailable: 'No disponible',
    continue: 'Continuar', not_required: 'No requerido', required: 'Requerido', automatic: 'Automática',
    agent_profile: 'Perfil del agente', classification: 'Clasificación', generation: 'Generación',
    research: 'Consulta de fuentes', primary_source_read: 'Consulta de fuente primaria', no_api_charge: 'Sin cargo de API',
    verification: 'Comprobación', not_used: 'Sin fallback de Regulay', used: 'Utilizado', unknown: 'No disponible',
    reviewed: 'Revisada por el modelo', web_search: 'Búsqueda web', web_read: 'Lectura web',
    web_browser_resource: 'Recurso del navegador', package_download: 'Descarga de dependencia',
    configured_upper_bound_estimate: 'Estimación máxima configurada',
  };
  const label = value => labels[value] || (present(value) ? String(value) : 'No disponible');
  const text = value => { if (byId('agentProgress')) byId('agentProgress').textContent = value || ''; };
  function node(tag, value, parent, className = '') {
    const element = document.createElement(tag);
    if (value != null) element.textContent = String(value);
    if (className) element.className = className;
    if (parent) parent.appendChild(element);
    return element;
  }
  function button(value, parent, action, className = 'btn btn-outline-primary btn-sm') {
    const element = node('button', value, parent, className);
    element.type = 'button'; element.addEventListener('click', action); return element;
  }
  function detail(parent, name, value) {
    if (!present(value)) return;
    node('dt', name, parent); node('dd', value, parent);
  }
  function details(parent, title, className = 'agent-details') {
    const element = node('details', null, parent, className);
    node('summary', title, element); return element;
  }
  function amount(value, currency) {
    return present(value) && Number.isFinite(Number(value)) ? `${value} ${currency || ''}`.trim() : 'No disponible';
  }
  function timestamp(value) {
    if (!value || !Number.isFinite(Date.parse(value))) return 'No disponible';
    return new Date(value).toLocaleString('es-ES');
  }
  function artifactUrl(value, action) {
    const query = action === 'download' ? '(?:\\?format=(?:docx|pdf))?' : '';
    return typeof value === 'string' && new RegExp('^/chat/agent/artifacts/[0-9a-f-]+/' + action + '/' + query + '$').test(value);
  }
  function checkRows(parent, checks) {
    const names = {integrity: 'Integridad del archivo', instructions: 'Formato e instrucciones',
      layout: 'Maquetación y paginación', sources: 'Fuentes y respaldo factual', security: 'Seguridad y políticas'};
    const area = node('ul', null, parent, 'agent-checks');
    Object.entries(names).forEach(([key, title]) => {
      const check = checks?.[key] || {};
      const status = ['passed', 'failed', 'reviewed'].includes(check.status) ? check.status : 'not_performed';
      const item = node('li', null, area);
      node('span', title, item, 'agent-check-label');
      node('span', status === 'failed' ? 'Fallida' : label(status), item, 'agent-check-status agent-check-' + status);
      node('small', check.detail || 'No hay una comprobación registrada para esta categoría.', item);
    });
  }
  function renderJev(parent, jev = {}) {
    jev = jev && typeof jev === 'object' ? jev : {};
    const area = node('dl', null, parent, 'agent-definition-list');
    detail(area, 'Estado de Jev', jev.status === 'failed' ? 'Falló' : label(jev.status || 'unknown'));
    detail(area, 'Propósito', label(jev.purpose));
    detail(area, 'Consulta', jev.consulted_at ? timestamp(jev.consulted_at) : 'No consta una consulta');
    if (jev.completed_at) detail(area, 'Fin', timestamp(jev.completed_at));
    if (jev.decision && typeof jev.decision === 'object') {
      Object.entries({category: 'Categoría', task: 'Tarea', difficulty: 'Dificultad'}).forEach(([key, name]) => detail(area, name, jev.decision[key]));
    } else if (typeof jev.decision === 'string') detail(area, 'Decisión', jev.decision);
    detail(area, 'Motivos devueltos', list(jev.reasons).join(' · ') || 'Jev no ha proporcionado motivos textuales.');
    detail(area, 'Recomendaciones devueltas', list(jev.recommendations).join(' · ') || 'Jev no ha proporcionado recomendaciones textuales.');
    const policy = jev.policy || {};
    detail(area, 'Política aplicada', [policy.source, present(policy.revision) ? `revisión ${policy.revision}` : null].filter(Boolean).join(' · ') || 'No disponible');
    detail(area, 'Clasificación exigida', policy.classification);
    detail(area, 'Umbral de la política', policy.threshold);
    detail(area, 'Efecto sobre la ejecución', label(jev.effect));
    if (jev.applied && typeof jev.applied === 'object') {
      detail(area, 'Decisión aplicada por Regulay', [jev.applied.sensitivity, jev.applied.task, jev.applied.difficulty].filter(present).join(' · '));
    }
    detail(area, 'Motivos locales del efecto', list(jev.reason_codes).join(' · '));
    if (jev.signals && typeof jev.signals === 'object' && Object.keys(jev.signals).length) {
      node('pre', JSON.stringify(jev.signals, null, 2), details(parent, 'Señales estructuradas devueltas por Jev'), 'agent-signals');
    }
    node('p', 'La decisión de enrutamiento se muestra en cada llamada. Una autorización local no es una aprobación de Jev.', parent, 'agent-explanation');
  }
  function renderCalls(parent, calls) {
    if (!calls.length) { node('p', 'No hay llamadas registradas.', parent, 'agent-explanation'); return; }
    const area = node('ol', null, parent, 'agent-calls');
    calls.forEach((call, index) => {
      const noModel = call.purpose === 'research' ? 'Lectura sin modelo' : 'No disponible';
      const row = details(node('li', null, area), `${call.sequence || index + 1}. ${label(call.purpose)} · ${call.model_effective || noModel}`);
      const values = node('dl', null, row, 'agent-definition-list');
      detail(values, 'Estado', label(call.status));
      detail(values, 'Proveedor', call.provider_name || call.provider || 'No disponible');
      detail(values, 'Modelo solicitado', call.model_requested || call.model || noModel);
      detail(values, 'Modelo efectivo', call.model_effective || noModel);
      detail(values, 'Propósito', label(call.purpose));
      if (call.route && typeof call.route === 'object') {
        detail(values, 'Ruta', label(call.route.mode)); detail(values, 'Destino', call.route.destination);
        detail(values, 'Conector', call.route.connector); detail(values, 'Proveedor de destino', call.route.upstream_provider);
      } else detail(values, 'Ruta', call.route || 'No disponible');
      const fallback = call.fallback;
      detail(values, 'Fallback', typeof fallback === 'object' && fallback ? label(fallback.status) : fallback === true ? 'Utilizado' : fallback === false ? 'No utilizado' : 'No disponible');
      if (fallback && typeof fallback === 'object') detail(values, 'Motivo de fallback', fallback.reason);
      detail(values, 'Inicio', call.started_at ? timestamp(call.started_at) : null);
      detail(values, 'Duración', present(call.duration_ms) ? `${call.duration_ms} ms` : 'No disponible');
      detail(values, 'Coste', amount(call.cost, call.currency));
      detail(values, 'Origen del coste', ({provider_reported: 'Informado por el proveedor', tariff_estimate: 'Estimación con las tarifas configuradas', no_api_charge: labels.no_api_charge, unknown: 'No disponible'})[call.cost_kind] || 'No disponible');
      if (call.jev) renderJev(details(row, 'Consulta Jev de esta llamada'), call.jev);
    });
  }
  function renderReceipt(parent, receipt = {}) {
    parent.replaceChildren();
    renderJev(details(parent, 'Consulta y decisión de Jev'), receipt.jev);
    const calls = list(receipt.calls);
    renderCalls(details(parent, `Secuencia de llamadas · ${calls.length} ${calls.length === 1 ? 'llamada' : 'llamadas'}`), calls);
  }
  function showOversight(receipt = {}) {
    const summary = byId('agentSummary'), trace = byId('agentTrace'); if (!summary || !trace) return;
    summary.replaceChildren();
    const calls = list(receipt.calls), total = receipt.total || {};
    const models = [...new Set(calls.map(call => call.model_effective).filter(Boolean))], cost = amount(total.cost, total.currency);
    const estimated = calls.some(call => ['tariff_estimate', 'configured_upper_bound_estimate'].includes(call.cost_kind)) ? ' · incluye estimación' : '';
    [['Seguridad local', label(receipt.policy?.status)],
      ['Jev', receipt.jev?.status === 'failed' ? 'Falló' : receipt.jev?.status ? label(receipt.jev.status) : 'Sin registro'],
      ['Modelo efectivo', models.length > 1 ? `${models.length} modelos · ${calls.length} llamadas` : models[0] || 'Sin dato efectivo'],
      ['Coste', cost === 'No disponible' && present(total.known_cost) ? `${amount(total.known_cost, total.currency)} conocido${estimated} · total no disponible` : cost + (cost === 'No disponible' ? '' : estimated)]
    ].forEach(([name, value]) => {
      const item = node('div', null, summary, 'agent-summary-item'); node('dt', name, item); node('dd', value, item);
    });
    renderReceipt(trace, receipt);
    if (receipt.policy?.reason_codes?.length) node('p', receipt.policy.reason_codes.join(' · '), details(trace, 'Decisión de la política local'), 'agent-explanation');
  }
  function documentPreview(artifact, parent) {
    const preview = artifact.preview || {}, urls = list(preview.pages), pending = artifact.status !== 'verified';
    const pane = details(parent, `Vista previa · ${urls.length} ${artifact.format === 'pptx' ? 'diapositivas' : 'páginas'}`); pane.open = pending;
    const pages = node('div', null, pane, 'agent-document-pages'), valid = urls.filter(url => artifactUrl(url, 'pages/\\d+'));
    let loaded = 0, reviewButton;
    valid.forEach((url, index) => {
      const figure = node('figure', null, pages), pageName = artifact.format === 'pptx' ? 'Diapositiva' : 'Página';
      node('figcaption', `${pageName} ${index + 1} de ${urls.length}`, figure);
      const img = node('img', null, figure);
      img.alt = `${pageName} ${index + 1}: ${preview.title || 'documento'}. Abre la imagen para revisarla a tamaño completo.`;
      img.onload = () => { loaded++; if (reviewButton) reviewButton.disabled = loaded !== urls.length; };
      img.onerror = () => node('p', `No se ha podido cargar la ${pageName.toLowerCase()} ${index + 1}. Recarga antes de aprobar la revisión.`, figure, 'agent-error');
      img.src = url;
      const link = node('a', `Abrir ${pageName.toLowerCase()} ${index + 1}`, figure); link.href = url; link.target = '_blank'; link.rel = 'noopener';
    });
    if (pending) {
      node('p', 'Revisa la legibilidad, las tablas, los símbolos y los cortes de todas las páginas. Tu confirmación registra únicamente la revisión visual.', pane, 'agent-explanation');
      reviewButton = button('Confirmar revisión visual de todas las páginas', pane, async () => {
        if (!artifactUrl(artifact.review_url, 'review')) return;
        reviewButton.disabled = true;
        try {
          const response = await fetch(artifact.review_url, {method: 'POST', headers: {'Content-Type': 'application/json', 'X-CSRFToken': csrf()},
            body: JSON.stringify({sha256: artifact.sha256, page_sha256: artifact.page_sha256, checks: artifact.review_checks})});
          if (!response.ok) throw new Error('Review unavailable');
          text('Revisión visual registrada. Esperando la finalización de la entrega.'); await snapshot();
        } catch (_) { text('No se pudo registrar la revisión visual. Recarga el estado para comprobar los permisos y la ejecución.'); reviewButton.disabled = loaded !== urls.length; }
      }, 'btn btn-primary btn-sm');
      reviewButton.disabled = !urls.length || valid.length !== urls.length || loaded !== urls.length;
    }
  }
  function sheetPreview(artifact, parent) {
    const preview = artifact.preview || {}, pane = details(parent, 'Vista previa de la hoja');
    if (Array.isArray(preview.sheets)) {
      preview.sheets.forEach(sheet => {
        node('h4', `${sheet.name} · ${sheet.rows} filas · ${sheet.columns} columnas`, pane);
        const table = node('table', null, node('div', null, pane, 'table-responsive'), 'table table-sm agent-sheet');
        const body = node('tbody', null, table);
        list(sheet.preview).forEach(row => { const tr = node('tr', null, body); list(row).forEach(value => node('td', value, tr)); });
      });
      return;
    }
    const table = node('table', null, node('div', null, pane, 'table-responsive'), 'table table-sm agent-sheet');
    node('caption', 'Muestra del archivo generado', table);
    const header = node('tr', null, node('thead', null, table));
    list(preview.headers).forEach(value => { node('th', value, header).scope = 'col'; });
    const body = node('tbody', null, table);
    list(preview.rows).forEach(row => { const tr = node('tr', null, body); list(row).forEach(value => node('td', value, tr)); });
    if (present(preview.total_euros)) node('p', `Total del archivo: ${preview.total_euros} €`, pane, 'agent-explanation');
    if (present(preview.rows_total)) node('p', `${preview.rows_total} filas en el archivo.`, pane, 'agent-explanation');
  }
  function showArtifact(artifact, parent, canExport) {
    const preview = artifact.preview || {}, format = (artifact.format || '').toUpperCase();
    const card = node('article', null, parent, 'agent-artifact'), header = node('div', null, card, 'agent-artifact-heading');
    node('span', format || 'ARCHIVO', header, 'agent-file-mark');
    const titleArea = node('div', null, header); node('h3', preview.title || 'Entregable', titleArea);
    const count = artifact.format === 'xlsx' ? (present(preview.sheet_count) ? `${preview.sheet_count} hojas` : 'Hojas: sin dato') :
      ['docx', 'pdf', 'pptx'].includes(artifact.format) ? `${preview.page_count ?? list(preview.pages).length} ${artifact.format === 'pptx' ? 'diapositivas' : 'páginas'}` : 'Archivo';
    node('p', `${format} · ${count} · Revisión ${artifact.revision}`, titleArea, 'agent-artifact-meta');
    if (artifact.data_mode === 'mock' || preview.data_mode === 'mock') node('p', 'Datos ficticios solicitados expresamente', card, 'agent-notice');
    const actions = node('div', null, card, 'agent-artifact-actions');
    if (artifact.status === 'verified') {
      const seen = new Set();
      [{format: artifact.format, url: artifact.download_url}, ...list(artifact.downloads)].forEach(download => {
        const downloadFormat = String(download.format || artifact.format || '').toLowerCase();
        if (!artifactUrl(download.url, 'download') || seen.has(downloadFormat)) return;
        seen.add(downloadFormat);
        const link = node('a', `Descargar ${downloadFormat.toUpperCase()}`, actions, 'btn btn-primary btn-sm');
        link.href = download.url; link.setAttribute('download', '');
      });
    } else node('span', 'Revisión visual pendiente', actions, 'agent-notice');
    if (professional() && artifact.status === 'verified' && !live(run?.status)) {
      button('Editar esta revisión', actions, () => {
        chosenRevision = artifact;
        const selection = byId('agentRevision');
        if (selection) {
          selection.hidden = false; selection.replaceChildren();
          node('span', `Edición de «${preview.title || 'Archivo'}», revisión ${artifact.revision}. Escribe los cambios. `, selection);
          button('Quitar selección', selection, () => { chosenRevision = null; selection.hidden = true; });
        }
        byId('prompt').focus();
      });
    }
    if (artifact.format === 'xlsx') sheetPreview(artifact, card);
    else if (['docx', 'pdf', 'pptx'].includes(artifact.format)) documentPreview(artifact, card);
    const checks = details(card, 'Comprobaciones del entregable'); checks.open = true;
    checkRows(checks, artifact.verification_checks);
    if (artifact.status === 'verified' && canExport) {
      const exportArea = details(card, 'Guardar una copia en Google Drive'), nameId = `agent-export-name-${artifact.id}`;
      const nameLabel = node('label', 'Nombre del archivo', exportArea, 'form-label small'); nameLabel.htmlFor = nameId;
      const name = node('input', null, exportArea, 'form-control form-control-sm mb-2'); name.id = nameId; name.maxLength = 120;
      name.value = `informe-r${artifact.revision}.${artifact.format || 'xlsx'}`;
      button('Preparar exportación', exportArea, () => {
        pendingExport = {artifactId: artifact.logical_id, baseRevision: artifact.id, exportName: name.value};
        byId('prompt').value = 'Guarda la revisión verificada en la carpeta autorizada de Drive.'; byId('chatForm').requestSubmit();
      });
    }
  }
  function progress(event) {
    if (!event || event.id <= cursor) return;
    cursor = event.id;
    if (!event.data?.text) return;
    text(event.data.text); node('li', event.data.text, byId('agentEvents'));
  }
  function showSources(sources) {
    const area = byId('agentSources'); if (!area) return; area.replaceChildren();
    if (!sources.length) return;
    const pane = details(area, `Fuentes · ${sources.filter(source => source.opened).length} consultadas`);
    const items = node('ol', null, pane, 'agent-event-list');
    sources.forEach(source => {
      const item = node('li', null, items);
      const title = node('a', source.title || source.final_url || source.url, item);
      const url = source.final_url || source.url;
      if (typeof url === 'string' && /^https?:\/\/[^\s]+$/i.test(url)) { title.href = url; title.target = '_blank'; title.rel = 'noopener noreferrer'; }
      node('p', source.opened ? (source.reading === 'complete' ? 'Lectura completa' : 'Lectura parcial') : 'Resultado del buscador · no abierto', item, 'agent-artifact-meta');
      if (source.excerpt || source.snippet) node('p', source.excerpt || source.snippet, item);
      if (source.opened) node('small', `Consulta: ${timestamp(source.retrieved_at)} · Publicación: ${source.publication_date || 'fecha desconocida'}`, item);
    });
  }
  async function snapshot() {
    if (!run) return;
    const expected = run.id, version = ++snapshotVersion;
    let data;
    try {
      const response = await fetch(run.status_url, {headers: {'Accept': 'application/json'}});
      if (!response.ok) throw new Error('Access unavailable');
      data = await response.json();
    } catch (error) {
      if (run?.id !== expected || version !== snapshotVersion) return;
      throw error;
    }
    if (run?.id !== expected || version !== snapshotVersion) return;
    run = {...run, ...data.run}; showExport(data.export, data.run); list(data.events).forEach(progress);
    byId('agentState').textContent = label(data.run.status); byId('agentActivity').dataset.state = data.run.status;
    byId('agentCancel').hidden = !live(data.run.status);
    if (byId('agentResume')) byId('agentResume').hidden = !data.run.resumable;
    const limitation = byId('agentLimitations'); limitation.replaceChildren();
    list(data.run.limitations).forEach(value => node('li', value, limitation)); limitation.hidden = !limitation.children.length;
    showOversight(data.receipt || data.result?.receipt || {}); revision = data.current_revision || null;
    showSources(list(data.sources));
    const operations = byId('agentOperations');
    if (operations) {
      operations.replaceChildren();
      if (data.infrastructure) node('p', 'El coste mostrado corresponde a APIs. El coste del sandbox y del tráfico no está disponible.', operations, 'agent-explanation');
      list(data.operations).forEach(operation => {
        const entry = details(operations, `${label(operation.name)} · ${label(operation.status)}`);
        if (typeof operation.details_url !== 'string' || !/^\/chat\/agent\/runs\/[0-9a-f-]+\/operations\/\d+\/$/.test(operation.details_url)) return;
        const control = button('Ver código y salida autorizada', entry, async () => {
          control.disabled = true;
          try {
            const response = await fetch(operation.details_url, {headers: {'Accept': 'application/json'}});
            if (!response.ok) throw new Error('Unavailable');
            const value = await response.json();
            node('pre', JSON.stringify(value, null, 2), entry, 'agent-code-output');
          } catch (_) { node('p', 'El detalle ya no está disponible con tus permisos actuales.', entry); }
        });
      });
    }
    const visible = list(data.artifacts).length ? data.artifacts : (revision ? [revision] : []);
    const nextKey = JSON.stringify([visible, data.export_enabled, live(data.run.status)]);
    if (nextKey !== artifactKey) {
      artifactKey = nextKey; const artifacts = byId('agentArtifacts'); artifacts.replaceChildren();
      visible.forEach(artifact => showArtifact(artifact, artifacts, data.export_enabled && !live(data.run.status)));
      if (!live(data.run.status)) artifacts.querySelector?.('.agent-artifact-actions')?.scrollIntoView?.({block: 'nearest'});
    }
    if (!live(data.run.status)) {
      stream?.close(); stream = null;
      if (list(data.events).length) text(data.events[data.events.length - 1].data.text);
      if (command && data.result && typeof window.renderResult === 'function') { window.renderResult(data.result, command); command = null; }
    }
    const failure = byId('agentFailure');
    if (failure) {
      const error = data.run.status === 'failed' && typeof data.result?.error === 'string' ? data.result.error.trim() : '';
      failure.textContent = error;
      failure.hidden = !error || error === byId('agentProgress').textContent.trim();
    }
    return data.run;
  }
  async function watch(next, submitted = null) {
    chosenRevision = null; if (byId('agentRevision')) byId('agentRevision').hidden = true;
    documentReference = null; pendingExport = null; mode = 'agent'; command = submitted; setMode(true);
    if (command) command.agentRun = next.id;
    byId('conversationMode')?.setAttribute('disabled', '');
    const panel = byId('agentActivity'); if (!panel) return;
    if (submitted?.userBubble) submitted.userBubble.after(panel);
    stream?.close(); stream = null;
    if (byId('agentFailure')) { byId('agentFailure').textContent = ''; byId('agentFailure').hidden = true; }
    if (run?.id !== next.id) { cursor = 0; artifactKey = ''; byId('agentEvents').replaceChildren(); byId('agentArtifacts').replaceChildren(); }
    run = next; setMode(true); byId('agentState').textContent = label(next.status); text('Petición recibida. Consultando el estado de la ejecución.');
    try {
      const state = await snapshot(); if (!state || !live(state.status)) return;
      const source = new EventSource(run.events_url + '?cursor=' + cursor); stream = source;
      const current = () => run?.id === next.id && stream === source;
      source.addEventListener('progress', message => {
        if (!current()) return;
        try {
          const event = JSON.parse(message.data); progress(event);
          if (['claimed', 'input', 'calculate', 'compose', 'render', 'verify', 'recalculate', 'rename', 'visual_pending', 'verified', 'draft', 'approval_pending', 'export_completed', 'export_uncertain', 'inference_completed', 'visual_reviewed', 'searching', 'reading', 'executing', 'installing', 'verifying'].includes(event.kind)) snapshot().catch(unavailable);
        } catch (_) { text('Se recibió un evento que no se pudo leer. Recarga el estado para continuar.'); }
      });
      source.addEventListener('terminal', () => { if (current()) { source.close(); snapshot().catch(unavailable); } });
      source.addEventListener('revoked', () => { if (current()) unavailable(); });
      source.onerror = () => { if (current()) text('Conexión interrumpida. Reconectando desde el último evento; el trabajo no se repite.'); };
    } catch (_) { unavailable(); }
  }
  function unavailable() {
    stream?.close(); stream = null;
    byId('agentCancel').hidden = true; byId('agentState').textContent = 'Estado no disponible'; byId('agentActivity').dataset.state = 'failed';
    byId('agentArtifacts').replaceChildren(); byId('agentExport')?.replaceChildren();
    byId('agentSummary')?.replaceChildren(); byId('agentTrace')?.replaceChildren(); revision = null; artifactKey = '';
    byId('agentSources')?.replaceChildren(); byId('agentOperations')?.replaceChildren(); chosenRevision = null;
    if (byId('agentFailure')) { byId('agentFailure').textContent = ''; byId('agentFailure').hidden = true; }
    text('El estado no está autorizado o no está disponible. Recarga el estado para comprobar el acceso.');
  }
  window.regulayAgent = {
    capture(file) {
      const selected = mode || byId('conversationMode')?.value;
      if (selected !== 'agent') return {};
      if (pendingExport) return {mode: 'agent', ...pendingExport};
      const selectedRevision = professional() ? chosenRevision : revision;
      return {mode: 'agent', documentReference: !file && documentReference,
        artifactId: !file && !documentReference && selectedRevision?.logical_id, baseRevision: !file && !documentReference && selectedRevision?.id};
    }, watch, renderReceipt
  };
  function showExport(proposal, state) {
    const area = byId('agentExport'); if (!area) return; area.replaceChildren(); if (!proposal) return;
    const card = node('article', null, area, 'agent-artifact'); node('h3', 'Guardar revisión en Google Drive', card);
    const values = node('dl', null, card, 'agent-definition-list');
    const statuses = {pending: 'Esperando aprobación', approved: 'Aprobado', rejected: 'Rechazado', intent: 'Guardando; resultado pendiente', uncertain: 'Resultado por confirmar', completed: 'Guardado confirmado'};
    [['Cuenta', proposal.account], ['Carpeta', proposal.folder], ['Nombre', proposal.name], ['Revisión', proposal.revision],
      ['Efecto', 'Crear un archivo nuevo'], ['Contenido', `${proposal.bytes} bytes`], ['SHA-256 del contenido', proposal.sha256],
      ['Estado', statuses[proposal.status] || proposal.status], ['Caduca', timestamp(proposal.expires_at)]].forEach(([name, value]) => detail(values, name, value));
    if (artifactUrl(proposal.preview_url, 'download')) {
      const content = node('a', 'Revisar el contenido exacto antes de aprobar', card, 'd-block small mb-2'); content.href = proposal.preview_url;
    }
    if (proposal.status === 'pending' && state.status === 'active' && Date.parse(proposal.expires_at) > Date.now()) {
      [['approve', 'Aprobar esta exportación'], ['reject', 'Rechazar']].forEach(([decision, title]) => {
        const control = button(title, card, async () => {
          control.disabled = true;
          try {
            const response = await fetch(proposal.decision_url, {method: 'POST', headers: {'Content-Type': 'application/json', 'X-CSRFToken': csrf()}, body: JSON.stringify({binding: proposal.binding, decision})});
            if (!response.ok) throw new Error('Approval changed'); await snapshot();
          } catch (_) { text('La propuesta ha caducado o sus permisos han cambiado. Recarga para comprobar el estado.'); }
        }, 'btn btn-outline-primary btn-sm me-2');
      });
    }
    if (proposal.status === 'uncertain' && state.status === 'interrupted') {
      const recover = button('Reconciliar el resultado de la exportación', card, async () => {
        recover.disabled = true;
        try {
          const response = await fetch(`/chat/agent/runs/${state.id}/recover-export/`, {method: 'POST', headers: {'X-CSRFToken': csrf()}});
          if (!response.ok) throw new Error('Recovery unavailable'); await watch(state);
        } catch (_) { text('No se pudo recuperar el resultado. Comprueba los permisos y la aprobación.'); recover.disabled = false; }
      });
    }
  }
  function setMode(active) {
    byId('agentActivity')?.classList.toggle('d-none', !active); byId('chatContainer')?.classList.toggle('agent-conversation', active);
    if (byId('attachmentHint')) byId('attachmentHint').textContent = active ?
      (professional() ? 'Investiga, calcula o crea archivos. Puedes adjuntar datos y documentos; elige «Editar esta revisión» para modificar un entregable.' :
        'Puedes crear sin adjunto. Para transformar datos: CSV o XLSX con item y amount_cents. Las revisiones conservan el archivo.') : 'Adjunta un documento compatible para el chat.';
    if (byId('fileInput')) byId('fileInput').accept = active && !professional() ? '.csv,.xlsx' : '.txt,.pdf,.docx,.pptx,.csv,.json,.py,.js,.md,.xlsx';
    if (byId('prompt')) byId('prompt').placeholder = active ? (professional() ? 'Describe qué quieres investigar, calcular o crear…' : 'Describe el documento, su formato, idioma y extensión…') : 'Escribe tu mensaje…';
  }
  document.addEventListener('DOMContentLoaded', () => {
    const sidebar = byId('conversationSidebar'), toggle = byId('conversationSidebarToggle');
    if (sidebar && toggle) {
      let collapsed = window.matchMedia?.('(max-width: 900px)').matches || false;
      const updateSidebar = () => { sidebar.hidden = collapsed; toggle.setAttribute('aria-expanded', String(!collapsed)); toggle.textContent = collapsed ? 'Mostrar conversaciones' : 'Ocultar conversaciones'; };
      updateSidebar(); toggle.addEventListener('click', () => { collapsed = !collapsed; updateSidebar(); });
    }
    byId('agentRefresh')?.addEventListener('click', () => { if (run) snapshot().catch(unavailable); });
    byId('agentResume')?.addEventListener('click', async () => {
      if (!run?.resumable) return;
      byId('agentResume').disabled = true;
      try {
        const response = await fetch(run.resume_url, {method: 'POST', headers: {'X-CSRFToken': csrf()}});
        if (!response.ok) throw new Error('Resume unavailable');
        const value = await response.json(); await watch(value.run);
      } catch (_) { text('No se puede reanudar: el punto guardado, los permisos o el presupuesto ya no son válidos.'); }
      finally { byId('agentResume').disabled = false; }
    });
    byId('agentDocumentSearch')?.addEventListener('click', async () => {
      const area = byId('agentDocumentResults'), control = byId('agentDocumentSearch'); control.disabled = true; documentReference = null; area.replaceChildren();
      try {
        const response = await fetch('/chat/agent/documents/search/', {method: 'POST', headers: {'Content-Type': 'application/json', 'X-CSRFToken': csrf()}, body: JSON.stringify({query: byId('agentDocumentQuery').value})});
        if (!response.ok) throw new Error('Unavailable'); const data = await response.json();
        if (!list(data.documents).length) node('p', 'No hay archivos compatibles en la carpeta autorizada.', area);
        list(data.documents).forEach(doc => {
          button(doc.label + ' · usar como entrada', area, () => { documentReference = doc.reference; area.replaceChildren(); node('p', doc.label + ' seleccionado. Escribe la petición y envíala.', area); byId('prompt').focus(); });
        });
      } catch (_) { node('p', 'Conector no disponible. Requiere una cuenta autorizada por el administrador.', area); }
      finally { control.disabled = false; }
    });
    let initial = null;
    try { initial = JSON.parse(byId('agent-initial')?.textContent || 'null'); } catch (_) { text('No se pudo restaurar la ejecución. Recarga la página.'); }
    if (initial) watch(initial);
    else if (byId('conversationMode')?.value === 'agent') setMode(true);
    byId('conversationMode')?.addEventListener('change', event => {
      setMode(event.target.value === 'agent'); byId('agentCancel').hidden = true;
      text('Crea un informe Word/PDF, una hoja Excel o una presentación a partir de tu petición. Los datos ficticios requieren una solicitud expresa.');
    });
    byId('agentCancel')?.addEventListener('click', async () => {
      if (!run) return; byId('agentCancel').disabled = true;
      try {
        const response = await fetch(run.cancel_url, {method: 'POST', headers: {'X-CSRFToken': csrf()}});
        if (!response.ok) throw new Error('Cancel unavailable'); await snapshot();
      } catch (_) { unavailable(); }
      finally { byId('agentCancel').disabled = false; }
    });
  });
  window.addEventListener('pagehide', () => stream?.close());
})();
