"""Rule meanings (T16, T17; Tech spec rule table) on hand-written staged rows: blank handling, inclusive ranges,
case and spaces, pattern, multi-key Unique across files, columns missing from older files."""
import pytest

from conftest import run_job, spec
from sankalan.model.rule import (ALLOWED_VALUES, DATE_RANGE, ERROR, IS_DATE, IS_NUMBER, NOT_BLANK, NUMBER_RANGE,
                                 PATTERN, TEXT_LENGTH, UNIQUE, WARNING, Rule, next_rule_id, with_type_rules)
from sankalan.model.template import Column
from sankalan.query import validate as qv
from sankalan.validation import issues as iss
from sankalan.validation import scan
from sankalan.validation.rules import RuleError, check_rule, pattern_regex, rules_for_type

COLS = [Column("c001", "Code"), Column("c002", "Amount", "Number", decimals=2),
        Column("c003", "Rate", "Number", decimals=0), Column("c004", "Doc Date", "Date"),
        Column("c005", "Party")]

# (_src_file, sheet, row, c001, c002, c003, c004, c005)
ROWS = [
    (0, "S", 2, "abc-12", "10.00", "18", "2026-04-01", "P1"),
    (0, "S", 3, "ABC-1", "20.00", "5", "2027-03-31", "P1"),
    (0, "S", 4, "ABC_12", "9.99", "15", "2026-03-31", "P2"),
    (0, "S", 5, None, "20.01", None, "2027-04-01", None),
    (0, "S", 6, "B2B", None, "28", None, "P3"),
    (0, "S", 7, " B2B", "-0.01", "0", "2026-10-01", "P3"),
    (1, "T", 2, "ÄBC-12", "0.00", "18", "2026-10-01", "P1"),
    (1, "T", 3, "ab ", "15.00", "12", "2026-10-01", None),
]
FAILURES = [(0, "S", 6, "c002", "12abc")]          # row 6 Amount typed "12abc": null, its text in c002_t


def _q(v):
    return "NULL" if v is None else "'" + v.replace("'", "''") + "'"


@pytest.fixture
def staged(storage):
    st = storage.folder.new_staging()
    vals = ", ".join(f"({f}, {_q(s)}, {r}, {_q(a)}, {_q(b)}, {_q(c)}, {_q(d)}, {_q(e)})"
                     for f, s, r, a, b, c, d, e in ROWS)
    text = {(f, r, c): v for f, _s, r, c, v in FAILURES}

    def t(f, r, c):
        return _q(text.get((f, r, c)))
    tv = ", ".join(f"({f}, {r}, {t(f, r, 'c002')}, {t(f, r, 'c003')}, {t(f, r, 'c004')})"
                   for f, _s, r, *_x in ROWS)
    storage.con.execute(f"""COPY (SELECT 'x' AS run_id, CAST(f AS INTEGER) AS _src_file, s AS _src_sheet,
        CAST(r AS BIGINT) AS _src_row, a AS c001, CAST(b AS DECIMAL(38,2)) AS c002, CAST(t2 AS VARCHAR) AS c002_t,
        CAST(c AS DECIMAL(38,0)) AS c003, CAST(t3 AS VARCHAR) AS c003_t, CAST(d AS DATE) AS c004,
        CAST(t4 AS VARCHAR) AS c004_t, e AS c005
        FROM (VALUES {vals}) t(f, s, r, a, b, c, d, e) JOIN (VALUES {tv}) x(f, r, t2, t3, t4) USING (f, r))
        TO '{(st.path / 'data.parquet').as_posix()}' (FORMAT parquet)""")
    return storage, st


def _fails(staged, *rules, columns=COLS):
    storage, st = staged
    r = run_job(storage.runner, lambda ctx: scan.validate(ctx, st, columns, list(rules),
                                                          {0: "A.xlsx", 1: "B.xlsx"}))
    rows = qv.read_issues(storage.con, r.issues)
    return {rid: [(x[0], x[2]) for x in rows if x[4] == rid] for rid in [*(x.id for x in r.rules)]}, rows


