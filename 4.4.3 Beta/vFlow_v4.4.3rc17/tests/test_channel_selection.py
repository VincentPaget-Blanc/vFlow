import pandas as pd

from vflow.services.channel_selection import plan_channel_menu


def df(*cols):
    return pd.DataFrame({c: [1] for c in cols})


def test_channel_plan_initializes_first_two_sorted_common_columns_in_legacy_order():
    plan = plan_channel_menu({'a': df('Y', 'X', 'Z')}, None, None)
    assert plan.values == ('X', 'Y', 'Z')
    assert plan.operations == (
        ('x_var', 'X'), ('y_var', 'Y'),
        ('x_channel', 'X'), ('y_channel', 'Y'),
    )


def test_channel_plan_reports_hidden_columns_across_files():
    plan = plan_channel_menu({'a': df('X', 'Y', 'A'), 'b': df('X', 'Y', 'B')}, 'X', 'Y')
    assert plan.values == ('X', 'Y')
    assert plan.mismatch_message == (
        "⚠ 2 column(s) not shared across all files (hidden from axis menus): 'A', 'B'"
    )
    assert plan.operations == (('x_var', 'X'), ('y_var', 'Y'))


def test_channel_plan_with_no_common_active_channel_fails_closed_instead_of_analysing_subset():
    plan = plan_channel_menu({'a': df('B', 'A'), 'b': df('C')}, None, None)
    assert plan.values == ()
    assert plan.mismatch_message.startswith("⚠ No channels are shared across all active files")
    assert plan.operations == (
        ('x_var', ''), ('y_var', ''),
        ('x_channel', None), ('y_channel', None),
    )


def test_channel_plan_stale_axes_keep_y_distinct_from_resolved_x():
    plan = plan_channel_menu({'a': df('A', 'B', 'C')}, 'STALE_X', 'STALE_Y')
    assert plan.values == ('A', 'B', 'C')
    assert plan.operations == (
        ('x_channel', 'A'), ('x_var', 'A'),
        ('y_channel', 'B'), ('y_var', 'B'),
    )


def test_channel_plan_single_column_with_uninitialized_x_preserves_legacy_y_fallback():
    plan = plan_channel_menu({'a': df('Only')}, None, 'stale')
    assert plan.values == ('Only',)
    assert plan.operations == (('y_channel', 'Only'), ('y_var', 'Only'))


def test_multi_file_duplicate_fcs_stain_suffixes_are_not_auto_matched():
    a = df('CD3', 'CD3_1', 'SSC')
    b = df('CD3', 'CD3_1', 'SSC')
    a.attrs['fcs_ambiguous_channel_names'] = ('CD3', 'CD3_1')
    b.attrs['fcs_ambiguous_channel_names'] = ('CD3', 'CD3_1')

    plan = plan_channel_menu({'a': a, 'b': b}, 'CD3', 'CD3_1')

    assert plan.values == ('SSC',)
    assert 'Duplicate FCS stain/channel labels' in plan.mismatch_message
    assert ('x_channel', 'SSC') in plan.operations


def test_single_file_duplicate_fcs_stain_suffixes_remain_usable():
    a = df('CD3', 'CD3_1', 'SSC')
    a.attrs['fcs_ambiguous_channel_names'] = ('CD3', 'CD3_1')

    plan = plan_channel_menu({'a': a}, 'CD3', 'CD3_1')

    assert plan.values == ('CD3', 'CD3_1', 'SSC')
    assert ('x_var', 'CD3') in plan.operations
    assert ('y_var', 'CD3_1') in plan.operations


def test_concatenated_provenance_columns_are_never_axis_candidates():
    frame = pd.DataFrame({
        'Source_File': ['a.csv', 'b.csv'],
        'Source_Path': ['/a/a.csv', '/b/b.csv'],
        'X': [1.0, 2.0],
        'Y': [3.0, 4.0],
        'Label': ['a', 'b'],
    })
    plan = plan_channel_menu({'pool.csv': frame}, None, None)
    assert plan.values == ('X', 'Y')
    assert plan.operations == (
        ('x_var', 'X'), ('y_var', 'Y'),
        ('x_channel', 'X'), ('y_channel', 'Y'),
    )


def test_concatenated_channel_missing_for_one_source_is_hidden_not_partially_analysed():
    frame = pd.DataFrame({
        'Source_File': ['a.csv', 'a.csv', 'b.csv', 'b.csv'],
        'Source_Path': ['/a/a.csv', '/a/a.csv', '/b/b.csv', '/b/b.csv'],
        'X': [1.0, 2.0, float('nan'), float('nan')],
        'Y': [3.0, 4.0, 5.0, 6.0],
        'Z': [7.0, 8.0, 9.0, 10.0],
    })
    plan = plan_channel_menu({'pool.csv': frame}, 'X', 'Y')
    assert plan.values == ('Y', 'Z')
    assert 'partial-source analysis' in plan.mismatch_message
    assert "'X'" in plan.mismatch_message
    assert ('x_channel', 'Y') in plan.operations
    assert ('y_channel', 'Z') in plan.operations


def test_object_metadata_column_is_not_an_axis_candidate():
    frame = pd.DataFrame({'Sample': ['A', 'B'], 'X': [1, 2], 'Y': [3, 4]})
    plan = plan_channel_menu({'a.csv': frame}, None, None)
    assert plan.values == ('X', 'Y')


def test_unnamed_csv_measurement_is_usable_single_file_but_not_auto_matched_across_files():
    a = pd.DataFrame({'Unnamed: 0': [10.5], 'X': [1.0], 'Y': [2.0]})
    b = pd.DataFrame({'Unnamed: 0': [99.5], 'X': [3.0], 'Y': [4.0]})
    a.attrs['csv_ambiguous_channel_names'] = ('Unnamed: 0',)
    b.attrs['csv_ambiguous_channel_names'] = ('Unnamed: 0',)

    single = plan_channel_menu({'a': a}, 'Unnamed: 0', 'X')
    assert 'Unnamed: 0' in single.values

    multi = plan_channel_menu({'a': a, 'b': b}, 'Unnamed: 0', 'X')
    assert 'Unnamed: 0' not in multi.values
    assert 'Unnamed CSV measurement columns' in multi.mismatch_message
    assert set(multi.values) == {'X', 'Y'}
