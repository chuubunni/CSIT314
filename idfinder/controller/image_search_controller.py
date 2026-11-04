"""Image-search business rules; no Flask request/session/SQL objects here."""
from pathlib import Path
from idfinder.controller.errors import ValidationError
from idfinder.controller.search_controller import SearchController
from idfinder.entities.image_search import ImageSearch
from idfinder.image_search.local import ImageAnalyser, prepare_image, rank_score, STYLE_RULES


class ImageSearchController:
    @staticmethod
    def analyse_upload(raw, filename):
        """Validate the upload and analyse it entirely offline with Pillow."""
        try:
            clean = prepare_image(raw, filename)
            features = ImageAnalyser().analyse(clean)
        except ValueError as exc:
            raise ValidationError(str(exc)) from exc
        return features, 'Local colour analysis (offline)'

    @staticmethod
    def rebuild(upload_folder, force=False):
        """Run explicitly using flask index-images; no per-search image rescanning."""
        root = Path(upload_folder).resolve()
        fingerprints = ImageSearch.fingerprints()
        records = ImageSearch.media()
        processed = 0
        cache = {}
        for row in records:
            # Only filenames already stored by our application, never user-supplied paths.
            link = row['link']
            path = (root / link).resolve()
            if path.parent != root or not path.is_file():
                continue
            stat = path.stat()
            old = fingerprints.get(row['mediaID'])
            if not force and old and old['link'] == link and old['file_size'] == stat.st_size and old['file_mtime_ns'] == stat.st_mtime_ns:
                continue
            try:
                signature = (link, stat.st_size, stat.st_mtime_ns)
                if signature not in cache:
                    clean = prepare_image(path.read_bytes(), link)
                    cache[signature] = ImageAnalyser().analyse(clean)
                features = cache[signature]
            except (ValueError, OSError):
                continue
            ImageSearch.save(row['mediaID'], row['idp_id'], link, stat.st_size, stat.st_mtime_ns, features)
            processed += 1
        ImageSearch.remove_stale([row['mediaID'] for row in records])
        return processed

    @staticmethod
    def results(features, property_type='', subtype='', category='', minimum='', maximum=''):
        projects = SearchController.search()  # Existing all-project query and image helper.
        grouped = {}
        for project_id, indexed in ImageSearch.all_features():
            grouped.setdefault(project_id, []).append(indexed)
        ranked = []
        for project in projects:
            candidates = grouped.get(project['id'], [])
            if not candidates:
                continue
            names = (project.get('category_names') or '').split(', ')
            score = max(rank_score(features, indexed, names) for indexed in candidates)
            item = dict(project)
            item['match_score'] = score
            known_names = [name for name in names if name in features['styles']]
            if known_names:
                top_name = max(known_names, key=lambda name: features['styles'][name])
                item['matched_category'] = top_name
                item['match_reason'] = STYLE_RULES.get(top_name, ('', '', 'Similar overall colour palette'))[2]
            else:
                item['matched_category'] = 'Visual similarity'
                item['match_reason'] = 'Similar overall colours and brightness'
            ranked.append(item)
        ranked.sort(key=lambda project: (-project['match_score'], project['id']))
        # Validate & reuse the original search query to narrow ranked results.
        filtered_ids = {p['id'] for p in SearchController.search(property_type, subtype, category)}
        try:
            lo = float(minimum) if minimum else 0.
            hi = float(maximum) if maximum else float('inf')
        except (ValueError, TypeError) as exc:
            raise ValidationError('Enter valid price amounts.') from exc
        if lo < 0 or hi < lo or hi < 0 or lo == float('inf'):
            raise ValidationError('Enter a valid price range.')
        return [p for p in ranked if p['id'] in filtered_ids and lo <= float(p['price'] or 0) <= hi]
