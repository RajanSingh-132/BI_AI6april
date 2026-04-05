import numpy as np

def total_leads(context):
    return context.get("leads")


def lead_conversion_rate(context):
    conversions = context.get("conversions")
    leads = context.get("leads")

    if not leads:
        return None

    return round((conversions / leads) * 100, 2)


def lead_contribution(context, global_context):
    leads = context.get("leads")
    total_leads = global_context.get("leads")

    if not total_leads:
        return None

    return round((leads / total_leads) * 100, 2)


def lead_quality(context):
    conversions = context.get("conversions")
    leads = context.get("leads")

    if not leads:
        return None

    return round(conversions / leads, 2)