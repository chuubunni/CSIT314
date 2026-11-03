"""PlatformChartsController: input validation and the calculations."""
from datetime import date

import pytest

from idfinder.controller.errors import ValidationError
from idfinder.controller.platform_charts_controller import PlatformChartsController

TODAY = date(2026, 10, 22)
ctrl = PlatformChartsController()


# ===== PM21 START: tests for the weekly activity graph (control) =====
def test_blank_end_means_today(ctx):
    data = ctrl.weekly_activity('', today=TODAY)
    assert data['end'] == '2026-10-22' and data['start'] == '2026-10-16'
    assert ctrl.weekly_activity(None, today=TODAY)['end'] == '2026-10-22'


def test_window_is_exactly_seven_days(ctx):
    data = ctrl.weekly_activity('2026-10-20', today=TODAY)
    assert len(data['labels']) == 7
    assert data['labels'][0] == '2026-10-14' and data['labels'][-1] == '2026-10-20'


def test_week_crossing_a_month_boundary(ctx):
    data = ctrl.weekly_activity('2026-11-03', today=date(2026, 11, 10))
    assert data['labels'][0] == '2026-10-28'
    assert '2026-10-31' in data['labels'] and '2026-11-01' in data['labels']


@pytest.mark.parametrize('bad', ['abc', '2026-13-45', '22/10/2026', '2026-02-30'])
def test_invalid_dates_are_rejected(ctx, bad):
    with pytest.raises(ValidationError):
        ctrl.weekly_activity(bad, today=TODAY)


def test_future_week_is_rejected_but_today_is_allowed(ctx):
    with pytest.raises(ValidationError):
        ctrl.weekly_activity('2026-10-23', today=TODAY)
    assert ctrl.weekly_activity('2026-10-22', today=TODAY)['end'] == '2026-10-22'


def test_totals_and_change_against_previous_week(make):
    designer = make.user('designer', created='2026-01-01 00:00:00')
    project = make.project(designer, created='2026-01-01 00:00:00')
    for day in (15, 16, 17, 18, 19):                       # 5 views in 14..20 Oct
        make.view(project, f'2026-10-{day} 10:00:00')
    for day in (7, 8, 9, 10):                              # 4 views in 7..13 Oct
        make.view(project, f'2026-10-{day:02d} 10:00:00')
    data = ctrl.weekly_activity('2026-10-20', today=TODAY)
    assert data['totals']['views'] == 5
    assert data['previous_totals']['views'] == 4
    assert data['change']['views'] == 25                   # (5 - 4) / 4
    assert data['has_activity'] is True


def test_no_previous_week_data_gives_none_not_a_division_error(make):
    designer = make.user('designer', created='2026-10-16 10:00:00')   # 1 new user this week
    data = ctrl.weekly_activity('2026-10-20', today=TODAY)
    assert data['totals']['users'] == 1
    assert data['change']['users'] is None


def test_week_with_no_activity(ctx):
    data = ctrl.weekly_activity('2026-10-20', today=TODAY)
    assert data['has_activity'] is False
    assert all(total == 0 for total in data['totals'].values())


@pytest.mark.parametrize('current,previous,expected', [
    (5, 4, 25), (3, 4, -25), (1, 3, -67), (4, 4, 0), (0, 4, -100), (7, 0, None), (0, 0, None)])
def test_percent_change(current, previous, expected):
    assert ctrl.percent_change(current, previous) == expected


# ===== PM23 START: tests for interest by design category (control) =====
def test_interest_has_data_flag(make):
    result = ctrl.interest_by_category()
    assert result['categories'] == [] and result['has_data'] is False
    assert result['top_viewed'] is None and result['top_shortlisted'] is None
    make.category('Modern')
    assert ctrl.interest_by_category()['has_data'] is False     # category exists, no interest yet
    designer = make.user('designer')
    project = make.project(designer)
    make.tag(project, 1)
    make.view(project, '2026-10-10 10:00:00')
    assert ctrl.interest_by_category()['has_data'] is True


def test_dashboard_summary_counts_last_7_days_and_top_category(make):
    from datetime import date
    designer = make.user('designer')
    project = make.project(designer, created='2026-10-01 09:00:00')
    modern = make.category('Modern')
    make.tag(project, modern)
    make.view(project, '2026-10-20 10:00:00')     # inside the 7 days ending 2026-10-23
    make.view(project, '2026-10-01 10:00:00')     # too old
    summary = ctrl.get_dashboard_summary(today=date(2026, 10, 23))
    assert summary == {'weekly_views': 1, 'weekly_saves': 0, 'top_category': 'Modern', 'available': True}
