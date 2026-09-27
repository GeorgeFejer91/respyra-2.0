// A coalesced live preview of the accepted raw inlet. XDF keeps the full signal.
export const MONITOR_HTML = `<section id="lsl-monitor" aria-label="Live LSL data and markers">
  <h2 data-measure>LSL data</h2>
  <p id="monitor-source" data-measure>Select a live raw Force stream in Experiment controls.</p>
  <label><span data-measure>Channel</span><select id="monitor-channel" disabled></select></label>
  <p id="monitor-value" data-measure>Waiting for samples.</p>
  <svg id="monitor-trace" viewBox="0 0 600 140" role="img" aria-label="Live channel preview over the last ten seconds">
    <path class="trace-grid" d="M0 1H600 M0 70H600 M0 139H600"/>
    <path id="trace-markers" class="trace-markers"/><path id="trace-line" class="trace-line"/>
  </svg>
  <div class="trace-scale"><span id="trace-range" data-measure>—</span><span data-measure>Last 10 s · preview</span></div>
  <h2 data-measure>Recent markers</h2>
  <p id="monitor-marker-state" data-measure>Waiting for marker outlet.</p>
  <ol id="monitor-markers" aria-label="Four latest published markers"></ol>
</section>`;

export function traceGeometry(points) {
  if (!points.length) return {path:'', min:null, max:null};
  const end = points.at(-1)[0], start = end - 10;
  const visible = points.filter(([time]) => time >= start);
  const values = visible.map(([, value]) => value);
  const low = Math.min(...values), high = Math.max(...values);
  const padding = Math.max((high - low) * .1, .01);
  const min = low - padding, max = high + padding;
  let previous;
  const path = visible.map(([time, value]) => {
    const command = previous === undefined || time - previous > 1.5 ? 'M' : 'L';
    previous = time;
    return `${command}${((time-start)*60).toFixed(2)},${(139-(value-min)/(max-min)*138).toFixed(2)}`;
  }).join(' ');
  return {path,min,max,start,end};
}

export function mountLslMonitor(root) {
  const byId = id => root.querySelector('#' + id);
  let progress = {}, online = true, signature = '', key = '', points = [];
  function render(next, connected = online) {
    progress = next; online = connected;
    const health = progress.health, preview = health?.preview;
    const channels = preview?.channels || [];
    const nextSignature = JSON.stringify([preview?.source_id, channels.map(({index,label,unit}) => [index,label,unit])]);
    if (nextSignature !== signature) {
      signature = nextSignature;
      byId('monitor-channel').replaceChildren(...channels.map(channel => {
        const option = document.createElement('option'); option.value = String(channel.index);
        option.textContent = channel.label + (channel.unit ? ` (${channel.unit})` : ''); return option;
      }));
      byId('monitor-channel').value = String(preview?.force_index);
    }
    byId('monitor-channel').disabled = !online || !channels.length;
    const channel = channels.find(c => String(c.index) === byId('monitor-channel').value);
    const nextKey = `${preview?.source_id}:${channel?.index}`;
    if (nextKey !== key) { key = nextKey; points = []; }
    if (online && Number.isFinite(channel?.value) && Number.isFinite(preview?.lsl_time) &&
        preview.lsl_time > (points.at(-1)?.[0] ?? -Infinity)) {
      points.push([preview.lsl_time,channel.value]);
      points = points.filter(([time]) => time >= preview.lsl_time - 10).slice(-100);
    }
    const status = !online ? 'Updates paused' : {live:'Live',stale:'Waiting for samples',lost:'Signal lost',disconnected:'Disconnected'}[health?.signal] || 'Waiting for samples';
    byId('monitor-source').textContent = preview ? preview.name : 'Select a live raw Force stream in Experiment controls.';
    byId('monitor-value').textContent = `${status} · ${Number.isFinite(channel?.value) ? channel.value.toFixed(3) + ' ' + channel.unit : 'No channel data'}`;
    const geometry = traceGeometry(points);
    byId('trace-line').setAttribute('d',geometry.path);
    byId('trace-range').textContent = geometry.min === null ? '—' : `${geometry.min.toFixed(2)}–${geometry.max.toFixed(2)} ${channel?.unit || ''}`;
    byId('trace-markers').setAttribute('d',(progress.recent || []).filter(marker =>
      Number.isFinite(marker.lsl_time) && marker.lsl_time >= geometry.start && marker.lsl_time <= geometry.end
    ).map(marker => { const x = ((marker.lsl_time-geometry.start)*60).toFixed(2); return `M${x},0V140`; }).join(' '));
    byId('monitor-marker-state').textContent = progress.markers ? `${progress.markers.name} · ${progress.markers.emitted} sent` : 'Waiting for marker outlet.';
    byId('monitor-markers').replaceChildren(...(progress.recent || []).slice(-4).reverse().map(marker => {
      const item = document.createElement('li'); item.dataset.measure = '';
      item.textContent = `${marker.seq} · ${marker.event}`; return item;
    }));
  }
  byId('monitor-channel').addEventListener('change', () => render(progress));
  return {render, clear() { points = []; key = ''; render({}); }};
}
