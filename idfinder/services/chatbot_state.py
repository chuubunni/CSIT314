# C18: AI customer chat assistant, search results and relevant page navigation.
"""C18: short-lived server memory for this single-process local prototype."""
from collections import deque
from copy import deepcopy
from threading import Lock
from time import monotonic
from idfinder.services.gemini_chat import ChatbotUnavailable


class ChatbotState:
    def __init__(self):
        self.lock = Lock()
        self.conversations = {}
        self.requests = {}
        self.busy = set()

    # C18: expire stale conversations and limit API requests per customer.
    def begin(self, key, user_id):
        now = monotonic()
        with self.lock:
            self.conversations = {k: v for k, v in self.conversations.items() if now - v[0] < 1800}
            self.requests = {k: v for k, v in self.requests.items() if v and now - v[-1] < 60}
            if user_id in self.busy:
                raise ChatbotUnavailable('Please wait for your previous message to finish.', 429)
            times = self.requests.setdefault(user_id, deque())
            while times and now - times[0] >= 60:
                times.popleft()
            if len(times) >= 10:
                raise ChatbotUnavailable('Please wait a minute before sending more messages.', 429)
            if key not in self.conversations and len(self.conversations) >= 500:
                self.conversations.pop(min(self.conversations, key=lambda k: self.conversations[k][0]))
            times.append(now)
            self.busy.add(user_id)
            return deepcopy(self.conversations.get(key, (now, {}))[1])

    # C18: save validated conversation state after a message completes.
    def finish(self, key, user_id, state=None):
        with self.lock:
            if state is not None:
                self.conversations[key] = (monotonic(), deepcopy(state))
            self.busy.discard(user_id)

    def clear(self, key, user_id):
        with self.lock:
            if user_id in self.busy:
                raise ChatbotUnavailable('Wait for the current reply before starting a new chat.', 429)
            self.conversations.pop(key, None)
            # C18: clearing conversation never resets the user's API rate limit.

    # C18: restore private recent messages without making an AI request.
    def history(self, key, user_id):
        with self.lock:
            now = monotonic()
            entry = self.conversations.get(key)
            state = entry[1] if entry and now - entry[0] < 1800 else {}
            return deepcopy(state.get('transcript', [])), user_id in self.busy
