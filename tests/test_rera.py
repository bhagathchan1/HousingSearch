"""Parser tests for the state RERA importers.

The HTML snippets below are small hand-written samples that mirror each portal's
markup (structure only; names and numbers are made up), so the tests run offline.
"""

from __future__ import annotations

from datetime import date

from housingsearch import insights
from housingsearch.rera import haryana, karnataka, maharashtra, tamilnadu
from housingsearch.rera.common import dates_in, dms_to_decimal, latest_date, title_case

KA_LIST = """<table id="approvedTable"><thead><tr><th>S.No</th></tr></thead><tbody>
<tr><td>1</td><td>PR/KN/170729/000001</td><td> PRM/KA/RERA/1251/446/PR/171010/000001 </td>
<td><a id="6" onclick="return showFileApplicationPreview(this);"></a></td><td>SAMPLE BUILDERS PRIVATE LIMITED</td>
<td>SAMPLE GREENS <p style="color:orange;"></p></td><td> APPROVED </td><td>Bengaluru Urban</td><td>Bengaluru East</td>
<td>Residential/Group Housing</td><td>10/10/2017</td><td>28/02/2022</td><td> 31-05-2021 </td>
<td> 31-05-2021 - 28-02-2023 </td><td> </td><td> </td><td></td><td></td><td></td><td></td><td></td></tr>
<tr><td>2</td><td>PR/KN/170729/000002</td><td>PRM/KA/RERA/1251/446/PR/171010/000002</td><td><a id="7"></a></td>
<td>X</td><td>MALL</td><td>APPROVED</td><td>Bengaluru Urban</td><td>Anekal</td><td>Commercial</td><td>01/01/2020</td>
<td>01/01/2024</td><td>01-01-2024</td><td></td><td></td><td></td><td></td><td></td><td></td><td></td><td></td></tr>
<tr><td>3</td><td>PR/KN/1</td><td>PRM/KA/RERA/1251/446/PR/171010/000003</td><td><a id="8"></a></td>
<td>Y</td><td>GONE</td><td>REJECTED Your file is rejected.</td><td>Bengaluru Urban</td><td>Anekal</td>
<td>Residential/Group Housing</td><td>01/01/2020</td><td>01/01/2024</td><td>01-01-2024</td><td></td><td></td><td></td>
<td></td><td></td><td></td><td></td><td></td></tr>
</tbody></table>"""

KA_DETAILS = """<div>Project Address : Sy.No. 1, Sample Village, Whitefield, Bangalore District : Bengaluru Urban
Pin Code : 560066 Latitude : 12°59'45.61"N North Longitude : 77°42'17.22"E East
Type of Inventory : 2 BHK No of Inventory : 100 Carpet Area (Sq Mtr) : 6500SqMtr
Type of Inventory : 2 BHK No of Inventory : 100 Carpet Area (Sq Mtr) : 6500SqMtr
Type of Inventory : 3 BHK No of Inventory : 40 Carpet Area (Sq Mtr) : 4000SqMtr</div>"""

HR_LIST = """<table><tr><th>Serial No.</th></tr>
<tr><td>1</td><td>GGM/100/1/2020/1 DATED 09.10.2020</td><td><a href="https://haryanarera.gov.in/view_project/searchprojectDetail/1">RERA-GRG-1-2020</a></td>
<td>SAMPLE HEIGHTS</td><td>SAMPLE PROMOTERS PRIVATE LIMITED</td><td>SECTOR 102 & 102 A GURUGRAM</td><td>GURUGRAM</td><td>HRERA</td>
<td></td><td>30/04/2027</td><td>View</td><td>View</td><td>View Monitoring Cases</td><td>View OC/CC/PCC</td></tr>
<tr><td>2</td><td>GGM/100/2/2019/2 DATED 01.01.2019 Lapsed Project</td><td>RERA-GRG-2-2019</td>
<td>SAMPLE COMMERCIAL COMPLEX</td><td>B</td><td>SECTOR 65</td><td>GURUGRAM</td><td>HRERA</td><td></td><td>01/01/2022</td><td></td><td></td></tr>
<tr><td>3</td><td>GGM/100/3/2019/3 DATED 01.01.2019 Lapsed Project</td><td>RERA-GRG-3-2019</td>
<td>SAMPLE RESIDENCY</td><td>C</td><td>SECTOR 65, GURUGRAM</td><td>GURUGRAM</td><td>HRERA</td><td></td><td>01/01/2022</td><td>QPR not Uploaded</td><td></td></tr>
</table>"""

