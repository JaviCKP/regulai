/* User preview is a separate authorized projection; never model context. */
(() => {
  let mode = null, revision = null, stream = null, run = null, cursor = 0, command = null, documentReference = null, pendingExport = null;
  const byId = id => document.getElementById(id);
  const csrf = () => document.querySelector('[name=csrfmiddlewaretoken]').value;
  const live = status => ['queued', 'active', 'outcome_unknown'].includes(status);
  const text = value => {
    if (byId('agentProgress')) byId('agentProgress').textContent = value;
  };
  function node(tag, value, parent) {
    const element = document.createElement(tag);
    if (value != null) element.textContent = String(value);
    if (parent) parent.appendChild(element);
    return element;
  }
  function showArtifact(artifact, parent, canExport) {
    const card = node('article', null, parent);
    card.className = 'border-top pt-2 mt-2';
    const heading = node('strong', artifact.preview.title, card);
    heading.style.overflowWrap = 'anywhere';
    if (artifact.status === 'verified' && canExport) {
      const area = node('div', null, card);
      area.className = 'd-flex flex-wrap gap-2 my-2';
      const label = node('label', 'Nombre al guardar en Drive', area);
      const name = node('input', null, label);
      name.className = 'form-control form-control-sm'; name.maxLength = 120;
      name.value = `informe-r${artifact.revision}.${artifact.format || 'xlsx'}`;
      const save = node('button', 'Preparar exportación a Drive', area);
      save.type = 'button'; save.className = 'btn btn-outline-primary btn-sm';
      save.onclick = () => {
        pendingExport = {artifactId: artifact.logical_id, baseRevision: artifact.id, exportName: name.value};
        byId('prompt').value = 'Guarda la revisión verificada en la carpeta autorizada de Drive.';
        byId('chatForm').requestSubmit();
      };
    }
    if (artifact.format && artifact.format !== 'xlsx') {
      const pending = artifact.status !== 'verified';
      const pageName = artifact.format === 'pptx' ? 'Diapositiva' : 'Página';
      node('p', `Revisión ${artifact.revision} · ${artifact.format.toUpperCase()} · ${pending ? 'Pendiente de revisión visual' : 'Verificado y revisado'}`, card).className = 'small text-muted';
      let loaded = 0;
      const pages = node('div', null, card);
      pages.className = 'agent-document-pages';
      let button;
      artifact.preview.pages.forEach((url, index) => {
        if (!/^\/chat\/agent\/artifacts\/[0-9a-f-]+\/pages\/\d+\/$/.test(url)) return;
        const figure = node('figure', null, pages);
        node('figcaption', `${pageName} ${index + 1} de ${artifact.preview.pages.length}`, figure).className = 'small';
        const img = node('img', null, figure);
        img.alt = `${pageName} ${index + 1} del documento para revisión visual`;
        img.style.cssText = 'width:100%;height:auto;border:1px solid #d9d9d9';
        img.onload = () => { loaded++; if (button) button.disabled = loaded !== artifact.preview.pages.length; };
        img.src = url;
        const full = node('a', `Abrir ${pageName.toLowerCase()} a tamaño completo`, figure);
        full.href = url; full.target = '_blank'; full.rel = 'noopener';
      });
      if (pending) {
        node('p', 'Revisa todas las páginas: texto legible, tablas completas, tildes y símbolos correctos, sin cortes, solapamientos ni restos de plantilla.', card).className = 'small';
        button = node('button', 'He revisado todas las páginas: publicar esta revisión', card);
        button.type = 'button'; button.className = 'btn btn-primary btn-sm'; button.disabled = true;
        button.onclick = async () => {
          button.disabled = true;
          try {
            const response = await fetch(artifact.review_url, {method: 'POST',
              headers: {'Content-Type': 'application/json', 'X-CSRFToken': csrf()},
              body: JSON.stringify({sha256: artifact.sha256, page_sha256: artifact.page_sha256, checks: artifact.review_checks})});
            if (!response.ok) throw new Error('Review unavailable');
            text('Revisión visual registrada. Finalizando la entrega.');
          } catch (_) { text('No se pudo registrar la revisión. Comprueba que la ejecución siga activa.'); }
        };
      } else {
        const link = node('a', `Descargar ${artifact.format.toUpperCase()} verificado`, card);
        link.href = artifact.download_url; link.className = 'btn btn-primary btn-sm'; link.setAttribute('download', '');
        node('p', artifact.format === 'pptx' ? 'Puedes cambiar el título o el texto de una diapositiva en el siguiente mensaje.' : 'En el siguiente mensaje puedes cambiar el título o el resumen, o pedir la versión PDF.', card).className = 'small mt-2';
      }
      return;
    }
    node('p', `Revisión ${artifact.revision} · Fórmulas y totales verificados`, card).className = 'small text-muted mb-1';
    const area = node('div', null, card);
    area.className = 'table-responsive';
    const table = node('table', null, area);
    table.className = 'table table-sm small';
    const header = node('tr', null, node('thead', null, table));
    artifact.preview.headers.forEach(value => node('th', value, header).scope = 'col');
    const body = node('tbody', null, table);
    artifact.preview.rows.forEach(row => {
      const tr = node('tr', null, body);
      row.forEach(value => {
        const cell = node('td', value, tr);
        cell.style.overflowWrap = 'anywhere';
        cell.style.maxWidth = '24rem';
      });
    });
    node('p', `Total: ${artifact.preview.total_euros} € · ${artifact.preview.rows_total} filas`, card).className = 'small fw-bold';
    const link = node('a', 'Descargar XLSX verificado', card);
    if (/^\/chat\/agent\/artifacts\/[0-9a-f-]+\/download\/$/.test(artifact.download_url)) link.href = artifact.download_url;
    link.className = 'btn btn-primary btn-sm';
    link.setAttribute('download', '');
    node('p', 'Para cambiar el título, escríbelo en el siguiente mensaje. Se conservarán los cálculos y el formato.', card).className = 'small mt-2 mb-0';
  }
  function progress(event) {
    if (event.id <= cursor) return;
    cursor = event.id;
    text(event.data.text);
    node('li', event.data.text, byId('agentEvents'));
  }
  async function snapshot() {
    const expected = run.id;
    const response = await fetch(run.status_url, {headers: {'Accept': 'application/json'}});
    if (!response.ok) throw new Error('Access unavailable');
    const data = await response.json();
    if (run.id !== expected) return;
    showExport(data.export, data.run);
    data.events.forEach(progress);
    byId('agentCancel').hidden = !live(data.run.status);
    revision = data.current_revision || null;
    const visible = data.artifacts.length ? data.artifacts : (revision ? [revision] : []);
    if (visible.length) {
      const artifacts = byId('agentArtifacts');
      artifacts.replaceChildren();
      visible.forEach(artifact => showArtifact(artifact, artifacts, data.export_enabled && !live(data.run.status)));
    }
    if (!live(data.run.status)) {
      stream?.close();
      stream = null;
      if (data.events.length) text(data.events[data.events.length - 1].data.text);
      if (command && data.result && typeof window.renderResult === 'function') {
        window.renderResult(data.result, command);
        command = null;
      }
    }
    return data.run;
  }
  async function watch(next, submitted = null) {
    documentReference = null;
    pendingExport = null;
    mode = 'agent';
    command = submitted;
    byId('attachmentHint').textContent = 'CSV/XLSX: item y amount_cents. El archivo se conserva para las revisiones.';
    byId('conversationMode')?.setAttribute('disabled', '');
    const panel = byId('agentActivity');
    if (!panel) return;
    panel.classList.remove('d-none');
    stream?.close();
    if (run?.id !== next.id) {
      cursor = 0;
      byId('agentEvents').replaceChildren();
    }
    run = next;
    text('Petición aceptada. Esperando un entorno limpio disponible.');
    try {
      const state = await snapshot();
      if (!state || !live(state.status)) return;
      stream = new EventSource(run.events_url + '?cursor=' + cursor);
      stream.addEventListener('progress', message => {
        const event = JSON.parse(message.data);
        progress(event);
        if (['visual_pending', 'approval_pending', 'export_completed', 'export_uncertain'].includes(event.kind)) snapshot().catch(unavailable);
      });
      stream.addEventListener('terminal', () => { stream?.close(); snapshot().catch(unavailable); });
      stream.addEventListener('revoked', unavailable);
      stream.onerror = () => text('Conexión de actividad interrumpida. Reconectando desde el último evento; el trabajo no se repite.');
    } catch (_) { unavailable(); }
  }
  function unavailable() {
    stream?.close();
    stream = null;
    byId('agentCancel').hidden = true;
    byId('agentArtifacts').replaceChildren();
    byId('agentExport')?.replaceChildren();
    revision = null;
    text('El estado ya no está autorizado o no está disponible. Recarga el chat para comprobar el acceso.');
  }
  window.regulayAgent = {
    capture(file) {
      const selected = mode || byId('conversationMode')?.value;
      if (selected !== 'agent') return {};
      if (pendingExport) return {mode: 'agent', ...pendingExport};
      return {mode: 'agent', documentReference: !file && documentReference,
        artifactId: !file && !documentReference && revision?.logical_id,
        baseRevision: !file && !documentReference && revision?.id};
    }, watch
  };
  function showExport(proposal, state) {
    const area = byId('agentExport');
    if (!area) return;
    area.replaceChildren();
    if (!proposal) return;
    const card = node('article', null, area);
    card.className = 'border rounded p-2 mt-2';
    node('strong', 'Guardar revisión en Google Drive', card);
    const details = node('dl', null, card); details.className = 'small my-2';
    const statuses = {pending: 'Esperando aprobación', approved: 'Aprobado', rejected: 'Rechazado',
      intent: 'Guardando; resultado pendiente', uncertain: 'Resultado por confirmar', completed: 'Guardado confirmado'};
    for (const [key, value] of [['Cuenta', proposal.account], ['Carpeta', proposal.folder],
      ['Nombre', proposal.name], ['Revisión', proposal.revision], ['Efecto', 'Crear un archivo nuevo'],
      ['Contenido', `${proposal.bytes} bytes`], ['SHA-256 del contenido', proposal.sha256],
      ['Estado', statuses[proposal.status] || proposal.status], ['Caduca', new Date(proposal.expires_at).toLocaleString('es-ES')]]) {
      node('dt', key, details); const item = node('dd', value, details); item.style.overflowWrap = 'anywhere';
    }
    const content = node('a', 'Revisar el contenido exacto antes de aprobar', card);
    content.href = proposal.preview_url; content.className = 'd-block small mb-2';
    if (proposal.status === 'pending' && state.status === 'active' && Date.parse(proposal.expires_at) > Date.now()) {
      for (const [decision, label] of [['approve', 'Aprobar esta exportación'], ['reject', 'Rechazar']]) {
        const button = node('button', label, card); button.type = 'button'; button.className = 'btn btn-outline-primary btn-sm me-2';
        button.onclick = async () => {
          button.disabled = true;
          try {
            const response = await fetch(proposal.decision_url, {method: 'POST',
              headers: {'Content-Type': 'application/json', 'X-CSRFToken': csrf()},
              body: JSON.stringify({binding: proposal.binding, decision})});
            if (!response.ok) throw new Error('Approval changed');
            await snapshot();
          } catch (_) { text('La propuesta ha caducado o sus permisos han cambiado. Recarga para comprobar el estado.'); }
        };
      }
    }
    if (proposal.status === 'uncertain' && state.status === 'interrupted') {
      const recover = node('button', 'Reconciliar el resultado de esta exportación', card);
      recover.type = 'button'; recover.className = 'btn btn-outline-primary btn-sm';
      recover.onclick = async () => {
        recover.disabled = true;
        const response = await fetch(`/chat/agent/runs/${state.id}/recover-export/`, {
          method: 'POST', headers: {'X-CSRFToken': csrf()}});
        if (response.ok) await watch(state); else text('La recuperación requiere permisos y aprobación vigentes.');
      };
    }
  }
  document.addEventListener('DOMContentLoaded', () => {
    byId('agentDocumentSearch')?.addEventListener('click', async () => {
      const area = byId('agentDocumentResults'), button = byId('agentDocumentSearch');
      button.disabled = true; documentReference = null; area.replaceChildren();
      try {
        const response = await fetch('/chat/agent/documents/search/', {method: 'POST',
          headers: {'Content-Type': 'application/json', 'X-CSRFToken': csrf()},
          body: JSON.stringify({query: byId('agentDocumentQuery').value})});
        if (!response.ok) throw new Error('Unavailable');
        const data = await response.json();
        if (!data.documents.length) node('p', 'No hay entradas compatibles autorizadas.', area);
        data.documents.forEach(doc => {
          const select = node('button', doc.label + ' · usar como entrada', area);
          select.type = 'button'; select.className = 'btn btn-outline-primary btn-sm me-2';
          select.onclick = () => { documentReference = doc.reference; area.replaceChildren();
            node('p', doc.label + ' seleccionado. Escribe la petición del informe y envíala.', area); };
        });
      } catch (_) { node('p', 'Conector no disponible. Requiere una cuenta autorizada por el administrador.', area); }
      finally { button.disabled = false; }
    });
    const initial = JSON.parse(byId('agent-initial')?.textContent || 'null');
    if (initial) watch(initial);
    byId('conversationMode')?.addEventListener('change', event => {
      const active = event.target.value === 'agent';
      byId('agentActivity')?.classList.toggle('d-none', !active);
      byId('agentCancel').hidden = true;
      text('Adjunta un CSV o XLSX sintético para crear una hoja Excel, un informe Word/PDF o una presentación.');
      byId('fileInput').accept = active ? '.csv,.xlsx' : '.txt,.pdf,.docx,.csv,.json,.py,.js,.md,.xlsx';
      byId('attachmentHint').textContent = active ? 'CSV/XLSX: item y amount_cents. El archivo se conserva para las revisiones.' : 'Adjunta un documento compatible para el chat.';
    });
    byId('agentCancel')?.addEventListener('click', async () => {
      if (!run) return;
      try {
        const response = await fetch(run.cancel_url, {method: 'POST', headers: {'X-CSRFToken': csrf()}});
        if (!response.ok) throw new Error('Cancel unavailable');
        await snapshot();
      } catch (_) { unavailable(); }
    });
  });
  window.addEventListener('pagehide', () => stream?.close());
})();
