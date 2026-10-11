
from myfirstapp.db import get_db


class IDPView:

    @staticmethod
    def record(idp_id, viewer_id=None):
        """Save one project page view."""
        db = get_db()

        db.execute(
            """
            INSERT INTO idp_view (idp_id, viewer_id)
            VALUES (?, ?)
            """,
            (idp_id, viewer_id)
        )

        db.commit()
