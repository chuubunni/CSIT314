"""PlatformCharts entity: the SQL behind PM21 (daily_activity) and PM21 (interest_by_category)."""
from datetime import date

from idfinder.entities.platform_charts import PlatformCharts

START, END = date(2026, 10, 14), date(2026, 10, 20)      # a 7-day window


# ===== PM21 START: tests for the weekly activity graph (entity) =====
def test_empty_database_gives_seven_zero_days(ctx):
    data = PlatformCharts.daily_activity(START, END)
    assert data['labels'] == ['2026-10-14', '2026-10-15', '2026-10-16', '2026-10-17',
                              '2026-10-18', '2026-10-19', '2026-10-20']
    for metric in ('projects', 'views', 'favourites', 'users'):
        assert data[metric] == [0] * 7


def test_days_without_activity_are_filled_with_zero(make):
    designer = make.user('designer', created='2026-09-01 00:00:00')
    project = make.project(designer, created='2026-09-01 00:00:00')
    make.view(project, '2026-10-15 10:00:00')
    make.view(project, '2026-10-15 11:00:00')
    make.view(project, '2026-10-18 08:00:00')
    data = PlatformCharts.daily_activity(START, END)
    assert data['views'] == [0, 2, 0, 0, 1, 0, 0]


def test_window_edges_are_whole_days(make):
    designer = make.user('designer', created='2026-09-01 00:00:00')
    project = make.project(designer, created='2026-09-01 00:00:00')
    make.view(project, '2026-10-13 23:59:59')     # last second before the window: out
    make.view(project, '2026-10-14 00:00:00')     # first second of the window: in
    make.view(project, '2026-10-20 23:59:59')     # last second of the window: in
    make.view(project, '2026-10-21 00:00:00')     # first second after the window: out
    data = PlatformCharts.daily_activity(START, END)
    assert data['views'] == [1, 0, 0, 0, 0, 0, 1]


def test_each_measure_comes_from_its_own_table(make):
    customer = make.user('customer', created='2026-10-16 09:00:00')          # 1 new user
    designer = make.user('designer', created='2026-10-16 10:00:00')          # 1 new user
    project = make.project(designer, created='2026-10-16 11:00:00')          # 1 new project
    make.view(project, '2026-10-16 12:00:00')                                # 1 view
    make.favourite(customer, project, '2026-10-16 13:00:00')                 # 1 favourite
    data = PlatformCharts.daily_activity(START, END)
    day = data['labels'].index('2026-10-16')
    assert data['users'][day] == 2
    assert data['projects'][day] == 1
    assert data['views'][day] == 1
    assert data['favourites'][day] == 1


def test_single_day_window(ctx):
    data = PlatformCharts.daily_activity(START, START)
    assert data['labels'] == ['2026-10-14']
    assert data['views'] == [0]


def test_end_before_start_is_rejected(ctx):
    import pytest
    with pytest.raises(ValueError):
        PlatformCharts.daily_activity(END, START)


# ===== PM21 CATEGORY INTEREST: tests for interest by design category (entity) =====
def _setup_categories(make):
    designer = make.user('designer')
    c1, c2 = make.user('customer'), make.user('customer')
    cat_a, cat_b, cat_c = make.category('Modern'), make.category('Scandinavian'), make.category('Industrial')
    p1, p2 = make.project(designer), make.project(designer)
    make.tag(p1, cat_a); make.tag(p1, cat_b)          # p1 is in two categories
    make.tag(p2, cat_a)
    for _ in range(3):
        make.view(p1, '2026-10-10 10:00:00')
    make.view(p2, '2026-10-10 10:00:00')
    make.favourite(c1, p1); make.favourite(c2, p1)
    return {r['name']: r for r in PlatformCharts.interest_by_category()}, cat_c


def test_project_in_two_categories_counts_in_both(make):
    rows, _ = _setup_categories(make)
    assert rows['Modern']['projects'] == 2 and rows['Modern']['views'] == 4 and rows['Modern']['favourites'] == 2
    assert rows['Scandinavian']['projects'] == 1 and rows['Scandinavian']['views'] == 3


def test_views_and_favourites_are_not_multiplied_by_the_join(make):
    # p1 has 3 views and 2 favourites. A careless double join gives 3 x 2 = 6 rows.
    rows, _ = _setup_categories(make)
    assert rows['Scandinavian']['views'] == 3
    assert rows['Scandinavian']['favourites'] == 2


def test_category_with_no_projects_is_kept_with_zeros(make):
    rows, _ = _setup_categories(make)
    assert rows['Industrial'] == {'id': rows['Industrial']['id'], 'name': 'Industrial', 'active': 1,
                                  'projects': 0, 'views': 0, 'favourites': 0}


def test_most_viewed_category_comes_first(make):
    _setup_categories(make)
    names = [r['name'] for r in PlatformCharts.interest_by_category()]
    assert names == ['Modern', 'Scandinavian', 'Industrial']


def test_ties_are_broken_by_shortlists_then_name(make):
    designer, customer = make.user('designer'), make.user('customer')
    zebra, apple, mango = make.category('Zebra'), make.category('Apple'), make.category('Mango')
    p_zebra, p_apple, p_mango = (make.project(designer) for _ in range(3))
    make.tag(p_zebra, zebra); make.tag(p_apple, apple); make.tag(p_mango, mango)
    for p in (p_zebra, p_apple, p_mango):
        make.view(p, '2026-10-10 10:00:00')                 # all tied on 1 view
    make.favourite(customer, p_zebra)                       # Zebra has 1 shortlist: first
    names = [r['name'] for r in PlatformCharts.interest_by_category()]
    assert names == ['Zebra', 'Apple', 'Mango']             # then A..Z for the rest


def test_inactive_categories_are_included_and_flagged(make):
    make.category('Retired', active=0)
    rows = PlatformCharts.interest_by_category()
    assert rows[0]['name'] == 'Retired' and rows[0]['active'] == 0


def test_no_categories_returns_empty_list(ctx):
    assert PlatformCharts.interest_by_category() == []