@spec("VAL-1", "VAL-2", "T14")
def test_not_blank_and_is_a_number(staged):
    got, rows = _fails(staged, Rule("r1", "c002", NOT_BLANK), Rule("r2", "c005", NOT_BLANK))
    assert got["r1"] == []                          # row 6 is text: not blank, only Is a number (TXT-13)
    assert got["c002.type"] == [(0, 6)]
    assert got["r2"] == [(0, 5), (1, 3)]
    assert got["c004.type"] == [] and got["c003.type"] == []


@spec("VAL-3", "T13")
def test_number_range_inclusive_and_not_negative(staged):
    got, rows = _fails(staged, Rule("r1", "c002", NUMBER_RANGE, {"min": "10", "max": "20"}),
                       Rule("r2", "c002", NUMBER_RANGE, {"not_negative": True}),
                       Rule("r3", "c002", NUMBER_RANGE, {"min": "10.005"}))
    assert got["r1"] == [(0, 4), (0, 5), (0, 7), (1, 2)]       # 9.99, 20.01, -0.01, 0.00; 10 and 20 pass
    assert got["r2"] == [(0, 7)]
    assert got["r3"] == [(0, 2), (0, 4), (0, 7), (1, 2)]        # 10.00 < 10.005: settings are never rounded
    p = {(x[2], x[4]): x[8] for x in rows}
    assert p[(4, "r1")] == "value is not between 10 and 20" and p[(7, "r2")] == "value is negative"
    assert p[(2, "r3")] == "value is less than 10.005"


@spec("VAL-5")
def test_date_range_inclusive(staged):
    got, rows = _fails(staged, Rule("r1", "c004", DATE_RANGE, {"from": "2026-04-01", "to": "2027-03-31"}))
    assert got["r1"] == [(0, 4), (0, 5)]
    assert {x[2]: x[7] for x in rows if x[4] == "r1"} == {4: "31-03-2026", 5: "01-04-2027"}
    assert rows[0][8] == "date is not between 01-04-2026 and 31-03-2027"


@spec("VAL-6", "T16")
def test_allowed_values_text_ignores_case_counts_spaces_and_numbers_by_value(staged):
    got, _ = _fails(staged, Rule("r1", "c001", ALLOWED_VALUES, {"values": ["b2b", "AB "]}),
                    Rule("r2", "c003", ALLOWED_VALUES, {"values": ["0", "5.00", "12", "18", "28"]}))
    assert got["r1"] == [(0, 2), (0, 3), (0, 4), (0, 7), (1, 2)]   # "B2B" and "ab " pass; " B2B" fails
    assert got["r2"] == [(0, 4)]                                   # 15; 5 = 5.00; null skipped


@spec("VAL-7")
def test_text_length_counts_spaces(staged):
    got, rows = _fails(staged, Rule("r1", "c001", TEXT_LENGTH, {"exact": 3}),
                       Rule("r2", "c001", TEXT_LENGTH, {"min": 5, "max": 6}))
    assert got["r1"] == [(0, 2), (0, 3), (0, 4), (0, 7), (1, 2)]   # "B2B", "ab " are 3; " B2B" is 4
    assert got["r2"] == [(0, 6), (0, 7), (1, 3)]
    assert {x[2]: x[8] for x in rows if x[4] == "r2"}[6] == "value has 3 characters; expected 5 to 6"


@spec("VAL-8", "T16")
def test_character_pattern(staged):
    got, rows = _fails(staged, Rule("r1", "c001", PATTERN, {"pattern": "AAA-99"}))
    assert got["r1"] == [(0, 3), (0, 4), (0, 6), (0, 7), (1, 2), (1, 3)]   # "abc-12" passes: A is either case
    assert rows[0][8] == "value doesn't match the pattern AAA-99"
    assert pattern_regex("AA.9 (x)") == r"[A-Za-z][A-Za-z]\.[0-9] \(x\)"