TN_LIST = """<table><tr><th>S. No</th></tr>
<tr><td>1</td><td>TNRERA/29/BLG/0001/2026 dated 02-01-2026</td>
<td>M/s. SAMPLE HOMES rep by its Partner, No.1, Main Road, Chennai-600001.</td>
<td>Project Name: SAMPLE NEST Registration for Stilt + 4 Floors with 12 Dwelling Units at S.No. 1 of Velachery Village, Chennai District.</td>
<td>Planning Permission No. 1/2025 issued by CMDA.</td><td>08.05.2028</td>
<td>Location of Site: Latitude-12.97; Longitude-80.22;</td><td></td><td>Progress of Work as on September 2026</td></tr>
<tr><td>2</td><td>TNRERA/16/BLG/0003/2026 dated 02-01-2026</td><td>M/s. OTHER, Tiruchirappalli</td>
<td>Project Name: FAR AWAY at Abhishekapuram Village, Tiruchirappalli District.</td><td></td><td>01.01.2030</td><td></td><td></td><td></td></tr>
</table>"""

MH_PAGE = """<div class="row shadow p-3 mb-5 bg-body rounded"> <div class="col-xl-4"> <p class="p-0"># P51800000001</p>
<h4 class="title4"><strong>SAMPLE TOWERS</strong></h4> <p class="darkBlue bold ">SAMPLE REALTY LLP</p>
<ul class="listingList"><li><a href="https://www.google.com/maps/search/?api=1&amp;query=19.07,72.90"><em class="fa-solid fa-location-dot"></em> Kurla </a></li></ul></div>
<div class="greyColor">Pincode</div> <p>400070</p> <div class="greyColor">District</div> <p>Mumbai Suburban</p>
<div class="greyColor">Last Modified</div> <p>2026-10-01</p> <div class="greyColor">Extension Certificate</div><a href="#" class="btnBdr">N/A</a>
<a href="https://maharerait.maharashtra.gov.in/public/project/view/99" class="viewLink">View Details</a></div>"""


def test_common_helpers():
    assert dates_in("31-05-2021 - 28.02.2022 and 2023-01-05") == ["2021-05-31", "2022-02-28", "2023-01-05"]
    assert latest_date("31-05-2021", "01/02/2024", "") == "2024-02-01"
    assert abs(dms_to_decimal("""12°59'45.61"N""") - 12.996003) < 1e-5
    assert title_case("K.L.BUILDERS PRIVATE LIMITED") == "K.L.Builders Private Limited"
    assert title_case("Godrej Air") == "Godrej Air"


def test_karnataka():
    rows = karnataka.parse_list(KA_LIST)
    assert len(rows) == 3
    recs = [r for r in (karnataka.to_record(x, completed=set()) for x in rows) if r]
    assert len(recs) == 1  # commercial and rejected rows are dropped
    rec = recs[0]
    assert rec["name"] == "Sample Greens" and rec["city"] == "Bengaluru" and rec["locality"] == "Bengaluru East"
    assert rec["launch_date"] == "2017-10-10"
    assert rec["rera_possession_date"] == "2023-02-28"  # latest of completion date and extensions
    assert rec["status"] == "Under Construction"
    done = karnataka.to_record(rows[0], completed={rows[0]["reg"]})
    assert done["status"] == "Ready to Move"
    det = karnataka.parse_details(KA_DETAILS)
    assert det["pincode"] == "560066" and abs(det["lat"] - 12.996) < 0.001
    assert [c["label"] for c in det["configurations"]] == ["2 BHK", "3 BHK"]  # duplicates removed
    assert det["configurations"][0]["carpet_sqft"] == 700  # 6500 sq m / 100 units in sq ft
    assert det["total_units"] == 140


def test_haryana():
    recs = [r for r in (haryana.to_record(x) for x in haryana.parse_list(HR_LIST)) if r]
    assert [r["name"] for r in recs] == ["Sample Heights", "Sample Residency"]  # commercial dropped
    a, b = recs
    assert a["locality"] == "Sector 102" and a["rera_status"] == "Registered" and a["status"] == "Ready to Move"
    assert a["rera_url"].endswith("/searchprojectDetail/1") and a["rera_possession_date"] == "2027-04-30"
    assert b["rera_status"] == "Lapsed" and "progress report" in b["description"]


