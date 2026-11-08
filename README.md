# How to run the website:

For cmd

'''
py -3 -m venv .venv
'''
.venv\Scripts\activate

pip install -r requirements.txt

pip install -r idfinder\requirements-image-review.txt

flask --app idfinder init-image-search

flask --app idfinder index-images


