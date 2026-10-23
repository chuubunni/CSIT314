// ID19: select-all and live bulk-selection counts.
const projects = [...document.querySelectorAll('input[name="idp_ids"]')];
const categories = [...document.querySelectorAll('input[name="category_ids"]')];
const summary = document.getElementById('selection-summary');
function update_summary() {
    summary.textContent = `${projects.filter(input => input.checked).length} projects selected · ${categories.filter(input => input.checked).length} replacement categories`;
}
document.getElementById('select-projects').addEventListener('click', function () {
    const select = projects.some(input => !input.checked);
    projects.forEach(input => { input.checked = select; });
    this.textContent = select ? 'Clear project selection' : 'Select all projects';
    update_summary();
});
[...projects, ...categories].forEach(input => input.addEventListener('change', update_summary));
update_summary();
