"""New graph data: trend, heatmap, category trend, ratings overview - controller rules and routes."""
from datetime import date, timedelta

import pytest

from idfinder.controller.errors import ValidationError
from idfinder.controller.platform_charts_controller import PlatformChartsController

TODAY = date(2026, 10, 31)


@pytest.fixture
def data(ctx, make):
    d = make.user('designer')
    c1, c2 = make.category('Modern'), make.category('Classic')
    p1, p2 = make.project(d), make.project(d)
    make.tag(p1, c1); make.tag(p2, c1); make.tag(p2, c2)
    return {'d': d, 'p1': p1, 'p2': p2}


def test_trend_rejects_unknown_metric(ctx):
    with pytest.raises(ValidationError):
        PlatformChartsController().trend('money', None, TODAY)


def test_trend_contract_and_zero_fill(data, make):
    make.view(data['p1'], '2026-10-30 10:00:00')
    t = PlatformChartsController().trend('views', None, TODAY)
    assert len(t['labels']) == len(t['values']) == len(t['moving_average']) == len(t['previous_week']) == 28
    assert t['values'][-2] == 1 and sum(t['values']) == 1 and t['partial_today'] is True
    assert t['forecast'] is None or len(t['forecast']['values']) == 7


def test_forecast_only_when_week_ends_today(data, make):
    for i in range(30):
        make.view(data['p1'], f'{(TODAY - timedelta(days=i + 1)).isoformat()} 10:00:00')
    c = PlatformChartsController()
    assert c.trend('views', None, TODAY)['forecast'] is not None
    assert c.trend('views', (TODAY - timedelta(days=3)).isoformat(), TODAY)['forecast'] is None


def test_todays_partial_count_is_not_flagged_or_used(data, make):
    for i in range(45):
        for _ in range(10):
            make.view(data['p1'], f'{(TODAY - timedelta(days=i + 1)).isoformat()} 10:00:00')
    t = PlatformChartsController().trend('views', None, TODAY)          # today has 0 views so far
    assert t['anomalies'] == []


def test_heatmap_offset_and_validation(data, make):
    make.view(data['p1'], '2026-10-30 22:00:00')            # Friday 22:00 UTC = Saturday 06:00 in Singapore
    c = PlatformChartsController()
    utc, sg = c.heatmap(None, None, TODAY), c.heatmap(None, '480', TODAY)
    assert utc['grid'][4][22] == 1 and sg['grid'][5][6] == 1 and sg['total'] == 1
    assert sg['peak'] == {'day': 'Sat', 'hour': 6, 'count': 1}
    for bad in ('abc', '99999', '-800', '1.5'):
        with pytest.raises(ValidationError):
            c.heatmap(None, bad, TODAY)


def test_interest_counts_are_not_multiplied(data, make):
    cust = make.user('customer')
    make.view(data['p2'], '2026-10-30 10:00:00'); make.view(data['p2'], '2026-10-30 11:00:00')
    make.favourite(cust, data['p2'])
    r = PlatformChartsController().interest_by_category()
    by = {x['name']: x for x in r['categories']}
    assert by['Modern']['views'] == 2 and by['Classic']['views'] == 2 and by['Modern']['favourites'] == 1
    assert by['Modern']['shortlist_rate'] == 50.0


def test_category_trend_groups_into_other_and_growth(ctx, make):
    d = make.user('designer')
    p = make.project(d)
    for i in range(7):
        make.tag(p, make.category(f'Cat{i}'))
    for w in range(8):
        make.view(p, f'{(TODAY - timedelta(days=w * 7 + 1)).isoformat()} 10:00:00')
    r = PlatformChartsController().category_trend(None, TODAY)
    assert len(r['series']) == 6 and r['series'][-1]['name'] == 'Other'
    assert all(len(s['data']) == 8 for s in r['series'])


def test_ratings_overview_ignores_hidden_reviews(ctx, make):
    d = make.user('designer')
    make.reviewed_job(d, 5, 'great', 0.5, created='2026-10-10 09:00:00')
    hidden = make.reviewed_job(d, 1, 'bad', -0.5, created='2026-10-11 09:00:00')
    from idfinder.db import get_db
    get_db().execute("UPDATE review SET status = 'hidden' WHERE rating = 1"); get_db().commit()
    r = PlatformChartsController().ratings_overview(TODAY)
    assert r['total'] == 1 and r['distribution'][5] == 1 and r['distribution'][1] == 0
    assert len(r['monthly']) == 6 and r['monthly'][-1]['label'] == '2026-10'


def test_new_routes_need_manager_and_validate(client, make):
    for path in ('trend', 'heatmap', 'category-trend', 'ratings'):
        assert client.get(f'/platform/charts/{path}').status_code == 401
    make.user('customer'); client.login('user1@test.com')
    assert client.get('/platform/charts/trend').status_code == 403


def test_new_routes_as_manager(client, make):
    m = make.user('manager')
    client.login(make.email(m))
    for path in ('trend', 'heatmap', 'category-trend', 'ratings', 'trend?metric=users', 'heatmap?tz=480'):
        r = client.get(f'/platform/charts/{path}')
        assert r.status_code == 200 and r.is_json, path
    assert client.get('/platform/charts/trend?metric=nope').status_code == 400
    assert client.get('/platform/charts/heatmap?tz=zzz').status_code == 400
    assert client.get('/platform/charts/trend?end=2020-13-45').status_code == 400
    page = client.get('/platform/charts/')
    assert page.status_code == 200 and b'id="weekly-chart"' in page.data and b'id="category-chart"' in page.data and b'id="ratings-chart"' in page.data
