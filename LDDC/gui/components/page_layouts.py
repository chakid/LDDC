# SPDX-FileCopyrightText: Copyright (C) 2024-2025 沉默の金 <cmzj@cmzj.org>
# SPDX-License-Identifier: GPL-3.0-only
"""Reflow the dense generated toolbars without changing their signals or behavior."""

from typing import TYPE_CHECKING

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QComboBox, QHBoxLayout, QLabel, QLayout, QListView, QSizePolicy, QTextBrowser, QVBoxLayout, QWidget

if TYPE_CHECKING:
    from LDDC.gui.view.batch_convert import BatchConvertWidget
    from LDDC.gui.view.local_match import LocalMatchWidget
    from LDDC.gui.view.setting import SettingWidget

def _row(*widgets: QWidget) -> QHBoxLayout:
    layout = QHBoxLayout()
    layout.setSpacing(10)
    for widget in widgets:
        layout.addWidget(widget)
    return layout


def refine_local_match(view: "LocalMatchWidget") -> None:
    grid = view.gridLayout
    while grid.count():
        grid.takeAt(0)
    grid.setContentsMargins(16, 14, 16, 14)
    grid.setHorizontalSpacing(12)
    grid.setVerticalSpacing(10)
    view.control_bar.setProperty("role", "card")
    view.control_bar.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
    toolbar = _row(view.select_files_button, view.select_dirs_button, view.save_path_button)
    toolbar.addStretch(1)
    toolbar.addWidget(view.start_cancel_pushButton)
    for button in (view.select_files_button, view.select_dirs_button, view.save_path_button, view.start_cancel_pushButton):
        button.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Fixed)
    grid.addLayout(toolbar, 0, 0, 1, 4)
    for row, fields in enumerate(((view.label_11, view.save_mode_comboBox, view.label, view.save2tag_mode_comboBox),
                                  (view.label_8, view.filename_mode_comboBox, view.label_10, view.lyricsformat_comboBox)), 1):
        for column, widget in enumerate(fields):
            if isinstance(widget, QLabel):
                widget.setProperty("role", "muted")
            else:
                widget.setMinimumWidth(0)
                widget.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
            grid.addWidget(widget, row, column)
    grid.setColumnStretch(1, 1)
    grid.setColumnStretch(3, 1)
    options = _row(view.label_9, view.original_checkBox, view.translate_checkBox, view.romanized_checkBox)
    options.addStretch(1)
    options.addWidget(view.label_3)
    view.min_score_spinBox.setFixedWidth(78)
    options.addWidget(view.min_score_spinBox)
    options.addWidget(view.skip_existing_lyrics_checkbox)
    grid.addLayout(options, 3, 0, 1, 4)
    view.source_listWidget.setMaximumSize(16777215, 44)
    view.source_listWidget.setMinimumHeight(44)
    view.source_listWidget.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
    view.label_2.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Preferred)
    view.source_listWidget.setFlow(QListView.Flow.LeftToRight)
    view.source_listWidget.setWrapping(False)
    sources = _row(view.label_2, view.source_listWidget)
    sources.setStretch(1, 1)
    grid.addLayout(sources, 4, 0, 1, 4)


def refine_batch_convert(view: "BatchConvertWidget") -> None:
    while view.gridLayout.count():
        view.gridLayout.takeAt(0)
    view.gridLayout.setContentsMargins(16, 14, 16, 14)
    view.control_bar.setProperty("role", "card")
    view.control_bar.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
    toolbar = _row(view.select_files_button, view.select_dirs_button, view.save_path_button)
    toolbar.addStretch(1)
    toolbar.addWidget(view.label)
    toolbar.addWidget(view.format_comboBox)
    toolbar.addWidget(view.start_button)
    for button in (view.select_files_button, view.select_dirs_button, view.save_path_button, view.start_button):
        button.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Fixed)
    view.gridLayout.addLayout(toolbar, 0, 0)
    view.gridLayout.addWidget(view.recursive_checkBox, 1, 0)
    view.gridLayout.setVerticalSpacing(10)
    view.label_2.setProperty("role", "muted")


