"""Real route/SQLite regressions for the reported v2 failures; no live AI calls."""
from datetime import date
import sqlite3
import time
from unittest.mock import patch

import pytest

from idfinder.controller.auth_controller import auth_control
from idfinder.controller.errors import ValidationError
from idfinder.controller.platform_charts_controller import PlatformChartsController
from idfinder.controller.review_controller import ReviewController
from idfinder.db import get_db
from idfinder.entities.platform_charts import PlatformCharts
from idfinder.entities.review import Review


CHARTS = ('weekly', 'trend', 'heatmap', 'category-trend')


def login(app, user):
    client = app.test_client()
    with client.session_transaction() as session:
        session['user_id'] = user
        session['story_form_token'] = 'regression-token'
    return client


@pytest.mark.parametrize('chart', CHARTS)
@pytest.mark.parametrize('end', ['0001-01-01','0001-01-14','0001-02-01','0001-02-25','1999-12-31','not-a-date','9999-12-31'])
def test_all_chart_routes_reject_invalid_or_underflowing_dates(app, make, chart, end):
    client = login(app, make.user('manager'))
    response = client.get('/platform/charts/'+chart, query_string={'end': end})
    assert response.status_code == 400
    assert isinstance(response.json['error'], str)


@pytest.mark.parametrize('chart', CHARTS)
def test_earliest_supported_chart_date_is_safe(app, make, chart):
    response = login(app, make.user('manager')).get('/platform/charts/'+chart, query_string={'end':'2000-01-01'})
    assert response.status_code == 200


def test_every_chart_measure_excludes_unpublished_projects(make):
    db = get_db()
    customer, designer = make.user(), make.user('designer')
    category = make.category('Regression style')
    for state in ('approved','draft','pending','rejected'):
        project = make.project(designer, created='2026-10-20 09:00:00')
        db.execute('UPDATE idp SET approval_status=? WHERE id=?', (state,project));db.commit()
        make.tag(project,category)
        make.view(project,'2026-10-20 10:00:00')
        make.favourite(customer,project,'2026-10-20 11:00:00')
    start=end=date(2026,10,20)
    daily=PlatformCharts.daily_activity(start,end)
    assert daily['projects']==[1]
    assert daily['views']==[1]
    assert daily['favourites']==[1]
    assert sum(sum(row) for row in PlatformCharts.views_by_weekday_hour(start,end))==1
    _, series=PlatformCharts.weekly_category_views(end)
    assert sum(series[category]['weeks'])==1
    row=next(r for r in PlatformCharts.interest_by_category() if r['id']==category)
    assert (row['projects'],row['views'],row['favourites'])==(1,1,1)


@pytest.mark.parametrize('digits',[20,200,5000])
def test_oversized_route_ids_return_404_before_sql(app, digits):
    client=app.test_client()
    response=client.get('/designers/'+'9'*digits)
    assert response.status_code==404


def test_repeated_create_form_does_not_edit_or_duplicate_review(app,make):
    c,d=make.user(),make.user('designer');job=make.engagement(c,d)
    client=login(app,c)
    data={'form_token':'regression-token','review_id':'','review_revision':'','rating':'5','comment':'A useful consultation.'}
    assert client.post(f'/jobs/{job}/review',data=data).status_code==302
    original=dict(Review.find_by_engagement(job))
    response=client.post(f'/jobs/{job}/review',data=data)
    assert response.status_code in (200,302,303,409)
    assert dict(Review.find_by_engagement(job))==original


def test_racing_duplicate_insert_is_handled_and_transaction_rolled_back(app,make):
    c,d=make.user(),make.user('designer');job=make.engagement(c,d)
    existing=make.review(job)
    db=get_db()
    client=login(app,c)
    with patch.object(Review,'find_by_engagement',return_value=None):
        response=client.post(f'/jobs/{job}/review',data={'form_token':'regression-token','rating':'4','comment':'Second click'})
    assert response.status_code in (200,302,303,409)
    assert not db.in_transaction
    assert db.execute('SELECT count(*) FROM review WHERE engagement_id=?',(job,)).fetchone()[0]==1
    assert Review.find(existing)['rating']==5


