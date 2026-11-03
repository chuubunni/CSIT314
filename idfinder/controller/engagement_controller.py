from idfinder.controller.errors import NotFoundError, PermissionDenied, ValidationError
from idfinder.entities.engagement import Engagement
from idfinder.entities.idp import IDP
from idfinder.entities.user import Users

MAX_TITLE = 100
MAX_MESSAGE = 1000
MAX_OPEN_PER_DESIGNER = 3      # a customer may have at most 3 unfinished jobs with one designer

# The only allowed moves between states. Anything else is refused.
TRANSITIONS = {
    'requested': {'ongoing', 'declined', 'cancelled'},
    'ongoing': {'completed', 'cancelled'},
}


class EngagementController:
    """Control: the rules for hiring a designer.

    customer asks  -> requested
    designer says yes -> ongoing, or no -> declined
    designer finishes -> completed   (this unlocks the customer's review)
    customer may withdraw while requested/ongoing -> cancelled
    """

    def request(self, customer_id, designer_id, title, message='', idp_id=None):
        title = ' '.join((title or '').split())
        message = (message or '').strip()
        if not 3 <= len(title) <= MAX_TITLE:
            raise ValidationError(f'Please describe the job in 3 to {MAX_TITLE} characters.')
        if len(message) > MAX_MESSAGE:
            raise ValidationError(f'The message must be {MAX_MESSAGE} characters or fewer.')

        designer = Users.get_info(designer_id)
        if designer is None or designer['Usertype'] != 'designer':
            raise NotFoundError('Designer not found.')
        if idp_id not in (None, ''):
            try:
                idp_id = int(idp_id)
            except (TypeError, ValueError):
                raise ValidationError('Please choose a valid project.')
            project = IDP.find(idp_id)
            if project is None or project['designer_id'] != designer_id or project['approval_status'] != 'approved':
                raise ValidationError('That project does not belong to this designer.')
        else:
            idp_id = None
        if Engagement.count_open(customer_id, designer_id) >= MAX_OPEN_PER_DESIGNER:
            raise ValidationError('You already have several unfinished jobs with this designer.')
        return Engagement.create(customer_id, designer_id, title, message, idp_id)

    def _load(self, engagement_id):
        engagement = Engagement.find(engagement_id)
        if engagement is None:
            raise NotFoundError('Job not found.')
        return engagement

    @staticmethod
    def _move(engagement, new_status):
        if new_status not in TRANSITIONS.get(engagement['status'], ()):
            raise ValidationError(f"A {engagement['status']} job cannot become {new_status}.")
        Engagement.set_status(engagement['id'], new_status)

    def accept(self, designer_id, engagement_id):
        engagement = self._load(engagement_id)
        if engagement['designer_id'] != designer_id:
            raise PermissionDenied('This job is not yours.')
        self._move(engagement, 'ongoing')

    def decline(self, designer_id, engagement_id):
        engagement = self._load(engagement_id)
        if engagement['designer_id'] != designer_id:
            raise PermissionDenied('This job is not yours.')
        self._move(engagement, 'declined')

    def complete(self, designer_id, engagement_id):
        engagement = self._load(engagement_id)
        if engagement['designer_id'] != designer_id:
            raise PermissionDenied('This job is not yours.')
        self._move(engagement, 'completed')

    def cancel(self, customer_id, engagement_id):
        engagement = self._load(engagement_id)
        if engagement['customer_id'] != customer_id:
            raise PermissionDenied('This job is not yours.')
        self._move(engagement, 'cancelled')

    def for_customer(self, customer_id):
        return Engagement.find_for_customer(customer_id)

    def for_designer(self, designer_id):
        return Engagement.find_for_designer(designer_id)