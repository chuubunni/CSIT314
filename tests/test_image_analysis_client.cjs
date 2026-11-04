/* Behaviour checks for image-analysis suggestions and stale response handling. */
const fs = require('node:fs');
const vm = require('node:vm');
const assert = require('node:assert/strict');

function element(value = '') {
  return {value, hidden: true, disabled: false, textContent: '', checked: false,
    listeners: {}, addEventListener(name, fn) { this.listeners[name] = fn; },
    focus() { this.focused = true; }};
}
const input = element(); input.files = [{name: 'original.jpg'}];
const title = element('My manual title');
const description = element('My manual description');
const modern = element(); modern.checked = false;
const rustic = element(); rustic.checked = true;
modern.closest = () => ({textContent: ' Modern '});
rustic.closest = () => ({textContent: ' Rustic '});
const form = {
  querySelector(selector) { return {'#images': input, '#title': title, '#description': description}[selector]; },
  querySelectorAll() { return [modern, rustic]; },
};
const selectors = ['analyse-image','apply-analysis','analysis-status','analysis-preview',
  'analysis-title','analysis-description','analysis-category'];
const nodes = Object.fromEntries(selectors.map(n => [`[data-${n}]`, element()]));
const panel = {
  dataset: {endpoint: '/api/analyze-image', formToken: 'session-token'},
  closest() { return form; }, querySelector(selector) { return nodes[selector]; },
  setAttribute() {}, removeAttribute() {},
};
let nextResponse = async () => ({ok: true, json: async () => ({title:'AI title',description:'AI description',category:'Modern'})});
let submitted;
const context = {
  document: {querySelectorAll() { return [panel]; }}, console, AbortController,
  setTimeout() { return 1; }, clearTimeout() {},
  FormData: class { constructor() { this.values = {}; } append(k,v) { this.values[k] = v; } },
  async fetch(url, options) { submitted = {url, options}; return nextResponse(); },
};
vm.createContext(context);
vm.runInContext(fs.readFileSync('idfinder/static/image_analysis.js', 'utf8'), context);
(async () => {
  await nodes['[data-analyse-image]'].listeners.click();
  assert.equal(submitted.options.body.values.image, input.files[0]);
  assert.equal(submitted.options.body.values.form_token, 'session-token');
  assert.equal(title.value, 'My manual title');
  assert.equal(description.value, 'My manual description');
  assert.equal(nodes['[data-analysis-preview]'].hidden, false);
  nodes['[data-apply-analysis]'].listeners.click();
  assert.equal(title.value, 'AI title');
  assert.equal(modern.checked, true); assert.equal(rustic.checked, false);
  assert.equal(input.files[0].name, 'original.jpg');
  let resolve;
  nextResponse = () => new Promise(r => { resolve = r; });
  const pending = nodes['[data-analyse-image]'].listeners.click();
  input.files = [{name: 'different.jpg'}];
  input.listeners.change();
  resolve({ok:true,json:async () => ({title:'STALE',description:'Old photo',category:'Modern'})});
  await pending;
  assert.equal(nodes['[data-analysis-preview]'].hidden, true);
  nodes['[data-apply-analysis]'].listeners.click();
  assert.equal(title.value, 'AI title');
  nextResponse = async () => ({ok:false,json:async () => ({error:'Quota reached'})});
  await nodes['[data-analyse-image]'].listeners.click();
  assert.equal(nodes['[data-analysis-status]'].textContent, 'Quota reached');
  assert.equal(nodes['[data-analyse-image]'].disabled, false);
  console.log('Passed: explicit apply, form token, original file preservation, stale response and error recovery.');
})().catch(error => { console.error(error); process.exitCode=1; });