def test_hidden_review_and_fourth_edit_rejected_atomically(make):
    c,d=make.user(),make.user('designer');job=make.engagement(c,d)
    review=make.review(job)
    ctrl=ReviewController()
    for i in range(3):ctrl.edit(c,review,4,f'Edited version {i}')
    assert Review.find(review)['edit_count']==3
    with pytest.raises(ValidationError):ctrl.edit(c,review,2,'Fourth edit')
    stale=dict(Review.find(review));stale['edit_count']=2
    with patch.object(ctrl,'_own_review',return_value=stale):
        with pytest.raises(ValidationError):ctrl.edit(c,review,1,'Stale edit')
    assert Review.find(review)['edit_count']==3
    stale=dict(Review.find(review));stale['edit_count']=0
    Review.set_status(review,'hidden','Manager decision')
    with patch.object(ctrl,'_own_review',return_value=stale):
        with pytest.raises(ValidationError):ctrl.edit(c,review,1,'After moderation')
    assert Review.find(review)['hidden_reason']=='Manager decision'
    assert Review.find(review)['comment']=='Edited version 2'


def test_hidden_and_final_reviews_have_no_edit_controls(app,make):
    c,d=make.user(),make.user('designer');job=make.engagement(c,d)
    review=make.review(job,status='hidden')
    client=login(app,c)
    html=client.get(f'/jobs/{job}/review').get_data(as_text=True)
    assert 'cannot be changed' in html
    assert 'class="rv-form"' not in html
    Review.set_status(review,'visible')
    get_db().execute('UPDATE review SET edit_count=3 WHERE id=?',(review,));get_db().commit()
    html=client.get(f'/jobs/{job}/review').get_data(as_text=True)
    assert '3 edits' in html
    assert 'class="rv-form"' not in html


def test_public_manager_registration_is_not_available_or_accepted(app,make):
    db=get_db();count=db.execute('SELECT count(*) FROM user').fetchone()[0]
    client=app.test_client()
    assert 'value="manager"' not in client.get('/auth/register').get_data(as_text=True)
    response=client.post('/auth/register',data={'name':'Untrusted','password':'pw','email':'no-manager@example.test','phone':'81234567','type':'manager'})
    assert response.status_code in (200,400,403)
    assert db.execute('SELECT count(*) FROM user').fetchone()[0]==count
    assert db.execute("SELECT id FROM user WHERE email='no-manager@example.test'").fetchone() is None


def test_real_sqlite_lock_returns_503_promptly_and_recovers(app,make):
    manager=make.user('manager');db=get_db()
    db.execute('PRAGMA busy_timeout=50')
    client=login(app,manager)
    lock=sqlite3.connect(app.config['DATABASE'])
    try:
        lock.execute('BEGIN EXCLUSIVE')
        started=time.monotonic()
        response=client.get('/platform/charts/weekly')
        assert response.status_code==503
        assert response.headers['Retry-After']=='1'
        assert isinstance(response.json['error'],str)
        assert time.monotonic()-started < 2
    finally:
        lock.rollback();lock.close()
    assert client.get('/platform/charts/weekly').status_code==200


def test_real_write_lock_returns_503_without_partial_review_then_recovers(app,make):
    c,d=make.user(),make.user('designer');job=make.engagement(c,d)
    db=get_db();db.execute('PRAGMA busy_timeout=50')
    client=login(app,c)
    payload={'form_token':'regression-token','review_id':'','review_revision':'','rating':'4','comment':'Helpful advice.'}
    lock=sqlite3.connect(app.config['DATABASE'])
    try:
        lock.execute('BEGIN IMMEDIATE')
        started=time.monotonic()
        response=client.post(f'/jobs/{job}/review',data=payload)
        assert response.status_code==503
        assert response.headers['Retry-After']=='1'
        assert time.monotonic()-started < 2
        assert not db.in_transaction
        assert Review.find_by_engagement(job) is None
    finally:
        lock.rollback();lock.close()
    assert client.post(f'/jobs/{job}/review',data=payload).status_code==302
    assert db.execute('SELECT count(*) FROM review WHERE engagement_id=?',(job,)).fetchone()[0]==1


def test_dashboard_report_excludes_private_project_activity(make):
    from datetime import datetime,timezone
    from idfinder.entities.platform_report import PlatformReport
    stamp=datetime.now(timezone.utc).replace(tzinfo=None).strftime('%Y-%m-%d %H:%M:%S')
    db=get_db();c,d=make.user(),make.user('designer')
    ids=[]
    for status in ('approved','draft','rejected','pending'):
        project=make.project(d,created=stamp);ids.append(project)
        db.execute('UPDATE idp SET approval_status=? WHERE id=?',(status,project));db.commit()
        make.view(project,stamp);make.favourite(c,project,stamp)
    summary=PlatformReport.overview('daily')
    assert summary['projects']==summary['views']==summary['favourites']==1
    assert [r['id'] for r in PlatformReport.interest()]==ids[:1]
