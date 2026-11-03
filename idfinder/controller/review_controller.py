import json
from datetime import datetime, timezone

from idfinder.controller import review_text
from idfinder.controller.errors import NotFoundError, PermissionDenied, ValidationError
from idfinder.controller.review_integrity import flag_reviews
from idfinder.entities.engagement import Engagement
from idfinder.entities.review import Review

MAX_COMMENT = 1000
MAX_REPLY = 500
MAX_REASON = 300


class ReviewController:
    """Control: who may review whom, and what happens to a review afterwards."""

    # ------------------------------------------------------------------ validation helpers
    @staticmethod
    def _check_rating(rating):
        # "5", 5 are fine; 0, 6, 4.5, "abc", True, None are not
        if isinstance(rating, bool):
            raise ValidationError('Please choose a rating from 1 to 5 stars.')
        try:
            value = int(str(rating).strip())
        except (TypeError, ValueError):
            raise ValidationError('Please choose a rating from 1 to 5 stars.')
        if not 1 <= value <= 5:
            raise ValidationError('Please choose a rating from 1 to 5 stars.')
        return value

    @staticmethod
    def _check_text(text, limit, what):
        text = (text or '').strip()
        if len(text) > limit:
            raise ValidationError(f'{what} must be {limit} characters or fewer.')
        return text

    @staticmethod
    def _analyse(comment):
        sentiment, aspects = review_text.analyse(comment)
        return sentiment, json.dumps(aspects)

    def _own_review(self, customer_id, review_id):
        review = Review.find(review_id)
        if review is None:
            raise NotFoundError('Review not found.')
        if review['customer_id'] != customer_id:
            raise PermissionDenied('You can only change your own review.')
        return review

    # ------------------------------------------------------------------ customer
    def submit(self, customer_id, engagement_id, rating, comment):
        engagement = Engagement.find(engagement_id)
        if engagement is None:
            raise NotFoundError('Job not found.')
        if engagement['customer_id'] != customer_id:
            raise PermissionDenied('You can only review your own jobs.')
        if engagement['status'] != 'completed':
            raise ValidationError('You can review a designer once the job is completed.')
        if Review.find_by_engagement(engagement_id) is not None:
            raise ValidationError('You have already reviewed this job. You can edit your review instead.')
        value = self._check_rating(rating)
        comment = self._check_text(comment, MAX_COMMENT, 'The review')
        sentiment, aspects = self._analyse(comment)
        return Review.create(engagement_id, customer_id, engagement['designer_id'],
                             value, comment, sentiment, aspects)

    def edit(self, customer_id, review_id, rating, comment):
        self._own_review(customer_id, review_id)
        value = self._check_rating(rating)
        comment = self._check_text(comment, MAX_COMMENT, 'The review')
        sentiment, aspects = self._analyse(comment)
        Review.update_content(review_id, value, comment, sentiment, aspects)

    def delete(self, customer_id, review_id):
        self._own_review(customer_id, review_id)
        Review.delete(review_id)

    def for_review_form(self, customer_id, engagement_id):
        """The job (and existing review, if any) behind the review form. Same checks as submit."""
        engagement = Engagement.find(engagement_id)
        if engagement is None:
            raise NotFoundError('Job not found.')
        if engagement['customer_id'] != customer_id:
            raise PermissionDenied('You can only review your own jobs.')
        if engagement['status'] != 'completed':
            raise ValidationError('You can review a designer once the job is completed.')
        return engagement, Review.find_by_engagement(engagement_id)

    # ------------------------------------------------------------------ designer
    def reply(self, designer_id, review_id, text):
        review = Review.find(review_id)
        if review is None:
            raise NotFoundError('Review not found.')
        if review['designer_id'] != designer_id:
            raise PermissionDenied('This review is not about you.')
        text = self._check_text(text, MAX_REPLY, 'The reply')
        Review.set_reply(review_id, text or None)           # an empty reply removes it

    def report(self, designer_id, review_id, reason):
        review = Review.find(review_id)
        if review is None:
            raise NotFoundError('Review not found.')
        if review['designer_id'] != designer_id:
            raise PermissionDenied('This review is not about you.')
        reason = self._check_text(reason, MAX_REASON, 'The reason')
        if not reason:
            raise ValidationError('Please say why you are reporting this review.')
        Review.set_report(review_id, reason)

    # ------------------------------------------------------------------ manager
    def moderation_queue(self):
        """All reviews with their integrity flags. Flagged/reported ones come first."""
        rows = [dict(r) for r in Review.find_for_moderation()]
        flags = flag_reviews(rows)
        for row in rows:
            row['flags'] = flags.get(row['id'], [])
            row['aspects_list'] = json.loads(row['aspects'] or '[]')
        rows.sort(key=lambda r: (-len(r['flags']), r['status'] == 'hidden'))
        return rows

    def hide(self, review_id, reason):
        review = Review.find(review_id)
        if review is None:
            raise NotFoundError('Review not found.')
        reason = self._check_text(reason, MAX_REASON, 'The reason')
        if not reason:
            raise ValidationError('Please give a reason for hiding the review.')
        Review.set_status(review_id, 'hidden', reason)

    def restore(self, review_id):
        if Review.find(review_id) is None:
            raise NotFoundError('Review not found.')
        Review.set_status(review_id, 'visible')

    def dismiss_report(self, review_id):
        if Review.find(review_id) is None:
            raise NotFoundError('Review not found.')
        Review.set_report(review_id, None)
