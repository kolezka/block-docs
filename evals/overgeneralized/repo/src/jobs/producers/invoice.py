from jobs.queue import enqueue


def request_invoice(invoice_id, customer_id):
    return enqueue(
        "render_invoice",
        {"invoice_id": invoice_id, "customer_id": customer_id},
        dedupe_key="invoice:{}".format(invoice_id),
    )
