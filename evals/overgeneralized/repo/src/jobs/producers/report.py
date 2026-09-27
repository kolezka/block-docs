from jobs.queue import enqueue


def schedule_report(report_id, period):
    payload = {"report_id": report_id, "period": period}
    return enqueue("build_report", payload)
