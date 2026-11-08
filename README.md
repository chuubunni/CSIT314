How to run:
py -3 -m venv .venv

.venv\Scripts\activate

pip install -r requirements.txt

flask --app idfinder init-image-search

flask --app idfinder index-images

If you want to try the bot locally, run this in your terminal before launching flask

CMD:
set “GEMINI_API_KEY=AQ.Ab8RN6JX1vMkgc-fEWnXbWKrqg1e0TCKgA3_1fAmrP5XUvkkVQ”
set “GEMINI_MODEL=gemini-3.5-flash-lite”


PS:
$env:GEMINI_API_KEY = “AQ.Ab8RN6JX1vMkgc-fEWnXbWKrqg1e0TCKgA3_1fAmrP5XUvkkVQ”
$env:GEMINI_MODEL = “gemini-3.5-flash-lite”
