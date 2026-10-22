// All options are rendered on the server. JS narrows the dependent dropdown.
// Without JS, the server still validates the selected parent/subtype pair.
document.querySelectorAll('[data-housing-selects]').forEach(container => {
    const type = container.querySelector('[data-housing-type]');
    const subtype = container.querySelector('[data-housing-subtype]');
    const options = Array.from(subtype.options).slice(1).map(option => option.cloneNode(true));
    function refresh() {
        const selected = subtype.value;
        subtype.replaceChildren(new Option(subtype.dataset.placeholder, ''));
        options.filter(option => !type.value || option.dataset.type === type.value)
            .forEach(option => subtype.append(option.cloneNode(true)));
        subtype.value = Array.from(subtype.options).some(o => o.value === selected) ? selected : '';
        if (!subtype.value) subtype.value = '';
        subtype.disabled = !type.value;
    }
    type.addEventListener('change', refresh);
    refresh();
});