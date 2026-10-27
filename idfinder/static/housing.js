class HousingFilter {
    constructor(group) {
        this.type = group.querySelector('[data-housing-type]');

        this.subtype = group.querySelector(
            '[data-housing-subtype]'
        );

        this.options = Array.from(
            this.subtype.querySelectorAll('option[data-type]')
        );

        this.placeholder = this.subtype.querySelector(
            'option[value=""]'
        );

        this.type.addEventListener(
            'change',
            () => this.refresh(false)
        );

        this.refresh(true);
    }

    refresh(keepSelection) {
        const selected = keepSelection
            ? this.subtype.value
            : '';

        this.subtype.replaceChildren(this.placeholder);

        this.options.forEach(option => {
            if (option.dataset.type === this.type.value) {
                option.selected = option.value === selected;
                this.subtype.append(option);
            }
        });

        const selectionExists = Array.from(
            this.subtype.options
        ).some(option => option.value === selected);

        if (!selected || !selectionExists) {
            this.subtype.value = '';
        }

        this.subtype.disabled = !this.type.value;
    }

    static initialise() {
        document.querySelectorAll(
            '[data-housing-selects]'
        ).forEach(group => {
            new HousingFilter(group);
        });
    }
}

HousingFilter.initialise();