# C18: AI customer chat assistant, search results and relevant page navigation.
"""C18: validate AI actions and answer using actual catalogue records."""
from idfinder.controller.errors import ValidationError
from idfinder.entities.housing import Housing
from idfinder.entities.category import Category
from idfinder.entities.idp import IDP
from idfinder.entities.chatbot_catalogue import ChatbotCatalogue
from idfinder.controller.chatbot_leaderboard import ChatbotLeaderboard
import re


HELP = {
    # C18: describe the existing ranking system using server-owned feature text.
    'leaderboard': ('The designer leaderboard combines star ratings, review sentiment, customer interest, '
                    'reliability and experience. You can filter by one design category, housing type and '
                    'minimum visible reviews, or change the five ranking weights. Ask for the top 5 HDB designers.', 'leaderboard'),
    'saving': ('Open a project or browse the project cards, then choose Save to favourites. '
               'Saved projects are available from My Favourites.', 'favourites'),
    'categories': ('Design categories are style labels such as Modern or Minimalist. '
                   'They are separate from housing types such as HDB or Condo.', 'home'),
    'search': ('Tell me your housing type, budget, styles or words from a project title or description. '
               'For example: Modern or Japandi projects in Bishan. Say both styles to require both tags. '
               'You can also ask for a designer by name.', 'designers'),
    'privacy': ('Your message and brief conversation context go to Google Gemini. '
                'Do not share passwords or private account details. This assistant only reads catalogue data.', 'chat'),
}
PAGES = {'home', 'profile', 'favourites', 'designers', 'chat', 'leaderboard'}  # C18: safe board navigation.


