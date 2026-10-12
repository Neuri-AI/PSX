"""Reviewed, component-specific G2 operation evidence. No backend-wide inheritance.

Each declaration cites a real native/headless test method and a single
component and operation. C2 validates its existence and source reference.
Future C3 work must add per-component update/reorder/disposal coverage rather
than promoting backend-general tests to fabricated component certification.
"""
from __future__ import annotations

from types import MappingProxyType

SUITES = MappingProxyType({
    "qt": "test_f3_g2_qt_family.py",
    "tk": "test_tkinter_f3_g2_renderer.py",
    "kivy": "test_kivy_f3_g2_renderer.py",
    "headless": "test_f3_g2_headless.py",
})

# Reviewed references. "create" represents mounting with an SFLE geometry
# assertion in the listed test; never indicates all other operations pass.
COMPONENT_OPERATION_TESTS = MappingProxyType({
    ("qt", "Text", "create"): "test_binding_and_native_geometry_owner",
    ("qt", "Button", "create"): "test_markup_nested_padding_and_local_coordinates",
    ("qt", "Checkbox", "create"): "test_native_controls_have_identical_sfle_rectangles",
    ("qt", "Input", "create"): "test_native_controls_have_identical_sfle_rectangles",
    ("qt", "TextArea", "create"): "test_textarea_auto_height_wraps_at_post_flex_width_without_remount",
    ("qt", "TextArea", "update"): "test_textarea_native_edit_remeasures_without_reconciler_remount",
    ("qt", "Slider", "create"): "test_native_controls_have_identical_sfle_rectangles",
    ("qt", "Radio", "create"): "test_additional_certified_controls_preserve_native_types_and_geometry",
    ("qt", "ProgressBar", "create"): "test_additional_certified_controls_preserve_native_types_and_geometry",
    ("qt", "Select", "create"): "test_interactive_switch_spinbox_select_preserve_geometry_state_events",
    ("qt", "Image", "create"): "test_image_intrinsic_and_sfle_paint_survive_reconcile_resize",
    ("qt", "Link", "create"): "test_portable_link_badge_divider_spacer_use_only_sfle_rectangles",
    ("qt", "Badge", "create"): "test_portable_link_badge_divider_spacer_use_only_sfle_rectangles",
    ("qt", "Divider", "create"): "test_structural_box_radiogroup_and_divider_children_are_sfle_owned",
    ("qt", "Spacer", "create"): "test_portable_link_badge_divider_spacer_use_only_sfle_rectangles",
    ("qt", "Switch", "create"): "test_interactive_switch_spinbox_select_preserve_geometry_state_events",
    ("qt", "SpinBox", "create"): "test_interactive_switch_spinbox_select_preserve_geometry_state_events",
    ("qt", "RadioGroup", "create"): "test_structural_box_radiogroup_and_divider_children_are_sfle_owned",
    ("qt", "Box", "create"): "test_structural_box_radiogroup_and_divider_children_are_sfle_owned",
    ("qt", "Scroll", "create"): "test_scroll_basic_sfle_viewport_hosts_explicit_content_flex",
    ("qt", "Flex", "create"): "test_binding_and_native_geometry_owner",
    ("tk", "Text", "create"): "test_real_ttk_widgets_use_sfle_place_not_pack_or_grid",
    ("tk", "Button", "create"): "test_real_ttk_widgets_use_sfle_place_not_pack_or_grid",
    ("tk", "Checkbox", "create"): "test_tk_checkbox_event_and_state_reconciliation_in_sfle_tree",
    ("tk", "Input", "create"): "test_input_native_geometry_comes_from_sfle_and_reuses_entry",
    ("tk", "Input", "update"): "test_input_placeholder_overlay_is_not_user_value_and_hides_on_update",
    ("tk", "TextArea", "create"): "test_textarea_wraps_at_real_sfle_width_and_preserves_edit_state",
    ("tk", "Slider", "create"): "test_additional_tk_native_primitives_have_sfle_geometry_no_pack",
    ("tk", "Radio", "create"): "test_additional_tk_native_primitives_have_sfle_geometry_no_pack",
    ("tk", "ProgressBar", "create"): "test_progressbar_native_sfle_geometry_without_pack",
    ("tk", "Select", "create"): "test_switch_spinbox_select_sfle_geometry_and_state_preservation",
    ("tk", "Image", "create"): "test_image_intrinsic_source_resize_and_keyed_native_reuse",
    ("tk", "Link", "create"): "test_portable_link_badge_divider_spacer_are_sfle_owned",
    ("tk", "Badge", "create"): "test_portable_link_badge_divider_spacer_are_sfle_owned",
    ("tk", "Divider", "create"): "test_structural_box_radiogroup_and_labeled_divider_native_rectangles",
    ("tk", "Spacer", "create"): "test_portable_link_badge_divider_spacer_are_sfle_owned",
    ("tk", "Switch", "create"): "test_switch_spinbox_select_sfle_geometry_and_state_preservation",
    ("tk", "SpinBox", "create"): "test_switch_spinbox_select_sfle_geometry_and_state_preservation",
    ("tk", "RadioGroup", "create"): "test_structural_box_radiogroup_and_labeled_divider_native_rectangles",
    ("tk", "Box", "create"): "test_structural_box_radiogroup_and_labeled_divider_native_rectangles",
    ("tk", "Scroll", "create"): "test_scroll_basic_sfle_viewport_and_explicit_flex_content",
    ("tk", "Flex", "create"): "test_real_ttk_widgets_use_sfle_place_not_pack_or_grid",
    ("kivy", "Text", "create"): "test_real_kivy_native_bottom_left_geometry_and_reconciliation",
    ("kivy", "Button", "create"): "test_real_kivy_native_bottom_left_geometry_and_reconciliation",
    ("kivy", "Checkbox", "create"): "test_explicit_bounds_checkbox_and_progressbar_sfle_geometry",
    ("kivy", "Input", "create"): "test_kivy_input_explicit_pixel_bounds_preserve_native_widget",
    ("kivy", "Input", "update"): "test_kivy_intrinsic_controls_without_pixel_bounds",
    ("kivy", "TextArea", "create"): "test_textarea_native_width_reflow_and_editing",
    ("kivy", "Slider", "create"): "test_real_kivy_native_bottom_left_geometry_and_reconciliation",
    ("kivy", "Radio", "create"): "test_structural_box_radio_group_and_labeled_divider_use_sfle",
    ("kivy", "ProgressBar", "create"): "test_explicit_bounds_checkbox_and_progressbar_sfle_geometry",
    ("kivy", "Select", "create"): "test_switch_spinbox_select_native_interaction_and_sfle_geometry",
    ("kivy", "Image", "create"): "test_image_intrinsic_source_and_native_sfle_geometry",
    ("kivy", "Link", "create"): "test_link_badge_divider_and_spacer_native_geometry",
    ("kivy", "Badge", "create"): "test_link_badge_divider_and_spacer_native_geometry",
    ("kivy", "Divider", "create"): "test_structural_box_radio_group_and_labeled_divider_use_sfle",
    ("kivy", "Spacer", "create"): "test_link_badge_divider_and_spacer_native_geometry",
    ("kivy", "Switch", "create"): "test_switch_spinbox_select_native_interaction_and_sfle_geometry",
    ("kivy", "SpinBox", "create"): "test_switch_spinbox_select_native_interaction_and_sfle_geometry",
    ("kivy", "RadioGroup", "create"): "test_structural_box_radio_group_and_labeled_divider_use_sfle",
    ("kivy", "Box", "create"): "test_structural_box_radio_group_and_labeled_divider_use_sfle",
    ("kivy", "Scroll", "create"): "test_scroll_basic_sfle_viewport_and_explicit_content_root",
    ("kivy", "Flex", "create"): "test_real_kivy_native_bottom_left_geometry_and_reconciliation",
    ("headless", "Button", "create"): "test_button_lifecycle_operations_use_real_headless_observations",
    ("headless", "Button", "update"): "test_button_lifecycle_operations_use_real_headless_observations",
    ("headless", "Button", "reorder"): "test_button_lifecycle_operations_use_real_headless_observations",
    ("headless", "Button", "event_rebind"): "test_button_lifecycle_operations_use_real_headless_observations",
    ("headless", "Button", "unmount"): "test_button_lifecycle_operations_use_real_headless_observations",
    ("headless", "Flex", "create"): "test_opt_in_headless_flex_is_real_sfle_geometry_not_a_dummy_layout",
    ("headless", "Text", "create"): "test_text_intrinsic_dimensions_must_be_host_supplied",
})
