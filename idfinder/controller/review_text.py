"""Reads the text of a review: how positive is it, and WHICH parts of the service does it praise
or criticise? Pure functions: no Flask, no database.

Sentiment uses the VADER library when it is installed (pip install vaderSentiment) and a small
built-in word list when it is not, so the site never breaks because a library is missing.

SENTIMENT -> one number from -1 (very negative) to +1 (very positive).
ASPECTS   -> for every sentence that mentions a topic (communication, timeliness, budget,
             creativity, quality, professionalism) the polarity (+1 / -1) of that sentence.
"""
import math
import re

try:                                                     # optional library
    from vaderSentiment.vaderSentiment import SentimentIntensityAnalyzer
    _VADER = SentimentIntensityAnalyzer()
except Exception:                                        # not installed -> fallback below
    _VADER = None

# A keyword matches the START of a word ("respons" -> "responsive", "responded").
# A keyword beginning with "=" must be a whole word ("=late" matches "late", not "plate").
ASPECTS = {
    'communication': ('communicat', 'respons', 'responded', 'replied', 'reply', 'update', 'listen',
                      'message', 'whatsapp', 'answer', 'explain', 'informed', '=touch'),
    'timeliness': ('on time', 'deadline', 'delay', '=late', 'schedule', 'punctual', 'prompt',
                   '=quick', '=slow', 'behind', '=fast', 'timeline', 'weeks', 'ahead of'),
    'budget': ('budget', 'price', '=cost', 'quote', 'expensive', 'cheap', 'afford', '=value',
               'overcharg', 'hidden fee', '=fees'),
    'creativity': ('creativ', '=idea', '=style', 'concept', 'aesthetic', 'layout', 'unique',
                   'inspir', 'vision', 'taste'),
    'quality': ('quality', 'craftsmanship', 'finish', 'workmanship', 'material', 'defect',
                'neat', 'durable', 'flaw', 'mistake', 'detail', '=result'),
    'professionalism': ('professional', '=trust', 'honest', 'reliable', 'courteous', 'attitude',
                        '=rude', 'polite', 'respect', 'friendly', 'patient', 'pushy'),
}


def _mentions(piece, keywords):
    for keyword in keywords:
        if keyword.startswith('='):
            pattern = r'\b' + re.escape(keyword[1:]) + r'(s|es|ed)?\b'
        else:
            pattern = r'\b' + re.escape(keyword)
        if re.search(pattern, piece):
            return True
    return False


_POSITIVE = {'good', 'great', 'excellent', 'amazing', 'awesome', 'love', 'loved', 'perfect', 'happy',
             'wonderful', 'fantastic', 'recommend', 'recommended', 'professional', 'helpful',
             'friendly', 'beautiful', 'creative', 'smooth', 'impressed', 'satisfied', 'responsive',
             'reliable', 'patient', 'honest', 'prompt', 'neat', 'stunning', 'worth', 'fast', 'quick'}
_NEGATIVE = {'bad', 'poor', 'terrible', 'awful', 'horrible', 'hate', 'worst', 'disappointed',
             'disappointing', 'late', 'delay', 'delayed', 'rude', 'slow', 'expensive', 'overpriced',
             'mistake', 'mistakes', 'defect', 'defects', 'unprofessional', 'ignored', 'avoid',
             'waste', 'messy', 'unresponsive', 'pushy', 'overcharged', 'problem', 'problems', 'worse'}
_NEGATIONS = {'not', "n't", 'never', 'no', 'without', 'hardly'}


def engine_name():
    return 'VADER' if _VADER is not None else 'built-in word list'


def _fallback_score(text):
    """Word-list sentiment with simple negation ("not good" flips). Result in -1..1."""
    words = re.findall(r"[a-z']+", text.lower())
    total = 0
    for i, word in enumerate(words):
        value = 1 if word in _POSITIVE else -1 if word in _NEGATIVE else 0
        if value and any(w in _NEGATIONS or w.endswith("n't") for w in words[max(0, i - 2):i]):
            value = -value                               # "not good", "never late"
        total += value
    return math.tanh(total / 2.0)                        # squash the count into -1..1


def sentiment(text):
    """-1..1, or None when there is no text to read."""
    text = (text or '').strip()
    if not text:
        return None
    if _VADER is not None:
        return round(_VADER.polarity_scores(text)['compound'], 4)
    return round(_fallback_score(text), 4)


def aspects(text):
    """[{'aspect': 'communication', 'polarity': 1}, ...] one entry per topic that was mentioned
    with a clear opinion (neutral mentions are ignored)."""
    found = {}
    # a sentence, or half a sentence around "but", is the unit that gets a polarity
    pieces = re.split(r'[.!?;\n]+|\bbut\b|\bhowever\b', (text or '').lower())
    for piece in pieces:
        piece = piece.strip()
        if not piece:
            continue
        score = sentiment(piece)
        if score is None or abs(score) < 0.2:
            continue
        polarity = 1 if score > 0 else -1
        for aspect, keywords in ASPECTS.items():
            if _mentions(piece, keywords):
                found.setdefault(aspect, []).append(polarity)
    # several mentions of one topic: the majority wins; a tie is treated as no clear opinion
    result = []
    for aspect, votes in found.items():
        net = sum(votes)
        if net:
            result.append({'aspect': aspect, 'polarity': 1 if net > 0 else -1})
    return sorted(result, key=lambda a: a['aspect'])


def analyse(text):
    """Everything the review controller stores: (sentiment, aspects)."""
    return sentiment(text), aspects(text)
