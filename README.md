# How to run the website:

1. Set up virtual environment:

```bash
py -3 -m venv .venv
.venv\Scripts\activate
```

2. Install requirements:

```bash
pip install -r requirements.txt
pip install -r idfinder\requirements-image-review.txt
```
3. Initialize indexes for customer search by image:

```bash
flask --app idfinder init-image-search
flask --app idfinder index-images
```

4. Run the website:

```bash
flask --app idfinder run
```

NOTE: test data is already loaded inside the website by default.