class ChatbotController:
    def __init__(self, interpreter):
        self.interpreter = interpreter

    @staticmethod
    # C18: a fresh query must not inherit constraints just because Gemini says so.
    def is_follow_up(message):
        text = ' '.join(message.casefold().split())
        if re.search(r'\b(?:start over|new search|fresh search|reset|(?:clear|remove) all filters|forget (?:that|the|previous))\b', text):
            return False
        return bool(re.search(
            r'^(?:only\b|also\b|instead\b|same\b|keep\b|still\b|what about\b|how about\b|'
            r'and\b|but\b|now only\b|remove\b|exclude\b|without\b|include\b|add\b|'
            r'under\b|below\b|above\b|over\b|between\b|up to\b|from\s+(?:\$|s\$|\d))|'
            r'\b(?:those|these|them|previous results|same filters|both styles|both categories|'
            r'both locations|both places|both terms|both keywords|the first|the second|the third|'
            r'first one|second one|third one|each of those)\b|'
            r'\b(?:either|any)\s+(?:of\s+(?:those|these|the)\s+)?(?:styles|style|categories|locations|places|terms|keywords|one)\b|'
            r'^(?:either|any)(?:\s+(?:instead|please))?[.!?]*$', text))

    @staticmethod
    # C18: enforce ANY for plain lists such as 'Japandi and Modern'. ALL requires
    # explicit wording linked to that group, or a genuine unchanged follow-up.
    def search_intent(message, incoming, old, follow_up):
        if not isinstance(incoming, dict):
            return incoming
        result = dict(incoming)
        groups = {}
        for field, scalar in [('categories', 'category'), ('keywords', 'keyword')]:
            value = incoming.get(field)
            if value is None and incoming.get(scalar):
                value = [incoming[scalar]]
            if value is None and follow_up:
                value = old.get(field) or ([old[scalar]] if old.get(scalar) else [])
            groups[field] = value if isinstance(value, list) and all(isinstance(v, str) for v in value) else []
        text = ' '.join(message.casefold().split())
        explicit = set()
        explicit_any = set()
        group_words = {'categories': r'(?:design\s+)?(?:styles|categories|tags)',
                       'keywords': r'(?:(?:content|search)\s+)?(?:terms|keywords|locations|places|phrases)'}
        for group, words in group_words.items():
            if re.search(r'\b(?:both|all|every)\s+(?:(?:of\s+)?(?:the|these|those)\s+)?' + words + r'\b', text):
                explicit.add(group)
            if re.search(r'\b(?:either|any)\s+(?:(?:of\s+)?(?:the|these|those)\s+)?' + words + r'\b', text):
                explicit_any.add(group)
        for group, terms in groups.items():
            hits = sorted((match.start(), match.end()) for term in terms
                          for match in re.finditer(r'(?<!\w)' + re.escape(term.casefold()) + r'(?!\w)', text))
            if any(re.search(r'\bor\b', text[a[1]:b[0]]) for a, b in zip(hits, hits[1:])):
                explicit_any.add(group)
        if re.search(r'\b(?:hybrid|blend|blended|combined styles)\b', text):
            explicit.add('categories')
        # A named 'both X and Y' belongs to the first mentioned filter group.
        for marker in re.finditer(r'\bboth\b|\b(?:each|every) project\b.{0,35}?\bmust\b', text):
            mentioned = []
            tail = text[marker.end():]
            for group, terms in groups.items():
                if len(terms) < 2:
                    continue
                for term in terms:
                    found = re.search(r'(?<!\w)' + re.escape(term.casefold()) + r'(?!\w)', tail)
                    if found:
                        mentioned.append((found.start(), group))
            if mentioned:
                explicit.add(min(mentioned)[1])
        for group, mode_field, scalar in [('categories', 'category_mode', 'category'), ('keywords', 'keyword_mode', 'keyword')]:
            current_mode = incoming.get(mode_field)
            # Leave malformed output to the normal validator instead of masking it.
            if current_mode is not None and (not isinstance(current_mode, str) or current_mode not in ('any', 'all')):
                continue
            terms = groups[group]
            if not terms:
                continue
            previous = old.get(group) or ([old[scalar]] if old.get(scalar) else [])
            unchanged = follow_up and {v.casefold() for v in terms} == {v.casefold() for v in previous}
            result[mode_field] = ('any' if group in explicit_any else 'all' if group in explicit
                                  else old.get(mode_field, 'any') if unchanged else 'any')
        return result

    @staticmethod
    def text(value, limit=120):
        if value is None:
            return None
        if not isinstance(value, str) or len(value) > limit:
            raise ValidationError('Please use a shorter, more specific search.')
        return ' '.join(value.split()) or None

    @staticmethod
    # C18: supply actual housing options and categories to the AI interpreter.
    def vocabulary():
        return {
            'property_types': [dict(row) for row in Housing.types()],
            'subtypes': [{'name': r['name'], 'type_code': r['type_code']} for r in Housing.subtypes()],
            'categories': [r['name'] for r in Category.find_all_active()],
            'allowed_pages': sorted(PAGES),
        }

    # C18: each housing alternative can name a type, subtype, or both.
    def resolve_housing(self, option):
        if not isinstance(option, dict) or set(option) - {'property_type', 'subtype_name'}:
            raise ValidationError('Use valid housing alternatives.')
        property_type = self.text(option.get('property_type'))
        subtype = self.text(option.get('subtype_name'))
        resolved = {}
        if property_type:
            match = next((r for r in Housing.types() if property_type.casefold() in
                          (r['code'].casefold(), r['name'].casefold())), None)
            if match is None:
                raise ValidationError('Please choose an available housing type.')
            resolved['property_type'] = match['code']
        if subtype:
            matches = [r for r in Housing.subtypes() if r['name'].casefold() == subtype.casefold()
                       and (not resolved or r['type_code'] == resolved['property_type'])]
            if len(matches) != 1:
                raise ValidationError('Please specify an available subtype and its housing type.')
            resolved.update(property_type=matches[0]['type_code'], subtype_id=matches[0]['id'], subtype_name=matches[0]['name'])
        if not resolved:
            raise ValidationError('Choose a housing type or room subtype for each alternative.')
        return resolved

    # C18: validate filters and preserve context for follow-up questions.
    def clean_filters(self, incoming, old, inherit):
        if not isinstance(incoming, dict) or type(inherit) is not bool:
            raise ValidationError('Please rephrase the project requirements.')
        if set(incoming) - {'property_type', 'subtype_name', 'housing_options', 'category', 'categories', 'category_mode', 'keyword', 'keywords', 'keyword_mode', 'min_price', 'max_price'}:
            raise ValidationError('That search option is not supported.')
        result = dict(old) if inherit else {}
        # C18: alternatives are OR-ed (4-Room HDB OR Landed), with budgets/styles
        # still applied to every result. Changing options replaces the old group.
        property_type = self.text(incoming.get('property_type'))
        subtype = self.text(incoming.get('subtype_name'))
        housing = incoming.get('housing_options')
        if housing is not None:
            if not isinstance(housing, list) or len(housing) > 10 or property_type or subtype:
                raise ValidationError('Choose up to 10 consistent housing alternatives.')
            options = [self.resolve_housing(option) for option in housing]
        elif property_type or subtype:
            options = [self.resolve_housing({'property_type': property_type or result.get('property_type'),
                                             'subtype_name': subtype})]
        else:
            options = None
        if options is not None:
            options = list({(o['property_type'], o.get('subtype_id')): o for o in options}.values())
            for key in ('property_type', 'subtype_id', 'subtype_name', 'housing_options'):
                result.pop(key, None)
            if options:
                result['housing_options'] = options
                if len(options) == 1:
                    result.update(options[0])
        # C18: accept several style tags; ANY is a union, ALL requires every tag.
        category = self.text(incoming.get('category'))  # Legacy single-style callers.
        categories = incoming.get('categories')
        mode = incoming.get('category_mode')
        if mode is not None and (not isinstance(mode, str) or mode not in ('any', 'all')):
            raise ValidationError('Choose either any style or all styles.')
        if categories is not None:
            if not isinstance(categories, list) or len(categories) > 10:
                raise ValidationError('Choose up to 10 design categories.')
            names = [self.text(value, 80) for value in categories]
            if any(value is None for value in names):
                raise ValidationError('Use valid design category names.')
            if category and {value.casefold() for value in names} != {category.casefold()}:
                raise ValidationError('Please provide one consistent list of design categories.')
        else:
            names = [category] if category else None
        if names is not None:
            available = {r['name'].casefold(): r for r in Category.find_all_active()}
            matches = []
            for name in dict.fromkeys(n.casefold() for n in names):
                if name not in available:
                    raise ValidationError('That design category is unavailable. Please choose one of the listed categories.')
                matches.append(available[name])
            for key in ('category', 'category_id', 'categories', 'category_ids', 'category_mode'):
                result.pop(key, None)
            if matches:
                result.update(categories=[r['name'] for r in matches], category_ids=[r['id'] for r in matches],
                              category_mode=mode or 'any')
                if len(matches) == 1:
                    result.update(category=matches[0]['name'], category_id=matches[0]['id'])
        elif mode is not None:
            if not result.get('category_ids') and not result.get('category_id'):
                raise ValidationError('Choose design categories before changing how they match.')
            result['category_mode'] = mode
        for field in ('min_price', 'max_price'):
            value = incoming.get(field)
            if value is not None:
                if type(value) is not int or not 0 <= value <= 1_000_000_000:
                    raise ValidationError('Use a valid budget in whole Singapore dollars.')
                result[field] = value
        if result.get('min_price', 0) > result.get('max_price', 1_000_000_000):
            raise ValidationError('The minimum budget cannot exceed the maximum budget.')
        # C18: places/content alternatives search title OR description for each
        # literal phrase. Explicit ALL requires every phrase, even across fields.
        keyword = self.text(incoming.get('keyword'))
        keywords = incoming.get('keywords')
        keyword_mode = incoming.get('keyword_mode')
        if keyword_mode is not None and (not isinstance(keyword_mode, str) or keyword_mode not in ('any', 'all')):
            raise ValidationError('Choose either any content term or all content terms.')
        if keywords is not None:
            if not isinstance(keywords, list) or len(keywords) > 8 or keyword:
                raise ValidationError('Choose up to 8 consistent content search terms.')
            terms = [self.text(term) for term in keywords]
            if any(term is None for term in terms):
                raise ValidationError('Use valid content search terms.')
        else:
            terms = [keyword] if keyword else None
        if terms is not None:
            terms = list({term.casefold(): term for term in terms}.values())
            for key in ('keyword', 'keywords', 'keyword_mode'):
                result.pop(key, None)
            if terms:
                result.update(keywords=terms, keyword_mode=keyword_mode or 'any')
                if len(terms) == 1:
                    result['keyword'] = terms[0]
        elif keyword_mode is not None:
            if not result.get('keywords') and not result.get('keyword'):
                raise ValidationError('Choose content terms before changing how they match.')
            result['keyword_mode'] = keyword_mode
        return result

    # C18: dispatch interpreted requests to permitted catalogue and navigation actions.
    def reply(self, message, state):
        follow_up = self.is_follow_up(message)
        context = self.vocabulary()
        context.update(previous_filters=state.get('filters', {}) if follow_up else {},
                       previous_results=state.get('results', []) if follow_up else [],
                       recent_messages=state.get('messages', [])[-4:] if follow_up else [],
                       request_scope='follow_up' if follow_up else 'new_search')
        # C18: ranking context is isolated from the previous project-search filters.
        context.update(previous_intent=state.get('last_intent') if follow_up else None,
                       previous_leaderboard=state.get('leaderboard_filters', {})
                       if follow_up and state.get('last_intent') == 'search_leaderboard' else {})
        action = self.interpreter.interpret(message, context)
        if not isinstance(action, dict):
            raise ValidationError('Please rephrase that request.')
        for name, limit in [('page', 30), ('topic', 30), ('question', 400), ('designer_name', 100)]:
            if action.get(name) is not None:
                action[name] = self.text(action[name], limit)
        intent = action.get('intent')
        answer = {'reply': '', 'projects': [], 'designers': [], 'actions': [], 'filters': {}}
        updated = dict(state)
        if intent == 'search_projects':
            inherit = action.get('inherit_filters')
            if type(inherit) is not bool:
                raise ValidationError('Please rephrase the project requirements.')
            old = state.get('filters', {}) if follow_up else {}
            incoming = self.search_intent(message, action.get('filters'), old if inherit else {}, follow_up and inherit)
            filters = self.clean_filters(incoming, old, inherit and follow_up)
            total, projects = ChatbotCatalogue.search(filters)
            # C18: explain style logic and expose every match through a paged list.
            details = []
            styles = filters.get('categories') or ([filters['category']] if filters.get('category') else [])
            if styles:
                operator = ' AND ' if filters.get('category_mode') == 'all' else ' OR '
                details.append('Styles: ' + operator.join(styles) + '.')
            housing = filters.get('housing_options', [])
            if housing:
                details.append('Housing: ' + ' OR '.join(' '.join(filter(None, [o.get('property_type'), o.get('subtype_name')])) for o in housing) + '.')
            terms = filters.get('keywords') or ([filters['keyword']] if filters.get('keyword') else [])
            if terms:
                operator = ' AND ' if filters.get('keyword_mode') == 'all' else ' OR '
                details.append('Title or description contains: ' + operator.join(terms) + '.')
            reply = (f'I found {total} matching project(s). Showing {len(projects)} here.' if total
                     else 'No projects match those requirements.')
            if not total and len(styles) > 1 and filters.get('category_mode') == 'all':
                reply += ' No project has every requested style tag. Try either style instead.'
            elif not total:
                reply += ' Try a wider budget, a different style or another keyword.'
            answer.update(projects=projects, filters=filters, total=total,
                          reply=' '.join([reply] + details),
                          actions=[{'page': 'project_search', 'filters': filters}] if total else [])
            updated.update(filters=filters, results=[{'id': p['id'], 'title': p['title']} for p in projects])
        elif intent == 'search_leaderboard':
            # C18: use validated options with the existing leaderboard controller.
            inherit = action.get('inherit_filters')
            if type(inherit) is not bool:
                raise ValidationError('Please rephrase the leaderboard filters.')
            project_filters = action.get('filters', {})
            if not isinstance(project_filters, dict) or any(value is not None and value != [] and value != ''
                                                           for value in project_filters.values()):
                raise ValidationError('The leaderboard supports one style, housing type, minimum reviews and ranking weights. '
                                      'Use project search for budgets, locations and room subtypes.')
            previous = state.get('leaderboard_filters', {}) if (
                follow_up and inherit and state.get('last_intent') == 'search_leaderboard') else {}
            incoming = action.get('leaderboard')
            filters = ChatbotLeaderboard.clean({} if incoming is None else incoming, previous)
            answer.update(ChatbotLeaderboard.search(filters))
            updated.update(leaderboard_filters=filters, filters={}, results=[])
        elif intent == 'search_designers':
            name = self.text(action.get('designer_name'), 100) or ''
            total, designers = ChatbotCatalogue.designers(name)
            answer.update(designers=designers, total=total,
                          reply=f'I found {total} designer(s). Showing {len(designers)}.',
                          actions=[{'page': 'designers', 'name': name}])
        elif intent == 'project_details':
            number = action.get('result_number')
            results = state.get('results', [])
            if type(number) is not int or not 1 <= number <= len(results):
                raise ValidationError('Search for projects first, then choose a result number from the displayed list.')
            project = IDP.find(results[number - 1]['id'])
            if project is None:
                raise ValidationError('That project is no longer available. Please run the search again.')
            answer.update(reply='Open this project to see its details and images.',
                          projects=[{k: project[k] for k in ('id', 'title', 'price', 'property_type', 'status')}])
        elif intent == 'navigate':
            page = action.get('page')
            if page not in PAGES:
                raise ValidationError('I can open browsing, your profile, favourites, designer search or the leaderboard.')
            answer.update(reply='Use the link below to open that page.', actions=[{'page': page}])
        elif intent == 'help':
            text, page = HELP.get(action.get('topic'), HELP['search'])
            answer.update(reply=text, actions=[{'page': page}])
        elif intent == 'clarify':
            answer['reply'] = self.text(action.get('question'), 400) or 'Would you like to search projects, find designers or open a page?'
        else:
            raise ValidationError('I can search projects, find or rank designers, explain features and open customer pages.')
        updated['last_intent'] = intent  # C18: retain ranking context only for explicit continuations.
        updated['messages'] = ((state.get('messages', []) if follow_up else []) + [message[:600]])[-4:]
        return answer, updated
