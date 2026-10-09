'use strict';
const $ = selector => document.querySelector(selector);
let state, meta, version, selectedId = null, replyId = null;
const preferenceKey = 'portfolio-forge.dropdown-preferences.v1';
const rememberedDropdowns = new Set(['new-project', 'new-type', 'project-filter', 'status-filter']);
let dropdownPreferences = {};
try {
    const stored = JSON.parse(localStorage.getItem(preferenceKey) || '{}');
    if (stored && typeof stored === 'object' && !Array.isArray(stored)) {
        for (const id of rememberedDropdowns) {
            if (typeof stored[id] === 'string') dropdownPreferences[id] = stored[id];
        }
    }
} catch { /* Storage unavailable or invalid: use the normal defaults. */ }
function rememberDropdown(element) {
    dropdownPreferences[element.id] = element.value;
    try { localStorage.setItem(preferenceKey, JSON.stringify(dropdownPreferences)); }
    catch { /* Keep this session usable even when browser storage is blocked. */ }
}
function restoreDropdown(element) {
    const saved = dropdownPreferences[element.id];
    if (typeof saved === 'string' && [...element.options].some(option => option.value === saved)) {
        element.value = saved;
    }
}

function notice(message, error = false) { $('#notice').textContent = message; $('#notice').classList.toggle('error', error); }
function options(element, values, preserve = true) {
    const old = element.value;
    element.replaceChildren();
    values.forEach(([value, label]) => { const option = document.createElement('option'); option.value = value; option.textContent = label; element.append(option); });
    if (preserve && values.some(([value]) => value === old)) element.value = old;
    if (rememberedDropdowns.has(element.id)) restoreDropdown(element);
}
const pairs = values => values.map(value => [value, value]);
function projectName(id) { return state.projects.find(project => project.id === id)?.name || 'Unknown project'; }
function selected() { return state.pbis.find(item => item.id === selectedId); }
async function fetchJSON(url, config = {}) {
    const response = await fetch(url, config);
    const result = await response.json();
    if (!response.ok) throw new Error(result.error || `HTTP ${response.status}`);
    return [result, response.headers.get('ETag')];
}
async function load() {
    [state, version] = await fetchJSON('/api/state');
    if (!meta) [meta] = await fetchJSON('/api/meta');
    render();
    if (selectedId) renderDetail();
    notice('Portfolio loaded. Saved changes persist on this computer.');
}
async function mutate(path, body, method = 'POST') {
    [state, version] = await fetchJSON(path, { method, headers: { 'Content-Type': 'application/json', 'If-Match': version }, body: JSON.stringify(body) });
    render();
    if (selectedId) renderDetail();
    notice('Saved.');
}
function render() {
    const projects = state.projects.map(project => [project.id, project.name]);
    options($('#new-project'), projects);
    options($('#project-filter'), [['', 'All projects'], ...projects]);
    options($('#status-filter'), [['', 'All statuses'], ...pairs(meta.statuses)]);
    options($('#new-type'), pairs(meta.types));
    $('#root').textContent = `Project parent: ${meta.portfolioRoot}`;
    $('#projects').replaceChildren();
    state.projects.forEach(project => { const li = document.createElement('li'); li.textContent = `${project.name} Â· ${project.folder}`; $('#projects').append(li); });
    renderBoard();
}
function renderBoard() {
    const project = $('#project-filter').value, status = $('#status-filter').value, search = $('#search').value.toLowerCase();
    const items = state.pbis.filter(item => (!project || item.projectId === project) && (!status || item.status === status) && `${item.title} ${item.description}`.toLowerCase().includes(search));
    $('#count').textContent = `${items.length} of ${state.pbis.length} PBIs`;
    const board = $('#board'); board.replaceChildren();
    if (!items.length) { const p = document.createElement('p'); p.className = 'muted'; p.textContent = 'No PBIs match. Create one to start your portfolio.'; board.append(p); }
    meta.statuses.forEach(status => {
        const group = items.filter(item => item.status === status);
        if (!group.length) return;
        const heading = document.createElement('h3'); heading.className = 'group-title'; heading.textContent = `${status} (${group.length})`; board.append(heading);
        group.sort((a, b) => b.number - a.number).forEach(item => {
            const button = document.createElement('button'); button.className = 'pbi';
            const title = document.createElement('strong'); title.textContent = `PBI-${item.number}: ${item.title}`;
            const description = document.createElement('small'); description.textContent = `${projectName(item.projectId)} Â· ${item.type} Â· ${item.assignedAgent} Â· ${item.areas.join(', ') || 'Awaiting classification'}`;
            button.append(title, description); button.addEventListener('click', () => { selectedId = item.id; replyId = null; $('#comment-form').reset(); renderDetail(); $('#detail-title').focus(); $('#detail').scrollIntoView({ behavior: 'smooth' }); }); board.append(button);
        });
    });
}
function renderDetail() {
    const item = selected(); if (!item) { $('#detail').hidden = true; return; }
    $('#detail').hidden = false; $('#detail-title').textContent = `PBI-${item.number}`;
    options($('#edit-project'), state.projects.map(p => [p.id, p.name]), false);
    options($('#edit-type'), pairs(meta.types), false); options($('#edit-status'), pairs(meta.statuses), false); options($('#edit-agent'), pairs(meta.agents), false);
    const form = $('#edit-pbi');
    for (const field of ['title', 'projectId', 'type', 'status', 'assignedAgent', 'description', 'acceptanceCriteria', 'implementationPlan', 'verificationPlan', 'result']) form.elements[field].value = item[field];
    $('#areas').replaceChildren();
    meta.areas.forEach(area => { const label = document.createElement('label'), checkbox = document.createElement('input'); checkbox.type = 'checkbox'; checkbox.name = 'areas'; checkbox.value = area; checkbox.checked = item.areas.includes(area); label.append(checkbox, document.createTextNode(area)); $('#areas').append(label); });
    options($('#dependencies'), state.pbis.filter(p => p.id !== item.id).map(p => [p.id, `PBI-${p.number}: ${p.title}`]), false);
    [...$('#dependencies').options].forEach(option => { option.selected = item.dependencies.includes(option.value); });
    $('#comments').replaceChildren();
    if (!item.comments.length) $('#comments').textContent = 'No discussion yet.';
    item.comments.forEach(comment => {
        const article = document.createElement('article'); article.className = 'comment' + (comment.parentMessageId ? ' reply' : '');
        const header = document.createElement('strong'); header.textContent = `${comment.author} Â· ${new Date(comment.createdAt).toLocaleString()}`;
        const body = document.createElement('p'); body.textContent = comment.body;
        if (comment.parentMessageId) { const parent = item.comments.find(c => c.id === comment.parentMessageId); const context = document.createElement('small'); context.textContent = `Reply to ${parent?.author || 'comment'}: ${parent?.body.slice(0, 90) || ''}`; article.append(context, document.createElement('br')); }
        const button = document.createElement('button'); button.type = 'button'; button.className = 'secondary'; button.textContent = 'Reply'; button.onclick = () => { replyId = comment.id; $('#reply-label').textContent = `Replying to ${comment.author}: ${comment.body.slice(0, 90)}`; $('#comment-form textarea').focus(); };
        article.append(header, body, button); $('#comments').append(article);
    });
    $('#history').replaceChildren(); item.history.forEach(event => { const li = document.createElement('li'); li.textContent = `${new Date(event.at).toLocaleString()} Â· ${event.actor}: ${event.action}`; $('#history').append(li); });
}
async function handle(event, action) {
    event.preventDefault(); const button = event.submitter; if (button) button.disabled = true;
    try { await action(); } catch (error) { notice(error.message, true); } finally { if (button) button.disabled = false; }
}
$('#project-form').onsubmit = event => handle(event, async () => { await mutate('/api/projects', Object.fromEntries(new FormData(event.target))); event.target.reset(); });
$('#new-pbi').onsubmit = event => handle(event, async () => { await mutate('/api/pbis', Object.fromEntries(new FormData(event.target))); selectedId = state.pbis.at(-1).id; replyId = null; event.target.reset(); restoreDropdown($('#new-project')); restoreDropdown($('#new-type')); renderDetail(); });
$('#edit-pbi').onsubmit = event => handle(event, async () => { const data = Object.fromEntries(new FormData(event.target)); data.areas = new FormData(event.target).getAll('areas'); data.dependencies = new FormData(event.target).getAll('dependencies'); data.actor = 'Owner'; await mutate(`/api/pbis/${selectedId}`, data, 'PATCH'); });
$('#comment-form').onsubmit = event => handle(event, async () => { await mutate(`/api/pbis/${selectedId}/comments`, { actor: 'Owner', body: event.target.elements.body.value, parentMessageId: replyId }); replyId = null; $('#reply-label').textContent = 'New comment'; event.target.reset(); });
$('#cancel-reply').onclick = () => { replyId = null; $('#reply-label').textContent = 'New comment'; };
$('#close').onclick = () => { selectedId = null; replyId = null; $('#detail').hidden = true; };
$('#refresh').onclick = async () => { if (!confirm('Refresh the portfolio? Unsaved edits will be discarded.')) return; try { await load(); } catch (error) { notice(error.message, true); } };
for (const id of ['#project-filter', '#status-filter', '#search']) $(id).addEventListener('input', () => { if (state) renderBoard(); });
for (const id of rememberedDropdowns) {
    document.getElementById(id).addEventListener('change', event => rememberDropdown(event.target));
}
load().catch(error => notice(error.message, true));