from datetime import datetime,timedelta
from decimal import Decimal
import pytest
from app.clock import aware
from app.features import frozen_vector,validate_source,three_month_cutoff,eligible_history
from app.validation import chronological_split,brier,fit_platt

START=aware("2026-10-13T19:00:00-07:00")
def history(n=10):
    return [{"started_at":(START-timedelta(days=i+1)).isoformat(),"ended_at":(START-timedelta(days=i+1)+timedelta(hours=3)).isoformat(),"win":i%2==0} for i in range(n)]

def test_frozen_vector_exact_order_and_target_date_exclusion():
    same_day={"started_at":(START-timedelta(hours=10)).isoformat(),"ended_at":(START-timedelta(hours=7)).isoformat(),"win":True}
    vector=frozen_vector({"games":5,"points_pct":.6},{"games":6,"points_pct":.4},{"home":history()+[same_day],"away":history(3)},START)
    assert len(vector)==15
    assert vector[:5]==pytest.approx([.6,.4,.2,5,6])
    assert vector[8:10]==[10,3]
    assert vector[10:]==[0,0,0,1,1]
    with pytest.raises(ValueError): frozen_vector({"games":4,"points_pct":.6},{"games":6,"points_pct":.4},{"home":history(),"away":history()},START)

@pytest.mark.parametrize("kind,hours",[("schedule",2),("standings",3),("history",26)])
def test_source_ages_and_postdate(kind,hours):
    anchor=START-timedelta(minutes=30)
    validate_source(kind,anchor-timedelta(hours=hours),anchor,anchor)
    with pytest.raises(ValueError): validate_source(kind,anchor-timedelta(hours=hours,seconds=1),anchor,anchor)
    with pytest.raises(ValueError): validate_source(kind,anchor,anchor+timedelta(seconds=1),anchor)
    with pytest.raises(ValueError): validate_source(kind,anchor+timedelta(seconds=1),anchor,anchor)

def test_timezone_dst_and_rolling_calendar_months():
    with pytest.raises(ValueError): aware(datetime(2026,10,13))
    assert three_month_cutoff(aware("2026-05-31T12:00:00-07:00")).day==28
    assert aware("2025-11-02T08:30:00Z").utcoffset()!=aware("2025-11-02T09:30:00Z").utcoffset()
    assert aware("2026-11-01T08:30:00Z").utcoffset()==aware("2026-11-01T09:30:00Z").utcoffset()==timedelta(hours=-7)
    games=history()+[{"started_at":"2026-07-01T12:00:00-07:00","ended_at":"2026-07-01T15:00:00-07:00","win":True}]
    assert len(eligible_history(games,START,True))==10

def test_overlapping_history_rejected():
    games=history(3);games[1]["ended_at"]=games[0]["ended_at"]
    with pytest.raises(ValueError): eligible_history(games,START)

def test_chronological_split_date_groups_and_embargo():
    records=[{"commence_time":(START+timedelta(days=i//10)).isoformat()} for i in range(600)]
    train,cal,test,embargo=chronological_split(records)
    assert [len(train),len(cal),len(test)]==[360,110,110]
    all_used={aware(r["commence_time"]).date() for r in train+cal+test}
    assert not set(embargo)&all_used
    assert max(aware(r["commence_time"]) for r in train)<min(aware(r["commence_time"]) for r in cal)
    with pytest.raises(ValueError): chronological_split(records[:300])

def test_brier_and_calibration_boundaries():
    assert brier([Decimal('.5'),Decimal('.5')],[0,1])==Decimal('.25')
    assert brier([0,1],[0,1])==0
    with pytest.raises(ValueError): brier([1.2],[1])
    with pytest.raises(ValueError): brier([],[])
    with pytest.raises(ValueError): fit_platt([{"probability":.6,"outcome":1}]*10)
