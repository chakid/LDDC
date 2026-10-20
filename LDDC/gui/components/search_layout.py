# SPDX-FileCopyrightText: Copyright (C) 2024-2025 沉默の金 <cmzj@cmzj.org>
# SPDX-License-Identifier: GPL-3.0-only
"""Layout refinements applied after the generated search form is constructed."""

from typing import TYPE_CHECKING

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QSizePolicy

from .custom_widgets import RowSelectionDelegate
from .theme import primary_button

if TYPE_CHECKING:
    from LDDC.gui.view.search import SearchWidgetBase


def refine_search_layout(view: "SearchWidgetBase") -> None:
    view.verticalLayout.setContentsMargins(24, 24, 24, 24)
    view.verticalLayout.setSpacing(14)
    view.horizontalLayout.setSpacing(10)
    # Remove the generated fixed gaps: the keyword field should use the available width.
    for spacer in (view.horizontalSpacer, view.horizontalSpacer_2):
        view.horizontalLayout.removeItem(spacer)
    view.source_comboBox.setMinimumWidth(122)
    view.search_type_comboBox.setMinimumWidth(90)
    view.search_keyword_lineEdit.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
    view.search_keyword_lineEdit.setClearButtonEnabled(True)
    view.horizontalLayout.setStretchFactor(view.search_keyword_lineEdit, 1)
    view.search_pushButton.setMinimumWidth(96)
    primary_button(view.search_pushButton)

    view.splitter.setHandleWidth(14)
    view.splitter.setStretchFactor(0, 6)
    view.splitter.setStretchFactor(1, 5)
    view.splitter.setSizes([540, 450])
    for panel, layout in ((view.layoutWidget_2, view.verticalLayout_3), (view.layoutWidget_3, view.verticalLayout_8)):
        panel.setProperty("role", "card")
        panel.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        panel.setMinimumWidth(280)
        layout.setContentsMargins(14, 14, 14, 14)
        layout.setSpacing(10)
    for label in (view.result_label, view.label_8):
        label.setProperty("role", "section")
        label.setFixedHeight(26)
    view.verticalLayout_3.setAlignment(view.return_toolButton, Qt.AlignmentFlag.AlignLeft)
    view.return_toolButton.setMaximumWidth(100)
    view.return_toolButton.setFixedHeight(34)
    view.lyric_langs_lineEdit.setFixedHeight(34)
    view.songid_lineEdit.setFixedHeight(34)
    view.songid_lineEdit.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
    view.horizontalLayout_5.setSpacing(6)
    view.horizontalLayout_5.setStretch(1, 2)
    view.horizontalLayout_5.setStretch(3, 1)
    view.label_2.setProperty("role", "muted")
    view.label_3.setProperty("role", "muted")
    view.results_tableWidget.setAlternatingRowColors(True)
    view.results_tableWidget.setItemDelegate(RowSelectionDelegate(view.results_tableWidget))
    view.results_tableWidget.verticalHeader().setDefaultSectionSize(40)
    view.results_tableWidget.horizontalHeader().setHighlightSections(False)