def refine_settings(view: "SettingWidget") -> None:
    # One scrollable column keeps the longer descriptions and API configuration readable.
    grid = view.gridLayout_6
    while grid.count():
        grid.takeAt(0)
    grid.setContentsMargins(0, 0, 8, 0)
    grid.setSpacing(16)
    grid.setSizeConstraint(QLayout.SizeConstraint.SetMinimumSize)
    view.label.setProperty("role", "title")
    for row, widget in enumerate((view.label, view.groupBox, view.groupBox_4, view.groupBox_2,
                                  view.groupBox_3, view.groupBox_6)):
        grid.addWidget(widget, row, 0)
    view.groupBox_5.hide()
    view.groupBox_7.hide()
    misc = view.gridLayout_2
    for old_layout in (misc, view.gridLayout_5):
        while old_layout.count():
            old_layout.takeAt(0)
    misc.setHorizontalSpacing(8)
    misc.setVerticalSpacing(10)
    misc.setSizeConstraint(QLayout.SizeConstraint.SetMinimumSize)
    view.groupBox_6.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Maximum)
    # Six settings share one control row; the checkbox aligns with the dropdowns.
    for column, (label, combo) in enumerate(((view.label_7, view.language_comboBox),
                                            (view.label_2, view.color_scheme_comboBox),
                                            (view.label_5, view.log_level_comboBox),
                                            (view.label_9, view.translate_source_comboBox),
                                            (view.label_17, view.translate_target_lang_comboBox))):
        label.setProperty("role", "muted")
        label.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Preferred)
        combo.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        combo.setMinimumContentsLength(1)
        combo.setSizeAdjustPolicy(QComboBox.SizeAdjustPolicy.AdjustToMinimumContentsLengthWithIcon)
        combo.setToolTip(combo.currentText())
        combo.currentTextChanged.connect(combo.setToolTip)
        misc.addWidget(label, 0, column)
        misc.addWidget(combo, 1, column)
        misc.setColumnStretch(column, 1)
    misc.addWidget(view.auto_check_update_checkBox, 1, 5, Qt.AlignmentFlag.AlignVCenter)
    # Keep the complete provider name visible in the compact settings row.
    view.translate_source_comboBox.setMinimumContentsLength(0)
    view.translate_source_comboBox.setSizeAdjustPolicy(QComboBox.SizeAdjustPolicy.AdjustToContents)
    misc.setColumnStretch(3, 2)
    for combo in (view.language_comboBox, view.color_scheme_comboBox, view.log_level_comboBox,
                  view.translate_target_lang_comboBox):
        combo.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Fixed)
    view.cache_size_label.setWordWrap(False)
    view.cache_size_label.setSizePolicy(QSizePolicy.Policy.Minimum, QSizePolicy.Policy.Fixed)
    actions = _row(view.cache_size_label)
    actions.addStretch(1)
    for button in (view.clear_cache_pushButton, view.open_log_dir_button, view.restore2default_pushButton):
        actions.addWidget(button)
    misc.addLayout(actions, 3, 0, 1, 6)
    view.multi_search_source_list.setMaximumWidth(16777215)
    view.multi_search_source_list.setFixedHeight(44)
    view.multi_search_source_list.setFlow(QListView.Flow.LeftToRight)
    view.multi_search_source_list.setWrapping(False)
    for listing in (view.lang_type_list, view.source_list):
        listing.setMaximumWidth(16777215)
        listing.setMinimumWidth(140)
        listing.setMinimumHeight(120 if listing != view.source_list else 158)
        listing.setMaximumHeight(180)
    for browser in view.findChildren(QTextBrowser):
        browser.setMaximumHeight(16777215)
        browser.setMinimumHeight(124)
    view.gridLayout_4.setContentsMargins(12, 12, 12, 12)

    # Keep translation-length dependent controls on full-width rows.
    lyrics_grid = view.gridLayout
    while lyrics_grid.count():
        lyrics_grid.takeAt(0)
    lyrics_grid.setSpacing(10)
    # The order label must not inherit the width of the longer labels below.
    order_row = _row(view.label_4, view.lyrics_order_buttons)
    order_row.setStretch(1, 1)
    lyrics_grid.addLayout(order_row, 0, 0, 1, 2)
    for row, checkbox in enumerate((view.skip_inst_lyrics_checkBox, view.auto_select_checkBox,
                                    view.add_end_timestamp_line_checkBox), 1):
        lyrics_grid.addWidget(checkbox, row, 0, 1, 2)
    for row, (label, control) in enumerate(((view.label_6, view.lrc_ms_digit_count_spinBox),
                                           (view.label_8, view.last_ref_line_time_sty_comboBox),
                                           (view.label_3, view.lrc_tag_info_src_comboBox)), 4):
        label.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Preferred)
        label.setWordWrap(True)
        lyrics_grid.addWidget(label, row, 0)
        lyrics_grid.addWidget(control, row, 1)
    lyrics_grid.setColumnStretch(1, 1)

    # Empty provider pages must not reserve the API form's height.
    translation = view.gridLayout_7
    while translation.count():
        translation.takeAt(0)
    misc.addWidget(view.translate_cfg_stackedWidget, 2, 0, 1, 6)
    view.translate_cfg_stackedWidget.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Minimum)
    while view.gridLayout_8.count():
        view.gridLayout_8.takeAt(0)
    for column, (label, field) in enumerate(((view.label_14, view.oai_base_url_lineEdit),
                                             (view.label_20, view.oai_key_lineEdit),
                                             (view.label_21, view.oai_model_lineEdit))):
        label.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Preferred)
        field.setMinimumWidth(80)
        field.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        view.gridLayout_8.addWidget(label, 0, column * 2)
        view.gridLayout_8.addWidget(field, 0, column * 2 + 1)
        view.gridLayout_8.setColumnStretch(column * 2 + 1, 3 if column < 2 else 2)
    view.gridLayout_8.setSizeConstraint(QLayout.SizeConstraint.SetMinimumSize)
    view.gridLayout_8.setContentsMargins(0, 6, 0, 0)
    view.gridLayout_8.setHorizontalSpacing(8)
    view.gridLayout_8.setVerticalSpacing(10)

    def update_translation_form(_index: int = 0) -> None:
        page = view.translate_cfg_stackedWidget.currentWidget()
        view.translate_cfg_stackedWidget.setVisible(page is not None and page.layout() is not None)
        view.groupBox_6.updateGeometry()

    view.translate_cfg_stackedWidget.currentChanged.connect(update_translation_form)
    update_translation_form()

    # The original desktop settings used eight columns of fixed-size controls.
    # Group related controls vertically so they also fit a laptop-sized window.
    desktop = view.gridLayout_3
    while desktop.count():
        desktop.takeAt(0)
    desktop.setSpacing(12)
    blocks = (
        (view.label_11, view.played_color_list, (view.played_add_color_button, view.played_del_color_button)),
        (view.label_12, view.unplayed_color_list, (view.unplayed_add_color_button, view.unplayed_del_color_button)),
        (view.label_13, view.lang_type_list, ()),
        (view.label_16, view.source_list, ()),
    )
    for column, (label, listing, buttons) in enumerate(blocks):
        block = QWidget(view.groupBox_3)
        layout = QVBoxLayout(block)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)
        layout.addWidget(label)
        listing.setMinimumSize(120, 158)
        listing.setMaximumSize(16777215, 158)
        listing.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        layout.addWidget(listing)
        if buttons:
            for button in buttons:
                button.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Fixed)
            layout.addLayout(_row(*buttons))
        else:
            layout.addStretch(1)
        desktop.addWidget(block, 0, column)
        desktop.setColumnStretch(column, 1)
    appearance = _row(view.label_10, view.font_comboBox, view.ui_font_size_label, view.ui_font_size_comboBox,
                      view.label_15, view.frame_rate_spinBox, view.auto_frame_rate_checkBox)
    appearance.setStretch(1, 1)
    appearance.setSpacing(8)
    for control in (view.ui_font_size_comboBox, view.frame_rate_spinBox, view.auto_frame_rate_checkBox):
        control.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
    view.font_comboBox.setMinimumWidth(0)
    view.font_comboBox.setMinimumContentsLength(4)
    view.font_comboBox.setSizeAdjustPolicy(QComboBox.SizeAdjustPolicy.AdjustToMinimumContentsLengthWithIcon)
    view.font_comboBox.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
    desktop.addLayout(appearance, 1, 0, 1, 4)
    desktop.addWidget(view.label_18, 2, 0, 1, 4)
    desktop.addWidget(view.show_local_song_lyrics_db_manager_button, 3, 0, 1, 4, Qt.AlignmentFlag.AlignLeft)
