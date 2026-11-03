# C18 Uncle David leaderboard search

Uncle David can now search the existing designer leaderboard. The integration reuses LeaderboardController and ranking.py, so scores, review visibility, priors, weights and ties follow the same rules as the leaderboard page. The ranking algorithm and database are unchanged.

Try these as a logged-in customer:

- Show the top 5 designers.
- Show the top 3 Modern HDB designers.
- Find the highest-rated Condo designers with at least 5 reviews.
- Show the most reliable designers.
- Only HDB designers. (A follow-up to the previous leaderboard search.)
- Open the leaderboard.
- How does the leaderboard score work?

Results show the current rank, score, visible review count, review average when available and completed jobs. Each card links to the existing designer profile. View full leaderboard carries the validated filters and all five weights to the existing page. Designers with no visible reviews are labelled honestly; baseline ranking values are not displayed as an actual customer review average.

The Top designers suggestion provides a quick entry from the floating widget. Ranking cards remain in the conversation history when navigating between pages.

The existing board supports one active design category, one housing type, a minimum of 0–50 visible reviews and five weights from 0–100. Chat previews 1–10 designers, defaulting to 5. Highest-rated prioritises the board's Bayesian star-rating component, not the raw average alone. Project-only criteria such as room subtype, project price and title/description location are not leaderboard filters; unsupported combinations require clarification. Existing project searches continue to support style, housing and content alternatives.

Gemini interprets the ranking request into structured options. Python validates the options and retrieves actual results. Fresh ranking searches start without previous project/ranking constraints; explicit follow-ups retain only the relevant ranking context. No API key, AI-generated SQL or private account fields are exposed to the browser.

Edited/new integration sections have C18 comments. Test with:

```bat
.venv\Scripts\python.exe -B -m unittest discover -s tests -p "test_c18_leaderboard.py" -v
```

The tests use an isolated database and simulated Gemini output. Restart Flask and refresh the browser after installing the changes. The widget script version was updated to refresh cached JavaScript. The existing server-side Gemini configuration remains in place.
