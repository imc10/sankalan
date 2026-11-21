"""Part names (Tech spec A2 8.3; AC-EXP-8a, AC-EXP-10)."""
from conftest import spec
from sankalan.exporting import PART_ROWS, part_count, plan, stem


@spec("AC-EXP-8a", "EXP-8", "T37")
def test_one_file_up_to_part_rows():
    assert PART_ROWS == 1_000_000
    assert plan(1_000_000, "Acme_Sales_R-0003_Data.csv") == ["Acme_Sales_R-0003_Data.csv"]
    assert plan(0, "x.csv") == ["x.csv"] and part_count(0) == 1
    assert plan(1_000_001, "Acme_Sales_R-0003_Data.csv") == ["Acme_Sales_R-0003_Data_part01of02.csv",
                                                             "Acme_Sales_R-0003_Data_part02of02.csv"]


@spec("AC-EXP-10", "EXP-9", "EXP-10")
def test_names_and_padding():
    assert plan(2_341_118, "Acme_Sales_R-0003.csv") == [f"Acme_Sales_R-0003_part0{k}of03.csv" for k in (1, 2, 3)]
    names = plan(119_000_001, "Big.csv")
    assert len(names) == 120 and names[0] == "Big_part001of120.csv" and names[-1] == "Big_part120of120.csv"
    assert plan(9_000_001, "Ten.csv")[-1] == "Ten_part10of10.csv"
    assert plan(3000, "Data.csv", part_rows=1000) == ["Data_part01of03.csv", "Data_part02of03.csv",
                                                     "Data_part03of03.csv"]


@spec("EXP-10")
def test_stem_drops_a_final_csv_of_any_case():
    assert stem("Report.CSV") == "Report" and stem("Report.Csv") == "Report" and stem("Report") == "Report"
    assert stem("a.csv.csv") == "a.csv" and stem("Report.txt") == "Report.txt"
    assert plan(2001, "Report.CSV", part_rows=1000)[0] == "Report_part01of03.csv"


@spec("EXP-8", "DO-7")
def test_all_outputs_plan_each_output_on_its_own():
    outs = {"State-wise sales.csv": 20, "By invoice.csv": 2500}
    plans = {n: plan(rows, n, part_rows=1000) for n, rows in outs.items()}
    assert plans["State-wise sales.csv"] == ["State-wise sales.csv"]
    assert plans["By invoice.csv"] == ["By invoice_part01of03.csv", "By invoice_part02of03.csv",
                                       "By invoice_part03of03.csv"]
