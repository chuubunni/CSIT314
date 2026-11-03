"""BOUNDARY tests: the pages and JSON routes behind the graphs, and who may use them.
PM21 = /platform/charts/weekly      PM23 = /platform/charts/categories
Dashboard summary = /platform/ shows a summary and links to /platform/charts/"""


def test_visitor_is_redirected_to_login(client):
    # the page redirects to the login page; the JSON routes answer 401 (a redirect would break fetch())
    page = client.get('/platform/charts/')
    assert page.status_code == 302 and '/auth/login' in page.headers['Location']
    assert client.get('/platform/charts/weekly').status_code == 401
    assert client.get('/platform/charts/categories').status_code == 401


def test_customer_is_forbidden(client, make):
    make.user('customer')
    client.login('user1@test.com')
    assert client.get('/platform/charts/weekly').status_code == 403
    assert client.get('/platform/charts/categories').status_code == 403


def test_designer_is_forbidden(client, make):
    make.user('designer')
    client.login('user1@test.com')
    assert client.get('/platform/charts/categories').status_code == 403


# ===== PM21 START: weekly route =====
def test_manager_gets_weekly_json(client, make):
    make.user('manager')
    client.login('user1@test.com')
    response = client.get('/platform/charts/weekly?end=2026-10-20')
    assert response.status_code == 200
    body = response.get_json()
    assert len(body['labels']) == 7 and body['end'] == '2026-10-20'
    assert set(body['series']) == {'projects', 'views', 'favourites', 'users'}


def test_manager_gets_error_for_bad_date(client, make):
    make.user('manager')
    client.login('user1@test.com')
    response = client.get('/platform/charts/weekly?end=not-a-date')
    assert response.status_code == 400
    assert 'valid date' in response.get_json()['error']


# ===== PM23 START: category route =====
def test_manager_gets_category_json(client, make):
    make.user('manager')
    make.category('Modern')
    client.login('user1@test.com')
    body = client.get('/platform/charts/categories').get_json()
    assert body['categories'][0]['name'] == 'Modern'


def test_charts_page_contains_both_sections(client, make):
    make.user('manager')
    client.login('user1@test.com')
    html = client.get('/platform/charts/').get_data(as_text=True)
    assert 'id="weekly-chart"' in html and 'id="category-chart"' in html


def test_charts_page_needs_a_manager(client, make):
    assert client.get('/platform/charts/').status_code == 302          # visitor
    make.user('customer')
    client.login('user1@test.com')
    assert client.get('/platform/charts/').status_code == 403          # customer


def test_dashboard_shows_summary_and_links_to_detailed_graphs(client, make):
    make.user('manager')
    client.login('user1@test.com')
    html = client.get('/platform/').get_data(as_text=True)
    assert 'id="charts-summary"' in html
    assert 'id="weekly-chart"' not in html
    assert 'href="/platform/charts/"' in html          # link to the detailed graphs page
    assert 'id="weekly-chart"' not in html             # the full graphs stay on their own page


def test_graph_assets_are_served(client):
    assert client.get('/static/vendor/chart.umd.js').status_code == 200
    assert client.get('/static/platform_charts.js').status_code == 200
