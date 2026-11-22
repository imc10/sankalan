"""Feature F at full size (``slow``): TPL-N full, 2 × 500,000 rows, loaded without checks through the real pipeline
with reader workers (AC-NCK-2, AC-NCK-4 at the Feature Spec A2 10.1 figures: 6,802 / 120 text values, 2,000 repeated
rows, 10 blank rows). The oracle is the generator's manifest."""
import pytest

import tpl_n
from conftest import commit_unchecked, load_tpl_n, open_storage, run_job, spec
from sankalan.query import catalogue as q
from sankalan.query.split import LEFT_OUT

pytestmark = pytest.mark.slow


@spec("AC-NCK-2", "AC-NCK-4", "NCK-4", "NCK-8", "T45")
def test_tpl_n_full_load_values_and_commit(tmp_path, tpl_n_full):
    fx, m = tpl_n_full
    assert (m.taxable_text_count, m.date_text_count, m.repeated, m.blank_rows) == (6_802, 120, 2_000, 10)
    s = open_storage(tmp_path)
    try:
        tid = q.create_template(s.con, tpl_n.template(q.insert_client(s.con, "Acme Traders")))
        sess = load_tpl_n(s, tid, fx, list(tpl_n.FILES), workers=2)
        ls = sess.loaded
        assert (ls.rows_read, ls.blank_rows, ls.rows_to_load) == (1_000_010, 10, 1_000_000)
        assert ls.text_counts == {"c002": 120, "c006": 6_802}
        data = f"read_parquet('{(sess.staging.path / 'data.parquet').as_posix()}')"
        cols = ", ".join(c.id for c in sess.columns)
        total, distinct = s.con.execute(f"SELECT count(*), count(DISTINCT ({cols})) FROM {data}").fetchone()
        assert total - distinct == 2_000                                     # repeated rows kept
        for cid, want in (("c006", m.taxable_text), ("c002", m.date_text)):
            got = run_job(s.runner, lambda ctx: sess.text_values(ctx, cid))
            assert [(v.text, v.count, v.file_name, v.sheet, v.row) for v in got] == \
                [(w["text"], w["count"], tpl_n.FILES[w["file_index"]], "", w["row"]) for w in want]
        c = commit_unchecked(s, sess)
        run = q.run_details(s.con, c.run_id)
        assert (run["rows_read"], run["rows_loaded"], run["rows_left_out"], run["checks"]) == (1_000_010, 1_000_000,
                                                                                               0, False)
        assert not (s.folder.run_dir(tid, c.run_id) / LEFT_OUT).exists()
    finally:
        s.close()