def test_tamilnadu():
    recs = [r for r in (tamilnadu.to_record(x) for x in tamilnadu.parse_list(TN_LIST)) if r]
    assert len(recs) == 1  # only the Chennai-area project
    r = recs[0]
    assert r["name"] == "Sample Nest" and r["builder"] == "Sample Homes" and r["locality"] == "Velachery"
    assert r["rera_possession_date"] == "2028-05-08" and r["lat"] == 12.97 and r["total_units"] == 12
    assert any(a["code"] == "PLAN" and a["status"] == "Obtained" for a in r["approvals"])


def test_maharashtra():
    rows = maharashtra.parse_page(MH_PAGE)
    assert len(rows) == 1
    r = maharashtra.to_record(rows[0], "Mumbai")
    assert r["rera_number"] == "P51800000001" and r["name"] == "Sample Towers" and r["builder"] == "Sample Realty LLP"
    assert r["locality"] == "Kurla" and r["pincode"] == "400070" and (r["lat"], r["lng"]) == (19.07, 72.90)
    assert r["rera_url"].endswith("/view/99")


def test_unknown_approvals_are_not_red_flags():
    rec = karnataka.to_record(karnataka.parse_list(KA_LIST)[0], completed=set())
    prop = {**rec, "rera_possession_date": "2030-01-01"}
    ap = insights.approvals_summary(prop, rec["approvals"])
    assert ap["missing_count"] == 0 and ap["unverified_count"] > 0
    dl = insights.delivery_summary(prop, today=date(2026, 1, 1))
    flags = insights.red_flags(prop, None, {}, dl, ap, {"count": 0}, [])
    assert not [f for f in flags if f["level"] == "critical"]
    ts = insights.trust_score(prop, None, dl, ap, {"count": 0}, [])
    assert ts["limited"] and ts["grade"] == "?"


def test_seed_selection(tmp_path, monkeypatch):
    from housingsearch import api, config

    demo = tmp_path / "demo_properties.json"
    demo.write_text("{}")
    monkeypatch.setattr(config, "SEED_DIR", tmp_path)
    monkeypatch.setattr(config, "SEED_FILE", demo)
    assert api.seed_files("auto") == [demo]  # no real data -> demo
    real = tmp_path / "rera_ka.json"
    real.write_text("{}")
    assert api.seed_files("auto") == [real]  # real data replaces demo
    assert api.seed_files("1") == [real, demo]
    assert api.seed_files("0") == [real]


TG_SAVED = """<html><body><table id="results"><thead><tr><th>S.No</th><th>Project Name</th><th>Promoter Name</th>
<th>Certificate No</th><th>District</th><th>Mandal</th><th>Village</th><th>Proposed Completion Date</th><th>Status</th></tr></thead>
<tbody><tr><td>1</td><td>SAMPLE SKY TOWERS</td><td>SAMPLE INFRA PVT LTD</td><td>P02400001234</td><td>Ranga Reddy</td>
<td>Serilingampally</td><td>Kokapet</td><td>31/12/2028</td><td>Approved</td></tr>
<tr><td>2</td><td>FAR FIELDS</td><td>OTHER</td><td>P01100000999</td><td>Warangal Urban</td><td>X</td><td>Y</td><td>01/01/2027</td><td>Approved</td></tr>
</tbody></table></body></html>"""


def test_telangana_saved_page(tmp_path):
    from housingsearch.rera import telangana

    f = tmp_path / "hyd.html"
    f.write_text(TG_SAVED)
    recs = telangana.from_files([f], log=lambda *_: None)
    assert len(recs) == 1  # Warangal is outside the Hyderabad region
    r = recs[0]
    assert (r["name"], r["builder"], r["city"], r["locality"]) == ("Sample Sky Towers", "Sample Infra Pvt Ltd", "Hyderabad", "Kokapet")
    assert r["rera_number"] == "P02400001234" and r["rera_possession_date"] == "2028-12-31"
    bad = tmp_path / "other.html"
    bad.write_text("<html><p>no table</p></html>")
    import pytest
    with pytest.raises(telangana.UnrecognisedPage):
        telangana.from_files([bad], log=lambda *_: None)


def test_implausible_coordinates_dropped():
    from housingsearch.rera.common import plausible_coords

    assert plausible_coords("Mumbai", 19.1, 72.9) == (19.1, 72.9)
    assert plausible_coords("Mumbai", 19.99, 73.79) == (None, None)  # Nashik, mistyped on the register
