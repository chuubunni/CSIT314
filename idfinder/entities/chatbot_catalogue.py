# C18: AI customer chat assistant, search results and relevant page navigation.
"""C18: bounded, read-only catalogue searches with parameterised values."""
from idfinder.db import get_db


def literal_like(value):
    return '%' + value.replace('\\', '\\\\').replace('%', '\\%').replace('_', '\\_') + '%'


class ChatbotCatalogue:
    @staticmethod
    # C18: search projects by housing, subtype, budget, category and keywords.
    def search(filters, limit=6, offset=0):
        # C18: chat previews are bounded; the results page uses the same predicates.
        if type(limit) is not int or not 1 <= limit <= 50 or type(offset) is not int or offset < 0:
            raise ValueError('Invalid result page.')
        conditions, values = [], []
        # C18: keep each type/subtype pair together, then union alternatives.
        if filters.get('housing_options'):
            alternatives = []
            for option in filters['housing_options']:
                parts = []
                for key, column in [('property_type', 'p.property_type'), ('subtype_id', 'p.property_subtype_id')]:
                    if option.get(key) is not None:
                        parts.append(column + ' = ?'); values.append(option[key])
                alternatives.append('(' + ' AND '.join(parts) + ')')
            conditions.append('(' + ' OR '.join(alternatives) + ')')
        else:
            for key, column in [('property_type', 'p.property_type'), ('subtype_id', 'p.property_subtype_id')]:
                if filters.get(key) is not None:
                    conditions.append(column + ' = ?'); values.append(filters[key])
        for key, comparison in [('min_price', '>='), ('max_price', '<=')]:
            if filters.get(key) is not None:
                conditions.append('p.price ' + comparison + ' ?')
                values.append(filters[key])
        category_ids = filters.get('category_ids') or ([filters['category_id']] if filters.get('category_id') is not None else [])
        if category_ids:
            placeholders = ','.join('?' for _ in category_ids)
            if filters.get('category_mode') == 'all':
                conditions.append('(SELECT COUNT(DISTINCT ic.category_id) FROM idp_category ic '
                                  'WHERE ic.idp_id=p.id AND ic.category_id IN (' + placeholders + '))=?')
                values.extend(category_ids); values.append(len(set(category_ids)))
            else:
                conditions.append('EXISTS (SELECT 1 FROM idp_category ic WHERE ic.idp_id=p.id '
                                  'AND ic.category_id IN (' + placeholders + '))')
                values.extend(category_ids)
        terms = filters.get('keywords') or ([filters['keyword']] if filters.get('keyword') else [])
        if terms:
            clauses = []
            for term in terms:
                clauses.append("(p.title LIKE ? ESCAPE '\\' OR COALESCE(p.description,'') LIKE ? ESCAPE '\\')")
                values.extend([literal_like(term)] * 2)
            operator = ' AND ' if filters.get('keyword_mode') == 'all' else ' OR '
            conditions.append('(' + operator.join(clauses) + ')')
        where = ' WHERE ' + ' AND '.join(conditions) if conditions else ''
        db = get_db()
        total = db.execute('SELECT COUNT(*) FROM idp p' + where, values).fetchone()[0]
        rows = db.execute(
            'SELECT p.id,p.title,p.description,p.price,p.property_type,p.status,'
            's.name AS subtype_name,u.name AS designer_name,c.companyName AS company_name '
            ',(SELECT GROUP_CONCAT(cat.name, ", ") FROM idp_category tags '
            'JOIN category cat ON cat.id=tags.category_id WHERE tags.idp_id=p.id) AS category_names '
            'FROM idp p LEFT JOIN property_subtype s ON s.id=p.property_subtype_id '
            'JOIN user u ON u.id=p.designer_id '
            'LEFT JOIN designer d ON d.userID=p.designer_id '
            'LEFT JOIN company c ON c.companyID=d.companyID' + where +
            ' ORDER BY p.created DESC,p.id DESC LIMIT ? OFFSET ?', values + [limit, offset]).fetchall()
        return total, [dict(row) for row in rows]

    @staticmethod
    # C18: find real designer accounts and companies using a literal name search.
    def designers(name):
        db = get_db()
        predicate = " WHERE u.name LIKE ? ESCAPE '\\'"
        params = (literal_like(name),)
        total = db.execute('SELECT COUNT(*) FROM designer d JOIN user u ON u.id=d.userID' + predicate, params).fetchone()[0]
        rows = db.execute(
            'SELECT u.id,u.name,c.companyName AS company_name,'
            '(SELECT COUNT(*) FROM idp p WHERE p.designer_id=u.id) AS project_count '
            'FROM designer d JOIN user u ON u.id=d.userID '
            'LEFT JOIN company c ON c.companyID=d.companyID' + predicate +
            ' ORDER BY u.name COLLATE NOCASE,u.id LIMIT 6', params).fetchall()
        return total, [dict(row) for row in rows]
