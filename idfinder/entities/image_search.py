"""SQL persistence for precomputed features (the only SQL layer)."""
import json
from idfinder.db import get_db


class ImageSearch:
    @staticmethod
    def media():
        return get_db().execute('SELECT mediaID, idp_id, link FROM idp_media').fetchall()

    @staticmethod
    def fingerprints():
        return {row['media_id']: dict(row) for row in get_db().execute(
            'SELECT media_id, file_size, file_mtime_ns, link FROM image_search_feature')}

    @staticmethod
    def save(media_id, idp_id, link, size, mtime, features):
        db = get_db()
        db.execute('INSERT OR REPLACE INTO image_search_feature VALUES (?,?,?,?,?,?)',
                   (media_id, idp_id, link, size, mtime, json.dumps(features)))
        db.commit()

    @staticmethod
    def remove_stale(ids):
        db = get_db()
        if ids:
            db.execute('DELETE FROM image_search_feature WHERE media_id NOT IN (' +
                       ','.join('?' for _ in ids) + ')', tuple(ids))
        else:
            db.execute('DELETE FROM image_search_feature')
        db.commit()

    @staticmethod
    def all_features():
        return [(row['idp_id'], json.loads(row['features_json'])) for row in get_db().execute(
            'SELECT idp_id, features_json FROM image_search_feature')]
