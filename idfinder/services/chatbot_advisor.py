"""C18: grounded explanations, confirmed search choices and saved-project comparison."""
from copy import deepcopy
import re
import secrets
from idfinder.controller.errors import ValidationError
from idfinder.controller.favourites_controller import FavouritesController
from idfinder.entities.chatbot_catalogue import ChatbotCatalogue
from idfinder.entities.favourites import Favourites


class ChatbotAdvisor:
    @staticmethod
    def answer(text, **extras):
        return dict(reply=text, projects=[], designers=[], actions=[], filters={}, **extras)

    @staticmethod
    def portable(filters):
        # C18: revalidate search choices using names rather than resolved database IDs.
        result = {k: filters[k] for k in ('min_price', 'max_price', 'categories', 'category_mode') if k in filters}
        if filters.get('housing_options'):
            result['housing_options'] = [{k: o[k] for k in ('property_type', 'subtype_name') if k in o}
                                         for o in filters['housing_options']]
        return result

    @staticmethod
    def options(answer, state, choices):
        # C18: option numbers refer only to validated choices in this conversation.
        state['search_choices'] = deepcopy(choices)
        state['choice_token'] = secrets.token_hex(8)
        answer['suggestions'] = [{'label': c['label'], 'message': f"Apply option {i+1} {state['choice_token']}"}
                                 for i, c in enumerate(choices)]

    @staticmethod
    def display_message(message, state, answer):
        # C18: keep internal option tokens and numeric IDs out of the visible transcript.
        if answer.get('comparison'):
            return 'Compare ' + ' and '.join(p['title'] for p in answer['comparison'])
        choice = re.fullmatch(r'Apply option ([1-3]) [a-f0-9]{16}', message)
        if choice and int(choice[1]) <= len(state.get('search_choices', [])):
            return state['search_choices'][int(choice[1])-1]['label']
        return message

    @classmethod
    def propose_styles(cls, names, filters, controller, state):
        if not isinstance(names, list) or not names or len(names) > 3:
            raise ValidationError('Please describe the style you have in mind.')
        proposed = controller.clean_filters({'categories': names, 'category_mode': 'any'}, filters, True)
        state = dict(state, awaiting_requirements=False)
        answer = cls.answer('That description may suit ' + ' or '.join(proposed['categories']) +
                            '. This is a style interpretation, not an analysis of project images. '
                            'Would you like to search those styles?')
        cls.options(answer, state, [{'label': 'Search these styles', 'filters': proposed}])
        return answer, state

    @classmethod
    def run_search(cls, filters, state, controller):
        # C18: reuse the existing validator and search; applying a choice needs no Gemini call.
        class SearchAction:
            def interpret(self, message, context):
                return {'intent': 'search_projects', 'filters': cls.portable_with_content(filters), 'inherit_filters': False}
        from idfinder.controller.chatbot_controller import ChatbotController
        command = 'Search selected requirements'
        if filters.get('category_mode') == 'all': command += ' with all styles'
        if filters.get('keyword_mode') == 'all': command += ' with all terms'
        answer, updated = ChatbotController(SearchAction()).reply(command, dict(state, search_choices=[]))
        return cls.enrich(answer, updated)

    @classmethod
    def reply(cls, message, state, customer_id, controller):
        text = ' '.join(message.casefold().split()).rstrip('.!?')
        updated = dict(state)
        # C18: preferences are never persisted; only conversation context is retained.
        if text in ('remember my search preferences', 'save my search preferences', 'use saved preferences',
                    'forget saved preferences', 'forget my saved preferences'):
            return cls.answer('I do not save preferences between conversations. Tell me your requirements here; '
                              'New chat clears the current conversation.'), updated
        choice = re.fullmatch(r'apply option ([1-3]) ([a-f0-9]{16})', text)
        if choice:
            choices = state.get('search_choices', [])
            index = int(choice[1]) - 1
            if index >= len(choices) or choice[2] != state.get('choice_token'):
                raise ValidationError('That option has expired. Please run the search again.')
            return cls.run_search(cls.portable_with_content(choices[index]['filters']), state, controller)
        if text.startswith('apply option '):
            raise ValidationError('That option has expired. Please run the search again.')
        pair = re.fullmatch(r'compare saved projects ([0-9]{1,19}) and ([0-9]{1,19})', text)
        if pair:
            ids = [int(v) for v in pair.groups()]
            if max(ids) > 9223372036854775807:
                raise ValidationError('Choose two valid saved projects.')
            allowed = state.get('comparison_ids', [])
            if any(v not in allowed for v in ids):
                raise ValidationError('Open Compare my favourites and choose two projects from that list.')
            projects, summary = FavouritesController().compare_projects(customer_id, [str(v) for v in ids])
            answer = cls.answer('Comparison of your two selected saved projects. Listed prices may cover different work.',
                                comparison=projects, comparison_summary=summary)
            answer['actions'] = [{'page': 'favourites'}]
            return answer, updated
        if controller.is_comparison_request(message):
            # C18: reveal only the current customer's approved saved projects.
            saved = Favourites.find_projects(customer_id)
            # C18: bounded picker; My Favourites remains available for the complete list.
            choices = [{'id': p['id'], 'title': p['title']} for p in saved[:30]]
            answer = cls.answer('You can compare two saved projects from My Favourites. '
                                'Choose two different projects below, then select Compare projects. '
                                'Save at least two projects first if you have not already.', comparison_choices=choices)
            answer['actions'] = [{'page': 'favourites'}]
            updated.update(comparison_ids=[p['id'] for p in choices], search_choices=[])
            return answer, updated
        # C18: collect requirements for vague recommendations, without blocking ordinary browsing.
        if re.fullmatch(r'(?:please )?(?:find|recommend|suggest)(?: me)? (?:a |an |some )?(?:interior )?designers? for my (?:house|home)', text):
            updated.update(awaiting_requirements=True, filters={}, results=[], search_choices=[], last_intent='clarify')
            return cls.answer('What property type are you renovating, what is your budget in SGD, '
                              'and which styles do you like? You can answer one at a time.'), updated
        # C18: new messages invalidate previous buttons, but retain real search context.
        updated['search_choices'] = []
        answer, updated = controller.reply(message, updated)
        if answer.get('style_proposal'):
            return cls.propose_styles(answer['style_proposal'], answer.get('filters', {}), controller, updated)
        return cls.enrich(answer, updated)

    @staticmethod
    def portable_with_content(filters):
        # C18: remove resolved IDs before revalidating a pending search choice.
        result = ChatbotAdvisor.portable(filters)
        for key in ('keywords', 'keyword_mode'):
            if key in filters: result[key] = filters[key]
        return result

    @classmethod
    def enrich(cls, answer, state):
        if 'total' not in answer or state.get('last_intent') != 'search_projects':
            return answer, state
        filters = answer.get('filters', {})
        for project in answer.get('projects', []):
            # C18: reasons use actual record values and only requested matching fields.
            reasons = []
            if 'min_price' in filters or 'max_price' in filters:
                reasons.append(f"Listed price S${project['price']:,.0f} matches your budget filter.")
            if filters.get('housing_options'):
                reasons.append('Property: ' + ' '.join(v for v in [project['property_type'], project.get('subtype_name')] if v) + '.')
            styles = filters.get('categories', [])
            tags = [v.strip() for v in (project.get('category_names') or '').split(',')]
            matches = [tag for tag in tags if tag.casefold() in {s.casefold() for s in styles}]
            if matches: reasons.append('Matching style tags: ' + ', '.join(matches) + '.')
            for term in filters.get('keywords', []):
                fields = [label for key, label in [('title', 'title'), ('description', 'description')]
                          if term.casefold() in (project.get(key) or '').casefold()]
                if fields: reasons.append('“' + term + '” appears in the ' + ' and '.join(fields) + '.')
            project['match_reasons'] = reasons or ['Available in the approved project catalogue; no specific preferences were supplied.']
        if answer['total']:
            return answer, state
        candidates = []
        if filters.get('category_mode') == 'all' and len(filters.get('categories', [])) > 1:
            candidate = dict(filters, category_mode='any')
            candidates.append(('Match either style instead', candidate))
        if 'max_price' in filters and filters['max_price'] < 1_000_000_000:
            budget = min(1_000_000_000, max(filters['max_price'] + 10000, round(filters['max_price'] * 1.2)))
            candidates.append((f'Raise maximum budget to S${budget:,}', dict(filters, max_price=budget)))
        if filters.get('keywords'):
            candidate = {k: v for k, v in filters.items() if k not in ('keywords', 'keyword', 'keyword_mode')}
            candidates.append(('Search without the title/description terms', candidate))
        choices = []
        for label, candidate in candidates:
            total, _ = ChatbotCatalogue.search(candidate, limit=1)
            if total:
                choices.append({'label': f'{label} ({total} matches)', 'filters': candidate})
        if choices:
            answer['reply'] += ' These alternatives have matches. Choose one to change the search; your original requirements are unchanged until then.'
            cls.options(answer, state, choices[:3])
        return answer, state
