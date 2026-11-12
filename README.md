# How to run the website:

1. Clone the repository:

```bash
git clone https://github.com/chuubunni/CSIT314.git
cd CSIT314
```

2. Set up virtual environment:

```bash
py -3 -m venv .venv
.venv\Scripts\activate
```

3. Install requirements:

```bash
pip install -r requirements.txt
pip install -r idfinder\requirements-image-review.txt
```
4. Initialize indexes for customer search by image:

```bash
flask --app idfinder init-image-search
flask --app idfinder index-images
```

5. Run the website:

```bash
flask --app idfinder run
```

NOTE: test data is already loaded inside the website by default. The default password for all test accounts is 123. 

Sample test accounts: 

Designer: chloe.teo@mail.com

Customer: jessica.chew@mail.com

Manager: theo@mail.com




