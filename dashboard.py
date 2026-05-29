from __future__ import annotations

import pandas as pd
import streamlit as st

from padea_ops.db import get_client, fetch_all


st.set_page_config(page_title="Padea Catering Ops", layout="wide")

client = get_client()

st.title("Padea Catering Operations")
st.caption("Prototype coordinator dashboard for weekly catering orders, exceptions, and confirmation status.")


def df(table: str, **kwargs) -> pd.DataFrame:
    rows = fetch_all(client, table, **kwargs)
    return pd.DataFrame(rows)


orders = df("orders")
exceptions = df("exceptions")

col1, col2, col3, col4, col5 = st.columns(5)

if not orders.empty and "status" in orders.columns:
    statuses = orders["status"].fillna("unknown")

    active_orders = orders[~statuses.isin(["cancelled", "delivered"])]
    review_count = statuses.isin(["draft", "ready_for_review", "needs_review"]).sum()
    sent_count = (statuses == "sent_to_caterer").sum()
    overdue_count = statuses.isin(["confirmation_overdue", "backup_required"]).sum()
    confirmed_count = (statuses == "confirmed").sum()

    col1.metric("Orders", len(orders))
    col2.metric("Awaiting review", int(review_count))
    col3.metric("Sent / awaiting confirmation", int(sent_count))
    col4.metric("Needs escalation", int(overdue_count))
    col5.metric("Confirmed", int(confirmed_count))
else:
    col1.metric("Orders", 0)
    col2.metric("Awaiting review", 0)
    col3.metric("Sent / awaiting confirmation", 0)
    col4.metric("Needs escalation", 0)
    col5.metric("Confirmed", 0)
    
st.divider()

st.subheader("Orders by status")

if not orders.empty:
    status_filter = st.multiselect(
        "Filter statuses",
        sorted(orders["status"].dropna().unique()),
        default=sorted(orders["status"].dropna().unique()),
    )

    visible_orders = orders[orders["status"].isin(status_filter)]

    st.dataframe(
        visible_orders[
            [
                "order_id",
                "session_id",
                "caterer_id",
                "delivery_date",
                "status",
                "generated_at",
                "approved_at",
                "sent_at",
                "confirmation_due_at",
                "confirmed_at",
                "backup_for_order_id",
                "failure_reason",
                "exception_count",
            ]
        ],
        use_container_width=True,
        hide_index=True,
    )
else:
    st.info("No orders found.")

st.divider()

st.subheader("Open exceptions")

if not exceptions.empty:
    base_exceptions = exceptions[exceptions["status"] == "open"] if "status" in exceptions else exceptions
    base_exceptions = base_exceptions.copy()

    severity_order = {
        "critical": 0,
        "high": 1,
        "medium": 2,
        "warning": 3,
        "low": 4,
        "info": 5,
    }

    filter_col1, filter_col2, filter_col3, filter_col4 = st.columns(4)

    with filter_col1:
        hide_date_mismatch = st.checkbox(
            "Hide date/day mismatch",
            value=True,
            key="exceptions_hide_date_mismatch_v2",
        )

    with filter_col2:
        entity_options = (
            sorted(base_exceptions["entity_type"].dropna().unique())
            if "entity_type" in base_exceptions.columns
            else []
        )

        selected_entity_types = st.multiselect(
            "Entity type",
            entity_options,
            default=[],
            key="exceptions_entity_type_filter_v2",
            help="Leave empty to show all entity types.",
        )

    with filter_col3:
        exception_type_options = (
            sorted(base_exceptions["exception_type"].dropna().unique())
            if "exception_type" in base_exceptions.columns
            else []
        )

        selected_exception_types = st.multiselect(
            "Exception type",
            exception_type_options,
            default=[],
            key="exceptions_exception_type_filter_v2",
            help="Leave empty to show all exception types.",
        )

    with filter_col4:
        severity_options = (
            sorted(
                base_exceptions["severity"].dropna().unique(),
                key=lambda x: severity_order.get(x, 99),
            )
            if "severity" in base_exceptions.columns
            else []
        )

        selected_severities = st.multiselect(
            "Severity",
            severity_options,
            default=[],
            key="exceptions_severity_filter_v2",
            help="Leave empty to show all severities.",
        )

    visible_exceptions = base_exceptions.copy()

    if hide_date_mismatch and "exception_type" in visible_exceptions.columns:
        visible_exceptions = visible_exceptions[
            visible_exceptions["exception_type"] != "date_day_mismatch"
        ]

    if selected_entity_types and "entity_type" in visible_exceptions.columns:
        visible_exceptions = visible_exceptions[
            visible_exceptions["entity_type"].isin(selected_entity_types)
        ]

    if selected_exception_types and "exception_type" in visible_exceptions.columns:
        visible_exceptions = visible_exceptions[
            visible_exceptions["exception_type"].isin(selected_exception_types)
        ]

    if selected_severities and "severity" in visible_exceptions.columns:
        visible_exceptions = visible_exceptions[
            visible_exceptions["severity"].isin(selected_severities)
        ]

    if "severity" in visible_exceptions.columns:
        visible_exceptions["_severity_rank"] = (
            visible_exceptions["severity"]
            .map(severity_order)
            .fillna(99)
        )
        visible_exceptions = visible_exceptions.sort_values("_severity_rank")

    display_columns = [
        "severity",
        "exception_type",
        "entity_type",
        "entity_id",
        "message",
        "source",
        "status",
    ]

    display_columns = [
        col for col in display_columns
        if col in visible_exceptions.columns
    ]

    if visible_exceptions.empty:
        st.success("No open exceptions match the current filters.")
    else:
        st.dataframe(
            visible_exceptions[display_columns],
            use_container_width=True,
            hide_index=True,
        )
else:
    st.success("No exceptions found.")

st.divider()

st.subheader("Backup-required orders")

if not orders.empty and "status" in orders:
    backup_orders = orders[orders["status"].isin(["confirmation_overdue", "backup_required"])]

    if backup_orders.empty:
        st.success("No backup escalation currently required.")
    else:
        st.warning(f"{len(backup_orders)} orders need backup attention.")
        st.dataframe(backup_orders, use_container_width=True, hide_index=True)