@spec("VAL-9", "T17")
def test_unique_multi_key_skips_blank_keys_and_names_first_occurrence_in_another_file(staged):
    got, rows = _fails(staged, Rule("r1", "c005", UNIQUE, {"columns": ["c003"]}),
                       Rule("r2", "c005", UNIQUE))
    assert got["r1"] == [(0, 2), (1, 2)]               # P1 + 18 twice; null Rate/Party rows skipped
    assert got["r2"] == [(0, 2), (0, 3), (0, 6), (0, 7), (1, 2)]   # P1 three times, P3 twice
    by = {(x[0], x[2], x[4]): x for x in rows}
    assert by[(1, 2, "r1")][8] == "same Party + Rate as A.xlsx, S, row 2" and by[(1, 2, "r1")][7] == "P1 + 18"
    assert by[(0, 2, "r1")][8] == "same Party + Rate in 2 rows; this is the first"
    assert by[(0, 3, "r2")][8] == "same Party as row 2" and by[(1, 2, "r2")][9] is False


@spec("MAP-11", "VR-8")
def test_column_missing_from_an_older_file_reads_as_blank(staged):
    cols = COLS + [Column("c006", "Branch")]
    got, _ = _fails(staged, Rule("r1", "c006", NOT_BLANK, severity=WARNING), columns=cols)
    assert len(got["r1"]) == len(ROWS)


@spec("VR-7")
def test_type_rules_added_kept_as_warning_and_not_removable():
    rules = with_type_rules(COLS, [Rule("c002.type", "c002", IS_NUMBER, severity=WARNING),
                                   Rule("r1", "c001", NOT_BLANK)])
    assert [(r.id, r.type, r.severity) for r in rules] == [
        ("c002.type", IS_NUMBER, WARNING), ("c003.type", IS_NUMBER, ERROR), ("c004.type", IS_DATE, ERROR),
        ("r1", NOT_BLANK, ERROR)]
    assert with_type_rules(COLS, [])[0].id == "c002.type"          # can't be removed: it comes back
    removed = [Column("c001", "Code", removed=True)] + COLS[1:]
    assert all(r.column_id != "c001" for r in with_type_rules(removed, rules))
    assert next_rule_id(rules) == "r2"


def test_rule_settings_are_checked():
    ok = [Rule("r1", "c002", NUMBER_RANGE, {"min": "0", "max": "5"}), Rule("r2", "c001", PATTERN, {"pattern": "A9"}),
          Rule("r3", "c003", ALLOWED_VALUES, {"values": ["5", "12.5"]}), Rule("r4", "c001", TEXT_LENGTH, {"exact": 15}),
          Rule("r5", "c004", DATE_RANGE, {"from": "2026-04-01"}), Rule("r6", "c001", UNIQUE, {"columns": ["c004"]})]
    for r in ok:
        check_rule(r, COLS)
    bad = [Rule("r1", "c001", NUMBER_RANGE, {"min": "0"}),                      # wrong column type
           Rule("r2", "c002", NUMBER_RANGE, {"min": "5", "max": "1"}),
           Rule("r3", "c002", NUMBER_RANGE, {}),
           Rule("r4", "c003", ALLOWED_VALUES, {"values": ["abc"]}),
           Rule("r5", "c001", ALLOWED_VALUES, {"values": []}),
           Rule("r6", "c001", TEXT_LENGTH, {"exact": -1}),
           Rule("r7", "c004", DATE_RANGE, {"from": "2027-01-01", "to": "2026-01-01"}),
           Rule("r8", "c001", PATTERN, {"pattern": ""}),
           Rule("r9", "c001", UNIQUE, {"columns": ["c099"]}),
           Rule("r10", "c099", NOT_BLANK),
           Rule("r11", "c002", NUMBER_RANGE, {"min": "0.1234567"})]
    for r in bad:
        with pytest.raises(RuleError):
            check_rule(r, COLS)
    assert rules_for_type("Text") == [NOT_BLANK, ALLOWED_VALUES, TEXT_LENGTH, PATTERN, UNIQUE]
    assert rules_for_type("Number") == [NOT_BLANK, NUMBER_RANGE, ALLOWED_VALUES, UNIQUE]
    assert rules_for_type("Date") == [NOT_BLANK, DATE_RANGE, UNIQUE]


@spec("UI-6", "NF-5")
def test_message_wording():
    assert iss.message("Sales_Errors.xlsx", "Sales", 214, "Taxable Value", "value is not a number") == \
        "Sales_Errors.xlsx, Sales, row 214, Taxable Value: value is not a number"
    assert iss.message("Feed.csv", "", 1087, "Customer", "value is blank") == "Feed.csv, row 1,087, Customer: " \
                                                                               "value is blank"
